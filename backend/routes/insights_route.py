"""API endpoints for insights and push subscriptions."""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models import InsightsListResponse
from insights.store import InsightStore
from insights.scoping import filter_by_role_scope
from assistant.prompt_builder import load_role

log = logging.getLogger(__name__)

router = APIRouter()

_STORE_PATH = Path(__file__).parent.parent.parent / "data" / "insights.json"
_SUBS_PATH = Path(__file__).parent.parent.parent / "data" / "push_subscriptions.json"
_DEFAULT_USER_ID = "demo_analyst"
_DEFAULT_ROLE = "default"

# User-to-role mapping for mock auth
_USER_ROLES = {
    "demo_analyst": "default",
    "demo_cfo": "cfo",
    "demo_commercial": "commercial",
    "demo_market_lead": "market_lead",
}


def _resolve_user(x_user_id: str | None) -> tuple[str, str]:
    """Resolve user ID and role from header."""
    user_id = x_user_id or _DEFAULT_USER_ID
    role_id = _USER_ROLES.get(user_id, _DEFAULT_ROLE)
    return user_id, role_id


@router.get("/insights")
def list_insights(
    sort: str = Query("date", pattern="^(date|severity)$"),
    status: str = Query("active", pattern="^(active|inactive|all)$"),
    limit: int = Query(50, ge=1, le=200),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    user_id, role_id = _resolve_user(x_user_id)
    role = load_role(role_id)
    scope = role.get("insight_scope", {
        "revenue": ["brand", "ta", "total"],
        "expenses": ["sub_unit", "unit", "total"],
        "market": ["brand_market"],
    })

    store = InsightStore(_STORE_PATH)
    insights = store.load_all()

    # Filter by status
    if status != "all":
        insights = [i for i in insights if i.get("status") == status]

    # Filter by role scope
    insights = filter_by_role_scope(insights, scope)

    # Sort
    severity_order = {"critical": 0, "notable": 1, "informational": 2}
    if sort == "severity":
        insights.sort(key=lambda i: severity_order.get(i.get("severity", ""), 3))
    else:
        insights.sort(key=lambda i: i.get("detected_at", ""), reverse=True)

    # Count before limiting
    unread = [i for i in insights if not i.get("read")]
    unread_critical = [i for i in unread if i.get("severity") == "critical"]

    return InsightsListResponse(
        insights=insights[:limit],
        unread_count=len(unread),
        unread_critical_count=len(unread_critical),
    )


@router.post("/insights/{insight_id}/read")
def mark_read(insight_id: str):
    store = InsightStore(_STORE_PATH)
    found = store.mark_read(insight_id)
    return {"ok": found}


@router.get("/insights/stream")
async def stream_insights(
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """SSE endpoint — pushes insight updates when data/insights.json changes."""
    user_id, role_id = _resolve_user(x_user_id)
    role = load_role(role_id)
    scope = role.get("insight_scope", {
        "revenue": ["brand", "ta", "total"],
        "expenses": ["sub_unit", "unit", "total"],
        "market": ["brand_market"],
    })

    async def event_generator():
        last_mtime = 0.0
        while True:
            try:
                current_mtime = _STORE_PATH.stat().st_mtime if _STORE_PATH.exists() else 0.0
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    store = InsightStore(_STORE_PATH)
                    insights = store.load_all()
                    insights = [i for i in insights if i.get("status") == "active"]
                    insights = filter_by_role_scope(insights, scope)
                    severity_order = {"critical": 0, "notable": 1, "informational": 2}
                    insights.sort(key=lambda i: i.get("detected_at", ""), reverse=True)

                    unread = [i for i in insights if not i.get("read")]
                    unread_critical = [i for i in unread if i.get("severity") == "critical"]

                    data = {
                        "insights": insights[:50],
                        "unread_count": len(unread),
                        "unread_critical_count": len(unread_critical),
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                else:
                    yield ": heartbeat\n\n"

                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/insights/{insight_id}/chat")
def insight_to_chat(insight_id: str):
    """Return insight as an AssistantContext-compatible object."""
    store = InsightStore(_STORE_PATH)
    insights = store.load_all()
    ins = next((i for i in insights if i["id"] == insight_id), None)
    if not ins:
        raise HTTPException(status_code=404, detail="Insight not found")

    entity = ins.get("entity", {})
    etype = entity.get("type", "")

    # Resolve node_id and node_name for all entity types
    if etype == "brand":
        node_id = entity.get("brand_id", "")
        node_name = entity.get("brand_id", "")
    elif etype == "ta":
        node_id = entity.get("ta", "")
        node_name = entity.get("ta", "")
    elif etype == "unit":
        node_id = entity.get("unit", "")
        node_name = entity.get("unit", "")
    elif etype == "sub_unit":
        node_id = entity.get("sub_unit", "")
        node_name = entity.get("sub_unit", "")
    elif etype == "brand_market":
        node_id = entity.get("brand_id", "")
        node_name = f"{entity.get('brand_id', '')} {entity.get('market_id', '')}".strip()
    elif etype == "total":
        node_id = "total"
        node_name = "Total"
    else:
        node_id = ""
        node_name = ""

    current_year = datetime.now(timezone.utc).year

    return {
        "source": "insight",
        "page": "overview",
        "period": {"year": current_year, "quarter": None},
        "dataPoint": {
            "node_id": node_id,
            "node_name": node_name,
            "insight_id": ins["id"],
            "detection_type": ins["detection_type"],
            "severity": ins.get("severity", ""),
            "explanation": (ins.get("ai_analysis") or {}).get("explanation", ""),
            "raw_stats": ins.get("raw_stats", {}),
        },
    }


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionInfo(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class PushSubscribeRequest(BaseModel):
    subscription: PushSubscriptionInfo


@router.post("/push/subscribe")
def push_subscribe(
    body: PushSubscribeRequest,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    user_id, role_id = _resolve_user(x_user_id)
    subs = _load_subs()

    # Remove existing subscription for this user
    subs = [s for s in subs if s["user_id"] != user_id]
    subs.append({
        "user_id": user_id,
        "role": role_id,
        "subscription": body.subscription.model_dump(),
    })
    _save_subs(subs)
    return {"ok": True}


@router.post("/push/unsubscribe")
def push_unsubscribe(
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    user_id, _ = _resolve_user(x_user_id)
    subs = _load_subs()
    subs = [s for s in subs if s["user_id"] != user_id]
    _save_subs(subs)
    return {"ok": True}


def _load_subs() -> list[dict]:
    if not _SUBS_PATH.exists():
        return []
    try:
        return json.loads(_SUBS_PATH.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_subs(subs: list[dict]):
    _SUBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=_SUBS_PATH.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(subs, f, indent=2)
        os.replace(tmp, _SUBS_PATH)
    except BaseException:
        os.unlink(tmp)
        raise

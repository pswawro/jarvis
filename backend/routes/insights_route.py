"""API endpoints for insights and push subscriptions."""

import asyncio
import fcntl
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models import InsightsListResponse
from insights.store import InsightStore
from insights.scoping import filter_by_role_scope
from assistant.prompt_builder import load_role
from user_preferences import UserPreferencesStore

log = logging.getLogger(__name__)

router = APIRouter()

_STORE_PATH = Path(__file__).parent.parent.parent / "data" / "insights.json"
_PREFS_PATH = Path(__file__).parent.parent.parent / "data" / "user_preferences.json"
_SUBS_PATH = Path(__file__).parent.parent.parent / "data" / "push_subscriptions.json"
_DEFAULT_USER_ID = "demo_analyst"
_DEFAULT_ROLE = "default"

_DEFAULT_SCOPE = {
    "revenue": ["brand", "ta", "total"],
    "expenses": ["sub_unit", "unit", "total"],
    "market": ["brand_market"],
}

# User-to-role mapping for mock auth
_USER_ROLES = {
    "demo_analyst": "default",
    "demo_cfo": "cfo",
    "demo_commercial": "commercial",
    "demo_market_lead": "market_lead",
}

_prefs_store = UserPreferencesStore(_PREFS_PATH)


def _resolve_user(x_user_id: str | None) -> tuple[str, str]:
    """Resolve user ID and role from header."""
    user_id = x_user_id or _DEFAULT_USER_ID
    role_id = _USER_ROLES.get(user_id, _DEFAULT_ROLE)
    return user_id, role_id


def _get_file_mtime_ns(path: Path) -> int:
    """Get file modification time in nanoseconds, 0 if file doesn't exist."""
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:
        return 0


@router.get("/insights")
def list_insights(
    sort: str = Query("date", pattern="^(date|severity)$"),
    status: str = Query("active", pattern="^(active|inactive|all)$"),
    limit: int = Query(50, ge=1, le=200),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    user_id, role_id = _resolve_user(x_user_id)
    role = load_role(role_id)
    scope = role.get("insight_scope", _DEFAULT_SCOPE)

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
        insights.sort(key=lambda i: (
            severity_order.get(i.get("severity", ""), 3),
            i.get("detected_at", ""),
        ))
    else:
        insights.sort(key=lambda i: i.get("detected_at", ""), reverse=True)

    # Inject bookmarked state
    bookmarks = set(_prefs_store.get_bookmarks(user_id))
    for ins in insights:
        ins["bookmarked"] = ins["id"] in bookmarks

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


@router.post("/insights/{insight_id}/bookmark")
def bookmark_insight(
    insight_id: str,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    # Validate insight exists
    store = InsightStore(_STORE_PATH)
    ins = next((i for i in store.load_all() if i["id"] == insight_id), None)
    if not ins:
        raise HTTPException(status_code=404, detail="Insight not found")

    user_id, _ = _resolve_user(x_user_id)
    _prefs_store.add_bookmark(user_id, insight_id)
    return {"ok": True}


@router.post("/insights/{insight_id}/unbookmark")
def unbookmark_insight(
    insight_id: str,
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    user_id, _ = _resolve_user(x_user_id)
    _prefs_store.remove_bookmark(user_id, insight_id)
    return {"ok": True}


@router.get("/insights/stream")
async def stream_insights(
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """SSE endpoint — pushes insight updates when data files change."""
    user_id, role_id = _resolve_user(x_user_id)
    role = load_role(role_id)
    scope = role.get("insight_scope", _DEFAULT_SCOPE)

    async def event_generator():
        last_insights_mtime = 0
        last_prefs_mtime = 0
        deadline = time.monotonic() + 30 * 60  # 30-minute timeout
        while time.monotonic() < deadline:
            try:
                insights_mtime = _get_file_mtime_ns(_STORE_PATH)
                prefs_mtime = _get_file_mtime_ns(_PREFS_PATH)
                changed = (insights_mtime != last_insights_mtime or prefs_mtime != last_prefs_mtime)

                if changed:
                    last_insights_mtime = insights_mtime
                    last_prefs_mtime = prefs_mtime
                    store = InsightStore(_STORE_PATH)
                    insights = store.load_all()
                    insights = [i for i in insights if i.get("status") == "active"]
                    insights = filter_by_role_scope(insights, scope)
                    insights.sort(key=lambda i: i.get("detected_at", ""), reverse=True)

                    # Inject bookmarked state
                    bookmarks = set(_prefs_store.get_bookmarks(user_id))
                    for ins in insights:
                        ins["bookmarked"] = ins["id"] in bookmarks

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
            except Exception:
                log.exception("SSE stream error")
                yield f"event: error\ndata: {{\"message\": \"Internal error\"}}\n\n"
                await asyncio.sleep(5)

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
    lock_fd = _acquire_subs_lock()
    try:
        subs = _load_subs()
        # Remove existing subscription for this user
        subs = [s for s in subs if s["user_id"] != user_id]
        subs.append({
            "user_id": user_id,
            "role": role_id,
            "subscription": body.subscription.model_dump(),
        })
        _save_subs(subs)
    finally:
        _release_subs_lock(lock_fd)
    return {"ok": True}


@router.post("/push/unsubscribe")
def push_unsubscribe(
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    user_id, _ = _resolve_user(x_user_id)
    lock_fd = _acquire_subs_lock()
    try:
        subs = _load_subs()
        subs = [s for s in subs if s["user_id"] != user_id]
        _save_subs(subs)
    finally:
        _release_subs_lock(lock_fd)
    return {"ok": True}


_SUBS_LOCK_PATH = _SUBS_PATH.with_suffix(".lock")


def _acquire_subs_lock():
    _SUBS_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = open(_SUBS_LOCK_PATH, "w")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release_subs_lock(fd):
    fcntl.flock(fd, fcntl.LOCK_UN)
    fd.close()


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
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

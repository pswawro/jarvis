"""Web Push notification delivery."""

import json
import logging
from pathlib import Path

import config

log = logging.getLogger(__name__)

_SUBS_PATH = Path(__file__).parent.parent.parent / "data" / "push_subscriptions.json"


def _load_subs() -> list[dict]:
    if not _SUBS_PATH.exists():
        return []
    try:
        return json.loads(_SUBS_PATH.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def send_push_for_insights(insights: list[dict], role_scopes: dict[str, dict]) -> int:
    """Send push notifications for push-eligible insights.

    Args:
        insights: list of insight dicts with push=True
        role_scopes: mapping of role_id -> insight_scope config

    Returns: number of notifications sent
    """
    if not config.VAPID_PRIVATE_KEY:
        log.warning("VAPID_PRIVATE_KEY not set — skipping push notifications")
        return 0

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        log.warning("pywebpush not installed — skipping push notifications")
        return 0

    subs = _load_subs()
    if not subs:
        log.info("No push subscriptions registered")
        return 0

    from insights.scoping import filter_by_role_scope

    vapid_claims = {"sub": f"mailto:{config.VAPID_CLAIMS_EMAIL}"}
    sent = 0

    for sub in subs:
        role_id = sub.get("role", "default")
        scope = role_scopes.get(role_id, {})

        # Filter insights this user should see
        visible = filter_by_role_scope(insights, scope)
        push_eligible = [i for i in visible if i.get("push")]

        for insight in push_eligible:
            payload = json.dumps({
                "title": "Jarvis Insight",
                "body": insight.get("ai_analysis", {}).get("explanation", "New insight detected")[:200],
                "severity": insight.get("severity", "notable"),
                "insight_id": insight["id"],
            })

            try:
                webpush(
                    subscription_info=sub["subscription"],
                    data=payload,
                    vapid_private_key=config.VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims,
                )
                sent += 1
                log.info("Push sent to %s for insight %s", sub["user_id"], insight["id"])
            except WebPushException as e:
                log.error("Push failed for %s: %s", sub["user_id"], e)
            except Exception as e:
                log.error("Unexpected push error for %s: %s", sub["user_id"], e)

    return sent

"""Fingerprinting and deduplication for detected anomalies."""

from datetime import datetime, timezone


def make_fingerprint(anomaly: dict) -> str:
    """Create a stable fingerprint from entity + domain + detection type."""
    entity = anomaly["entity"]
    etype = entity["type"]
    detection = anomaly["detection_type"]
    domain = anomaly["data_domain"]

    parts = [etype]
    # Add identifying fields based on entity type
    if etype == "brand":
        parts.append(entity.get("brand_id", ""))
        if entity.get("market_id"):
            parts.append(entity["market_id"])
    elif etype == "ta":
        parts.append(entity.get("ta", ""))
    elif etype == "total":
        pass  # just "total"
    elif etype == "unit":
        parts.append(entity.get("unit", ""))
    elif etype == "sub_unit":
        parts.append(entity.get("sub_unit", ""))
    elif etype == "brand_market":
        parts.append(entity.get("brand_id", ""))
        parts.append(entity.get("market_id", ""))

    parts.append(domain)
    parts.append(detection)
    return "_".join(p for p in parts if p)


def deduplicate(
    anomalies: list[dict],
    existing_insights: list[dict],
    escalation_factor: float = 1.3,
) -> tuple[list[dict], list[dict], set[str]]:
    """Compare new anomalies against existing insights.

    Returns:
        new: anomalies that have no matching active insight
        updated: existing insights that were escalated (severity worsened)
        seen_fingerprints: all fingerprints from this detection run
    """
    now = datetime.now(timezone.utc).isoformat()
    active_by_fp = {
        ins["fingerprint"]: ins
        for ins in existing_insights
        if ins.get("status") == "active"
    }

    new = []
    updated = []
    seen_fps = set()

    for anomaly in anomalies:
        fp = make_fingerprint(anomaly)
        seen_fps.add(fp)

        if fp in active_by_fp:
            existing = active_by_fp[fp]
            existing["last_seen"] = now

            # Escalate if significantly worse (floor of 0.1 prevents 0*factor=0 always escalating)
            prev_score = max(existing.get("statistical_score", 0), 0.1)
            if anomaly["statistical_score"] > prev_score * escalation_factor:
                existing["statistical_score"] = anomaly["statistical_score"]
                existing["read"] = False  # re-flag as unread
                existing["raw_stats"] = anomaly.get("raw_stats", existing.get("raw_stats"))
                updated.append(existing)
        else:
            new.append(anomaly)

    return new, updated, seen_fps

"""Insight detection trigger script.

Usage: cd backend && python -m insights.run
"""

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend is on sys.path when run as module
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import data_loader
from insights.config import load_sensitivity_profile
from insights.detector import detect_outliers, detect_drift, detect_target_misses, detect_competitive_shifts
from insights.dedup import make_fingerprint, deduplicate
from insights.analyzer import analyze_insight
from insights.store import InsightStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

STORE_PATH = Path(__file__).parent.parent.parent / "data" / "insights.json"


def _make_insight(anomaly: dict, run_id: str, ai_result: dict | None, profile: dict) -> dict:
    """Build a full insight record from an anomaly and optional AI analysis."""
    now = datetime.now(timezone.utc).isoformat()
    fp = make_fingerprint(anomaly)

    if ai_result:
        severity = ai_result["revised_severity"]
        push = ai_result["push"]
    else:
        # Fallback: assign severity from statistical score
        score = anomaly.get("statistical_score", 0)
        if score >= profile["zscore_critical"]:
            severity = "critical"
        elif score >= profile["zscore_notable"]:
            severity = "notable"
        else:
            severity = "informational"
        push = False

    return {
        "id": f"ins_{uuid.uuid4().hex[:8]}",
        "fingerprint": fp,
        "detected_at": now,
        "last_seen": now,
        "run_id": run_id,
        "entity": anomaly["entity"],
        "detection_type": anomaly["detection_type"],
        "data_domain": anomaly.get("data_domain", ""),
        "statistical_score": anomaly.get("statistical_score", 0),
        "status": "active",
        "read": False,
        "push": push,
        "severity": severity,
        "ai_analysis": ai_result,
        "raw_stats": anomaly.get("raw_stats", {}),
    }


def run():
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    log.info("=== Insight detection run: %s ===", run_id)

    # Load data
    data_loader.load_all()
    profile = load_sensitivity_profile()
    threshold = profile["zscore_notable"]
    log.info("Profile: %s (threshold=%.1f)", profile, threshold)

    # Run all detectors
    all_anomalies = []

    # Revenue outliers & drift by brand+market
    rev = data_loader.revenue
    all_anomalies.extend(detect_outliers(
        rev, "revenue", "brand", ["brand_id", "market_id"], profile, "revenue"))
    all_anomalies.extend(detect_drift(
        rev, "revenue", "brand", ["brand_id", "market_id"], profile, "revenue"))

    # Revenue by TA (aggregate)
    rev_by_ta = rev.merge(data_loader.products[["brand_id", "therapeutic_area"]], on="brand_id")
    ta_monthly = rev_by_ta.groupby(["period_date", "therapeutic_area"]).agg(
        revenue=("revenue", "sum")).reset_index()
    ta_monthly.rename(columns={"therapeutic_area": "ta"}, inplace=True)
    all_anomalies.extend(detect_outliers(
        ta_monthly, "revenue", "ta", ["ta"], profile, "revenue"))
    all_anomalies.extend(detect_drift(
        ta_monthly, "revenue", "ta", ["ta"], profile, "revenue"))

    # Revenue total
    total_monthly = rev.groupby("period_date").agg(revenue=("revenue", "sum")).reset_index()
    total_monthly["_total"] = "total"
    all_anomalies.extend(detect_outliers(
        total_monthly, "revenue", "total", ["_total"], profile, "revenue"))
    all_anomalies.extend(detect_drift(
        total_monthly, "revenue", "total", ["_total"], profile, "revenue"))

    # Target misses (revenue vs budget)
    # Targets CSV uses entity_id, not brand_id — rename for merge compatibility
    tgt = data_loader.targets.rename(columns={"entity_id": "brand_id"})
    all_anomalies.extend(detect_target_misses(
        rev, tgt, "revenue", "budget_amount", "brand", ["brand_id", "market_id"], profile))

    # Expense outliers & drift by sub_unit
    # Expenses CSV uses sub_unit_id and total_operating_expenses columns
    exp = data_loader.expenses
    all_anomalies.extend(detect_outliers(
        exp, "total_operating_expenses", "sub_unit", ["sub_unit_id"], profile, "expenses"))
    all_anomalies.extend(detect_drift(
        exp, "total_operating_expenses", "sub_unit", ["sub_unit_id"], profile, "expenses"))

    # Expense by unit (aggregate) — join with organization to get unit column
    exp_with_unit = exp.merge(
        data_loader.organization[["sub_unit_id", "unit"]], on="sub_unit_id", how="left")
    unit_monthly = exp_with_unit.groupby(["period_date", "unit"]).agg(
        total_operating_expenses=("total_operating_expenses", "sum")).reset_index()
    all_anomalies.extend(detect_outliers(
        unit_monthly, "total_operating_expenses", "unit", ["unit"], profile, "expenses"))
    all_anomalies.extend(detect_drift(
        unit_monthly, "total_operating_expenses", "unit", ["unit"], profile, "expenses"))

    # Competitive shifts
    all_anomalies.extend(detect_competitive_shifts(data_loader.commercial, profile))

    log.info("Detected %d raw anomalies", len(all_anomalies))

    # Dedup against existing insights
    store = InsightStore(STORE_PATH)
    existing = store.load_all()
    new_anomalies, escalated, seen_fps = deduplicate(all_anomalies, existing)

    log.info("After dedup: %d new, %d escalated", len(new_anomalies), len(escalated))

    # Separate above/below threshold
    above = [a for a in new_anomalies if a.get("statistical_score", 0) >= threshold]
    below = [a for a in new_anomalies if a.get("statistical_score", 0) < threshold]

    log.info("Above threshold (will analyze): %d, Below (informational): %d", len(above), len(below))

    # AI analysis for above-threshold anomalies
    new_insights = []
    for anomaly in above:
        log.info("Analyzing: %s", make_fingerprint(anomaly))
        ai_result = analyze_insight(anomaly)
        new_insights.append(_make_insight(anomaly, run_id, ai_result, profile))

    # Below threshold: store as informational without AI
    for anomaly in below:
        new_insights.append(_make_insight(anomaly, run_id, None, profile))

    # Re-analyze escalated insights
    for ins in escalated:
        log.info("Re-analyzing escalated: %s", ins["fingerprint"])
        ai_result = analyze_insight(ins)
        if ai_result:
            ins["ai_analysis"] = ai_result
            ins["severity"] = ai_result["revised_severity"]
            ins["push"] = ai_result["push"]

    # Transition inactive
    inactive_count = 0
    for ins in existing:
        if ins["status"] == "active" and ins["fingerprint"] not in seen_fps:
            ins["status"] = "inactive"
            inactive_count += 1

    # Merge and save
    all_insights = existing + new_insights
    store.save_all(all_insights)

    log.info("=== Run complete: %d new, %d escalated, %d inactive ===",
             len(new_insights), len(escalated), inactive_count)

    return {
        "run_id": run_id,
        "detected": len(all_anomalies),
        "new": len(new_insights),
        "escalated": len(escalated),
        "inactive": inactive_count,
    }


if __name__ == "__main__":
    run()

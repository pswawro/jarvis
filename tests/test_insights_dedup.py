"""Tests for insight fingerprinting and deduplication."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from insights.dedup import make_fingerprint, deduplicate


def test_fingerprint_brand_outlier():
    anomaly = {
        "entity": {"type": "brand", "brand_id": "TAGRISSO", "market_id": "US"},
        "detection_type": "outlier",
        "data_domain": "revenue",
    }
    fp = make_fingerprint(anomaly)
    assert fp == "brand_TAGRISSO_US_revenue_outlier"


def test_fingerprint_ta_drift():
    anomaly = {
        "entity": {"type": "ta", "ta": "Oncology"},
        "detection_type": "drift",
        "data_domain": "revenue",
    }
    fp = make_fingerprint(anomaly)
    assert fp == "ta_Oncology_revenue_drift"


def test_fingerprint_unit_target_miss():
    anomaly = {
        "entity": {"type": "unit", "unit": "Commercial"},
        "detection_type": "target_miss",
        "data_domain": "expenses",
    }
    fp = make_fingerprint(anomaly)
    assert fp == "unit_Commercial_expenses_target_miss"


def test_deduplicate_new_anomaly():
    existing = []
    anomalies = [{
        "entity": {"type": "brand", "brand_id": "X", "market_id": "US"},
        "detection_type": "outlier",
        "data_domain": "revenue",
        "statistical_score": 3.5,
    }]
    new, updated, seen_fps = deduplicate(anomalies, existing)
    assert len(new) == 1
    assert len(updated) == 0
    assert "brand_X_US_revenue_outlier" in seen_fps


def test_deduplicate_suppresses_existing():
    existing = [{
        "id": "ins_old",
        "fingerprint": "brand_X_US_revenue_outlier",
        "status": "active",
        "statistical_score": 3.0,
        "read": True,
    }]
    anomalies = [{
        "entity": {"type": "brand", "brand_id": "X", "market_id": "US"},
        "detection_type": "outlier",
        "data_domain": "revenue",
        "statistical_score": 3.1,  # similar, not worsened
    }]
    new, updated, seen_fps = deduplicate(anomalies, existing)
    assert len(new) == 0
    assert len(updated) == 0  # last_seen updated in place, but not "escalated"


def test_deduplicate_escalates_worsened():
    existing = [{
        "id": "ins_old",
        "fingerprint": "brand_X_US_revenue_outlier",
        "status": "active",
        "statistical_score": 2.5,
        "read": True,
        "severity": "notable",
    }]
    anomalies = [{
        "entity": {"type": "brand", "brand_id": "X", "market_id": "US"},
        "detection_type": "outlier",
        "data_domain": "revenue",
        "statistical_score": 4.0,  # significantly worse
    }]
    new, updated, seen_fps = deduplicate(anomalies, existing)
    assert len(new) == 0
    assert len(updated) == 1
    assert updated[0]["read"] is False  # re-flagged as unread
    assert updated[0]["statistical_score"] == 4.0

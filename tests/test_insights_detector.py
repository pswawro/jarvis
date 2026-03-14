"""Tests for statistical anomaly detection."""

import pandas as pd
import numpy as np
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from insights.detector import detect_outliers, detect_drift, detect_target_misses, detect_competitive_shifts


@pytest.fixture
def revenue_df():
    """Monthly revenue with one outlier month."""
    dates = pd.date_range("2024-01-01", periods=12, freq="MS")
    values = [100, 102, 98, 101, 99, 103, 100, 97, 101, 100, 99, 150]  # Dec is outlier
    return pd.DataFrame({
        "period_date": dates,
        "brand_id": "DRUG_A",
        "market_id": "US",
        "actual_amount": values,
    })


@pytest.fixture
def profile():
    return {
        "zscore_critical": 3.0,
        "zscore_notable": 2.0,
        "rolling_window_months": 3,
        "target_miss_pct": 0.12,
        "market_share_delta_pct": 2.5,
    }


def test_detect_outliers_finds_spike(revenue_df, profile):
    anomalies = detect_outliers(
        revenue_df, "actual_amount", "brand",
        group_cols=["brand_id", "market_id"],
        profile=profile,
        data_domain="revenue",
    )
    assert len(anomalies) >= 1
    outlier = anomalies[0]
    assert outlier["detection_type"] == "outlier"
    assert outlier["entity"]["brand_id"] == "DRUG_A"
    assert outlier["statistical_score"] > profile["zscore_notable"]


def test_detect_outliers_no_anomaly_in_flat_data(profile):
    dates = pd.date_range("2024-01-01", periods=12, freq="MS")
    df = pd.DataFrame({
        "period_date": dates,
        "brand_id": "DRUG_B",
        "market_id": "US",
        "actual_amount": [100] * 12,
    })
    anomalies = detect_outliers(
        df, "actual_amount", "brand",
        group_cols=["brand_id", "market_id"],
        profile=profile,
        data_domain="revenue",
    )
    assert len(anomalies) == 0


def test_detect_drift_finds_upward_trend(profile):
    dates = pd.date_range("2024-01-01", periods=12, freq="MS")
    # Baseline has natural variance; last 3 months well above historical mean
    values = [100, 102, 98, 101, 99, 103, 97, 101, 100, 120, 125, 130]
    df = pd.DataFrame({
        "period_date": dates,
        "unit": "Sales",
        "actual_amount": values,
    })
    anomalies = detect_drift(
        df, "actual_amount", "unit",
        group_cols=["unit"],
        profile=profile,
        data_domain="expenses",
    )
    assert len(anomalies) >= 1
    assert anomalies[0]["detection_type"] == "drift"


def test_detect_target_misses(profile):
    dates = pd.date_range("2024-01-01", periods=3, freq="MS")
    revenue = pd.DataFrame({
        "period_date": dates,
        "brand_id": "DRUG_A",
        "market_id": "US",
        "actual_amount": [80, 85, 70],
    })
    targets = pd.DataFrame({
        "period_date": dates,
        "brand_id": "DRUG_A",
        "market_id": "US",
        "budget_amount": [100, 100, 100],
    })
    anomalies = detect_target_misses(
        revenue, targets, "actual_amount", "budget_amount",
        entity_type="brand",
        group_cols=["brand_id", "market_id"],
        profile=profile,
    )
    # 70 vs 100 is a 30% miss, should be flagged
    assert any(a["raw_stats"]["miss_pct"] >= 0.12 for a in anomalies)


def test_detect_competitive_shifts(profile):
    dates = pd.date_range("2024-01-01", periods=6, freq="MS")
    df = pd.DataFrame({
        "period_date": dates,
        "brand_id": "DRUG_A",
        "market_id": "US",
        "category": "Oncology",
        "az_market_share_pct": [50, 50, 50, 50, 50, 44],  # 6pt drop last month
    })
    anomalies = detect_competitive_shifts(df, profile)
    assert len(anomalies) >= 1
    assert anomalies[0]["detection_type"] == "competitive_shift"

"""Tests for insights configuration loading."""

import os
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from insights.config import load_sensitivity_profile


def test_load_default_profile():
    profile = load_sensitivity_profile()
    assert profile["zscore_critical"] == 3.0
    assert profile["zscore_notable"] == 2.0
    assert profile["rolling_window_months"] == 3
    assert profile["target_miss_pct"] == 0.12
    assert profile["market_share_delta_pct"] == 2.5


def test_load_high_profile_via_env(monkeypatch):
    monkeypatch.setenv("INSIGHT_SENSITIVITY", "high")
    profile = load_sensitivity_profile()
    assert profile["zscore_critical"] == 2.5


def test_invalid_profile_falls_back_to_default():
    profile = load_sensitivity_profile("nonexistent")
    assert profile["zscore_critical"] == 3.0

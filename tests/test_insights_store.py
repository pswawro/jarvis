"""Tests for insight JSON store with atomic writes."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from insights.store import InsightStore


@pytest.fixture
def store(tmp_path):
    return InsightStore(tmp_path / "insights.json")


def test_empty_store_returns_empty_list(store):
    assert store.load_all() == []


def test_save_and_load_insight(store):
    insight = {
        "id": "ins_test1",
        "fingerprint": "brand_X_revenue_outlier",
        "status": "active",
        "read": False,
    }
    store.save_all([insight])
    loaded = store.load_all()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "ins_test1"


def test_atomic_write_creates_valid_json(store):
    insights = [{"id": f"ins_{i}", "status": "active"} for i in range(5)]
    store.save_all(insights)
    # Verify the file is valid JSON
    raw = json.loads(store.path.read_text())
    assert len(raw) == 5


def test_mark_read(store):
    insights = [
        {"id": "ins_a", "read": False, "status": "active"},
        {"id": "ins_b", "read": False, "status": "active"},
    ]
    store.save_all(insights)
    result = store.mark_read("ins_a")
    assert result is True
    loaded = store.load_all()
    assert loaded[0]["read"] is True
    assert loaded[1]["read"] is False


def test_mark_read_nonexistent_returns_false(store):
    store.save_all([{"id": "ins_a", "read": False, "status": "active"}])
    result = store.mark_read("ins_nonexistent")
    assert result is False

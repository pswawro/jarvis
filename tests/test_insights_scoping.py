"""Tests for role-based insight filtering."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from insights.scoping import filter_by_role_scope


@pytest.fixture
def sample_insights():
    return [
        {"id": "1", "entity": {"type": "brand"}, "data_domain": "revenue"},
        {"id": "2", "entity": {"type": "ta"}, "data_domain": "revenue"},
        {"id": "3", "entity": {"type": "total"}, "data_domain": "revenue"},
        {"id": "4", "entity": {"type": "unit"}, "data_domain": "expenses"},
        {"id": "5", "entity": {"type": "brand_market"}, "data_domain": "market"},
    ]


def test_cfo_scope(sample_insights):
    scope = {"revenue": ["total", "ta"], "expenses": ["total", "unit"], "market": ["brand_market"]}
    filtered = filter_by_role_scope(sample_insights, scope)
    ids = [i["id"] for i in filtered]
    assert "1" not in ids  # brand-level revenue hidden
    assert "2" in ids      # ta-level revenue visible
    assert "3" in ids      # total revenue visible
    assert "4" in ids      # unit expenses visible
    assert "5" in ids      # market visible


def test_default_scope_sees_everything(sample_insights):
    scope = {
        "revenue": ["brand", "ta", "total"],
        "expenses": ["sub_unit", "unit", "total"],
        "market": ["brand_market"],
    }
    filtered = filter_by_role_scope(sample_insights, scope)
    assert len(filtered) == 5


def test_empty_scope_hides_domain(sample_insights):
    scope = {"revenue": ["brand"], "expenses": [], "market": []}
    filtered = filter_by_role_scope(sample_insights, scope)
    ids = [i["id"] for i in filtered]
    assert "1" in ids
    assert "4" not in ids
    assert "5" not in ids

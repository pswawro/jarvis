"""Shared constants, validation, and filter helpers for route modules."""

from __future__ import annotations

import math

from fastapi import HTTPException
import pandas as pd

import data_loader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPARATOR_FIELD = {"BUD": "budget_amount", "MTP": "mtp_amount", "RBU2": "rbu2_amount"}
COMPARATOR_LABELS = {"BUD": "Budget", "MTP": "MTP", "RBU2": "RBU2", "PYACT": "Prior Year"}

LEVEL_COLS = {
    "ta":       {"group": "therapeutic_area", "name": "therapeutic_area"},
    "brand":    {"group": "brand_id",         "name": "brand_name"},
    "market":   {"group": "market_id",        "name": "market_name"},
    "region":   {"group": "region",           "name": "region"},
}
VALID_QUARTERS = {"Q1", "Q2", "Q3", "Q4"}
_CURRENT_YEAR = __import__("datetime").date.today().year
VALID_YEARS = set(range(_CURRENT_YEAR - 2, _CURRENT_YEAR + 2))
VALID_COMPARATORS = {"BUD", "MTP", "RBU2", "PYACT"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_params(
    year: int = 2025,
    quarter: str | None = None,
    comparator: str = "BUD",
):
    """Validate common route parameters. Raises HTTPException(400) on invalid input."""
    if year not in VALID_YEARS:
        raise HTTPException(status_code=400, detail=f"Invalid year {year}. Must be one of {sorted(VALID_YEARS)}")
    if quarter is not None and quarter not in VALID_QUARTERS:
        raise HTTPException(status_code=400, detail=f"Invalid quarter '{quarter}'. Must be one of {sorted(VALID_QUARTERS)}")
    if comparator not in VALID_COMPARATORS:
        raise HTTPException(status_code=400, detail=f"Invalid comparator '{comparator}'. Must be one of {sorted(VALID_COMPARATORS)}")


def parse_quarter(quarter: str) -> int:
    """Parse 'Q1'..'Q4' into quarter number 1..4. Call only after validate_params."""
    return int(quarter[1])


# ---------------------------------------------------------------------------
# Variance calculation
# ---------------------------------------------------------------------------

def safe_round(val: float, ndigits: int = 1) -> float:
    """Round a value, returning 0.0 for NaN/Inf."""
    if math.isnan(val) or math.isinf(val):
        return 0.0
    return round(val, ndigits)


def var_pct(actual: float, compare: float) -> float:
    """Percentage variance: (actual - compare) / compare * 100, or 0 if compare is 0/NaN/Inf."""
    try:
        if not compare or compare == 0 or math.isnan(compare) or math.isinf(compare):
            return 0.0
        if math.isnan(actual) or math.isinf(actual):
            return 0.0
    except TypeError:
        return 0.0
    return safe_round((actual - compare) / compare * 100)


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------

def parse_list(csv_str: str | None) -> list[str] | None:
    """Parse comma-separated string into list, or None if empty."""
    if not csv_str:
        return None
    return [s.strip() for s in csv_str.split(",") if s.strip()]


def filter_by_ta(rev: pd.DataFrame, tgt: pd.DataFrame, ta: str | None):
    """Filter revenue and targets by therapeutic area. Returns (rev, tgt, prods)."""
    prods = data_loader.products
    if ta:
        ta_list = parse_list(ta)
        if ta_list:
            prods = prods[prods.therapeutic_area.isin(ta_list)]
            ta_brands = prods.brand_id.tolist()
            rev = rev[rev.brand_id.isin(ta_brands)]
            tgt = tgt[tgt.entity_id.isin(ta_brands)]
    return rev, tgt, prods


def filter_by_market(rev: pd.DataFrame, tgt: pd.DataFrame, market_id: str | None):
    """Filter revenue and targets by market. Returns (rev, tgt)."""
    if market_id:
        mkt_list = parse_list(market_id)
        if mkt_list:
            rev = rev[rev.market_id.isin(mkt_list)]
            tgt = tgt[tgt.market_id.isin(mkt_list)]
    return rev, tgt


def filter_by_period(
    rev: pd.DataFrame,
    tgt: pd.DataFrame,
    year: int,
    quarter: str | None = None,
):
    """Filter to year and optional quarter. Returns (rev_period, tgt_period)."""
    r = rev[rev.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    if quarter:
        q_num = parse_quarter(quarter)
        r = r[r.quarter == quarter]
        t = t[t.period_date.dt.quarter == q_num]
    return r, t


def get_prior_year(
    rev: pd.DataFrame,
    year: int,
    quarter: str | None = None,
    market_id: str | None = None,
):
    """Get prior year revenue, optionally filtered."""
    r_py = rev[rev.year == year - 1]
    if quarter:
        r_py = r_py[r_py.quarter == quarter]
    if market_id:
        mkt_list = parse_list(market_id)
        if mkt_list:
            r_py = r_py[r_py.market_id.isin(mkt_list)]
    return r_py


def apply_standard_filters(
    rev: pd.DataFrame,
    tgt: pd.DataFrame,
    ta: str | None = None,
    brand_id: str | None = None,
    market_id: str | None = None,
):
    """Apply TA, brand, and market filters to revenue and targets DataFrames.

    Returns (rev, tgt, prods) after filtering.
    """
    prods = data_loader.products
    if ta:
        ta_list = parse_list(ta)
        if ta_list:
            prods = prods[prods.therapeutic_area.isin(ta_list)]
            ta_brands = prods.brand_id.tolist()
            rev = rev[rev.brand_id.isin(ta_brands)]
            tgt = tgt[tgt.entity_id.isin(ta_brands)]
    if brand_id:
        bid_list = parse_list(brand_id)
        if bid_list:
            prods = prods[prods.brand_id.isin(bid_list)]
            rev = rev[rev.brand_id.isin(bid_list)]
            tgt = tgt[tgt.entity_id.isin(bid_list)]
    if market_id:
        mkt_list = parse_list(market_id)
        if mkt_list:
            rev = rev[rev.market_id.isin(mkt_list)]
            tgt = tgt[tgt.market_id.isin(mkt_list)]
    return rev, tgt, prods


def period_label(year: int, quarter: str | None) -> str:
    """Format period label like 'Q1 2025' or 'FY 2025'."""
    if quarter and len(quarter) >= 2:
        return f"Q{quarter[1]} {year}"
    return f"FY {year}"

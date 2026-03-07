"""Generic tree builder — composable drill hierarchies for any domain."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
import pandas as pd

import data_loader
from models import TreeTableSpec, TreeNode, TreeNodeValues
from routes.shared import validate_params, var_pct, safe_round, period_label, COMPARATOR_LABELS

router = APIRouter()

# ---------------------------------------------------------------------------
# Dimension config (loaded once)
# ---------------------------------------------------------------------------

_DIM_CONFIG: dict | None = None


def _load_dim_config() -> dict:
    global _DIM_CONFIG
    if _DIM_CONFIG is None:
        p = Path(__file__).resolve().parent.parent.parent / "data" / "dimensions.json"
        with open(p) as f:
            _DIM_CONFIG = json.load(f)
    return _DIM_CONFIG


def get_dimensions_config() -> dict:
    """Public accessor for config endpoint."""
    return _load_dim_config()


# ---------------------------------------------------------------------------
# Level → column mappings per domain
# ---------------------------------------------------------------------------

# Revenue: columns available after enriching the revenue fact table
_REVENUE_LEVELS = {
    "ta":     {"group": "therapeutic_area", "name": "therapeutic_area", "id_prefix": "ta"},
    "brand":  {"group": "brand_id",         "name": "brand_name",       "id_prefix": "brand"},
    "market": {"group": "market_id",        "name": "market_name",      "id_prefix": "mkt"},
    "region": {"group": "region",           "name": "region",           "id_prefix": "reg"},
}

_EXPENSE_LEVELS = {
    "unit":     {"group": "unit",         "name": "unit",           "id_prefix": "unit"},
    "sub_unit": {"group": "sub_unit_id",  "name": "sub_unit_name",  "id_prefix": "sub"},
}

_COMPETITIVE_LEVELS = {
    "category": {"group": "category",  "name": "category",   "id_prefix": "cat"},
    "brand":    {"group": "brand_id",  "name": "brand_name", "id_prefix": "brand"},
}

DOMAIN_LEVELS = {
    "revenue": _REVENUE_LEVELS,
    "expense": _EXPENSE_LEVELS,
    "competitive": _COMPETITIVE_LEVELS,
}


def _detect_domain(levels: list[str]) -> str:
    """Determine domain from the level IDs. All must belong to one domain."""
    cfg = _load_dim_config()
    level_map = {lv["id"]: lv["domain"] for lv in cfg["levels"]}
    domains = set()
    for lv in levels:
        d = level_map.get(lv)
        if d is None:
            raise HTTPException(400, f"Unknown level '{lv}'. Available: {list(level_map.keys())}")
        domains.add(d)
    if len(domains) != 1:
        raise HTTPException(400, f"All levels must be same domain. Got: {domains}")
    return domains.pop()


# ---------------------------------------------------------------------------
# Revenue domain builder
# ---------------------------------------------------------------------------

def _enrich_revenue(df: pd.DataFrame) -> pd.DataFrame:
    prods = data_loader.products[["brand_id", "brand_name", "therapeutic_area"]]
    geo = data_loader.geographies[["market_id", "market_name", "region"]]
    df = df.merge(prods, on="brand_id", how="left")
    df = df.merge(geo, on="market_id", how="left")
    return df


def _enrich_targets_revenue(df: pd.DataFrame) -> pd.DataFrame:
    prods = data_loader.products[["brand_id", "brand_name", "therapeutic_area"]]
    geo = data_loader.geographies[["market_id", "market_name", "region"]]
    df = df.merge(prods, left_on="entity_id", right_on="brand_id", how="left")
    df = df.merge(geo, on="market_id", how="left")
    return df


def _build_revenue_tree(
    levels: list[str],
    year: int,
    quarter: str | None,
    market_id: str | None,
    ta: str | None,
    comparator: str,
    brand_id: str | None = None,
) -> TreeTableSpec:
    rev = data_loader.revenue
    tgt = data_loader.targets[data_loader.targets.target_type == "revenue"]
    prods = data_loader.products

    # Apply TA filter
    if ta:
        ta_list = [t.strip() for t in ta.split(",")]
        ta_brands = prods[prods.therapeutic_area.isin(ta_list)].brand_id.tolist()
        rev = rev[rev.brand_id.isin(ta_brands)]
        tgt = tgt[tgt.entity_id.isin(ta_brands)]

    # Apply brand/product filter
    if brand_id:
        bid_list = [b.strip() for b in brand_id.split(",")]
        rev = rev[rev.brand_id.isin(bid_list)]
        tgt = tgt[tgt.entity_id.isin(bid_list)]

    # Apply market filter
    mkt_list = [m.strip() for m in market_id.split(",")] if market_id else None
    if mkt_list:
        rev = rev[rev.market_id.isin(mkt_list)]
        tgt = tgt[tgt.market_id.isin(mkt_list)]

    # Period filter
    r = rev[rev.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    if quarter:
        q_num = int(quarter[1])
        r = r[r.quarter == quarter]
        t = t[t.period_date.dt.quarter == q_num]

    r_py = rev[rev.year == year - 1]
    if quarter:
        r_py = r_py[r_py.quarter == quarter]
    if mkt_list:
        r_py = r_py[r_py.market_id.isin(mkt_list)]

    r_full = rev[rev.year == year]
    if mkt_list:
        r_full = r_full[r_full.market_id.isin(mkt_list)]

    # Enrich with dimension columns
    r_e = _enrich_revenue(r)
    r_py_e = _enrich_revenue(r_py)
    r_full_e = _enrich_revenue(r_full)
    t_e = _enrich_targets_revenue(t)

    comp_label = COMPARATOR_LABELS.get(comparator, comparator)
    level_cols = _REVENUE_LEVELS

    def _make_values(actual, budget, forecast, py, mtp, rbu2, spark):
        comp_val = py if comparator == "PYACT" else {"BUD": budget, "MTP": mtp, "RBU2": rbu2}.get(comparator, budget)
        return TreeNodeValues(
            actual=round(actual, 1),
            budget=round(budget, 1),
            variance_pct=var_pct(actual, budget),
            prior_year=round(py, 1),
            py_variance_pct=var_pct(actual, py),
            sparkline=spark,
            forecast=round(forecast, 1),
            forecast_variance_pct=var_pct(actual, forecast),
            mtp=round(mtp, 1),
            mtp_variance_pct=var_pct(actual, mtp),
            rbu2=round(rbu2, 1),
            rbu2_variance_pct=var_pct(actual, rbu2),
            comparator_label=comp_label,
            comparator_value=round(comp_val, 1),
            comparator_variance_pct=var_pct(actual, comp_val),
        )

    def _build_nodes(data, data_py, data_full, targets, depth):
        if depth >= len(levels):
            return []

        lv = levels[depth]
        cfg = level_cols[lv]
        gcol = cfg["group"]
        ncol = cfg["name"]
        prefix = cfg["id_prefix"]
        is_leaf = depth == len(levels) - 1

        nodes: list[TreeNode] = []

        for key, grp in data.groupby(gcol, sort=True):
            name = str(grp[ncol].iloc[0]) if ncol != gcol else str(key)
            node_id = f"{prefix}_{key}" if prefix else str(key)

            if is_leaf:
                actual = float(grp["revenue"].sum())
                grp_py = data_py[data_py[gcol] == key]
                py = float(grp_py["revenue"].sum()) if not grp_py.empty else 0.0
                grp_t = targets[targets[gcol] == key]
                budget = float(grp_t["budget_amount"].sum()) if not grp_t.empty else 0.0
                forecast = float(grp_t["forecast_amount"].sum()) if not grp_t.empty else 0.0
                mtp = float(grp_t["mtp_amount"].sum()) if not grp_t.empty else 0.0
                rbu2 = float(grp_t["rbu2_amount"].sum()) if not grp_t.empty else 0.0
                grp_full = data_full[data_full[gcol] == key]
                spark_s = grp_full.groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)
                spark = [round(v, 1) for v in spark_s.values]

                nodes.append(TreeNode(
                    id=node_id, name=name,
                    values=_make_values(actual, budget, forecast, py, mtp, rbu2, spark),
                ))
            else:
                grp_py = data_py[data_py[gcol] == key]
                grp_full = data_full[data_full[gcol] == key]
                grp_t = targets[targets[gcol] == key]
                children = _build_nodes(grp, grp_py, grp_full, grp_t, depth + 1)

                if not children:
                    continue

                actual = sum(c.values.actual for c in children)
                budget = sum(c.values.budget for c in children)
                forecast = sum(c.values.forecast or 0 for c in children)
                mtp = sum(c.values.mtp or 0 for c in children)
                rbu2 = sum(c.values.rbu2 or 0 for c in children)
                py = sum(c.values.prior_year or 0 for c in children)
                spark = [round(sum(c.values.sparkline[i] for c in children), 1) for i in range(12)]

                nodes.append(TreeNode(
                    id=node_id, name=name,
                    values=_make_values(actual, budget, forecast, py, mtp, rbu2, spark),
                    children=children,
                ))

        return nodes

    children = _build_nodes(r_e, r_py_e, r_full_e, t_e, 0)

    # Root node
    grand_actual = sum(c.values.actual for c in children)
    grand_budget = sum(c.values.budget for c in children)
    grand_forecast = sum(c.values.forecast or 0 for c in children)
    grand_mtp = sum(c.values.mtp or 0 for c in children)
    grand_rbu2 = sum(c.values.rbu2 or 0 for c in children)
    grand_py = sum(c.values.prior_year or 0 for c in children)
    grand_spark_s = r_full_e.groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)
    grand_spark = [round(v, 1) for v in grand_spark_s.values]

    return TreeTableSpec(
        period_label=period_label(year, quarter),
        columns=["Name", "Actual", f"vs {comp_label}", "Trend"],
        tree=TreeNode(
            id="TOTAL_AZ",
            name="Total AZ",
            values=_make_values(grand_actual, grand_budget, grand_forecast, grand_py, grand_mtp, grand_rbu2, grand_spark),
            children=children,
        ),
    )


# ---------------------------------------------------------------------------
# Expense domain builder
# ---------------------------------------------------------------------------

def _enrich_expenses(df: pd.DataFrame) -> pd.DataFrame:
    org = data_loader.organization[["sub_unit_id", "sub_unit_name", "unit"]]
    return df.merge(org, on="sub_unit_id", how="left")


def _build_expense_tree(
    levels: list[str],
    year: int,
    quarter: str | None,
    comparator: str,
) -> TreeTableSpec:
    exp = data_loader.expenses
    tgt = data_loader.targets[data_loader.targets.target_type == "expense"]
    hc = data_loader.headcount

    e = exp[exp.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    h = hc[hc.year == year]
    if quarter:
        q_num = int(quarter[1])
        e = e[e.quarter == quarter]
        t = t[t.period_date.dt.quarter == q_num]
        h = h[h.quarter == quarter]

    e_py = exp[exp.year == year - 1]
    if quarter:
        e_py = e_py[e_py.quarter == quarter]

    e_full = exp[exp.year == year]

    # Enrich with org columns
    e_e = _enrich_expenses(e)
    e_py_e = _enrich_expenses(e_py)
    e_full_e = _enrich_expenses(e_full)

    # Enrich targets
    org = data_loader.organization[["sub_unit_id", "sub_unit_name", "unit"]]
    t_e = t.merge(org, left_on="entity_id", right_on="sub_unit_id", how="left")

    # Headcount enriched
    h_e = h.merge(org, on="sub_unit_id", how="left")

    comp_label = COMPARATOR_LABELS.get(comparator, comparator)
    level_cols = _EXPENSE_LEVELS

    def _make_expense_node(actual, budget, forecast, py, mtp, rbu2, spark,
                           personnel=0, external=0, other=0, fte=0, headcount_val=0):
        comp_val = py if comparator == "PYACT" else {"BUD": budget, "MTP": mtp, "RBU2": rbu2}.get(comparator, budget)
        cost_per_fte = round(actual / fte, 2) if fte > 0 else None
        return TreeNodeValues(
            actual=round(actual, 1),
            budget=round(budget, 1),
            variance_pct=var_pct(actual, budget),
            prior_year=round(py, 1),
            py_variance_pct=var_pct(actual, py),
            sparkline=spark,
            forecast=round(forecast, 1),
            forecast_variance_pct=var_pct(actual, forecast),
            mtp=round(mtp, 1),
            mtp_variance_pct=var_pct(actual, mtp),
            rbu2=round(rbu2, 1),
            rbu2_variance_pct=var_pct(actual, rbu2),
            comparator_label=comp_label,
            comparator_value=round(comp_val, 1),
            comparator_variance_pct=var_pct(actual, comp_val),
            personnel_costs=round(personnel, 1),
            external_costs=round(external, 1),
            other_costs=round(other, 1),
            fte_count=round(fte, 1),
            headcount=int(headcount_val),
            cost_per_fte=cost_per_fte,
        )

    def _build_nodes(data, data_py, data_full, targets, hc_data, depth):
        if depth >= len(levels):
            return []

        lv = levels[depth]
        cfg = level_cols[lv]
        gcol = cfg["group"]
        ncol = cfg["name"]
        prefix = cfg["id_prefix"]
        is_leaf = depth == len(levels) - 1

        nodes: list[TreeNode] = []

        for key, grp in data.groupby(gcol, sort=True):
            name = str(grp[ncol].iloc[0]) if ncol != gcol else str(key)
            node_id = f"{prefix}_{key}" if prefix else str(key)

            if is_leaf:
                actual = float(grp["total_operating_expenses"].sum())
                personnel = float(grp["personnel_costs"].sum())
                external = float(grp["external_costs"].sum())
                other = float(grp["other_costs"].sum())

                grp_py = data_py[data_py[gcol] == key]
                py = float(grp_py["total_operating_expenses"].sum()) if not grp_py.empty else 0.0

                grp_t = targets[targets[gcol] == key] if gcol in targets.columns else pd.DataFrame()
                budget = float(grp_t["budget_amount"].sum()) if not grp_t.empty else 0.0
                forecast = float(grp_t["forecast_amount"].sum()) if not grp_t.empty else 0.0
                mtp = float(grp_t["mtp_amount"].sum()) if not grp_t.empty else 0.0
                rbu2 = float(grp_t["rbu2_amount"].sum()) if not grp_t.empty else 0.0

                grp_h = hc_data[hc_data[gcol] == key] if gcol in hc_data.columns else pd.DataFrame()
                fte = float(grp_h["fte_count"].mean()) if not grp_h.empty else 0.0
                headcount_val = int(grp_h["headcount"].max()) if not grp_h.empty else 0

                grp_full = data_full[data_full[gcol] == key]
                spark_s = grp_full.groupby("month")["total_operating_expenses"].sum().reindex(range(1, 13), fill_value=0)
                spark = [round(v, 1) for v in spark_s.values]

                nodes.append(TreeNode(
                    id=node_id, name=name,
                    values=_make_expense_node(actual, budget, forecast, py, mtp, rbu2, spark,
                                              personnel, external, other, fte, headcount_val),
                ))
            else:
                grp_py = data_py[data_py[gcol] == key]
                grp_full = data_full[data_full[gcol] == key]
                grp_t = targets[targets[gcol] == key] if gcol in targets.columns else pd.DataFrame()
                grp_h = hc_data[hc_data[gcol] == key] if gcol in hc_data.columns else pd.DataFrame()
                children = _build_nodes(grp, grp_py, grp_full, grp_t, grp_h, depth + 1)

                if not children:
                    continue

                actual = sum(c.values.actual for c in children)
                budget = sum(c.values.budget for c in children)
                forecast = sum(c.values.forecast or 0 for c in children)
                mtp = sum(c.values.mtp or 0 for c in children)
                rbu2 = sum(c.values.rbu2 or 0 for c in children)
                py = sum(c.values.prior_year or 0 for c in children)
                personnel = sum(c.values.personnel_costs or 0 for c in children)
                external = sum(c.values.external_costs or 0 for c in children)
                other = sum(c.values.other_costs or 0 for c in children)
                fte = sum(c.values.fte_count or 0 for c in children)
                headcount_val = sum(c.values.headcount or 0 for c in children)
                spark = [round(sum(c.values.sparkline[i] for c in children), 1) for i in range(12)]

                nodes.append(TreeNode(
                    id=node_id, name=name,
                    values=_make_expense_node(actual, budget, forecast, py, mtp, rbu2, spark,
                                              personnel, external, other, fte, headcount_val),
                    children=children,
                ))

        return nodes

    children = _build_nodes(e_e, e_py_e, e_full_e, t_e, h_e, 0)

    grand_actual = sum(c.values.actual for c in children)
    grand_budget = sum(c.values.budget for c in children)
    grand_forecast = sum(c.values.forecast or 0 for c in children)
    grand_mtp = sum(c.values.mtp or 0 for c in children)
    grand_rbu2 = sum(c.values.rbu2 or 0 for c in children)
    grand_py = sum(c.values.prior_year or 0 for c in children)
    grand_personnel = sum(c.values.personnel_costs or 0 for c in children)
    grand_external = sum(c.values.external_costs or 0 for c in children)
    grand_other = sum(c.values.other_costs or 0 for c in children)
    grand_fte = sum(c.values.fte_count or 0 for c in children)
    grand_hc = sum(c.values.headcount or 0 for c in children)
    grand_spark_s = e_full_e.groupby("month")["total_operating_expenses"].sum().reindex(range(1, 13), fill_value=0)
    grand_spark = [round(v, 1) for v in grand_spark_s.values]

    return TreeTableSpec(
        period_label=period_label(year, quarter),
        columns=["Name", "Actual", f"vs {comp_label}", "Personnel", "External", "Other", "FTE", "$/FTE", "Trend"],
        tree=TreeNode(
            id="TOTAL_AZ",
            name="Total AZ",
            values=_make_expense_node(grand_actual, grand_budget, grand_forecast, grand_py, grand_mtp, grand_rbu2,
                                      grand_spark, grand_personnel, grand_external, grand_other, grand_fte, grand_hc),
            children=children,
        ),
    )


# ---------------------------------------------------------------------------
# Competitive domain builder
# ---------------------------------------------------------------------------

def _build_competitive_tree(
    levels: list[str],
    year: int,
    quarter: str | None,
    market_id: str | None,
    ta: str | None,
) -> TreeTableSpec:
    comm = data_loader.commercial
    prods = data_loader.products

    if ta:
        ta_list = [t.strip() for t in ta.split(",")]
        ta_brands = prods[prods.therapeutic_area.isin(ta_list)].brand_id.tolist()
        comm = comm[comm.brand_id.isin(ta_brands)]
    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
        comm = comm[comm.market_id.isin(mkt_list)]

    c = comm[comm.period_date.dt.year == year]
    c_py = comm[comm.period_date.dt.year == year - 1]
    if quarter:
        q_num = int(quarter[1])
        c = c[c.period_date.dt.quarter == q_num]
        c_py = c_py[c_py.period_date.dt.quarter == q_num]

    c_full = comm[comm.period_date.dt.year == year]

    # Enrich with brand names
    brand_names = dict(zip(prods.brand_id, prods.brand_name))
    level_cols = _COMPETITIVE_LEVELS

    def _share_spark(df_full, filter_col, filter_val):
        sub = df_full[df_full[filter_col] == filter_val] if filter_col else df_full
        monthly = sub.groupby(sub.period_date.dt.month).agg(
            az=("az_revenue_usd_m", "sum"),
            mkt=("total_market_size_usd_m", "sum"),
        ).reindex(range(1, 13), fill_value=0)
        share = (monthly["az"] / monthly["mkt"] * 100).where(monthly["mkt"] > 0, 0.0)
        return [safe_round(v) for v in share.values]

    def _build_nodes(data, data_py, data_full, depth):
        if depth >= len(levels):
            return []

        lv = levels[depth]
        cfg = level_cols[lv]
        gcol = cfg["group"]
        ncol = cfg["name"]
        prefix = cfg["id_prefix"]
        is_leaf = depth == len(levels) - 1

        nodes: list[TreeNode] = []

        for key, grp in data.groupby(gcol, sort=True):
            if lv == "brand":
                name = brand_names.get(key, str(key))
            else:
                name = str(grp[ncol].iloc[0]) if ncol != gcol else str(key)
            node_id = f"{prefix}_{key}" if prefix else str(key)

            if is_leaf:
                az_rev = grp.az_revenue_usd_m.sum()
                mkt_size = grp.total_market_size_usd_m.sum()
                share = safe_round(az_rev / mkt_size * 100) if mkt_size > 0 else 0.0
                growth = safe_round(grp.market_growth_pct.mean())

                grp_py = data_py[data_py[gcol] == key]
                py_rev = grp_py.az_revenue_usd_m.sum() if not grp_py.empty else 0.0
                py_mkt = grp_py.total_market_size_usd_m.sum() if not grp_py.empty else 0.0
                py_share = safe_round(py_rev / py_mkt * 100) if py_mkt > 0 else 0.0
                share_delta = safe_round(share - py_share)

                grp_full = data_full[data_full[gcol] == key]
                monthly = grp_full.groupby(grp_full.period_date.dt.month).agg(
                    az=("az_revenue_usd_m", "sum"),
                    mkt=("total_market_size_usd_m", "sum"),
                ).reindex(range(1, 13), fill_value=0)
                spark_share = (monthly["az"] / monthly["mkt"] * 100).where(monthly["mkt"] > 0, 0.0)
                spark = [safe_round(v) for v in spark_share.values]

                nodes.append(TreeNode(
                    id=node_id, name=name,
                    values=TreeNodeValues(
                        actual=safe_round(az_rev),
                        budget=safe_round(mkt_size),
                        variance_pct=share_delta,
                        py_variance_pct=growth,
                        sparkline=spark,
                        market_share_pct=share,
                    ),
                ))
            else:
                grp_py = data_py[data_py[gcol] == key]
                grp_full = data_full[data_full[gcol] == key]
                children = _build_nodes(grp, grp_py, grp_full, depth + 1)

                if not children:
                    continue

                cat_az = sum(ch.values.actual for ch in children)
                cat_mkt = sum(ch.values.budget for ch in children)
                cat_share = round(cat_az / cat_mkt * 100, 1) if cat_mkt > 0 else 0.0

                # PY share for this group
                if not grp_py.empty:
                    py_rev = grp_py.az_revenue_usd_m.sum()
                    py_mkt_size = grp_py.total_market_size_usd_m.sum()
                    py_share = round(py_rev / py_mkt_size * 100, 1) if py_mkt_size > 0 else 0.0
                else:
                    py_share = 0.0
                share_delta = safe_round(cat_share - py_share)
                growth = safe_round(grp.market_growth_pct.mean())

                # Group-level sparkline
                gf = grp_full.groupby(grp_full.period_date.dt.month).agg(
                    az=("az_revenue_usd_m", "sum"),
                    mkt=("total_market_size_usd_m", "sum"),
                ).reindex(range(1, 13), fill_value=0)
                spark_share = (gf["az"] / gf["mkt"] * 100).where(gf["mkt"] > 0, 0.0)
                spark = [safe_round(v) for v in spark_share.values]

                nodes.append(TreeNode(
                    id=node_id, name=name,
                    values=TreeNodeValues(
                        actual=safe_round(cat_az),
                        budget=safe_round(cat_mkt),
                        variance_pct=share_delta,
                        py_variance_pct=growth,
                        sparkline=spark,
                        market_share_pct=cat_share,
                    ),
                    children=children,
                ))

        return nodes

    children = _build_nodes(c, c_py, c_full, 0)

    grand_az = sum(ch.values.actual for ch in children)
    grand_mkt = sum(ch.values.budget for ch in children)
    grand_share = round(grand_az / grand_mkt * 100, 1) if grand_mkt > 0 else 0.0
    grand_py_rev = c_py.az_revenue_usd_m.sum()
    grand_py_mkt = c_py.total_market_size_usd_m.sum()
    grand_py_share = safe_round(grand_py_rev / grand_py_mkt * 100) if grand_py_mkt > 0 else 0.0
    grand_share_delta = safe_round(grand_share - grand_py_share)
    grand_growth = safe_round(c.market_growth_pct.mean())

    gf = c_full.groupby(c_full.period_date.dt.month).agg(
        az=("az_revenue_usd_m", "sum"),
        mkt=("total_market_size_usd_m", "sum"),
    ).reindex(range(1, 13), fill_value=0)
    grand_spark_share = (gf["az"] / gf["mkt"] * 100).where(gf["mkt"] > 0, 0.0)
    grand_spark = [safe_round(v) for v in grand_spark_share.values]

    return TreeTableSpec(
        period_label=period_label(year, quarter),
        columns=["Name", "AZ Rev", "Shr Δ", "Mkt Grw", "Share", "Trend"],
        tree=TreeNode(
            id="TOTAL_AZ_MARKET",
            name="Total AZ",
            values=TreeNodeValues(
                actual=safe_round(grand_az),
                budget=safe_round(grand_mkt),
                variance_pct=grand_share_delta,
                py_variance_pct=grand_growth,
                sparkline=grand_spark,
                market_share_pct=grand_share,
            ),
            children=children,
        ),
    )


# ---------------------------------------------------------------------------
# Generic endpoint
# ---------------------------------------------------------------------------

@router.get("/tree", response_model=TreeTableSpec)
def get_tree(
    levels: str = Query(..., description="Comma-separated level IDs, e.g. 'ta,brand,market'"),
    year: int = 2025,
    quarter: str | None = None,
    market_id: str | None = None,
    ta: str | None = None,
    brand_id: str | None = None,
    comparator: str = "BUD",
):
    level_list = [lv.strip() for lv in levels.split(",") if lv.strip()]
    if not level_list:
        raise HTTPException(400, "At least one level is required")

    validate_params(year=year, quarter=quarter, comparator=comparator)
    domain = _detect_domain(level_list)

    if domain == "revenue":
        return _build_revenue_tree(level_list, year, quarter, market_id, ta, comparator, brand_id=brand_id)
    elif domain == "expense":
        return _build_expense_tree(level_list, year, quarter, comparator)
    elif domain == "competitive":
        return _build_competitive_tree(level_list, year, quarter, market_id, ta)
    else:
        raise HTTPException(400, f"Unknown domain: {domain}")


@router.get("/dimensions")
def get_dimensions():
    """Return available dimension levels and config."""
    return _load_dim_config()

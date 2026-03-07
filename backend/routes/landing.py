"""Landing view — actuals for closed months, forecast for future months.

Returns a blended 12-month table where past months show actuals
and future months show the selected comparator (budget/mtp/rbu2).
Supports composable drill hierarchy via `levels` param.
"""

from fastapi import APIRouter

import data_loader
from models import TreeTableSpec, TreeNode, TreeNodeValues
from routes.shared import validate_params, COMPARATOR_FIELD

router = APIRouter()

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Level → column mappings (mirrors tree_generic.py)
_LEVEL_COLS = {
    "ta":     {"group": "therapeutic_area", "name": "therapeutic_area"},
    "brand":  {"group": "brand_id",         "name": "brand_name"},
    "market": {"group": "market_id",        "name": "market_name"},
    "region": {"group": "region",           "name": "region"},
}


@router.get("/landing", response_model=TreeTableSpec)
def get_landing_view(
    year: int = 2025,
    market_id: str | None = None,
    ta: str | None = None,
    brand_id: str | None = None,
    comparator: str = "BUD",
    closed_month: int = 8,
    levels: str | None = None,
):
    validate_params(year=year, comparator=comparator)
    """closed_month: last month with actuals (1-12). Months after this use forecast."""

    # Parse levels
    level_list = [lv.strip() for lv in levels.split(",") if lv.strip()] if levels else ["ta", "brand"]

    rev = data_loader.revenue
    tgt = data_loader.targets[data_loader.targets.target_type == "revenue"]
    prods = data_loader.products
    geo = data_loader.geographies

    if ta:
        ta_list = [t.strip() for t in ta.split(",")]
        prods = prods[prods.therapeutic_area.isin(ta_list)]
        ta_brands = prods.brand_id.tolist()
        rev = rev[rev.brand_id.isin(ta_brands)]
        tgt = tgt[tgt.entity_id.isin(ta_brands)]
    if brand_id:
        bid_list = [b.strip() for b in brand_id.split(",")]
        prods = prods[prods.brand_id.isin(bid_list)]
        rev = rev[rev.brand_id.isin(bid_list)]
        tgt = tgt[tgt.entity_id.isin(bid_list)]
    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
        rev = rev[rev.market_id.isin(mkt_list)]
        tgt = tgt[tgt.market_id.isin(mkt_list)]

    r = rev[rev.year == year]
    t = tgt[tgt.period_date.dt.year == year]

    comp_field = COMPARATOR_FIELD.get(comparator, "budget_amount")

    # Enrich with dimension columns
    r = r.merge(prods[["brand_id", "brand_name", "therapeutic_area"]], on="brand_id", how="left")
    r = r.merge(geo[["market_id", "market_name", "region"]], on="market_id", how="left")

    t = t.merge(prods[["brand_id", "brand_name", "therapeutic_area"]], left_on="entity_id", right_on="brand_id", how="left")
    t = t.merge(geo[["market_id", "market_name", "region"]], on="market_id", how="left")

    # Build group columns for each level
    group_cols = []
    name_cols = []
    for lv in level_list:
        cfg = _LEVEL_COLS.get(lv)
        if cfg:
            group_cols.append(cfg["group"])
            name_cols.append(cfg["name"])

    if not group_cols:
        group_cols = ["therapeutic_area"]
        name_cols = ["therapeutic_area"]

    # Aggregate monthly actuals and forecast by all group columns + month
    act_agg = r.groupby(group_cols + ["month"])["revenue"].sum().reset_index()
    comp_agg = t.groupby(group_cols + [t.period_date.dt.month.rename("month")])[comp_field].sum().reset_index()

    def _blend_monthly(act_df, comp_df, grp_filter: dict) -> list[float]:
        """Return 12 blended values for a specific group filter."""
        af = act_df
        cf = comp_df
        for col, val in grp_filter.items():
            af = af[af[col] == val]
            cf = cf[cf[col] == val]
        act_by_month = dict(zip(af["month"], af["revenue"]))
        comp_by_month = dict(zip(cf["month"], cf[comp_field]))
        return [
            round(float(act_by_month.get(m + 1, 0)), 1) if m < closed_month
            else round(float(comp_by_month.get(m + 1, 0)), 1)
            for m in range(12)
        ]

    def _build_level(depth: int, parent_filter: dict) -> list[TreeNode]:
        """Recursively build tree nodes for each level."""
        if depth >= len(group_cols):
            return []

        gcol = group_cols[depth]
        ncol = name_cols[depth]

        # Get unique values at this level within parent filter
        filtered = act_agg
        for col, val in parent_filter.items():
            filtered = filtered[filtered[col] == val]
        unique_vals = filtered[gcol].dropna().unique()

        # Also check comp_agg for values that might only exist in forecast
        filtered_comp = comp_agg
        for col, val in parent_filter.items():
            filtered_comp = filtered_comp[filtered_comp[col] == val]
        unique_comp = filtered_comp[gcol].dropna().unique()
        all_vals = sorted(set(unique_vals) | set(unique_comp))

        # Get name mapping
        name_map = {}
        if gcol != ncol:
            name_source = r
            for col, val in parent_filter.items():
                name_source = name_source[name_source[col] == val]
            if len(name_source) > 0:
                name_map = dict(zip(name_source[gcol], name_source[ncol]))

        nodes = []
        for val in all_vals:
            current_filter = {**parent_filter, gcol: val}
            children = _build_level(depth + 1, current_filter)
            name = name_map.get(val, str(val))

            if children:
                monthly = [round(sum(c.values.sparkline[i] for c in children), 1) for i in range(12)]
            else:
                monthly = _blend_monthly(act_agg, comp_agg, current_filter)

            fy_total = sum(monthly)
            nodes.append(TreeNode(
                id=str(val),
                name=str(name),
                values=TreeNodeValues(
                    actual=round(fy_total, 1),
                    budget=round(fy_total, 1),
                    variance_pct=0,
                    sparkline=monthly,
                ),
                children=children,
            ))
        return nodes

    top_children = _build_level(0, {})

    grand_monthly = [round(sum(c.values.sparkline[i] for c in top_children), 1) for i in range(12)]
    grand_total = sum(grand_monthly)

    columns = MONTHS[:closed_month] + [f"{m}*" for m in MONTHS[closed_month:]] + ["FY Total"]

    return TreeTableSpec(
        period_label=f"Landing {year} (closed through {MONTHS[closed_month - 1]})",
        columns=["Name"] + columns,
        tree=TreeNode(
            id="TOTAL_AZ",
            name="Total AZ",
            values=TreeNodeValues(
                actual=round(grand_total, 1),
                budget=round(grand_total, 1),
                variance_pct=0,
                sparkline=grand_monthly,
            ),
            children=top_children,
        ),
    )

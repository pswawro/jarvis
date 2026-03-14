"""Generic chart endpoint — converts any view's tree into a LineChartSpec.

Returns cumulative series starting from PY End, fully described in JSON
so the frontend is a dumb renderer.
"""

from collections import deque

from fastapi import APIRouter, Query

from models import LineChartSpec, ChartSeries
from routes.brand import get_brand_view
from routes.region import get_region_view
from routes.unit import get_unit_view
from routes.market import get_market_view
from routes.tree_generic import get_tree

router = APIRouter()

COLORS = [
    "#2563EB", "#059669", "#D97706", "#7C3AED", "#DC2626",
    "#0891B2", "#4F46E5", "#CA8A04", "#0D9488", "#E11D48",
]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SCENARIO_COLORS = {
    "Actuals": "#2563EB",
    "Budget": "#DC2626",
    "MTP": "#059669",
    "RBU2": "#D97706",
    "Prior Year": "#9CA3AF",
}


def _to_series(name: str, data) -> ChartSeries:
    return ChartSeries(
        id=name.lower().replace(" ", "_"),
        name=name,
        color=SCENARIO_COLORS[name],
        data=[round(float(v), 1) for v in data.values],
    )


def _find_node(tree, node_id: str):
    """Find a node by id in the tree (BFS)."""
    queue = deque([tree])
    while queue:
        n = queue.popleft()
        if n.id == node_id:
            return n
        queue.extend(n.children)
    return None


def _tree_to_chart(tree_spec, cumulative: bool = True, drill: str | None = None) -> LineChartSpec:
    tree = tree_spec.tree

    drill_path: list[str] = []
    if drill:
        target = _find_node(tree, drill)
        if target and target.children:
            nodes = target.children
            # Build breadcrumb path
            drill_path = [target.name]
        else:
            nodes = tree.children if tree.children else [tree]
    else:
        nodes = tree.children if tree.children else [tree]

    # Include drillable node IDs so frontend knows which legends are clickable
    drillable_ids = [n.id for n in nodes if n.children]

    x_labels = ["PY End"] + MONTHS
    series_list: list[ChartSeries] = []

    for i, node in enumerate(nodes):
        py_total = 0.0
        if node.values.prior_year is not None:
            py_total = node.values.prior_year
        elif node.values.py_variance_pct is not None and node.values.py_variance_pct != 0:
            py_total = node.values.actual / (1 + node.values.py_variance_pct / 100)

        if cumulative:
            # PY End, then PY End + cumulative YTD per month
            data = [round(py_total, 1)]
            running = py_total
            for v in node.values.sparkline:
                running += v
                data.append(round(running, 1))
        else:
            data = [round(py_total, 1)] + [round(v, 1) for v in node.values.sparkline]

        series_list.append(ChartSeries(
            id=node.id,
            name=node.name,
            color=COLORS[i % len(COLORS)],
            data=data,
        ))

    return LineChartSpec(
        period_label=tree_spec.period_label,
        x_labels=x_labels,
        series=series_list,
        drillable_ids=drillable_ids,
        drill_path=drill_path,
    )


@router.get("/brand/chart", response_model=LineChartSpec)
def get_brand_chart(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None, drill: str | None = None, comparator: str = "BUD"):
    tree_spec = get_brand_view(year=year, quarter=quarter, market_id=market_id, ta=ta, comparator=comparator)
    return _tree_to_chart(tree_spec, drill=drill)


@router.get("/region/chart", response_model=LineChartSpec)
def get_region_chart(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None, drill: str | None = None, comparator: str = "BUD"):
    tree_spec = get_region_view(year=year, quarter=quarter, market_id=market_id, ta=ta, comparator=comparator)
    return _tree_to_chart(tree_spec, drill=drill)


@router.get("/unit/chart", response_model=LineChartSpec)
def get_unit_chart(year: int = 2025, quarter: str | None = None, drill: str | None = None, comparator: str = "BUD"):
    tree_spec = get_unit_view(year=year, quarter=quarter, comparator=comparator)
    return _tree_to_chart(tree_spec, drill=drill)


@router.get("/market/chart", response_model=LineChartSpec)
def get_market_chart(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None, drill: str | None = None):
    """Market view sparklines are share %, not revenue — show monthly share trend."""
    tree_spec = get_market_view(year=year, quarter=quarter, market_id=market_id, ta=ta)
    tree = tree_spec.tree

    drill_path: list[str] = []
    if drill:
        target = _find_node(tree, drill)
        if target and target.children:
            nodes = target.children
            drill_path = [target.name]
        else:
            nodes = tree.children if tree.children else [tree]
    else:
        nodes = tree.children if tree.children else [tree]

    drillable_ids = [n.id for n in nodes if n.children]

    series_list: list[ChartSeries] = []
    for i, node in enumerate(nodes):
        series_list.append(ChartSeries(
            id=node.id,
            name=node.name,
            color=COLORS[i % len(COLORS)],
            data=[round(v, 1) for v in node.values.sparkline],
        ))

    return LineChartSpec(
        period_label=tree_spec.period_label,
        x_labels=MONTHS,
        series=series_list,
        y_format="percent",
        drillable_ids=drillable_ids,
        drill_path=drill_path,
    )


@router.get("/tree/chart", response_model=LineChartSpec)
def get_tree_chart(
    levels: str = Query(..., description="Comma-separated level IDs"),
    year: int = 2025,
    quarter: str | None = None,
    market_id: str | None = None,
    ta: str | None = None,
    brand_id: str | None = None,
    comparator: str = "BUD",
    drill: str | None = None,
):
    """Generic chart endpoint using composable levels."""
    tree_spec = get_tree(levels=levels, year=year, quarter=quarter, market_id=market_id, ta=ta, brand_id=brand_id, comparator=comparator)

    # Detect competitive domain for share-based rendering
    level_list = [lv.strip() for lv in levels.split(",")]
    competitive_levels = {"category"}
    is_competitive = any(lv in competitive_levels for lv in level_list)

    if is_competitive:
        tree = tree_spec.tree
        drill_path: list[str] = []
        if drill:
            target = _find_node(tree, drill)
            if target and target.children:
                nodes = target.children
                drill_path = [target.name]
            else:
                nodes = tree.children if tree.children else [tree]
        else:
            nodes = tree.children if tree.children else [tree]

        drillable_ids = [n.id for n in nodes if n.children]
        series_list: list[ChartSeries] = []
        for i, node in enumerate(nodes):
            series_list.append(ChartSeries(
                id=node.id, name=node.name, color=COLORS[i % len(COLORS)],
                data=[round(v, 1) for v in node.values.sparkline],
            ))
        return LineChartSpec(
            period_label=tree_spec.period_label,
            x_labels=MONTHS,
            series=series_list,
            y_format="percent",
            drillable_ids=drillable_ids,
            drill_path=drill_path,
        )

    return _tree_to_chart(tree_spec, drill=drill)


@router.get("/scenario-chart", response_model=LineChartSpec)
def get_scenario_chart(
    year: int = 2025,
    entity_id: str | None = None,
    market_id: str | None = None,
    ta: str | None = None,
    brand_id: str | None = None,
    dimension: str | None = None,
    levels: str | None = None,
):
    """Multi-scenario overlay: Actuals / Budget / MTP / RBU2 / PY for one entity or total."""
    import data_loader

    # Detect expense domain from levels or legacy dimension param
    is_expense = False
    if levels:
        is_expense = any(lv.strip() in ("unit", "sub_unit") for lv in levels.split(","))
    elif dimension == "unit":
        is_expense = True

    if is_expense:
        return _scenario_chart_expense(year, entity_id, data_loader)

    rev = data_loader.revenue[data_loader.revenue.year == year]
    tgt = data_loader.targets[
        (data_loader.targets.target_type == "revenue")
        & (data_loader.targets.period_date.dt.year == year)
    ]
    rev_py = data_loader.revenue[data_loader.revenue.year == year - 1]

    if ta:
        ta_list = [t.strip() for t in ta.split(",")]
        ta_brands = data_loader.products[data_loader.products.therapeutic_area.isin(ta_list)].brand_id.tolist()
        rev = rev[rev.brand_id.isin(ta_brands)]
        tgt = tgt[tgt.entity_id.isin(ta_brands)]
        rev_py = rev_py[rev_py.brand_id.isin(ta_brands)]

    if brand_id:
        bid_list = [b.strip() for b in brand_id.split(",")]
        rev = rev[rev.brand_id.isin(bid_list)]
        tgt = tgt[tgt.entity_id.isin(bid_list)]
        rev_py = rev_py[rev_py.brand_id.isin(bid_list)]

    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
        rev = rev[rev.market_id.isin(mkt_list)]
        tgt = tgt[tgt.market_id.isin(mkt_list)]
        rev_py = rev_py[rev_py.market_id.isin(mkt_list)]

    if entity_id:
        rev = rev[rev.brand_id == entity_id]
        tgt = tgt[tgt.entity_id == entity_id]
        rev_py = rev_py[rev_py.brand_id == entity_id]

    # Monthly actuals
    act_monthly = rev.groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)
    py_monthly = rev_py.groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)

    # Monthly targets (single groupby)
    tgt_agg = tgt.groupby(tgt.period_date.dt.month)[["budget_amount", "mtp_amount", "rbu2_amount"]].sum().reindex(range(1, 13), fill_value=0)
    bud_monthly = tgt_agg["budget_amount"]
    mtp_monthly = tgt_agg["mtp_amount"]
    rbu2_monthly = tgt_agg["rbu2_amount"]

    entity_label = entity_id or "Total"
    return LineChartSpec(
        period_label=f"FY {year} — {entity_label}",
        x_labels=MONTHS,
        series=[
            _to_series("Actuals", act_monthly),
            _to_series("Budget", bud_monthly),
            _to_series("MTP", mtp_monthly),
            _to_series("RBU2", rbu2_monthly),
            _to_series("Prior Year", py_monthly),
        ],
    )


def _scenario_chart_expense(year: int, entity_id: str | None, data_loader) -> LineChartSpec:
    """Scenario chart for expense/unit dimension."""
    exp = data_loader.expenses
    tgt = data_loader.targets[data_loader.targets.target_type == "expense"]

    e = exp[exp.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    e_py = exp[exp.year == year - 1]

    if entity_id:
        e = e[e.sub_unit_id == entity_id]
        t = t[t.entity_id == entity_id]
        e_py = e_py[e_py.sub_unit_id == entity_id]

    act_monthly = e.groupby("month")["total_operating_expenses"].sum().reindex(range(1, 13), fill_value=0)
    py_monthly = e_py.groupby("month")["total_operating_expenses"].sum().reindex(range(1, 13), fill_value=0)

    tgt_agg = t.groupby(t.period_date.dt.month)[["budget_amount", "mtp_amount", "rbu2_amount"]].sum().reindex(range(1, 13), fill_value=0)

    entity_label = entity_id or "Total Expenses"
    return LineChartSpec(
        period_label=f"FY {year} — {entity_label}",
        x_labels=MONTHS,
        series=[
            _to_series("Actuals", act_monthly),
            _to_series("Budget", tgt_agg["budget_amount"]),
            _to_series("MTP", tgt_agg["mtp_amount"]),
            _to_series("RBU2", tgt_agg["rbu2_amount"]),
            _to_series("Prior Year", py_monthly),
        ],
    )

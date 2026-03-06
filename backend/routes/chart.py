"""Generic chart endpoint — converts any view's tree into a LineChartSpec.

Returns cumulative series starting from PY End, fully described in JSON
so the frontend is a dumb renderer.
"""

from fastapi import APIRouter, Query

from models import LineChartSpec, ChartSeries
from routes.brand import get_brand_view
from routes.region import get_region_view
from routes.unit import get_unit_view
from routes.market import get_market_view

router = APIRouter()

COLORS = [
    "#2563EB", "#059669", "#D97706", "#7C3AED", "#DC2626",
    "#0891B2", "#4F46E5", "#CA8A04", "#0D9488", "#E11D48",
]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _find_node(tree, node_id: str):
    """Find a node by id in the tree (BFS)."""
    queue = [tree]
    while queue:
        n = queue.pop(0)
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
def get_brand_chart(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None, drill: str | None = None):
    tree_spec = get_brand_view(year=year, quarter=quarter, market_id=market_id, ta=ta)
    return _tree_to_chart(tree_spec, drill=drill)


@router.get("/region/chart", response_model=LineChartSpec)
def get_region_chart(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None, drill: str | None = None):
    tree_spec = get_region_view(year=year, quarter=quarter, market_id=market_id, ta=ta)
    return _tree_to_chart(tree_spec, drill=drill)


@router.get("/unit/chart", response_model=LineChartSpec)
def get_unit_chart(year: int = 2025, quarter: str | None = None, drill: str | None = None):
    tree_spec = get_unit_view(year=year, quarter=quarter)
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

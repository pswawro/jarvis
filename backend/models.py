"""Pydantic models = JSON visualization specs."""

from pydantic import BaseModel


# --- KPI Spec ---

class KpiComparison(BaseModel):
    label: str
    variance_pct: float


class KpiCard(BaseModel):
    label: str
    value: float
    unit: str
    comparisons: list[KpiComparison]


class KpiStripSpec(BaseModel):
    type: str = "kpi_strip"
    period_label: str
    cards: list[KpiCard]


# --- Tree Table Spec ---

class TreeNodeValues(BaseModel):
    actual: float
    budget: float
    variance_pct: float
    prior_year: float | None = None
    py_variance_pct: float | None = None
    sparkline: list[float]
    forecast: float | None = None
    forecast_variance_pct: float | None = None
    market_share_pct: float | None = None
    market_growth_pct: float | None = None
    personnel_costs: float | None = None
    external_costs: float | None = None
    other_costs: float | None = None


class TreeNode(BaseModel):
    id: str
    name: str
    values: TreeNodeValues
    children: list["TreeNode"] = []


class TreeTableSpec(BaseModel):
    type: str = "tree_table"
    period_label: str
    columns: list[str]
    tree: TreeNode


# --- Chart Spec ---

class ChartSeries(BaseModel):
    id: str
    name: str
    color: str
    data: list[float]


class ReferenceLine(BaseModel):
    label: str
    style: str
    data: list[float]


class LineChartSpec(BaseModel):
    type: str = "line_chart"
    period_label: str
    x_labels: list[str]
    series: list[ChartSeries]
    reference_lines: list[ReferenceLine] = []
    y_format: str = "currency"  # "currency" | "percent"
    drillable_ids: list[str] = []
    drill_path: list[str] = []


# --- Assistant ---

class AssistantRequest(BaseModel):
    context: dict
    question: str


class AssistantChunk(BaseModel):
    type: str  # "tool_use" | "tool_done" | "facts" | "interpretation" | "hypothesis" | "visual" | "done" | "error"
    content: str

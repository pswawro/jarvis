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
    mtp: float | None = None
    mtp_variance_pct: float | None = None
    rbu2: float | None = None
    rbu2_variance_pct: float | None = None
    comparator_label: str | None = None
    comparator_value: float | None = None
    comparator_variance_pct: float | None = None
    market_share_pct: float | None = None
    market_growth_pct: float | None = None
    personnel_costs: float | None = None
    external_costs: float | None = None
    other_costs: float | None = None
    fte_count: float | None = None
    headcount: int | None = None
    cost_per_fte: float | None = None


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

class AssistantHistoryMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str  # question text or summary of assistant response

class AssistantRequest(BaseModel):
    context: dict = {}
    question: str
    history: list[AssistantHistoryMessage] = []


class AssistantChunk(BaseModel):
    type: str  # "tool_use" | "tool_done" | "facts" | "interpretation" | "hypothesis" | "visual" | "done" | "error"
    content: str


class InsightEntity(BaseModel):
    type: str
    brand_id: str | None = None
    market_id: str | None = None
    ta: str | None = None
    unit: str | None = None
    sub_unit: str | None = None


class InsightResponse(BaseModel):
    id: str
    fingerprint: str
    detected_at: str
    last_seen: str
    run_id: str
    entity: InsightEntity
    detection_type: str
    data_domain: str
    statistical_score: float
    status: str
    read: bool
    push: bool
    severity: str
    ai_analysis: dict | None = None
    raw_stats: dict = {}


class InsightsListResponse(BaseModel):
    insights: list[InsightResponse]
    unread_count: int
    unread_critical_count: int

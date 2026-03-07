// JSON visualization spec types — matches backend Pydantic models

export interface KpiComparison {
  label: string;
  variance_pct: number;
}

export interface KpiCard {
  label: string;
  value: number;
  unit: string;
  comparisons: KpiComparison[];
}

export interface KpiStripSpec {
  type: "kpi_strip";
  period_label: string;
  cards: KpiCard[];
}

export interface TreeNodeValues {
  actual: number;
  budget: number;
  variance_pct: number;
  prior_year: number | null;
  py_variance_pct: number | null;
  sparkline: number[];
  forecast: number | null;
  forecast_variance_pct: number | null;
  mtp: number | null;
  mtp_variance_pct: number | null;
  rbu2: number | null;
  rbu2_variance_pct: number | null;
  comparator_label: string | null;
  comparator_value: number | null;
  comparator_variance_pct: number | null;
  market_share_pct: number | null;
  market_growth_pct: number | null;
  personnel_costs: number | null;
  external_costs: number | null;
  other_costs: number | null;
  fte_count: number | null;
  headcount: number | null;
  cost_per_fte: number | null;
}

export interface TreeNode {
  id: string;
  name: string;
  values: TreeNodeValues;
  children: TreeNode[];
}

export interface TreeTableSpec {
  type: "tree_table";
  period_label: string;
  columns: string[];
  tree: TreeNode;
}

export interface ChartSeries {
  id: string;
  name: string;
  color: string;
  data: number[];
}

export interface ReferenceLine {
  label: string;
  style: string;
  data: number[];
}

export interface LineChartSpec {
  type: "line_chart";
  period_label: string;
  x_labels: string[];
  series: ChartSeries[];
  reference_lines: ReferenceLine[];
  y_format?: "currency" | "percent";
  drillable_ids: string[];
  drill_path: string[];
}

// Interaction event surfaced from charts — structured for LLM consumption
export interface ChartInteraction {
  type: "hover" | "click";
  series_name: string;
  series_id: string;
  x_label: string;
  x_index: number;
  value: number;
  formatted_value: string;
}

// FCT-aligned navigation types
export type PageType = "overview" | "landing" | "phased";

// Composable dimensions
export type LevelId = "ta" | "brand" | "market" | "region" | "unit" | "sub_unit" | "category";
export type Domain = "revenue" | "expense" | "competitive";

export interface LevelDef {
  id: LevelId;
  label: string;
  domain: Domain;
}

export interface DimensionConfig {
  levels: LevelId[];
  label?: string;
}

export interface SavedDimension {
  id: string;
  label: string;
  levels: LevelId[];
  createdAt: string;
}

// Legacy alias — kept for backward compat during migration
export type Dimension = "brand" | "region" | "unit" | "market";

// FCT-aligned filter types
export type Comparator = "BUD" | "MTP" | "RBU2" | "PYACT";
export type Scale = "M" | "K" | "B";
export type Granularity = "year" | "quarter" | "month";

export interface Filters {
  market_id: string[];
  ta: string[];
  product: string[];
  comparator: Comparator;
  scale: Scale;
  year: number;
  granularity: Granularity;
}

export interface Period {
  year: number;
  quarter: string | null;
}

export interface AssistantContext {
  source: "tree_row" | "treemap_bar" | "time_chart_point" | "header";
  page: PageType;
  dimension?: Dimension;
  levels?: LevelId[];
  period: Period;
  filters: Filters;
  dataPoint?: {
    node_id?: string;
    node_name?: string;
    values?: Partial<TreeNodeValues>;
    parent_path?: string[];
    drill_path?: string[];
    series_name?: string;
    series_id?: string;
    x_label?: string;
    value?: number;
    formatted_value?: string;
  };
}

// Config types from /api/config
export interface AppConfig {
  comparators: { id: string; label: string; field: string | null }[];
  period_types: { id: string; label: string }[];
  accounts: { id: string; label: string; category: string }[];
  scales: { id: string; label: string; divisor: number }[];
  defaults: { comparator: string; period_type: string; scale: string; month: number | null; account: string };
  data_refreshed_at?: string;
}

// Bookmark state for localStorage
export interface BookmarkState {
  id: string;
  label: string;
  period: Period;
  filters: Filters;
  activeView: number;
  createdAt: string;
}

// Assistant chat types
export interface ToolStatus {
  label: string;
  done: boolean;
}

export interface Visual {
  tool: "render_table" | "render_chart";
  title: string;
  headers?: string[];
  rows?: string[][];
  type?: "bar" | "line";
  labels?: string[];
  datasets?: { name: string; values: number[]; color?: string }[];
}

export interface ConfigProposal {
  summary: string;
  comparator?: string;
  year?: number;
  quarter?: string;
  market_id?: string[];
  ta?: string[];
  page?: string;
  dimension?: string;
  levels?: LevelId[];
  scale?: string;
  scenario_preset?: string;
}

export interface Clarification {
  question: string;
  options: string[];
}

export interface ThinkingStep {
  step: "plan" | "finding" | "pivot";
  content: string;
}

export type TimelineEvent =
  | { kind: "tool"; tool: ToolStatus }
  | { kind: "thinking"; step: ThinkingStep };

export interface Message {
  role: "user" | "assistant";
  question?: string;
  facts?: string;
  interpretation?: string;
  hypothesis?: string;
  tools?: ToolStatus[];
  visuals?: Visual[];
  configProposal?: ConfigProposal;
  clarification?: Clarification;
  thinking?: ThinkingStep[];
  timeline?: TimelineEvent[];
}

export interface ChatSummary {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface ChatState {
  id: string;
  title: string;
  messages: Message[];
  context: AssistantContext | null;
  createdAt: string;
  updatedAt: string;
}

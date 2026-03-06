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
  market_share_pct: number | null;
  market_growth_pct: number | null;
  personnel_costs: number | null;
  external_costs: number | null;
  other_costs: number | null;
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

export interface Filters {
  market_id: string[];
  ta: string[];
}

export interface Period {
  year: number;
  quarter: string | null;
}

export interface AssistantContext {
  source: "tree_row" | "treemap_bar" | "time_chart_point" | "header";
  view: "Brand" | "Region" | "Unit" | "Market";
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

import type { Filters } from "./types";

export function filtersToExtra(filters: Filters): Record<string, string> {
  const extra: Record<string, string> = {};
  if (filters.market_id.length) extra.market_id = filters.market_id.join(",");
  if (filters.ta.length) extra.ta = filters.ta.join(",");
  if (filters.product.length) extra.brand_id = filters.product.join(",");
  extra.comparator = filters.comparator;
  return extra;
}

/** Scale factors: raw data is in $M. Divide by factor to get target unit. */
const SCALE_DIVISORS: Record<string, number> = { M: 1, K: 0.001, B: 1000 };

export function scaleValue(value: number, scale: string): string {
  const d = SCALE_DIVISORS[scale] || 1;
  const scaled = value / d;
  if (scale === "B") return scaled.toFixed(2);
  if (scale === "K") return Math.round(scaled).toLocaleString();
  return scaled.toFixed(1);
}

export function scaleLabel(scale: string): string {
  return scale === "M" ? "$M" : scale === "K" ? "$K" : "$B";
}

const COMPARATOR_LABELS: Record<string, string> = {
  BUD: "vs Bgt",
  MTP: "vs MTP",
  RBU2: "vs RBU2",
  PYACT: "vs PY",
};

export function comparatorLabel(comparator: string): string {
  return COMPARATOR_LABELS[comparator] ?? "vs Bgt";
}

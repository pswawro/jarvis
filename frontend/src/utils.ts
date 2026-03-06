import type { Filters } from "./types";

export function filtersToExtra(filters: Filters): Record<string, string> {
  const extra: Record<string, string> = {};
  if (filters.market_id.length) extra.market_id = filters.market_id.join(",");
  if (filters.ta.length) extra.ta = filters.ta.join(",");
  return extra;
}

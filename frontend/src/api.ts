import type { Period } from "./types";

const BASE = "/api";

export async function fetchApi<T>(
  path: string,
  period: Period,
  extra?: Record<string, string>
): Promise<T> {
  const params = new URLSearchParams({ year: String(period.year) });
  if (period.quarter) params.set("quarter", period.quarter);
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      if (v) params.set(k, v);
    }
  }
  const res = await fetch(`${BASE}${path}?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

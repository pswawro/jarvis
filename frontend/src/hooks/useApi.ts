import { useState, useEffect } from "react";
import { fetchApi } from "../api";
import type { Period } from "../types";

export function useApi<T>(
  path: string,
  period: Period,
  extra?: Record<string, string>
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchApi<T>(path, period, extra)
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [path, period.year, period.quarter, JSON.stringify(extra)]);

  return { data, loading, error };
}

import { useState, useEffect, useMemo } from "react";
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

  // Stabilize extra as a string key outside the effect dependency array
  const extraKey = useMemo(() => JSON.stringify(extra), [extra]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const parsedExtra: Record<string, string> | undefined = extraKey ? JSON.parse(extraKey) : undefined;
    fetchApi<T>(path, period, parsedExtra)
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
  }, [path, period.year, period.quarter, extraKey]);

  return { data, loading, error };
}

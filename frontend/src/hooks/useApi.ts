import { useState, useEffect, useMemo } from "react";
import { fetchApi } from "../api";
import type { Period } from "../types";

export function useApi<T>(
  path: string,
  period: Period,
  extra?: Record<string, string>
) {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: string | null }>({
    data: null,
    loading: true,
    error: null,
  });

  // Stabilize extra as a string key outside the effect dependency array
  const extraKey = useMemo(() => JSON.stringify(extra), [extra]);

  // Reset to loading when inputs change
  const fetchKey = `${path}|${period.year}|${period.quarter}|${extraKey}`;
  const [prevFetchKey, setPrevFetchKey] = useState(fetchKey);
  if (fetchKey !== prevFetchKey) {
    setPrevFetchKey(fetchKey);
    setState({ data: null, loading: true, error: null });
  }

  useEffect(() => {
    let cancelled = false;

    const parsedExtra: Record<string, string> | undefined = extraKey ? JSON.parse(extraKey) : undefined;
    fetchApi<T>(path, period, parsedExtra)
      .then((d) => {
        if (!cancelled) {
          setState({ data: d, loading: false, error: null });
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setState({ data: null, loading: false, error: e.message });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [path, period, extraKey]);

  return state;
}

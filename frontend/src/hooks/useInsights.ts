import { useState, useEffect, useCallback, useRef } from "react";
import type { InsightsListResponse } from "../types";

export function useInsights() {
  const [data, setData] = useState<InsightsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const pendingRef = useRef(new Set<string>());
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const source = new EventSource("/api/insights/stream");
    sourceRef.current = source;

    source.onmessage = (event) => {
      try {
        const json: InsightsListResponse = JSON.parse(event.data);
        setData(json);
        setError(null);
        setLoading(false);
      } catch (e) {
        console.warn("Failed to parse SSE data:", e);
        setError("Received invalid data from server");
        setLoading(false);
      }
    };

    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) {
        setError("Connection closed. Please refresh the page.");
      } else {
        setError("Connection lost, reconnecting...");
      }
    };

    abortRef.current = new AbortController();

    return () => {
      source.close();
      sourceRef.current = null;
      abortRef.current?.abort();
    };
  }, []);

  const markRead = useCallback(async (id: string) => {
    // Guard: check current data via ref-like pattern to avoid React 19 batching issues
    // We always fire the API call and let the server be the source of truth;
    // the optimistic update is just for UI responsiveness.
    setData((prev) => {
      if (!prev) return prev;
      const target = prev.insights.find((i) => i.id === id);
      if (!target || target.read) return prev;
      return {
        ...prev,
        insights: prev.insights.map((i) =>
          i.id === id ? { ...i, read: true } : i
        ),
        unread_count: Math.max(0, prev.unread_count - 1),
        unread_critical_count:
          target.severity === "critical"
            ? Math.max(0, prev.unread_critical_count - 1)
            : prev.unread_critical_count,
      };
    });

    try {
      const resp = await fetch(`/api/insights/${id}/read`, { method: "POST", signal: abortRef.current?.signal });
      if (!resp.ok) console.warn(`Failed to mark insight ${id} as read: HTTP ${resp.status}`);
    } catch {
      // SSE will reconcile state
    }
  }, []);

  const toggleBookmark = useCallback(async (id: string) => {
    if (pendingRef.current.has(id)) return;
    pendingRef.current.add(id);

    let shouldBookmark: boolean | null = null;

    setData((prev) => {
      if (!prev) return prev;
      const target = prev.insights.find((i) => i.id === id);
      if (!target) return prev;
      shouldBookmark = !target.bookmarked;
      return {
        ...prev,
        insights: prev.insights.map((i) =>
          i.id === id ? { ...i, bookmarked: shouldBookmark! } : i
        ),
      };
    });

    if (shouldBookmark === null) {
      pendingRef.current.delete(id);
      return;
    }

    const endpoint = shouldBookmark ? "bookmark" : "unbookmark";
    try {
      const resp = await fetch(`/api/insights/${id}/${endpoint}`, { method: "POST", signal: abortRef.current?.signal });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    } catch {
      // Revert on failure
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          insights: prev.insights.map((i) =>
            i.id === id ? { ...i, bookmarked: !shouldBookmark! } : i
          ),
        };
      });
    } finally {
      pendingRef.current.delete(id);
    }
  }, []);

  const getInsightContext = useCallback(async (id: string) => {
    const resp = await fetch(`/api/insights/${id}/chat`, { method: "POST", signal: abortRef.current?.signal });
    if (!resp.ok) throw new Error(`Failed to load insight context: HTTP ${resp.status}`);
    return resp.json();
  }, []);

  const subscribeToPush = useCallback(async () => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;

    try {
      const reg = await navigator.serviceWorker.register("/sw.js");
      const permission = await Notification.requestPermission();
      if (permission !== "granted") return;

      const configResp = await fetch("/api/config");
      const config = await configResp.json();
      if (!config.vapid_public_key) return;

      const subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: config.vapid_public_key,
      });

      await fetch("/api/push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subscription: subscription.toJSON() }),
      });
    } catch (e) {
      console.warn("Push subscription failed:", e);
    }
  }, []);

  return {
    insights: data?.insights ?? [],
    unreadCount: data?.unread_count ?? 0,
    unreadCriticalCount: data?.unread_critical_count ?? 0,
    loading,
    error,
    markRead,
    toggleBookmark,
    getInsightContext,
    subscribeToPush,
  };
}

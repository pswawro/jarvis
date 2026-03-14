import { useState, useEffect, useCallback, useRef } from "react";
import type { InsightsListResponse } from "../types";

export function useInsights() {
  const [data, setData] = useState<InsightsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const source = new EventSource("/api/insights/stream");
    sourceRef.current = source;

    source.onmessage = (event) => {
      try {
        const json: InsightsListResponse = JSON.parse(event.data);
        setData(json);
        setError(null);
      } catch (e) {
        console.warn("Failed to parse SSE data:", e);
      }
      setLoading(false);
    };

    source.onerror = () => {
      // EventSource auto-reconnects; just flag the error state temporarily
      setError("Connection lost, reconnecting...");
    };

    return () => {
      source.close();
      sourceRef.current = null;
    };
  }, []);

  const markRead = useCallback(async (id: string) => {
    // Check if already read before decrementing counts
    const insight = data?.insights.find((i) => i.id === id);
    if (insight?.read) return;

    await fetch(`/api/insights/${id}/read`, { method: "POST" });
    // Optimistic local update; SSE will confirm shortly
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
  }, [data?.insights]);

  const getInsightContext = useCallback(async (id: string) => {
    const resp = await fetch(`/api/insights/${id}/chat`, { method: "POST" });
    if (!resp.ok) throw new Error(`Failed to load insight context: HTTP ${resp.status}`);
    return resp.json();
  }, []);

  const subscribeToPush = useCallback(async () => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;

    try {
      const reg = await navigator.serviceWorker.register("/sw.js");
      const permission = await Notification.requestPermission();
      if (permission !== "granted") return;

      // Get VAPID public key from backend config
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
    getInsightContext,
    subscribeToPush,
  };
}

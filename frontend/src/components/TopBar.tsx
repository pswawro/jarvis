import { useEffect, useState } from "react";
import clsx from "clsx";

interface Props {
  onAssistantOpen?: () => void;
  onExport?: () => void;
  onInsightsOpen?: () => void;
  hasNotification?: boolean;
  unreadInsightCount?: number;
  hasUnreadCritical?: boolean;
}

export function TopBar({ onAssistantOpen, onExport, onInsightsOpen, hasNotification, unreadInsightCount, hasUnreadCritical }: Props) {
  const [freshness, setFreshness] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/config", { signal: controller.signal })
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((cfg) => setFreshness(cfg.data_refreshed_at))
      .catch(() => {});
    return () => controller.abort();
  }, []);

  return (
    <header className="bg-az-navy">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-white/95 to-white/80 flex items-center justify-center shadow-sm shadow-black/20">
            <span className="text-az-navy text-sm font-extrabold leading-none">J</span>
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-white text-[15px] tracking-tight leading-none">Jarvis</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[10px] text-white/30 font-medium tracking-[0.15em] uppercase leading-none">AstraZeneca</span>
              {freshness && (
                <span className="text-[9px] text-white/20 font-medium leading-none" title="Data refreshed at">
                  {freshness}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {onExport && (
            <button
              onClick={onExport}
              className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
              title="Export CSV"
            >
              <svg className="w-4 h-4 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
            </button>
          )}
          {onInsightsOpen && (
            <button
              onClick={onInsightsOpen}
              className={clsx(
                "relative w-8 h-8 rounded-lg flex items-center justify-center transition-colors",
                hasUnreadCritical
                  ? "bg-amber-500/20 border border-amber-500/40 hover:bg-amber-500/30"
                  : "bg-white/10 hover:bg-white/20"
              )}
              title="Push Insights"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5.002 5.002 0 117.072 0l.46 2.298a1 1 0 01-.981 1.197h-6.078a1 1 0 01-.981-1.197l.46-2.298z"
                  className={hasUnreadCritical ? "text-amber-400" : "text-white/70"}
                />
              </svg>
              {(unreadInsightCount ?? 0) > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 rounded-full bg-red-500 flex items-center justify-center border-2 border-az-navy">
                  <span className="text-white text-[8px] font-bold">{unreadInsightCount}</span>
                </span>
              )}
            </button>
          )}
          {onAssistantOpen && (
            <button
              onClick={onAssistantOpen}
              className="relative w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
              title="Ask Jarvis"
            >
              <svg className="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none">
                <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5A8.48 8.48 0 0121 11v.5z" stroke="url(#ai-grad)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="8.5" cy="11.5" r="1" fill="url(#ai-grad)" opacity={0.8} />
                <circle cx="12.5" cy="11.5" r="1" fill="url(#ai-grad)" opacity={0.8} />
                <circle cx="16.5" cy="11.5" r="1" fill="url(#ai-grad)" opacity={0.8} />
                <defs>
                  <linearGradient id="ai-grad" x1="3" y1="3" x2="21" y2="21" gradientUnits="userSpaceOnUse">
                    <stop stopColor="#c4b5fd" />
                    <stop offset="1" stopColor="#60a5fa" />
                  </linearGradient>
                </defs>
              </svg>
              {hasNotification && (
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-amber-400 ring-2 ring-az-navy" />
              )}
            </button>
          )}
        </div>
      </div>
      <div className="h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
    </header>
  );
}

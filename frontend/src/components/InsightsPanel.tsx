import { useState, useMemo } from "react";
import { motion, AnimatePresence, type PanInfo } from "framer-motion";
import type { Insight } from "../types";
import { InsightCard } from "./InsightCard";

interface Props {
  open: boolean;
  onClose: () => void;
  insights: Insight[];
  onAddToChat: (id: string) => void;
  onToggleBookmark: (id: string) => void;
}

type SortBy = "date" | "severity";

const SEVERITY_ORDER: Record<string, number> = { critical: 0, notable: 1, informational: 2 };

export function InsightsPanel({ open, onClose, insights, onAddToChat, onToggleBookmark }: Props) {
  const [sortBy, setSortBy] = useState<SortBy>("date");
  const [bookmarkFilter, setBookmarkFilter] = useState(false);

  const filtered = useMemo(() => {
    if (!bookmarkFilter) return insights;
    return insights.filter((i) => i.bookmarked);
  }, [insights, bookmarkFilter]);

  const sorted = useMemo(() => [...filtered].sort((a, b) => {
    if (sortBy === "severity") {
      const sevDiff = (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3);
      if (sevDiff !== 0) return sevDiff;
    }
    return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
  }), [filtered, sortBy]);

  const handleDragEnd = (_: unknown, info: PanInfo) => {
    if (info.offset.y > 100) onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/60 z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            className="fixed inset-x-0 bottom-0 z-50 bg-[#0f1225] rounded-t-2xl max-h-[85vh] flex flex-col"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            drag="y"
            dragConstraints={{ top: 0 }}
            dragElastic={0.2}
            onDragEnd={handleDragEnd}
          >
            {/* Drag handle */}
            <div className="flex justify-center pt-3 pb-2 cursor-grab active:cursor-grabbing">
              <div className="w-10 h-1 rounded-full bg-white/20" />
            </div>

            {/* Header */}
            <div className="flex items-center justify-between px-4 pb-3">
              <div className="flex items-center gap-2">
                <span className="text-[15px]">💡</span>
                <span className="text-white font-semibold text-[15px]">Push Insights</span>
              </div>
              <div className="flex gap-1.5">
                <button
                  onClick={() => setBookmarkFilter((v) => !v)}
                  className={`text-[11px] px-2 py-0.5 rounded-xl border transition-colors flex items-center gap-1 ${
                    bookmarkFilter
                      ? "border-amber-400/50 text-amber-400"
                      : "border-white/10 text-white/40 hover:border-white/20"
                  }`}
                  title={bookmarkFilter ? "Show all" : "Show bookmarked only"}
                  aria-label={bookmarkFilter ? "Show all insights" : "Show bookmarked only"}
                  aria-pressed={bookmarkFilter}
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill={bookmarkFilter ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                  </svg>
                </button>
                <button
                  onClick={() => setSortBy("date")}
                  className={`text-[11px] px-2 py-0.5 rounded-xl border transition-colors ${
                    sortBy === "date"
                      ? "border-white/30 text-white/70"
                      : "border-white/10 text-white/40 hover:border-white/20"
                  }`}
                >
                  Date ↓
                </button>
                <button
                  onClick={() => setSortBy("severity")}
                  className={`text-[11px] px-2 py-0.5 rounded-xl border transition-colors ${
                    sortBy === "severity"
                      ? "border-white/30 text-white/70"
                      : "border-white/10 text-white/40 hover:border-white/20"
                  }`}
                >
                  Severity
                </button>
              </div>
            </div>

            {/* Insight list */}
            <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-2">
              {sorted.length === 0 ? (
                <div className="text-center text-white/30 text-sm py-12">
                  {bookmarkFilter ? "No bookmarked insights" : "No insights detected yet"}
                </div>
              ) : (
                sorted.map((ins) => (
                  <InsightCard key={ins.id} insight={ins} onAddToChat={onAddToChat} onToggleBookmark={onToggleBookmark} />
                ))
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

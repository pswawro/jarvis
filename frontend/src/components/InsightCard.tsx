import { useState } from "react";
import clsx from "clsx";
import type { Insight } from "../types";
import { parseMarkdown } from "./assistant";

interface Props {
  insight: Insight;
  onAddToChat: (id: string) => void;
  onToggleBookmark: (id: string) => void;
}

const SEVERITY_STYLES = {
  critical: { chip: "text-red-400 bg-red-400/15", border: "border-l-red-500" },
  notable: { chip: "text-amber-400 bg-amber-400/15", border: "border-l-amber-500" },
  informational: { chip: "text-white/40 bg-white/8", border: "border-l-white/20" },
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0) return "just now";
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function InsightCard({ insight, onAddToChat, onToggleBookmark }: Props) {
  const isInactive = insight.status === "inactive";
  const hasAI = !!insight.ai_analysis && (!!insight.ai_analysis.explanation || (insight.ai_analysis.sections?.length ?? 0) > 0);
  const styles = SEVERITY_STYLES[insight.severity] ?? SEVERITY_STYLES.informational;

  return (
    <div
      className={clsx(
        "rounded-[10px] p-3 border-l-[3px] transition-opacity",
        styles.border,
        isInactive ? "bg-white/[0.02] opacity-50" : insight.read ? "bg-white/[0.04] opacity-75" : "bg-white/[0.06]"
      )}
    >
      {/* Header row */}
      <div className="flex items-center gap-1.5 mb-1.5">        {isInactive ? (
          <span className="text-[9px] font-bold text-white/40 bg-white/8 px-1.5 py-0.5 rounded uppercase">
            Inactive
          </span>
        ) : (
          <span className={clsx("text-[9px] font-bold px-1.5 py-0.5 rounded uppercase", styles.chip)}>
            {insight.severity}
          </span>
        )}        {!isInactive && hasAI && insight.ai_analysis?.sections?.length && (
          <span
            className={clsx(
              "text-[9px] font-bold px-1.5 py-0.5 rounded uppercase",
              insight.outcome === "positive"
                ? "text-emerald-400 bg-emerald-400/15"
                : "text-rose-400 bg-rose-400/15"
            )}
            title={insight.outcome === "positive" ? "Positive outcome" : "Negative outcome"}
          >
            {insight.outcome === "positive" ? "↑ positive" : "↓ negative"}
          </span>
        )}
        <span className="text-[10px] text-white/30">{relativeTime(insight.detected_at)}</span>
        <button
          onClick={(e) => { e.stopPropagation(); onToggleBookmark(insight.id); }}
          className="ml-auto text-white/30 hover:text-amber-400 transition-colors"
          title={insight.bookmarked ? "Remove bookmark" : "Bookmark"}
          aria-label={insight.bookmarked ? "Remove bookmark" : "Bookmark"}
          aria-pressed={insight.bookmarked}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill={insight.bookmarked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" className={insight.bookmarked ? "text-amber-400" : ""} />
          </svg>
        </button>
        {!insight.read && !isInactive && (
          <div className="w-1.5 h-1.5 rounded-full bg-blue-400" title="Unread" />
        )}
      </div>

      {/* Title — build from entity + detection type */}
      <div className="text-[13px] font-medium text-white mb-1 leading-snug">
        {_buildTitle(insight)}
      </div>

      {/* AI Analysis */}
      {hasAI ? (
        <InsightAnalysis ai={insight.ai_analysis!} />
      ) : (
        <div className="text-[11px] text-white/50 leading-relaxed">
          Statistical detection only — no AI analysis
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-1.5 mt-2">
        <button
          onClick={() => onAddToChat(insight.id)}
          className="text-[10px] text-blue-400/80 hover:text-blue-400 transition-colors"
        >
          {hasAI ? "Add to chat →" : "Add to chat & analyze →"}
        </button>
      </div>
    </div>
  );
}

const SECTION_LABELS: Record<string, string> = {
  facts: "Key Facts",
  interpretation: "Interpretation",
  hypothesis: "Hypothesis",
  recommendations: "Suggested Actions",
};

const SECTION_COLORS: Record<string, string> = {
  facts: "border-green-500",
  interpretation: "border-blue-500",
  hypothesis: "border-purple-500",
  recommendations: "border-amber-500",
};

function InsightAnalysis({ ai }: { ai: NonNullable<Insight["ai_analysis"]> }) {
  const [expanded, setExpanded] = useState(false);
  const sections = ai.sections ?? [];

  // Show first section as preview, rest on expand
  const preview = sections[0];
  const rest = sections.slice(1);

  if (!preview) {
    if (!ai.explanation) {
      return (
        <div className="text-[11px] text-white/40 leading-relaxed italic">
          AI analysis pending
        </div>
      );
    }
    return (
      <div className="text-[11px] text-white/60 leading-relaxed whitespace-pre-line">
        {parseMarkdown(ai.explanation, true)}
      </div>
    );
  }

  return (
    <div className="text-[11px] leading-relaxed space-y-1.5">
      {/* First section shown as preview */}
      <InsightSection tag={preview[0]} content={preview[1]} />

      {rest.length > 0 && expanded && (
        <div className="space-y-1.5">
          {rest.map(([tag, content]) => (
            <InsightSection key={tag} tag={tag} content={content} />
          ))}
        </div>
      )}
      {rest.length > 0 && (
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
          className="text-[10px] text-white/30 hover:text-white/50 transition-colors mt-1"
        >
          {expanded ? "Show less" : `Show more (${rest.length} sections)`}
        </button>
      )}
    </div>
  );
}

function InsightSection({ tag, content }: { tag: string; content: string }) {
  const color = SECTION_COLORS[tag] ?? "border-white/20";
  const label = SECTION_LABELS[tag] ?? tag;
  return (
    <div className={`border-l-2 ${color} pl-2.5`}>
      <div className="text-[9px] font-bold uppercase tracking-wider text-white/35 mb-0.5">
        {label}
      </div>
      <div className="text-white/60">{content ? parseMarkdown(content, true) : null}</div>
    </div>
  );
}

function _buildTitle(ins: Insight): string {
  const entity = ins.entity;
  const name = entity.brand_id || entity.ta || entity.unit || entity.sub_unit || "Total";
  const market = entity.market_id ? ` ${entity.market_id}` : "";
  const domain = ins.data_domain === "revenue" ? "revenue" : ins.data_domain === "expenses" ? "OpEx" : "market share";
  const stats = ins.raw_stats ?? {};

  switch (ins.detection_type) {
    case "outlier": {
      const current = stats.current_value as number | undefined;
      const mean = stats.mean as number | undefined;
      if (current != null && mean != null) {
        const dir = current > mean ? "above" : "below";
        return `${name}${market} ${domain} ${dir} average (z=${stats.zscore ?? "?"})`;
      }
      return `${name}${market} ${domain} outlier detected`;
    }
    case "drift":
      return `${name}${market} ${domain} trending away from baseline`;
    case "target_miss": {
      const missPct = stats.miss_pct as number | undefined;
      if (missPct != null) {
        return `${name}${market} ${domain} ${(missPct * 100).toFixed(0)}% below target`;
      }
      return `${name}${market} ${domain} below target`;
    }
    case "competitive_shift": {
      const delta = stats.delta_pct as number | undefined;
      if (delta != null) {
        const dir = delta > 0 ? "gained" : "lost";
        return `${name}${market} ${dir} ${Math.abs(delta).toFixed(1)}pp market share`;
      }
      return `${name}${market} market share shift detected`;
    }
    default:
      return `${name}${market} anomaly detected`;
  }
}

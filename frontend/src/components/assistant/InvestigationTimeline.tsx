import { useState } from "react";
import type { TimelineEvent } from "../../types";

const STEP_ICONS: Record<string, string> = { plan: "\ud83d\udd0d", finding: "\ud83d\udca1", pivot: "\u21a9\ufe0f" };
const STEP_COLORS: Record<string, string> = { plan: "text-gray-500", finding: "text-gray-600", pivot: "text-amber-600" };

export function InvestigationTimeline({ timeline, defaultExpanded }: { timeline: TimelineEvent[]; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded ?? false);

  if (timeline.length === 0) return null;

  const toolCount = timeline.filter((e) => e.kind === "tool").length;
  const thinkCount = timeline.filter((e) => e.kind === "thinking").length;
  const parts: string[] = [];
  if (toolCount > 0) parts.push(`${toolCount} tool${toolCount > 1 ? "s" : ""}`);
  if (thinkCount > 0) parts.push(`${thinkCount} step${thinkCount > 1 ? "s" : ""}`);

  return (
    <div className="space-y-1">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
      >
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? "rotate-90" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span>Investigation ({parts.join(", ")})</span>
      </button>
      {expanded && (
        <div className="space-y-1 pl-2 border-l-2 border-gray-200 ml-1">
          {timeline.map((event, i) =>
            event.kind === "tool" ? (
              <div key={i} className={`flex items-center gap-2 text-[11px] ${event.tool.done ? "text-gray-400" : "text-gray-600"}`}>
                {event.tool.done ? (
                  <svg className="w-3 h-3 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <span className="w-3 h-3 flex items-center justify-center">
                    <span className="w-1.5 h-1.5 bg-az-navy rounded-full animate-pulse" />
                  </span>
                )}
                <span>{event.tool.label}</span>
              </div>
            ) : (
              <div key={i} className="flex items-start gap-1.5 text-[11px]">
                <span className="shrink-0 leading-none mt-px">{STEP_ICONS[event.step.step] || ""}</span>
                <span className={STEP_COLORS[event.step.step] || "text-gray-500"}>{event.step.content}</span>
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}

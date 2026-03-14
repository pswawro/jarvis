import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type {
  AssistantContext,
  Message,
  ToolStatus,
  Visual,
  ConfigProposal,
  Clarification,
  ThinkingStep,
  TimelineEvent,
  ChatSummary,
} from "../types";
import { ChatListPanel } from "./ChatListPanel";

interface Props {
  open: boolean;
  onClose: () => void;

  // From useAssistantChat hook
  activeChatId: string | null;
  messages: Message[];
  activeContext: AssistantContext | null;
  loading: boolean;
  liveTools: ToolStatus[];
  liveVisuals: Visual[];
  liveResponse: { facts: string; interpretation: string; hypothesis: string; recommendations: string };
  liveConfigProposal: ConfigProposal | null;
  liveClarification: Clarification | null;
  liveThinking: ThinkingStep[];
  liveTimeline: TimelineEvent[];

  sendQuestion: (q: string) => void;
  setActiveContext: (ctx: AssistantContext | null) => void;
  onApplyConfig?: (cfg: ConfigProposal) => void;

  chatList: ChatSummary[];
  switchChat: (id: string) => void;
  newChat: (context?: AssistantContext) => void;
  deleteChat: (id: string) => void;
}

const COMPARATOR_LABELS: Record<string, string> = { BUD: "Budget", MTP: "Mid-Term Plan", RBU2: "Reforecast", PYACT: "Prior Year" };
const PAGE_LABELS: Record<string, string> = { overview: "Overview", landing: "Landing", trend: "Trend", scenarios: "Scenarios" };
const DIM_LABELS: Record<string, string> = { brand: "Brand", region: "Region", unit: "Unit", market: "Market" };

function ContextChip({ context, onClear }: { context: AssistantContext; onClear: () => void }) {
  if (context.source === "header") return null;
  const dp = context.dataPoint;
  const dimLabel = context.dimension ? (DIM_LABELS[context.dimension] || context.dimension) : context.levels?.join(" → ");
  const parts = [dp?.node_name || dp?.series_name || "", dimLabel ? `${dimLabel} / ${PAGE_LABELS[context.page] || context.page}` : (PAGE_LABELS[context.page] || context.page), `${context.period.year}${context.period.quarter ? " " + context.period.quarter : ""}`].filter(Boolean);
  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 rounded-lg text-[12px] text-gray-600">
      <span className="text-gray-400">&#x1f4cd;</span>
      <span className="truncate">{parts.join(" \u00b7 ")}</span>
      <button onClick={onClear} className="ml-auto shrink-0 text-gray-400 hover:text-gray-600 transition-colors">
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

const STEP_ICONS: Record<string, string> = { plan: "\ud83d\udd0d", finding: "\ud83d\udca1", pivot: "\u21a9\ufe0f" };
const STEP_COLORS: Record<string, string> = { plan: "text-gray-500", finding: "text-gray-600", pivot: "text-amber-600" };

function InvestigationTimeline({ timeline, defaultExpanded }: { timeline: TimelineEvent[]; defaultExpanded?: boolean }) {
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

function parseBold(text: string, keyBase: number) {
  const parts: (string | JSX.Element)[] = [];
  const re = /\*\*(.+?)\*\*/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = keyBase;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    parts.push(<strong key={key++} className="font-semibold text-gray-800">{match[1]}</strong>);
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function parseMarkdown(text: string) {
  const lines = text.split("\n");
  const result: JSX.Element[] = [];
  let bullets: string[] = [];
  let tableRows: string[][] = [];
  let key = 0;

  const flushBullets = () => {
    if (bullets.length === 0) return;
    result.push(
      <ul key={key++} className="list-disc list-inside space-y-0.5">
        {bullets.map((b, i) => (
          <li key={i}>{parseBold(b, key + i * 100)}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  const flushTable = () => {
    if (tableRows.length === 0) return;
    const header = tableRows[0];
    const body = tableRows.slice(1);
    result.push(
      <div key={key++} className="overflow-x-auto my-1">
        <table className="w-full text-[12px] border-collapse">
          <thead>
            <tr className="border-b border-gray-200">
              {header.map((h, i) => (
                <th key={i} className="text-left py-1.5 px-2 font-semibold text-gray-600 whitespace-nowrap">{parseBold(h.trim(), key + i * 100)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((row, ri) => (
              <tr key={ri} className="border-b border-gray-50">
                {row.map((cell, ci) => (
                  <td key={ci} className="py-1 px-2 text-gray-700 whitespace-nowrap">{parseBold(cell.trim(), key + ri * 100 + ci)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );
    tableRows = [];
  };

  const isTableRow = (line: string) => line.trim().startsWith("|") && line.trim().endsWith("|");
  const isSeparator = (line: string) => /^\|[\s:-]+(\|[\s:-]+)*\|$/.test(line.trim());
  const parseTableRow = (line: string) => line.trim().slice(1, -1).split("|");

  for (const line of lines) {
    if (isTableRow(line)) {
      flushBullets();
      if (isSeparator(line)) continue; // skip --- separator rows
      tableRows.push(parseTableRow(line));
    } else {
      flushTable();
      const bullet = line.match(/^[-•]\s+(.*)/);
      if (bullet) {
        bullets.push(bullet[1]);
      } else {
        flushBullets();
        result.push(<span key={key++}>{parseBold(line, key * 100)}{"\n"}</span>);
      }
    }
  }
  flushBullets();
  flushTable();
  return result;
}

function CollapsedMessage({ msg, index, onApply, applied }: { msg: Message; index: number; onApply: (p: ConfigProposal, i: number) => void; applied: boolean }) {
  const [expanded, setExpanded] = useState(false);
  // Build a short summary of the assistant response
  const summary = msg.configProposal
    ? `Config: ${msg.configProposal.summary || "View change proposed"}`
    : msg.clarification
    ? `Asked: ${msg.clarification.question}`
    : msg.facts
    ? msg.facts.slice(0, 80) + (msg.facts.length > 80 ? "..." : "")
    : "Response";

  return (
    <div className="space-y-1">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-[11px] text-gray-400 hover:text-gray-600 transition-colors w-full text-left"
      >
        <svg
          className={`w-3 h-3 shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span className="truncate">{summary}</span>
      </button>
      {expanded && (
        <div className="space-y-2 pl-3 border-l border-gray-200 ml-1">
          {msg.configProposal && (
            <ConfigProposalCard
              proposal={msg.configProposal}
              onApply={() => onApply(msg.configProposal!, index)}
              applied={applied}
            />
          )}
          {msg.facts && <Section label="Facts" color="border-green-500" content={msg.facts} />}
          {msg.interpretation && <Section label="Interpretation" color="border-blue-500" content={msg.interpretation} />}
          {msg.hypothesis && <Section label="Hypothesis" color="border-purple-500" content={msg.hypothesis} />}
          {msg.recommendations && <Section label="Suggested Actions" color="border-amber-500" content={msg.recommendations} />}
        </div>
      )}
      <div className="border-b border-gray-100" />
    </div>
  );
}

function Section({ label, color, content }: { label: string; color: string; content: string }) {
  return (
    <div className={`border-l-2 ${color} pl-3`}>
      <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">{label}</div>
      <div className="text-[13px] text-gray-700 leading-relaxed">{parseMarkdown(content)}</div>
    </div>
  );
}

function ConfigProposalCard({ proposal, onApply, applied }: { proposal: ConfigProposal; onApply: () => void; applied: boolean }) {
  const LEVEL_LABELS: Record<string, string> = { ta: "TA", brand: "Brand", market: "Market", region: "Region", unit: "Unit", sub_unit: "Sub-unit", category: "Category" };
  const PRESET_LABELS: Record<string, string> = { all: "All Scenarios", bud: "ACT vs Budget", mtp: "ACT vs MTP", rbu2: "ACT vs RBU2", py: "ACT vs PY", bud_mtp: "ACT vs BUD & MTP", bud_py: "ACT vs BUD & PY" };
  const changes: string[] = [];
  if (proposal.comparator) changes.push(`Comparator: ${COMPARATOR_LABELS[proposal.comparator] || proposal.comparator}`);
  if (proposal.page) changes.push(`Page: ${PAGE_LABELS[proposal.page] || proposal.page}`);
  if (proposal.levels?.length) changes.push(`Levels: ${proposal.levels.map((l) => LEVEL_LABELS[l] || l).join(" → ")}`);
  else if (proposal.dimension) changes.push(`Dimension: ${DIM_LABELS[proposal.dimension] || proposal.dimension}`);
  if (proposal.market_id?.length) changes.push(`Market: ${proposal.market_id.join(", ")}`);
  if (proposal.ta?.length) changes.push(`TA: ${proposal.ta.join(", ")}`);
  if (proposal.year) changes.push(`Year: ${proposal.year}`);
  if (proposal.quarter) changes.push(`Quarter: ${proposal.quarter}`);
  if (proposal.scale) changes.push(`Scale: $${proposal.scale}`);
  if (proposal.scenario_preset) changes.push(`Scenario: ${PRESET_LABELS[proposal.scenario_preset] || proposal.scenario_preset}`);

  return (
    <div className="rounded-lg border border-az-navy/20 bg-az-navy/5 p-3 space-y-2">
      <div className="text-[13px] text-gray-700 font-medium">{proposal.summary}</div>
      {changes.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {changes.map((c) => (
            <span key={c} className="inline-flex px-2 py-0.5 rounded-full bg-white text-[11px] text-gray-600 border border-gray-200">
              {c}
            </span>
          ))}
        </div>
      )}
      <button
        onClick={onApply}
        disabled={applied}
        className={`w-full py-2 rounded-lg text-[13px] font-semibold transition-all ${
          applied
            ? "bg-green-100 text-green-700 cursor-default"
            : "bg-az-navy text-white hover:bg-az-navy/90 active:scale-[0.98]"
        }`}
      >
        {applied ? "Applied" : "Apply to Dashboard"}
      </button>
    </div>
  );
}

function ClarificationCard({ clarification, onSelect, disabled }: { clarification: Clarification; onSelect: (opt: string) => void; disabled: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [freeText, setFreeText] = useState("");

  const handleClick = (opt: string) => {
    if (disabled || selected) return;
    setSelected(opt);
    onSelect(opt);
  };

  const handleFreeSubmit = () => {
    if (disabled || selected || !freeText.trim()) return;
    setSelected(freeText.trim());
    onSelect(freeText.trim());
  };

  return (
    <div className="space-y-2">
      <div className="text-[13px] font-medium text-gray-700">{clarification.question}</div>
      <div className="flex flex-col gap-1.5">
        {clarification.options.map((opt) => (
          <button
            key={opt}
            onClick={() => handleClick(opt)}
            disabled={disabled || !!selected}
            className={`text-left px-3 py-2 rounded-lg text-[13px] border transition-all ${
              selected === opt
                ? "border-az-navy bg-az-navy/10 text-az-navy font-medium"
                : selected
                  ? "border-gray-100 text-gray-300 cursor-default"
                  : "border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50 active:bg-gray-100"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
      {!disabled && !selected && (
        <div className="flex gap-1.5 mt-1">
          <input
            type="text"
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleFreeSubmit(); }}
            placeholder="Or type your own answer..."
            className="flex-1 px-3 py-1.5 text-[12px] border border-gray-200 rounded-lg focus:border-az-navy focus:outline-none"
          />
          <button
            onClick={handleFreeSubmit}
            disabled={!freeText.trim()}
            className="px-3 py-1.5 text-[12px] font-medium text-white bg-az-navy rounded-lg disabled:opacity-30 hover:bg-az-navy/90 transition-colors"
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
}

function VisualIcon({ visual, onClick }: { visual: Visual; onClick: () => void }) {
  const icon = visual.tool === "render_table" ? "\ud83d\udcca" : visual.tool === "decompose_variance" ? "\ud83d\udd0d" : "\ud83d\udcc8";
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-gray-100 hover:bg-gray-200 text-[11px] text-gray-600 transition-colors"
      title={visual.title}
    >
      <span>{icon}</span>
      <span>{visual.title}</span>
    </button>
  );
}

function VisualOverlay({ visual, onClose }: { visual: Visual; onClose: () => void }) {
  let content: React.ReactNode = null;
  try {
    if (visual.tool === "render_table" && visual.headers && visual.rows) {
      content = (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-gray-200">
                {visual.headers.map((h, i) => (
                  <th key={i} className="text-left py-2 px-2 font-semibold text-gray-600">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visual.rows.map((row, ri) => (
                <tr key={ri} className="border-b border-gray-50">
                  {(Array.isArray(row) ? row : []).map((cell, ci) => (
                    <td key={ci} className="py-1.5 px-2 text-gray-700">{String(cell ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    } else if (visual.tool === "render_chart" && visual.datasets) {
      const labels = visual.labels || [];
      content = (
        <div className="space-y-4">
          {visual.datasets.map((ds, di) => {
            const vals = Array.isArray(ds.values) ? ds.values.map(Number) : [];
            const max = vals.length > 0 ? vals.reduce((a, b) => Math.max(a, b), 0) : 0;
            const barH = 96;
            return (
              <div key={di}>
                <div className="text-[11px] text-gray-500 mb-1">{ds.name}</div>
                <div className="flex items-end gap-1" style={{ height: barH + 20 }}>
                  {vals.map((v, vi) => {
                    const h = max > 0 ? (v / max) * barH : 0;
                    return (
                      <div key={vi} className="flex-1 flex flex-col items-center justify-end">
                        <div className="text-[9px] text-gray-500 mb-0.5">
                          {typeof v === "number" ? (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v % 1 === 0 ? v : v.toFixed(1)) : v}
                        </div>
                        <div
                          className="w-full rounded-t"
                          style={{
                            height: Math.max(h, v > 0 ? 2 : 0),
                            backgroundColor: ds.color || "#003366",
                          }}
                        />
                        <span className="text-[8px] text-gray-400 truncate w-full text-center mt-0.5">
                          {labels[vi] ?? ""}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      );
    } else if (visual.tool === "decompose_variance" && visual.factors) {
      const factors = visual.factors;
      const totalVal = visual.total_value || 0;
      const maxAbs = factors.reduce((m, f) => Math.max(m, Math.abs(f.value)), Math.abs(totalVal));
      const vUnit = visual.unit || "$M";
      const maxBarW = 180; // max bar width in px

      const fmtVal = (v: number) => `${v >= 0 ? "+" : ""}${Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1)}${vUnit}`;

      content = (
        <div className="space-y-1">
          {factors.map((f, i) => {
            const w = maxAbs > 0 ? (Math.abs(f.value) / maxAbs) * maxBarW : 0;
            const isPositive = f.value >= 0;
            return (
              <div key={i} className="flex items-center gap-2">
                <div className="w-[90px] shrink-0 text-right text-[11px] text-gray-600 truncate">{f.label}</div>
                <div className="flex-1 flex items-center" style={{ minHeight: 24 }}>
                  <div
                    className="rounded-sm h-[18px]"
                    style={{
                      width: Math.max(w, 3),
                      backgroundColor: isPositive ? "#22c55e" : "#ef4444",
                    }}
                  />
                  <span className={`ml-1.5 text-[10px] font-medium whitespace-nowrap ${isPositive ? "text-green-700" : "text-red-700"}`}>
                    {fmtVal(f.value)}
                  </span>
                </div>
              </div>
            );
          })}
          {/* Total row */}
          <div className="flex items-center gap-2 border-t border-gray-200 pt-1.5 mt-1.5">
            <div className="w-[90px] shrink-0 text-right text-[11px] font-semibold text-gray-800">{visual.total_label}</div>
            <div className="flex-1 flex items-center" style={{ minHeight: 24 }}>
              <div
                className="rounded-sm h-[18px]"
                style={{
                  width: Math.max(maxAbs > 0 ? (Math.abs(totalVal) / maxAbs) * maxBarW : 0, 3),
                  backgroundColor: totalVal >= 0 ? "#003366" : "#991b1b",
                }}
              />
              <span className={`ml-1.5 text-[10px] font-bold whitespace-nowrap ${totalVal >= 0 ? "text-gray-800" : "text-red-800"}`}>
                {fmtVal(totalVal)}
              </span>
            </div>
          </div>
          {/* Detail annotations */}
          {factors.some((f) => f.detail) && (
            <div className="space-y-0.5 pt-2 border-t border-gray-100 mt-2">
              {factors.filter((f) => f.detail).map((f, i) => (
                <div key={i} className="text-[10px] text-gray-500">
                  <span className="font-medium text-gray-600">{f.label}:</span> {f.detail}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }
  } catch {
    content = <div className="text-[12px] text-red-500">Unable to render this visual.</div>;
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[70vh] overflow-auto p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-800">{visual.title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        {content || <div className="text-[12px] text-gray-400">No data to display.</div>}
      </div>
    </div>
  );
}

export function AssistantDrawer({
  open,
  onClose,
  activeChatId,
  messages,
  activeContext,
  loading,
  liveTools,
  liveVisuals,
  liveResponse,
  liveConfigProposal,
  liveClarification,
  liveThinking,
  liveTimeline,
  sendQuestion,
  setActiveContext,
  onApplyConfig,
  chatList,
  switchChat,
  newChat,
  deleteChat,
}: Props) {
  const [question, setQuestion] = useState("");
  const [appliedProposals, setAppliedProposals] = useState<Set<number>>(new Set());
  const [expandedVisual, setExpandedVisual] = useState<Visual | null>(null);
  const [showChatList, setShowChatList] = useState(false);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);
  const voiceTranscriptRef = useRef("");
  const voiceTimeoutRef = useRef<number | null>(null);
  const voiceStoppingRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Cleanup voice recognition on unmount
  useEffect(() => {
    return () => {
      if (voiceTimeoutRef.current) clearTimeout(voiceTimeoutRef.current);
      recognitionRef.current?.stop();
    };
  }, []);

  // Auto-scroll when new content arrives
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, liveTimeline.length, liveResponse.facts, liveResponse.interpretation, liveResponse.hypothesis, liveResponse.recommendations, liveConfigProposal, liveClarification]);

  const hasSpeech = typeof window !== "undefined" && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

  const VOICE_TIMEOUT_MS = 30_000;

  const stopVoiceAndSend = useCallback(() => {
    voiceStoppingRef.current = true;
    recognitionRef.current?.stop();
    if (voiceTimeoutRef.current) { clearTimeout(voiceTimeoutRef.current); voiceTimeoutRef.current = null; }
    const transcript = voiceTranscriptRef.current.trim();
    voiceTranscriptRef.current = "";
    setListening(false);
    setQuestion("");
    if (transcript) sendQuestion(transcript);
  }, [sendQuestion]);

  const toggleVoice = useCallback(() => {
    if (!hasSpeech) {
      alert("Voice input requires Chrome, Edge, or Safari. Please switch browsers to use this feature.");
      return;
    }

    if (listening) {
      stopVoiceAndSend();
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognitionRef.current = recognition;
    voiceTranscriptRef.current = "";
    voiceStoppingRef.current = false;

    recognition.onresult = (event: any) => {
      let finalText = "";
      let interimText = "";
      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interimText += result[0].transcript;
        }
      }
      voiceTranscriptRef.current = finalText;
      setQuestion(finalText + (interimText ? interimText : ""));
    };
    recognition.onerror = () => { if (!voiceStoppingRef.current) { setListening(false); setQuestion(""); } };
    recognition.onend = () => {
      // Browser may auto-stop continuous recognition — restart unless user clicked stop
      if (!voiceStoppingRef.current) {
        try { recognition.start(); } catch { setListening(false); }
      }
    };

    recognition.start();
    setListening(true);
    // Safety timeout
    voiceTimeoutRef.current = window.setTimeout(stopVoiceAndSend, VOICE_TIMEOUT_MS);
  }, [listening, hasSpeech, stopVoiceAndSend]);

  const questionRef = useRef(question);
  questionRef.current = question;

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (questionRef.current.trim()) {
        sendQuestion(questionRef.current);
        setQuestion("");
      }
    },
    [sendQuestion],
  );

  const handleClarificationSelect = useCallback(
    (option: string) => {
      sendQuestion(option);
    },
    [sendQuestion],
  );

  const handleApplyProposal = useCallback(
    (proposal: ConfigProposal, msgIndex: number) => {
      onApplyConfig?.(proposal);
      setAppliedProposals((prev) => new Set(prev).add(msgIndex));
      onClose();
    },
    [onApplyConfig, onClose],
  );

  const handleNewChat = useCallback(() => {
    newChat();
    setShowChatList(false);
    setAppliedProposals(new Set());
  }, [newChat]);

  const handleSwitchChat = useCallback(
    (id: string) => {
      switchChat(id);
      setShowChatList(false);
      setAppliedProposals(new Set());
    },
    [switchChat],
  );

  const hasAnyContent = messages.length > 0 || liveResponse.facts || liveResponse.interpretation || liveResponse.hypothesis || liveTools.length > 0 || liveConfigProposal || liveClarification;

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-50 bg-black/30"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-2xl shadow-2xl flex flex-col"
            style={{ maxHeight: "80vh" }}
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
          >
            {/* Handle bar + chat list toggle — drag only from here */}
            <motion.div
              className="flex items-center justify-between px-4 py-2 cursor-grab active:cursor-grabbing touch-none"
              drag="y"
              dragConstraints={{ top: 0, bottom: 0 }}
              dragElastic={0.2}
              onDragEnd={(_, info) => {
                if (info.offset.y > 100) onClose();
              }}
            >
              <button
                onClick={() => setShowChatList((v) => !v)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                title="Chat history"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
                </svg>
              </button>
              <div className="w-10 h-1 rounded-full bg-gray-300" />
              <div className="w-4" />
            </motion.div>

            {/* Chat list panel */}
            <AnimatePresence>
              {showChatList && (
                <ChatListPanel
                  chatList={chatList}
                  activeChatId={activeChatId}
                  onSwitch={handleSwitchChat}
                  onNew={handleNewChat}
                  onDelete={deleteChat}
                />
              )}
            </AnimatePresence>

            {/* Context chip */}
            {activeContext && activeContext.source !== "header" && (
              <div className="px-4 pb-2">
                <ContextChip
                  context={activeContext}
                  onClear={() => setActiveContext(activeContext ? { ...activeContext, source: "header", dataPoint: undefined } : null)}
                />
              </div>
            )}

            {/* Scrollable response area */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
              {/* Past messages */}
              {messages.map((msg, i) => {
                const isOld = i < messages.length - 2; // older than the current exchange
                return msg.role === "user" ? (
                  <div key={i} className="text-[12px] text-gray-500 italic">{msg.question}</div>
                ) : isOld ? (
                  <CollapsedMessage key={i} msg={msg} index={i} onApply={handleApplyProposal} applied={appliedProposals.has(i)} />
                ) : (
                  <div key={i} className="space-y-2">
                    {msg.timeline && msg.timeline.length > 0 ? (
                      <InvestigationTimeline timeline={msg.timeline} />
                    ) : (
                      /* Fallback for old messages without timeline */
                      (msg.tools?.length || msg.thinking?.length) ? (
                        <InvestigationTimeline
                          timeline={[
                            ...(msg.tools || []).map((t): TimelineEvent => ({ kind: "tool", tool: t })),
                            ...(msg.thinking || []).map((s): TimelineEvent => ({ kind: "thinking", step: s })),
                          ]}
                        />
                      ) : null
                    )}
                    {msg.configProposal && (
                      <ConfigProposalCard
                        proposal={msg.configProposal}
                        onApply={() => handleApplyProposal(msg.configProposal!, i)}
                        applied={appliedProposals.has(i)}
                      />
                    )}
                    {msg.clarification && (
                      <ClarificationCard
                        clarification={msg.clarification}
                        onSelect={handleClarificationSelect}
                        disabled={loading || i < messages.length - 1}
                      />
                    )}
                    {msg.facts && <Section label="Facts" color="border-green-500" content={msg.facts} />}
                    {msg.visuals && msg.visuals.length > 0 && (
                      <div className="flex flex-wrap gap-2 pl-3">
                        {msg.visuals.map((v, vi) => (
                          <VisualIcon key={vi} visual={v} onClick={() => setExpandedVisual(v)} />
                        ))}
                      </div>
                    )}
                    {msg.interpretation && <Section label="Interpretation" color="border-blue-500" content={msg.interpretation} />}
                    {msg.hypothesis && <Section label="Hypothesis" color="border-purple-500" content={msg.hypothesis} />}
                    {msg.recommendations && <Section label="Suggested Actions" color="border-amber-500" content={msg.recommendations} />}
                    {i < messages.length - 1 && <div className="border-b border-gray-100" />}
                  </div>
                );
              })}

              {/* Live streaming state */}
              {liveTimeline.length > 0 && (
                <InvestigationTimeline timeline={liveTimeline} defaultExpanded />
              )}
              {liveConfigProposal && (
                <ConfigProposalCard proposal={liveConfigProposal} onApply={() => { onApplyConfig?.(liveConfigProposal); onClose(); }} applied={false} />
              )}
              {liveClarification && (
                <ClarificationCard clarification={liveClarification} onSelect={() => {}} disabled />
              )}
              {liveResponse.facts && <Section label="Facts" color="border-green-500" content={liveResponse.facts} />}
              {liveVisuals.length > 0 && (
                <div className="flex flex-wrap gap-2 pl-3">
                  {liveVisuals.map((v, i) => (
                    <VisualIcon key={i} visual={v} onClick={() => setExpandedVisual(v)} />
                  ))}
                </div>
              )}
              {liveResponse.interpretation && <Section label="Interpretation" color="border-blue-500" content={liveResponse.interpretation} />}
              {liveResponse.hypothesis && <Section label="Hypothesis" color="border-purple-500" content={liveResponse.hypothesis} />}
              {liveResponse.recommendations && <Section label="Suggested Actions" color="border-amber-500" content={liveResponse.recommendations} />}

              {/* Empty state */}
              {!hasAnyContent && !loading && (
                <div className="text-center text-gray-400 text-sm py-8">
                  Ask anything about your dashboard data...
                </div>
              )}

              {/* Loading indicator when no tools yet */}
              {loading && liveTools.length === 0 && (
                <div className="flex items-center gap-2 text-[12px] text-gray-500">
                  <span className="w-2 h-2 bg-az-navy rounded-full animate-pulse" />
                  Thinking...
                </div>
              )}
            </div>

            {/* Input */}
            <div className="px-4 py-3 border-t border-gray-100">
              <form onSubmit={handleSubmit} className="flex gap-2">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask a follow-up..."
                  className="flex-1 px-3 py-2 text-[13px] bg-gray-50 rounded-lg border border-gray-200 focus:outline-none focus:border-az-navy/30 focus:ring-1 focus:ring-az-navy/20"
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={toggleVoice}
                  disabled={loading}
                  className={`px-2 py-2 rounded-lg text-[13px] transition-all ${
                    listening
                      ? "bg-red-500 text-white animate-pulse"
                      : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                  }`}
                  title={listening ? "Send voice message" : "Voice input"}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-14 0m7 7v4m-4 0h8M12 1a3 3 0 00-3 3v7a3 3 0 006 0V4a3 3 0 00-3-3z" />
                  </svg>
                </button>
                <button
                  type="submit"
                  disabled={loading || !question.trim()}
                  className="px-3 py-2 bg-az-navy text-white rounded-lg text-[13px] font-medium disabled:opacity-40 transition-opacity"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </button>
              </form>
            </div>
          </motion.div>

          {/* Visual overlay */}
          <AnimatePresence>
            {expandedVisual && (
              <VisualOverlay visual={expandedVisual} onClose={() => setExpandedVisual(null)} />
            )}
          </AnimatePresence>
        </>
      )}
    </AnimatePresence>
  );
}

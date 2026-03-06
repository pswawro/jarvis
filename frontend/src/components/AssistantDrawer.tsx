import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { AssistantContext } from "../types";

interface ToolStatus {
  label: string;
  done: boolean;
}

interface Visual {
  tool: "render_table" | "render_chart";
  title: string;
  headers?: string[];
  rows?: string[][];
  type?: "bar" | "line";
  labels?: string[];
  datasets?: { name: string; values: number[]; color?: string }[];
}

interface Message {
  role: "user" | "assistant";
  question?: string;
  facts?: string;
  interpretation?: string;
  hypothesis?: string;
  tools?: ToolStatus[];
  visuals?: Visual[];
}

interface Props {
  open: boolean;
  onClose: () => void;
  context: AssistantContext | null;
}

function ContextChip({ context, onClear }: { context: AssistantContext; onClear: () => void }) {
  if (context.source === "header") return null;
  const dp = context.dataPoint;
  const parts = [dp?.node_name || dp?.series_name || "", context.view, `${context.period.year}${context.period.quarter ? " " + context.period.quarter : ""}`].filter(Boolean);
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

function ToolIndicators({ tools }: { tools: ToolStatus[] }) {
  if (tools.length === 0) return null;
  return (
    <div className="space-y-1">
      {tools.map((t, i) => (
        <div key={i} className={`flex items-center gap-2 text-[11px] ${t.done ? "text-gray-400" : "text-gray-600"}`}>
          {t.done ? (
            <svg className="w-3 h-3 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <span className="w-3 h-3 flex items-center justify-center">
              <span className="w-1.5 h-1.5 bg-az-navy rounded-full animate-pulse" />
            </span>
          )}
          <span>{t.label}</span>
        </div>
      ))}
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

  for (const line of lines) {
    const bullet = line.match(/^[-•]\s+(.*)/);
    if (bullet) {
      bullets.push(bullet[1]);
    } else {
      flushBullets();
      result.push(<span key={key++}>{parseBold(line, key * 100)}{"\n"}</span>);
    }
  }
  flushBullets();
  return result;
}

function Section({ label, color, content }: { label: string; color: string; content: string }) {
  return (
    <div className={`border-l-2 ${color} pl-3`}>
      <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">{label}</div>
      <div className="text-[13px] text-gray-700 leading-relaxed">{parseMarkdown(content)}</div>
    </div>
  );
}

function VisualIcon({ visual, onClick }: { visual: Visual; onClick: () => void }) {
  const icon = visual.tool === "render_table" ? "\ud83d\udcca" : "\ud83d\udcc8";
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
        {visual.tool === "render_table" && visual.headers && visual.rows && (
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
                    {row.map((cell, ci) => (
                      <td key={ci} className="py-1.5 px-2 text-gray-700">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {visual.tool === "render_chart" && visual.labels && visual.datasets && (
          <div className="space-y-4">
            {visual.datasets.map((ds, di) => {
              const max = Math.max(...ds.values, 0);
              const barH = 96; // px
              return (
                <div key={di}>
                  <div className="text-[11px] text-gray-500 mb-1">{ds.name}</div>
                  <div className="flex items-end gap-1" style={{ height: barH + 20 }}>
                    {ds.values.map((v, vi) => {
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
                            {visual.labels![vi]}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export function AssistantDrawer({ open, onClose, context }: Props) {
  const [activeContext, setActiveContext] = useState<AssistantContext | null>(null);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [liveTools, setLiveTools] = useState<ToolStatus[]>([]);
  const [liveVisuals, setLiveVisuals] = useState<Visual[]>([]);
  const [liveResponse, setLiveResponse] = useState({ facts: "", interpretation: "", hypothesis: "" });
  const [expandedVisual, setExpandedVisual] = useState<Visual | null>(null);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevContextRef = useRef<AssistantContext | null>(null);

  // When opened with a NEW context, reset conversation; otherwise keep history
  useEffect(() => {
    if (open && context) {
      const isNewContext = context !== prevContextRef.current;
      prevContextRef.current = context;
      if (isNewContext) {
        setActiveContext(context);
        setMessages([]);
        setLiveTools([]);
        setLiveVisuals([]);
        setLiveResponse({ facts: "", interpretation: "", hypothesis: "" });
        setQuestion("");
      }
    }
  }, [open, context]);

  // Auto-scroll when new content arrives
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [liveTools, liveResponse, messages]);

  const sendQuestion = useCallback(
    async (q: string) => {
      if (!q.trim() || loading) return;
      setLoading(true);
      setLiveResponse({ facts: "", interpretation: "", hypothesis: "" });
      setLiveTools([]);
      setLiveVisuals([]);

      // Add user message to history
      setMessages((prev) => [...prev, { role: "user", question: q }]);

      try {
        const res = await fetch("/api/assistant", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ context: activeContext, question: q }),
        });

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        const accumulated = { facts: "", interpretation: "", hypothesis: "" };
        const accVisuals: Visual[] = [];
        const accTools: ToolStatus[] = [];

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n\n");
          buffer = lines.pop()!;

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6));
              switch (data.type) {
                case "tool_use":
                  accTools.push({ label: data.content, done: false });
                  setLiveTools([...accTools]);
                  break;
                case "tool_done":
                  for (let i = accTools.length - 1; i >= 0; i--) {
                    if (!accTools[i].done) { accTools[i] = { ...accTools[i], done: true }; break; }
                  }
                  setLiveTools([...accTools]);
                  break;
                case "facts":
                  accumulated.facts = data.content;
                  setLiveResponse({ ...accumulated });
                  break;
                case "interpretation":
                  accumulated.interpretation = data.content;
                  setLiveResponse({ ...accumulated });
                  break;
                case "hypothesis":
                  accumulated.hypothesis = data.content;
                  setLiveResponse({ ...accumulated });
                  break;
                case "visual":
                  accVisuals.push(JSON.parse(data.content));
                  setLiveVisuals([...accVisuals]);
                  break;
                case "done":
                  // Finalize: move live state into message history
                  setMessages((prev) => [
                    ...prev,
                    {
                      role: "assistant",
                      facts: accumulated.facts,
                      interpretation: accumulated.interpretation,
                      hypothesis: accumulated.hypothesis,
                      tools: [...accTools],
                      visuals: [...accVisuals],
                    },
                  ]);
                  setLiveTools([]);
                  setLiveVisuals([]);
                  setLiveResponse({ facts: "", interpretation: "", hypothesis: "" });
                  break;
                case "error":
                  accumulated.facts = accumulated.facts || `Error: ${data.content}`;
                  setLiveResponse({ ...accumulated });
                  break;
              }
            } catch {
              // skip malformed SSE lines
            }
          }
        }
      } catch (e: any) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", facts: `Connection error: ${e.message}` },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [activeContext, loading],
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (question.trim()) {
        sendQuestion(question);
        setQuestion("");
      }
    },
    [question, sendQuestion],
  );

  const hasAnyContent = messages.length > 0 || liveResponse.facts || liveResponse.interpretation || liveResponse.hypothesis || liveTools.length > 0;

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
            drag="y"
            dragConstraints={{ top: 0 }}
            dragElastic={0.2}
            onDragEnd={(_, info) => {
              if (info.offset.y > 100) onClose();
            }}
          >
            {/* Handle bar */}
            <div className="flex justify-center py-2 cursor-grab">
              <div className="w-10 h-1 rounded-full bg-gray-300" />
            </div>

            {/* Context chip */}
            {activeContext && activeContext.source !== "header" && (
              <div className="px-4 pb-2">
                <ContextChip
                  context={activeContext}
                  onClear={() => setActiveContext((c) => c ? { ...c, source: "header", dataPoint: undefined } : null)}
                />
              </div>
            )}

            {/* Scrollable response area */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
              {/* Past messages */}
              {messages.map((msg, i) =>
                msg.role === "user" ? (
                  <div key={i} className="text-[12px] text-gray-500 italic">{msg.question}</div>
                ) : (
                  <div key={i} className="space-y-2">
                    {msg.tools && msg.tools.length > 0 && (
                      <ToolIndicators tools={msg.tools} />
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
                    {i < messages.length - 1 && <div className="border-b border-gray-100" />}
                  </div>
                ),
              )}

              {/* Live streaming state */}
              <ToolIndicators tools={liveTools} />
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

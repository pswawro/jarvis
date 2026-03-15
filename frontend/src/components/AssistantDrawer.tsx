import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type {
  AssistantContext,
  Message,
  ToolStatus,
  Visual,
  ConfigProposal,
  Clarification,
  TimelineEvent,
  ChatSummary,
} from "../types";
import { ChatListPanel } from "./ChatListPanel";
import {
  parseMarkdown,
  InvestigationTimeline,
  ConfigProposalCard,
  ClarificationCard,
  VisualOverlay,
  VisualIcon,
} from "./assistant";

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
  liveTimeline: TimelineEvent[];

  sendQuestion: (q: string) => void;
  setActiveContext: (ctx: AssistantContext | null) => void;
  onApplyConfig?: (cfg: ConfigProposal) => void;

  chatList: ChatSummary[];
  switchChat: (id: string) => void;
  newChat: (context?: AssistantContext) => void;
  deleteChat: (id: string) => void;
}

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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- SpeechRecognition types not in lib
  const recognitionRef = useRef<any>(null);
  const voiceTranscriptRef = useRef("");
  const voiceTimeoutRef = useRef<number | null>(null);
  const voiceStoppingRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- SpeechRecognition is a non-standard API
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

    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- SpeechRecognition is a non-standard API
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognitionRef.current = recognition;
    voiceTranscriptRef.current = "";
    voiceStoppingRef.current = false;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- SpeechRecognition event types
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

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const input = (e.target as HTMLFormElement).querySelector("input");
      const value = input?.value?.trim() ?? "";
      if (value) {
        sendQuestion(value);
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
            role="dialog"
            aria-modal="true"
            aria-label="AI Assistant"
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

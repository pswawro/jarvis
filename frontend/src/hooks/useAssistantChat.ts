import { useState, useRef, useCallback, useEffect } from "react";
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
  ChatState,
} from "../types";

const CHAT_LIST_KEY = "jarvis_chat_list";
const CHAT_PREFIX = "jarvis_chat_";
const MAX_CHATS = 20;

function genId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

function loadChatList(): ChatSummary[] {
  try {
    return JSON.parse(localStorage.getItem(CHAT_LIST_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveChatList(list: ChatSummary[]) {
  try {
    localStorage.setItem(CHAT_LIST_KEY, JSON.stringify(list));
  } catch {
    // QuotaExceeded — prune oldest chats but keep at least 1
    const toRemove = Math.min(5, Math.max(list.length - 1, 0));
    if (toRemove > 0) {
      for (const old of list.slice(0, toRemove)) {
        localStorage.removeItem(CHAT_PREFIX + old.id);
      }
      const pruned = list.slice(toRemove);
      try {
        localStorage.setItem(CHAT_LIST_KEY, JSON.stringify(pruned));
      } catch {
        // give up — memory-only
      }
    }
  }
}

function loadChat(id: string): ChatState | null {
  try {
    const raw = localStorage.getItem(CHAT_PREFIX + id);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveChat(state: ChatState) {
  try {
    localStorage.setItem(CHAT_PREFIX + state.id, JSON.stringify(state));
  } catch {
    // best effort
  }
}

function deleteChatStorage(id: string) {
  localStorage.removeItem(CHAT_PREFIX + id);
}

export interface UseAssistantChat {
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

  hasUnreadResponse: boolean;
  markRead: () => void;
  setDrawerOpen: (open: boolean) => void;

  sendQuestion: (q: string) => void;
  setActiveContext: (ctx: AssistantContext | null) => void;

  chatList: ChatSummary[];
  switchChat: (id: string) => void;
  newChat: (context?: AssistantContext) => void;
  deleteChat: (id: string) => void;

  onApplyConfig?: (cfg: ConfigProposal) => void;
}

export function useAssistantChat(onApplyConfig?: (cfg: ConfigProposal) => void): UseAssistantChat {
  const [chatList, setChatList] = useState<ChatSummary[]>(loadChatList);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeContext, setActiveContext] = useState<AssistantContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [liveTools, setLiveTools] = useState<ToolStatus[]>([]);
  const [liveVisuals, setLiveVisuals] = useState<Visual[]>([]);
  const [liveResponse, setLiveResponse] = useState({ facts: "", interpretation: "", hypothesis: "", recommendations: "" });
  const [liveConfigProposal, setLiveConfigProposal] = useState<ConfigProposal | null>(null);
  const [liveClarification, setLiveClarification] = useState<Clarification | null>(null);
  const [liveThinking, setLiveThinking] = useState<ThinkingStep[]>([]);
  const [liveTimeline, setLiveTimeline] = useState<TimelineEvent[]>([]);
  const [hasUnreadResponse, setHasUnreadResponse] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const drawerOpenRef = useRef(false);
  const activeChatIdRef = useRef<string | null>(null);
  const activeContextRef = useRef<AssistantContext | null>(null);
  const messagesRef = useRef<Message[]>([]);
  const chatListRef = useRef<ChatSummary[]>(chatList);
  const loadingRef = useRef(false);
  const requestIdRef = useRef(0); // Track current request to avoid stale finally blocks

  // Keep refs in sync
  useEffect(() => { activeChatIdRef.current = activeChatId; }, [activeChatId]);
  useEffect(() => { activeContextRef.current = activeContext; }, [activeContext]);
  useEffect(() => { messagesRef.current = messages; }, [messages]);
  useEffect(() => { chatListRef.current = chatList; }, [chatList]);

  // Abort in-flight request on unmount
  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  const setDrawerOpen = useCallback((open: boolean) => {
    drawerOpenRef.current = open;
  }, []);

  const markRead = useCallback(() => {
    setHasUnreadResponse(false);
  }, []);

  const persistChat = useCallback((msgs: Message[], ctx: AssistantContext | null, chatId: string, list: ChatSummary[]) => {
    const now = new Date().toISOString();
    const existing = list.find((c) => c.id === chatId);
    const title = existing?.title || msgs.find((m) => m.role === "user")?.question?.slice(0, 50) || "New Chat";

    const chatState: ChatState = {
      id: chatId,
      title,
      messages: msgs,
      context: ctx,
      createdAt: existing?.createdAt || now,
      updatedAt: now,
    };
    saveChat(chatState);

    let newList: ChatSummary[];
    if (existing) {
      newList = list.map((c) => (c.id === chatId ? { ...c, title, updatedAt: now } : c));
    } else {
      newList = [...list, { id: chatId, title, createdAt: now, updatedAt: now }];
    }
    // Enforce max chats
    while (newList.length > MAX_CHATS) {
      const oldest = newList.shift()!;
      deleteChatStorage(oldest.id);
    }
    saveChatList(newList);
    setChatList(newList);
  }, []);

  const resetLive = useCallback(() => {
    setLiveTools([]);
    setLiveVisuals([]);
    setLiveResponse({ facts: "", interpretation: "", hypothesis: "", recommendations: "" });
    setLiveConfigProposal(null);
    setLiveClarification(null);
    setLiveThinking([]);
    setLiveTimeline([]);
  }, []);

  const sendQuestion = useCallback(
    (q: string) => {
      if (!q.trim() || loadingRef.current) return;

      // Capture context at send time to avoid stale closure
      const ctx = activeContextRef.current;

      // Abort any in-flight request
      abortRef.current?.abort();

      // Ensure we have an active chat
      let chatId = activeChatIdRef.current;
      if (!chatId) {
        chatId = genId();
        setActiveChatId(chatId);
        activeChatIdRef.current = chatId;
      }

      const thisRequestId = ++requestIdRef.current;
      setLoading(true);
      loadingRef.current = true;
      resetLive();

      const userMsg: Message = { role: "user", question: q };
      const newMessages = [...messagesRef.current, userMsg];
      setMessages(newMessages);
      messagesRef.current = newMessages;

      // Persist on send
      persistChat(newMessages, ctx, chatId, chatListRef.current);

      const controller = new AbortController();
      abortRef.current = controller;

      (async () => {
        try {
          // Build conversation history from previous messages
          // Keep last 3 exchanges (6 msgs) in full; compress older ones into a summary
          const RECENT_EXCHANGE_COUNT = 3;
          const allPrev = messagesRef.current.slice(0, -1); // exclude the just-added user msg
          const recentCutoff = Math.max(0, allPrev.length - RECENT_EXCHANGE_COUNT * 2);
          const olderMsgs = allPrev.slice(0, recentCutoff);
          const recentMsgs = allPrev.slice(recentCutoff);

          const history: { role: string; content: string }[] = [];

          // Compress older messages into a single summary
          if (olderMsgs.length > 0) {
            const summaryLines: string[] = [];
            for (const msg of olderMsgs) {
              if (msg.role === "user" && msg.question) {
                summaryLines.push(`User: ${msg.question.slice(0, 80)}`);
              } else if (msg.role === "assistant") {
                if (msg.configProposal) summaryLines.push(`Assistant: [Config: ${msg.configProposal.summary}]`);
                else if (msg.clarification) summaryLines.push(`Assistant: [Asked: ${msg.clarification.question}]`);
                else if (msg.facts) summaryLines.push(`Assistant: ${msg.facts.slice(0, 100)}...`);
              }
            }
            if (summaryLines.length > 0) {
              history.push({ role: "user", content: `[Earlier in this conversation:\n${summaryLines.join("\n")}]` });
              history.push({ role: "assistant", content: "Understood, I have context from our earlier discussion." });
            }
          }

          // Recent messages in full
          for (const msg of recentMsgs) {
            if (msg.role === "user" && msg.question) {
              history.push({ role: "user", content: msg.question });
            } else if (msg.role === "assistant") {
              const parts: string[] = [];
              if (msg.configProposal) parts.push(`[Proposed config: ${msg.configProposal.summary}]`);
              if (msg.clarification) parts.push(`[Asked: ${msg.clarification.question}]`);
              if (msg.facts) parts.push(msg.facts.length > 500 ? msg.facts.slice(0, 500) + "..." : msg.facts);
              if (msg.interpretation) parts.push(msg.interpretation.length > 300 ? msg.interpretation.slice(0, 300) + "..." : msg.interpretation);
              if (msg.hypothesis) parts.push(msg.hypothesis.length > 300 ? msg.hypothesis.slice(0, 300) + "..." : msg.hypothesis);
              if (parts.length > 0) {
                history.push({ role: "assistant", content: parts.join("\n") });
              }
            }
          }

          const res = await fetch("/api/assistant", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ context: ctx || {}, question: q, history }),
            signal: controller.signal,
          });

          if (!res.ok || !res.body) {
            throw new Error(`Server error (${res.status})`);
          }

          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          const accumulated = { facts: "", interpretation: "", hypothesis: "", recommendations: "" };
          const accVisuals: Visual[] = [];
          const accTools: ToolStatus[] = [];
          let accConfigProposal: ConfigProposal | null = null;
          let accClarification: Clarification | null = null;
          const accThinking: ThinkingStep[] = [];
          const accTimeline: TimelineEvent[] = [];

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
                  case "tool_use": {
                    const toolEntry: ToolStatus = { label: data.content, done: false };
                    accTools.push(toolEntry);
                    setLiveTools([...accTools]);
                    accTimeline.push({ kind: "tool", tool: toolEntry });
                    setLiveTimeline([...accTimeline]);
                    break;
                  }
                  case "tool_done":
                    for (let i = accTools.length - 1; i >= 0; i--) {
                      if (!accTools[i].done) { accTools[i] = { ...accTools[i], done: true }; break; }
                    }
                    setLiveTools([...accTools]);
                    // Also update the timeline entry
                    for (let i = accTimeline.length - 1; i >= 0; i--) {
                      if (accTimeline[i].kind === "tool" && !accTimeline[i].tool.done) {
                        accTimeline[i] = { kind: "tool", tool: { ...accTimeline[i].tool, done: true } };
                        break;
                      }
                    }
                    setLiveTimeline([...accTimeline]);
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
                  case "recommendations":
                    accumulated.recommendations = data.content;
                    setLiveResponse({ ...accumulated });
                    break;
                  case "visual":
                    accVisuals.push(JSON.parse(data.content));
                    setLiveVisuals([...accVisuals]);
                    break;
                  case "config_proposal":
                    accConfigProposal = JSON.parse(data.content);
                    setLiveConfigProposal(accConfigProposal);
                    break;
                  case "thinking": {
                    const thinkStep: ThinkingStep = JSON.parse(data.content);
                    accThinking.push(thinkStep);
                    setLiveThinking([...accThinking]);
                    accTimeline.push({ kind: "thinking", step: thinkStep });
                    setLiveTimeline([...accTimeline]);
                    break;
                  }
                  case "clarification":
                    accClarification = JSON.parse(data.content);
                    setLiveClarification(accClarification);
                    break;
                  case "done": {
                    const assistantMsg: Message = {
                      role: "assistant",
                      facts: accumulated.facts,
                      interpretation: accumulated.interpretation,
                      hypothesis: accumulated.hypothesis,
                      recommendations: accumulated.recommendations || undefined,
                      tools: [...accTools],
                      visuals: [...accVisuals],
                      configProposal: accConfigProposal || undefined,
                      clarification: accClarification || undefined,
                      thinking: accThinking.length > 0 ? [...accThinking] : undefined,
                      timeline: accTimeline.length > 0 ? [...accTimeline] : undefined,
                    };
                    const finalMessages = [...messagesRef.current, assistantMsg];
                    setMessages(finalMessages);
                    messagesRef.current = finalMessages;
                    resetLive();

                    // Persist on done
                    const cid = activeChatIdRef.current!;
                    persistChat(finalMessages, ctx, cid, chatListRef.current);

                    // Notify if drawer is closed
                    if (!drawerOpenRef.current) {
                      setHasUnreadResponse(true);
                    }
                    break;
                  }
                  case "error":
                    accumulated.facts = accumulated.facts || `Error: ${data.content}`;
                    setLiveResponse({ ...accumulated });
                    break;
                }
              } catch {
                // skip malformed SSE
              }
            }
          }
        } catch (e: any) {
          if (e.name === "AbortError") return;
          const errMsg: Message = { role: "assistant", facts: `Connection error: ${e.message}` };
          const finalMessages = [...messagesRef.current, errMsg];
          setMessages(finalMessages);
          messagesRef.current = finalMessages;
        } finally {
          // Only clear loading if this is still the active request
          if (requestIdRef.current === thisRequestId) {
            setLoading(false);
            loadingRef.current = false;
          }
        }
      })();
    },
    [resetLive, persistChat],
  );

  const switchChat = useCallback(
    (id: string) => {
      if (id === activeChatIdRef.current) return;
      // Abort in-flight
      abortRef.current?.abort();
      setLoading(false);
      resetLive();

      const chatState = loadChat(id);
      if (chatState) {
        setActiveChatId(id);
        setMessages(chatState.messages);
        messagesRef.current = chatState.messages;
        setActiveContext(chatState.context);
      }
    },
    [resetLive],
  );

  const newChat = useCallback(
    (context?: AssistantContext) => {
      // Abort in-flight
      abortRef.current?.abort();
      setLoading(false);
      resetLive();

      const id = genId();
      setActiveChatId(id);
      activeChatIdRef.current = id;
      setMessages([]);
      messagesRef.current = [];
      setActiveContext(context || null);
    },
    [resetLive],
  );

  const deleteChat = useCallback(
    (id: string) => {
      deleteChatStorage(id);
      const newList = chatListRef.current.filter((c) => c.id !== id);
      saveChatList(newList);
      setChatList(newList);

      // If deleting the active chat, switch to latest or clear
      if (activeChatIdRef.current === id) {
        if (newList.length > 0) {
          const latest = newList[newList.length - 1];
          switchChat(latest.id);
        } else {
          setActiveChatId(null);
          setMessages([]);
          messagesRef.current = [];
          setActiveContext(null);
        }
      }
    },
    [switchChat],
  );

  return {
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
    hasUnreadResponse,
    markRead,
    setDrawerOpen,
    sendQuestion,
    setActiveContext,
    chatList,
    switchChat,
    newChat,
    deleteChat,
    onApplyConfig,
  };
}

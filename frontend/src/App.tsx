import { useState, useRef, useMemo, useCallback, useEffect } from "react";
import type { Period, Filters, PageType, DimensionConfig, LevelId, KpiStripSpec, ChartInteraction, AssistantContext, ConfigProposal } from "./types";
import { useApi } from "./hooks/useApi";
import { useAssistantChat } from "./hooks/useAssistantChat";
import { filtersToExtra } from "./utils";
import { TopBar } from "./components/TopBar";
import { KpiStrip } from "./components/KpiStrip";
import { FilterBar } from "./components/FilterBar";
import { ViewTabs } from "./components/ViewTabs";
import { SwipeContainer } from "./components/SwipeContainer";
import { OverviewPage } from "./components/OverviewPage";
import { LandingView } from "./components/LandingView";
import { ScenariosPage } from "./components/ScenariosPage";
import { AssistantDrawer } from "./components/AssistantDrawer";
import { useInsights } from "./hooks/useInsights";
import { InsightsPanel } from "./components/InsightsPanel";

const PAGES: PageType[] = ["overview", "landing", "phased"];

export default function App() {
  const [filters, setFilters] = useState<Filters>({
    market_id: [],
    ta: [],
    product: [],
    comparator: "BUD",
    scale: "B",
    year: new Date().getFullYear(),
    granularity: "quarter",
  });
  const [page, setPage] = useState<PageType>("overview");
  const [dimConfig, setDimConfig] = useState<DimensionConfig>({ levels: ["ta", "brand", "market"] });
  const [scenarioPreset, setScenarioPreset] = useState("all");
  const lastInteractionRef = useRef<ChartInteraction | null>(null);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [insightsOpen, setInsightsOpen] = useState(false);
  const insights = useInsights();

  // Derive Period from filters for API calls
  const period = useMemo<Period>(() => ({ year: filters.year, quarter: null }), [filters.year]);

  const pageIndex = PAGES.indexOf(page);

  const handlePageSwitch = useCallback((index: number) => {
    setPage(PAGES[index] ?? "overview");
  }, []);

  const handleApplyConfig = useCallback((cfg: ConfigProposal) => {
    // Apply all filter changes in a single update to avoid cascading renders/API calls
    setFilters((f) => {
      const next = { ...f };
      if (cfg.comparator !== undefined) next.comparator = cfg.comparator as Filters["comparator"];
      if (cfg.scale !== undefined) next.scale = cfg.scale as Filters["scale"];
      if (cfg.market_id !== undefined) next.market_id = cfg.market_id;
      if (cfg.ta !== undefined) next.ta = cfg.ta;
      if (cfg.year !== undefined) next.year = cfg.year;
      if (cfg.quarter !== undefined) {
        next.granularity = "quarter" as const;
      }
      return next;
    });
    if (cfg.page) setPage(cfg.page as PageType);
    if (cfg.scenario_preset) setScenarioPreset(cfg.scenario_preset);
    if (cfg.levels) setDimConfig({ levels: cfg.levels });
    else if (cfg.dimension) {
      const LEGACY_MAP: Record<string, LevelId[]> = {
        brand: ["ta", "brand", "market"],
        region: ["region", "market", "brand"],
        unit: ["unit", "sub_unit"],
        market: ["category", "brand"],
      };
      const levels = LEGACY_MAP[cfg.dimension];
      if (levels) setDimConfig({ levels });
    }
  }, []);

  const assistant = useAssistantChat(handleApplyConfig);

  useEffect(() => {
    assistant.setDrawerOpen(assistantOpen);
    if (assistantOpen) assistant.markRead();
  }, [assistantOpen, assistant.setDrawerOpen, assistant.markRead]);

  // Listen for service worker messages (push notification clicks)
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type === "open-insights") {
        setInsightsOpen(true);
      }
    };
    navigator.serviceWorker?.addEventListener("message", handler);
    return () => navigator.serviceWorker?.removeEventListener("message", handler);
  }, []);

  // Parse ?insights=open URL param (from push notification click)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("insights") === "open") {
      setInsightsOpen(true);
      // Clean up URL
      params.delete("insights");
      const newUrl = params.toString()
        ? `${window.location.pathname}?${params}`
        : window.location.pathname;
      window.history.replaceState({}, "", newUrl);
    }
  }, []);

  // Register for push notifications on mount
  useEffect(() => {
    insights.subscribeToPush();
  }, [insights.subscribeToPush]);

  const handleInteraction = useCallback((interaction: ChartInteraction) => {
    lastInteractionRef.current = interaction;
  }, []);

  const handleAssistantTrigger = useCallback((ctx: AssistantContext) => {
    assistant.newChat(ctx);
    setAssistantOpen(true);
  }, [assistant.newChat]);

  const handleAssistantOpen = useCallback(() => {
    if (!assistant.activeChatId) {
      assistant.setActiveContext({
        source: "header",
        page,
        levels: dimConfig.levels,
        period,
        filters,
      });
    }
    setAssistantOpen(true);
  }, [page, dimConfig.levels, period, filters, assistant.activeChatId, assistant.setActiveContext]);

  // Use ref to access latest filters without recreating callbacks
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const handleInsightToChat = useCallback(async (insightId: string) => {
    try {
      await insights.markRead(insightId);
      const raw = await insights.getInsightContext(insightId);
      const ctx: AssistantContext = {
        ...raw,
        filters: { ...filtersRef.current },
      };
      setInsightsOpen(false);
      const question = ctx.dataPoint?.explanation
        ? `Analyze this insight: ${ctx.dataPoint.explanation}`
        : "Analyze this data anomaly and provide recommendations.";
      assistant.newChat(ctx, question);
      setAssistantOpen(true);
    } catch (e) {
      console.error("Failed to open insight in chat:", e);
    }
  }, [insights.markRead, insights.getInsightContext, assistant.newChat]);

  const extra = useMemo(() => filtersToExtra(filters), [filters]);
  const { data: kpiData } = useApi<KpiStripSpec>("/kpi", period, extra);

  const handleExport = useCallback(() => {
    const params = new URLSearchParams({ year: String(filters.year) });
    if (filters.market_id.length) params.set("market_id", filters.market_id.join(","));
    if (filters.ta.length) params.set("ta", filters.ta.join(","));
    window.open(`/api/export/${dimConfig.levels.join(",")}?${params}`, "_blank");
  }, [dimConfig.levels, filters]);

  return (
    <div className="flex flex-col h-screen h-[100dvh] bg-[#f8f9fb]">
      <TopBar
        onAssistantOpen={handleAssistantOpen}
        onExport={handleExport}
        onInsightsOpen={() => setInsightsOpen(true)}
        hasNotification={assistant.hasUnreadResponse}
        unreadInsightCount={insights.unreadCount}
        hasUnreadCritical={insights.unreadCriticalCount > 0}
      />
      <FilterBar filters={filters} onChange={setFilters} dimConfig={dimConfig} onDimConfigChange={setDimConfig} page={page} />
      <KpiStrip spec={kpiData} scale={filters.scale} />
      <ViewTabs activeIndex={pageIndex} onSwitch={handlePageSwitch} />
      <SwipeContainer activeIndex={pageIndex} onSwitch={handlePageSwitch}>
        <OverviewPage period={period} filters={filters} dimConfig={dimConfig} onInteraction={handleInteraction} onAssistantTrigger={handleAssistantTrigger} />
        <LandingView period={period} filters={filters} dimConfig={dimConfig} />
        <ScenariosPage period={period} filters={filters} dimConfig={dimConfig} scenarioPreset={scenarioPreset} onScenarioPresetChange={setScenarioPreset} onInteraction={handleInteraction} onAssistantTrigger={handleAssistantTrigger} />
      </SwipeContainer>
      <AssistantDrawer
        open={assistantOpen}
        onClose={() => setAssistantOpen(false)}
        activeChatId={assistant.activeChatId}
        messages={assistant.messages}
        activeContext={assistant.activeContext}
        loading={assistant.loading}
        liveTools={assistant.liveTools}
        liveVisuals={assistant.liveVisuals}
        liveResponse={assistant.liveResponse}
        liveConfigProposal={assistant.liveConfigProposal}
        liveClarification={assistant.liveClarification}
        liveThinking={assistant.liveThinking}
        liveTimeline={assistant.liveTimeline}
        sendQuestion={assistant.sendQuestion}
        setActiveContext={assistant.setActiveContext}
        onApplyConfig={handleApplyConfig}
        chatList={assistant.chatList}
        switchChat={assistant.switchChat}
        newChat={assistant.newChat}
        deleteChat={assistant.deleteChat}
      />
      <InsightsPanel
        open={insightsOpen}
        onClose={() => setInsightsOpen(false)}
        insights={insights.insights}
        onAddToChat={handleInsightToChat}
        onToggleBookmark={insights.toggleBookmark}
      />
    </div>
  );
}

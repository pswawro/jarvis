import { useState, useMemo, useCallback, useEffect } from "react";
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

const PAGES: PageType[] = ["overview", "landing", "phased"];

export default function App() {
  const [filters, setFilters] = useState<Filters>({
    market_id: [],
    ta: [],
    product: [],
    comparator: "BUD",
    scale: "B",
    year: 2025,
    granularity: "quarter",
  });
  const [page, setPage] = useState<PageType>("overview");
  const [dimConfig, setDimConfig] = useState<DimensionConfig>({ levels: ["ta", "brand", "market"] });
  const [scenarioPreset, setScenarioPreset] = useState("all");
  const [lastInteraction, setLastInteraction] = useState<ChartInteraction | null>(null);
  const [assistantOpen, setAssistantOpen] = useState(false);

  // Derive Period from filters for API calls
  const period = useMemo<Period>(() => ({ year: filters.year, quarter: null }), [filters.year]);

  const pageIndex = PAGES.indexOf(page);

  const handlePageSwitch = useCallback((index: number) => {
    setPage(PAGES[index] ?? "overview");
  }, []);

  const handleApplyConfig = useCallback((cfg: ConfigProposal) => {
    if (cfg.comparator) setFilters((f) => ({ ...f, comparator: cfg.comparator as Filters["comparator"] }));
    if (cfg.scale) setFilters((f) => ({ ...f, scale: cfg.scale as Filters["scale"] }));
    if (cfg.market_id) setFilters((f) => ({ ...f, market_id: cfg.market_id! }));
    if (cfg.ta) setFilters((f) => ({ ...f, ta: cfg.ta! }));
    if (cfg.year) setFilters((f) => ({ ...f, year: cfg.year! }));
    if (cfg.quarter !== undefined) {
      // Legacy: map quarter to granularity
      if (cfg.quarter) {
        setFilters((f) => ({ ...f, granularity: "quarter" as const }));
      }
    }
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
  }, [assistantOpen]);

  const handleInteraction = useCallback((interaction: ChartInteraction) => {
    setLastInteraction(interaction);
    (window as any).__chartInteraction = interaction;
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
        hasNotification={assistant.hasUnreadResponse}
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
    </div>
  );
}

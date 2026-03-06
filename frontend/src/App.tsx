import { useState, useMemo, useCallback } from "react";
import type { Period, Filters, KpiStripSpec, ChartInteraction, AssistantContext } from "./types";
import type { ViewMode } from "./components/ViewToggle";
import { useApi } from "./hooks/useApi";
import { filtersToExtra } from "./utils";
import { TopBar } from "./components/TopBar";
import { KpiStrip } from "./components/KpiStrip";
import { FilterBar } from "./components/FilterBar";
import { ViewTabs } from "./components/ViewTabs";
import { SwipeContainer } from "./components/SwipeContainer";
import { BrandView } from "./components/BrandView";
import { RegionView } from "./components/RegionView";
import { UnitView } from "./components/UnitView";
import { MarketView } from "./components/MarketView";
import { AssistantDrawer } from "./components/AssistantDrawer";

export default function App() {
  const [period, setPeriod] = useState<Period>({ year: 2025, quarter: null });
  const [filters, setFilters] = useState<Filters>({ market_id: [], ta: [] });
  const [activeView, setActiveView] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [lastInteraction, setLastInteraction] = useState<ChartInteraction | null>(null);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantContext, setAssistantContext] = useState<AssistantContext | null>(null);

  // Expose interaction data on window for LLM consumption
  const handleInteraction = useCallback((interaction: ChartInteraction) => {
    setLastInteraction(interaction);
    (window as any).__chartInteraction = interaction;
  }, []);

  const VIEW_NAMES = ["Brand", "Region", "Unit", "Market"] as const;

  const handleAssistantTrigger = useCallback((ctx: AssistantContext) => {
    setAssistantContext(ctx);
    setAssistantOpen(true);
  }, []);

  const handleAssistantOpen = useCallback(() => {
    setAssistantContext({
      source: "header",
      view: VIEW_NAMES[activeView],
      period,
      filters,
    });
    setAssistantOpen(true);
  }, [activeView, period, filters]);

  const extra = useMemo(() => filtersToExtra(filters), [filters]);

  const { data: kpiData } = useApi<KpiStripSpec>("/kpi", period, extra);

  return (
    <div className="flex flex-col h-screen h-[100dvh] bg-[#f8f9fb]">
      <TopBar period={period} onPeriodChange={setPeriod} onAssistantOpen={handleAssistantOpen} />
      <FilterBar filters={filters} onChange={setFilters} />
      <KpiStrip spec={kpiData} />
      <ViewTabs activeIndex={activeView} onSwitch={setActiveView} />
      <SwipeContainer activeIndex={activeView} onSwitch={setActiveView}>
        <BrandView period={period} filters={filters} mode={viewMode} onModeChange={setViewMode} onInteraction={handleInteraction} onAssistantTrigger={handleAssistantTrigger} />
        <RegionView period={period} filters={filters} mode={viewMode} onModeChange={setViewMode} onInteraction={handleInteraction} onAssistantTrigger={handleAssistantTrigger} />
        <UnitView period={period} mode={viewMode} onModeChange={setViewMode} onInteraction={handleInteraction} onAssistantTrigger={handleAssistantTrigger} />
        <MarketView period={period} filters={filters} mode={viewMode} onModeChange={setViewMode} onInteraction={handleInteraction} onAssistantTrigger={handleAssistantTrigger} />
      </SwipeContainer>
      <AssistantDrawer open={assistantOpen} onClose={() => setAssistantOpen(false)} context={assistantContext} />
    </div>
  );
}

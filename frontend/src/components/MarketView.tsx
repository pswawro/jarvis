import { useState, useEffect, useMemo, useCallback } from "react";
import type { Period, Filters, TreeTableSpec, LineChartSpec, ChartInteraction, AssistantContext } from "../types";
import { useApi } from "../hooks/useApi";
import { TreeTable } from "./TreeTable";
import { TimeChart } from "./TimeChart";
import { TreeMapChart } from "./TreeMapChart";
import { ViewToggle, type ViewMode } from "./ViewToggle";
import { filtersToExtra } from "../utils";

interface Props {
  period: Period;
  filters: Filters;
  mode: ViewMode;
  onModeChange: (m: ViewMode) => void;
  onInteraction?: (i: ChartInteraction) => void;
  onAssistantTrigger?: (ctx: AssistantContext) => void;
}

export function MarketView({ period, filters, mode, onModeChange, onInteraction, onAssistantTrigger }: Props) {
  const [drill, setDrill] = useState<string | null>(null);
  const extra = useMemo(() => filtersToExtra(filters), [filters]);
  const chartExtra = useMemo(() => ({ ...extra, ...(drill ? { drill } : {}) }), [extra, drill]);
  useEffect(() => { setDrill(null); }, [filters, period]);
  const { data, loading } = useApi<TreeTableSpec>("/market", period, extra);
  const { data: chartData, loading: chartLoading } = useApi<LineChartSpec>("/market/chart", period, chartExtra);

  const wrapTrigger = useCallback(
    (ctx: AssistantContext) => {
      onAssistantTrigger?.({ ...ctx, view: "Market", period, filters });
    },
    [onAssistantTrigger, period, filters],
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 bg-white border-b border-gray-100">
        <h2 className="text-[13px] font-semibold text-gray-500 tracking-tight">Competitive Positioning</h2>
        <ViewToggle mode={mode} onToggle={onModeChange} />
      </div>

      {mode === "table" ? (
        !data ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <TreeTable
            tree={data.tree}
            columns={data.columns}
            headerLabels={{
              actual: "AZ Rev",
              variance: "Shr \u0394",
              pyVariance: "Mkt Grw",
              share: "Share",
              trend: "Shr Trend",
            }}
            varianceSuffix="pp"
            onAssistantTrigger={wrapTrigger}
          />
        )
      ) : mode === "trend" ? (
        chartLoading || !chartData ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <TimeChart spec={chartData} onDrill={setDrill} onDrillBack={() => setDrill(null)} onInteraction={onInteraction} onAssistantTrigger={wrapTrigger} />
        )
      ) : !data ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <TreeMapChart spec={data} onAssistantTrigger={wrapTrigger} />
      )}
    </div>
  );
}

import { useEffect, useMemo, useState, useCallback } from "react";
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

export function BrandView({ period, filters, mode, onModeChange, onInteraction, onAssistantTrigger }: Props) {
  const [drill, setDrill] = useState<string | null>(null);
  const extra = useMemo(() => filtersToExtra(filters), [filters]);
  const chartExtra = useMemo(() => ({ ...extra, ...(drill ? { drill } : {}) }), [extra, drill]);
  useEffect(() => { setDrill(null); }, [filters, period]);
  const { data } = useApi<TreeTableSpec>("/brand", period, extra);
  const { data: chartData, loading: chartLoading } = useApi<LineChartSpec>("/brand/chart", period, chartExtra);

  const wrapTrigger = useCallback(
    (ctx: AssistantContext) => {
      onAssistantTrigger?.({ ...ctx, view: "Brand", period, filters });
    },
    [onAssistantTrigger, period, filters],
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 bg-white border-b border-gray-100">
        <h2 className="text-[13px] font-semibold text-gray-500 tracking-tight">Revenue by Brand</h2>
        <ViewToggle mode={mode} onToggle={onModeChange} />
      </div>

      {mode === "table" ? (
        !data ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <TreeTable tree={data.tree} columns={data.columns} onAssistantTrigger={wrapTrigger} />
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

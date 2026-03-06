import { useState, useMemo, useEffect, useCallback } from "react";
import type { Period, TreeTableSpec, LineChartSpec, ChartInteraction, AssistantContext } from "../types";
import { useApi } from "../hooks/useApi";
import { TreeTable } from "./TreeTable";
import { TimeChart } from "./TimeChart";
import { TreeMapChart } from "./TreeMapChart";
import { ViewToggle, type ViewMode } from "./ViewToggle";

interface Props {
  period: Period;
  mode: ViewMode;
  onModeChange: (m: ViewMode) => void;
  onInteraction?: (i: ChartInteraction) => void;
  onAssistantTrigger?: (ctx: AssistantContext) => void;
}

export function UnitView({ period, mode, onModeChange, onInteraction, onAssistantTrigger }: Props) {
  const [drill, setDrill] = useState<string | null>(null);
  const drillExtra = useMemo(() => (drill ? { drill } : undefined), [drill]);
  useEffect(() => { setDrill(null); }, [period]);
  const { data, loading } = useApi<TreeTableSpec>("/unit", period);
  const { data: chartData, loading: chartLoading } = useApi<LineChartSpec>("/unit/chart", period, drillExtra);

  const wrapTrigger = useCallback(
    (ctx: AssistantContext) => {
      onAssistantTrigger?.({ ...ctx, view: "Unit", period, filters: { market_id: [], ta: [] } });
    },
    [onAssistantTrigger, period],
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 bg-white border-b border-gray-100">
        <h2 className="text-[13px] font-semibold text-gray-500 tracking-tight">Expenses by Unit</h2>
        <ViewToggle mode={mode} onToggle={onModeChange} />
      </div>

      {mode === "table" ? (
        !data ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <TreeTable tree={data.tree} columns={data.columns} invertColor onAssistantTrigger={wrapTrigger} />
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
        <TreeMapChart spec={data} invertColor onAssistantTrigger={wrapTrigger} />
      )}
    </div>
  );
}

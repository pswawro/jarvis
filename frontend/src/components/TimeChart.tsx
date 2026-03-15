import { useRef, useMemo, useCallback } from "react";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { LineChart as ELineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { LineChartSpec, ChartInteraction, AssistantContext } from "../types";
import { escapeHtml, sanitizeColor } from "../escapeHtml";
import { makeBaseContext } from "../utils";

echarts.use([
  ELineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

function fmtCurrency(v: number) {
  return v >= 1000 ? `$${(v / 1000).toFixed(1)}B` : `$${v.toFixed(0)}M`;
}

function fmtPercent(v: number) {
  return `${v.toFixed(1)}%`;
}

interface Props {
  spec: LineChartSpec;
  onDrill?: (seriesId: string) => void;
  onDrillBack?: () => void;
  onInteraction?: (interaction: ChartInteraction) => void;
  onAssistantTrigger?: (ctx: AssistantContext) => void;
}

/** Convert our semantic LineChartSpec → ECharts option JSON */
function specToOption(spec: LineChartSpec): echarts.EChartsCoreOption {
  const fmt = spec.y_format === "percent" ? fmtPercent : fmtCurrency;
  const drillableSet = new Set(spec.drillable_ids ?? []);

  return {
    animation: false,
    grid: {
      top: 12,
      right: 16,
      bottom: spec.x_labels.length > 6 ? 60 : 24,
      left: 4,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: spec.x_labels,
      axisLine: { lineStyle: { color: "#e5e7eb" } },
      axisTick: { show: false },
      axisLabel: { fontSize: 10, color: "#9ca3af" },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        fontSize: 10,
        color: "#9ca3af",
        formatter: (v: number) => fmt(v),
      },
      splitLine: { lineStyle: { color: "#e5e7eb", opacity: 0.5 } },
      min: "dataMin",
      max: "dataMax",
    },
    tooltip: {
      trigger: "item",
      backgroundColor: "#fff",
      borderColor: "#e5e7eb",
      borderWidth: 1,
      padding: [4, 8],
      textStyle: { fontSize: 12 },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params;
        const color = sanitizeColor(p.color);
        const val = fmt(p.value as number);
        return `<div style="font-size:10px;color:#9ca3af;margin-bottom:1px">${escapeHtml(p.name)}</div>
                <div style="color:${color};font-weight:600">${escapeHtml(p.seriesName)}: ${val}</div>`;
      },
      extraCssText: "border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,0.06);",
    },
    legend: {
      type: "scroll",
      bottom: spec.x_labels.length > 6 ? 24 : 0,
      itemWidth: 16,
      itemHeight: 2,
      textStyle: { fontSize: 11 },
      formatter: (name: string) => {
        const s = spec.series.find((s) => s.name === name);
        return s && drillableSet.has(s.id) ? `${name} \u25B8` : name;
      },
    },
    dataZoom: spec.x_labels.length > 6
      ? [
          {
            type: "slider",
            height: 18,
            bottom: 2,
            borderColor: "#d1d5db",
            backgroundColor: "#f9fafb",
            fillerColor: "rgba(37,99,235,0.08)",
            handleStyle: { color: "#9ca3af" },
            textStyle: { fontSize: 9, color: "#9ca3af" },
            dataBackground: {
              lineStyle: { color: "#d1d5db" },
              areaStyle: { color: "#f3f4f6" },
            },
          },
        ]
      : [],
    series: spec.series.map((s) => ({
      id: s.id,
      name: s.name,
      type: "line" as const,
      data: s.data,
      symbol: spec.x_labels.length <= 13 ? "circle" : "none",
      symbolSize: 5,
      lineStyle: { width: 2, color: s.color },
      itemStyle: { color: s.color },
      emphasis: {
        lineStyle: { width: 3 },
        focus: "series" as const,
      },
    })),
  };
}

export function TimeChart({ spec, onDrill, onDrillBack, onInteraction, onAssistantTrigger }: Props) {
  const chartRef = useRef<ReactEChartsCore>(null);
  const fmt = useMemo(() => spec.y_format === "percent" ? fmtPercent : fmtCurrency, [spec.y_format]);

  const drillableSet = useMemo(() => new Set(spec.drillable_ids ?? []), [spec.drillable_ids]);
  const isDrilled = spec.drill_path && spec.drill_path.length > 0;

  const option = useMemo(() => specToOption(spec), [spec]);

  const buildInteraction = useCallback(
    (type: "hover" | "click", params: any): ChartInteraction | null => {
      const seriesSpec = spec.series.find((s) => s.name === params.seriesName);
      if (!seriesSpec) return null;
      return {
        type,
        series_name: params.seriesName,
        series_id: seriesSpec.id,
        x_label: params.name,
        x_index: params.dataIndex,
        value: params.value as number,
        formatted_value: fmt(params.value as number),
      };
    },
    [spec.series, fmt]
  );

  const onEvents = useMemo(
    () => ({
      click: (params: any) => {
        if (params.componentType !== "series") return;
        // Surface interaction
        if (onInteraction) {
          const interaction = buildInteraction("click", params);
          if (interaction) onInteraction(interaction);
        }
      },
      mouseover: (params: any) => {
        if (params.componentType !== "series") return;
        if (onInteraction) {
          const interaction = buildInteraction("hover", params);
          if (interaction) onInteraction(interaction);
        }
      },
      contextmenu: (params: any) => {
        if (params.componentType !== "series" || !onAssistantTrigger) return;
        params.event?.event?.preventDefault?.();
        const seriesSpec = spec.series.find((s) => s.name === params.seriesName);
        if (!seriesSpec) return;
        onAssistantTrigger({
          ...makeBaseContext("time_chart_point"),
          dataPoint: {
            series_name: params.seriesName,
            series_id: seriesSpec.id,
            x_label: params.name,
            value: params.value as number,
            formatted_value: fmt(params.value as number),
          },
        });
      },
      legendselectchanged: (params: any) => {
        // Check if clicked legend is drillable
        const clickedName = params.name;
        const s = spec.series.find((s) => s.name === clickedName);
        if (s && drillableSet.has(s.id) && onDrill) {
          // Re-select the legend item (undo ECharts toggle) then drill
          const instance = chartRef.current?.getEchartsInstance();
          if (instance) {
            instance.dispatchAction({
              type: "legendSelect",
              name: clickedName,
            });
          }
          onDrill(s.id);
        }
      },
    }),
    [spec.series, drillableSet, onDrill, onInteraction, onAssistantTrigger, buildInteraction, fmt]
  );

  return (
    <div className="w-full px-3 pt-3 pb-1 flex flex-col">
      {isDrilled && onDrillBack && (
        <button
          onClick={onDrillBack}
          className="self-start flex items-center gap-1 text-[11px] font-medium text-gray-400 hover:text-az-navy px-2 py-0.5 rounded border border-gray-200 hover:border-gray-300 transition-colors mb-1"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
          {spec.drill_path[0]}
        </button>
      )}
      <div className="w-full h-64 sm:h-80">
        <ReactEChartsCore
          ref={chartRef}
          echarts={echarts}
          option={option}
          style={{ height: "100%", width: "100%" }}
          notMerge
          onEvents={onEvents}
        />
      </div>
    </div>
  );
}

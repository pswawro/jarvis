import { useState, useMemo, useRef } from "react";
import clsx from "clsx";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { LineChart as ELineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { Period, Filters, DimensionConfig, Scale, TreeTableSpec, TreeNode } from "../types";
import { useApi } from "../hooks/useApi";
import { filtersToExtra, scaleValue, scaleLabel } from "../utils";

echarts.use([ELineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, CanvasRenderer]);

interface Props {
  period: Period;
  filters: Filters;
  dimConfig: DimensionConfig;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const COLORS = [
  "#2563EB", "#059669", "#D97706", "#7C3AED", "#DC2626",
  "#0891B2", "#4F46E5", "#CA8A04", "#0D9488", "#E11D48",
];

const FADED_COLORS = [
  "#93bbfd", "#6ee7b7", "#fcd34d", "#c4b5fd", "#fca5a5",
  "#67e8f9", "#a5b4fc", "#fde047", "#5eead4", "#fda4af",
];

function fmtVal(v: number, scale: Scale): string {
  return `${scaleLabel(scale).replace("$", "")}${scaleValue(v, scale)}`;
}


function LandingRow({ node, depth, columns, closedMonth, scale }: { node: TreeNode; depth: number; columns: string[]; closedMonth: number; scale: Scale }) {
  const [expanded, setExpanded] = useState(depth === 0);
  const hasChildren = node.children.length > 0;
  const monthly = node.values.sparkline;
  const fyTotal = monthly.reduce((a, b) => a + b, 0);

  return (
    <>
      <tr
        onClick={hasChildren ? () => setExpanded(!expanded) : undefined}
        className={clsx(
          "border-b border-gray-100 transition-colors",
          depth === 0 && "bg-gray-50/80 font-semibold",
          depth === 1 && "bg-white font-medium",
          depth >= 2 && "bg-white text-gray-600",
          hasChildren && "cursor-pointer hover:bg-gray-50"
        )}
      >
        <td className="sticky left-0 bg-inherit px-3 py-1.5 text-[12px] whitespace-nowrap z-10" style={{ paddingLeft: 12 + depth * 16 }}>
          <span className="flex items-center gap-1">
            {hasChildren && (
              <svg className={clsx("w-3 h-3 transition-transform", expanded && "rotate-90")} fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
              </svg>
            )}
            {node.name}
          </span>
        </td>
        {monthly.map((val, i) => (
          <td
            key={i}
            className={clsx(
              "px-2 py-1.5 text-[11px] tabular-nums text-right whitespace-nowrap",
              i < closedMonth ? "text-az-navy" : "text-gray-400 italic"
            )}
          >
            {fmtVal(val, scale)}
          </td>
        ))}
        <td className="px-2 py-1.5 text-[11px] tabular-nums text-right font-semibold text-az-navy whitespace-nowrap">
          {fmtVal(fyTotal, scale)}
        </td>
      </tr>
      {expanded && node.children.map((child) => (
        <LandingRow key={child.id} node={child} depth={depth + 1} columns={columns} closedMonth={closedMonth} scale={scale} />
      ))}
    </>
  );
}

/* ---- Landing Chart: actuals solid, forecast faded + dashed, vertical "Now" line ---- */

function LandingChart({ data, closedMonth, scale }: { data: TreeTableSpec; closedMonth: number; scale: Scale }) {
  const chartRef = useRef<ReactEChartsCore>(null);
  const option = useMemo<echarts.EChartsOption>(() => {
    const fmtAxis = (v: number) => `${scaleLabel(scale)}${scaleValue(v, scale)}`;

    const nodes = data.tree.children.length > 0 ? data.tree.children : [data.tree];
    const xLabels = MONTHS.map((m, i) => i < closedMonth ? m : `${m}*`);
    const seriesList: any[] = [];

    for (let i = 0; i < nodes.length; i++) {
      const node = nodes[i];
      const color = COLORS[i % COLORS.length];
      const fadedColor = FADED_COLORS[i % FADED_COLORS.length];
      const sparkline = node.values.sparkline.map((v) => Math.round(v * 10) / 10);

      // Actuals: data up to closedMonth, null after
      const actualsData = sparkline.map((v, mi) => mi < closedMonth ? v : null);
      // Forecast: bridge from last actual so lines connect, then forecast data
      const forecastData = sparkline.map((v, mi) => mi >= closedMonth - 1 ? v : null);

      seriesList.push({
        name: node.name,
        type: "line",
        data: actualsData,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { width: 2, color },
        itemStyle: { color },
        emphasis: { lineStyle: { width: 3 }, focus: "series" as const },
        // Add vertical cutoff line only to first series
        ...(i === 0 ? {
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: { color: "#9ca3af", width: 1, type: "dashed" },
            data: [{ xAxis: closedMonth - 1 }],
            label: { show: true, formatter: "Now", position: "insideStartTop", fontSize: 9, color: "#9ca3af" },
          },
        } : {}),
      });

      seriesList.push({
        name: `${node.name} (fcst)`,
        type: "line",
        data: forecastData,
        symbol: "circle",
        symbolSize: 4,
        connectNulls: false,
        lineStyle: { width: 1.5, color, opacity: 0.35 },
        itemStyle: { color, opacity: 0.35 },
        legendHoverLink: false,
      });
    }

    // Only show actuals series in legend
    const legendData = nodes.map((n) => n.name);

    return {
      animation: false,
      grid: { top: 12, right: 16, bottom: 52, left: 4, containLabel: true },
      xAxis: {
        type: "category",
        data: xLabels,
        axisLine: { lineStyle: { color: "#e5e7eb" } },
        axisTick: { show: false },
        axisLabel: { fontSize: 10, color: "#9ca3af" },
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { fontSize: 10, color: "#9ca3af", formatter: (v: number) => fmtAxis(v) },
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
          const val = fmtAxis(p.value as number);
          const name = p.seriesName.replace(" (fcst)", "");
          const isFcst = p.seriesName.includes("(fcst)");
          const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
          return `<div style="font-size:10px;color:#9ca3af;margin-bottom:1px">${esc(p.name)}</div>
                  <div style="color:${p.color};font-weight:600">${esc(name)}: ${val}${isFcst ? " <i style='color:#9ca3af'>(forecast)</i>" : ""}</div>`;
        },
        extraCssText: "border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,0.06);",
      },
      legend: {
        type: "scroll",
        bottom: 0,
        itemWidth: 16,
        itemHeight: 2,
        textStyle: { fontSize: 11 },
        data: legendData,
      },
      series: seriesList,
    };
  }, [data, closedMonth, scale]);

  return (
    <div className="w-full px-3 pt-3 pb-1 flex flex-col">
      <div className="w-full h-64 sm:h-80">
        <ReactEChartsCore
          ref={chartRef}
          echarts={echarts}
          option={option}
          style={{ height: "100%", width: "100%" }}
          notMerge
        />
      </div>
    </div>
  );
}

/* ---- Main component ---- */

export function LandingView({ period, filters, dimConfig }: Props) {
  const [chartMode, setChartMode] = useState(false);
  const scale = filters.scale;
  const levelsKey = dimConfig.levels.join(",");
  const extra = useMemo(() => {
    const e = filtersToExtra(filters);
    e.closed_month = String(new Date().getMonth() || 12);
    e.levels = levelsKey;
    return e;
  }, [filters, levelsKey]);

  const { data, loading, error } = useApi<TreeTableSpec>("/landing", period, extra);

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center text-[13px] text-red-500">
        Failed to load data. Please try refreshing.
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const columns = data.columns;
  const closedMonth = new Date().getMonth() || 12; // getMonth() is 0-indexed; Jan=0→use 12 (Dec)

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 bg-white border-b border-gray-100">
        <div className="flex items-center gap-2">
          <h2 className="text-[13px] font-semibold text-gray-500 tracking-tight">{data.period_label}</h2>
          <span className="text-[10px] text-gray-400">* = forecast</span>
        </div>
        <button
          onClick={() => setChartMode((m) => !m)}
          className={clsx(
            "p-1 rounded transition-colors",
            chartMode ? "text-az-navy bg-blue-50" : "text-gray-400 hover:text-gray-600"
          )}
          title={chartMode ? "Show table" : "Show chart"}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            {chartMode ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-12.75A1.125 1.125 0 014.5 4.5h15a1.125 1.125 0 011.125 1.125v12.75M3.375 19.5h17.25M20.625 19.5a1.125 1.125 0 001.125-1.125V5.625a1.125 1.125 0 00-1.125-1.125H4.5" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
            )}
          </svg>
        </button>
      </div>

      {chartMode ? (
        <div className="flex-1">
          <LandingChart data={data} closedMonth={closedMonth} scale={scale} />
        </div>
      ) : (
        <div className="flex-1 overflow-auto">
          <table className="w-full text-left border-collapse min-w-[700px]">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50/60 sticky top-0 z-20">
                <th className="sticky left-0 bg-gray-50/60 px-3 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider z-20 w-0">
                  {columns[0]}
                </th>
                {columns.slice(1).map((col) => (
                  <th
                    key={col}
                    className={clsx(
                      "px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-right",
                      col.endsWith("*") ? "text-gray-300" : col === "FY Total" ? "text-az-navy" : "text-gray-400"
                    )}
                  >
                    {col.replace("*", "")}
                    {col.endsWith("*") && <span className="text-gray-300">*</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <LandingRow node={data.tree} depth={0} columns={columns} closedMonth={closedMonth} scale={scale} />
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

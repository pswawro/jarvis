import { useState, useRef, useMemo, useCallback } from "react";
import ReactEChartsCore from "echarts-for-react/lib/core";
import * as echarts from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { TreeNode, TreeTableSpec, AssistantContext } from "../types";
import { escapeHtml, sanitizeColor } from "../escapeHtml";
import { makeBaseContext } from "../utils";

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

function fmtValue(val: number): string {
  if (Math.abs(val) >= 1000) return `$${(val / 1000).toFixed(1)}B`;
  return `$${val.toFixed(0)}M`;
}

function varianceColor(pct: number, invert: boolean): string {
  const v = invert ? -pct : pct;
  if (v >= 3) return "#059669";
  if (v >= 0.5) return "#34d399";
  if (v >= -0.5) return "#6b7280";
  if (v >= -3) return "#f87171";
  return "#dc2626";
}

function findNode(node: TreeNode, id: string): TreeNode | null {
  if (node.id === id) return node;
  for (const c of node.children) {
    const found = findNode(c, id);
    if (found) return found;
  }
  return null;
}

interface Props {
  spec: TreeTableSpec;
  invertColor?: boolean;
  onAssistantTrigger?: (ctx: AssistantContext) => void;
  drillPath?: { id: string; name: string }[];
  onDrillPathChange?: (path: { id: string; name: string }[]) => void;
}

export function TreeMapChart({ spec, invertColor = false, onAssistantTrigger, drillPath: externalDrillPath, onDrillPathChange }: Props) {
  const [internalDrillPath, setInternalDrillPath] = useState<{ id: string; name: string }[]>([]);
  const drillPath = externalDrillPath ?? internalDrillPath;
  const setDrillPath = onDrillPathChange ?? setInternalDrillPath;
  const chartRef = useRef<ReactEChartsCore>(null);

  const currentNode = useMemo(() => {
    if (drillPath.length === 0) return spec.tree;
    const last = drillPath[drillPath.length - 1];
    return findNode(spec.tree, last.id) ?? spec.tree;
  }, [spec.tree, drillPath]);

  const items = useMemo(() => {
    const children = currentNode.children.length > 0 ? currentNode.children : [currentNode];
    return [...children].sort((a, b) => Math.abs(b.values.actual) - Math.abs(a.values.actual));
  }, [currentNode]);

  const drillable = useMemo(
    () => new Set(items.filter((n) => n.children.length > 0).map((n) => n.id)),
    [items],
  );

  const option = useMemo(() => {
    const names = items.map((n) => n.name);
    const actuals = items.map((n) => Math.abs(n.values.actual));
    const budgets = items.map((n) => Math.abs(n.values.comparator_value ?? n.values.budget));
    const variances = items.map((n) => n.values.comparator_variance_pct ?? n.values.variance_pct);
    const ids = items.map((n) => n.id);
    const compLabel = items[0]?.values.comparator_label ?? "Budget";

    return {
      animation: true,
      animationDuration: 300,
      animationEasing: "cubicOut",
      tooltip: {
        backgroundColor: "#fff",
        borderColor: "#e5e7eb",
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { fontSize: 12, color: "#374151" },
        extraCssText: "border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.08);",
        formatter: (params: any) => {
          const idx = params.dataIndex;
          const sign = variances[idx] >= 0 ? "+" : "";
          const color = varianceColor(variances[idx], invertColor);
          const canDrill = drillable.has(ids[idx]);
          const eName = escapeHtml(names[idx]);
          const eCompLabel = escapeHtml(compLabel);
          return `<div style="font-weight:600;font-size:13px;margin-bottom:4px">${eName}</div>
                  <div style="display:flex;justify-content:space-between;gap:16px">
                    <span style="color:#9ca3af">Actual</span><span style="font-weight:500">${fmtValue(actuals[idx])}</span>
                  </div>
                  <div style="display:flex;justify-content:space-between;gap:16px">
                    <span style="color:#9ca3af">${eCompLabel}</span><span style="font-weight:500">${fmtValue(budgets[idx])}</span>
                  </div>
                  <div style="color:${color};font-weight:600;margin-top:4px;font-size:13px">${sign}${variances[idx].toFixed(1)}%</div>
                  ${canDrill ? '<div style="color:#9ca3af;font-size:10px;margin-top:4px">Click to drill down</div>' : ""}`;
        },
      },
      grid: {
        left: 100,
        right: 120,
        top: 4,
        bottom: 4,
      },
      xAxis: {
        type: "value" as const,
        show: false,
        splitLine: { show: false },
      },
      yAxis: {
        type: "category" as const,
        data: names,
        inverse: true,
        axisLabel: {
          fontSize: 11,
          color: "#374151",
          fontWeight: 600 as any,
          width: 100,
          overflow: "truncate" as any,
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          name: "Actual",
          type: "bar",
          data: actuals.map((v, i) => ({
            value: v,
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: sanitizeColor(varianceColor(variances[i], invertColor)) },
                { offset: 1, color: sanitizeColor(varianceColor(variances[i], invertColor)) + "cc" },
              ]),
              borderRadius: [0, 4, 4, 0],
            },
          })),
          barMaxWidth: 32,
          barMinWidth: 12,
          barCategoryGap: "18%",
          z: 2,
          emphasis: {
            itemStyle: { shadowBlur: 6, shadowColor: "rgba(0,0,0,0.12)" },
          },
          label: {
            show: true,
            position: "right" as const,
            fontSize: 11,
            fontWeight: 500 as any,
            color: "#6b7280",
            formatter: (params: any) => {
              const idx = params.dataIndex;
              const sign = variances[idx] >= 0 ? "+" : "";
              const vColor = variances[idx] >= 0.5 ? "green" : variances[idx] <= -0.5 ? "red" : "";
              const arrow = drillable.has(ids[idx]) ? " ›" : "";
              return `${fmtValue(params.value)}  {${vColor || "neutral"}|${sign}${variances[idx].toFixed(1)}%}${arrow}`;
            },
            rich: {
              green: { fontSize: 11, fontWeight: 600 as any, color: "#059669" },
              red: { fontSize: 11, fontWeight: 600 as any, color: "#dc2626" },
              neutral: { fontSize: 11, fontWeight: 500 as any, color: "#9ca3af" },
            },
          },
        },
        {
          name: compLabel,
          type: "bar",
          data: budgets,
          barMaxWidth: 32,
          barMinWidth: 12,
          barGap: "-100%",
          z: 1,
          itemStyle: {
            color: "#e5e7eb",
            borderRadius: [0, 4, 4, 0],
          },
          label: { show: false },
        },
      ],
    } as echarts.EChartsCoreOption;
  }, [items, invertColor, drillable]);

  const handleClick = useCallback(
    (params: any) => {
      if (params.seriesName !== "Actual") return;
      const idx = params.dataIndex;
      const node = items[idx];
      if (node.children.length > 0) {
        setDrillPath([...drillPath, { id: node.id, name: node.name }]);
      }
    },
    [items, drillPath, setDrillPath],
  );

  const handleBack = useCallback(() => {
    setDrillPath(drillPath.slice(0, -1));
  }, [drillPath, setDrillPath]);

  const handleContextMenu = useCallback(
    (params: any) => {
      if (params.seriesName !== "Actual" || !onAssistantTrigger) return;
      params.event?.event?.preventDefault?.();
      const idx = params.dataIndex;
      const node = items[idx];
      onAssistantTrigger({
        ...makeBaseContext("treemap_bar"),
        dataPoint: {
          node_id: node.id,
          node_name: node.name,
          values: node.values,
          drill_path: drillPath.map((p) => p.name),
        },
      });
    },
    [items, drillPath, onAssistantTrigger],
  );

  const onEvents = useMemo(() => ({ click: handleClick, contextmenu: handleContextMenu }), [handleClick, handleContextMenu]);

  return (
    <div className="flex flex-col w-full h-full">
      {drillPath.length > 0 && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-gray-100">
          <button
            onClick={handleBack}
            className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </button>
          <span className="text-[11px] text-gray-300">|</span>
          {drillPath.map((p, i) => (
            <span key={p.id} className="text-[11px] text-gray-400">
              {i > 0 && <span className="mx-1 text-gray-300">›</span>}
              {p.name}
            </span>
          ))}
        </div>
      )}
      <div className="flex-1 px-1 pt-1 pb-1 min-h-0">
        <ReactEChartsCore
          ref={chartRef}
          echarts={echarts}
          option={option}
          style={{ height: "100%", width: "100%" }}
          onEvents={onEvents}
          notMerge
        />
      </div>
    </div>
  );
}

import React, { useMemo, useCallback, useState } from "react";
import clsx from "clsx";
import type { Period, Filters, DimensionConfig, LineChartSpec, ChartInteraction, AssistantContext, Scale } from "../types";
import { useApi } from "../hooks/useApi";
import { TimeChart } from "./TimeChart";
import { filtersToExtra, scaleValue, scaleLabel } from "../utils";

/* ---------- Types matching backend PhasedTreeSpec ---------- */

interface PhasedPeriod {
  label: string;
  ACT: number;
  BUD: number;
  MTP: number;
  RBU2: number;
  PY: number;
}

interface PhasedTreeNode {
  id: string;
  name: string;
  periods: PhasedPeriod[];
  children: PhasedTreeNode[];
}

interface PhasedTreeSpec {
  type: "phased_tree";
  period_label: string;
  granularity: string;
  period_labels: string[];
  scenarios: string[];
  tree: PhasedTreeNode;
}

/* ---------- Props ---------- */

interface Props {
  period: Period;
  filters: Filters;
  dimConfig: DimensionConfig;
  scenarioPreset: string;
  onScenarioPresetChange: (preset: string) => void;
  onInteraction?: (i: ChartInteraction) => void;
  onAssistantTrigger?: (ctx: AssistantContext) => void;
}

/* ---------- Constants ---------- */

const SCENARIO_LABELS: Record<string, string> = {
  ACT: "Actuals",
  BUD: "Budget",
  MTP: "MTP",
  RBU2: "RBU2",
  PY: "Prior Year",
};

const SCENARIO_STYLES: Record<string, string> = {
  ACT: "text-az-navy font-semibold",
  BUD: "text-blue-500",
  MTP: "text-emerald-600",
  RBU2: "text-amber-600",
  PY: "text-gray-400",
};

interface ScenarioPreset {
  id: string;
  label: string;
  keys: string[];           // comparator keys to show (ACT is always the base)
}

const SCENARIO_PRESETS: ScenarioPreset[] = [
  { id: "all",      label: "All Scenarios",     keys: ["BUD", "MTP", "RBU2", "PY"] },
  { id: "bud",      label: "ACT vs Budget",     keys: ["BUD"] },
  { id: "mtp",      label: "ACT vs MTP",        keys: ["MTP"] },
  { id: "rbu2",     label: "ACT vs RBU2",       keys: ["RBU2"] },
  { id: "py",       label: "ACT vs Prior Year", keys: ["PY"] },
  { id: "bud_mtp",  label: "ACT vs BUD & MTP",  keys: ["BUD", "MTP"] },
  { id: "bud_py",   label: "ACT vs BUD & PY",   keys: ["BUD", "PY"] },
];

/* ---------- Helpers ---------- */

function fmtVal(v: number, scale: Scale): string {
  return `${scaleLabel(scale).replace("$", "")}${scaleValue(v, scale)}`;
}

function fmtPct(v: number): string {
  if (!isFinite(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}

function varPct(actual: number, comp: number): number {
  if (comp === 0) return 0;
  return ((actual - comp) / Math.abs(comp)) * 100;
}

function periodTotal(periods: PhasedPeriod[], key: string): number {
  return periods.reduce((s, p) => s + (p[key as keyof PhasedPeriod] as number), 0);
}

/* ---------- Flattened row for rendering ---------- */

interface FlatRow {
  node: PhasedTreeNode;
  depth: number;
}

function flattenTree(node: PhasedTreeNode, depth: number, expandedIds: Set<string>): FlatRow[] {
  const rows: FlatRow[] = [{ node, depth }];
  if (expandedIds.has(node.id) && node.children.length > 0) {
    for (const child of node.children) {
      rows.push(...flattenTree(child, depth + 1, expandedIds));
    }
  }
  return rows;
}

/* ---------- Component ---------- */

const EXPENSE_LEVELS = new Set(["unit", "sub_unit"]);

export function ScenariosPage({ period, filters, dimConfig, scenarioPreset, onScenarioPresetChange, onInteraction, onAssistantTrigger }: Props) {
  const [chartMode, setChartMode] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set(["TOTAL"]));
  const [expandedScenarios, setExpandedScenarios] = useState<Set<string>>(new Set());
  const [scenarioDropdownOpen, setScenarioDropdownOpen] = useState(false);

  const levelsKey = dimConfig.levels.join(",");
  const granularity = filters.granularity;
  const scale = filters.scale;
  const isExpense = dimConfig.levels.some((l) => EXPENSE_LEVELS.has(l));
  const useFilters = !isExpense;
  const extra = useMemo(() => useFilters ? filtersToExtra(filters) : {}, [filters, useFilters]);

  // Scenario chart
  const scenarioExtra = useMemo(() => ({ ...extra, levels: levelsKey }), [extra, levelsKey]);
  const { data: scenarioData, loading: scenarioLoading, error: scenarioError } = useApi<LineChartSpec>("/scenario-chart", period, scenarioExtra);

  // Phased tree — reuse `extra` instead of recomputing filtersToExtra
  const phasedExtra = useMemo(() => ({
    ...extra,
    granularity,
    levels: levelsKey,
  }), [extra, granularity, levelsKey]);
  const { data: phasedData, loading: phasedLoading, error: phasedError } = useApi<PhasedTreeSpec>("/phased", period, phasedExtra);

  const flatRows = useMemo(() => {
    if (!phasedData) return [];
    return flattenTree(phasedData.tree, 0, expandedIds);
  }, [phasedData, expandedIds]);

  const toggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleScenarioDetail = useCallback((id: string) => {
    setExpandedScenarios((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const wrapTrigger = useCallback(
    (ctx: AssistantContext) => {
      onAssistantTrigger?.({ ...ctx, page: "phased", levels: dimConfig.levels, period, filters });
    },
    [onAssistantTrigger, dimConfig.levels, period, filters],
  );

  const periodLabels = phasedData?.period_labels ?? [];
  const activePreset = SCENARIO_PRESETS.find((p) => p.id === scenarioPreset) ?? SCENARIO_PRESETS[0];
  const marginKeys = activePreset.keys;
  const headerLabel = activePreset.keys.length === 1
    ? `${filters.year} Actuals vs ${SCENARIO_LABELS[activePreset.keys[0]]}`
    : `${filters.year} Scenario Comparison`;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-white border-b border-gray-100">
        <h2 className="text-[13px] font-semibold text-gray-500 tracking-tight">Scenarios</h2>

        {/* Scenario preset selector */}
        <div className="relative">
          <button
            onClick={() => setScenarioDropdownOpen(!scenarioDropdownOpen)}
            className={clsx(
              "flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border transition-all",
              scenarioDropdownOpen
                ? "border-az-navy bg-blue-50 text-az-navy"
                : "border-gray-200 text-gray-600 hover:border-gray-300"
            )}
          >
            {activePreset.label}
            <svg
              className={clsx("w-3 h-3 transition-transform", scenarioDropdownOpen && "rotate-180")}
              fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
          {scenarioDropdownOpen && (
            <>
              <div className="fixed inset-0 z-30" onClick={() => setScenarioDropdownOpen(false)} />
              <div className="absolute left-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-40 py-1 min-w-[180px]">
                {SCENARIO_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => { onScenarioPresetChange(preset.id); setScenarioDropdownOpen(false); }}
                    className={clsx(
                      "w-full text-left px-3 py-1.5 text-[11px] font-medium transition-colors",
                      preset.id === scenarioPreset
                        ? "text-az-navy bg-blue-50"
                        : "text-gray-600 hover:bg-gray-50"
                    )}
                  >
                    <span>{preset.label}</span>
                    <span className="block text-[9px] text-gray-400 mt-0.5">
                      {preset.keys.map((k) => SCENARIO_LABELS[k]).join(", ")}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="flex-1" />

        <button
          onClick={() => setChartMode(!chartMode)}
          className={clsx(
            "p-1 rounded transition-colors",
            chartMode ? "text-az-navy bg-blue-50" : "text-gray-400 hover:text-gray-600"
          )}
          title={chartMode ? "Show table" : "Show trend"}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            {chartMode ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-12.75A1.125 1.125 0 014.5 4.5h15a1.125 1.125 0 011.125 1.125v12.75M3.375 19.5h17.25M20.625 19.5a1.125 1.125 0 001.125-1.125V5.625a1.125 1.125 0 00-1.125-1.125H4.5" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
            )}
          </svg>
        </button>
      </div>

      {chartMode ? (
        <div className="flex-1">
          {scenarioError ? (
            <div className="h-full flex items-center justify-center text-[13px] text-red-500">
              Failed to load scenario data. Please try refreshing.
            </div>
          ) : scenarioLoading || !scenarioData ? (
            <div className="h-full flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <TimeChart spec={scenarioData} onInteraction={onInteraction} onAssistantTrigger={wrapTrigger} />
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-auto">
          {phasedError ? (
            <div className="flex items-center justify-center py-8 text-[13px] text-red-500">
              Failed to load data. Please try refreshing.
            </div>
          ) : phasedLoading || !phasedData ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-6 h-6 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <table className="w-full text-left border-collapse min-w-[600px]">
              <thead className="sticky top-0 z-20">
                {/* Grouping row: year + comparator */}
                <tr className="bg-gray-50/60">
                  <th rowSpan={2} className="sticky left-0 bg-gray-50/60 px-3 py-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wider z-20 border-b border-gray-200 align-bottom w-0">
                    Name
                  </th>
                  <th
                    colSpan={periodLabels.length}
                    className="px-2 py-1 text-[10px] font-semibold text-az-navy tracking-wide text-center border-b border-gray-100"
                  >
                    {headerLabel}
                  </th>
                  <th rowSpan={2} className="px-2 py-1 text-[10px] font-semibold text-az-navy uppercase tracking-wider text-right border-b border-gray-200 align-bottom">
                    Total
                  </th>
                </tr>
                {/* Period labels row */}
                <tr className="bg-gray-50/60 border-b border-gray-200">
                  {periodLabels.map((pl) => (
                    <th key={pl} className="px-2 py-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wider text-right">
                      {pl}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {flatRows.map(({ node, depth }) => {
                  const hasChildren = node.children.length > 0;
                  const isExpanded = expandedIds.has(node.id);
                  const showScenarios = marginKeys.length <= 2 || expandedScenarios.has(node.id);
                  const actTotal = periodTotal(node.periods, "ACT");

                  return (
                    <React.Fragment key={node.id}>
                      {/* Main row — ACT values */}
                      <tr
                        onClick={hasChildren ? () => toggleExpand(node.id) : undefined}
                        onDoubleClick={() => toggleScenarioDetail(node.id)}
                        className={clsx(
                          "border-b transition-colors",
                          depth === 0 && "bg-gray-50/80 border-gray-200",
                          depth === 1 && "bg-white border-gray-100",
                          depth >= 2 && "bg-white border-gray-50",
                          hasChildren && "cursor-pointer hover:bg-gray-50"
                        )}
                      >
                        <td className="sticky left-0 bg-inherit px-3 py-1.5 whitespace-nowrap z-10" style={{ paddingLeft: 12 + depth * 16 }}>
                          <span className="flex items-center gap-1">
                            {hasChildren && (
                              <svg
                                className={clsx("w-3 h-3 shrink-0 transition-transform", isExpanded && "rotate-90")}
                                fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor"
                              >
                                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                              </svg>
                            )}
                            <span className={clsx(
                              depth === 0 && "text-[12px] font-semibold text-az-navy",
                              depth === 1 && "text-[12px] font-medium text-az-navy/85",
                              depth >= 2 && "text-[11px] font-normal text-gray-600"
                            )}>
                              {node.name}
                            </span>
                          </span>
                        </td>
                        {node.periods.map((p) => (
                          <td key={p.label} className={clsx(
                            "px-2 py-1.5 text-right tabular-nums whitespace-nowrap text-az-navy",
                            depth === 0 && "text-[12px] font-semibold",
                            depth === 1 && "text-[12px] font-medium",
                            depth >= 2 && "text-[11px]"
                          )}>
                            {fmtVal(p.ACT, scale)}
                          </td>
                        ))}
                        <td className={clsx(
                          "px-2 py-1.5 text-right tabular-nums whitespace-nowrap text-az-navy font-bold",
                          depth === 0 ? "text-[12px]" : "text-[11px]"
                        )}>
                          {fmtVal(actTotal, scale)}
                        </td>
                      </tr>

                      {/* Scenario detail rows (toggled by double-click) */}
                      {showScenarios && marginKeys.map((scenario) => {
                        const scTotal = periodTotal(node.periods, scenario);
                        return (
                          <tr key={`${node.id}_${scenario}`} className="border-b border-gray-50 bg-gray-50/30">
                            <td className="sticky left-0 bg-gray-50/30 px-3 py-1 whitespace-nowrap z-10" style={{ paddingLeft: 12 + depth * 16 + 16 }}>
                              <span className={clsx("text-[11px]", SCENARIO_STYLES[scenario])}>
                                {SCENARIO_LABELS[scenario]}
                              </span>
                            </td>
                            {node.periods.map((p) => (
                              <td key={p.label} className={clsx("px-2 py-1 text-right tabular-nums text-[11px] whitespace-nowrap", SCENARIO_STYLES[scenario])}>
                                {fmtVal(p[scenario as keyof PhasedPeriod] as number, scale)}
                              </td>
                            ))}
                            <td className={clsx("px-2 py-1 text-right tabular-nums text-[11px] font-medium whitespace-nowrap", SCENARIO_STYLES[scenario])}>
                              {fmtVal(scTotal, scale)}
                            </td>
                          </tr>
                        );
                      })}
                      {showScenarios && marginKeys.map((key) => {
                        const totalPct = varPct(periodTotal(node.periods, "ACT"), periodTotal(node.periods, key));
                        return (
                          <tr key={`${node.id}_var_${key}`} className="border-b border-gray-50 bg-gray-50/30">
                            <td className="sticky left-0 bg-gray-50/30 px-3 py-0.5 whitespace-nowrap z-10" style={{ paddingLeft: 12 + depth * 16 + 16 }}>
                              <span className={clsx("text-[10px] font-medium", SCENARIO_STYLES[key])}>
                                vs {SCENARIO_LABELS[key]}
                              </span>
                            </td>
                            {node.periods.map((p) => {
                              const pct = varPct(p.ACT, p[key as keyof PhasedPeriod] as number);
                              return (
                                <td key={p.label} className={clsx(
                                  "px-2 py-0.5 text-right tabular-nums text-[10px] font-medium whitespace-nowrap",
                                  pct > 0 ? "text-emerald-600" : pct < 0 ? "text-red-500" : "text-gray-400"
                                )}>
                                  {fmtPct(pct)}
                                </td>
                              );
                            })}
                            <td className={clsx(
                              "px-2 py-0.5 text-right tabular-nums text-[10px] font-semibold whitespace-nowrap",
                              totalPct > 0 ? "text-emerald-600" : totalPct < 0 ? "text-red-500" : "text-gray-400"
                            )}>
                              {fmtPct(totalPct)}
                            </td>
                          </tr>
                        );
                      })}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import type { Period, Filters, DimensionConfig, LevelId, TreeTableSpec, ChartInteraction, AssistantContext, TreeNode } from "../types";
import { useApi } from "../hooks/useApi";
import { TreeTable } from "./TreeTable";
import { TreeMapChart } from "./TreeMapChart";
import { filtersToExtra, comparatorLabel } from "../utils";
import clsx from "clsx";

/** Walk the tree finding the deepest single-branch expanded path (skipping root). */
function expandedIdsToDrillPath(tree: TreeNode, expandedIds: Set<string>): { id: string; name: string }[] {
  const path: { id: string; name: string }[] = [];
  let current = tree;
  while (current.children.length > 0) {
    const expandedChildren = current.children.filter((c) => expandedIds.has(c.id));
    if (expandedChildren.length === 1) {
      path.push({ id: expandedChildren[0].id, name: expandedChildren[0].name });
      current = expandedChildren[0];
    } else {
      break;
    }
  }
  return path;
}

/** Convert a chart drillPath into expandedIds for the table (expand root + each path node). */
function drillPathToExpandedIds(tree: TreeNode, drillPath: { id: string; name: string }[]): Set<string> {
  const ids = new Set([tree.id]);
  for (const p of drillPath) {
    ids.add(p.id);
  }
  return ids;
}

interface Props {
  period: Period;
  filters: Filters;
  dimConfig: DimensionConfig;
  onInteraction?: (i: ChartInteraction) => void;
  onAssistantTrigger?: (ctx: AssistantContext) => void;
}

// Domain detection from levels
const LEVEL_DOMAINS: Record<LevelId, string> = {
  ta: "revenue", brand: "revenue", market: "revenue", region: "revenue",
  unit: "expense", sub_unit: "expense",
  category: "competitive",
};

const LEVEL_LABELS: Record<LevelId, string> = {
  ta: "Therapeutic Area", brand: "Brand", market: "Market", region: "Region",
  unit: "Unit", sub_unit: "Sub-unit", category: "Category",
};

function getDomain(levels: LevelId[]): string {
  return LEVEL_DOMAINS[levels[0]] ?? "revenue";
}

function getDomainConfig(domain: string) {
  switch (domain) {
    case "expense":
      return { useFilters: false, invertColor: true, headerLabels: undefined, varianceSuffix: undefined };
    case "competitive":
      return { useFilters: true, invertColor: false, headerLabels: { actual: "AZ Rev", variance: "Shr \u0394", share: "Share", trend: "Shr Trend" }, varianceSuffix: "pp" };
    default:
      return { useFilters: true, invertColor: false, headerLabels: undefined, varianceSuffix: undefined };
  }
}

function getSubtitle(levels: LevelId[], domain: string): string {
  const path = levels.map((l) => LEVEL_LABELS[l]).join(" → ");
  switch (domain) {
    case "expense": return `Expenses by ${path}`;
    case "competitive": return `Market Share by ${path}`;
    default: return `Revenue by ${path}`;
  }
}

export function OverviewPage({ period, filters, dimConfig, onAssistantTrigger }: Props) {
  const [chartMode, setChartMode] = useState(false);
  const [chartDrillPath, setChartDrillPath] = useState<{ id: string; name: string }[]>([]);
  const [tableExpandedIds, setTableExpandedIds] = useState<Set<string>>(new Set());
  const levelsKey = dimConfig.levels.join(",");
  const domain = getDomain(dimConfig.levels);
  const config = getDomainConfig(domain);
  const subtitle = getSubtitle(dimConfig.levels, domain);
  const dataRef = useRef<TreeTableSpec | null>(null);

  // Reset drill state when levels change
  useEffect(() => {
    setChartDrillPath([]);
    setTableExpandedIds(new Set());
  }, [levelsKey]);

  const extra = useMemo(() => {
    const e = config.useFilters ? filtersToExtra(filters) : {};
    e.levels = levelsKey;
    return e;
  }, [filters, config.useFilters, levelsKey]);
  const { data } = useApi<TreeTableSpec>("/tree", period, extra);

  // Initialize table expandedIds when data loads
  useEffect(() => {
    if (data && data !== dataRef.current) {
      dataRef.current = data;
      setTableExpandedIds((prev) => prev.size === 0 ? new Set([data.tree.id]) : prev);
    }
  }, [data]);

  const handleToggleMode = useCallback(() => {
    if (!data) return;
    if (chartMode) {
      // Switching chart → table: sync chart drill into table expanded ids
      setTableExpandedIds(drillPathToExpandedIds(data.tree, chartDrillPath));
    } else {
      // Switching table → chart: sync table expanded into chart drill path
      setChartDrillPath(expandedIdsToDrillPath(data.tree, tableExpandedIds));
    }
    setChartMode((m) => !m);
  }, [chartMode, data, chartDrillPath, tableExpandedIds]);

  const wrapTrigger = useCallback(
    (ctx: AssistantContext) => {
      onAssistantTrigger?.({ ...ctx, page: "overview", levels: dimConfig.levels, period, filters });
    },
    [onAssistantTrigger, dimConfig.levels, period, filters],
  );

  if (!data) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 bg-white border-b border-gray-100">
        <h2 className="text-[13px] font-semibold text-gray-500 tracking-tight">{subtitle}</h2>
        <button
          onClick={handleToggleMode}
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

      {chartMode && (
        <TreeMapChart spec={data} invertColor={config.invertColor} onAssistantTrigger={wrapTrigger} drillPath={chartDrillPath} onDrillPathChange={setChartDrillPath} />
      )}
      <div className={chartMode ? "hidden" : "contents"}>
        <TreeTable
          tree={data.tree}
          columns={data.columns}
          invertColor={config.invertColor}
          headerLabels={config.headerLabels ?? { variance: comparatorLabel(filters.comparator) }}
          varianceSuffix={config.varianceSuffix}
          onAssistantTrigger={wrapTrigger}
          scale={filters.scale}
          comparator={filters.comparator}
          expandedIds={tableExpandedIds}
          onExpandedIdsChange={setTableExpandedIds}
        />
      </div>
    </div>
  );
}

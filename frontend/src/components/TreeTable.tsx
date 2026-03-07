import { useState, useMemo } from "react";
import clsx from "clsx";
import type { TreeNode, AssistantContext, Scale, Comparator } from "../types";
import { TreeRow } from "./TreeRow";

type SortKey = "actual" | "forecast" | "variance_pct" | "market_share_pct";
type SortDir = "asc" | "desc";

interface HeaderLabels {
  actual?: string;
  variance?: string;
  share?: string;
  trend?: string;
}

interface Props {
  tree: TreeNode;
  columns: string[];
  invertColor?: boolean;
  headerLabels?: HeaderLabels;
  varianceSuffix?: string;
  onAssistantTrigger?: (ctx: AssistantContext) => void;
  scale?: Scale;
  comparator?: Comparator;
  expandedIds?: Set<string>;
  onExpandedIdsChange?: (ids: Set<string>) => void;
}

function sortChildren(children: TreeNode[], sortKey: SortKey, sortDir: SortDir): TreeNode[] {
  return [...children].sort((a, b) => {
    const aVal = a.values[sortKey] ?? 0;
    const bVal = b.values[sortKey] ?? 0;
    if (Number.isNaN(aVal) || Number.isNaN(bVal)) return 0;
    return sortDir === "desc" ? bVal - aVal : aVal - bVal;
  });
}

export function TreeTable({ tree, columns, invertColor, headerLabels, varianceSuffix, onAssistantTrigger, scale, comparator, expandedIds: externalExpandedIds, onExpandedIdsChange }: Props) {
  const [internalExpandedIds, setInternalExpandedIds] = useState<Set<string>>(() => new Set([tree.id]));
  const expandedIds = externalExpandedIds ?? internalExpandedIds;
  const setExpandedIds = onExpandedIdsChange ?? setInternalExpandedIds;
  const [sortKey, setSortKey] = useState<SortKey>("actual");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function toggleExpand(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sortIndicator = (key: SortKey) =>
    sortKey === key ? (sortDir === "desc" ? " \u25BC" : " \u25B2") : "";

  const visibleRows = useMemo(() => {
    const rows: { node: TreeNode; depth: number; parentPath: string[] }[] = [];

    function walk(node: TreeNode, depth: number, parentPath: string[]) {
      rows.push({ node, depth, parentPath });
      if (expandedIds.has(node.id) && node.children.length > 0) {
        const sorted = sortChildren(node.children, sortKey, sortDir);
        for (const child of sorted) {
          walk(child, depth + 1, [...parentPath, node.name]);
        }
      }
    }

    walk(tree, 0, []);
    return rows;
  }, [tree, expandedIds, sortKey, sortDir]);

  const showShare = columns.includes("Share");
  const showForecast = columns.includes("Forecast");
  const showExpenseBreakdown = columns.includes("Personnel");
  const h = {
    actual: headerLabels?.actual ?? "Actual",
    variance: headerLabels?.variance ?? "vs Bgt",
    share: headerLabels?.share ?? "Mkt Shr",
    trend: headerLabels?.trend ?? "12m Trend",
  };

  return (
    <div className="flex flex-col max-w-4xl mx-auto w-full">
      {/* Column headers */}
      <div className="sticky top-0 z-10 flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200 text-[10px] font-medium text-gray-500 uppercase tracking-wider">
        <span className="flex-1 min-w-0">Name</span>
        <button onClick={() => handleSort("actual")} className={clsx("text-right shrink-0 w-[72px] hover:text-az-navy transition-colors", sortKey === "actual" && "text-az-navy")}>
          {h.actual}{sortIndicator("actual")}
        </button>
        {showForecast && (
          <button onClick={() => handleSort("forecast")} className={clsx("hidden sm:block text-right shrink-0 w-[72px] hover:text-az-navy transition-colors", sortKey === "forecast" && "text-az-navy")}>
            Fcst{sortIndicator("forecast")}
          </button>
        )}
        {showExpenseBreakdown && (
          <>
            <span className="hidden sm:block shrink-0 w-[64px] text-right">Personnel</span>
            <span className="hidden sm:block shrink-0 w-[64px] text-right">External</span>
            <span className="hidden sm:block shrink-0 w-[64px] text-right">Other</span>
          </>
        )}
        <button onClick={() => handleSort("variance_pct")} className={clsx("shrink-0 hover:text-az-navy w-[72px] text-right transition-colors", sortKey === "variance_pct" && "text-az-navy")}>
          {h.variance}{sortIndicator("variance_pct")}
        </button>
        {showShare && (
          <button onClick={() => handleSort("market_share_pct")} className={clsx("hidden sm:block shrink-0 hover:text-az-navy w-[60px] text-right transition-colors", sortKey === "market_share_pct" && "text-az-navy")}>
            {h.share}{sortIndicator("market_share_pct")}
          </button>
        )}
        <span className="hidden sm:block w-[72px] text-center">{h.trend}</span>
      </div>

      {/* Rows */}
      <div className="overflow-y-auto flex-1">
        {visibleRows.map(({ node, depth, parentPath }) => (
          <TreeRow
            key={node.id}
            node={node}
            depth={depth}
            isExpanded={expandedIds.has(node.id)}
            hasChildren={node.children.length > 0}
            onToggle={() => toggleExpand(node.id)}
            showShare={showShare}
            showForecast={showForecast}
            showExpenseBreakdown={showExpenseBreakdown}
            invertColor={invertColor}
            varianceSuffix={varianceSuffix}
            parentPath={parentPath}
            onAssistantTrigger={onAssistantTrigger}
            scale={scale}
            comparator={comparator}
          />
        ))}
      </div>
    </div>
  );
}

import { memo, useCallback } from "react";
import clsx from "clsx";
import type { TreeNode, TreeNodeValues, AssistantContext, Scale, Comparator } from "../types";
import { VariancePill } from "./VariancePill";
import { Sparkline } from "./Sparkline";
import { useLongPress } from "../hooks/useLongPress";
import { scaleValue } from "../utils";

interface Props {
  node: TreeNode;
  depth: number;
  isExpanded: boolean;
  hasChildren: boolean;
  onToggle: () => void;
  showShare?: boolean;
  showForecast?: boolean;
  showExpenseBreakdown?: boolean;
  invertColor?: boolean;
  varianceSuffix?: string;
  parentPath?: string[];
  onAssistantTrigger?: (ctx: AssistantContext) => void;
  scale?: Scale;
  comparator?: Comparator;
}

function formatValue(val: number, scale: Scale = "M"): string {
  const suffix = scale === "M" ? "M" : scale === "K" ? "K" : "B";
  return `$${scaleValue(val, scale)}${suffix}`;
}

const COMPARATOR_VARIANCE: Record<Comparator, keyof TreeNodeValues> = {
  BUD: "variance_pct",
  MTP: "mtp_variance_pct",
  RBU2: "rbu2_variance_pct",
  PYACT: "py_variance_pct",
};

export const TreeRow = memo(function TreeRow({ node, depth, isExpanded, hasChildren, onToggle, showShare, showForecast, showExpenseBreakdown, invertColor, varianceSuffix, parentPath, onAssistantTrigger, scale = "M", comparator = "BUD" }: Props) {
  const { values } = node;

  const triggerAssistant = useCallback(() => {
    if (!onAssistantTrigger) return;
    onAssistantTrigger({
      source: "tree_row",
      page: "overview", // will be overridden by page component wrapper
      dimension: "brand", // will be overridden
      period: { year: new Date().getFullYear(), quarter: null }, // will be overridden
      filters: { market_id: [], ta: [], product: [], comparator: "BUD", scale: "M", year: new Date().getFullYear(), granularity: "quarter" }, // will be overridden
      dataPoint: {
        node_id: node.id,
        node_name: node.name,
        values: node.values,
        parent_path: parentPath,
      },
    });
  }, [onAssistantTrigger, node, parentPath]);

  const longPress = useLongPress(triggerAssistant);

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      if (!onAssistantTrigger) return;
      e.preventDefault();
      triggerAssistant();
    },
    [onAssistantTrigger, triggerAssistant],
  );

  const handleClick = useCallback(() => {
    if (hasChildren && !longPress.didLongPress.current) onToggle();
  }, [hasChildren, longPress.didLongPress, onToggle]);

  return (
    <button
      onClick={hasChildren ? handleClick : undefined}
      onContextMenu={handleContextMenu}
      {...longPress}
      className={clsx(
        "w-full flex items-center gap-1.5 sm:gap-2 px-3 text-left transition-colors",
        depth === 0 && "py-2.5 bg-gray-50/80 border-b border-gray-200",
        depth === 1 && "py-2 bg-white border-b border-gray-100",
        depth >= 2 && "py-1.5 bg-white border-b border-gray-50",
        hasChildren && "cursor-pointer hover:bg-gray-50",
        !hasChildren && "cursor-default hover:bg-gray-50/50"
      )}
    >
      {/* Indent + chevron */}
      <div
        className="flex items-center shrink-0"
        style={{ paddingLeft: depth * 16 }}
      >
        {hasChildren ? (
          <svg
            className={clsx(
              "w-3 h-3 transition-transform duration-200",
              isExpanded ? "rotate-90 text-gray-500" : "text-gray-400"
            )}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2.5}
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
        ) : (
          <span className="w-3" />
        )}
      </div>

      {/* Name */}
      <span
        className={clsx(
          "flex-1 truncate",
          depth === 0 && "text-sm font-semibold text-az-navy",
          depth === 1 && "text-sm font-medium text-az-navy/85",
          depth >= 2 && "text-[13px] font-normal text-gray-600"
        )}
      >
        {node.name}
      </span>

      {/* Actual value */}
      <span
        className={clsx(
          "tabular-nums shrink-0 text-az-navy w-[72px] text-right",
          depth === 0 && "text-sm font-semibold",
          depth === 1 && "text-sm font-medium",
          depth >= 2 && "text-[13px]"
        )}
      >
        {formatValue(values.actual, scale)}
      </span>

      {/* Forecast */}
      {showForecast && values.forecast != null && (
        <span
          className={clsx(
            "hidden sm:inline-flex tabular-nums shrink-0 text-gray-500 w-[72px] text-right",
            depth === 0 && "text-sm font-semibold",
            depth === 1 && "text-sm font-medium",
            depth >= 2 && "text-[13px]"
          )}
        >
          {formatValue(values.forecast, scale)}
        </span>
      )}

      {/* Expense breakdown columns */}
      {showExpenseBreakdown && (
        <>
          <span className={clsx("hidden sm:inline-flex tabular-nums shrink-0 text-gray-500 w-[64px] text-right", depth === 0 ? "text-[12px] font-semibold" : depth === 1 ? "text-[12px] font-medium" : "text-[11px]")}>
            {formatValue(values.personnel_costs ?? 0, scale)}
          </span>
          <span className={clsx("hidden sm:inline-flex tabular-nums shrink-0 text-gray-500 w-[64px] text-right", depth === 0 ? "text-[12px] font-semibold" : depth === 1 ? "text-[12px] font-medium" : "text-[11px]")}>
            {formatValue(values.external_costs ?? 0, scale)}
          </span>
          <span className={clsx("hidden sm:inline-flex tabular-nums shrink-0 text-gray-500 w-[64px] text-right", depth === 0 ? "text-[12px] font-semibold" : depth === 1 ? "text-[12px] font-medium" : "text-[11px]")}>
            {formatValue(values.other_costs ?? 0, scale)}
          </span>
          {values.fte_count != null && (
            <span className={clsx("hidden sm:inline-flex tabular-nums shrink-0 text-gray-500 w-[54px] text-right", depth === 0 ? "text-[12px] font-semibold" : depth === 1 ? "text-[12px] font-medium" : "text-[11px]")}>
              {values.fte_count >= 1000 ? `${(values.fte_count / 1000).toFixed(1)}K` : values.fte_count.toFixed(0)}
            </span>
          )}
          {values.cost_per_fte != null && (
            <span className={clsx("hidden sm:inline-flex tabular-nums shrink-0 text-gray-500 w-[54px] text-right", depth === 0 ? "text-[12px] font-semibold" : depth === 1 ? "text-[12px] font-medium" : "text-[11px]")}>
              {formatValue(values.cost_per_fte, scale)}
            </span>
          )}
        </>
      )}

      {/* vs Comparator (Budget/MTP/RBU2/PY) */}
      <VariancePill value={(values[COMPARATOR_VARIANCE[comparator]] as number | null) ?? values.variance_pct ?? 0} invertColor={invertColor} suffix={varianceSuffix} />

      {/* Market Share */}
      {showShare && values.market_share_pct != null && (
        <span className="hidden sm:inline-flex text-[11px] font-medium tabular-nums text-gray-500 w-[60px] text-right shrink-0">
          {values.market_share_pct.toFixed(1)}%
        </span>
      )}

      {/* Sparkline */}
      <span className="hidden sm:inline-flex w-[72px] justify-center">
        <Sparkline data={values.sparkline} />
      </span>
    </button>
  );
});

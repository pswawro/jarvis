import { useState } from "react";
import clsx from "clsx";
import type { KpiStripSpec, Scale } from "../types";
import { scaleValue, scaleLabel } from "../utils";

interface Props {
  spec: KpiStripSpec | null;
  scale?: Scale;
}

function fmt(value: number, unit: string, scale: Scale = "M"): string {
  if (unit === "%") return `${value.toFixed(1)}%`;
  return `${scaleLabel(scale)}${scaleValue(value, scale)}`;
}

function fmtVariance(value: number, isMargin: boolean): string {
  const sign = value > 0 ? "+" : "";
  if (isMargin) return `${sign}${value.toFixed(1)}pp`;
  return `${sign}${value.toFixed(1)}%`;
}

export function KpiStrip({ spec, scale = "M" }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  if (!spec) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5 md:gap-2 px-3 py-1.5 md:py-2.5">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-[44px] md:h-[56px] bg-white/60 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  const chevron = (
    <svg
      className={clsx("w-3.5 h-3.5 text-gray-400 transition-transform duration-200", collapsed && "rotate-180")}
      fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
    </svg>
  );

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="flex items-center gap-3 px-3 py-1.5 border-b border-gray-100 w-full text-left overflow-x-auto hover:bg-gray-50/50 transition-colors"
      >
        {spec.cards.map((card) => (
          <span key={card.label} className="text-[9px] text-gray-500 whitespace-nowrap shrink-0">
            <span className="font-medium text-az-navy">{fmt(card.value, card.unit, scale)}</span>
            {" "}
            <span className="text-[8px] uppercase tracking-wider">{card.label}</span>
          </span>
        ))}
        <span className="flex-1" />
        {chevron}
      </button>
    );
  }

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5 md:gap-2 px-3 py-1.5 md:py-2.5">
        {spec.cards.map((card) => {
          const isExpense = card.label === "Total OpEx";
          const isMargin = card.unit === "%";

          return (
            <div
              key={card.label}
              className="bg-white rounded-lg px-2.5 py-1.5 md:px-3 md:py-2.5 border border-gray-100 shadow-sm"
            >
              <div className="text-[9px] md:text-[10px] text-gray-500 font-medium uppercase tracking-wider">
                {card.label}
              </div>
              <div className="text-base md:text-lg font-semibold text-az-navy leading-tight mt-0.5">
                {fmt(card.value, card.unit, scale)}
              </div>
              <div className="flex gap-2 md:gap-3 mt-0.5 md:mt-1">
                {card.comparisons.map((c) => {
                  const good = isExpense ? c.variance_pct < 0 : c.variance_pct > 0;
                  const bad = isExpense ? c.variance_pct > 0 : c.variance_pct < 0;
                  return (
                    <span
                      key={c.label}
                      className={clsx(
                        "text-[10px] font-medium",
                        good && "text-emerald-600",
                        bad && "text-rose-500",
                        c.variance_pct === 0 && "text-gray-400"
                      )}
                    >
                      <span className="text-gray-400 font-normal">{c.label} </span>
                      {fmtVariance(c.variance_pct, isMargin)}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      <button
        onClick={() => setCollapsed(true)}
        className="flex items-center justify-center w-full py-0.5 hover:bg-gray-50 transition-colors"
        title="Collapse KPIs"
      >
        {chevron}
      </button>
    </div>
  );
}

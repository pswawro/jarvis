import clsx from "clsx";
import type { KpiStripSpec } from "../types";

interface Props {
  spec: KpiStripSpec | null;
}

function fmt(value: number, unit: string): string {
  if (unit === "%") return `${value.toFixed(1)}%`;
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}B`;
  return `$${value.toFixed(0)}M`;
}

function fmtVariance(value: number, isMargin: boolean): string {
  const sign = value > 0 ? "+" : "";
  if (isMargin) return `${sign}${value.toFixed(1)}pp`;
  return `${sign}${value.toFixed(1)}%`;
}

export function KpiStrip({ spec }: Props) {
  if (!spec) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5 md:gap-2 px-3 py-1.5 md:py-2.5">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-[44px] md:h-[56px] bg-white/60 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  return (
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
              {fmt(card.value, card.unit)}
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
  );
}

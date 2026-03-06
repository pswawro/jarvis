import { useState } from "react";
import clsx from "clsx";
import type { Filters } from "../types";

const MARKETS = [
  { id: "US", label: "United States" },
  { id: "CN", label: "China" },
];

const TAS = [
  { id: "Oncology", label: "Oncology" },
  { id: "CVRM", label: "CVRM" },
  { id: "R&I", label: "R&I" },
  { id: "Rare Disease", label: "Rare Disease" },
  { id: "V&I", label: "V&I" },
];

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
}

export function FilterBar({ filters, onChange }: Props) {
  const [open, setOpen] = useState(false);

  const hasFilters = filters.market_id.length > 0 || filters.ta.length > 0;

  function toggle(arr: string[], value: string): string[] {
    return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
  }

  // Grouped chips
  const chips: { key: string; label: string; onRemove: () => void }[] = [];
  if (filters.market_id.length) {
    const labels = filters.market_id.map(
      (id) => MARKETS.find((m) => m.id === id)?.label ?? id
    );
    chips.push({
      key: "market",
      label: `Market: ${labels.join(", ")}`,
      onRemove: () => onChange({ ...filters, market_id: [] }),
    });
  }
  if (filters.ta.length) {
    chips.push({
      key: "ta",
      label: `TA: ${filters.ta.join(", ")}`,
      onRemove: () => onChange({ ...filters, ta: [] }),
    });
  }

  return (
    <div className="relative bg-white border-b border-gray-200">
      {/* Toggle row + active chips */}
      <div className="flex items-center gap-2 px-3 py-1.5">
        <button
          onClick={() => setOpen(!open)}
          className={clsx(
            "flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-md transition-colors shrink-0",
            open || hasFilters
              ? "text-az-navy bg-blue-50"
              : "text-gray-400 hover:text-gray-600 hover:bg-gray-50"
          )}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z" />
          </svg>
          Filters
          <svg
            className={clsx("w-3 h-3 transition-transform duration-200", open && "rotate-180")}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2.5}
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </button>

        {/* Active filter chips — grouped by category */}
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {chips.map((chip) => (
            <span
              key={chip.key}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-az-navy bg-blue-50 pl-2 pr-1 py-0.5 rounded-full whitespace-nowrap"
            >
              {chip.label}
              <button
                onClick={chip.onRemove}
                className="w-4 h-4 flex items-center justify-center rounded-full hover:bg-blue-100 transition-colors"
              >
                <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </span>
          ))}
        </div>

        {hasFilters && (
          <button
            onClick={() => onChange({ market_id: [], ta: [] })}
            className="text-[10px] text-gray-400 hover:text-gray-600 ml-auto shrink-0"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Overlay filter panel */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-30"
            onClick={() => setOpen(false)}
          />
          {/* Panel — positioned absolute below the filter bar */}
          <div className="absolute left-0 right-0 z-40 bg-white border-b border-gray-200 shadow-lg px-3 pb-3 pt-1 flex flex-col sm:flex-row gap-3">
            {/* Market filter */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Market</span>
              <div className="flex flex-wrap gap-1">
                {MARKETS.map((m) => (
                  <button
                    key={m.id}
                    onClick={() =>
                      onChange({ ...filters, market_id: toggle(filters.market_id, m.id) })
                    }
                    className={clsx(
                      "px-2.5 py-1 text-[11px] font-medium rounded-md border transition-all",
                      filters.market_id.includes(m.id)
                        ? "border-az-navy bg-az-navy text-white"
                        : "border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
                    )}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </div>

            {/* TA filter */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Therapeutic Area</span>
              <div className="flex flex-wrap gap-1">
                {TAS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() =>
                      onChange({ ...filters, ta: toggle(filters.ta, t.id) })
                    }
                    className={clsx(
                      "px-2.5 py-1 text-[11px] font-medium rounded-md border transition-all",
                      filters.ta.includes(t.id)
                        ? "border-az-navy bg-az-navy text-white"
                        : "border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

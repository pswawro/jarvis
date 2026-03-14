import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import clsx from "clsx";
import type { Filters, Comparator, Scale, Granularity, DimensionConfig, LevelId, PageType } from "../types";
import { DimensionPicker } from "./DimensionPicker";

const CURRENT_YEAR = new Date().getFullYear();
const YEARS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2];

const GRANULARITIES: { id: Granularity; label: string }[] = [
  { id: "year", label: "Yearly" },
  { id: "quarter", label: "Quarterly" },
  { id: "month", label: "Monthly" },
];

const COMPARATORS: { id: Comparator; label: string }[] = [
  { id: "BUD", label: "Budget" },
  { id: "MTP", label: "MTP" },
  { id: "RBU2", label: "RBU2" },
  { id: "PYACT", label: "PY" },
];

const SCALES: { id: Scale; label: string }[] = [
  { id: "K", label: "$K" },
  { id: "M", label: "$M" },
  { id: "B", label: "$B" },
];

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

const PRODUCTS: { id: string; label: string; ta: string }[] = [
  { id: "BEYFORTUS", label: "Beyfortus", ta: "V&I" },
  { id: "BREZTRI", label: "Breztri", ta: "R&I" },
  { id: "BRILINTA", label: "Brilinta", ta: "CVRM" },
  { id: "CALQUENCE", label: "Calquence", ta: "Oncology" },
  { id: "CRESTOR", label: "Crestor", ta: "CVRM" },
  { id: "ENHERTU", label: "Enhertu", ta: "Oncology" },
  { id: "FARXIGA", label: "Farxiga", ta: "CVRM" },
  { id: "FASENRA", label: "Fasenra", ta: "R&I" },
  { id: "IMFINZI", label: "Imfinzi", ta: "Oncology" },
  { id: "KOSELUGO", label: "Koselugo", ta: "Oncology" },
  { id: "LOKELMA", label: "Lokelma", ta: "CVRM" },
  { id: "LYNPARZA", label: "Lynparza", ta: "Oncology" },
  { id: "SAPHNELO", label: "Saphnelo", ta: "R&I" },
  { id: "SOLIRIS", label: "Soliris", ta: "Rare Disease" },
  { id: "STRENSIQ", label: "Strensiq", ta: "Rare Disease" },
  { id: "SYMBICORT", label: "Symbicort", ta: "R&I" },
  { id: "TAGRISSO", label: "Tagrisso", ta: "Oncology" },
  { id: "TEZSPIRE", label: "Tezspire", ta: "R&I" },
  { id: "TRUQAP", label: "Truqap", ta: "Oncology" },
  { id: "ULTOMIRIS", label: "Ultomiris", ta: "Rare Disease" },
];

const LEVEL_LABELS: Record<LevelId, string> = {
  ta: "TA", brand: "Brand", market: "Market", region: "Region",
  unit: "Unit", sub_unit: "Sub-unit", category: "Category",
};

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
  dimConfig: DimensionConfig;
  onDimConfigChange: (d: DimensionConfig) => void;
  page: PageType;
}

export function FilterBar({ filters, onChange, dimConfig, onDimConfigChange, page }: Props) {
  const [open, setOpen] = useState(false);
  const [dimPickerOpen, setDimPickerOpen] = useState(false);
  const [productDropdownOpen, setProductDropdownOpen] = useState(false);
  const [productSearch, setProductSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  // Focus search when dropdown opens
  useEffect(() => {
    if (productDropdownOpen && searchRef.current) {
      searchRef.current.focus();
    }
    if (!productDropdownOpen) setProductSearch("");
  }, [productDropdownOpen]);

  const hasDataFilters = filters.market_id.length > 0 || filters.ta.length > 0 || filters.product.length > 0;

  function toggle(arr: string[], value: string): string[] {
    return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
  }

  const removeMarkets = useCallback(() => onChange({ ...filters, market_id: [] }), [onChange, filters]);
  const removeTas = useCallback(() => onChange({ ...filters, ta: [], product: [] }), [onChange, filters]);
  const removeProducts = useCallback(() => onChange({ ...filters, product: [] }), [onChange, filters]);

  // TAs that are relevant given selected products
  const activeTAsFromProducts = useMemo(() => {
    if (filters.product.length === 0) return null; // no constraint
    return new Set(filters.product.map((pid) => PRODUCTS.find((p) => p.id === pid)?.ta).filter(Boolean));
  }, [filters.product]);

  // Products filtered by TA selection, then by search, sorted alphabetically
  const filteredProducts = useMemo(() => {
    let list = PRODUCTS;
    if (filters.ta.length > 0) {
      const taSet = new Set(filters.ta);
      list = list.filter((p) => taSet.has(p.ta));
    }
    if (productSearch.trim()) {
      const q = productSearch.trim().toLowerCase();
      list = list.filter((p) => p.label.toLowerCase().includes(q));
    }
    return list; // already alphabetical
  }, [filters.ta, productSearch]);

  // Active filter chips — always show all settings
  const chips = useMemo(() => {
    const result: { key: string; label: string; onRemove?: () => void }[] = [];
    // Settings chips (always visible, no remove — click filter to change)
    result.push({ key: "year", label: `${filters.year}` });
    const gl = GRANULARITIES.find((g) => g.id === filters.granularity)?.label ?? filters.granularity;
    result.push({ key: "granularity", label: gl });
    const cl = COMPARATORS.find((c) => c.id === filters.comparator)?.label ?? filters.comparator;
    result.push({ key: "comparator", label: `vs ${cl}` });
    // Data filter chips (removable)
    if (filters.market_id.length) {
      const labels = filters.market_id.map(
        (id) => MARKETS.find((m) => m.id === id)?.label ?? id
      );
      result.push({ key: "market", label: `Market: ${labels.join(", ")}`, onRemove: removeMarkets });
    }
    if (filters.ta.length) {
      result.push({ key: "ta", label: `TA: ${filters.ta.join(", ")}`, onRemove: removeTas });
    }
    if (filters.product.length) {
      const labels = filters.product.map(
        (id) => PRODUCTS.find((p) => p.id === id)?.label ?? id
      );
      result.push({ key: "product", label: `Product: ${labels.join(", ")}`, onRemove: removeProducts });
    }
    return result;
  }, [filters, removeMarkets, removeTas, removeProducts]);

  const showDimensions = true;

  const clearAll = useCallback(() => {
    onChange({
      market_id: [],
      ta: [],
      product: [],
      comparator: "BUD",
      scale: "B",
      year: CURRENT_YEAR,
      granularity: "quarter",
    });
  }, [onChange]);

  return (
    <div className="relative bg-white border-b border-gray-200">
      {/* Top row */}
      <div className="flex flex-wrap items-center gap-1.5 px-3 py-1.5">
        {/* Filter button */}
        <button
          onClick={() => setOpen(!open)}
          className={clsx(
            "flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-md transition-colors shrink-0",
            open || hasDataFilters
              ? "text-az-navy bg-blue-50"
              : "text-gray-400 hover:text-gray-600 hover:bg-gray-50"
          )}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z" />
          </svg>
          <svg
            className={clsx("w-3 h-3 transition-transform duration-200", open && "rotate-180")}
            fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </button>

        {/* Active filter chips */}
        {chips.map((chip) => (
          <span
            key={chip.key}
            className={clsx(
              "inline-flex items-center gap-1 text-[11px] font-medium py-0.5 rounded-full",
              chip.onRemove
                ? "text-az-navy bg-blue-50 pl-2 pr-1"
                : "text-gray-500 bg-gray-100 px-2"
            )}
          >
            {chip.label}
            {chip.onRemove && (
              <button
                onClick={chip.onRemove}
                className="w-4 h-4 flex items-center justify-center rounded-full hover:bg-blue-100 transition-colors"
              >
                <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </span>
        ))}

        {hasDataFilters && (
          <button
            onClick={() => onChange({ ...filters, market_id: [], ta: [], product: [] })}
            className="text-[10px] text-gray-400 hover:text-gray-600"
          >
            Clear
          </button>
        )}

        <div className="flex-1 min-w-[8px]" />

        {/* Dimension + Scale group — separated from filter chips */}
        <div className="flex items-center gap-1.5 shrink-0 pl-1.5 border-l border-gray-200">
          {showDimensions && (
            <button
              onClick={() => setDimPickerOpen(!dimPickerOpen)}
              className={clsx(
                "flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold transition-all",
                dimPickerOpen ? "bg-az-navy text-white" : "bg-az-navy/90 text-white/90 hover:bg-az-navy"
              )}
            >
              {dimConfig.levels.map((l, i) => (
                <span key={l} className="flex items-center gap-1">
                  {i > 0 && <span className="text-white/50">→</span>}
                  <span>{LEVEL_LABELS[l]}</span>
                </span>
              ))}
              <svg
                className={clsx("w-3 h-3 ml-0.5 transition-transform duration-200", dimPickerOpen && "rotate-180")}
                fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
          )}

          <div className="flex bg-gray-100 rounded-md p-[2px]">
            {SCALES.map((s) => (
              <button
                key={s.id}
                onClick={() => onChange({ ...filters, scale: s.id })}
                className={clsx(
                  "px-1.5 py-0.5 text-[10px] font-semibold rounded transition-all duration-150",
                  filters.scale === s.id
                    ? "bg-white text-gray-700 shadow-sm"
                    : "text-gray-400 hover:text-gray-600"
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Dimension picker panel */}
      {dimPickerOpen && (
        <DimensionPicker
          current={dimConfig}
          onApply={(cfg) => { onDimConfigChange(cfg); setDimPickerOpen(false); }}
          onClose={() => setDimPickerOpen(false)}
        />
      )}

      {/* Unified filter panel */}
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => { setOpen(false); setProductDropdownOpen(false); }} />
          <div className="absolute left-0 right-0 z-40 bg-white border-b border-gray-200 shadow-lg px-3 pb-3 pt-1">
            <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-x-6 gap-y-3">
              {/* Year */}
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Year</span>
                <div className="flex gap-1">
                  {YEARS.map((y) => (
                    <button
                      key={y}
                      onClick={() => onChange({ ...filters, year: y })}
                      className={clsx(
                        "px-2.5 py-1 text-[11px] font-semibold rounded-md border transition-all tabular-nums",
                        filters.year === y
                          ? "border-az-navy bg-az-navy text-white"
                          : "border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
                      )}
                    >
                      {y}
                    </button>
                  ))}
                </div>
              </div>

              {/* View by */}
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">View By</span>
                <div className="flex gap-1">
                  {GRANULARITIES.map((g) => (
                    <button
                      key={g.id}
                      onClick={() => onChange({ ...filters, granularity: g.id })}
                      className={clsx(
                        "px-2.5 py-1 text-[11px] font-medium rounded-md border transition-all",
                        filters.granularity === g.id
                          ? "border-az-navy bg-az-navy text-white"
                          : "border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
                      )}
                    >
                      {g.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Comparator */}
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Comparator</span>
                <div className="flex gap-1">
                  {COMPARATORS.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => onChange({ ...filters, comparator: c.id })}
                      className={clsx(
                        "px-2.5 py-1 text-[11px] font-medium rounded-md border transition-all",
                        filters.comparator === c.id
                          ? "border-az-navy bg-az-navy text-white"
                          : "border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
                      )}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Market */}
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Market</span>
                <div className="flex flex-wrap gap-1">
                  {MARKETS.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => onChange({ ...filters, market_id: toggle(filters.market_id, m.id) })}
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

              {/* Therapeutic Area — grey out TAs not matching selected products */}
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Therapeutic Area</span>
                <div className="flex flex-wrap gap-1">
                  {TAS.map((t) => {
                    const isActive = filters.ta.includes(t.id);
                    const isGreyed = activeTAsFromProducts !== null && !activeTAsFromProducts.has(t.id) && !isActive;
                    return (
                      <button
                        key={t.id}
                        onClick={() => {
                          const newTa = toggle(filters.ta, t.id);
                          // When removing a TA, also remove products that belonged only to that TA
                          let newProducts = filters.product;
                          if (isActive && newTa.length > 0) {
                            const allowedTas = new Set(newTa);
                            newProducts = filters.product.filter((pid) => {
                              const prod = PRODUCTS.find((p) => p.id === pid);
                              return prod ? allowedTas.has(prod.ta) : false;
                            });
                          } else if (isActive && newTa.length === 0) {
                            // Removing last TA — keep all products
                          }
                          onChange({ ...filters, ta: newTa, product: newProducts });
                        }}
                        className={clsx(
                          "px-2.5 py-1 text-[11px] font-medium rounded-md border transition-all",
                          isActive
                            ? "border-az-navy bg-az-navy text-white"
                            : isGreyed
                              ? "border-gray-100 text-gray-300 cursor-default"
                              : "border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
                        )}
                      >
                        {t.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Product (searchable dropdown) */}
              <div className="flex flex-col gap-1 relative col-span-2 sm:col-span-1">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Product</span>
                <button
                  onClick={() => setProductDropdownOpen(!productDropdownOpen)}
                  className={clsx(
                    "flex items-center justify-between px-2.5 py-1 text-[11px] font-medium rounded-md border transition-all min-w-[160px] text-left",
                    filters.product.length > 0
                      ? "border-az-navy bg-blue-50 text-az-navy"
                      : "border-gray-200 text-gray-500 hover:border-gray-300"
                  )}
                >
                  <span className="truncate">
                    {filters.product.length === 0
                      ? "All products"
                      : filters.product.length === 1
                        ? PRODUCTS.find((p) => p.id === filters.product[0])?.label ?? filters.product[0]
                        : `${filters.product.length} selected`}
                  </span>
                  <svg
                    className={clsx("w-3 h-3 ml-1 shrink-0 transition-transform", productDropdownOpen && "rotate-180")}
                    fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                  </svg>
                </button>

                {productDropdownOpen && (
                  <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 w-52 max-h-[280px] flex flex-col">
                    {/* Search input */}
                    <div className="px-2 py-1.5 border-b border-gray-100">
                      <input
                        ref={searchRef}
                        type="text"
                        value={productSearch}
                        onChange={(e) => setProductSearch(e.target.value)}
                        placeholder="Search products..."
                        className="w-full px-2 py-1 text-[11px] border border-gray-200 rounded-md focus:border-az-navy focus:outline-none"
                      />
                    </div>

                    {/* Clear + product list */}
                    <div className="overflow-y-auto flex-1">
                      {filters.product.length > 0 && !productSearch && (
                        <button
                          onClick={() => onChange({ ...filters, product: [] })}
                          className="w-full px-3 py-1.5 text-[11px] text-gray-400 hover:bg-gray-50 text-left border-b border-gray-100"
                        >
                          Clear selection
                        </button>
                      )}
                      {filteredProducts.length === 0 ? (
                        <div className="px-3 py-3 text-[11px] text-gray-400 italic text-center">No matches</div>
                      ) : (
                        filteredProducts.map((p) => (
                          <button
                            key={p.id}
                            onClick={() => onChange({ ...filters, product: toggle(filters.product, p.id) })}
                            className={clsx(
                              "w-full flex items-center gap-2 px-3 py-1.5 text-[11px] font-medium text-left hover:bg-gray-50 transition-colors",
                              filters.product.includes(p.id) ? "text-az-navy" : "text-gray-600"
                            )}
                          >
                            <span className={clsx(
                              "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                              filters.product.includes(p.id)
                                ? "bg-az-navy border-az-navy"
                                : "border-gray-300"
                            )}>
                              {filters.product.includes(p.id) && (
                                <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                                </svg>
                              )}
                            </span>
                            <span className="flex-1">{p.label}</span>
                            <span className="text-[9px] text-gray-400">{p.ta}</span>
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Clear all */}
            <div className="mt-3 pt-2 border-t border-gray-100 flex justify-end">
              <button
                onClick={clearAll}
                className="text-[11px] font-medium text-gray-400 hover:text-red-500 transition-colors"
              >
                Reset all filters
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

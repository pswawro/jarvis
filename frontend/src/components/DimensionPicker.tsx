import { useState, useCallback } from "react";
import clsx from "clsx";
import type { LevelId, DimensionConfig, SavedDimension } from "../types";
import { useSavedDimensions } from "../hooks/useSavedDimensions";

const ALL_LEVELS: { id: LevelId; label: string; domain: string }[] = [
  { id: "ta", label: "Therapeutic Area", domain: "revenue" },
  { id: "brand", label: "Brand", domain: "revenue" },
  { id: "market", label: "Market", domain: "revenue" },
  { id: "region", label: "Region", domain: "revenue" },
  { id: "unit", label: "Unit", domain: "expense" },
  { id: "sub_unit", label: "Sub-unit", domain: "expense" },
  { id: "category", label: "Category", domain: "competitive" },
];

const LEVEL_LABELS: Record<LevelId, string> = {
  ta: "TA", brand: "Brand", market: "Market", region: "Region",
  unit: "Unit", sub_unit: "Sub-unit", category: "Category",
};

function getDomain(levels: LevelId[]): string | null {
  if (levels.length === 0) return null;
  const first = ALL_LEVELS.find((l) => l.id === levels[0]);
  return first?.domain ?? null;
}

interface Props {
  current: DimensionConfig;
  onApply: (config: DimensionConfig) => void;
  onClose: () => void;
}

export function DimensionPicker({ current, onApply, onClose }: Props) {
  const [draft, setDraft] = useState<LevelId[]>([...current.levels]);
  const [saveName, setSaveName] = useState("");
  const [showSaveInput, setShowSaveInput] = useState(false);
  const { saved, save, remove } = useSavedDimensions();

  const domain = getDomain(draft);
  const available = ALL_LEVELS.filter(
    (l) => !draft.includes(l.id) && (domain === null || l.domain === domain)
  );

  const addLevel = useCallback((id: LevelId) => {
    setDraft((prev) => [...prev, id]);
  }, []);

  const removeLevel = useCallback((idx: number) => {
    setDraft((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const cycleLevel = useCallback((idx: number, direction: -1 | 1) => {
    setDraft((prev) => {
      // Single level: cycle through ALL levels (across domains)
      if (prev.length === 1) {
        const allIds = ALL_LEVELS.map((l) => l.id);
        const curIdx = allIds.indexOf(prev[0]);
        const nextIdx = (curIdx + direction + allIds.length) % allIds.length;
        return [allIds[nextIdx]];
      }
      // Multiple levels: reorder within list
      const swapIdx = idx + direction;
      if (swapIdx < 0 || swapIdx >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[swapIdx]] = [next[swapIdx], next[idx]];
      return next;
    });
  }, []);

  const handleApply = useCallback(() => {
    if (draft.length === 0) return;
    onApply({ levels: draft });
    onClose();
  }, [draft, onApply, onClose]);

  const handleSave = useCallback(() => {
    if (!saveName.trim() || draft.length === 0) return;
    save(saveName.trim(), draft);
    setSaveName("");
    setShowSaveInput(false);
  }, [saveName, draft, save]);

  const handleApplySaved = useCallback((s: SavedDimension) => {
    onApply({ levels: [...s.levels], label: s.label });
    onClose();
  }, [onApply, onClose]);

  return (
    <>
      <div className="fixed inset-0 z-30" onClick={onClose} />
      <div className="absolute left-0 right-0 z-40 bg-white border-b border-gray-200 shadow-lg px-3 pb-3 pt-2">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Saved configurations */}
          <div className="flex flex-col gap-1.5 min-w-[160px]">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Saved</span>
            {saved.length === 0 ? (
              <span className="text-[11px] text-gray-400 italic">None yet</span>
            ) : (
              <div className="flex flex-wrap gap-1">
                {saved.map((s) => (
                  <div key={s.id} className="flex items-center gap-0.5">
                    <button
                      onClick={() => handleApplySaved(s)}
                      className={clsx(
                        "px-2 py-1 text-[11px] font-medium rounded-l-md border transition-all",
                        s.levels.join(",") === current.levels.join(",")
                          ? "border-az-navy bg-az-navy text-white"
                          : "border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50"
                      )}
                      title={s.levels.map((l) => LEVEL_LABELS[l]).join(" → ")}
                    >
                      {s.label}
                    </button>
                    <button
                      onClick={() => remove(s.id)}
                      className="px-1 py-1 text-[11px] border border-l-0 border-gray-200 rounded-r-md text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Level builder */}
          <div className="flex-1 flex flex-col gap-1.5">
            <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Drill Hierarchy</span>

            {/* Current levels */}
            <div className="flex flex-wrap gap-1 min-h-[28px]">
              {draft.map((lv, i) => (
                <div key={lv} className="flex items-center gap-0.5">
                  {i > 0 && <span className="text-[10px] text-gray-300 mx-0.5">→</span>}
                  <span className="inline-flex items-center gap-0.5 bg-blue-50 text-az-navy text-[11px] font-medium pl-2 pr-0.5 py-0.5 rounded-md">
                    {LEVEL_LABELS[lv]}
                    <button onClick={() => cycleLevel(i, -1)} className="p-0.5 hover:bg-blue-100 rounded" title={draft.length === 1 ? "Previous level" : "Move left"}>
                      <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                      </svg>
                    </button>
                    <button onClick={() => cycleLevel(i, 1)} className="p-0.5 hover:bg-blue-100 rounded" title={draft.length === 1 ? "Next level" : "Move right"}>
                      <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                      </svg>
                    </button>
                    <button onClick={() => removeLevel(i)} className="p-0.5 hover:bg-red-100 rounded text-gray-400 hover:text-red-500" title="Remove">
                      <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </span>
                </div>
              ))}
              {draft.length === 0 && (
                <span className="text-[11px] text-gray-400 italic py-0.5">Pick levels below to build hierarchy</span>
              )}
            </div>

            {/* Available levels */}
            {available.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {available.map((l) => (
                  <button
                    key={l.id}
                    onClick={() => addLevel(l.id)}
                    className="px-2 py-0.5 text-[11px] font-medium rounded-md border border-dashed border-gray-300 text-gray-500 hover:border-gray-400 hover:text-gray-700 hover:bg-gray-50 transition-all"
                  >
                    + {l.label}
                  </button>
                ))}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-2 mt-1">
              <button
                onClick={handleApply}
                disabled={draft.length === 0}
                className="px-3 py-1 text-[11px] font-semibold rounded-md bg-az-navy text-white hover:bg-az-navy/90 disabled:opacity-40 transition-colors"
              >
                Apply
              </button>
              <button
                onClick={() => setDraft(["ta", "brand", "market"])}
                className="px-2 py-1 text-[11px] font-medium text-gray-400 hover:text-gray-600 transition-colors"
              >
                Reset
              </button>
              {showSaveInput ? (
                <div className="flex items-center gap-1">
                  <input
                    type="text"
                    value={saveName}
                    onChange={(e) => setSaveName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSave()}
                    placeholder="Name..."
                    className="px-2 py-0.5 text-[11px] border border-gray-300 rounded-md w-28 focus:border-az-navy focus:outline-none"
                    autoFocus
                  />
                  <button
                    onClick={handleSave}
                    disabled={!saveName.trim() || draft.length === 0}
                    className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 transition-colors"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => { setShowSaveInput(false); setSaveName(""); }}
                    className="text-[11px] text-gray-400 hover:text-gray-600"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowSaveInput(true)}
                  disabled={draft.length === 0}
                  className="px-2 py-1 text-[11px] font-medium text-gray-500 hover:text-gray-700 disabled:opacity-40 transition-colors"
                >
                  Save as...
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

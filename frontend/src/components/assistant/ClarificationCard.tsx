import { useState } from "react";
import type { Clarification } from "../../types";

export function ClarificationCard({ clarification, onSelect, disabled }: { clarification: Clarification; onSelect: (opt: string) => void; disabled: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [freeText, setFreeText] = useState("");

  const handleClick = (opt: string) => {
    if (disabled || selected) return;
    setSelected(opt);
    onSelect(opt);
  };

  const handleFreeSubmit = () => {
    if (disabled || selected || !freeText.trim()) return;
    setSelected(freeText.trim());
    onSelect(freeText.trim());
  };

  return (
    <div className="space-y-2">
      <div className="text-[13px] font-medium text-gray-700">{clarification.question}</div>
      <div className="flex flex-col gap-1.5">
        {clarification.options.map((opt) => (
          <button
            key={opt}
            onClick={() => handleClick(opt)}
            disabled={disabled || !!selected}
            className={`text-left px-3 py-2 rounded-lg text-[13px] border transition-all ${
              selected === opt
                ? "border-az-navy bg-az-navy/10 text-az-navy font-medium"
                : selected
                  ? "border-gray-100 text-gray-300 cursor-default"
                  : "border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50 active:bg-gray-100"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
      {!disabled && !selected && (
        <div className="flex gap-1.5 mt-1">
          <input
            type="text"
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleFreeSubmit(); }}
            placeholder="Or type your own answer..."
            className="flex-1 px-3 py-1.5 text-[12px] border border-gray-200 rounded-lg focus:border-az-navy focus:outline-none"
          />
          <button
            onClick={handleFreeSubmit}
            disabled={!freeText.trim()}
            className="px-3 py-1.5 text-[12px] font-medium text-white bg-az-navy rounded-lg disabled:opacity-30 hover:bg-az-navy/90 transition-colors"
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
}

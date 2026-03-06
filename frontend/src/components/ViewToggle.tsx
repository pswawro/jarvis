import clsx from "clsx";

export type ViewMode = "table" | "trend" | "treemap";

interface Props {
  mode: ViewMode;
  onToggle: (m: ViewMode) => void;
}

const LABELS: Record<ViewMode, string> = {
  table: "Table",
  treemap: "Chart",
  trend: "Trend",
};

export function ViewToggle({ mode, onToggle }: Props) {
  return (
    <div className="flex bg-gray-100 rounded-md p-0.5">
      {(["table", "treemap", "trend"] as const).map((m) => (
        <button
          key={m}
          onClick={() => onToggle(m)}
          className={clsx(
            "px-3 py-1 text-[11px] font-medium rounded transition-all duration-150",
            mode === m
              ? "bg-white text-az-navy shadow-sm"
              : "text-gray-400 hover:text-gray-600"
          )}
        >
          {LABELS[m]}
        </button>
      ))}
    </div>
  );
}

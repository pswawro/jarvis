import type { Period } from "../types";

interface Props {
  period: Period;
  onPeriodChange: (p: Period) => void;
  onAssistantOpen?: () => void;
}

const YEARS = [2025, 2024, 2023];
const QUARTERS = [null, "Q1", "Q2", "Q3", "Q4"];

export function TopBar({ period, onPeriodChange, onAssistantOpen }: Props) {
  return (
    <header className="bg-az-navy">
      {/* Top row: brand + year */}
      <div className="flex items-center justify-between px-4 pt-3 pb-1.5 sm:pb-3 sm:pt-3.5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-white/95 to-white/80 flex items-center justify-center shadow-sm shadow-black/20">
            <span className="text-az-navy text-sm font-extrabold leading-none">J</span>
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-white text-[15px] tracking-tight leading-none">Jarvis</span>
            <span className="text-[10px] text-white/30 font-medium tracking-[0.15em] uppercase mt-0.5 leading-none">AstraZeneca</span>
          </div>
        </div>

        {/* Desktop: all controls in one row */}
        <div className="hidden sm:flex items-center gap-2">
          {onAssistantOpen && (
            <button
              onClick={onAssistantOpen}
              className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
              title="Ask Jarvis"
            >
              <svg className="w-4 h-4 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
              </svg>
            </button>
          )}
          <div className="flex bg-white/[0.06] rounded-lg p-[3px]">
            {YEARS.map((y) => (
              <button
                key={y}
                onClick={() => onPeriodChange({ ...period, year: y })}
                className={`px-3 py-1 text-[12px] font-semibold rounded-md transition-all duration-150 tabular-nums ${
                  period.year === y
                    ? "bg-white text-az-navy shadow-sm"
                    : "text-white/35 hover:text-white/60"
                }`}
              >
                {y}
              </button>
            ))}
          </div>

          <div className="w-px h-5 bg-white/10" />

          <div className="flex bg-white/[0.06] rounded-lg p-[3px]">
            {QUARTERS.map((q) => (
              <button
                key={q ?? "FY"}
                onClick={() => onPeriodChange({ ...period, quarter: q })}
                className={`px-2.5 py-1 text-[12px] font-medium rounded-md transition-all duration-150 ${
                  period.quarter === q
                    ? "bg-white text-az-navy shadow-sm"
                    : "text-white/35 hover:text-white/60"
                }`}
              >
                {q ?? "FY"}
              </button>
            ))}
          </div>
        </div>

        {/* Mobile: year + assistant icon */}
        <div className="flex sm:hidden items-center gap-2">
          {onAssistantOpen && (
            <button
              onClick={onAssistantOpen}
              className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
              title="Ask Jarvis"
            >
              <svg className="w-4 h-4 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
              </svg>
            </button>
          )}
          <div className="flex bg-white/[0.06] rounded-lg p-[3px]">
            {YEARS.map((y) => (
              <button
                key={y}
                onClick={() => onPeriodChange({ ...period, year: y })}
                className={`px-2.5 py-1 text-[12px] font-semibold rounded-md transition-all duration-150 tabular-nums ${
                  period.year === y
                    ? "bg-white text-az-navy shadow-sm"
                    : "text-white/35 hover:text-white/60"
                }`}
              >
                {y}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Mobile: quarter row */}
      <div className="flex sm:hidden justify-center px-4 pb-2.5">
        <div className="flex bg-white/[0.06] rounded-lg p-[3px]">
          {QUARTERS.map((q) => (
            <button
              key={q ?? "FY"}
              onClick={() => onPeriodChange({ ...period, quarter: q })}
              className={`px-3.5 py-1 text-[12px] font-medium rounded-md transition-all duration-150 ${
                period.quarter === q
                  ? "bg-white text-az-navy shadow-sm"
                  : "text-white/35 hover:text-white/60"
              }`}
            >
              {q ?? "FY"}
            </button>
          ))}
        </div>
      </div>

      <div className="h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
    </header>
  );
}

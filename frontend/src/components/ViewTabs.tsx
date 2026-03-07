import clsx from "clsx";

interface Props {
  activeIndex: number;
  onSwitch: (index: number) => void;
}

const TABS = [
  { label: "Overview", subtitle: "Performance Summary" },
  { label: "Landing", subtitle: "Actuals + Forecast" },
  { label: "Phased", subtitle: "Scenario Comparison" },
];

export function ViewTabs({ activeIndex, onSwitch }: Props) {
  return (
    <>
      {/* Desktop tabs */}
      <div className="hidden md:flex border-b border-gray-200 bg-white">
        {TABS.map((tab, i) => (
          <button
            key={tab.label}
            onClick={() => onSwitch(i)}
            className={clsx(
              "flex-1 py-2.5 text-sm font-medium border-b-2 transition-all duration-200",
              i === activeIndex
                ? "border-az-navy text-az-navy"
                : "border-transparent text-gray-400 hover:text-gray-600"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Mobile pill indicators */}
      <div className="flex md:hidden justify-center items-center gap-1.5 py-2.5 bg-white border-b border-gray-200">
        {TABS.map((tab, i) => (
          <button
            key={tab.label}
            onClick={() => onSwitch(i)}
            className={clsx(
              "flex items-center gap-1.5 transition-all duration-200",
              i === activeIndex && "px-3 py-1 rounded-full bg-gray-100"
            )}
          >
            <span
              className={clsx(
                "rounded-full transition-all duration-200",
                i === activeIndex
                  ? "w-1.5 h-1.5 bg-az-navy"
                  : "w-2 h-2 bg-gray-300"
              )}
            />
            {i === activeIndex && (
              <span className="text-xs font-medium text-az-navy">
                {tab.label}
              </span>
            )}
          </button>
        ))}
      </div>
    </>
  );
}

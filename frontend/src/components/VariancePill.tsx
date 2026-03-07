import { memo } from "react";
import clsx from "clsx";

interface Props {
  value: number;
  invertColor?: boolean;
  suffix?: string;
}

export const VariancePill = memo(function VariancePill({ value, invertColor, suffix = "%" }: Props) {
  const isPositive = value > 0;
  const isNeutral = value === 0;
  const isGood = invertColor ? value < 0 : value > 0;
  const isBad = invertColor ? value > 0 : value < 0;

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-0.5 text-[11px] font-medium tabular-nums whitespace-nowrap shrink-0 w-[72px] justify-end",
        isNeutral && "text-gray-400",
        isGood && "text-emerald-600",
        isBad && "text-rose-500"
      )}
    >
      {!isNeutral && (
        <span className="text-[7px] leading-none opacity-70">
          {isPositive ? "\u25B2" : "\u25BC"}
        </span>
      )}
      {isPositive ? "+" : ""}
      {value.toFixed(1)}{suffix}
    </span>
  );
});

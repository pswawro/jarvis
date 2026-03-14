import { memo, useId, useMemo } from "react";

interface Props {
  data: number[];
  width?: number;
  height?: number;
}

export const Sparkline = memo(function Sparkline({ data, width = 64, height = 28 }: Props) {
  const id = useId();
  const computed = useMemo(() => {
    if (data.length < 2) return null;

    const min = data.reduce((a, b) => Math.min(a, b), Infinity);
    const max = data.reduce((a, b) => Math.max(a, b), -Infinity);
    const range = max - min || 1;
    const padX = 2;
    const padY = 3;

    const coords = data.map((v, i) => {
      const x = padX + (i / (data.length - 1)) * (width - padX * 2);
      const y = padY + (height - padY * 2) - ((v - min) / range) * (height - padY * 2);
      return { x, y };
    });

    const linePoints = coords.map((c) => `${c.x},${c.y}`).join(" ");

    const areaPath = [
      `M ${coords[0].x},${height - 1}`,
      `L ${coords.map((c) => `${c.x},${c.y}`).join(" L ")}`,
      `L ${coords[coords.length - 1].x},${height - 1}`,
      "Z",
    ].join(" ");

    const up = data[data.length - 1] >= data[0];
    const lineColor = up ? "#059669" : "#e11d48";
    const fillColor = up ? "#059669" : "#e11d48";
    const last = coords[coords.length - 1];

    return { linePoints, areaPath, up, lineColor, fillColor, last };
  }, [data, width, height]);

  if (!computed) return null;
  const { linePoints, areaPath, up, lineColor, fillColor, last } = computed;

  return (
    <svg width={width} height={height} className="shrink-0">
      <defs>
        <linearGradient id={`spark-${id}-${up ? "up" : "dn"}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fillColor} stopOpacity="0.15" />
          <stop offset="100%" stopColor={fillColor} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#spark-${id}-${up ? "up" : "dn"})`} />
      <polyline
        fill="none"
        stroke={lineColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={linePoints}
      />
      <circle cx={last.x} cy={last.y} r="2" fill={lineColor} />
    </svg>
  );
});

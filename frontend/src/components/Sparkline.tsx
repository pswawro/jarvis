interface Props {
  data: number[];
  width?: number;
  height?: number;
}

export function Sparkline({ data, width = 64, height = 28 }: Props) {
  if (!data.length) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padX = 2;
  const padY = 3;

  const coords = data.map((v, i) => {
    const x = padX + (i / (data.length - 1)) * (width - padX * 2);
    const y = padY + (height - padY * 2) - ((v - min) / range) * (height - padY * 2);
    return { x, y };
  });

  const linePoints = coords.map((c) => `${c.x},${c.y}`).join(" ");

  // Closed path for the area fill
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

  return (
    <svg width={width} height={height} className="shrink-0">
      <defs>
        <linearGradient id={`spark-${up ? "up" : "dn"}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fillColor} stopOpacity="0.15" />
          <stop offset="100%" stopColor={fillColor} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#spark-${up ? "up" : "dn"})`} />
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
}

import type { Visual } from "../../types";

function VisualIcon({ visual, onClick }: { visual: Visual; onClick: () => void }) {
  const icon = visual.tool === "render_table" ? "\ud83d\udcca" : visual.tool === "decompose_variance" ? "\ud83d\udd0d" : "\ud83d\udcc8";
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-gray-100 hover:bg-gray-200 text-[11px] text-gray-600 transition-colors"
      title={visual.title}
    >
      <span>{icon}</span>
      <span>{visual.title}</span>
    </button>
  );
}

function TableVisual({ visual }: { visual: Visual }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-gray-200">
            {visual.headers!.map((h, i) => (
              <th key={i} className="text-left py-2 px-2 font-semibold text-gray-600">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visual.rows!.map((row, ri) => (
            <tr key={ri} className="border-b border-gray-50">
              {(Array.isArray(row) ? row : []).map((cell, ci) => (
                <td key={ci} className="py-1.5 px-2 text-gray-700">{String(cell ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartVisual({ visual }: { visual: Visual }) {
  const labels = visual.labels || [];
  return (
    <div className="space-y-4">
      {visual.datasets!.map((ds, di) => {
        const vals = Array.isArray(ds.values) ? ds.values.map(Number) : [];
        const max = vals.length > 0 ? vals.reduce((a, b) => Math.max(a, b), 0) : 0;
        const barH = 96;
        return (
          <div key={di}>
            <div className="text-[11px] text-gray-500 mb-1">{ds.name}</div>
            <div className="flex items-end gap-1" style={{ height: barH + 20 }}>
              {vals.map((v, vi) => {
                const h = max > 0 ? (v / max) * barH : 0;
                return (
                  <div key={vi} className="flex-1 flex flex-col items-center justify-end">
                    <div className="text-[9px] text-gray-500 mb-0.5">
                      {typeof v === "number" ? (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v % 1 === 0 ? v : v.toFixed(1)) : v}
                    </div>
                    <div
                      className="w-full rounded-t"
                      style={{
                        height: Math.max(h, v > 0 ? 2 : 0),
                        backgroundColor: ds.color || "#003366",
                      }}
                    />
                    <span className="text-[8px] text-gray-400 truncate w-full text-center mt-0.5">
                      {labels[vi] ?? ""}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function VarianceVisual({ visual }: { visual: Visual }) {
  const factors = visual.factors!;
  const totalVal = visual.total_value || 0;
  const maxAbs = factors.reduce((m, f) => Math.max(m, Math.abs(f.value)), Math.abs(totalVal));
  const vUnit = visual.unit || "$M";
  const maxBarW = 180;

  const fmtVal = (v: number) => `${v >= 0 ? "+" : ""}${Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1)}${vUnit}`;

  return (
    <div className="space-y-1">
      {factors.map((f, i) => {
        const w = maxAbs > 0 ? (Math.abs(f.value) / maxAbs) * maxBarW : 0;
        const isPositive = f.value >= 0;
        return (
          <div key={i} className="flex items-center gap-2">
            <div className="w-[90px] shrink-0 text-right text-[11px] text-gray-600 truncate">{f.label}</div>
            <div className="flex-1 flex items-center" style={{ minHeight: 24 }}>
              <div
                className="rounded-sm h-[18px]"
                style={{
                  width: Math.max(w, 3),
                  backgroundColor: isPositive ? "#22c55e" : "#ef4444",
                }}
              />
              <span className={`ml-1.5 text-[10px] font-medium whitespace-nowrap ${isPositive ? "text-green-700" : "text-red-700"}`}>
                {fmtVal(f.value)}
              </span>
            </div>
          </div>
        );
      })}
      <div className="flex items-center gap-2 border-t border-gray-200 pt-1.5 mt-1.5">
        <div className="w-[90px] shrink-0 text-right text-[11px] font-semibold text-gray-800">{visual.total_label}</div>
        <div className="flex-1 flex items-center" style={{ minHeight: 24 }}>
          <div
            className="rounded-sm h-[18px]"
            style={{
              width: Math.max(maxAbs > 0 ? (Math.abs(totalVal) / maxAbs) * maxBarW : 0, 3),
              backgroundColor: totalVal >= 0 ? "#003366" : "#991b1b",
            }}
          />
          <span className={`ml-1.5 text-[10px] font-bold whitespace-nowrap ${totalVal >= 0 ? "text-gray-800" : "text-red-800"}`}>
            {fmtVal(totalVal)}
          </span>
        </div>
      </div>
      {factors.some((f) => f.detail) && (
        <div className="space-y-0.5 pt-2 border-t border-gray-100 mt-2">
          {factors.filter((f) => f.detail).map((f, i) => (
            <div key={i} className="text-[10px] text-gray-500">
              <span className="font-medium text-gray-600">{f.label}:</span> {f.detail}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function VisualContent({ visual }: { visual: Visual }) {
  if (visual.tool === "render_table" && visual.headers && visual.rows) {
    return <TableVisual visual={visual} />;
  }
  if (visual.tool === "render_chart" && visual.datasets) {
    return <ChartVisual visual={visual} />;
  }
  if (visual.tool === "decompose_variance" && visual.factors) {
    return <VarianceVisual visual={visual} />;
  }
  return null;
}

function VisualOverlay({ visual, onClose }: { visual: Visual; onClose: () => void }) {

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[70vh] overflow-auto p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-800">{visual.title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <VisualContent visual={visual} />
      </div>
    </div>
  );
}

export { VisualIcon, VisualOverlay };

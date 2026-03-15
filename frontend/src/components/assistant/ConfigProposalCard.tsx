import type { ConfigProposal } from "../../types";

const COMPARATOR_LABELS: Record<string, string> = { BUD: "Budget", MTP: "Mid-Term Plan", RBU2: "Reforecast", PYACT: "Prior Year" };
const PAGE_LABELS: Record<string, string> = { overview: "Overview", landing: "Landing", trend: "Trend", scenarios: "Scenarios" };
const DIM_LABELS: Record<string, string> = { brand: "Brand", region: "Region", unit: "Unit", market: "Market" };
const LEVEL_LABELS: Record<string, string> = { ta: "TA", brand: "Brand", market: "Market", region: "Region", unit: "Unit", sub_unit: "Sub-unit", category: "Category" };
const PRESET_LABELS: Record<string, string> = { all: "All Scenarios", bud: "ACT vs Budget", mtp: "ACT vs MTP", rbu2: "ACT vs RBU2", py: "ACT vs PY", bud_mtp: "ACT vs BUD & MTP", bud_py: "ACT vs BUD & PY" };

export function ConfigProposalCard({ proposal, onApply, applied }: { proposal: ConfigProposal; onApply: () => void; applied: boolean }) {
  const changes: string[] = [];
  if (proposal.comparator) changes.push(`Comparator: ${COMPARATOR_LABELS[proposal.comparator] || proposal.comparator}`);
  if (proposal.page) changes.push(`Page: ${PAGE_LABELS[proposal.page] || proposal.page}`);
  if (proposal.levels?.length) changes.push(`Levels: ${proposal.levels.map((l) => LEVEL_LABELS[l] || l).join(" \u2192 ")}`);
  else if (proposal.dimension) changes.push(`Dimension: ${DIM_LABELS[proposal.dimension] || proposal.dimension}`);
  if (proposal.market_id?.length) changes.push(`Market: ${proposal.market_id.join(", ")}`);
  if (proposal.ta?.length) changes.push(`TA: ${proposal.ta.join(", ")}`);
  if (proposal.year) changes.push(`Year: ${proposal.year}`);
  if (proposal.quarter) changes.push(`Quarter: ${proposal.quarter}`);
  if (proposal.scale) changes.push(`Scale: $${proposal.scale}`);
  if (proposal.scenario_preset) changes.push(`Scenario: ${PRESET_LABELS[proposal.scenario_preset] || proposal.scenario_preset}`);

  return (
    <div className="rounded-lg border border-az-navy/20 bg-az-navy/5 p-3 space-y-2">
      <div className="text-[13px] text-gray-700 font-medium">{proposal.summary}</div>
      {changes.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {changes.map((c) => (
            <span key={c} className="inline-flex px-2 py-0.5 rounded-full bg-white text-[11px] text-gray-600 border border-gray-200">
              {c}
            </span>
          ))}
        </div>
      )}
      <button
        onClick={onApply}
        disabled={applied}
        className={`w-full py-2 rounded-lg text-[13px] font-semibold transition-all ${
          applied
            ? "bg-green-100 text-green-700 cursor-default"
            : "bg-az-navy text-white hover:bg-az-navy/90 active:scale-[0.98]"
        }`}
      >
        {applied ? "Applied" : "Apply to Dashboard"}
      </button>
    </div>
  );
}

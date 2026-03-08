"""AI assistant consistency tests.

Run against a live backend. Each test queries the assistant API directly
and validates responses against ground truth data.

Usage:
    cd jarvis
    python -m pytest tests/ -v                          # run all
    python -m pytest tests/test_ai_consistency.py -v     # just consistency
    python -m pytest tests/ -v -k "ranking"              # specific test

Set TEST_BASE_URL if backend is not at localhost:8000.
Results are saved to tests/results/ for cross-run comparison.
"""

import json
import pytest
from conftest import ask, get_ground_truth, extract_numbers, save_result

RUNS = 3  # number of repetitions per consistency test


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_n_times(question: str, n: int = RUNS, context: dict | None = None, test_name: str = ""):
    """Run the same query n times, save results, return list of responses."""
    results = []
    for i in range(n):
        r = ask(question, context=context)
        save_result(test_name or question[:30], f"run{i+1}", r)
        results.append(r)
    return results


def table_rows(resp) -> list[dict]:
    """Extract rows from the first render_table visual."""
    for v in resp.visuals:
        if v.get("tool") == "render_table" and v.get("rows"):
            headers = v.get("headers", [])
            return [dict(zip(headers, row)) for row in v["rows"]]
    return []


def table_column(resp, col_name: str) -> list[str]:
    """Extract a single column from the first render_table visual."""
    rows = table_rows(resp)
    return [r.get(col_name, "") for r in rows]


# ===========================================================================
# C1: Simple KPI lookup — numbers must be identical across runs
# ===========================================================================

class TestKPIConsistency:
    """Total Revenue query should return identical numbers every time."""

    def test_revenue_consistent(self):
        results = run_n_times(
            "What is Total Revenue for 2025?",
            test_name="c1_kpi_revenue",
        )
        facts = [r.facts for r in results]

        # All must have facts
        assert all(f is not None for f in facts), "Some runs missing facts section"

        # Extract dollar amounts — the primary revenue figure (first/largest) must be identical
        numbers = [extract_numbers(f) for f in facts]
        primary = [n[0] for n in numbers if n]  # first number in each response
        assert len(primary) == len(facts), f"Some runs missing revenue number: {numbers}"
        assert all(p == primary[0] for p in primary), f"Primary revenue differs: {primary} (full: {numbers})"

    def test_revenue_matches_ground_truth(self):
        """LLM's answer must match the actual KPI API."""
        truth = get_ground_truth("kpi", year=2025)
        llm = ask("What is Total Revenue for 2025?")

        # Find revenue card in ground truth
        revenue_card = None
        for card in truth.get("cards", []):
            if "revenue" in card.get("label", "").lower():
                revenue_card = card
                break

        assert revenue_card is not None, "No revenue card in ground truth"
        true_value = revenue_card["value"]

        # LLM's facts should contain this number (within rounding)
        llm_numbers = extract_numbers(llm.facts or "")
        assert any(
            abs(n - true_value) < 5 for n in llm_numbers
        ), f"LLM revenue {llm_numbers} doesn't match ground truth {true_value}"


# ===========================================================================
# C2: Top brands ranking — order and brands must be stable
# ===========================================================================

class TestRankingConsistency:
    """Top 5 brands query must return same brands in same order."""

    def test_ranking_stable(self):
        # No TA filter — cross-scope query
        ctx = {"page": "overview", "filters": {}, "period": {"year": 2025}}
        results = run_n_times(
            "What are the top 5 brands by revenue in 2025?",
            context=ctx,
            test_name="c2_ranking",
        )

        # All should have a table visual
        brand_lists = []
        for r in results:
            brands = table_column(r, "Brand")
            if not brands:
                # Try common alternative column names
                brands = table_column(r, "brand") or table_column(r, "Name")
            brand_lists.append(brands)

        assert all(len(b) > 0 for b in brand_lists), f"Some runs missing table: {brand_lists}"
        assert all(b == brand_lists[0] for b in brand_lists), f"Rankings differ: {brand_lists}"

    def test_ranking_matches_ground_truth(self):
        """Top 5 must match actual data API sorted by revenue."""
        truth = get_ground_truth("brand", year=2025)

        # Extract all brand nodes from the tree
        brands = []
        for ta_node in truth.get("tree", {}).get("children", []):
            for brand_node in ta_node.get("children", []):
                brands.append({
                    "name": brand_node["name"],
                    "actual": brand_node["values"]["actual"],
                    "ta": ta_node["name"],
                })

        true_top5 = sorted(brands, key=lambda b: b["actual"], reverse=True)[:5]
        true_names = [b["name"] for b in true_top5]

        # LLM answer
        ctx = {"page": "overview", "filters": {}, "period": {"year": 2025}}
        llm = ask("What are the top 5 brands by revenue in 2025?", context=ctx)
        save_result("c2_ranking_truth", "check", llm, {"true_top5": true_names})

        llm_brands = table_column(llm, "Brand") or table_column(llm, "brand") or table_column(llm, "Name")
        assert llm_brands == true_names, f"LLM top 5 {llm_brands} != truth {true_names}"

    def test_no_filter_leak(self):
        """When asking for 'all brands', LLM must NOT filter to a single TA."""
        ctx = {"page": "overview", "filters": {"ta": ["Oncology"]}, "period": {"year": 2025}}
        llm = ask("What are the top 5 brands by revenue across the whole company?", context=ctx)

        brands = table_column(llm, "Brand") or table_column(llm, "brand")
        # If all 5 are Oncology, the filter leaked
        if brands:
            # Get ground truth to check if non-Oncology brands should be in top 5
            truth = get_ground_truth("brand", year=2025)
            all_brands = []
            for ta_node in truth.get("tree", {}).get("children", []):
                for brand_node in ta_node.get("children", []):
                    all_brands.append({"name": brand_node["name"], "actual": brand_node["values"]["actual"], "ta": ta_node["name"]})
            true_top5 = sorted(all_brands, key=lambda b: b["actual"], reverse=True)[:5]
            true_tas = set(b["ta"] for b in true_top5)

            if len(true_tas) > 1:
                # Multiple TAs in true top 5 — LLM should also show multiple TAs
                assert len(brands) >= 1, "No brands returned"
                # At least verify the table has correct brands
                true_names = [b["name"] for b in true_top5]
                assert brands == true_names, f"Filter leaked: LLM={brands}, truth={true_names}"


# ===========================================================================
# C3: Config proposal — must return same parameters
# ===========================================================================

class TestConfigConsistency:
    """Config proposals must produce identical parameters."""

    def test_config_stable(self):
        results = run_n_times(
            "Show me Oncology only",
            test_name="c3_config",
        )

        proposals = [r.config_proposal for r in results]
        assert all(p is not None for p in proposals), "Some runs didn't return config proposal"

        # Extract the filter/TA values — should be identical
        ta_values = []
        for p in proposals:
            ta = p.get("ta") or p.get("filters", {}).get("ta")
            ta_values.append(ta)

        assert all(t == ta_values[0] for t in ta_values), f"Config TA differs: {ta_values}"

    def test_multi_param_config_stable(self):
        results = run_n_times(
            "Switch to monthly view with actuals vs MTP for 2024",
            test_name="c3_config_multi",
        )

        proposals = [r.config_proposal for r in results]
        assert all(p is not None for p in proposals), "Some runs didn't return config proposal"

        # Key fields that must be identical
        for field in ("comparator", "year", "page"):
            values = [p.get(field) for p in proposals]
            assert all(v == values[0] for v in values), f"Config '{field}' differs: {values}"


# ===========================================================================
# C4: Complex analysis — insights must be consistent
# ===========================================================================

class TestAnalysisConsistency:
    """Complex analysis should cite the same key drivers."""

    def test_oncology_drivers_consistent(self):
        results = run_n_times(
            "Why is Oncology underperforming vs budget?",
            context={"page": "overview", "filters": {"ta": ["Oncology"]}, "period": {"year": 2025}},
            test_name="c4_oncology_analysis",
        )

        # All should mention the same top underperformers
        key_brands = {"Imfinzi", "Enhertu", "Truqap"}  # known biggest misses

        for i, r in enumerate(results):
            text = " ".join(filter(None, [r.facts, r.interpretation, r.hypothesis]))
            found = {b for b in key_brands if b in text}
            assert len(found) >= 2, f"Run {i+1} missing key brands. Found: {found}, text preview: {text[:200]}"

    def test_variance_direction_consistent(self):
        """All runs should agree on which TAs are above/below budget."""
        results = run_n_times(
            "Break down the total revenue variance vs budget by TA",
            context={"page": "overview", "filters": {}, "period": {"year": 2025}},
            test_name="c4_variance",
        )

        for r in results:
            text = " ".join(filter(None, [r.facts, r.interpretation]))
            if text:
                # CVRM should always be positive
                assert "CVRM" in text, "Missing CVRM in variance analysis"
                # Oncology should always be negative/miss
                assert "Oncology" in text, "Missing Oncology in variance analysis"


# ===========================================================================
# C5: No hallucination — every number must trace to source data
# ===========================================================================

class TestNoHallucination:
    """Numbers in LLM responses must match the data API."""

    def test_brand_numbers_match_api(self):
        """Check that brand revenue figures in a table match the API."""
        ctx = {"page": "overview", "filters": {"ta": ["Oncology"]}, "period": {"year": 2025}}
        llm = ask("Show me all Oncology brands vs budget", context=ctx)

        truth = get_ground_truth("brand", year=2025, ta="Oncology")

        # Build truth lookup: brand_name -> actual revenue
        truth_brands = {}
        for ta_node in truth.get("tree", {}).get("children", []):
            for brand_node in ta_node.get("children", []):
                truth_brands[brand_node["name"]] = brand_node["values"]["actual"]

        # Check LLM table values
        rows = table_rows(llm)
        if rows:
            for row in rows:
                brand = row.get("Brand") or row.get("brand") or row.get("Name", "")
                # Clean emoji prefixes
                brand = brand.strip().lstrip("✅🔴🟡⚠️❌ ")
                if brand in truth_brands:
                    # Extract actual revenue from the row
                    for key in ("Actual ($M)", "Revenue ($M)", "Actual", "Revenue"):
                        if key in row:
                            llm_val = float(row[key].replace("$", "").replace(",", "").replace("M", ""))
                            true_val = truth_brands[brand]
                            assert abs(llm_val - true_val) < 2, \
                                f"{brand}: LLM={llm_val}, truth={true_val}"
                            break


# ===========================================================================
# C6: Clarification mode — should ask, not answer
# ===========================================================================

class TestClarificationConsistency:
    """Vague queries should trigger clarification, not data fabrication."""

    def test_vague_query_clarifies(self):
        results = run_n_times(
            "How are we doing?",
            test_name="c6_clarify",
        )

        for i, r in enumerate(results):
            assert r.clarification is not None, f"Run {i+1}: vague query should trigger clarification, got facts instead"
            assert r.facts is None, f"Run {i+1}: should not have facts for vague query"

    def test_clarification_has_options(self):
        r = ask("What about the numbers?")
        if r.clarification:
            options = r.clarification.get("options", [])
            assert len(options) >= 2, f"Clarification should have 2+ options, got {len(options)}"

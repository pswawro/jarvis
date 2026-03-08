"""Compare AI test results across different model configurations.

Usage:
    # Run tests with Sonnet (default)
    LLM_MODEL_ID=eu.anthropic.claude-sonnet-4-6 python -m pytest tests/ -v
    mv tests/results tests/results_sonnet

    # Run tests with Opus
    LLM_MODEL_ID_HEAVY=eu.anthropic.claude-opus-4-6 python -m pytest tests/ -v
    mv tests/results tests/results_opus

    # Compare
    python tests/compare_runs.py tests/results_sonnet tests/results_opus
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def load_results(directory: Path) -> dict[str, list[dict]]:
    """Load all result JSON files, grouped by test name."""
    grouped = defaultdict(list)
    for f in sorted(directory.glob("*.json")):
        data = json.loads(f.read_text())
        grouped[data["test"]].append(data)
    return dict(grouped)


def compare_consistency(runs: list[dict], label: str) -> dict:
    """Check if multiple runs of the same test are consistent."""
    report = {"test": label, "runs": len(runs), "issues": []}

    # Check facts consistency
    facts = [r.get("facts") for r in runs if r.get("facts")]
    if len(set(facts)) > 1:
        report["issues"].append(f"Facts differ across {len(set(facts))} variants")

    # Check visual table consistency
    visuals = [r.get("visuals", []) for r in runs]
    table_counts = [len([v for v in vs if v.get("tool") == "render_table"]) for vs in visuals]
    if len(set(table_counts)) > 1:
        report["issues"].append(f"Table count varies: {table_counts}")

    # Check config proposal consistency
    configs = [r.get("config_proposal") for r in runs if r.get("config_proposal")]
    if len(configs) > 1:
        keys_sets = [set(c.keys()) for c in configs]
        if len(set(frozenset(k) for k in keys_sets)) > 1:
            report["issues"].append(f"Config keys differ: {keys_sets}")

    # Check durations
    durations = [r["duration_ms"] for r in runs]
    avg = sum(durations) / len(durations)
    report["avg_duration_ms"] = int(avg)
    report["max_duration_ms"] = max(durations)

    if not report["issues"]:
        report["verdict"] = "CONSISTENT"
    else:
        report["verdict"] = "INCONSISTENT"

    return report


def compare_two_configs(dir_a: Path, dir_b: Path):
    """Compare results from two different model configurations."""
    results_a = load_results(dir_a)
    results_b = load_results(dir_b)

    all_tests = sorted(set(results_a.keys()) | set(results_b.keys()))

    print(f"\n{'='*70}")
    print(f"  Model Comparison: {dir_a.name} vs {dir_b.name}")
    print(f"{'='*70}\n")

    for test in all_tests:
        runs_a = results_a.get(test, [])
        runs_b = results_b.get(test, [])

        print(f"\n--- {test} ---")

        if runs_a:
            report_a = compare_consistency(runs_a, f"{dir_a.name}")
            print(f"  {dir_a.name}: {report_a['verdict']} ({report_a['runs']} runs, avg {report_a['avg_duration_ms']}ms)")
            for issue in report_a["issues"]:
                print(f"    ! {issue}")

        if runs_b:
            report_b = compare_consistency(runs_b, f"{dir_b.name}")
            print(f"  {dir_b.name}: {report_b['verdict']} ({report_b['runs']} runs, avg {report_b['avg_duration_ms']}ms)")
            for issue in report_b["issues"]:
                print(f"    ! {issue}")

        if runs_a and runs_b:
            # Compare key metrics
            avg_a = sum(r["duration_ms"] for r in runs_a) / len(runs_a)
            avg_b = sum(r["duration_ms"] for r in runs_b) / len(runs_b)
            speedup = avg_a / avg_b if avg_b > 0 else 0
            print(f"  Speed: {dir_a.name}={int(avg_a)}ms, {dir_b.name}={int(avg_b)}ms ({speedup:.1f}x)")

            # Compare errors
            errors_a = sum(1 for r in runs_a if r.get("error"))
            errors_b = sum(1 for r in runs_b if r.get("error"))
            if errors_a or errors_b:
                print(f"  Errors: {dir_a.name}={errors_a}, {dir_b.name}={errors_b}")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        # Single directory — just show consistency
        d = Path(sys.argv[1])
        results = load_results(d)
        print(f"\nConsistency Report: {d.name}")
        print(f"{'='*50}")
        for test, runs in sorted(results.items()):
            report = compare_consistency(runs, test)
            status = "PASS" if report["verdict"] == "CONSISTENT" else "FAIL"
            print(f"  [{status}] {test} ({report['runs']} runs, avg {report['avg_duration_ms']}ms)")
            for issue in report["issues"]:
                print(f"        ! {issue}")

    elif len(sys.argv) == 3:
        compare_two_configs(Path(sys.argv[1]), Path(sys.argv[2]))

    else:
        print("Usage:")
        print("  python compare_runs.py tests/results              # consistency check")
        print("  python compare_runs.py results_sonnet results_opus  # compare configs")

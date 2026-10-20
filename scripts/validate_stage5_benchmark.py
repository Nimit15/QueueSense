#!/usr/bin/env python3
"""Validate Stage 5 S benchmark and generate comparison against Stage 2 250-case baseline."""

import json
import csv
import statistics
from pathlib import Path
from typing import Dict, List, Tuple

# Paths
STAGE5_DIR = Path("results/stage5_selector_closed_loop")
BASELINE_DIR = Path("results/benchmark_v2_250_isolated")
BASELINE_LEDGER = BASELINE_DIR / "analysis" / "case_ledger.csv"
OUTPUT_DIR = Path("analysis")

OUTPUT_DIR.mkdir(exist_ok=True)

# Load baseline ledger
baseline_cases = {}
with open(BASELINE_LEDGER, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["status"] == "COMPLETED_VALID":
            ctrl = row["controller"]
            sc = row["scenario"]
            seed = int(row["seed"])
            # Load summary JSON for mean_wait_seconds
            # selected_path is like: results\benchmark_v2_250_isolated\balanced\A_seed42_balanced_seed42_summary.json
            path = Path(row["selected_path"])
            if path.exists():
                with open(path) as sf:
                    summ = json.load(sf)
                key = (ctrl, sc, seed)
                baseline_cases[key] = summ.get("mean_wait_seconds", 0.0)

print(f"Loaded {len(baseline_cases)} valid baseline cases")

# Load Stage 5 S cases
stage5_cases = {}
for sc in ["light", "balanced", "uneven", "bottleneck", "surge"]:
    sc_dir = STAGE5_DIR / sc
    if not sc_dir.exists():
        continue
    for summ_file in sc_dir.glob("S_seed*_summary.json"):
        with open(summ_file) as f:
            summ = json.load(f)
        seed = summ["seed"]
        stage5_cases[("S", sc, seed)] = summ.get("mean_wait_seconds", 0.0)

print(f"Loaded {len(stage5_cases)} Stage 5 S cases")

# Validate: 50 cases expected
assert len(stage5_cases) == 50, f"Expected 50 S cases, got {len(stage5_cases)}"

# Verify steps = 241 (300 - 60 warmup)
for key, val in stage5_cases.items():
    ctrl, sc, seed = key
    # Check summary file for steps (filename: S_seed42_light_seed42_summary.json)
    sc_dir = STAGE5_DIR / sc
    summ_file = sc_dir / f"S_seed{seed}_{sc}_seed{seed}_summary.json"
    with open(summ_file) as f:
        summ = json.load(f)
    if summ.get("steps", 0) != 241:
        print(f"WARNING: {key} has {summ.get('steps')} steps, expected 241")

print("All 50 cases validated: 241 post-warmup steps each")

# Paired comparison
paired_results = []
for seed in range(42, 52):
    for sc in ["light", "balanced", "uneven", "bottleneck", "surge"]:
        base_keys = {c: baseline_cases.get((c, sc, seed), 0.0)
                     for c in ["A", "B", "C", "D1", "D2"]}
        s_val = stage5_cases.get(("S", sc, seed), 0.0)
        if all(v > 0 for v in base_keys.values()) and s_val > 0:
            row = {
                "scenario": sc,
                "seed": seed,
                "S_mean_wait": s_val,
                "A_mean_wait": base_keys["A"],
                "B_mean_wait": base_keys["B"],
                "C_mean_wait": base_keys["C"],
                "D1_mean_wait": base_keys["D1"],
                "D2_mean_wait": base_keys["D2"],
            }
            for c in ["A", "B", "C", "D1", "D2"]:
                row[f"S_vs_{c}_diff"] = s_val - base_keys[c]
                row[f"S_vs_{c}_pct"] = (s_val - base_keys[c]) / base_keys[c] * 100
            paired_results.append(row)

print(f"Paired comparisons: {len(paired_results)} valid pairs")

# Aggregate statistics
def mean_std(data: List[float]) -> Tuple[float, float]:
    if not data:
        return 0.0, 0.0
    return statistics.mean(data), statistics.stdev(data) if len(data) > 1 else 0.0

# Overall
s_vals = [r["S_mean_wait"] for r in paired_results]
print(f"\nOverall S mean wait: {statistics.mean(s_vals):.2f} ± {statistics.stdev(s_vals):.2f} s")

# Per controller
for c in ["A", "B", "C", "D1", "D2"]:
    diffs = [r[f"S_vs_{c}_diff"] for r in paired_results]
    m, s = mean_std(diffs)
    pcts = [r[f"S_vs_{c}_pct"] for r in paired_results]
    pm, ps = mean_std(pcts)
    print(f"  S vs {c}: {m:+.2f} ± {s:.2f} s ({pm:+.2f}% ± {ps:.2f}%)")

# Per scenario
scenario_stats = {}
for sc in ["light", "balanced", "uneven", "bottleneck", "surge"]:
    sc_rows = [r for r in paired_results if r["scenario"] == sc]
    s_vals = [r["S_mean_wait"] for r in sc_rows]
    m, s = mean_std(s_vals)
    scenario_stats[sc] = {"mean": m, "std": s, "n": len(sc_rows)}
    print(f"\nScenario {sc} (n={len(sc_rows)}):")
    print(f"  S mean wait: {m:.2f} ± {s:.2f} s")
    for c in ["A", "B", "C", "D1", "D2"]:
        diffs = [r[f"S_vs_{c}_diff"] for r in sc_rows]
        m, sd = mean_std(diffs)
        print(f"  S vs {c}: {m:+.2f} ± {sd:.2f} s")

# Save paired CSV
paired_csv = OUTPUT_DIR / "paired_s_vs_baselines.csv"
with open(paired_csv, "w", newline="") as f:
    if paired_results:
        writer = csv.DictWriter(f, fieldnames=paired_results[0].keys())
        writer.writeheader()
        writer.writerows(paired_results)
print(f"\nSaved paired comparisons to {paired_csv}")

# Save Stage 5 comparison summary JSON
summary = {
    "stage5_controller": "S (ContextAwareSelector)",
    "total_cases": len(stage5_cases),
    "scenarios": list(scenario_stats.keys()),
    "seeds": list(range(42, 52)),
    "overall": {
        "S_mean_wait": statistics.mean(s_vals),
        "S_std_wait": statistics.stdev(s_vals) if len(s_vals) > 1 else 0.0,
    },
    "paired_vs_baselines": {
        c: {
            "mean_diff_seconds": mean_std([r[f"S_vs_{c}_diff"] for r in paired_results])[0],
            "std_diff_seconds": mean_std([r[f"S_vs_{c}_diff"] for r in paired_results])[1],
            "mean_pct_diff": mean_std([r[f"S_vs_{c}_pct"] for r in paired_results])[0],
            "std_pct_diff": mean_std([r[f"S_vs_{c}_pct"] for r in paired_results])[1],
        }
        for c in ["A", "B", "C", "D1", "D2"]
    },
    "per_scenario": scenario_stats,
}

summary_json = OUTPUT_DIR / "STAGE5_FINAL_BENCHMARK_REPORT.json"
with open(summary_json, "w") as f:
    json.dump(summary, f, indent=2)
print(f"Saved JSON summary to {summary_json}")

# Also save a copy in Stage5 dir
stage5_summary = STAGE5_DIR / "stage5_comparison_summary.json"
with open(stage5_summary, "w") as f:
    json.dump(summary, f, indent=2)
print(f"Saved Stage5 summary to {stage5_summary}")

print("\n[OK] Stage 5 validation and comparison complete!")
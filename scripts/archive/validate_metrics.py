#!/usr/bin/env python3
"""
Validate metrics definitions and compute proper statistics.
"""
import json
import pandas as pd
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path("results/benchmark_full")
SCENARIOS = ["balanced", "bottleneck", "light", "surge", "uneven"]
CONTROLLERS = ["A", "B", "C", "D"]
SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]

# Load manifest
with open("results/benchmark_manifest.json") as f:
    manifest = json.load(f)

runs = manifest["runs"]

# Compute proper statistics
stats = defaultdict(lambda: defaultdict(list))

for run in runs:
    scenario = run["scenario"]
    controller = run["controller"]
    seed = run["seed"]

    # Load first file (all duplicates are identical)
    fpath = run["files"][0]
    df = pd.read_csv(fpath)

    # The current metrics only use final row, but we should aggregate over measurement window
    # For now, validate what the current summary actually measures
    final_row = df.iloc[-1]

    # Store final values as per current benchmark - use new metrics where available
    # arrived_cumulative is the correct completed trips metric
    stats[(scenario, controller)]["arrived_cumulative"].append(int(final_row.get("arrived_cumulative", final_row.get("completed", 0))))
    # Keep legacy completed for reference (remaining_expected)
    stats[(scenario, controller)]["remaining_expected"].append(int(final_row.get("remaining_expected", final_row.get("completed", 0))))
    stats[(scenario, controller)]["queue_north"].append(int(final_row.get("queue_north", 0)))
    stats[(scenario, controller)]["queue_east"].append(int(final_row.get("queue_east", 0)))
    stats[(scenario, controller)]["spillback_ns"].append(int(final_row.get("spillback_ns", 0)))
    stats[(scenario, controller)]["spillback_ew"].append(int(final_row.get("spillback_ew", 0)))

# Generate report
report = []
for (scenario, controller), metrics in stats.items():
    for metric, values in metrics.items():
        values = [v for v in values if v is not None]
        if not values:
            continue
        report.append({
            "scenario": scenario,
            "controller": controller,
            "metric": metric,
            "n": len(values),
            "mean": sum(values)/len(values),
            "std": pd.Series(values).std(),
            "min": min(values),
            "max": max(values),
            "median": pd.Series(values).median(),
            "p95": pd.Series(values).quantile(0.95)
        })

df_report = pd.DataFrame(report)
print(df_report.to_string(index=False))

# Save
df_report.to_csv("results/validated_statistics.csv", index=False)
print("\nSaved to results/validated_statistics.csv")

# Check anomalies
print("\n=== ANOMALIES ===")
for scenario in SCENARIOS:
    for controller in CONTROLLERS:
        vals = stats[(scenario, controller)].get("arrived_cumulative", [])
        if len(set(vals)) == 1 and len(vals) > 1:
            print(f"{scenario}/{controller}: all arrived_cumulative values identical: {vals[0]}")

#!/usr/bin/env python3
"""Run the complete QueueSense benchmark: 5 scenarios × 4 controllers × 10 seeds = 200 runs.

This is a clean run from scratch with the fixed simulation runner.
"""

import os
import sys
import time
from pathlib import Path

# Setup
base_dir = Path("D:/QueueSense")
os.chdir(base_dir)
sys.path.insert(0, str(base_dir / "src"))

print("=" * 70)
print("QueueSense Full Benchmark Runner (Clean Run)")
print("=" * 70)
print(f"Working directory: {base_dir}")
print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Configuration - all scenarios, all controllers, all 10 seeds
route_files = {
    "light": ["sumo/routes/benchmark/light.rou.xml"],
    "balanced": ["sumo/routes/benchmark/balanced.rou.xml"],
    "uneven": ["sumo/routes/benchmark/uneven.rou.xml"],
    "bottleneck": ["sumo/routes/benchmark/bottleneck.rou.xml"],
    "surge": ["sumo/routes/benchmark/surge.rou.xml"],
}

SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
CONTROLLERS = ["A", "B", "C", "D"]
SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]

print(f"Scenarios: {SCENARIOS}")
print(f"Controllers: {CONTROLLERS}")
print(f"Seeds: {SEEDS}")
print(f"Total runs: {len(SCENARIOS) * len(CONTROLLERS) * len(SEEDS)} (200)")
print()

from queuesense.benchmark.runner import BenchmarkRunner

output_dir = base_dir / "results" / "benchmark_final"
print(f"Output directory: {output_dir}")

runner = BenchmarkRunner(
    net_file=r"D:\QueueSense\sumo\network\corridor.net.xml",
    route_files=route_files,
    output_dir=str(output_dir),
    step_length=1.0,
    duration=3600,
    warmup_time=300,
    seeds=SEEDS,
    scenarios=SCENARIOS,
    gui=False,
)

print("Starting full benchmark (200 runs)...")
print("Each run: ~30-60 seconds. Total estimated: 2-4 hours.")
print("Progress will be shown in the output file.")
print()

start_time = time.time()
results = runner.run_benchmark()
elapsed = time.time() - start_time

print("Generating summary...")
summary = runner.generate_summary(results)
runner.write_summary(summary)

print()
print("=" * 70)
print("BENCHMARK COMPLETE")
print("=" * 70)
print(f"Total runs: {summary.get('total_runs', 0)}")
print(f"Successful: {summary.get('successful_runs', 0)}")
print(f"Failed: {summary.get('failed_runs', 0)}")
print(f"Elapsed time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
print()

# Verify output files
output_dir_path = Path(output_dir)
csv_files = list(output_dir_path.rglob("*.csv"))
print(f"CSV files created: {len(csv_files)} (expected: 200)")

# Check per-scenario counts
print("\nPer-scenario breakdown:")
for scenario in SCENARIOS:
    scenario_dir = output_dir_path / scenario
    if scenario_dir.exists():
        count = len(list(scenario_dir.glob("*.csv")))
        print(f"  {scenario}: {count} CSV files")
    else:
        print(f"  {scenario}: 0 CSV files (directory missing)")

# Verify data quality for a few files
print("\nData quality verification (first file per scenario):")
import csv
for scenario in SCENARIOS:
    scenario_dir = output_dir_path / scenario
    if scenario_dir.exists():
        csv_files_s = sorted(scenario_dir.glob("*.csv"))
        if csv_files_s:
            with open(csv_files_s[0]) as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                if rows:
                    times = [float(r['time']) for r in rows]
                    arrived = [int(r.get('arrived_cumulative', 0)) for r in rows]
                    print(f"  {scenario}/{csv_files_s[0].name}: {len(rows)} rows, "
                          f"time {min(times):.0f}-{max(times):.0f}s, arrived={max(arrived)}")

# Write consolidated summary report
print("\nWriting consolidated summary report...")
report_path = base_dir / "results" / "benchmark_final" / "CONSOLIDATED_SUMMARY.json"

# Build summary
summary_data = {
    "generated": time.strftime('%Y-%m-%d %H:%M:%S'),
    "total_expected": 200,
    "total_runs": summary.get('total_runs', 0),
    "successful_runs": summary.get('successful_runs', 0),
    "failed_runs": summary.get('failed_runs', 0),
    "scenarios": summary.get('scenarios', []),
    "controllers": summary.get('controllers', []),
    "seeds": summary.get('seeds', []),
    "metrics": summary.get('metrics', {}),
}

with open(report_path, 'w') as f:
    json.dump(summary_data, f, indent=2)

# Also write human-readable text summary
text_path = base_dir / "results" / "benchmark_final" / "CONSOLIDATED_SUMMARY.txt"
with open(text_path, 'w') as f:
    f.write("QueueSense Benchmark - Full Summary\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(f"Total expected runs: 200 (5 scenarios × 4 controllers × 10 seeds)\n")
    f.write(f"Total runs: {summary.get('total_runs', 0)}\n")
    f.write(f"Successful: {summary.get('successful_runs', 0)}\n")
    f.write(f"Failed: {summary.get('failed_runs', 0)}\n\n")
    f.write(f"Scenarios: {', '.join(summary.get('scenarios', []))}\n")
    f.write(f"Controllers: {', '.join(summary.get('controllers', []))}\n")
    f.write(f"Seeds: {', '.join(map(str, summary.get('seeds', [])))}\n\n")
    f.write("Per-scenario, per-controller metrics:\n")
    if 'metrics' in summary and summary['metrics']:
        import json
        f.write(json.dumps(summary['metrics'], indent=2)[:3000])

print(f"\nReports written:")
print(f"  JSON: {report_path}")
print(f"  Text: {text_path}")
print()
print("Done!")
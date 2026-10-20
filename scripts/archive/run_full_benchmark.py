#!/usr/bin/env python3
"""Run the complete QueueSense benchmark: 5 scenarios × 4 controllers × 10 seeds = 200 runs."""

import os
import sys
import time
from pathlib import Path

# Setup
base_dir = Path("D:/QueueSense")
os.chdir(base_dir)
sys.path.insert(0, str(base_dir / "src"))

print("=" * 70)
print("QueueSense Full Benchmark Runner")
print("=" * 70)
print(f"Working directory: {base_dir}")
print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Configuration
route_files = {
    "light": [str(base_dir / "sumo" / "routes" / "benchmark" / "light.rou.xml")],
    "balanced": [str(base_dir / "sumo" / "routes" / "benchmark" / "balanced.rou.xml")],
    "uneven": [str(base_dir / "sumo" / "routes" / "benchmark" / "uneven.rou.xml")],
    "bottleneck": [str(base_dir / "sumo" / "routes" / "benchmark" / "bottleneck.rou.xml")],
    "surge": [str(base_dir / "sumo" / "routes" / "benchmark" / "surge.rou.xml")],
}

SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
CONTROLLERS = ["A", "B", "C", "D"]
SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]

print(f"Scenarios: {SCENARIOS}")
print(f"Controllers: {CONTROLLERS}")
print(f"Seeds: {SEEDS}")
print(f"Total runs: {len(SCENARIOS) * len(CONTROLLERS) * len(SEEDS)}")
print()

# Import after path setup
from queuesense.benchmark.runner import BenchmarkRunner

# Create runner with new output directory
output_dir = base_dir / "results" / "benchmark_final"
print(f"Output directory: {output_dir}")

runner = BenchmarkRunner(
    net_file=str(base_dir / "sumo" / "network" / "corridor.net.xml"),
    route_files=route_files,
    output_dir=str(output_dir),
    step_length=1.0,
    duration=3600,
    warmup_time=300,
    seeds=SEEDS,
    scenarios=SCENARIOS,
    gui=False,
)

# Run benchmark
print("Starting full benchmark...")
print("This will run 200 combinations (5 scenarios × 4 controllers × 10 seeds).")
print("Each run takes ~30-60 seconds. Total estimated time: 2-4 hours.")
print()

start_time = time.time()
results = runner.run_benchmark()
elapsed = time.time() - start_time

# Generate and write summary
print("Generating summary...")
summary = runner.generate_summary(results)
runner.write_summary(summary)

# Print summary
print()
print("=" * 70)
print("BENCHMARK COMPLETE")
print("=" * 70)
print(f"Total runs: {summary.get('total_runs', 0)}")
print(f"Successful: {summary.get('successful_runs', 0)}")
print(f"Failed: {summary.get('failed_runs', 0)}")
print(f"Elapsed time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
print()

# Show per-scenario breakdown
if 'metrics' in summary and summary['metrics']:
    print("Per-scenario controller summary:")
    for metric_name, metric_data in summary['metrics'].items():
        if isinstance(metric_data, list) and metric_data:
            # Show first entry as representative
            first = metric_data[0]
            scenario = first.get('scenario', '?')
            controller = first.get('controller', '?')
            print(f"  {metric_name}: scenario={scenario}, controller={controller}")

# Verify output files
output_dir_path = Path(output_dir)
csv_files = list(output_dir_path.rglob("*.csv"))
print(f"\nCSV files created: {len(csv_files)} (expected: 200)")

# Check a few files
if csv_files:
    import csv
    # Show stats for first 5 files
    for csv_file in sorted(csv_files)[:5]:
        with open(csv_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                times = [float(r['time']) for r in rows]
                arrived = [int(r.get('arrived_cumulative', 0)) for r in rows]
                print(f"  {csv_file.name}: {len(rows)} rows, time {min(times):.0f}-{max(times):.0f}s, arrived={max(arrived)}")

# Write a quick validation report
print()
print("Writing validation report...")
report_dir = base_dir / "results" / "benchmark_final"
report_path = report_dir / "VALIDATION_REPORT.txt"
with open(report_path, 'w') as f:
    f.write("QueueSense Benchmark - Validation Report\n")
    f.write("=" * 50 + "\n\n")
    f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(f"Total runs: {summary.get('total_runs', 0)}\n")
    f.write(f"Successful: {summary.get('successful_runs', 0)}\n")
    f.write(f"Failed: {summary.get('failed_runs', 0)}\n\n")
    f.write(f"Scenarios: {', '.join(summary.get('scenarios', []))}\n")
    f.write(f"Controllers: {', '.join(summary.get('controllers', []))}\n")
    f.write(f"Seeds: {', '.join(map(str, summary.get('seeds', [])))}\n\n")
    f.write(f"Elapsed time: {elapsed:.1f} seconds\n\n")
    f.write("Per-scenario, per-controller metrics:\n")
    if 'metrics' in summary and summary['metrics']:
        import json
        f.write(json.dumps(summary['metrics'], indent=2)[:5000])

print(f"Report written to: {report_path}")
print()
print("Done!")
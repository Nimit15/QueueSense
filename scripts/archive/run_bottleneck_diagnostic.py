#!/usr/bin/env python3
"""
Run a diagnostic benchmark on bottleneck scenario: seed=42, all 4 controllers.
Output to results/time_bottleneck/
"""

import os
import sys
import csv
from pathlib import Path

# Setup path
base_dir = Path(__file__).parent.resolve()
os.chdir(base_dir)
sys.path.insert(0, str(base_dir / "src"))

print("QueueSense Bottleneck Diagnostic Benchmark")
print("=" * 60)

# Configuration
NET_FILE = "sumo/network/corridor.net.xml"
ROUTE_DIR = "sumo/routes"

# Scenario for diagnostic
SCENARIO = "bottleneck"

# All controller IDs
CONTROLLERS = ["A", "B", "C", "D"]

# Single seed for diagnostic
SEEDS = [42]

# Build route_files dict
route_files = {}
route_path = base_dir / ROUTE_DIR / f"{SCENARIO}.rou.xml"
if route_path.exists():
    route_files[SCENARIO] = [str(route_path)]
    print(f"Found route: {SCENARIO} -> {route_path}")
else:
    print(f"MISSING route: {SCENARIO} -> {route_path}")
    sys.exit(1)

# Check net file
net_path = base_dir / NET_FILE
if not net_path.exists():
    print(f"ERROR: Network file not found: {net_path}")
    sys.exit(1)
print(f"Network file: {net_path}")

print()
print(f"Scenario: {SCENARIO}")
print(f"Controllers: {CONTROLLERS}")
print(f"Seeds: {SEEDS}")
print(f"Total runs: {len(route_files) * len(CONTROLLERS) * len(SEEDS)}")
print()

# Import after path setup
from queuesense.benchmark.runner import BenchmarkRunner

# Create runner
output_dir = base_dir / "results" / "time_bottleneck"

runner = BenchmarkRunner(
    net_file=str(net_path),
    route_files=route_files,
    output_dir=str(output_dir),
    step_length=1.0,
    duration=3600,
    warmup_time=300,
    seeds=SEEDS,
    scenarios=list(route_files.keys()),
    gui=False,
)

# Run benchmark
print("Starting benchmark...")
import time
start_time = time.time()

results = runner.run_benchmark()
summary = runner.generate_summary(results)
runner.write_summary(summary)

elapsed = time.time() - start_time

print()
print("=" * 60)
print("BENCHMARK COMPLETE")
print("=" * 60)
print(f"Total runs: {summary.get('total_runs', 0)}")
print(f"Successful: {summary.get('successful_runs', 0)}")
print(f"Failed: {summary.get('failed_runs', 0)}")
print(f"Elapsed time: {elapsed:.1f} seconds")
print(f"Output directory: {output_dir}")

# Verify output files
csv_files = list(output_dir.rglob("*.csv"))
print(f"CSV files created: {len(csv_files)}")

# Show results for each controller
print("\nResults per controller:")
for controller in CONTROLLERS:
    # Find the CSV file for this combination
    pattern = f"{controller}_seed{SEEDS[0]}_*.csv"
    files = list((output_dir / SCENARIO).glob(pattern))
    if files:
        latest = max(files, key=lambda x: x.stat().st_mtime)
        with open(latest) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                last_row = rows[-1]
                arrived = int(last_row.get('arrived_cumulative', 0))
                remaining = int(last_row.get('remaining_expected', 0))
                spillback_ns = int(last_row.get('spillback_ns', 0))
                spillback_ew = int(last_row.get('spillback_ew', 0))
                print(f"Controller {controller}: arrived={arrived}, remaining={remaining}, spillback_NS={spillback_ns}, spillback_EW={spillback_ew}")
    else:
        print(f"Controller {controller}: NO FILE FOUND")

# Also generate a simple text summary
summary_path = output_dir / "SUMMARY.txt"
with open(summary_path, "w") as f:
    f.write("QueueSense Bottleneck Diagnostic Results (seed=42)\\n")
    f.write("=" * 50 + "\\n\\n")
    for controller in CONTROLLERS:
        pattern = f"{controller}_seed{SEEDS[0]}_*.csv"
        files = list((output_dir / SCENARIO).glob(pattern))
        if files:
            latest = max(files, key=lambda x: x.stat().st_mtime)
            with open(latest) as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                if rows:
                    last_row = rows[-1]
                    arrived = int(last_row.get('arrived_cumulative', 0))
                    remaining = int(last_row.get('remaining_expected', 0))
                    spillback_ns = int(last_row.get('spillback_ns', 0))
                    spillback_ew = int(last_row.get('spillback_ew', 0))
                    f.write(f"Controller {controller}:\\n")
                    f.write(f"  Arrived cumulative: {arrived}\\n")
                    f.write(f"  Remaining expected: {remaining}\\n")
                    f.write(f"  Spillback NS: {spillback_ns}\\n")
                    f.write(f"  Spillback EW: {spillback_ew}\\n\\n")

print(f"Summary written to: {summary_path}")
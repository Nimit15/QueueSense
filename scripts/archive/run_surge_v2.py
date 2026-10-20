#!/usr/bin/env python3
"""Run surge scenario only - clean version."""

import os, sys
from pathlib import Path

base_dir = Path("D:/QueueSense")
os.chdir(base_dir)
sys.path.insert(0, str(base_dir / "src"))

from queuesense.benchmark.runner import BenchmarkRunner

route_files = {"surge": ["sumo/routes/benchmark/surge.rou.xml"]}
output_dir = base_dir / "results" / "benchmark_final"

runner = BenchmarkRunner(
    net_file=r"D:\QueueSense\sumo\network\corridor.net.xml",
    route_files=route_files,
    output_dir=str(output_dir),
    step_length=1.0,
    duration=3600,
    warmup_time=300,
    seeds=[42, 43, 44, 45, 46, 47, 48, 49, 50, 51],
    scenarios=["surge"],
    gui=False,
)

print("Running surge scenario...")
results = runner.run_benchmark()
summary = runner.generate_summary(results)
runner.write_summary(summary)

print(f"\nSurge: total={summary.get('total_runs')}, successful={summary.get('successful_runs')}, failed={summary.get('failed_runs')}")

import csv
output_dir_path = Path(output_dir)
scenario_dir = output_dir_path / "surge"
csv_files = list(scenario_dir.glob("*.csv"))
print(f"CSV files: {len(csv_files)}")

if csv_files:
    for f in csv_files[:2]:
        with open(f) as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            times = [float(r['time']) for r in rows]
            arrived = [int(r.get('arrived_cumulative', 0)) for r in rows]
            print(f"  {f.name}: {len(rows)} rows, time {min(times):.0f}-{max(times):.0f}s, arrived={max(arrived)}")
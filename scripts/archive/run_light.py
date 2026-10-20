#!/usr/bin/env python3
"""Run light scenario only."""

import os, sys
from pathlib import Path

base_dir = Path("D:/QueueSense")
os.chdir(base_dir)
sys.path.insert(0, str(base_dir / "src"))

from queuesense.benchmark.runner import BenchmarkRunner

route_files = {"light": ["sumo/routes/benchmark/light.rou.xml"]}
output_dir = base_dir / "results" / "benchmark_final_clean"

runner = BenchmarkRunner(
    net_file=r"D:\QueueSense\sumo\network\corridor.net.xml",
    route_files=route_files,
    output_dir=str(output_dir),
    step_length=1.0,
    duration=3600,
    warmup_time=300,
    seeds=[42, 43, 44, 45, 46, 47, 48, 49, 50, 51],
    scenarios=["light"],
    gui=False,
)

print("Running light scenario...")
results = runner.run_benchmark()
summary = runner.generate_summary(results)
runner.write_summary(summary)

print(f"\nLight: total={summary.get('total_runs')}, successful={summary.get('successful_runs')}, failed={summary.get('failed_runs')}")

import csv
output_dir_path = Path(output_dir)
scenario_dir = output_dir_path / "light"
csv_files = list(scenario_dir.glob("*.csv"))
print(f"CSV files: {len(csv_files)}")

if csv_files:
    valid_count = 0
    for f in csv_files:
        with open(f) as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            if len(rows) == 3302:
                times = [float(r['time']) for r in rows]
                arrived = [int(r.get('arrived_cumulative', 0)) for r in rows]
                if max(arrived) > 0 and min(times) == 0.0 and max(times) == 3600.0:
                    valid_count += 1
                    # Extract controller and seed from filename
                    fname = f.stem
                    parts = fname.split('_')
                    if len(parts) >= 3:
                        controller = parts[0]
                        seed_str = parts[1]
                        if seed_str.startswith('seed'):
                            seed_num = seed_str[4:]
                            print(f"  {f.name}: ctrl={controller}, seed={seed_num}, valid")
                        else:
                            print(f"  {f.name}: valid but unusual seed format")
                    else:
                        print(f"  {f.name}: valid but unusual filename")
                else:
                    print(f"  {f.name}: has {len(rows)} rows but metrics don't match")
            else:
                print(f"  {f.name}: has {len(rows)} rows (expected 3302)")
    print(f"Valid runs: {valid_count}/{len(csv_files)}")
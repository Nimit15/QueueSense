#!/usr/bin/env python3
"""
Run the full QueueSense benchmark in batches.
Each batch runs a subset of the 200 combinations to allow for interruptions.

Total: 5 scenarios × 4 controllers × 10 seeds = 200 runs
Each run: 3600s simulation = ~2-3 minutes real time
Total estimated: ~8-12 hours
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Dict
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.benchmark.runner import BenchmarkRunner

# Configuration
NET_FILE = "sumo/network/corridor.net.xml"
ROUTE_DIR = "sumo/routes/benchmark"

# All scenarios with existing route files
ALL_SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
ALL_CONTROLLERS = ["A", "B", "C", "D"]
ALL_SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]


def build_route_files(scenarios: List[str]) -> Dict[str, List[str]]:
    """Build route_files dict for given scenarios."""
    route_files = {}
    for scenario in scenarios:
        route_path = f"{ROUTE_DIR}/{scenario}.rou.xml"
        if os.path.exists(route_path):
            route_files[scenario] = [route_path]
        else:
            print(f"WARNING: Route file not found: {route_path}")
    return route_files


def run_batch(
    batch_name: str,
    scenarios: List[str],
    controllers: List[str],
    seeds: List[int],
    output_dir: str = "results/benchmark_final",
    duration: int = 3600,
    warmup_time: int = 300,
):
    """Run a batch of benchmark combinations."""
    route_files = build_route_files(scenarios)
    if not route_files:
        print("No valid route files found!")
        return

    output_dir = Path(output_dir) / batch_name
    output_dir.mkdir(parents=True, exist_ok=True)

    runner = BenchmarkRunner(
        net_file=NET_FILE,
        route_files=route_files,
        output_dir=str(output_dir),
        step_length=1.0,
        duration=duration,
        warmup_time=warmup_time,
        seeds=seeds,
        scenarios=scenarios,
        gui=False,
    )

    print(f"\n{'='*60}")
    print(f"Starting batch: {batch_name}")
    print(f"Scenarios: {scenarios}")
    print(f"Controllers: {controllers}")
    print(f"Seeds: {seeds}")
    print(f"Expected runs: {len(scenarios) * len(controllers) * len(seeds)}")
    print(f"Output: {output_dir}")
    print(f"{'='*60}")

    start_time = time.time()
    results = runner.run_benchmark()
    summary = runner.generate_summary(results)
    runner.write_summary(summary)
    elapsed = time.time() - start_time

    print(f"\nBatch '{batch_name}' completed in {elapsed:.1f}s")
    print(f"Total runs: {summary.get('total_runs', 0)}")
    print(f"Successful: {summary.get('successful_runs', 0)}")
    print(f"Failed: {summary.get('failed_runs', 0)}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Run QueueSense benchmark in batches")
    parser.add_argument("--batch", type=str, default="batch1", help="Batch name")
    parser.add_argument("--scenarios", nargs="+", default=ALL_SCENARIOS, help="Scenarios to run")
    parser.add_argument("--controllers", nargs="+", default=ALL_CONTROLLERS, help="Controllers to run")
    parser.add_argument("--seeds", nargs="+", type=int, default=ALL_SEEDS, help="Seeds to run")
    parser.add_argument("--output-dir", type=str, default="results/benchmark_final", help="Output directory")
    parser.add_argument("--duration", type=int, default=3600, help="Simulation duration")
    parser.add_argument("--warmup", type=int, default=300, help="Warmup time")
    args = parser.parse_args()

    # Convert seeds to list if single value
    if len(args.seeds) == 1 and args.seeds[0] == ALL_SEEDS[0]:
        args.seeds = ALL_SEEDS

    run_batch(
        batch_name=args.batch,
        scenarios=args.scenarios,
        controllers=args.controllers,
        seeds=args.seeds,
        output_dir=args.output_dir,
        duration=args.duration,
        warmup_time=args.warmup,
    )


if __name__ == "__main__":
    main()

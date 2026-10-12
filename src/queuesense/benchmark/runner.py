"""
Benchmark Runner for QueueSense Baselines
Runs FixedTime, Actuated, and QueuePressure controllers across scenarios with common seeds.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List
import csv

import yaml

from queuesense.simulation.runner import SimulationRunner
from queuesense.controllers import (
    FixedTimeController,
    ActuatedController,
    QueuePressureController,
)


logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Runs a suite of scenarios with multiple controllers."""

    def __init__(
        self,
        net_file: str,
        route_files: Dict[str, List[str]],
        output_dir: str = "results/benchmark",
        step_length: float = 1.0,
        duration: int = 3600,
        warmup_time: int = 300,
        seeds: List[int] = [42, 43, 44],
        scenarios: List[str] = ["light", "balanced", "uneven", "bottleneck", "surge"],
        gui: bool = False,
    ):
        """
        Initialize benchmark runner.

        Args:
            net_file: Path to SUMO network file
            route_files: Dict mapping scenario names to route file lists
            output_dir: Directory to save benchmark results
            step_length: Simulation step length (s)
            duration: Total simulation duration (s)
            warmup_time: Warmup period before metrics collection (s)
            seeds: Random seeds for reproducibility
            scenarios: List of scenario names to run
            gui: Whether to run with SUMO-GUI
        """
        self.net_file = net_file
        self.route_files = route_files
        self.output_dir = Path(output_dir)
        self.step_length = step_length
        self.duration = duration
        self.warmup_time = warmup_time
        self.seeds = seeds
        self.scenarios = scenarios
        self.gui = gui

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Controllers to benchmark
        self.controllers = {
            "A": FixedTimeController(),
            "B": ActuatedController(gap_threshold=3.0),
            "C": QueuePressureController(alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0),
        }

        logger.info(
            f"BenchmarkRunner initialized: scenarios={scenarios}, seeds={seeds}, "
            f"controllers={list(self.controllers.keys())}, duration={duration}s"
        )

    def _validate_config(self):
        """Validate configuration before running benchmarks."""
        if not Path(self.net_file).exists():
            raise FileNotFoundError(f"Network file not found: {self.net_file}")

        for scenario, files in self.route_files.items():
            for f in files:
                if not Path(f).exists():
                    raise FileNotFoundError(f"Route file not found for scenario {scenario}: {f}")

        logger.info("Configuration validated successfully")

    def _run_scenario_for_controller(self, scenario: str, controller_id: str, seed: int):
        """Run a single scenario with a single controller.

        Args:
            scenario: Scenario name
            controller_id: Controller identifier (A, B, C)
            seed: Random seed for reproducibility

        Returns:
            Dict with run-level results
        """
        controller = self.controllers[controller_id]
        route_files = self.route_files.get(scenario, [])

        # Create subdirectory per scenario
        scenario_dir = self.output_dir / scenario
        scenario_dir.mkdir(exist_ok=True)

        # Unique output filename with scenario, controller, and seed
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = scenario_dir / f"{controller_id}_seed{seed}_{ts}.csv"

        runner = SimulationRunner(
            net_file=self.net_file,
            route_files=route_files,
            output_dir=str(scenario_dir),
            step_length=self.step_length,
            duration=self.duration,
            warmup_time=self.warmup_time,
            controller=controller,
            gui=self.gui,
            csv_prefix=f"{controller_id}_seed{seed}",
        )

        try:
            logger.info(f"Running {scenario} with Controller {controller_id} (seed={seed})")
            runner.run()
            logger.info(f"Completed {scenario}/{controller_id}/seed={seed}")

            # Read the generated CSV to extract summary metrics
            import glob
            csv_files = list(scenario_dir.glob(f"{controller_id}_seed{seed}_*.csv"))
            if not csv_files:
                logger.error(f"No CSV generated for {scenario}/{controller_id}/seed={seed}")
                return {
                    "scenario": scenario,
                    "controller": controller_id,
                    "seed": seed,
                    "status": "failed",
                    "error": "no_output",
                }

            # Read the last (most recent) CSV file
            latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
            with open(latest_csv, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if not rows:
                    logger.error(f"Empty CSV for {scenario}/{controller_id}/seed={seed}")
                    return {
                        "scenario": scenario,
                        "controller": controller_id,
                        "seed": seed,
                        "status": "failed",
                        "error": "empty_output",
                    }

            # Extract summary metrics from last row
            last_row = rows[-1]
            summary = {
                "scenario": scenario,
                "controller": controller_id,
                "seed": seed,
                "status": "success",
                "time": float(last_row.get("time", 0.0)),
                "completed": int(last_row.get("completed", 0)),
                "queue_north": int(last_row.get("queue_north", 0)),
                "queue_south": int(last_row.get("queue_south", 0)),
                "queue_east": int(last_row.get("queue_east", 0)),
                "queue_west": int(last_row.get("queue_west", 0)),
                "spillback_ns": int(last_row.get("spillback_ns", 0)),
                "spillback_ew": int(last_row.get("spillback_ew", 0)),
                "output_file": str(latest_csv),
            }

            return summary

        except Exception as e:
            logger.exception(f"Failed to run {scenario}/{controller_id}/seed={seed}: {e}")
            return {
                "scenario": scenario,
                "controller": controller_id,
                "seed": seed,
                "status": "failed",
                "error": str(e),
            }

    def run_benchmark(self) -> List[Dict]:
        """Run the full benchmark suite.

        Returns:
            List of run-level result dictionaries
        """
        self._validate_config()
        results = []

        for scenario in self.scenarios:
            for controller_id in self.controllers.keys():
                for seed in self.seeds:
                    result = self._run_scenario_for_controller(scenario, controller_id, seed)
                    results.append(result)

        return results

    def generate_summary(self, results: List[Dict]) -> Dict:
        """Generate a summary report from run-level results.

        Args:
            results: List of run-level result dicts

        Returns:
            Dict with summary statistics and comparisons
        """
        import pandas as pd

        df = pd.DataFrame(results)
        if df.empty:
            return {"error": "no_results"}

        # Filter successful runs
        df_success = df[df["status"] == "success"]

        summary = {
            "total_runs": len(results),
            "successful_runs": len(df_success),
            "failed_runs": len(df[df["status"] == "failed"]),
            "scenarios": sorted(df_success["scenario"].unique().tolist()),
            "controllers": sorted(df_success["controller"].unique().tolist()),
            "seeds": sorted(df_success["seed"].unique().tolist()),
            "metrics": {},
        }

        # Compute mean/std per scenario/controller for key metrics
        for metric in ["completed", "queue_north", "queue_south", "queue_east", "queue_west", "spillback_ns", "spillback_ew"]:
            if metric in df_success.columns:
                agg_df = df_success.groupby(["scenario", "controller"])[metric].agg(["mean", "std", "min", "max"])
                summary["metrics"][metric] = agg_df.reset_index().to_dict(orient="records")

        return summary

    def write_summary(self, summary: Dict):
        """Write summary to JSON and text files."""
        import json

        summary_file = self.output_dir / "summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        text_file = self.output_dir / "summary.txt"
        with open(text_file, "w") as f:
            f.write("QueueSense Baseline Benchmark Summary\n")
            f.write("=" * 50 + "\n")
            f.write(f"Total runs: {summary.get('total_runs', 0)}\n")
            f.write(f"Successful: {summary.get('successful_runs', 0)}\n")
            f.write(f"Failed: {summary.get('failed_runs', 0)}\n")
            f.write(f"Scenarios: {', '.join(summary.get('scenarios', []))}\n")
            f.write(f"Controllers: {', '.join(summary.get('controllers', []))}\n")
            f.write(f"Seeds: {', '.join(map(str, summary.get('seeds', [])))}\n")

        logger.info(f"Summary written to {summary_file} and {text_file}")


def run_baseline_benchmark(
    net_file: str,
    route_files: Dict[str, List[str]],
    output_dir: str = "results/benchmark",
    step_length: float = 1.0,
    duration: int = 3600,
    warmup_time: int = 300,
    seeds: List[int] = [42, 43, 44],
    scenarios: List[str] = ["light", "balanced", "uneven", "bottleneck", "surge"],
    gui: bool = False,
):
    """Convenience function to run the baseline benchmark.

    Args:
        net_file: Path to SUMO network file
        route_files: Dict mapping scenario names to route file lists
        output_dir: Output directory for benchmark results
        step_length: Simulation step length
        duration: Total duration
        warmup_time: Warmup period
        seeds: Random seeds
        scenarios: List of scenario names
        gui: Run with GUI
    """
    runner = BenchmarkRunner(
        net_file=net_file,
        route_files=route_files,
        output_dir=output_dir,
        step_length=step_length,
        duration=duration,
        warmup_time=warmup_time,
        seeds=seeds,
        scenarios=scenarios,
        gui=gui,
    )
    results = runner.run_benchmark()
    summary = runner.generate_summary(results)
    runner.write_summary(summary)
    return results, summary

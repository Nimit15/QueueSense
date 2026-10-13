"""
Tests for the benchmark runner.
"""

import pytest
import shutil
from pathlib import Path

from queuesense.benchmark.runner import BenchmarkRunner, run_baseline_benchmark


class TestBenchmarkRunner:
    """Test the benchmark runner and its scenarios."""

    def setup_method(self):
        """Clean up benchmark results before each test."""
        shutil.rmtree("results/benchmark", ignore_errors=True)

    def teardown_method(self):
        """Clean up benchmark results after each test."""
        shutil.rmtree("results/benchmark", ignore_errors=True)

    def test_runner_initialization(self):
        """BenchmarkRunner should initialize correctly."""
        runner = BenchmarkRunner(
            net_file="sumo/network/corridor.net.xml",
            route_files={"balanced": ["sumo/routes/benchmark/balanced.rou.xml"]},
            output_dir="results/benchmark",
            seeds=[42],
            scenarios=["balanced"],
        )
        assert runner.net_file == "sumo/network/corridor.net.xml"
        assert "balanced" in runner.route_files
        assert runner.seeds == [42]
        assert runner.scenarios == ["balanced"]
        assert "A" in runner.controllers
        assert "B" in runner.controllers
        assert "C" in runner.controllers

    def test_smoke_run(self):
        """Run a minimal benchmark smoke test."""
        results, summary = run_baseline_benchmark(
            net_file="sumo/network/corridor.net.xml",
            route_files={"balanced": ["sumo/routes/benchmark/balanced.rou.xml"]},
            output_dir="results/benchmark",
            step_length=1.0,
            duration=120,
            warmup_time=30,
            seeds=[42],
            scenarios=["balanced"],
            gui=False,
        )
        assert len(results) == 4  # 1 scenario * 4 controllers * 1 seed
        assert summary["successful_runs"] == 4
        assert summary["failed_runs"] == 0
        assert "metrics" in summary

    def test_output_files_exist(self):
        """Verify that benchmark runner creates output files."""
        run_baseline_benchmark(
            net_file="sumo/network/corridor.net.xml",
            route_files={"balanced": ["sumo/routes/benchmark/balanced.rou.xml"]},
            output_dir="results/benchmark",
            step_length=1.0,
            duration=120,
            warmup_time=30,
            seeds=[42],
            scenarios=["balanced"],
            gui=False,
        )
        # Check that summary files exist
        assert Path("results/benchmark/summary.json").exists()
        assert Path("results/benchmark/summary.txt").exists()
        # Check that CSV files exist
        csvs = list(Path("results/benchmark/balanced").glob("*.csv"))
        assert len(csvs) == 4  # A, B, C, D

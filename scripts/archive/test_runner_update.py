#!/usr/bin/env python3
"""
Test the updated SimulationRunner with downstream eligibility logic.
"""

import os
import sys
from queuesense.simulation.runner import SimulationRunner
from queuesense.controllers.fixed_time import FixedTimeController

def test_runner_initialization():
    """Test that the runner initializes correctly with downstream edges mapping."""
    net_file = "D:/QueueSense/sumo/network/corridor.net.xml"
    route_files = ["D:/QueueSense/sumo/routes/bottleneck.rou.xml"]

    print("Testing SimulationRunner initialization...")
    try:
        runner = SimulationRunner(
            net_file=net_file,
            route_files=route_files,
            output_dir="D:/QueueSense/results/test_init",
            step_length=1.0,
            duration=100,  # Short test
            warmup_time=0,
            controller=FixedTimeController(),
            gui=False,
            csv_prefix="test_init",
            seed=42
        )

        print(f"Downstream threshold: {runner.downstream_threshold}")
        print(f"Downstream edges mapping: {runner._downstream_edges}")

        # Check that we have the expected mappings
        expected_edges = ["in_north", "in_east", "in_west"]
        for edge in expected_edges:
            if edge in runner._downstream_edges:
                print(f"* {edge} -> {runner._downstream_edges[edge]}")
            else:
                print(f"! {edge} not found in downstream edges")

        return True
    except Exception as e:
        print(f"! Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_runner_initialization()
    sys.exit(0 if success else 1)
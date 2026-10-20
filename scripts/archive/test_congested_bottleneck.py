#!/usr/bin/env python3
"""
Test script to run all four controllers on the congested bottleneck scenario.
"""

import os
import sys
from queuesense.simulation.runner import SimulationRunner
from queuesense.controllers.fixed_time import FixedTimeController
from queuesense.controllers.actuated import ActuatedController
from queuesense.controllers.queue_pressure import QueuePressureController
from queuesense.controllers.queuesense import QueueSenseController

def run_controller_test(controller_class, controller_name, net_file, route_files, output_dir, seed=42):
    """Run a single controller test."""
    print(f"\n=== Testing {controller_name} ===")

    # Create controller instance
    if controller_name == "FixedTime":
        controller = FixedTimeController()
    elif controller_name == "Actuated":
        controller = ActuatedController()
    elif controller_name == "QueuePressure":
        controller = QueuePressureController()
    elif controller_name == "QueueSense":
        controller = QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=0.85, max_wait=90.0
        )
    else:
        raise ValueError(f"Unknown controller: {controller_name}")

    # Create and run simulation
    runner = SimulationRunner(
        net_file=net_file,
        route_files=route_files,
        output_dir=output_dir,
        step_length=1.0,
        duration=3600,
        warmup_time=300,
        controller=controller,
        gui=False,
        csv_prefix=f"{controller_name.lower()}_congested",
        seed=seed
    )

    try:
        runner.run()
        print(f"{controller_name} completed successfully")
        return True
    except Exception as e:
        print(f"{controller_name} failed: {e}")
        return False

def main():
    """Run all four controllers on congested bottleneck scenario."""
    net_file = "D:/QueueSense/sumo/network/corridor.net.xml"
    route_files = ["D:/QueueSense/sumo/routes/bottleneck_congested.rou.xml"]
    output_dir = "D:/QueueSense/results/congested_test"

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    controllers = [
        (FixedTimeController, "FixedTime"),
        (ActuatedController, "Actuated"),
        (QueuePressureController, "QueuePressure"),
        (QueueSenseController, "QueueSense")
    ]

    results = {}
    for controller_class, controller_name in controllers:
        success = run_controller_test(
            controller_class, controller_name,
            net_file, route_files, output_dir, seed=42
        )
        results[controller_name] = success

    print("\n=== SUMMARY ===")
    for controller_name, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"{controller_name}: {status}")

    # Return overall success
    return all(results.values())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
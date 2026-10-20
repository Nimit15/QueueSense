#!/usr/bin/env python3
"""
Test the network with slow speed on art_east to cause queue formation and spillback.
"""

import os
import sys
from queuesense.simulation.runner import SimulationRunner
from queuesense.controllers.fixed_time import FixedTimeController
from queuesense.controllers.actuated import ActuatedController
from queuesense.controllers.queue_pressure import QueuePressureController
from queuesense.controllers.queuesense import QueueSenseController

def run_controller_test(controller_class, controller_name, net_file, route_files, output_dir, seed=42, duration=600):
    """Run a single controller test."""
    print(f"\n=== Testing {controller_name} (duration={duration}s) ===")

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
        duration=duration,
        warmup_time=0,
        controller=controller,
        gui=False,
        csv_prefix=f"{controller_name.lower()}_slow_art_east",
        seed=seed
    )

    try:
        runner.run()
        print(f"{controller_name} completed successfully")
        return True
    except Exception as e:
        print(f"{controller_name} failed: {e}")
        return False

def get_max_spillback(csv_file, column):
    import csv
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        max_val = 0
        for row in reader:
            val = int(row[column])
            if val > max_val:
                max_val = val
        return max_val

def main():
    """Test slow art_east network."""
    net_file = "D:/QueueSense/sumo/network_slow_art_east/corridor.net.xml"
    route_files = ["D:/QueueSense/sumo/routes/bottleneck_congested.rou.xml"]
    output_dir = "D:/QueueSense/results/slow_art_east_test"

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
            net_file, route_files, output_dir, seed=42, duration=600
        )
        results[controller_name] = success

    print("\n=== SLOW ART_EAST TEST RESULTS ===")
    for controller_name, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"{controller_name}: {status}")
        if success:
            csv_file = os.path.join(output_dir, f"{controller_name.lower()}_slow_art_east_*.csv")
            import glob
            csv_files = glob.glob(csv_file)
            if csv_files:
                latest = max(csv_files, key=os.path.getctime)
                max_ns = get_max_spillback(latest, 'spillback_ns')
                max_ew = get_max_spillback(latest, 'spillback_ew')
                print(f"  Max spillback_ns: {max_ns}, Max spillback_ew: {max_ew}")

    # Return overall success
    return all(results.values())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
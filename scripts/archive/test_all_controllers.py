#!/usr/bin/env python3
"""Test all 5 controllers with the light scenario."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner
from queuesense.controllers import FixedTimeController, ActuatedController, QueuePressureController, QueueSenseController

NET_FILE = "sumo/network_v2/corridor.net.xml"
ROUTE_FILE = "sumo/routes_v2/benchmark/light.rou.xml"
SEED = 42
DURATION = 300
WARMUP = 60
STEP_LENGTH = 1.0

CTRLS = ["A", "B", "C", "D1", "D2"]
CONTROLLERS = {
    "A": FixedTimeController(),
    "B": ActuatedController(gap_threshold=3.0),
    "C": QueuePressureController(alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0),
    "D1": QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0),
    "D2": QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0),
}

SCENARIO = "light"

print(f"Testing all controllers with {SCENARIO} scenario")
print("=" * 60)

output_dir = Path("results/v2_test_all2")
output_dir.mkdir(exist_ok=True)

for ctrl_id in CTRLS:
    print(f"\n--- Controller {ctrl_id} ---")
    spillback = ctrl_id in ("D1", "D2")

    runner = MultiJunctionSimulationRunner(
        net_file="sumo/network_v2/corridor.net.xml",
        route_files=["sumo/routes_v2/benchmark/light.rou.xml"],
        output_dir=str(Path("results/v2_test_all2")),
        step_length=1.0,
        duration=300,
        warmup_time=60,
        seed=42,
        use_coordinator=True,
        use_spillback_gate=spillback,
        gui=False,
        csv_prefix=f"{ctrl_id}_seed42_light",
    )

    try:
        start = time.time()
        runner.run()
        elapsed = time.time() - start

        csv_path = Path("results/v2_test_all2") / f"{ctrl_id}_seed42_light.csv"
        if csv_path.exists():
            with open(csv_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                last = rows[-1]
                print(f"  OK: {last['arrived_cumulative']} arr, {last['remaining_expected']} remain, "
                      f"{elapsed:.1f}s, {len(rows)} rows")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {str(e)[:60]}")

print("\nDone.")
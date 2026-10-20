#!/usr/bin/env python3
"""Run ONE controller × ONE scenario to verify V2 system works."""

import sys
import time
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner
from queuesense.controllers import FixedTimeController, ActuatedController, QueuePressureController, QueueSenseController

# Minimal test: light scenario + Controller A (FixedTime)
NET_FILE = "sumo/network_v2/corridor.net.xml"
ROUTE_FILE = "sumo/routes_v2/benchmark/light.rou.xml"
SEED = 42
DURATION = 300  # 5 min for quick test
WARMUP = 60
STEP_LENGTH = 1.0

print("=" * 60)
print("V2 MINIMAL SMOKE TEST: light + FixedTime (Controller A)")
print("=" * 60)

runner = MultiJunctionSimulationRunner(
    net_file=NET_FILE,
    route_files=[ROUTE_FILE],
    output_dir="results/v2_minimal_test",
    step_length=STEP_LENGTH,
    duration=DURATION,
    warmup_time=WARMUP,
    seed=SEED,
    use_coordinator=True,
    use_spillback_gate=False,
    gui=False,
    csv_prefix="A_seed42_light",
)

try:
    print("Starting simulation...")
    runner.run()
    print("SUCCESS - simulation completed")

    # Read results
    csv_path = Path("results/v2_minimal_test/A_seed42_light.csv")
    if csv_path.exists():
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            print(f"\nResults:")
            print(f"  Rows: {len(rows)}")
            print(f"  Time range: {rows[0]['time']} to {rows[-1]['time']}")
            print(f"  Arrived: {rows[-1]['arrived_cumulative']}")
            print(f"  Remaining: {rows[-1]['remaining_expected']}")
            print(f"  Column names: {list(rows[0].keys())}")
    else:
        print(f"\nERROR: CSV file not found: {csv_path}")

except Exception as e:
    print(f"\nFAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nDone.")
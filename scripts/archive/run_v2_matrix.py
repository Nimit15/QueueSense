#!/usr/bin/env python3
"""V2 diagnostic matrix: 5 scenarios × 5 controllers, sequential execution."""

import sys
import time
import json
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner
from queuesense.controllers import FixedTimeController, ActuatedController, QueuePressureController, QueueSenseController

# Configuration
NET_FILE = "sumo/network_v2/corridor.net.xml"
ROUTE_DIR = "sumo/routes_v2/benchmark"
SEED = 42
DURATION = 300     # 5 minutes per run (diagnostic horizon)
WARMUP = 60
STEP_LENGTH = 1.0

SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
CTRLS = ["A", "B", "C", "D1", "D2"]

# Initialize controllers
CONTROLLERS = {
    "A": FixedTimeController(),
    "B": ActuatedController(gap_threshold=3.0),
    "C": QueuePressureController(alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0),
    "D1": QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0),
    "D2": QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0),
)

OUTPUT_DIR = Path("results/network_v2_diagnostics")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Verify network and routes exist
assert Path(NET_FILE).exists(), "Network file not found"
for s in SCENARIOS:
    assert Path(ROUTE_DIR, f"{s}.rou.xml").exists(), f"Missing route: {s}"

print(f"V2 Diagnostic Matrix - Seed {SEED}, Duration {DURATION}s per run")
print(f"Controllers: {', '.join(CTRLS)} | Scenarios: {', '.join(SCENARIOS)}")
print(f"Total: {len(SCENARIOS) * len(CTRLS)} runs (sequential)")
print()

results = []

for scenario in SCENARIOS:
    print(f"[{scenario.upper():8s}] ", flush=True)
    route_files = [str(Path(ROUTE_DIR, f"{scenario}.rou.xml"))]

    for ctrl_id in CTRLS:
        print(f"running {ctrl_id}...", flush=True)
        spillback_gate = (ctrl_id == "D2")

        # Initialize runner
        runner = MultiJunctionSimulationRunner(
            net_file=NET_FILE,
            route_files=route_files,
            output_dir=str(OUTPUT_DIR),
            step_length=STEP_LENGTH,
            duration=DURATION,
            warmup_time=WARMUP,
            seed=SEED,
            use_coordinator=True,
            use_spillback_gate=spillback_gate,
            gui=False,
            csv_prefix=f"{ctrl_id}_seed{SEED}_{scenario}",
        )

        # Run simulation
        simulation_ok = False
        try:
            runner.run()
            simulation_ok = True
        except Exception as e:
            pass

        # Initialize result with defaults
        result = {
            "scenario": scenario,
            "controller": ctrl_id,
            "seed": SEED,
            "status": "failed",
            "runtime_s": None,
            "arrived_cumulative": 0,
            "remaining_expected": 0,
            "total_rows": 0,
            "output_file": "",
            "spillback_gate": "ON" if spillback_gate else "OFF",
            "error": None,
        }

        if simulation_ok:
            # Read results CSV
            csv_path = OUTPUT_DIR / f"{ctrl_id}_seed{SEED}_{scenario}.csv"
            if csv_path.exists():
                with open(csv_path) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    last_row = rows[-1] if rows else {}

                    result.update({
                        "status": "success",
                        "runtime_s": DURATION - WARMUP,  # approximate
                        "arrived_cumulative": int(last_row.get("arrived_cumulative", 0)),
                        "remaining_expected": int(last_row.get("remaining_expected", 0)),
                        "total_rows": len(rows),
                        "output_file": str(csv_path),
                    )

                    # Try to read spillback metrics
                    if "spillback_ns" in last_row:
                        result["spillback_ns"] = last_row["spillback_ns"]
                    if "spillback_ew" in last_row:
                        result["spillback_ew"] = last_row["spillback_ew"]

                    # Update spillback gate from CSV if present
                    if "spillback_gate" in last_row:
                        result["spillback_gate"] = last_row["spillback_gate"]

                    result["runtime_s"] = time.time() - t_start  # wall clock

                    result["spillback_gate"] = spillback_gate  # restore intended setting

                result["spillback_gate"] = spillback_gate  # intended setting

            results.append(result)

            arr = result["arrived_cumulative"]
            gate = result["spillback_gate"]
            print(f"  OK: arrived={arr} gate={gate}")
        else:
            print(f"  FAILED: simulation did not complete")
            # result already has defaults (failed status)

        results.append(result)

    print()  # blank line between scenarios

# Print summary
print(f"\nTotal: {len(results)} runs  Successful: {successful}  Failed: {failed}")

# ... etc
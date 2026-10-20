#!/usr/bin/env python3
"""Run the 25-run V2 diagnostic matrix sequentially."""

import sys
import time
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner
from queuesense.controllers import FixedTimeController, ActuatedController, QueuePressureController, QueueSenseController

# Configuration
NET_FILE = "sumo/network_v2/corridor.net.xml"
ROUTE_DIR = "sumo/routes_v2/benchmark"
SEED = 42
DURATION = 3600  # Full diagnostic horizon (3600s)
WARMUP = 300
STEP_LENGTH = 1.0
SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
OUTPUT_DIR = "results/network_v2_diagnostics"

print("=" * 70)
print("V2 25-RUN DIAGNOSTIC MATRIX")
print("=" * 70)
print(f"Seed: {SEED}")
print(f"Duration: {DURATION}s")
print(f"Warmup: {WARMUP}s")
print(f"Step length: {STEP_LENGTH}s")
print(f"Controllers: A (FixedTime), B (Actuated), C (QueuePressure), D1 (QueueSense-no-gate), D2 (QueueSense-with-gate)")
print(f"Scenarios: {', '.join(SCENARIOS)}")
print(f"Total runs: {len(SCENARIOS) * 5}")
print()

# Set up output directory
output_dir = Path(OUTPUT_DIR)
output_dir.mkdir(parents=True, exist_ok=True)

# Check network and routes exist
net_path = Path(NET_FILE)
if not net_path.exists():
    print(f"ERROR: Network file not found: {net_path}")
    sys.exit(1)

print("[OK] Network file exists")

route_files = {}
for scenario in SCENARIOS:
    route_path = Path(ROUTE_DIR) / f"{scenario}.rou.xml"
    if route_path.exists():
        route_files[scenario] = [str(route_path)]
    else:
        print(f"WARNING: Missing route: {route_path}")

print(f"Found {len(route_files)} scenario route files")
print("Running 25 scenarios × controllers sequentially...")
print()

# Run each scenario × controller combination sequentially
results = []

for scenario in SCENARIOS:
    print(f"[{scenario.upper():8s}] running all 5 controllers...")

    route_files_scenario = route_files.get(scenario, [])
    if not route_files_scenario:
        print(f"  SKIPPING: No route files found")
        continue

    for ctrl_id in ["A", "B", "C", "D1", "D2"]:
        print(f"  Controller {ctrl_id}: starting...", end=" ", flush=True)

        run_start = time.time()

        # Determine spillback gate setting
        # D1: spillback gate OFF, D2: spillback gate ON
        # A, B, C: gate OFF (they don't have the concept)
        spillback_gate = (ctrl_id == "D2")

        runner = MultiJunctionSimulationRunner(
            net_file=str(net_path),
            route_files=route_files_scenario,
            output_dir=str(output_dir),
            step_length=STEP_LENGTH,
            duration=DURATION,
            warmup_time=WARMUP,
            seed=SEED,
            use_coordinator=True,
            use_spillback_gate=spillback_gate,
            gui=False,
            csv_prefix=f"{ctrl_id}_seed{SEED}_{scenario}",
        )

        try:
            runner.run()
            elapsed = time.time() - run_start

            # Read results
            csv_file = output_dir / f"{ctrl_id}_seed{SEED}_{scenario}.csv"
            if csv_file.exists():
                with open(csv_file) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    last_row = rows[-1] if rows else {}

                    result = {
                        "scenario": scenario,
                        "controller": ctrl_id,
                        "seed": SEED,
                        "status": "success",
                        "runtime_s": elapsed,
                        "time_final": last_row.get("time", "N/A"),
                        "arrived_cumulative": int(last_row.get("arrived_cumulative", 0)),
                        "remaining_expected": int(last_row.get("remaining_expected", 0)),
                        "total_rows": len(rows),
                        "output_file": str(csv_file),
                        "spillback_gate": "ON" if spillback_gate else "OFF",
                    }

                    # Add safety metrics if present
                    if "spillback_ns" in last_row:
                        result["spillback_ns"] = last_row["spillback_ns"]
                    if "spillback_ew" in last_row:
                        result["spillback_ew"] = last_row["spillback_ew"]

                    results.append(result)
                    print(f"OK ({last_row.get('arrived_cumulative', 0)} arr, {elapsed:.1f}s)")
                except Exception as e:
                    print(f"CSV ERROR ({e})")
        except Exception as e:
            elapsed = time.time() - run_start
            results.append({
                "scenario": scenario,
                "controller": ctrl_id,
                "seed": SEED,
                "status": "failed",
                "runtime_s": elapsed,
                "error": str(e),
                "spillback_gate": "ON" if spillback_gate else "OFF",
            })
            print(f"FAILED ({str(e)[:40]} {elapsed:.1f}s)")

print()
print("=" * 70)
print(f"DIAGNOSTIC MATRIX COMPLETE")
print("=" * 70)
print(f"Total runs: {len(results)}")
successful = sum(1 for r in results if r["status"] == "success")
failed = sum(1 for r in results if r["status"] == "failed")
print(f"Successful: {successful}")
print(f"Failed: {failed}")

# Print summary table
print()
print("RESULTS TABLE:")
print("-" * 70)
print(f"{'Scenario':<10} {'Ctrl':<3} {'Status':<8} {'Arrived':<8} {'Remaining':<12} {'Runtime[s}':<10} {'Gate'}")
print("-" * 70)
for r in results:
    gate = r["spillback_gate"] if "spillback_gate" in r else "N/A"
    print(f"{r['scenario']:<10} {r['controller']:<3} {r['status']:<8} {str(r['arrived_cumulative']):<8} {str(r['remaining_expected']):<12} {r['runtime_s']:<10.1f} {gate}")

# Save results CSV
print()
print("Saving diagnostic summary...")
import json
summary = {
    "seed": SEED,
    "duration_s": DURATION,
    "runs": len(results),
    "successful": successful,
    "failed": failed,
    "runs": results
}
summary_file = Path(OUTPUT_DIR) / "diagnostic_summary.json"
with open(summary_file, "w") as f:
    json.dump(summary, f, indent=2)
print(f"Summary written to {summary_file}")

# Go/no-go recommendation
print()
if successful == 25:
    print("✓ All 25 runs completed successfully - ready for full benchmark")
elif successful >= 15:
    print("⚠ Partial completion - investigate failures before full benchmark")
else:
    print("✗ Insufficient completion - diagnose failures before full benchmark")
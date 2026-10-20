#!/usr/bin/env python3
"""Run the complete 25-run V2 diagnostic matrix sequentially."""

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
DURATION = 300  # 5 min per run for diagnostic
WARMUP = 60
STEP_LENGTH = 1.0

SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
CTRLS = ["A", "B", "C", "D1", "D2"]

CONTROLLERS = {
    "A": FixedTimeController(),
    "B": ActuatedController(gap_threshold=3.0),
    "C": QueuePressureController(alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0),
    "D1": QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0),
    "D2": QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0),
}

OUTPUT_DIR = Path("results/network_v2_diagnostics")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("V2 25-RUN DIAGNOSTIC MATRIX (sequential execution)")
print("=" * 70)
print(f"Seed: {SEED}")
print(f"Duration: {DURATION}s per run (5 min)")
print(f"Warmup: {WARMUP}s")
print(f"Controllers: A (FixedTime), B (Actuated), C (QueuePressure), D1 (QueueSense-no-gate), D2 (QueueSense-with-gate)")
print(f"Scenarios: {', '.join(SCENARIOS)}")
print(f"Total runs: {len(SCENARIOS) * len(CTRLS)}")
print()

# Check network and routes exist
if not Path(NET_FILE).exists():
    print(f"ERROR: Network file not found")
    sys.exit(1)

for scenario in SCENARIOS:
    if not Path(ROUTE_DIR) / f"{scenario}.rou.xml":
        print(f"WARNING: Missing route for {scenario}")

print("Starting sequential execution...")
print()

results = []

for scenario in SCENARIOS:
    print(f"[{scenario.upper():8s}] starting all 5 controllers...")

    route_files = [str(Path(ROUTE_DIR) / f"{scenario}.rou.xml")]

    for ctrl_id in CTRLS:
        print(f"  Controller {ctrl_id:2s}: starting...", flush=True)

        # Determine spillback gate
        spillback_gate = (ctrl_id == "D2")

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

        start_time = time.time()
        try:
            runner.run()
            elapsed = time.time() - start_time

            # Read results
            csv_path = OUTPUT_DIR / f"{ctrl_id}_seed{SEED}_{scenario}.csv"
            if csv_path.exists():
                with open(csv_path) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    last_row = rows[-1] if rows else {}

                    result = {
                        "scenario": scenario,
                        "controller": ctrl_id,
                        "seed": SEED,
                        "status": "success",
                        "runtime_s": elapsed,
                        "arrived_cumulative": int(last_row.get("arrived_cumulative", 0)),
                        "remaining_expected": int(last_row.get("remaining_expected", 0)),
                        "total_rows": len(rows),
                        "output_file": str(csv_path),
                        "spillback_gate": "ON" if spillback_gate else "OFF",
                    }
                    results.append(result)
                    print(f"  ✓ OK: {last_row.get('arrived_cumulative', 0)} arrived, {elapsed:.1f}s")
                except Exception as e:
                    print(f"  CSV ERROR: {str(e)[:60)}")
                    results.append({
                        "scenario": scenario,
                        "controller": ctrl_id,
                        "seed": SEED,
                        "status": "failed",
                        "runtime_s": elapsed,
                        "error": str(e)[:80],
                        "spillback_gate": "ON" if spillback_gate else "OFF",
                    })
        except Exception as e:
            elapsed = time.time() - start_time
            results.append({
                "scenario": scenario,
                "controller": ctrl_id,
                "seed": SEED,
                "status": "failed",
                "runtime_s": elapsed,
                "error": str(e)[:80],
                "spillback_gate": "ON" if spillback_gate else "OFF",
            })
            print(f"  ✗ FAILED: {type(e).__name__}: {str(e)[:40]} {elapsed:.1f}s")

print()
print("=" * 70)
print("DIAGNOSTIC MATRIX COMPLETE")
print("=" * 70)
successful = sum(1 for r in results if r["status"] == "success")
failed = sum(1 for r in results if r["status"] == "failed")
print(f"Total: {len(results)} runs")
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

# Save summary
print()
print("Saving diagnostic summary...")
summary = {
    "seed": SEED,
    "duration_s": DURATION,
    "total_runs": len(results),
    "successful": successful,
    "failed": failed,
    "runs": results
}
summary_file = OUTPUT_DIR / "diagnostic_summary.json"
with open(summary_file, "w") as f:
    json.dump(summary, f, indent=2)
print(f"Summary written to {summary_file}")

# Check spillback activation
print()
d1_runs = [r for r in results if r["controller"] == "D1"]
d2_runs = [r for r in results if r["controller"] == "D2"]
print("D1 vs D2 spillback comparison:")
d1_spillback_on = sum(1 for r in d1_runs if r["spillback_gate"] == "ON")
d2_spillback_on = sum(1 for r in d2_runs if r["spillback_gate"] == "ON")
print(f"  D1 (gate OFF): {d1_spillback_on} runs with gate ON (should be 0)")
print(f"  D2 (gate ON): {d2_spillback_on} runs with gate ON")

if successful == 25:
    print("\n✓ All 25 runs completed - ready for full multi-seed benchmark")
elif successful >= 15:
    print("\n⚠ Partial completion - investigate failures before full benchmark")
else:
    print("\n✗ Insufficient completion - diagnose failures before full benchmark")
#!/usr/bin/env python3
"""Definitive 250-case QueueSense benchmark runner.

Configuration:
  - Scenarios: light, balanced, uneven, bottleneck, surge (5)
  - Controllers: A, B, C, D1, D2 (5)
  - Seeds: 42-51 (10)
  - Total runs: 250

Enforces:
  - Per-junction independent mutable controller instances.
  - Per-case manifest preservation (JSON).
  - Output to results/benchmark_v2_250_isolated/ (must be new/unused).
"""

import sys
import json
import time
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.controllers import FixedTimeController, ActuatedController, QueuePressureController, QueueSenseController, ContextAwareSelector
from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner

# Parameters
NET_FILE = "sumo/network_v2/corridor.net.xml"
SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
CTRL_IDS = ["A", "B", "C", "D1", "D2", "S"]
SEEDS = range(42, 52)
DURATION = 300
WARMUP = 60
THRESHOLD = 0.30
OUTPUT_DIR = Path("results/benchmark_v2_250_isolated")

def build_controllers(ctrl_id):
    """Factory for per-junction independent instances."""
    gate_enabled = (ctrl_id == "D2")
    def _make_queuesense():
        return QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=THRESHOLD, max_wait=90.0,
            spillback_gate_enabled=gate_enabled,
        )

    if ctrl_id == "A":
        return {j: FixedTimeController() for j in ["J1", "J2", "J3"]}
    elif ctrl_id == "B":
        return {j: ActuatedController(gap_threshold=3.0) for j in ["J1", "J2", "J3"]}
    elif ctrl_id == "C":
        return {j: QueuePressureController(alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0) for j in ["J1", "J2", "J3"]}
    elif ctrl_id in ["D1", "D2"]:
        return {j: _make_queuesense() for j in ["J1", "J2", "J3"]}
    elif ctrl_id == "S":
        # Controller S: ContextAwareSelector with per-junction independent instances
        return {j: ContextAwareSelector(
            junction_id=j,
            alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0,
            spillback_threshold=THRESHOLD,
            soft_risk_threshold=0.24,
            clear_exit_threshold=0.22,
            max_staleness_s=1.0,
        ) for j in ["J1", "J2", "J3"]}
    raise ValueError(f"Unknown controller: {ctrl_id}")

def run_case(scenario, ctrl_id, seed):
    """Run single benchmark case."""
    case_id = f"{ctrl_id}_seed{seed}_{scenario}"
    case_dir = OUTPUT_DIR / scenario
    case_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing run (resume support)
    existing = case_dir / f"{case_id}_summary.json"
    if existing.exists():
        # Verify the existing run is valid (steps > 0)
        try:
            import json
            with open(existing) as f:
                summary = json.load(f)
            if summary.get("steps", 0) > 0:
                print(f"  Skipping {case_id} (already completed, {summary.get('arrived_cumulative', 0)} arrivals)")
                return {"status": "skipped", "case": case_id}
        except Exception:
            pass  # Invalid summary, will re-run

    print(f"  Running {case_id}...", end="", flush=True)

    runner = MultiJunctionSimulationRunner(
        net_file=NET_FILE,
        route_files=[f"sumo/routes_v2/benchmark/{scenario}.rou.xml"],
        output_dir=str(case_dir),
        step_length=1.0,
        duration=DURATION,
        warmup_time=WARMUP,
        seed=seed,
        controllers=build_controllers(ctrl_id),
        use_coordinator=True,
        use_spillback_gate=(ctrl_id == "D2"),
        gui=False,
        csv_prefix=case_id,
    )

    runner.run()
    print(" DONE")
    return {"status": "success", "case": case_id}

def main():
    if OUTPUT_DIR.exists():
        print(f"ERROR: Output directory {OUTPUT_DIR} already exists. Choose another version.")
        sys.exit(1)

    print(f"Starting 250-case benchmark. Output: {OUTPUT_DIR}")
    print("(Resume mode: existing valid results are preserved)")
    start = time.time()

    total = 250
    completed = 0

    for scenario in SCENARIOS:
        print(f"\nScenario: {scenario}")
        for ctrl_id in CTRL_IDS:
            for seed in SEEDS:
                run_case(scenario, ctrl_id, seed)
                completed += 1

    elapsed = time.time() - start
    print(f"\nCompleted {completed}/{total} runs in {elapsed/60:.1f} minutes")

if __name__ == "__main__":
    main()
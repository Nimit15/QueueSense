#!/usr/bin/env python3
"""Stage 5: Closed-loop SUMO benchmark of Controller S (50 cases).

Runs ContextAwareSelector (Controller S) across all 5 scenarios × 10 seeds (42..51)
using the exact V2 corridor network and routes. Output to results/stage5_selector_closed_loop/.
Resumable: skips already-completed valid S cases.
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from queuesense.controllers import (
    FixedTimeController, ActuatedController,
    QueuePressureController, QueueSenseController, ContextAwareSelector
)
from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner

# Parameters (identical to Stage 2)
NET_FILE = "sumo/network_v2/corridor.net.xml"
SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
CTRL_IDS = ["S"]  # Only Controller S for this benchmark
SEEDS = range(42, 52)
DURATION = 300
WARMUP = 60
THRESHOLD = 0.30
OUTPUT_DIR = Path("results/stage5_selector_closed_loop")

def build_controllers(ctrl_id):
    """Factory for per-junction independent instances."""
    if ctrl_id == "S":
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
        use_spillback_gate=True,  # S uses gate
        gui=False,
        csv_prefix=case_id,
    )

    runner.run()
    print(" DONE")
    return {"status": "success", "case": case_id}

def main():
    print(f"Starting Stage 5 benchmark (Controller S only). Output: {OUTPUT_DIR}")
    print("(Resume mode: existing valid results are preserved)")
    start = time.time()

    total = len(SCENARIOS) * len(CTRL_IDS) * len(SEEDS)  # 50
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
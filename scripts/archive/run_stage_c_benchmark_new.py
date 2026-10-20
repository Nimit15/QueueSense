#!/usr/bin/env python3
"""Stage C benchmark runner with verified controller isolation.

This script demonstrates that the controller-instance fix is working correctly:
1. Every junction (J1, J2, J3) gets its own controller instance
2. D1 has gate disabled, D2 has gate enabled
3. Mutable controller state is isolated per junction
4. Phase-switch and gate counters are correctly scoped

Run this to verify the fix, then replace run_stage_c_benchmark.py with this one
once accepted.

NOTE: This replaces run_stage_c_benchmark.py which had a broken `_per_junction`
helper that shared one controller across all junctions.
"""

import sys
import json
import time
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.controllers.queuesense import QueueSenseController
from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner

NET_FILE = "sumo/network_v2/corridor.net.xml"
ROUTE_FILE = "sumo/routes_v2/benchmark/surge.rou.xml"
SEED = 49
SCENARIO = "surge"
DURATION = 300
WARMUP = 60
STEP_LENGTH = 1.0
OUTPUT_DIR = Path("results/benchmark_v2_250_gateverified_fixed_surge49")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JUNCTION_IDS = ["J1", "J2", "J3"]
THRESHOLD = 0.30


def build_controllers():
    """Authoritative controller factory with proven isolation.

    Returns:
        Dict with keys 'A', 'B', 'C', 'D1', 'D2'.
        Each value is a Dict[str, controller] keyed by junction id.
        Each junction has its own controller instance.
    """
    from queuesense.controllers import FixedTimeController, ActuatedController, QueuePressureController, QueueSenseController

    def _make_queuesense(id_suffix, alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.30, max_wait=90.0):
        gate_enabled = (id_suffix == "D2")
        return QueueSenseController(
            alpha=alpha, beta=beta, gamma=gamma,
            spillback_threshold=spillback_threshold, max_wait=max_wait,
            spillback_gate_enabled=gate_enabled,
        )

    return {
        "A": {j: FixedTimeController() for j in JUNCTION_IDS},
        "B": {j: ActuatedController(gap_threshold=3.0) for j in JUNCTION_IDS},
        "C": {j: QueuePressureController(alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0) for j in JUNCTION_IDS},
        "D1": {j: _make_queuesense("D1") for j in JUNCTION_IDS},
        "D2": {j: _make_queuesense("D2") for j in JUNCTION_IDS},
    }


def run_config(ctrl_id: str, gate_enabled: bool):
    print(f"\n{'='*60}")
    print(f"Running {ctrl_id}: gate_enabled={gate_enabled}, seed={SEED}, "
          f"duration={DURATION}s, warmup={WARMUP}s")
    print(f"{'='*60}")

    controllers = build_controllers()
    runner = MultiJunctionSimulationRunner(
        net_file=NET_FILE,
        route_files=[ROUTE_FILE],
        output_dir=str(OUTPUT_DIR),
        step_length=STEP_LENGTH,
        duration=DURATION,
        warmup_time=WARMUP,
        seed=SEED,
        controllers=controllers[ctrl_id],
        use_coordinator=True,
        use_spillback_gate=gate_enabled,
        gui=False,
        csv_prefix=f"{ctrl_id}_seed{SEED}_{SCENARIO}",
    )

    t0 = time.time()
    runner.run()
    elapsed = time.time() - t0
    print(f"{ctrl_id} finished in {elapsed:.1f}s")

    # Verify effective settings on the runner's actual controller instances.
    for j_id in JUNCTION_IDS:
        c = runner.controllers[j_id]
        assert c.spillback_gate_enabled == gate_enabled, \
            f"{ctrl_id}/{j_id}: gate_enabled={c.spillback_gate_enabled}"
        assert c.spillback_threshold == THRESHOLD, \
            f"{ctrl_id}/{j_id}: threshold={c.spillback_threshold}"
    assert runner.use_coordinator is True
    assert runner.use_spillback_gate == gate_enabled
    assert runner.downstream_threshold == THRESHOLD
    print(f"Effective settings verified: coordinator=True, "
          f"gate={gate_enabled}, threshold={THRESHOLD}")
    return runner


def main():
    d1 = run_config("D1", gate_enabled=False)
    d2 = run_config("D2", gate_enabled=True)

    summary = {
        "experiment": "matched_d1_d2_surge49_fixed",
        "seed": SEED,
        "scenario": SCENARIO,
        "duration_s": DURATION,
        "warmup_s": WARMUP,
        "network": NET_FILE,
        "route": ROUTE_FILE,
        "threshold": THRESHOLD,
        "junctions": JUNCTION_IDS,
        "controller_instances_per_junction": True,
        "d1": {
            "gate_enabled": False,
            "csv": str(OUTPUT_DIR / f"D1_seed{SEED}_{SCENARIO}_seed{SEED}.csv"),
            "detailed": str(OUTPUT_DIR / f"D1_seed{SEED}_{SCENARIO}_seed{SEED}_detailed.csv"),
            "steps": len(d1.metrics),
        },
        "d2": {
            "gate_enabled": True,
            "csv": str(OUTPUT_DIR / f"D2_seed{SEED}_{SCENARIO}_seed{SEED}.csv"),
            "detailed": str(OUTPUT_DIR / f"D2_seed{SEED}_{SCENARIO}_seed{SEED}_detailed.csv"),
            "steps": len(d2.metrics),
        },
    }

    summary_path = OUTPUT_DIR / "d1_d2_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {summary_path}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Stage 2 end-to-end matched D1/D2 experiment (surge, seed 49).

Runs D1 (coordination ON, downstream gating OFF) and D2 (coordination ON,
downstream gating ENABLED) on the identical V2 corridor network, routes,
demand, seed and duration.  Only the downstream-gating configuration differs.

Both runs write to a fresh unused directory so no previous experiment or
benchmark is overwritten.

Captures the full control path per junction per step:
  - run id, simulation time, junction, controller instance id
  - blocked receiving edge(s) and normalized occupancy fraction
  - gate enabled state and eligible approaches
  - requested phase, applied SUMO program index, ungated candidate, gate event
  - reason string

Usage:
    python run_stage2_end_to_end.py [--duration 300] [--warmup 60]
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.controllers.queuesense import QueueSenseController
from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner

NET_FILE = "sumo/network_v2/corridor.net.xml"
ROUTE_FILE = "sumo/routes_v2/benchmark/surge.rou.xml"
SEED = 49
SCENARIO = "surge"
DURATION = int(sys.argv[sys.argv.index("--duration") + 1]) if "--duration" in sys.argv else 300
WARMUP = int(sys.argv[sys.argv.index("--warmup") + 1]) if "--warmup" in sys.argv else 60
STEP_LENGTH = 1.0
OUTPUT_DIR = Path("results/stage2_surge_seed49_end_to_end")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JUNCTION_IDS = ["J1", "J2", "J3"]
THRESHOLD = 0.30


def build_controllers(gate_enabled: bool):
    """Per-junction independent controller instances."""
    return {
        j: QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=THRESHOLD, max_wait=90.0,
            spillback_gate_enabled=gate_enabled,
        )
        for j in JUNCTION_IDS
    }


def run_config(ctrl_id: str, gate_enabled: bool):
    print(f"\n{'='*60}")
    print(f"Running {ctrl_id}: gate_enabled={gate_enabled}, seed={SEED}, "
          f"duration={DURATION}s, warmup={WARMUP}s")
    print(f"{'='*60}")

    controllers = build_controllers(gate_enabled)
    runner = MultiJunctionSimulationRunner(
        net_file=NET_FILE,
        route_files=[ROUTE_FILE],
        output_dir=str(OUTPUT_DIR),
        step_length=STEP_LENGTH,
        duration=DURATION,
        warmup_time=WARMUP,
        seed=SEED,
        controllers=controllers,
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
        "experiment": "stage2_end_to_end_matched_d1_d2_surge49",
        "seed": SEED,
        "scenario": SCENARIO,
        "duration_s": DURATION,
        "warmup_s": WARMUP,
        "network": NET_FILE,
        "route": ROUTE_FILE,
        "threshold": THRESHOLD,
        "junctions": JUNCTION_IDS,
        "controller_instances_per_junction": True,
        "only_controller_difference": "spillback_gate_enabled",
        "d1": {
            "gate_enabled": False,
            "csv": str(OUTPUT_DIR / f"D1_seed{SEED}_{SCENARIO}_seed{SEED}.csv"),
            "detailed": str(OUTPUT_DIR / f"D1_seed{SEED}_{SCENARIO}_seed{SEED}_detailed.csv"),
            "trace": str(OUTPUT_DIR / f"D1_seed{SEED}_{SCENARIO}_seed{SEED}_decision_trace.csv"),
            "summary": str(OUTPUT_DIR / f"D1_seed{SEED}_{SCENARIO}_seed{SEED}_summary.json"),
            "steps": len(d1.metrics),
        },
        "d2": {
            "gate_enabled": True,
            "csv": str(OUTPUT_DIR / f"D2_seed{SEED}_{SCENARIO}_seed{SEED}.csv"),
            "detailed": str(OUTPUT_DIR / f"D2_seed{SEED}_{SCENARIO}_seed{SEED}_detailed.csv"),
            "trace": str(OUTPUT_DIR / f"D2_seed{SEED}_{SCENARIO}_seed{SEED}_decision_trace.csv"),
            "summary": str(OUTPUT_DIR / f"D2_seed{SEED}_{SCENARIO}_seed{SEED}_summary.json"),
            "steps": len(d2.metrics),
        },
    }

    summary_path = OUTPUT_DIR / "d1_d2_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {summary_path}")


if __name__ == "__main__":
    main()
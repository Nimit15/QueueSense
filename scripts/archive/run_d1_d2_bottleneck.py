#!/usr/bin/env python3
"""Matched D1/D2 bottleneck experiment (seed 42).

Runs D1 (coordination ON, downstream gating OFF) and D2 (coordination ON,
downstream gating ENABLED) on the identical V2 corridor network, routes,
demand, seed and duration.  Only the downstream-gating configuration differs.

Produces, per run:
  - main CSV: per-step metrics with per-receiving-edge occupancy, threshold
    crossings, eligibility, gate-suppression flags and applied phase.
  - detailed CSV: per-receiving-edge audit trail (one row per edge per step).
  - summary JSON: gate-intervention inventory with ungated vs applied phases.

Usage:
    python run_d1_d2_bottleneck.py [--duration 300] [--seed 42]
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.controllers.queuesense import QueueSenseController
from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner

NET_FILE = "sumo/network_v2/corridor.net.xml"
ROUTE_FILE = "sumo/routes_v2/benchmark/bottleneck.rou.xml"
SEED = 42
DURATION = int(sys.argv[sys.argv.index("--duration") + 1]) if "--duration" in sys.argv else 300
WARMUP = 60
STEP_LENGTH = 1.0
OUTPUT_DIR = Path(sys.argv[sys.argv.index("--output-dir") + 1]) if "--output-dir" in sys.argv else Path("results/d1_d2_bottleneck_seed42")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JUNCTION_IDS = ["J1", "J2", "J3"]
THRESHOLD = 0.30


def build_controllers(gate_enabled: bool):
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
        csv_prefix=f"{ctrl_id}_seed{SEED}_bottleneck",
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
        "experiment": "matched_d1_d2_bottleneck",
        "seed": SEED,
        "duration_s": DURATION,
        "warmup_s": WARMUP,
        "network": NET_FILE,
        "route": ROUTE_FILE,
        "threshold": THRESHOLD,
        "junctions": JUNCTION_IDS,
        "d1": {
            "gate_enabled": False,
            "csv": str(OUTPUT_DIR / "D1_seed42_bottleneck_seed42.csv"),
            "detailed": str(OUTPUT_DIR / "D1_seed42_bottleneck_seed42_detailed.csv"),
            "steps": len(d1.metrics),
        },
        "d2": {
            "gate_enabled": True,
            "csv": str(OUTPUT_DIR / "D2_seed42_bottleneck_seed42.csv"),
            "detailed": str(OUTPUT_DIR / "D2_seed42_bottleneck_seed42_detailed.csv"),
            "steps": len(d2.metrics),
        },
    }

    summary_path = OUTPUT_DIR / "d1_d2_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary written to {summary_path}")


if __name__ == "__main__":
    main()
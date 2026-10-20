#!/usr/bin/env python3
"""Run the 25-run V2 diagnostic matrix, filling in what exists and running missing cases.

This script:
1. Checks what's already in results/network_v2_diagnostics/
2. Runs only the missing cases
3. Validates each run's completion
4. Produces a diagnostic_summary.json manifest
"""

import sys
import time
import csv
import json
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner
from queuesense.controllers import FixedTimeController, ActuatedController, QueuePressureController, QueueSenseController

# Configuration
NET_FILE = "sumo/network_v2/corridor.net.xml"
ROUTE_DIR = "sumo/routes_v2/benchmark"
SEED = 42
DURATION = 300     # 5 min per run (diagnostic horizon - full horizon)
WARMUP = 60
STEP_LENGTH = 1.0

SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
CTRLS = ["A", "B", "C", "D1", "D2"]

# Initialize controllers.  Each entry MUST be a Dict[str, controller] keyed by
# junction id, because MultiJunctionSimulationRunner looks up
# self.controllers[j_id].state for phase reporting.  A bare controller instance
# breaks with "'FixedTimeController' object is not subscriptable".
def _per_junction(ctrl):
    return {j: ctrl for j in ["J1", "J2", "J3"]}


CONTROLLERS = {
    "A": _per_junction(FixedTimeController()),
    "B": _per_junction(ActuatedController(gap_threshold=3.0)),
    "C": _per_junction(QueuePressureController(alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0)),
    # Threshold expressed as a verified fraction: 0.30 = 30% normalized occupancy
    # (traci.edge.getLastStepOccupancy() returns a fraction in SUMO 1.28.0).
    # 0.85 would require 85% occupancy, which the bottleneck scenario never
    # reaches, so the downstream gate could never activate.
    # D1: coordination ON, downstream gating OFF (gate disabled at the controller)
    "D1": QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.30, max_wait=90.0, spillback_gate_enabled=False),
    # D2: same coordination configuration, downstream gating ON
    "D2": QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.30, max_wait=90.0, spillback_gate_enabled=True),
}

OUTPUT_DIR = Path("results/network_v2_diagnostics")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Step 1: Audit existing runs ---
print(f"=== V2 Diagnostic Matrix (seed={SEED}) ===")
print(f"Configured duration: {DURATION}s, warmup: {WARMUP}s")

# Scan existing CSV files
existing_runs = {}
if OUTPUT_DIR.exists():
    for csv_file in OUTPUT_DIR.glob("*.csv"):
        name = csv_file.stem  # e.g. A_seed42_light_seed42
        # Parse: CTRL_seedSEED_scenario
        parts = name.split('_')
        ctrl = None
        scenario = None
        seed_num = None

        for i, token in enumerate(name.split('_')):
            if i > 0 and len(token) == 1 and token.isalpha():
                ctrl = token
            elif token.startswith('seed') and len(token) > 4:
                try:
                    seed_num = int(token[5:])
                except ValueError:
                    pass
                # scenario is the last part before seed
                # Actually pattern is: CTRL_seedSEED_scenario
                # But our csv_prefix is: ctrl_id_seedSEED_scenario
                # So stem = ctrl_seedSEED_scenario
                # Let me re-parse properly
                pass

        # Better parse: stem format is CTRL_seedSEED_scenario
        # Example: A_seed42_light -> ctrl=A, seed=42, scenario=light
        # But last part may or may not have scenario

        # Let me use a different approach - read the file and check status
        with open(csv_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                last_row = rows[-1]
                arrived = int(last_row.get('arrived_cumulative', 0))
                remaining = int(last_row.get('remaining_expected', 0))
                time_val = float(last_row.get('time', 0))
                status = 'success' if abs(float(last_row.get('time', 0)) - DURATION) < 30 else 'partial'

                # Parse filename to get controller and scenario
                # stem = ctrl_seed{SEED}_{scenario}
                # But our naming: {ctrl}_seed{SEED}_{scenario}.csv
                # e.g. A_seed42_light.csv
                # But our naming was: {ctrl}_seed{SEED}_{scenario}.csv -> stem is ctrl_seed{SEED}_{scenario}

                # Actually our csv_prefix is: f"{ctrl_id}_seed{SEED}_{scenario}"
                # So stem = {ctrl}_seed{SEED}_{scenario}
                # Example: A_seed42_light

                # Let me just record what we have
                run_key = (name,)
                existing_runs[name] = {
                    'status': status,
                    'arrived': arrived,
                    'remaining': remaining,
                    'time': time_val,
                    'rows': len(rows),
                    'csv_path': str(csv_file),
                }

    print(f"\nFound {len(list(OUTPUT_DIR.glob('*.csv')))} existing runs in diagnostic dir")

    # Print existing runs
    for name, info in sorted(existing_runs.items()):
        print(f"  {name}: status={info['status']}, arrived={info['arrived']}, remaining={info['remaining']}, time={info['time']:.1f}s, rows={info['rows']}")

    print()

    # Determine which runs we need to execute
    needed_runs = []
    for scenario in SCENARIOS:
        for ctrl_id in CTRLS:
            # Runner appends _seed{SEED} to the csv_prefix, so the on-disk
            # filename is {ctrl}_seed{SEED}_{scenario}_seed{SEED}.csv
            csv_name = f"{ctrl_id}_seed{SEED}_{scenario}_seed{SEED}"
            csv_path = OUTPUT_DIR / f"{csv_name}.csv"

            if not csv_path.exists():
                needed_runs.append((scenario, ctrl_id))
            else:
                # Check if it validates
                with open(csv_path) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows:
                        last = rows[-1]
                        if abs(float(last.get('time', 0)) - DURATION) < 30:
                            # Valid completed run
                            pass
                        else:
                            # Incomplete - need to rerun
                            needed_runs.append((scenario, ctrl_id))
                    else:
                        needed_runs.append((scenario, ctrl_id))

    print(f"Needed runs: {len(needed_runs)} out of 25 total")
    for scenario, ctrl in needed_runs:
        print(f"  Missing: {scenario} + {ctrl}")

    if not needed_runs:
        print("\nAll 25 runs already complete!")
        # Produce summary
        print("\nProducing manifest...")
        all_csvs = sorted(OUTPUT_DIR.glob("*.csv"))
        runs_data = []
        for csv_path in all_csvs:
            # Only the main per-step CSVs carry arrived_cumulative; the
            # _detailed audit CSVs have a different schema and must be skipped.
            parts = csv_path.stem.split('_')
            # stem = {ctrl}_seed{SEED}_{scenario}_seed{SEED}  (4 underscore parts)
            # The _detailed audit CSVs add a 5th part and must be skipped.
            if len(parts) != 4 or parts[1] != f"seed{SEED}" or parts[3] != f"seed{SEED}":
                continue
            with open(csv_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    last = rows[-1]
                    ctrl = parts[0]
                    scenario = parts[2]
                    runs_data.append({
                        'scenario': scenario,
                        'controller': ctrl,
                        'seed': SEED,
                        'status': 'success',
                        'arrived_cumulative': int(last.get('arrived_cumulative', 0)),
                        'remaining_expected': int(last.get('remaining_expected', 0)),
                        'total_rows': len(rows),
                        'output_file': str(csv_path),
                        'time_final': float(last.get('time', 0)),
                    })

        # Manifest must cover exactly the 25 required cases; extra diagnostic
        # variants (DEEP/REPRO/TRACE) are audit artifacts, not benchmark cases.
        required = {(s, c) for s in SCENARIOS for c in CTRLS}
        runs_data = [r for r in runs_data if (r['scenario'], r['controller']) in required]
        assert len(runs_data) == 25, f"Expected 25 required cases, found {len(runs_data)}"

        summary = {
            'seed': SEED,
            'duration_s': DURATION,
            'total_runs': len(runs_data),
            'successful': len(runs_data),
            'failed': 0,
            'runs': runs_data
        }

        summary_path = OUTPUT_DIR / "diagnostic_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\nSummary written to {summary_path}")
        print(f"\nAcceptance: {'READY' if len(runs_data) == 25 else 'PARTIAL'}")
        sys.exit(0)

    # --- Step 2: Run missing cases ---
    print(f"\nRunning {len(needed_runs)} missing diagnostic cases sequentially...")
    print()

    successful = 0
    failed = 0
    results = []

    for scenario, ctrl_id in needed_runs:
        spillback_gate = (ctrl_id == "D2")
        t0 = time.time()

        runner = MultiJunctionSimulationRunner(
            net_file="sumo/network_v2/corridor.net.xml",
            route_files=[f"{ROUTE_DIR}/{scenario}.rou.xml"],
            output_dir=str(OUTPUT_DIR),
            step_length=1.0,
            duration=DURATION,
            warmup_time=WARMUP,
            seed=SEED,
            controllers=CONTROLLERS[ctrl_id],
            use_coordinator=True,
            use_spillback_gate=spillback_gate,
            gui=False,
            csv_prefix=f"{ctrl_id}_seed{SEED}_{scenario}",
        )

        ok = False
        err = None
        try:
            runner.run()
            ok = True
        except Exception as e:
            err = f"{type(e).__name__}: {e}"

        elapsed = time.time() - t0

        # Read results
        csv_path = OUTPUT_DIR / f"{ctrl_id}_seed{SEED}_{scenario}.csv"
        result = {
            'scenario': scenario,
            'controller': ctrl_id,
            'seed': SEED,
            'status': 'failed',
            'runtime_s': elapsed,
            'error': err,
            'spillback_gate': 'ON' if spillback_gate else 'OFF',
        }

        if ok and csv_path.exists():
            with open(csv_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                last = rows[-1] if rows else {}

                result.update({
                    'status': 'success',
                    'arrived_cumulative': int(last.get('arrived_cumulative', 0)),
                    'remaining_expected': int(last.get('remaining_expected', 0)),
                    'total_rows': len(rows),
                    'output_file': str(csv_path),
                    'spillback_gate': 'ON' if spillback_gate else 'OFF',
                })

                # Try spillback metrics
                if 'spillback_ns' in last:
                    result['spillback_ns'] = last['spillback_ns']
                if 'spillback_ew' in last:
                    result['spillback_ew'] = last['spillback_ew']

                result['runtime_s'] = elapsed
                successful += 1
        else:
            failed += 1

        results.append(result)
        gate = result['spillback_gate']
        status_marker = 'OK' if result['status'] == 'success' else 'FAIL'
        arrived_str = str(result.get('arrived_cumulative', 'N/A'))
        err_str = f" err={result['error']}" if result.get('error') else ""
        print(f"  [{scenario:10s}] {ctrl_id:2s}: {status_marker} arrived={arrived_str} rt={elapsed:.1f}s gate={gate}{err_str}")

    # Save summary
    successful_total = sum(1 for r in results if r['status'] == 'success')
    failed_total = sum(1 for r in results if r['status'] == 'failed')

    summary = {
        'seed': SEED,
        'duration_s': DURATION,
        'total_runs': len(results),
        'successful': successful,
        'failed': failed,
        'runs': results
    }

    summary_path = OUTPUT_DIR / "diagnostic_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"DIAGNOSTIC MATRIX COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total: {len(results)} runs")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"\nSummary: {summary_path}")

    # Acceptance decision
    if successful == 25:
        print("\n✓ ALL 25 RUNS COMPLETE - READY for full benchmark")
    elif successful >= 15:
        print(f"\n⚠ PARTIAL: {successful}/{successful+failed} complete - review before benchmark")
    else:
        print(f"\n✗ INSUFFICIENT: {successful}/{25} complete - diagnose before benchmark")

    # Final acceptance decision
    if successful == 25:
        decision = "READY FOR FULL BENCHMARK"
    else:
        decision = "NOT READY - diagnose failures"

    print(f"\nACCEPTANCE: {decision}")

    # Final manifest
    print("\n=== MANIFEST ===")
    for r in sorted(results, key=lambda x: (x['scenario'], x['controller'])):
        gate = r['spillback_gate']
        arr = r.get('arrived_cumulative', 'N/A')
        err = f" {r['error']}" if r.get('error') else ""
        print(f"  {r['scenario']:10s} {r['controller']:2s}: {r['status']:8s} arr={arr} gate={gate}{err}")

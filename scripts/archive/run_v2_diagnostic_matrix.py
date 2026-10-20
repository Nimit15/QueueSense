#!/usr/bin/env python3
"""Run the 25-run V2 diagnostic matrix, filling in what exists and running missing cases."""

import sys
import time
import json
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner
from queuesense.controllers import FixedTimeController, ActuatedController, QueuePressureController, QueueSenseController

NET_FILE = "sumo/network_v2/corridor.net.xml"
ROUTE_DIR = "sumo/routes_v2/benchmark"
SEED = 42
DURATION = 300
WARMUP = 60

SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
CTRLS = ["A", "B", "C", "D1", "D2"]

OUTPUT_DIR = Path("results/network_v2_diagnostics")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

existing_runs = {}
if OUTPUT_DIR.exists():
    for csv_file in OUTPUT_DIR.glob("*.csv"):
        name = csv_file.stem
        with open(csv_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                last_row = rows[-1]
                arrived = int(last_row.get('arrived_cumulative', 0))
                remaining = int(last_row.get('remaining_expected', 0))
                time_val = float(last_row.get('time', 0))
                status = 'success' if abs(time_val - DURATION) < 30 else 'partial'
                existing_runs[name] = {
                    'status': status,
                    'arrived': arrived,
                    'remaining': remaining,
                    'time': time_val,
                    'rows': len(rows),
                    'csv_path': str(csv_file),
                }

print(f"=== V2 Diagnostic Matrix (seed={SEED}) ===")
print(f"Duration: {DURATION}s, warmup: {WARMUP}s")
print(f"\nFound {len(existing_runs)} existing runs")
for name, info in sorted(existing_runs.items()):
    print(f"  {name}: arrived={info['arrived']}, time={info['time']:.1f}s, rows={info['rows']}")

needed_runs = []
for scenario in SCENARIOS:
    for ctrl_id in CTRLS:
        csv_name = f"{ctrl_id}_seed{SEED}_{scenario}"
        csv_path = OUTPUT_DIR / f"{csv_name}_seed{SEED}.csv"
        csv_path_alt = OUTPUT_DIR / f"{csv_name}.csv"
        found = False
        for path in [csv_path, csv_path_alt]:
            if path.exists():
                with open(path) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows:
                        last = rows[-1]
                        if abs(float(last.get('time', 0)) - DURATION) < 30:
                            found = True
                            break
        if not found:
            needed_runs.append((scenario, ctrl_id))

print(f"\nNeeded runs: {len(needed_runs)} out of 25 total")
for scenario, ctrl in needed_runs:
    print(f"  Missing: {scenario} + {ctrl}")

if not needed_runs:
    print("\nAll 25 runs already complete!")
    sys.exit(0)

print(f"\nRunning {len(needed_runs)} missing cases sequentially...")
successful = 0
failed = 0
results = []

SPILLBACK_THRESHOLD = 0.30

for scenario, ctrl_id in needed_runs:
    t0 = time.time()

    if ctrl_id == "A":
        controllers = {f"J{i}": FixedTimeController() for i in [1, 2, 3]}
        spillback_gate = False
    elif ctrl_id == "B":
        controllers = {f"J{i}": ActuatedController(gap_threshold=3.0) for i in [1, 2, 3]}
        spillback_gate = False
    elif ctrl_id == "C":
        controllers = {f"J{i}": QueuePressureController(alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0) for i in [1, 2, 3]}
        spillback_gate = False
    elif ctrl_id == "D1":
        controllers = {f"J{i}": QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=SPILLBACK_THRESHOLD,
            max_wait=90.0, spillback_gate_enabled=False) for i in [1, 2, 3]}
        spillback_gate = False  # D1: gate OFF
    elif ctrl_id == "D2":
        controllers = {f"J{i}": QueueSenseController(
            alpha=0.4, beta=0.4, gamma=0.2,
            spillback_threshold=SPILLBACK_THRESHOLD,
            max_wait=90.0, spillback_gate_enabled=True) for i in [1, 2, 3]}
        spillback_gate = True  # D2: gate ON
    else:
        print(f"  [{scenario}] {ctrl_id}: Unknown controller")
        continue

    runner = MultiJunctionSimulationRunner(
        net_file="sumo/network_v2/corridor.net.xml",
        route_files=[f"{ROUTE_DIR}/{scenario}.rou.xml"],
        output_dir=str(OUTPUT_DIR),
        step_length=1.0,
        duration=DURATION,
        warmup_time=WARMUP,
        seed=SEED,
        controllers=controllers,
        use_coordinator=(ctrl_id in ("D1", "D2")),
        use_spillback_gate=spillback_gate,
        gui=False,
        csv_prefix=f"{ctrl_id}_seed{SEED}_{scenario}",
    )

    ok = False
    try:
        runner.run()
        ok = True
    except Exception as e:
        print(f"  [{scenario}] {ctrl_id}: Exception: {str(e)[:80]}")

    elapsed = time.time() - t0
    csv_path = OUTPUT_DIR / f"{ctrl_id}_seed{SEED}_{scenario}_seed{SEED}.csv"

    result = {
        'scenario': scenario,
        'controller': ctrl_id,
        'seed': SEED,
        'status': 'failed',
        'runtime_s': elapsed,
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
            })
            successful += 1
    else:
        failed += 1

    results.append(result)
    status_marker = 'OK' if result['status'] == 'success' else 'FAIL'
    print(f"  [{scenario:10s}] {ctrl_id:2s}: {status_marker} arr={result.get('arrived_cumulative', 0)} rt={elapsed:.1f}s gate={result['spillback_gate']}")

# Include existing successful runs
for name, info in existing_runs.items():
    if info['status'] == 'success':
        parts = name.split('_')
        ctrl = parts[0]
        scenario = parts[2] if len(parts) > 2 else 'unknown'
        successful += 1
        results.append({
            'scenario': scenario,
            'controller': ctrl,
            'seed': SEED,
            'status': 'success',
            'arrived_cumulative': info['arrived'],
            'remaining_expected': info['remaining'],
            'total_rows': info['rows'],
            'output_file': info['csv_path'],
            'spillback_gate': 'OFF' if ctrl != 'D2' else 'ON',
        })

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
print(f"Total: {len(results)}, Successful: {successful}, Failed: {failed}")
print(f"Summary: {summary_path}")

if successful == 25:
    print("\nALL 25 RUNS COMPLETE - READY for full benchmark")
elif successful >= 15:
    print(f"\nPARTIAL: {successful}/25 complete")
else:
    print(f"\nINSUFFICIENT: {successful}/25 complete")

print("\n=== MANIFEST ===")
for r in sorted(results, key=lambda x: (x['scenario'], x['controller'])):
    print(f"  {r['scenario']:10s} {r['controller']:2s}: {r['status']:8s} arr={r.get('arrived_cumulative', 0):3d} gate={r['spillback_gate']}")
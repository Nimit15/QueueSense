"""Independent benchmark matrix audit script.

Reconstructs the expected 250-case identity matrix and validates actual artifacts.
Expected matrix: 5 controllers x 5 scenarios x 10 seeds = 250 unique identities.
"""

import json
import csv
import re
from pathlib import Path
from collections import defaultdict

def parse_filename_to_identity(fname_stem):
    """Parse a summary file stem (without _summary.json) to (controller, scenario, seed).

    Handles two formats:
    - A_seed42_light_seed42 (from run_benchmark_matrix.py)
    - D2_seed42_surge (from resume_benchmark.py)
    """
    # Use regex to extract: controller, seed, scenario
    # Format 1: A_seed42_light_seed42
    # Format 2: D2_seed42_surge
    # Pattern: (controller)_seed(seed)_(scenario)(?:_seed(seed))?

    # Split by _seed
    parts = fname_stem.split('_seed')
    # parts[0] = controller, parts[1] starts with seed number

    if len(parts) >= 2:
        controller = parts[0]
        if len(parts) == 3:
            # Format 1: A_seed42_light_seed42 -> ['A', '42_light', '42']
            seed = int(parts[1].split('_')[0])
            scenario = parts[1].split('_', 1)[1]
            return controller, scenario, seed
        elif len(parts) == 2:
            # Format 2: D2_seed42_surge -> ['D2', '42_surge']
            rest = parts[1].split('_')
            seed = int(rest[0])
            scenario = rest[1]
            return controller, scenario, seed

    return None, None, None

def audit_benchmark():
    output_dir = Path("results/benchmark_v2_250_isolated")
    scenarios = ["light", "balanced", "uneven", "bottleneck", "surge"]
    controllers = ["A", "B", "C", "D1", "D2"]
    seeds = range(42, 52)

    # Build expected identities
    expected_identities = []
    for s in scenarios:
        for c in controllers:
            for seed in seeds:
                case_id = f"{c}_seed{seed}_{s}"
                expected_identities.append(case_id)

    # Build expected dict: case_id -> (controller, scenario, seed)
    expected_map = {}
    for case_id in expected_identities:
        parts = case_id.split('_seed')
        ctrl = parts[0]
        rest = parts[1].split('_')
        seed = int(rest[0])
        scenario = rest[1]
        expected_map[case_id] = (ctrl, scenario, seed)

    print(f"Expected identities: {len(expected_identities)}")
    assert len(expected_identities) == 250, f"Expected 250 identities, got {len(expected_identities)}"

    # Ledger
    ledger = {}
    for case_id in expected_identities:
        ledger[case_id] = {
            "status": "MISSING",
            "controller": None,
            "scenario": None,
            "seed": None,
            "path": None,
            "csv_path": None,
            "steps": None,
            "arrived": None,
            "error": None,
        }

    # Track all summary files found
    all_summary_files = []

    # Scan output directories
    for scenario in scenarios:
        scenario_dir = output_dir / scenario
        if not scenario_dir.exists():
            print(f"WARNING: scenario directory missing: {scenario_dir}")
            continue

        for summary_file in sorted(scenario_dir.glob("*_summary.json")):
            all_summary_files.append(str(summary_file))

    print(f"Total summary files found: {len(all_summary_files)}")

    # First pass: collect and validate all summary files
    validated_cases = {}  # case_id -> list of valid summary file paths
    corrupt_files = []
    invalid_files = []

    for summary_file in all_summary_files:
        sf = Path(summary_file)
        fname = sf.stem  # remove .json
        if fname.endswith("_summary"):
            fname = fname[:-len("_summary")]

        try:
            with open(sf, 'r') as f:
                raw = f.read()

            if not raw.strip():
                corrupt_files.append((str(sf), "empty file"))
                continue

            data = json.loads(raw)
        except json.JSONDecodeError as e:
            corrupt_files.append((str(sf), f"JSON decode error: {e}"))
            continue

        # Determine format and extract identity
        ctrl = data.get("controller")
        scen = data.get("scenario")
        seed = data.get("seed")

        if ctrl is None or scen is None or seed is None:
            # Try parsing from filename
            ctrl, scen, seed = parse_filename_to_identity(fname)
            if ctrl is None:
                invalid_files.append((str(sf), "Cannot parse filename"))
                continue
            case_id = f"{ctrl}_seed{seed}_{scen}"
        else:
            case_id = f"{ctrl}_seed{seed}_{scen}"

        # Validate this is an expected identity
        if case_id not in expected_map:
            invalid_files.append((str(sf), f"Unexpected case_id: {case_id}"))
            continue

        # Validate summary content
        steps = data.get("steps", 0)
        arrived = data.get("arrived_cumulative", 0)

        # Check CSV exists - match by controller_seed_scenario pattern
        csv_found = False
        csv_path = None

        for csv_file in sf.parent.glob(f"{ctrl}_seed{seed}_{scen}*.csv"):
            if csv_file.name.endswith(".csv") and not csv_file.name.endswith("_decision_trace.csv") and not csv_file.name.endswith("_detailed.csv"):
                csv_found = True
                csv_path = str(csv_file)
                break

        is_valid = steps > 0 and csv_found

        if is_valid:
            if case_id not in validated_cases:
                validated_cases[case_id] = []
            validated_cases[case_id].append({
                "summary_path": str(sf),
                "csv_path": csv_path,
                "steps": steps,
                "arrived": arrived,
                "data": data,
            })
        else:
            invalid_files.append((str(sf), f"steps={steps}, csv_found={csv_found}"))

    # Build final ledger
    duplicates_found = []
    for case_id in expected_identities:
        ctrl, scen, seed = expected_map[case_id]
        ledger[case_id]["controller"] = ctrl
        ledger[case_id]["scenario"] = scen
        ledger[case_id]["seed"] = seed

        results = validated_cases.get(case_id, [])
        if len(results) == 0:
            # Check if there were corrupt/invalid files for this case
            found_invalid = [f for f in invalid_files if case_id in f[0] or (ctrl in f[0] and f"seed{seed}" in f[0] and scen in f[0])]
            found_corrupt = [f for f in corrupt_files if case_id in f[0] or (ctrl in f[0] and f"seed{seed}" in f[0] and scen in f[0])]

            if found_corrupt:
                ledger[case_id]["status"] = "CORRUPT_JSON"
                ledger[case_id]["error"] = found_corrupt[0][1]
                ledger[case_id]["path"] = found_corrupt[0][0]
            elif found_invalid:
                ledger[case_id]["status"] = "INCOMPLETE"
                ledger[case_id]["error"] = found_invalid[0][1]
                ledger[case_id]["path"] = found_invalid[0][0]
            else:
                ledger[case_id]["status"] = "MISSING"
        elif len(results) == 1:
            ledger[case_id]["status"] = "COMPLETED_VALID"
            ledger[case_id]["path"] = results[0]["summary_path"]
            ledger[case_id]["csv_path"] = results[0]["csv_path"]
            ledger[case_id]["steps"] = results[0]["steps"]
            ledger[case_id]["arrived"] = results[0]["arrived"]
        else:
            # Multiple valid results - mark as duplicate, pick best one
            ledger[case_id]["status"] = "DUPLICATE"
            ledger[case_id]["path"] = results[0]["summary_path"]
            ledger[case_id]["csv_path"] = results[0]["csv_path"]
            ledger[case_id]["steps"] = results[0]["steps"]
            ledger[case_id]["arrived"] = results[0]["arrived"]
            ledger[case_id]["duplicate_paths"] = [r["summary_path"] for r in results[1:]]
            duplicates_found.append(case_id)

    # Count
    stats = defaultdict(int)
    for k, v in ledger.items():
        stats[v["status"]] += 1

    print("\n=== Ledger Statistics ===")
    for status, count in sorted(stats.items()):
        print(f"  {status}: {count}")

    print("\n=== Per-scenario breakdown ===")
    for scenario in scenarios:
        counts = defaultdict(int)
        for case_id, info in ledger.items():
            if info.get("scenario") == scenario:
                counts[info["status"]] += 1
        print(f"  {scenario}: {dict(counts)}")

    print("\n=== Per-controller breakdown ===")
    for controller in controllers:
        counts = defaultdict(int)
        for case_id, info in ledger.items():
            if info.get("controller") == controller:
                counts[info["status"]] += 1
        print(f"  {controller}: {dict(counts)}")

    # List missing
    missing = [k for k, v in ledger.items() if v["status"] == "MISSING"]
    print(f"\n=== Missing cases ({len(missing)}) ===")
    for m in sorted(missing):
        print(f"  {m}")

    # List corrupt
    corrupt = [k for k, v in ledger.items() if v["status"] == "CORRUPT_JSON"]
    print(f"\n=== Corrupt JSON cases ({len(corrupt)}) ===")
    for c in sorted(corrupt):
        print(f"  {c} -> {ledger[c].get('path')} ({ledger[c].get('error')})")

    # List duplicates
    print(f"\n=== Duplicate cases ({len(duplicates_found)}) ===")
    for d in sorted(duplicates_found):
        print(f"  {d}: {ledger[d]['path']}")
        for dup in ledger[d].get("duplicate_paths", []):
            print(f"    duplicate: {dup}")

    # Verify CSV existence for valid cases
    print("\n=== CSV existence validation ===")
    missing_csv_count = 0
    for case_id, info in ledger.items():
        if info["status"] in ("COMPLETED_VALID", "DUPLICATE"):
            if info.get("csv_path") is None:
                missing_csv_count += 1
                print(f"  CSV missing for {case_id}")
    print(f"  Total CSVs missing: {missing_csv_count}")

    # Verify D1 vs D2 gate config
    print("\n=== GATE CONFIG VERIFICATION ===")
    for controller in ["D1", "D2"]:
        controller_cases = [k for k, v in ledger.items() if v.get("controller") == controller and v["status"] in ("COMPLETED_VALID", "DUPLICATE")]
        mismatches = []
        for case_id in controller_cases:
            summary_path = ledger[case_id].get("path")
            if summary_path:
                try:
                    with open(summary_path) as f:
                        data = json.load(f)
                    gate = data.get("spillback_gate")
                    expected = controller == "D2"
                    if gate != expected:
                        mismatches.append(f"{case_id}: gate={gate}, expected={expected}")
                except Exception as e:
                    mismatches.append(f"{case_id}: corrupt summary ({e})")
        if mismatches:
            for m in mismatches:
                print(f"  MISMATCH: {m}")
        else:
            print(f"  {controller}: all {len(controller_cases)} cases verified (spillback_gate={'true' if controller=='D2' else 'false'})")

    # Save ledger
    output_dir_analysis = output_dir / "analysis"
    output_dir_analysis.mkdir(parents=True, exist_ok=True)

    with open(output_dir_analysis / "case_ledger.json", "w") as f:
        json.dump(ledger, f, indent=2)

    with open(output_dir_analysis / "case_ledger.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["case_id", "controller", "scenario", "seed", "status", "path", "csv_path", "steps", "arrived", "error"])
        for case_id in sorted(ledger.keys()):
            row = ledger[case_id]
            writer.writerow([case_id, row.get("controller", ""), row.get("scenario", ""),
                             row.get("seed", ""), row["status"], row.get("path", ""),
                             row.get("csv_path", ""), row.get("steps", ""),
                             row.get("arrived", ""), row.get("error", "")])

    print(f"\nLedger saved to {output_dir_analysis}")
    return ledger

if __name__ == "__main__":
    audit_benchmark()

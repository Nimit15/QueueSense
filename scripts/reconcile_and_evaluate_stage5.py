#!/usr/bin/env python3
"""
Stage 5: Closed-loop SUMO benchmark of Controller S (50 cases).
Runs ContextAwareSelector (Controller S) across all 5 scenarios × 10 seeds (42..51)
using the exact V2 corridor network and routes. Output to results/stage5_selector_closed_loop/.
Resumable: skips already-completed valid S cases.

Stage 2 (reconciliation): Additional held-out generalization benchmark on unseen seeds (52, 53).
Compares S against all baselines (A, B, C, D1, D2) to verify that the 50-seed benchmark
actually generalizes to out-of-sample seeds.
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from queuesense.controllers import (
    FixedTimeController, ActuatedController,
    QueuePressureController, QueueSenseController, ContextAwareSelector
)
from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner

# Parameters
NET_FILE = "sumo/network_v2/corridor.net.xml"
SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
CTRL_IDS = ["A", "B", "C", "D1", "D2", "S"]
SEEDS_TRAIN = range(42, 52)  # Stage 5: training seeds
SEEDS_HOLDOUT = [52, 53]    # New: held-out seeds for generalization evaluation
DURATION = 300
WARMUP = 60
THRESHOLD = 0.30
OUTPUT_DIR_TRAIN = Path("results/stage5_selector_closed_loop")
OUTPUT_DIR_HOLDOUT = Path("results/stage5_heldout_seeds")

OUTPUT_DIR_TRAIN.mkdir(exist_ok=True)
OUTPUT_DIR_HOLDOUT.mkdir(exist_ok=True)

# Build controllers with same parameters for all runs
def build_controllers(ctrl_id: str, junction_id: str = None):
    """Factory for per-junction independent instances."""
    gate_enabled = (ctrl_id in ["D2", "S"])
    
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
    elif ctrl_id in ["D1", "D2", "S"]:
        return {j: _make_queuesense() for j in ["J1", "J2", "J3"]}
    raise ValueError(f"Unknown controller: {ctrl_id}")

def run_single_case(scenario: str, ctrl_id: str, seed: int, output_dir: Path, use_spillback_gate: bool) -> Dict[str, Any]:
    """Run a single benchmark case and return metadata."""
    case_id = f"{ctrl_id}_seed{seed}_{scenario}"
    case_dir = output_dir / scenario
    case_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing run (resume support)
    existing = case_dir / f"{case_id}_summary.json"
    if existing.exists():
        try:
            with open(existing) as f:
                summary = json.load(f)
            if summary.get("steps", 0) > 0:
                print(f"  Skipping {case_id} (already completed, {summary.get('arrived_cumulative', 0)} arrivals)")
                return {"status": "skipped", "case": case_id}
        except Exception:
            pass

    print(f"  Running {case_id}...", end="", flush=True)

    controllers = build_controllers(ctrl_id)

    runner = MultiJunctionSimulationRunner(
        net_file=NET_FILE,
        route_files=[f"sumo/routes_v2/benchmark/{scenario}.rou.xml"],
        output_dir=str(case_dir),
        step_length=1.0,
        duration=DURATION,
        warmup_time=WARMUP,
        seed=seed,
        controllers=controllers,
        use_coordinator=True,
        use_spillback_gate=use_spillback_gate,
        gui=False,
        csv_prefix=case_id,
    )

    runner.run()
    print(" DONE")
    return {"status": "success", "case": case_id, "case_id": case_id}

def extract_metrics_from_summary(summary_path: Path) -> Dict[str, Any]:
    """Extract key metrics from a summary JSON file."""
    with open(summary_path) as f:
        summary = json.load(f)
    
    # Post-warmup metrics (t=60..300s, 241 steps)
    csv_path = Path(summary["csv"])
    if not csv_path.exists():
        return None
    
    metrics = {
        "mean_wait_per_vehicle_s": 0.0,
        "total_waiting_vehicle_seconds": 0.0,
        "completed_arrivals": 0,
        "unfinished_vehicles": 0,
        "physical_congestion_steps": 0,
        "gate_intervention_steps": 0,
        "phase_switches": 0,
        "teleports": 0,
        "arrived_cumulative": summary.get("arrived_cumulative", 0),
        "total_wait_seconds": summary.get("total_wait_seconds", 0.0),
        "mean_wait_seconds": summary.get("mean_wait_seconds", 0.0),
        "steps": summary.get("steps", 0),
        "duration": summary.get("duration", 300),
    }
    
    # Read CSV to compute precise metrics
    try:
        with open(csv_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            post_warmup_rows = list(reader)[60:301]  # t=60..300s inclusive
            
            total_wait_sum = 0.0
            vehicle_count = 0
            physical_congestion_count = 0
            gate_intervention_count = 0
            phase_switches_count = 0
            teleports_count = 0
            
            for row in post_warmup_rows:
                # Extract metrics from CSV
                if "queue_count" in row:
                    vehicle_count += float(row["queue_count"])
                if "total_wait_seconds" in row:
                    total_wait_sum += float(row["total_wait_seconds"])
                if "edge_occupancy_fraction" in row:
                    occ = float(row["edge_occupancy_fraction"])
                    if occ >= 0.30:
                        physical_congestion_count += 1
                if "gate_intervention" in row and row["gate_intervention"] == "1":
                    gate_intervention_count += 1
                # Phase switches from decision trace if available
            
            metrics["mean_wait_per_vehicle_s"] = total_wait_sum / max(vehicle_count, 1)
            metrics["total_waiting_vehicle_seconds"] = total_wait_sum
            metrics["physical_congestion_steps"] = physical_congestion_count
            metrics["gate_intervention_steps"] = gate_intervention_count
            
    except Exception as e:
        print(f"Warning: Could not process {csv_path}: {e}")
    
    return metrics

def run_heldout_benchmark() -> Dict[str, Any]:
    """Run held-out generalization benchmark on seeds 52, 53."""
    print("=" * 70)
    print("STAGE 2: HELD-OUT GENERALIZATION BENCHMARK (seeds 52, 53)")
    print("=" * 70)
    print("Running held-out generalization evaluation on unseen seeds 52, 53")
    print("Testing out-of-sample generalization across all 6 controllers (A, B, C, D1, D2, S)")
    
    heldout_results = {}
    total_cases = 0
    completed_cases = 0
    
    for scenario in SCENARIOS:
        print(f"\nScenario: {scenario}")
        heldout_results[scenario] = {}
        
        for ctrl_id in CTRL_IDS:
            heldout_results[scenario][ctrl_id] = {}
            use_gate = (ctrl_id in ["D2", "S"])
            
            for seed in SEEDS_HOLDOUT:
                case_id = f"{ctrl_id}_seed{seed}_{scenario}"
                print(f"  Running {case_id}...", end="", flush=True)
                
                # Run the case
                result = run_single_case(scenario, ctrl_id, seed, OUTPUT_DIR_HOLDOUT, use_gate)
                
                if result["status"] == "skipped":
                    heldout_results[scenario][ctrl_id][seed] = {"status": "skipped"}
                    total_cases += 1
                else:
                    # Extract metrics from summary
                    case_dir = OUTPUT_DIR_HOLDOUT / scenario
                    summary_file = case_dir / f"{case_id}_seed{seed}_summary.json"
                    metrics = extract_metrics_from_summary(summary_file)
                    
                    heldout_results[scenario][ctrl_id][seed] = metrics
                    completed_cases += 1
                    total_cases += 1
                    print(" DONE")
    
    return {
        "status": "completed",
        "heldout_results": heldout_results,
        "total_cases": total_cases,
        "completed_cases": completed_cases,
    }

def main():
    print("=" * 70)
    print("STAGE 5: CLOSED-LOOP CONTROLLERS S BENCHMARK (seeds 42..51)")
    print("=" * 70)
    print("Running closed-loop benchmark for Controller S only (standard evaluation)")
    print("(All 50 cases across 5 scenarios × 10 seeds)")
    
    # Stage 5: Run closed-loop S benchmark (existing behavior)
    start_train = time.time()
    train_results = []
    
    for scenario in SCENARIOS:
        print(f"\nScenario: {scenario}")
        for ctrl_id in ["S"]:  # Only S for Stage 5
            for seed in SEEDS_TRAIN:
                use_gate = (ctrl_id in ["D2", "S"])
                result = run_single_case(scenario, ctrl_id, seed, OUTPUT_DIR_TRAIN, use_gate)
                train_results.append(result)
    
    train_elapsed = time.time() - start_train
    print(f"\nStage 5 completed in {train_elapsed/60:.1f} minutes")
    
    # Stage 2: Run held-out generalization benchmark
    heldout_results = run_heldout_benchmark()
    
    # Generate unified metrics summary
    print("\n" + "=" * 70)
    print("STAGE 2 RECONCILIATION: UNIFIED METRICS SUMMARY")
    print("=" * 70)
    
    unified_metrics = {
        "stage": "stage2_unified_reconciliation",
        "development_matrix": {},
        "heldout_evaluation": {},
        "comparison": {},
    }
    
    # Process development matrix (Stage 5 results)
    for scenario in SCENARIOS:
        unified_metrics["development_matrix"][scenario] = {}
        for ctrl_id in CTRL_IDS:
            unified_metrics["development_matrix"][scenario][ctrl_id] = {}
            
            mean_waits = []
            total_waits = []
            
            for seed in SEEDS_TRAIN:
                case_dir = OUTPUT_DIR_TRAIN / scenario
                summary_file = case_dir / f"{ctrl_id}_seed{seed}_{scenario}_seed{seed}_summary.json"
                if summary_file.exists():
                    metrics = extract_metrics_from_summary(summary_file)
                    if metrics:
                        mean_waits.append(metrics["mean_wait_per_vehicle_s"])
                        total_waits.append(metrics["total_waiting_vehicle_seconds"])
            
            unified_metrics["development_matrix"][scenario][ctrl_id] = {
                "mean_wait_per_vehicle_s": {
                    "mean": statistics.mean(mean_waits) if mean_waits else 0.0,
                    "std": statistics.stdev(mean_waits) if len(mean_waits) > 1 else 0.0,
                    "n": len(mean_waits),
                    "all": mean_waits,
                },
                "total_waiting_vehicle_seconds": {
                    "mean": statistics.mean(total_waits) if total_waits else 0.0,
                    "std": statistics.stdev(total_waits) if len(total_waits) > 1 else 0.0,
                    "n": len(total_waits),
                    "all": total_waits,
                },
            }
    
    # Process held-out evaluation results
    for scenario in SCENARIOS:
        unified_metrics["heldout_evaluation"][scenario] = {}
        for ctrl_id in CTRL_IDS:
            unified_metrics["heldout_evaluation"][scenario][ctrl_id] = {}
            
            mean_waits = []
            total_waits = []
            
            for seed in SEEDS_HOLDOUT:
                if seed in heldout_results["heldout_results"][scenario][ctrl_id]:
                    metrics = heldout_results["heldout_results"][scenario][ctrl_id][seed]
                    if metrics and metrics.get("mean_wait_per_vehicle_s", 0) > 0:
                        mean_waits.append(metrics["mean_wait_per_vehicle_s"])
                        total_waits.append(metrics["total_waiting_vehicle_seconds"])
            
            unified_metrics["heldout_evaluation"][scenario][ctrl_id] = {
                "mean_wait_per_vehicle_s": {
                    "mean": statistics.mean(mean_waits) if mean_waits else 0.0,
                    "std": statistics.stdev(mean_waits) if len(mean_waits) > 1 else 0.0,
                    "n": len(mean_waits),
                    "all": mean_waits,
                },
                "total_waiting_vehicle_seconds": {
                    "mean": statistics.mean(total_waits) if total_waits else 0.0,
                    "std": statistics.stdev(total_waits) if len(total_waits) > 1 else 0.0,
                    "n": len(total_waits),
                    "all": total_waits,
                },
            }
    
    # Save unified metrics
    output_path = OUTPUT_DIR_TRAIN / "reconciled_metrics_summary.json"
    with open(output_path, "w") as f:
        json.dump(unified_metrics, f, indent=2)
    
    print(f"\nUnified metrics saved to: {output_path}")
    
    # Generate human-readable analysis
    print("\n" + "=" * 70)
    print("RECONCILIATION ANALYSIS")
    print("=" * 70)
    
    print("\nDEVELOPMENT MATRIX (Stage 5: seeds 42..51)")
    print("-" * 70)
    
    for scenario in SCENARIOS:
        print(f"\nScenario: {scenario.upper()}")
        print("Controller | Mean Wait (s/veh) | Total Wait (veh·s) | Cases")
        print("-" * 70)
        for ctrl_id in CTRL_IDS:
            stats = unified_metrics["development_matrix"][scenario][ctrl_id]
            mw = stats["mean_wait_per_vehicle_s"]
            tw = stats["total_waiting_vehicle_seconds"]
            print(f"{ctrl_id:9} | {mw['mean']:18.3f} ± {mw['std']:5.3f} | {tw['mean']:21.1f} ± {tw['std']:8.1f} | {mw['n']:5}")
    
    print("\nHELD-OUT EVALUATION (Stage 2: seeds 52..53)")
    print("-" * 70)
    
    for scenario in SCENARIOS:
        print(f"\nScenario: {scenario.upper()}")
        print("Controller | Mean Wait (s/veh) | Total Wait (veh·s) | Cases")
        print("-" * 70)
        for ctrl_id in CTRL_IDS:
            stats = unified_metrics["heldout_evaluation"][scenario][ctrl_id]
            mw = stats["mean_wait_per_vehicle_s"]
            tw = stats["total_waiting_vehicle_seconds"]
            print(f"{ctrl_id:9} | {mw['mean']:18.3f} ± {mw['std']:5.3f} | {tw['mean']:21.1f} ± {tw['std']:8.1f} | {mw['n']:5}")
    
    # Paired seed differences (S vs baselines)
    print("\nPAIRED SEED DIFFERENCES (S vs Baselines)")
    print("-" * 70)
    print("Scenario | Seed | S vs A (s) | S vs C (s) | S vs D1 (s) | S vs D2 (s)")
    print("-" * 70)
    
    for scenario in SCENARIOS:
        for seed in SEEDS_TRAIN:
            # Development matrix differences
            base_s = unified_metrics["development_matrix"][scenario]["S"]["mean_wait_per_vehicle_s"]["mean"]
            base_c = unified_metrics["development_matrix"][scenario]["C"]["mean_wait_per_vehicle_s"]["mean"]
            base_d1 = unified_metrics["development_matrix"][scenario]["D1"]["mean_wait_per_vehicle_s"]["mean"]
            base_d2 = unified_metrics["development_matrix"][scenario]["D2"]["mean_wait_per_vehicle_s"]["mean"]
            
            print(f"{scenario:9} | {seed:4} | {base_s - base_c:9.3f} | {base_s - base_c:9.3f} | {base_s - base_d1:9.3f} | {base_s - base_d2:9.3f}")
    
    print("\n" + "=" * 70)
    print("STAGE 2 RECONCILIATION COMPLETE")
    print("=" * 70)
    print(f"Development matrix cases: {len(SEEDS_TRAIN) * len(SCENARIOS)}")
    print(f"Held-out evaluation cases: {len(SEEDS_HOLDOUT) * len(SCENARIOS)}")
    print(f"Total cases processed: {total_cases}")
    print(f"Output directory: {OUTPUT_DIR_TRAIN}")

if __name__ == "__main__":
    main()
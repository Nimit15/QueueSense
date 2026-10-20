import os
import sys
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from queuesense.benchmark.runner import BenchmarkRunner

base_dir = "D:/QueueSense"
route_files = {
    "light": ["sumo/routes/benchmark/light.rou.xml"],
    "balanced": ["sumo/routes/benchmark/balanced.rou.xml"],
    "uneven": ["sumo/routes/benchmark/uneven.rou.xml"],
    "bottleneck": ["sumo/routes/benchmark/bottleneck.rou.xml"],
    "surge": ["sumo/routes/benchmark/surge.rou.xml"],
}
SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]
CONTROLLERS = ["A", "B", "C", "D"]
SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]

# Determine missing combinations
import glob
missing = []
for scenario in SCENARIOS:
    for controller in CONTROLLERS:
        for seed in SEEDS:
            pattern = os.path.join(base_dir, "results", "benchmark_final", scenario, f"{controller}_seed{seed}_*.csv")
            files = glob.glob(pattern)
            if not files:
                missing.append((scenario, controller, seed))

print(f"Found {len(missing)} missing runs.")
if not missing:
    print("No missing runs.")
    sys.exit(0)

# We'll run each missing combo individually using the BenchmarkRunner's internal method.
# But easier: create a runner and call _run_scenario_for_controller for each missing.
# However, that method is not public. We'll instead create a runner and temporarily modify its seeds/scenarios/controllers?
# Let's just run the benchmark but filter? Instead, we'll create a runner and then replace its run_benchmark method to only run missing.
# Simpler: we'll just run the benchmark for each missing combo by creating a SimulationRunner directly.
# Let's do that.

from queuesense.simulation.runner import SimulationRunner
from queuesense.controllers import (
    FixedTimeController,
    ActuatedController,
    QueuePressureController,
    QueueSenseController,
)

controller_map = {
    "A": FixedTimeController(),
    "B": ActuatedController(gap_threshold=3.0),
    "C": QueuePressureController(alpha=0.4, beta=0.4, gamma=0.2, max_wait=90.0),
    "D": QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85, max_wait=90.0),
}

net_file = r"D:\QueueSense\sumo\network\corridor.net.xml"
step_length = 1.0
duration = 3600
warmup_time = 300
gui = False

output_base = os.path.join(base_dir, "results", "benchmark_final")

for scenario, controller_id, seed in missing:
    print(f"Running {scenario} controller {controller_id} seed {seed}...")
    controller = controller_map[controller_id]
    route_list = route_files[scenario]
    scenario_dir = os.path.join(output_base, scenario)
    os.makedirs(scenario_dir, exist_ok=True)
    runner = SimulationRunner(
        net_file=net_file,
        route_files=route_list,
        output_dir=scenario_dir,
        step_length=step_length,
        duration=duration,
        warmup_time=warmup_time,
        controller=controller,
        gui=gui,
        csv_prefix=f"{controller_id}_seed{seed}",
        seed=seed,
    )
    try:
        runner.run()
        print(f"  Completed.")
    except Exception as e:
        print(f"  Failed: {e}")

print("Done.")

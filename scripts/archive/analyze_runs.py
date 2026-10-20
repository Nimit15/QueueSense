import os
import glob

base_dir = "results/benchmark_final"
scenarios = ["light", "balanced", "uneven", "bottleneck", "surge"]
controllers = ["A", "B", "C", "D"]
seeds = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]

missing = []
for scenario in scenarios:
    for controller in controllers:
        for seed in seeds:
            pattern = f"{base_dir}/{scenario}/{controller}_seed{seed}_*.csv"
            files = glob.glob(pattern)
            if not files:
                missing.append((scenario, controller, seed))

print(f"Missing runs: {len(missing)}")
for m in missing[:10]:
    print(m)
if len(missing) > 10:
    print(f"  ... and {len(missing)-10} more")

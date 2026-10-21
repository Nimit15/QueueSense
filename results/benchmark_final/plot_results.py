import json
import matplotlib.pyplot as plt
import numpy as np
import os

# Load summary
with open('summary.json', 'r') as f:
    data = json.load(f)

# Extract metrics
metrics = data['metrics']

# Helper to get values for a metric
def get_values(metric_name):
    vals = []
    for entry in metrics[metric_name]:
        vals.append(entry['mean'])
    return vals

# Controller labels
controllers = ['A', 'B', 'C', 'D']
scenarios = data['scenarios']  # should be ['bottleneck'] for this run, but we have multiple scenarios in the final benchmark?
# Actually the summary.json we have is from the bottleneck only run? Wait, we ran the full benchmark with all scenarios.
# Let's check the summary.json content from earlier: it only had bottleneck. That suggests the summary.json we looked at was from the bottleneck diagnostic.
# But the final benchmark we just ran (run_full_benchmark.py) should have produced a summary with all scenarios.
# Let's check the file again; maybe it got overwritten? We'll read the file now.

# Re-read to be sure
with open('summary.json', 'r') as f:
    data = json.load(f)
print("Scenarios in summary:", data.get('scenarios'))
print("Controllers:", data.get('controllers'))
print("Seeds:", data.get('seeds'))

# We'll plot per scenario
scenarios = data['scenarios']
controllers = data['controllers']

# For each metric, create a grouped bar chart per scenario
metric_names = ['arrived_cumulative', 'remaining_expected', 'queue_north', 'queue_south', 'queue_east', 'queue_west', 'spillback_ns', 'spillback_ew']

for metric in metric_names:
    if metric not in data['metrics']:
        continue
    plt.figure(figsize=(10, 6))
    # We'll have groups for each scenario, and within each group, bars for each controller
    n_scenarios = len(scenarios)
    n_controllers = len(controllers)
    bar_width = 0.8 / (n_controllers + 1)  # spacing
    indices = np.arange(n_scenarios)

    for i, c in enumerate(controllers):
        # Collect mean values for this controller across scenarios
        means = []
        for s in scenarios:
            # Find entry for this scenario and controller
            vals = [e['mean'] for e in data['metrics'][metric] if e['scenario'] == s and e['controller'] == c]
            if vals:
                means.append(vals[0])
            else:
                means.append(0)
        plt.bar(indices + i * bar_width, means, bar_width, label=f'Controller {c}')

    plt.xlabel('Scenario')
    plt.ylabel(metric.replace('_', ' ').title())
    plt.title(f'{metric.replace("_", " ").title()} by Scenario and Controller')
    plt.xticks(indices + bar_width * (n_controllers - 1) / 2, scenarios)
    plt.legend()
    plt.tight_layout()

    # Save figure
    out_file = f'{metric}.png'
    plt.savefig(out_file, dpi=150)
    plt.close()
    print(f'Saved {out_file}')

# Also create a summary table text file
with open('summary_table.txt', 'w') as f:
    f.write('QueueSense Benchmark Summary\\n')
    f.write('='*50 + '\\n\\n')
    for metric in metric_names:
        if metric not in data['metrics']:
            continue
        f.write(f'{metric}:\\n')
        for entry in data['metrics'][metric]:
            f.write(f"  Scenario: {entry['scenario']}, Controller: {entry['controller']}, Mean: {entry['mean']:.2f}, Std: {entry.get('std', 0):.2f}, Min: {entry['min']}, Max: {entry['max']}\\n")
        f.write('\\n')
print('Saved summary_table.txt')
import csv
import numpy as np

def analyze_pressure_log(fname, controller_name):
    path = f'D:/QueueSense/results/diagnostics/{fname}'
    times = []
    pressures_ns = []
    pressures_ew = []
    phases = []
    reasons = []
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            times.append(float(row['time']))
            pressures_ns.append(float(row['pressure_north_south']))
            pressures_ew.append(float(row['pressure_east_west']))
            phases.append(row['controller_phase'])
            reasons.append(row['controller_reason'])
    times = np.array(times)
    pressures_ns = np.array(pressures_ns)
    pressures_ew = np.array(pressures_ew)
    print(f'\n=== {controller_name} ===')
    print(f'Time steps: {len(times)}')
    print(f'Pressure NS: min={pressures_ns.min():.4f}, mean={pressures_ns.mean():.4f}, max={pressures_ns.max():.4f}')
    print(f'Pressure EW: min={pressures_ew.min():.4f}, mean={pressures_ew.mean():.4f}, max={pressures_ew.max():.4f}')
    # Count phase occurrences
    from collections import Counter
    phase_counts = Counter(phases)
    print(f'Phase distribution: {phase_counts}')
    # Determine when NS pressure > EW pressure and vice versa
    ns_greater = np.sum(pressures_ns > pressures_ew)
    ew_greater = np.sum(pressures_ew > pressures_ns)
    equal = np.sum(pressures_ns == pressures_ew)
    print(f'Steps where NS pressure > EW pressure: {ns_greater} ({100*ns_greater/len(times):.1f}%)')
    print(f'Steps where EW pressure > NS pressure: {ew_greater} ({100*ew_greater/len(times):.1f}%)')
    print(f'Steps where equal: {equal} ({100*equal/len(times):.1f}%)')
    # For Controller C: should select higher pressure (so if NS > EW, select NS; if EW > NS, select EW)
    # For Controller D: should select lower pressure (if both eligible) -> select NS if EW > NS? Actually D selects lower pressure, so if NS > EW, select EW; if EW > NS, select NS.
    # We'll compute expected phase based on each rule and compare to actual.
    # But first, need to know eligibility: both directions eligible if downstream_available True for both north and east? Actually eligibility per approach.
    # We'll approximate: if both north and east downstream_available True (from logs) then both directions eligible.
    # Let's load downstream flags.
    # We'll re-read the log to get downstream flags? Not in this log. We'll need to parse edge logs or approximate.
    # For simplicity, assume both directions eligible (since downstream occupancy low).
    # Compute expected phase for C: choose phase with higher pressure.
    expected_phase_c = np.where(pressures_ns >= pressures_ew, 'NORTH_SOUTH', 'EAST_WEST')
    # For D: choose phase with lower pressure.
    expected_phase_d = np.where(pressures_ns <= pressures_ew, 'NORTH_SOUTH', 'EAST_WEST')
    # Compare
    actual = np.array(phases)
    match_c = np.sum(expected_phase_c == actual)
    match_d = np.sum(expected_phase_d == actual)
    print(f'Controller C expected phase matches actual: {match_c} / {len(times)} ({100*match_c/len(times):.1f}%)')
    print(f'Controller D expected phase matches actual: {match_d} / {len(times)} ({100*match_d/len(times):.1f}%)')

analyze_pressure_log('pressure_log_QueuePressure_seed42.csv', 'QueuePressure')
analyze_pressure_log('pressure_log_QueueSense_seed42.csv', 'QueueSense')
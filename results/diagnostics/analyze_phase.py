import csv

def analyze_phase_log(fname):
    path = f'D:/QueueSense/results/diagnostics/{fname}'
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        phases = []
        reasons = []
        for row in reader:
            phases.append(row['phase_index'])
            reasons.append(row['controller_reason'])
    # Count phase occurrences
    from collections import Counter
    phase_counts = Counter(phases)
    print(f'Phase distribution: {phase_counts}')
    # Count reason occurrences
    reason_counts = Counter(reasons)
    print(f'Top reasons: {reason_counts.most_common(5)}')

print('=== QueuePressure ===')
analyze_phase_log('phase_log_QueuePressure_seed42.csv')
print('\n=== QueueSense ===')
analyze_phase_log('phase_log_QueueSense_seed42.csv')
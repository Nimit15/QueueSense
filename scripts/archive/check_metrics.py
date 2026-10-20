import csv
from pathlib import Path

# Check actual metrics for one combo
f = Path('results/benchmark_corrected/balanced/A_seed42_20261014_163528.csv')
with open(f) as fh:
    reader = csv.DictReader(fh)
    rows = list(reader)
    print('File:', f)
    print('Rows:', len(rows))
    print('First row:', rows[0])
    print('Last row:', rows[-1])
    # Check arrived_cumulative progression
    arrived = [int(r['arrived_cumulative']) for r in rows]
    print('Arrived cumulative values (unique):', sorted(set(arrived))[-10:])
    print('Max arrived:', max(arrived))
    print('Remaining values:', set([r['remaining_expected'] for r in rows]))

print('\n--- Check seed 45 ---\n')
f = Path('results/benchmark_corrected/balanced/A_seed45_20261014_163530.csv')
with open(f) as fh:
    reader = csv.DictReader(fh)
    rows = list(reader)
    print('Rows:', len(rows))
    print('Last row:', rows[-1])

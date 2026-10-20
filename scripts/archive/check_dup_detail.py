import csv
from pathlib import Path
from collections import defaultdict

base = Path('results/benchmark_corrected')
combo_data = defaultdict(list)

for f in base.rglob('*.csv'):
    parts = f.stem.split('_')
    if len(parts) < 2:
        continue
    controller = parts[0]
    seed = parts[1].replace('seed','')
    scenario = f.parent.name
    combo_data[(scenario,controller,seed)].append(str(f))

# Count by seed
seed_counts = defaultdict(int)
for k,v in combo_data.items():
    seed_counts[k[2]] += 1

print('Combos per seed:')
for s in sorted(seed_counts):
    print(s, seed_counts[s])

# Find combos with 1 file
one_file = [k for k,v in combo_data.items() if len(v)==1]
print(f"\nCombos with 1 file: {len(one_file)}")
for k in one_file[:20]:
    print(k, combo_data[k])

# Find combos with 3 files
three_file = [k for k,v in combo_data.items() if len(v)==3]
print(f"\nCombos with 3 files: {len(three_file)}")

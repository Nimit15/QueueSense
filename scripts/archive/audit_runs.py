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
    # read file
    try:
        with open(f) as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            if not rows:
                continue
            last = rows[-1]
            arrived = int(last.get('arrived_cumulative',0))
            remaining = int(last.get('remaining_expected',0))
            time_val = float(last.get('time',0))
            combo_data[(scenario,controller,seed)].append({
                'file': str(f),
                'rows': len(rows),
                'arrived': arrived,
                'remaining': remaining,
                'time': time_val
            })
    except Exception as e:
        print(f'Error reading {f}: {e}')

# Summary
print(f"Unique combos: {len(combo_data)}")
# Expected: 5*4*10=200
missing = []
for scenario in ['balanced','bottleneck','light','surge','uneven']:
    for controller in ['A','B','C','D']:
        for seed in ['42','43','44','45','46','47','48','49','50','51']:
            if (scenario,controller,seed) not in combo_data:
                missing.append((scenario,controller,seed))
print(f"Missing combos: {len(missing)}")
for m in missing:
    print(m)

# Check duplicates
dup = {k:v for k,v in combo_data.items() if len(v)>1}
print(f"Duplicates: {len(dup)}")
for k,v in list(dup.items())[:10]:
    print(k, len(v))
    # Check if same content
    first = v[0]
    same = all(x['arrived']==first['arrived'] and x['remaining']==first['remaining'] for x in v)
    print('  same content:', same)

# Check metric validity
invalid = []
for k,v in combo_data.items():
    # use first
    data = v[0]
    if data['time'] > 3600 + 10:
        invalid.append((k,'time too long'))
    if data['arrived'] < 0:
        invalid.append((k,'negative arrived'))
    if data['remaining'] < 0:
        invalid.append((k,'negative remaining'))
print(f"Invalid combos: {len(invalid)}")

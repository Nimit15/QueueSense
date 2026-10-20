import os
from pathlib import Path
base=Path('results/benchmark_corrected')
files=list(base.rglob('*.csv'))
print('total', len(files))
seeds=set()
for f in files:
    parts=f.stem.split('_')
    seed=parts[1] if len(parts)>1 else ''
    seeds.add(seed)
print('seeds found', sorted(seeds))
# check duplicates
from collections import defaultdict
combo=defaultdict(list)
for f in files:
    parts=f.stem.split('_')
    if len(parts)>=2:
        controller=parts[0]
        seed=parts[1]
        scenario=f.parent.name
        combo[(scenario,controller,seed)].append(str(f))
for k,v in list(combo.items())[:10]:
    print(k, len(v))
print('duplicates:', sum(1 for v in combo.values() if len(v)>1))

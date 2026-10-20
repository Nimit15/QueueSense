#!/usr/bin
python3
import os, sys
sys.path.insert(0, 'D:/QueueSense/src')
os.chdir('D:/QueueSense')

scenarios = ['light', 'bottleneck', 'surge', 'uneven']
for s in scenarios:
    path = 'sumo/' + s + '/benchmark/' + s + '.rou.xml'
    exists = os.path.exists(path)
    # Also check simpler path
    if not exists:
        path2 = 'sumo/' + s + '.rou.xml'
        exists2 = os.path.exists(path2)
    status = 'OK' if exists or exists2 else 'MISSING'
    print(s +': path1=' + ('sumo/' + s + '/benchmark/' + s + '.rou.xml') + ' path2=' + ('sumo/' + s + '.rou.xml') + ' - ' + status)
    # Try all possible paths
    paths_to_try = [
        'sumo/' + s + '/benchmark/' + s + '.rou.xml',
        'sumo/' + s + '.rou.xml',
        'sumo/benchmark/' + s + '.rou.xml',
    ]
    for p in paths_to_try:
        if os.path.exists(p):
            print('  Found at: ' + p)
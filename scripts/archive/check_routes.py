#!/usr/bin/env python3
import os, sys
os.chdir('D:/QueueSense')
sys.path.insert(0, 'src')

scenarios = ['light', 'bottle
ck', 'surge', 'uneven']
for s in scenarios:
    path = f'sumo/{s}.rou.xml'
    exists = os.path.exists(path)
    status = 'OK' if exists else 'MISSING'
    print(f
scenario}: {path} - {status}')
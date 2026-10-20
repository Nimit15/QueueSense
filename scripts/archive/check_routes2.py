#!/usr/bin
python3
import os
import sys

os.chdir('D:/QueueSense')
sys.path.insert(0, 'src')

scenarios = ['light', 'bottle
ck', 'surge', 'uneven']
for s in scenarios:
    path = 'sumo/' + s + '.rou.xml'
    exists = os.path.exists(path)
    status = 'OK' if exists else 'MISSING'
    print(s + ':': ' + path + ' - ' + status)
#!/bin/bash
# Daily RF summary — sent at 8 AM and 8 PM via ntfy
# Shows the PREVIOUS 12 hours of activity (not current)

cd /home/tyler/projects/rf-monitor

SUMMARY=$(.venv/bin/python3 -c "
import json, glob
from datetime import datetime, timedelta

LOCAL_TZ = datetime.now().astimezone().tzinfo
now = datetime.now().astimezone()
twelve_ago = now - timedelta(hours=12)

# Load recent cycles
eis = []
max_k = 0
n_active_cycles = 0
for logf in sorted(glob.glob('results/sentinel_*.jsonl')):
    with open(logf) as f:
        for line in f:
            try:
                c = json.loads(line)
                ts = datetime.fromisoformat(c['timestamp'].replace('Z','+00:00')).astimezone(LOCAL_TZ)
                if ts < twelve_ago:
                    continue
                ei = c.get('exposure_index', 0) or 0
                eis.append(ei)
                mk = 0
                for fs, rs in c.get('stare',{}).items():
                    for r in rs:
                        k = r.get('kurtosis', 0)
                        if k > mk: mk = k
                if mk > max_k: max_k = mk
                if mk > 20: n_active_cycles += 1
            except: pass

# Load symptoms
n_symptoms = 0
try:
    with open('results/evidence/symptom_log.jsonl') as f:
        for line in f:
            try:
                s = json.loads(line)
                ts = s.get('timestamp','')
                if 'T' in ts:
                    dt = datetime.fromisoformat(ts.replace('Z','+00:00')).astimezone(LOCAL_TZ)
                    if dt > twelve_ago:
                        n_symptoms += 1
            except: pass
except: pass

import numpy as np
if eis:
    print(f'Last 12h: {len(eis)} cycles')
    print(f'EI: mean={np.mean(eis):.0f} max={max(eis):.0f}')
    print(f'Kurt max: {max_k:.0f}')
    print(f'Active: {n_active_cycles}/{len(eis)} ({n_active_cycles/len(eis)*100:.0f}%)')
    print(f'Symptoms logged: {n_symptoms}')
else:
    print('No data in last 12h')
" 2>/dev/null)

curl -s -X POST "http://100.96.113.92:8090/artemis-checkin" \
  -H "Title: 12h Summary" \
  -H "Priority: low" \
  -H "Tags: bar_chart" \
  -d "$SUMMARY" \
  > /dev/null 2>&1

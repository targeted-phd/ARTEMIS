#!/bin/bash
# Rebuild ML master dataset from all sentinel + symptom + IQ data
cd /home/tyler/projects/rf-monitor
.venv/bin/python3 -c "
import json, glob, os, numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Use system local timezone (CDT in March = UTC-5, CST in Nov = UTC-6)
# astimezone() handles DST automatically
LOCAL_TZ = datetime.now().astimezone().tzinfo
K_NOISE = 8.5
TARGETS = [622,624,628,630,632,634,636,826,828,830,832,834,878]
ZONE_A_START = datetime(2026, 3, 13, 16, 55, tzinfo=LOCAL_TZ)

# ── Load all cycles, deduplicate ──
all_raw = []
for logf in sorted(glob.glob('results/sentinel_*.jsonl')):
    with open(logf) as f:
        for line in f:
            try:
                c = json.loads(line)
                ts_str = c.get('timestamp', '')
                if ts_str:
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00')).astimezone(LOCAL_TZ)
                    all_raw.append((ts, c))
            except: pass

seen = set()
cycles = []
for ts, c in sorted(all_raw, key=lambda x: x[0]):
    key = ts.strftime('%Y%m%d%H%M%S')
    if key not in seen:
        seen.add(key)
        cycles.append((ts, c))

# ── Build timeline ──
dataset = []
prev_ts = None
for ts, c in cycles:
    if prev_ts and (ts - prev_ts).total_seconds() > 300:
        dataset.append({
            'cst': prev_ts.strftime('%Y-%m-%d %H:%M:%S'), 'hour': prev_ts.hour, 'minute': prev_ts.minute,
            'day_of_week': prev_ts.strftime('%A'), 'is_night': prev_ts.hour >= 21 or prev_ts.hour < 6,
            'type': 'GAP_NO_DATA', 'gap_minutes': round((ts - prev_ts).total_seconds()/60, 1),
            'has_zone_a': ts >= ZONE_A_START,
            'ei_total': None, 'ei_zone_a': None, 'ei_zone_b': None,
            'max_kurt': None, 'max_kurt_zone_a': None, 'max_kurt_zone_b': None, 'max_kurt_ul': None,
            'n_active_targets': None, 'total_pulses': None,
            'mean_pulse_width_us': None, 'total_pulse_duration_us': None, 'symptoms': [],
        })
    prev_ts = ts

    ei_total=0; ei_a=0; ei_b=0; max_k=0; max_ka=0; max_kb=0; max_kul=0
    total_p=0; all_w=[]; total_pw=0; active_t=set()
    for fs, readings in c.get('stare',{}).items():
        for r in readings:
            k=r.get('kurtosis',K_NOISE); pdb=r.get('mean_pwr_db',-44); pl=10**(pdb/10)
            f=r.get('freq_mhz',r.get('nominal_freq_mhz',0)); pc=r.get('pulse_count',0)
            total_p+=pc
            if k>max_k: max_k=k
            if isinstance(f,(int,float)):
                if 618<f<640 and k>max_ka: max_ka=k
                if 820<f<840 and k>max_kb: max_kb=k
                if 870<f<890 and k>max_kul: max_kul=k
                if k>20:
                    n=min(TARGETS,key=lambda t:abs(t-f))
                    if abs(n-f)<4: active_t.add(n)
            pls=r.get('pulses',[])
            if isinstance(pls,list) and pls and isinstance(pls[0],dict):
                ws=[p.get('width_us',0) for p in pls if isinstance(p,dict)]
                all_w.extend(ws); tw=sum(ws); nl=len(ws); nt=pc if pc>nl else nl
                if nl>0 and nt>nl: tw=(tw/nl)*nt
            else: tw=pc*2.5
            total_pw+=tw
            ei_r=pl*tw*max(k/K_NOISE,1.0); ei_total+=ei_r
            if isinstance(f,(int,float)):
                if 618<f<640: ei_a+=ei_r
                elif 820<f<840: ei_b+=ei_r

    ha = ts>=ZONE_A_START
    dataset.append({
        'cst':ts.strftime('%Y-%m-%d %H:%M:%S'),'hour':ts.hour,'minute':ts.minute,
        'day_of_week':ts.strftime('%A'),'is_night':ts.hour>=21 or ts.hour<6,
        'type':'ACTIVE' if ei_total>20 else 'QUIET','has_zone_a':ha,
        'ei_total':round(ei_total,2),'ei_zone_a':round(ei_a,2) if ha else None,
        'ei_zone_b':round(ei_b,2),'max_kurt':round(max_k,1),
        'max_kurt_zone_a':round(max_ka,1) if ha else None,'max_kurt_zone_b':round(max_kb,1),
        'max_kurt_ul':round(max_kul,1),'n_active_targets':len(active_t),
        'total_pulses':total_p,'mean_pulse_width_us':round(float(np.mean(all_w)),2) if all_w else None,
        'total_pulse_duration_us':round(total_pw,1),'gap_minutes':None,'symptoms':[],
    })

# ── Join symptoms ──
symptoms=[]
try:
    with open('results/evidence/symptom_log.jsonl') as f:
        for line in f:
            try:
                s=json.loads(line)
                ts=s.get('alert_ts') or s.get('timestamp','')
                if 'T' in ts:
                    dt=datetime.fromisoformat(ts.replace('Z','+00:00')).astimezone(LOCAL_TZ)
                    s['_cst']=dt.replace(tzinfo=None)
                    s['cst']=dt.strftime('%Y-%m-%d %H:%M:%S')
                    s['hour']=dt.hour
                symptoms.append(s)
            except: pass
except: pass

tl_times=[]
for r in dataset:
    try: tl_times.append(datetime.strptime(r['cst'],'%Y-%m-%d %H:%M:%S'))
    except: tl_times.append(None)

for s in symptoms:
    if not s.get('symptom') or not s.get('_cst'): continue
    st=s['_cst']
    bi=None; bd=float('inf')
    for i,t in enumerate(tl_times):
        if t: d=abs((t-st).total_seconds())
        else: continue
        if d<bd: bd=d; bi=i
    if bi is not None and bd<300:
        sym = s['symptom']
        sev = s.get('severity', 1)
        try: sev = int(sev)
        except: sev = 1
        if sym not in dataset[bi].get('symptoms', []):
            dataset[bi].setdefault('symptoms', []).append(sym)
        # Track max severity per symptom per row
        sev_key = f'sev_{sym}'
        dataset[bi][sev_key] = max(dataset[bi].get(sev_key, 0), sev)

# All 7 symptom types — always present as columns even if unreported
all_st={'speech','headache','tinnitus','paresthesia','pressure','sleep','nausea'}
for r in dataset:
    for s in r.get('symptoms',[]): all_st.add(s)
for r in dataset:
    for st in sorted(all_st):
        # Single column per symptom: 0=absent, 1=mild, 2=moderate, 3=severe
        r[st] = r.get(f'sev_{st}', 0)
        # Clean up redundant columns
        r.pop(f'sym_{st}', None)
        r.pop(f'sev_{st}', None)
    # Three states:
    # did_respond=True + symptoms present -> confirmed symptoms
    # did_respond=True + all zeros -> confirmed CLEAR (explicitly no symptoms)
    # did_respond=False -> UNKNOWN (never responded, set symptom cols to None)
    has_symptoms = len([s for s in r.get('symptoms', []) if s != 'clear']) > 0
    has_clear = 'clear' in r.get('symptoms', [])
    r['did_respond'] = has_symptoms or has_clear
    if not r['did_respond']:
        # Unknown — null out all symptom columns so ML ignores these rows
        for st in all_st:
            r[st] = None
        r['any_symptom'] = None
        r['max_severity'] = None
        r['symptom_total'] = None
    else:
        r['any_symptom'] = 1 if has_symptoms else 0
        r['max_severity'] = max((r.get(st, 0) or 0 for st in all_st), default=0)
        r['symptom_total'] = sum((r.get(st, 0) or 0 for st in all_st))

# ── Exponential back-fill interpolation with unknown rolloff ──
# Back-fill: response severity decays into the PAST (5-min half-life, 15-min max)
# Forward-rolloff: after a response, severity decays into the FUTURE (10-min half-life, 30-min max)
# Beyond both windows: None (unknown) — NOT zero
HALF_LIFE_BACK=5.0; DECAY_BACK=np.log(2)/HALF_LIFE_BACK; MAX_BACK=15.0
HALF_LIFE_FWD=10.0; DECAY_FWD=np.log(2)/HALF_LIFE_FWD; MAX_FWD=30.0
tl_times=[]
for r in dataset:
    try: tl_times.append(datetime.strptime(r['cst'],'%Y-%m-%d %H:%M:%S'))
    except: tl_times.append(None)

# Parse all symptom reports + clear reports with timestamps
sym_reports=[]
clear_times=[]
for s in symptoms:
    ts2=s.get('alert_ts') or s.get('timestamp','')
    try:
        if 'T' in ts2:
            d2=datetime.fromisoformat(ts2.replace('Z','+00:00')).astimezone(LOCAL_TZ).replace(tzinfo=None)
        else: continue
    except: continue
    if s.get('symptom')=='clear':
        clear_times.append(d2)
        continue
    if not s.get('symptom'): continue
    sv=s.get('severity',2) or 2
    try: sv=int(sv)
    except: sv=2
    sym_reports.append({'time':d2,'symptom':s['symptom'],'severity':sv})

# For each row, determine if it's within reach of any response
# If not, symptoms are unknown (None)
for i,r in enumerate(dataset):
    t=tl_times[i]
    if t is None: continue

    # Check if this row is within range of ANY symptom report or clear
    all_report_times = [rpt['time'] for rpt in sym_reports] + clear_times
    nearest_report_min = min((abs((rt-t).total_seconds()/60.0) for rt in all_report_times), default=999)
    in_coverage = nearest_report_min <= MAX_FWD  # within 30 min of any response

    for st in all_st:
        if not in_coverage:
            r[st+'_interp'] = None
            continue
        mx=0.0
        for rpt in sym_reports:
            if rpt['symptom']!=st: continue
            dm=(rpt['time']-t).total_seconds()/60.0
            # Back-fill: report is AFTER this row (dm > 0), decay into past
            if 0<dm<=MAX_BACK:
                mx=max(mx, rpt['severity']*np.exp(-DECAY_BACK*dm))
            # At the report time
            elif -1.0<=dm<=0:
                mx=max(mx, float(rpt['severity']))
            # Forward-rolloff: report is BEFORE this row (dm < 0), decay into future
            elif -MAX_FWD<=dm<-1.0:
                mx=max(mx, rpt['severity']*np.exp(-DECAY_FWD*abs(dm)))
        r[st+'_interp']=round(mx,2) if mx>0.05 else 0.0

    # Aggregates — None if out of coverage
    if not in_coverage:
        r['any_symptom_interp']=None
        r['max_severity_interp']=None
        r['symptom_total_interp']=None
    else:
        iv=[r.get(st+'_interp',0) or 0 for st in all_st]
        r['any_symptom_interp']=1 if any(v>0.05 for v in iv) else 0
        r['max_severity_interp']=round(max(iv),2)
        r['symptom_total_interp']=round(sum(iv),2)

# ── Assemble master ──
iq_meta=[{'file':f,'cst':datetime.fromtimestamp(os.path.getmtime(f),tz=LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S'),
    'freq_mhz':next((float(p.replace('MHz','')) for p in Path(f).stem.split('_') if 'MHz' in p),None),
    'size_bytes':os.path.getsize(f)} for f in sorted(glob.glob('captures/*.iq'))]
spec_data=[]
for sf in sorted(glob.glob('results/spectrograms/*.json')):
    try:
        with open(sf) as f: spec_data.append(json.load(f))
    except: pass
wideband=None
try:
    with open('results/wideband_survey_20260313.json') as f: wideband=json.load(f)
except: pass

nw=sum(1 for r in dataset if r.get('any_symptom'))
master={
    'metadata':{'generated':datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %I:%M:%S %p %Z'),'timezone':'Local (auto-DST)',
        'symptoms_joined':True,'symptom_columns':{f'sym_{s}':f'binary: {s}' for s in sorted(all_st)}},
    'timeline':dataset,'symptoms':symptoms,'iq_captures':iq_meta,'spectrograms':spec_data,
    'wideband_survey':wideband,
    'stats':{'total_rows':len(dataset),'active':sum(1 for d in dataset if d['type']=='ACTIVE'),
        'quiet':sum(1 for d in dataset if d['type']=='QUIET'),'gaps':sum(1 for d in dataset if d['type']=='GAP_NO_DATA'),
        'rows_with_symptoms':nw,'symptom_types':sorted(list(all_st)),
        'ei_max':max((d['ei_total'] for d in dataset if d.get('ei_total')),default=0),
        'monitoring_start':dataset[0]['cst'],'monitoring_end':dataset[-1]['cst']},
}
for s in symptoms: s.pop('_cst',None)

# ── Join pulse + BRF features from pulse_features.json + brf_timeseries.json ──
import bisect
try:
    with open('results/pulse_features.json') as f:
        pf_data = [r for r in json.load(f) if r.get('has_signal')]
    brf_lk = {}
    try:
        with open('results/brf_timeseries.json') as f:
            brf_lk = {r['file']: r for r in json.load(f).get('per_file', [])}
    except: pass
    # Build sorted time index
    pf_idx = []
    for pf in pf_data:
        try:
            mt = datetime.fromtimestamp(os.path.getmtime(pf['file'])).astimezone(LOCAL_TZ).replace(tzinfo=None)
            pf_idx.append((mt, pf))
        except: pass
    pf_idx.sort(key=lambda x: x[0])
    pf_times = [x[0] for x in pf_idx]
    td150 = timedelta(seconds=150)
    n_pj = 0
    for i, r in enumerate(dataset):
        t = tl_times[i]
        if t is None: continue
        lo = bisect.bisect_left(pf_times, t - td150)
        hi = bisect.bisect_right(pf_times, t + td150)
        nearby = [pf_idx[j][1] for j in range(lo, hi)]
        if not nearby:
            r['pulse_n_files'] = 0
            for k in ['pulse_width_mean_us','pulse_bw_mean_hz','pulse_modulation_index',
                       'pulse_prf_hz','pulse_n_bursts_mean','pulse_energy_total','pulse_duty_cycle',
                       'brf_mean_hz','brf_std_hz','brf_cv','brf_range_hz']:
                r[k] = None
            continue
        n_pj += 1
        def sm(vals):
            v = [x for x in vals if x]
            return round(float(np.mean(v)), 3) if v else None
        r['pulse_n_files'] = len(nearby)
        r['pulse_width_mean_us'] = sm([p.get('pulse_width_mean_us') for p in nearby])
        r['pulse_bw_mean_hz'] = sm([p.get('pulse_bw_mean_hz') for p in nearby])
        r['pulse_modulation_index'] = sm([p.get('modulation_index') for p in nearby])
        r['pulse_prf_hz'] = sm([p.get('prf_hz') for p in nearby])
        r['pulse_n_bursts_mean'] = sm([p.get('n_bursts') for p in nearby])
        r['pulse_energy_total'] = sm([p.get('pulse_energy_total') for p in nearby])
        r['pulse_duty_cycle'] = sm([p.get('duty_cycle') for p in nearby])
        bv = [brf_lk[p['file']] for p in nearby if p['file'] in brf_lk]
        r['brf_mean_hz'] = sm([b['brf_mean'] for b in bv])
        r['brf_std_hz'] = sm([b['brf_std'] for b in bv])
        r['brf_cv'] = sm([b['brf_cv'] for b in bv])
        r['brf_range_hz'] = sm([b['brf_range'] for b in bv])
    master['metadata']['pulse_features_joined'] = True
except Exception as e:
    n_pj = 0
    print(f'Pulse join skipped: {e}')

with open('results/ml_master_dataset.json','w') as f: json.dump(master,f,default=str)
print(f'OK: {len(dataset)} rows, {nw} with symptoms, {len(iq_meta)} IQ, {len(spec_data)} spectrograms, {n_pj} pulse-joined')
"

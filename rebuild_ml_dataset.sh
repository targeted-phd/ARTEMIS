#!/bin/bash
# Rebuild ML master dataset from all sentinel + symptom + IQ data
cd /home/tyler/projects/rf-monitor
.venv/bin/python3 -c "
import json, glob, os, numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=-6))
K_NOISE = 8.5
TARGETS = [622,624,628,630,632,634,636,826,828,830,832,834,878]
ZONE_A_START = datetime(2026, 3, 13, 16, 55, tzinfo=CST)

# ── Load all cycles, deduplicate ──
all_raw = []
for logf in sorted(glob.glob('results/sentinel_*.jsonl')):
    with open(logf) as f:
        for line in f:
            try:
                c = json.loads(line)
                ts_str = c.get('timestamp', '')
                if ts_str:
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00')).astimezone(CST)
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
                    dt=datetime.fromisoformat(ts.replace('Z','+00:00')).astimezone(CST)
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

all_st=set()
for r in dataset:
    for s in r.get('symptoms',[]): all_st.add(s)
for r in dataset:
    for st in sorted(all_st):
        # Single column per symptom: 0=absent, 1=mild, 2=moderate, 3=severe
        r[st] = r.get(f'sev_{st}', 0)
        # Clean up redundant columns
        r.pop(f'sym_{st}', None)
        r.pop(f'sev_{st}', None)
    r['any_symptom'] = 1 if r.get('symptoms') else 0
    r['max_severity'] = max((r.get(st, 0) for st in all_st), default=0)
    r['symptom_total'] = sum(r.get(st, 0) for st in all_st)

# ── Assemble master ──
iq_meta=[{'file':f,'cst':datetime.fromtimestamp(os.path.getmtime(f),tz=CST).strftime('%Y-%m-%d %H:%M:%S'),
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
    'metadata':{'generated':datetime.now(CST).strftime('%Y-%m-%d %I:%M:%S %p CST'),'timezone':'CST (UTC-6)',
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
with open('results/ml_master_dataset.json','w') as f: json.dump(master,f,default=str)
print(f'OK: {len(dataset)} rows, {nw} with symptoms, {len(iq_meta)} IQ, {len(spec_data)} spectrograms')
"

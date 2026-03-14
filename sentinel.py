#!/usr/bin/env python3
"""
RF Sentinel — Combined stare + sweep monitor (24h hardened).

Cycle:
  1. STARE: Rapid alternating captures on target frequencies
  2. SWEEP: Quick kurtosis scan of full band to detect frequency migration

Hardened for long runs:
  - Hourly log rotation (corruption only loses 1 hour)
  - fsync after every write
  - Periodic checkpoint saves (baseline + state)
  - IQ capture disk budget (capped at --iq-budget-mb)
  - Disk space monitoring
  - Hourly summary reports
  - All entries SHA-256 hashed
"""

import subprocess
import sys
import json
import signal
import hashlib
import time
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats as sp_stats

SAMPLE_RATE = 2_400_000
SETTLE_SAMPLES = 48_000
DC_NOTCH_BINS = 32
MIN_PULSE_SAMPLES = 3
RESULTS_DIR = os.environ.get("RESULTS_DIR", "results")
IQ_DUMP_DIR = os.environ.get("IQ_DUMP_DIR", "captures")
CHECKPOINT_FILE = os.environ.get("CHECKPOINT_FILE",
                                 os.path.join(RESULTS_DIR, "sentinel_checkpoint.json"))
NTFY_URL = os.environ.get("NTFY_URL", "http://100.96.113.92:8090/artemis-alerts")
TAG_URL = os.environ.get("TAG_URL", "http://100.96.113.92:8091/tag")

Path(RESULTS_DIR).mkdir(exist_ok=True)
Path(IQ_DUMP_DIR).mkdir(exist_ok=True)

_stop = False


# ── IO helpers ──────────────────────────────────────────────────────────────

def ntfy_push(level, max_kurt, active_freqs, cycle_num, stare_results=None):
    """Push alert to ntfy with self-contained RF context in button URLs.
    Each notification has a unique alert_id (nonce). Button URLs carry
    the alert_id + RF snapshot so the tag server needs no lookups."""
    try:
        import urllib.parse
        priorities = {"detect": "default", "high": "high", "critical": "urgent"}
        labels = {"detect": "DETECT", "high": "HIGH", "critical": "CRITICAL"}
        freq_str = ", ".join(f"{f:.0f}" for f in sorted(active_freqs)[:6])
        title = f"{labels.get(level, level)} — {len(active_freqs)} freqs active"
        body = (f"max_kurt={max_kurt:.0f} | freqs: {freq_str}\n"
                f"cycle {cycle_num} @ {datetime.now().strftime('%H:%M:%S')}")

        # Unique alert ID (nonce) — prevents replay, identifies event
        alert_id = hashlib.sha256(
            f"{cycle_num}-{time.time()}-{os.urandom(8).hex()}".encode()
        ).hexdigest()[:16]
        alert_ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        # Compact RF snapshot to embed in URL
        rf_snap = json.dumps({
            "c": cycle_num,
            "ts": alert_ts,
            "aid": alert_id,
            "mk": round(max_kurt, 1),
            "nf": len(active_freqs),
            "af": [round(f, 1) for f in sorted(active_freqs)[:10]],
        }, separators=(',', ':'))
        rf_encoded = urllib.parse.quote(rf_snap)

        def btn(label, symptom):
            return (f"http, {label}, {TAG_URL}?s={symptom}&rf={rf_encoded}, "
                    f"method=POST, clear=true")

        actions = "; ".join([
            btn("Speech", "speech"),
            btn("Paresthesia", "paresthesia"),
            btn("Headache", "headache"),
        ])

        subprocess.Popen([
            "curl", "-s", "-X", "POST", NTFY_URL,
            "-H", f"Title: {title}",
            "-H", f"Priority: {priorities.get(level, 'default')}",
            "-H", f"Tags: artemis,{level}",
            "-H", f"Actions: {actions}",
            "-d", body,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # never let ntfy failure block sentinel


def _generate_tone(freq_hz=800, duration_ms=200, sample_rate=44100):
    """Generate a raw PCM tone as bytes (signed 16-bit LE, mono)."""
    n_samples = int(sample_rate * duration_ms / 1000)
    t = np.arange(n_samples) / sample_rate
    # Apply envelope to avoid click
    tone = np.sin(2 * np.pi * freq_hz * t)
    env = np.ones(n_samples)
    fade = min(500, n_samples // 4)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    pcm = (tone * env * 30000).astype(np.int16)
    return pcm.tobytes()


def alert_sound(level="detect"):
    """Play audible alert via paplay raw PCM. Levels: detect, high, critical."""
    try:
        if level == "detect":
            pcm = _generate_tone(660, 150)
        elif level == "high":
            pcm = _generate_tone(880, 150) + _generate_tone(880, 150) + _generate_tone(880, 150)
        elif level == "critical":
            # Rising siren
            pcm = b""
            for f in [600, 800, 1000, 1200, 1000, 800]:
                pcm += _generate_tone(f, 100)
        else:
            return
        p = subprocess.Popen(
            ["paplay", "--raw", "--format=s16le", "--rate=44100", "--channels=1"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p.stdin.write(pcm)
        p.stdin.close()
    except (FileNotFoundError, BrokenPipeError, OSError):
        # Fall back to terminal bell
        sys.stdout.write("\a")
        sys.stdout.flush()


def write_flush(filepath, line):
    """Append line and force to disk."""
    with open(filepath, "a") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def save_checkpoint(path, data):
    """Atomic checkpoint: write to tmp then rename."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_checkpoint(path):
    """Load checkpoint if it exists."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def disk_free_mb():
    st = shutil.disk_usage("/")
    return st.free / (1024 * 1024)


def iq_dir_size_mb():
    total = 0
    for f in Path(IQ_DUMP_DIR).glob("*.iq"):
        total += f.stat().st_size
    return total / (1024 * 1024)


# ── RF helpers ──────────────────────────────────────────────────────────────

def capture_iq(freq_hz, dwell_ms, gain):
    num_samples = int(SAMPLE_RATE * dwell_ms / 1000)
    total = num_samples + SETTLE_SAMPLES
    nbytes = total * 2
    cmd = ["rtl_sdr", "-f", str(int(freq_hz)), "-s", str(SAMPLE_RATE),
           "-g", str(gain), "-n", str(nbytes), "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=15)
        if len(r.stdout) < nbytes:
            return None, None
        raw = r.stdout[:nbytes]
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None, None

    iq = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
    iq = (iq - 127.5) / 127.5
    z = iq[0::2] + 1j * iq[1::2]
    z = z[SETTLE_SAMPLES:]

    Z = np.fft.fft(z)
    h = DC_NOTCH_BINS // 2
    Z[:h] = 0
    Z[-h:] = 0
    z = np.fft.ifft(Z)
    return z, raw


def analyze_iq(iq, freq_hz):
    amp = np.abs(iq)
    mu = np.mean(amp)
    sigma = np.std(amp)
    kurt = float(sp_stats.kurtosis(amp, fisher=False))
    pwr = amp ** 2
    avg_pwr = np.mean(pwr)
    peak_pwr = np.max(pwr)
    papr_db = float(10 * np.log10(peak_pwr / avg_pwr)) if avg_pwr > 0 else 0

    thresh = mu + 4 * sigma
    above = (amp > thresh).astype(np.int8)
    pulses = []
    if np.any(above):
        diffs = np.diff(np.concatenate(([0], above, [0])))
        starts = np.where(diffs == 1)[0]
        ends = np.where(diffs == -1)[0]
        for s, e in zip(starts, ends):
            w = e - s
            if w >= MIN_PULSE_SAMPLES:
                pk = float(np.max(amp[s:e]))
                snr = round(20 * np.log10(pk / mu), 1) if mu > 0 else 0
                pulses.append({
                    "offset_us": round(s / SAMPLE_RATE * 1e6, 1),
                    "width_us": round(w / SAMPLE_RATE * 1e6, 2),
                    "snr_db": snr,
                })

    return {
        "freq_mhz": round(freq_hz / 1e6, 3),
        "kurtosis": round(kurt, 3),
        "papr_db": round(papr_db, 2),
        "mean_pwr_db": round(float(10 * np.log10(avg_pwr)) if avg_pwr > 0 else -999, 2),
        "pulse_count": len(pulses),
        "pulses": pulses[:15],
    }


def hash_data(data_str):
    return hashlib.sha256(data_str.encode()).hexdigest()[:16]


# ── Main sentinel ───────────────────────────────────────────────────────────

def jitter_freq(freq_hz, max_offset_mhz=1.5):
    """Add random frequency offset for wobble around target.
    Offset is uniform in [-max_offset, +max_offset] MHz."""
    offset = np.random.uniform(-max_offset_mhz, max_offset_mhz) * 1e6
    return int(freq_hz + offset)


def run_sentinel(target_freqs_mhz, sweep_start, sweep_stop, sweep_step,
                 gain, stare_dwell_ms, sweep_dwell_ms,
                 stare_pairs_per_cycle, duration_s, iq_budget_mb):

    target_freqs_hz = [int(f * 1e6) for f in target_freqs_mhz]
    sweep_freqs = np.arange(int(sweep_start * 1e6), int(sweep_stop * 1e6) + 1,
                            int(sweep_step * 1e6))

    ts_start = datetime.now()
    start_epoch = ts_start.timestamp()

    # Log file rotates hourly
    def log_path():
        return (f"{RESULTS_DIR}/sentinel_"
                f"{datetime.now().strftime('%Y%m%d_%H')}.jsonl")

    current_log = log_path()
    current_hour = datetime.now().hour

    print(f"\n{'='*72}")
    print(f"  RF SENTINEL — 24h Hardened Run")
    print(f"  Targets: {', '.join(f'{f:.0f}' for f in target_freqs_mhz)} MHz")
    print(f"  Sweep: {sweep_start:.0f}–{sweep_stop:.0f} MHz ({len(sweep_freqs)} ch)")
    print(f"  Stare: {stare_pairs_per_cycle} pairs/cycle @ {stare_dwell_ms}ms")
    print(f"  Duration: {duration_s/3600:.1f}h  |  Gain: {gain}dB")
    print(f"  IQ budget: {iq_budget_mb} MB  |  Disk free: {disk_free_mb():.0f} MB")
    print(f"  Log: {current_log} (rotates hourly)")
    print(f"  Checkpoint: {CHECKPOINT_FILE}")
    print(f"  Started: {ts_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*72}\n")

    # ── Try to resume from checkpoint ──
    ckpt = load_checkpoint(CHECKPOINT_FILE)
    if ckpt and ckpt.get("baseline"):
        print("  [RESUME] Found checkpoint, loading baseline...")
        baseline = {float(k): v for k, v in ckpt["baseline"].items()}
        bl_median = ckpt.get("bl_median", 8.0)
        bl_sigma = ckpt.get("bl_sigma", 1.0)
        target_history = ckpt.get("target_history", {})
        # Convert string keys back to float
        target_history = {float(k): v for k, v in target_history.items()}
        cycle_offset = ckpt.get("total_cycles", 0)
        total_migrations = ckpt.get("total_migrations", 0)
        print(f"  [RESUME] Baseline loaded ({len(baseline)} channels), "
              f"resuming from cycle {cycle_offset}")
    else:
        # ── Fresh baseline sweep ──
        print("  [INIT] Baseline sweep...")
        baseline = {}
        for freq in sweep_freqs:
            if _stop:
                break
            iq, _ = capture_iq(freq, sweep_dwell_ms, gain)
            if iq is None:
                continue
            r = analyze_iq(iq, freq)
            baseline[r["freq_mhz"]] = r["kurtosis"]
            sys.stdout.write(f"\r    {freq/1e6:.0f} MHz")
            sys.stdout.flush()

        bl_kurts = list(baseline.values())
        bl_median = float(np.median(bl_kurts))
        bl_mad = float(np.median(np.abs(np.array(bl_kurts) - bl_median)))
        bl_sigma = bl_mad * 1.4826 if bl_mad > 0 else 0.01
        target_history = {f: {"initial_kurt": baseline.get(f, 0)}
                          for f in target_freqs_mhz}
        cycle_offset = 0
        total_migrations = 0

        print(f"\n  [INIT] Baseline: median kurt={bl_median:.2f} σ={bl_sigma:.2f}")

    print(f"  [INIT] Target baseline kurtosis:")
    for f in target_freqs_mhz:
        bk = baseline.get(f, None)
        ik = target_history.get(f, {}).get("initial_kurt", bk)
        print(f"    {f:.0f} MHz: baseline={bk:.2f}"
              + (f"  initial={ik:.2f}" if ik != bk else "")
              if bk else f"    {f:.0f} MHz: no data")

    # Save initial checkpoint
    save_checkpoint(CHECKPOINT_FILE, {
        "baseline": baseline,
        "bl_median": bl_median,
        "bl_sigma": bl_sigma,
        "target_history": target_history,
        "total_cycles": cycle_offset,
        "total_migrations": total_migrations,
        "start_time": ts_start.isoformat(),
    })

    # ── Hourly stats accumulators ──
    hourly_stare_kurts = {f: [] for f in target_freqs_mhz}
    hourly_stare_pulses = {f: 0 for f in target_freqs_mhz}
    hourly_anomalies = []
    hourly_migrations = 0
    hourly_cycles = 0
    hourly_errors = 0
    last_checkpoint = time.time()

    cycle = 0
    while not _stop:
        elapsed = time.time() - start_epoch
        if elapsed > duration_s:
            break

        cycle += 1
        hourly_cycles += 1
        cycle_start = time.time()

        # ── Hourly log rotation ──
        now_hour = datetime.now().hour
        if now_hour != current_hour:
            # Print hourly summary before rotating
            print(f"\n{'─'*72}")
            print(f"  HOURLY SUMMARY — hour ending {datetime.now().strftime('%H:%M')}")
            print(f"  Cycles: {hourly_cycles}  |  Errors: {hourly_errors}")
            for f in target_freqs_mhz:
                k_list = hourly_stare_kurts[f]
                if k_list:
                    print(f"    {f:.0f} MHz: kurt mean={np.mean(k_list):.1f} "
                          f"range={min(k_list):.1f}–{max(k_list):.1f} "
                          f"pulses={hourly_stare_pulses[f]}")
            if hourly_anomalies:
                print(f"  New anomalies this hour: {len(hourly_anomalies)}")
                for a in hourly_anomalies[:5]:
                    print(f"    {a['freq_mhz']:.3f} MHz: kurt={a['kurtosis']:.1f}")
            if hourly_migrations > 0:
                print(f"  >>> MIGRATION EVENTS THIS HOUR: {hourly_migrations}")
            print(f"  IQ captures: {iq_dir_size_mb():.0f} MB / {iq_budget_mb} MB budget")
            print(f"  Disk free: {disk_free_mb():.0f} MB")
            print(f"{'─'*72}")

            # Reset hourly counters
            hourly_stare_kurts = {f: [] for f in target_freqs_mhz}
            hourly_stare_pulses = {f: 0 for f in target_freqs_mhz}
            hourly_anomalies = []
            hourly_migrations = 0
            hourly_cycles = 0
            hourly_errors = 0

            current_hour = now_hour
            current_log = log_path()
            print(f"\n  [LOG] Rotated to {current_log}")

        # ── Disk space check ──
        free_mb = disk_free_mb()
        if free_mb < 1000:
            print(f"\n  [WARN] Disk space low: {free_mb:.0f} MB free. "
                  "Stopping IQ saves.")
            iq_budget_mb = 0  # stop saving IQ
        if free_mb < 200:
            print(f"\n  [CRIT] Disk critically low ({free_mb:.0f} MB). Stopping.")
            break

        # ── STARE PHASE (interleaved Zone A + B with jitter) ──
        stare_results = {f: [] for f in target_freqs_mhz}

        # Shuffle target order each cycle to avoid bias
        cycle_targets = list(target_freqs_hz)
        np.random.shuffle(cycle_targets)

        for pair_i in range(stare_pairs_per_cycle):
            if _stop:
                break
            for freq_hz in cycle_targets:
                # Apply frequency jitter (wobble ±1.5 MHz)
                jittered = jitter_freq(freq_hz)
                try:
                    iq, raw = capture_iq(jittered, stare_dwell_ms, gain)
                except Exception as e:
                    hourly_errors += 1
                    continue
                if iq is None:
                    hourly_errors += 1
                    continue
                # Analyze at jittered freq but bucket under nominal target
                r = analyze_iq(iq, jittered)
                r["nominal_freq_mhz"] = round(freq_hz / 1e6, 3)
                r["jitter_mhz"] = round((jittered - freq_hz) / 1e6, 2)
                r["wall_time"] = time.time()
                r["elapsed_s"] = round(time.time() - start_epoch, 2)
                # Bucket under nominal frequency for aggregation
                nominal_mhz = round(freq_hz / 1e6, 1)
                stare_results.setdefault(nominal_mhz, []).append(r)

                # Track hourly stats
                hourly_stare_kurts.setdefault(r["freq_mhz"], []).append(r["kurtosis"])
                hourly_stare_pulses[r["freq_mhz"]] = \
                    hourly_stare_pulses.get(r["freq_mhz"], 0) + r["pulse_count"]

                # Save IQ if elevated kurtosis and within budget
                if r["kurtosis"] > 25 and iq_dir_size_mb() < iq_budget_mb:
                    ts = datetime.now().strftime("%H%M%S")
                    iq_f = f"{IQ_DUMP_DIR}/sentinel_{r['freq_mhz']:.0f}MHz_{ts}.iq"
                    with open(iq_f, "wb") as f:
                        f.write(raw)
                        f.flush()
                        os.fsync(f.fileno())

        # Print stare summary
        ts_now = datetime.now().strftime("%H:%M:%S")
        elapsed_h = elapsed / 3600
        print(f"\n  [{ts_now}] CYCLE {cycle + cycle_offset}  "
              f"({elapsed_h:.2f}h / {duration_s/3600:.0f}h)")
        print(f"  ├─ STARE:")
        for freq_mhz in target_freqs_mhz:
            results = stare_results.get(freq_mhz, [])
            if not results:
                print(f"  │  {freq_mhz:.0f} MHz: no data")
                continue
            kurts = [r["kurtosis"] for r in results]
            total_p = sum(r["pulse_count"] for r in results)
            print(f"  │  {freq_mhz:.0f} MHz: kurt={np.mean(kurts):.1f} "
                  f"(range {min(kurts):.1f}–{max(kurts):.1f})  "
                  f"total_pulses={total_p}")

            # Check if target dropped
            init_k = target_history.get(freq_mhz, {}).get("initial_kurt", 0)
            if init_k > bl_median + 3 * bl_sigma:
                if np.mean(kurts) < bl_median + bl_sigma:
                    print(f"  │  >>> TARGET DROPPED: {freq_mhz:.0f} MHz "
                          f"went from kurt={init_k:.1f} to {np.mean(kurts):.1f}")

        # ── AUDIBLE ALERT (rate-limited: notify on state CHANGE only) ──
        all_cycle_kurts = []
        for results in stare_results.values():
            all_cycle_kurts.extend(r["kurtosis"] for r in results)

        current_level = "quiet"
        if all_cycle_kurts:
            max_kurt = max(all_cycle_kurts)
            active_freqs = set()
            for fmhz, results in stare_results.items():
                if any(r["kurtosis"] > 20 for r in results):
                    active_freqs.add(fmhz)
            n_active_freqs = len(active_freqs)

            if max_kurt > 200 or n_active_freqs >= 6:
                current_level = "critical"
            elif max_kurt > 80 or n_active_freqs >= 4:
                current_level = "high"
            elif max_kurt > 30 or n_active_freqs >= 2:
                current_level = "detect"

            # Only send ntfy on state transitions (new activation, escalation,
            # de-escalation). Local beep plays every cycle for awareness.
            level_changed = (current_level != getattr(run_sentinel, '_prev_level', 'quiet'))
            run_sentinel._prev_level = current_level

            if current_level != "quiet":
                # Always beep locally (short, non-intrusive)
                alert_sound(current_level)
                print(f"  │  {'🔴' if current_level=='critical' else '🟡' if current_level=='high' else '🟢'} "
                      f"{current_level.upper()}: max_kurt={max_kurt:.0f} "
                      f"active_freqs={n_active_freqs} EI={ei_total:.0f}")

                # Only push ntfy notification on state change
                if level_changed:
                    ntfy_push(current_level, max_kurt, active_freqs,
                              cycle + cycle_offset)
        else:
            if getattr(run_sentinel, '_prev_level', 'quiet') != 'quiet':
                # Notify de-activation
                run_sentinel._prev_level = 'quiet'

        # ── SWEEP PHASE ──
        print(f"  ├─ SWEEP: ", end="", flush=True)
        sweep_results = []
        new_anomalies = []

        for freq in sweep_freqs[::3]:
            if _stop:
                break
            try:
                iq, _ = capture_iq(freq, sweep_dwell_ms, gain)
            except Exception:
                hourly_errors += 1
                continue
            if iq is None:
                continue
            r = analyze_iq(iq, freq)

            bl_kurt = baseline.get(r["freq_mhz"], bl_median)
            deviation = (r["kurtosis"] - bl_kurt) / bl_sigma

            if deviation > 5.0 and r["freq_mhz"] not in target_freqs_mhz:
                prev_kurt = baseline.get(r["freq_mhz"], bl_median)
                if r["kurtosis"] > prev_kurt * 2:
                    anom = {
                        **r,
                        "baseline_kurt": round(prev_kurt, 2),
                        "deviation_sigma": round(deviation, 1),
                    }
                    new_anomalies.append(anom)
                    hourly_anomalies.append(anom)

            sweep_results.append(r)

        print(f"{len(sweep_results)} channels scanned")

        if new_anomalies:
            print(f"  │")
            print(f"  ├─ >>> NEW ANOMALIES (not in target list):")
            for a in sorted(new_anomalies, key=lambda x: x["kurtosis"],
                            reverse=True)[:5]:
                print(f"  │  {a['freq_mhz']:.3f} MHz: kurt={a['kurtosis']:.1f} "
                      f"(was {a['baseline_kurt']:.1f}, +{a['deviation_sigma']:.0f}σ)  "
                      f"pulses={a['pulse_count']}")

            # Check for migration
            for freq_mhz in target_freqs_mhz:
                sr = stare_results.get(freq_mhz, [])
                if sr:
                    curr_kurt = np.mean([r["kurtosis"] for r in sr])
                    init_kurt = target_history.get(freq_mhz, {}).get("initial_kurt", 0)
                    if init_kurt > 20 and curr_kurt < init_kurt * 0.3:
                        print(f"  │")
                        print(f"  ╠══ MIGRATION EVENT DETECTED ══")
                        print(f"  ║  {freq_mhz:.0f} MHz dropped: "
                              f"{init_kurt:.0f} → {curr_kurt:.1f}")
                        print(f"  ║  New anomalies appeared at:")
                        for a in new_anomalies[:3]:
                            print(f"  ║    {a['freq_mhz']:.3f} MHz "
                                  f"(kurt={a['kurtosis']:.1f})")
                        print(f"  ╚══════════════════════════════")
                        total_migrations += 1
                        hourly_migrations += 1

        print(f"  └─ cycle time: {time.time() - cycle_start:.1f}s")

        # ── Log cycle (fsync'd) ──
        # ── EXPOSURE INDEX (Buckingham Pi) ──
        # EI = Σ_f [ P_linear × N_pulses × (kurtosis / k_noise) ]
        # Dimensionless, monotonic with actual RF exposure
        K_NOISE = 8.5
        ei_total, ei_zone_a, ei_zone_b = 0.0, 0.0, 0.0
        for fmhz, results in stare_results.items():
            for r in results:
                k = r.get("kurtosis", K_NOISE)
                p = r.get("pulse_count", 0)
                pwr_db = r.get("mean_pwr_db", -44)
                p_lin = 10 ** (pwr_db / 10)
                ei_r = p_lin * p * max(k / K_NOISE, 1.0)
                ei_total += ei_r
                f = r.get("freq_mhz", r.get("nominal_freq_mhz", fmhz))
                if isinstance(f, (int, float)):
                    if 618 < f < 640: ei_zone_a += ei_r
                    elif 820 < f < 840: ei_zone_b += ei_r

        cycle_entry = {
            "cycle": cycle + cycle_offset,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_s": round(elapsed, 1),
            "exposure_index": round(ei_total, 2),
            "ei_zone_a": round(ei_zone_a, 2),
            "ei_zone_b": round(ei_zone_b, 2),
            "stare": {str(f): results
                      for f, results in stare_results.items()},
            "new_anomalies": new_anomalies,
            "sweep_channels": len(sweep_results),
        }
        entry_str = json.dumps(cycle_entry, default=str)
        cycle_entry["hash"] = hash_data(entry_str)
        write_flush(current_log, json.dumps(cycle_entry, default=str))

        # ── Rolling baseline update ──
        for r in sweep_results:
            old = baseline.get(r["freq_mhz"], r["kurtosis"])
            baseline[r["freq_mhz"]] = old * 0.9 + r["kurtosis"] * 0.1

        # ── Checkpoint every 5 minutes ──
        if time.time() - last_checkpoint > 300:
            save_checkpoint(CHECKPOINT_FILE, {
                "baseline": baseline,
                "bl_median": bl_median,
                "bl_sigma": bl_sigma,
                "target_history": target_history,
                "total_cycles": cycle + cycle_offset,
                "total_migrations": total_migrations,
                "start_time": ts_start.isoformat(),
                "last_update": datetime.now(timezone.utc).isoformat(),
            })
            last_checkpoint = time.time()

    # ── Final checkpoint + summary ──
    save_checkpoint(CHECKPOINT_FILE, {
        "baseline": baseline,
        "bl_median": bl_median,
        "bl_sigma": bl_sigma,
        "target_history": target_history,
        "total_cycles": cycle + cycle_offset,
        "total_migrations": total_migrations,
        "start_time": ts_start.isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "status": "completed" if not _stop else "interrupted",
    })

    elapsed_total = time.time() - start_epoch
    print(f"\n{'='*72}")
    print(f"  SENTINEL COMPLETE — {cycle + cycle_offset} total cycles "
          f"in {elapsed_total/3600:.1f}h")
    print(f"  Migration events: {total_migrations}")
    print(f"  IQ captures: {iq_dir_size_mb():.0f} MB")
    print(f"  Logs: {RESULTS_DIR}/sentinel_*.jsonl")
    print(f"  Checkpoint: {CHECKPOINT_FILE}")
    print(f"{'='*72}\n")


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="RF Sentinel — 24h hardened stare + sweep monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 24-hour run with defaults
  python sentinel.py --duration 86400

  # Custom targets, wider sweep
  python sentinel.py --targets 826,828,830,832,834,878 --sweep-stop 1766

  # Resume from checkpoint (just run again, it auto-detects)
  python sentinel.py --duration 86400
        """
    )
    parser.add_argument("--targets", type=str,
                        default="622,624,628,630,632,634,636,826,828,830,832,834,878",
                        help="Comma-separated target freqs MHz (Zone A + Zone B)")
    parser.add_argument("--sweep-start", type=float, default=50)
    parser.add_argument("--sweep-stop", type=float, default=1000)
    parser.add_argument("--sweep-step", type=float, default=6)
    parser.add_argument("--gain", type=float, default=28.0)
    parser.add_argument("--stare-dwell", type=int, default=200)
    parser.add_argument("--sweep-dwell", type=int, default=100)
    parser.add_argument("--stare-pairs", type=int, default=5)
    parser.add_argument("--duration", type=int, default=86400,
                        help="Duration seconds (default: 86400 = 24h)")
    parser.add_argument("--iq-budget-mb", type=int, default=2000,
                        help="Max MB for IQ captures (default: 2000)")

    args = parser.parse_args()
    targets = [float(f.strip()) for f in args.targets.split(",")]

    global _stop
    signal.signal(signal.SIGINT, lambda s, f: (
        print("\n  [Ctrl-C] Finishing current cycle, then stopping..."),
        setattr(sys.modules[__name__], '_stop', True)
    ))

    run_sentinel(
        target_freqs_mhz=targets,
        sweep_start=args.sweep_start,
        sweep_stop=args.sweep_stop,
        sweep_step=args.sweep_step,
        gain=args.gain,
        stare_dwell_ms=args.stare_dwell,
        sweep_dwell_ms=args.sweep_dwell,
        stare_pairs_per_cycle=args.stare_pairs,
        duration_s=args.duration,
        iq_budget_mb=args.iq_budget_mb,
    )


if __name__ == "__main__":
    main()

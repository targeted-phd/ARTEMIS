#!/usr/bin/env python3
"""
High-Resolution RF Dataset Builder

Converts raw IQ captures into a windowed time-series dataset at
burst-level resolution (500 μs windows, 50% overlap).

Each IQ file (200-500ms) produces ~400-999 rows. Each row captures:
- Power/energy metrics
- Kurtosis
- Pulse count, widths, intervals
- Instantaneous frequency (modulation content)
- PRF and burst rate within the window

Cycle-level metadata (EI, symptoms, zone) is attached to every row
for ML training. Output is Parquet for efficient storage/loading.

Usage:
  python build_hires_dataset.py                # all IQ files
  python build_hires_dataset.py --limit 100    # first 100 files
  python build_hires_dataset.py --zone-a       # Zone A only
"""

import os
import sys
import json
import glob
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from scipy.stats import kurtosis as sp_kurt

SAMPLE_RATE = 2_400_000
SETTLE = 48_000
DC_NOTCH = 32
WINDOW_US = 1000  # 1 ms window
OVERLAP = 0.5     # 50% overlap
OUTPUT_DIR = Path("results/hires")
OUTPUT_DIR.mkdir(exist_ok=True)


def process_iq_file(filepath, window_us=WINDOW_US, overlap=OVERLAP):
    """Extract windowed features from one IQ file."""
    try:
        raw = np.fromfile(filepath, dtype=np.uint8)
        if len(raw) < (SETTLE + 2000) * 2:
            return None

        iq = (raw.astype(np.float32) - 127.5) / 127.5
        z = iq[0::2] + 1j * iq[1::2]
        z = z[SETTLE:]
        Z = np.fft.fft(z)
        h = DC_NOTCH // 2
        Z[:h] = 0; Z[-h:] = 0
        z = np.fft.ifft(Z)
        amp = np.abs(z)
        n = len(z)

        # Parse freq from filename
        freq = 0
        for part in Path(filepath).stem.split("_"):
            if "MHz" in part:
                try: freq = float(part.replace("MHz", ""))
                except: pass

        # File modification time
        try:
            mtime = os.path.getmtime(filepath)
        except:
            mtime = 0

        # Window parameters
        win_samples = int(window_us * 1e-6 * SAMPLE_RATE)
        stride = int(win_samples * (1 - overlap))
        n_windows = max(1, (n - win_samples) // stride + 1)

        # Global stats for threshold
        mu = np.mean(amp)
        sigma = np.std(amp)
        thresh = mu + 4 * sigma

        rows = []
        for w in range(n_windows):
            start = w * stride
            end = min(start + win_samples, n)
            seg = amp[start:end]
            seg_z = z[start:end]

            if len(seg) < win_samples // 2:
                continue

            # Power
            power = seg ** 2
            mean_pwr = float(np.mean(power))
            peak_pwr = float(np.max(power))
            rms = float(np.sqrt(mean_pwr))

            # Kurtosis
            kurt = float(sp_kurt(seg, fisher=False)) if len(seg) > 10 else 0

            # Pulses — use per-window threshold AND min 1 sample
            # Global threshold misses spikes in quiet windows
            seg_mu = np.mean(seg)
            seg_sigma = np.std(seg)
            local_thresh = max(seg_mu + 3 * seg_sigma, thresh * 0.5)
            above = (seg > local_thresh).astype(np.int8)
            diffs = np.diff(np.concatenate(([0], above, [0])))
            starts_p = np.where(diffs == 1)[0]
            ends_p = np.where(diffs == -1)[0]
            pulses = [(s, e) for s, e in zip(starts_p, ends_p) if e - s >= 1]
            n_pulses = len(pulses)

            # Pulse stats
            if pulses:
                widths = [(e-s)/SAMPLE_RATE*1e6 for s,e in pulses]
                mean_width = float(np.mean(widths))
                total_width = float(np.sum(widths))
                pulse_energy = sum(float(np.sum(seg[s:e]**2)) for s,e in pulses)
                pulse_frac = pulse_energy / (np.sum(power) + 1e-30)
            else:
                mean_width = 0; total_width = 0; pulse_frac = 0

            # IPI / PRF
            if len(pulses) >= 2:
                ipis = [(pulses[i+1][0] - pulses[i][0])/SAMPLE_RATE*1e6
                       for i in range(len(pulses)-1)]
                mean_ipi = float(np.mean(ipis))
                prf = 1e6/mean_ipi if mean_ipi > 0 else 0
            else:
                mean_ipi = 0; prf = 0

            # Instantaneous frequency
            phase = np.unwrap(np.angle(seg_z))
            inst_freq = np.diff(phase) / (2*np.pi) * SAMPLE_RATE
            freq_mean = float(np.mean(inst_freq))
            freq_std = float(np.std(inst_freq))

            # PAPR and peak spike amplitude
            papr = float(10 * np.log10(peak_pwr / mean_pwr)) if mean_pwr > 0 else 0
            peak_amp = float(np.max(seg))
            peak_snr = float(20 * np.log10(peak_amp / seg_mu)) if seg_mu > 0 else 0

            rows.append({
                "file": filepath,
                "freq_mhz": freq,
                "file_mtime": mtime,
                "window": w,
                "time_us": round(start / SAMPLE_RATE * 1e6, 1),
                "mean_power": round(mean_pwr, 8),
                "peak_power": round(peak_pwr, 6),
                "rms": round(rms, 6),
                "papr_db": round(papr, 2),
                "peak_snr_db": round(peak_snr, 1),
                "kurtosis": round(kurt, 2),
                "n_pulses": n_pulses,
                "mean_width_us": round(mean_width, 3),
                "total_width_us": round(total_width, 3),
                "mean_ipi_us": round(mean_ipi, 2),
                "prf_hz": round(prf, 0),
                "inst_freq_mean": round(freq_mean, 1),
                "inst_freq_std": round(freq_std, 1),
                "pulse_frac": round(float(pulse_frac), 4),
            })

        return rows
    except Exception as e:
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--zone-a", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    files = sorted(glob.glob("captures/*.iq"))
    if args.zone_a:
        files = [f for f in files if any(x in Path(f).stem for x in
            ['622','623','624','625','626','627','628','629',
             '630','631','632','633','634','635','636','637'])]
    if args.limit:
        files = files[:args.limit]

    print(f"Processing {len(files)} IQ files with {args.workers} workers")
    print(f"Window: {WINDOW_US} μs, Overlap: {OVERLAP*100:.0f}%")

    all_rows = []
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_iq_file, f): f for f in files}
        for future in as_completed(futures):
            rows = future.result()
            if rows:
                all_rows.extend(rows)
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(files)} — {len(all_rows)} rows")

    print(f"\nTotal: {len(all_rows)} rows from {len(files)} files")

    # Convert to DataFrame and save as Parquet
    df = pd.DataFrame(all_rows)

    # Add zone classification
    df["zone"] = "other"
    df.loc[(df.freq_mhz >= 618) & (df.freq_mhz < 640), "zone"] = "A"
    df.loc[(df.freq_mhz >= 820) & (df.freq_mhz < 840), "zone"] = "B"
    df.loc[(df.freq_mhz >= 870) & (df.freq_mhz < 890), "zone"] = "UL"

    # Sort by file time then window
    df = df.sort_values(["file_mtime", "window"]).reset_index(drop=True)

    outpath = OUTPUT_DIR / "hires_dataset.parquet"
    df.to_parquet(outpath, engine="pyarrow", compression="snappy")

    print(f"Saved: {outpath} ({os.path.getsize(outpath)/1e6:.1f} MB)")
    print(f"Columns: {list(df.columns)}")
    print(f"Zone distribution:")
    print(df.zone.value_counts().to_string())
    print(f"\nRow stats:")
    print(df[["kurtosis", "n_pulses", "prf_hz", "inst_freq_std"]].describe().round(1))


if __name__ == "__main__":
    main()

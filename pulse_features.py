#!/usr/bin/env python3
"""
Pulse-Level Feature Extractor — per-IQ-file burst and pulse analysis.

Processes raw IQ captures and extracts microsecond-resolution features:
- Per-pulse: width, amplitude, SNR, instantaneous frequency, bandwidth
- Per-burst: duration, pulse count, inter-pulse interval stats, spectral content
- Per-file: burst repetition rate, duty cycle, modulation index

Output: results/pulse_features.json — one entry per IQ file, ready for ML.
"""

import os
import sys
import json
import glob
import numpy as np
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

SAMPLE_RATE = 2_400_000
SETTLE_SAMPLES = 48_000
DC_NOTCH_BINS = 32
MIN_PULSE_SAMPLES = 3
CAPTURES_DIR = os.environ.get("IQ_DUMP_DIR", "captures")
OUTPUT_FILE = "results/pulse_features.json"


def load_iq(filepath):
    """Load RTL-SDR IQ, strip settle, DC notch."""
    raw = np.fromfile(filepath, dtype=np.uint8)
    if len(raw) < (SETTLE_SAMPLES + 1000) * 2:
        return None
    iq = (raw.astype(np.float32) - 127.5) / 127.5
    z = iq[0::2] + 1j * iq[1::2]
    z = z[SETTLE_SAMPLES:]
    Z = np.fft.fft(z)
    h = DC_NOTCH_BINS // 2
    Z[:h] = 0
    Z[-h:] = 0
    z = np.fft.ifft(Z)
    return z


def extract_freq_from_name(filename):
    name = Path(filename).stem
    for part in name.split("_"):
        if "MHz" in part:
            try:
                return float(part.replace("MHz", ""))
            except ValueError:
                pass
    return 0


def detect_pulses_detailed(z):
    """Detect pulses and extract detailed per-pulse features."""
    amp = np.abs(z)
    mu = np.mean(amp)
    sigma = np.std(amp)
    thresh = mu + 4 * sigma

    above = (amp > thresh).astype(np.int8)
    diffs = np.diff(np.concatenate(([0], above, [0])))
    starts = np.where(diffs == 1)[0]
    ends = np.where(diffs == -1)[0]

    # Phase for instantaneous frequency
    phase = np.unwrap(np.angle(z))
    inst_freq = np.diff(phase) / (2 * np.pi) * SAMPLE_RATE

    pulses = []
    for s, e in zip(starts, ends):
        width_samples = e - s
        if width_samples < MIN_PULSE_SAMPLES:
            continue

        width_us = width_samples / SAMPLE_RATE * 1e6
        peak_amp = float(np.max(amp[s:e]))
        mean_amp = float(np.mean(amp[s:e]))
        snr_db = float(20 * np.log10(peak_amp / mu)) if mu > 0 else 0

        # Instantaneous frequency during pulse
        if e - 1 > s and e - 1 < len(inst_freq):
            pf = inst_freq[s:e - 1]
            if len(pf) > 0:
                mean_freq = float(np.mean(pf))
                std_freq = float(np.std(pf))
                bw = float(np.max(pf) - np.min(pf))
            else:
                mean_freq = std_freq = bw = 0.0
        else:
            mean_freq = std_freq = bw = 0.0

        # Energy (amplitude² × duration)
        energy = float(np.sum(amp[s:e] ** 2)) / SAMPLE_RATE * 1e6

        pulses.append({
            "start_sample": int(s),
            "width_us": round(width_us, 3),
            "peak_amp": round(peak_amp, 5),
            "mean_amp": round(mean_amp, 5),
            "snr_db": round(snr_db, 1),
            "inst_freq_mean_hz": round(mean_freq, 1),
            "inst_freq_std_hz": round(std_freq, 1),
            "bandwidth_hz": round(bw, 1),
            "energy": round(energy, 4),
        })

    return pulses, float(mu), float(sigma), float(thresh)


def detect_bursts(pulses):
    """Group pulses into bursts based on inter-pulse intervals."""
    if len(pulses) < 2:
        return [], []

    # Inter-pulse intervals
    ipis = []
    for i in range(1, len(pulses)):
        gap_us = (pulses[i]["start_sample"] - pulses[i - 1]["start_sample"]) / SAMPLE_RATE * 1e6
        ipis.append(gap_us)

    if not ipis:
        return [], ipis

    # Burst detection: gap > 5× median IPI = burst boundary
    median_ipi = np.median(ipis)
    burst_threshold = max(median_ipi * 5, 100)  # at least 100 μs gap

    bursts = []
    current_burst = [pulses[0]]
    for i, ipi in enumerate(ipis):
        if ipi > burst_threshold:
            # End of burst
            if len(current_burst) >= 2:
                bursts.append(current_burst)
            current_burst = [pulses[i + 1]]
        else:
            current_burst.append(pulses[i + 1])
    if len(current_burst) >= 2:
        bursts.append(current_burst)

    return bursts, ipis


def extract_features(filepath):
    """Extract all pulse-level features from one IQ file."""
    try:
        z = load_iq(filepath)
        if z is None:
            return None

        freq_mhz = extract_freq_from_name(filepath)
        n_samples = len(z)
        duration_ms = n_samples / SAMPLE_RATE * 1000

        # Detect pulses
        pulses, noise_mean, noise_std, thresh = detect_pulses_detailed(z)

        if not pulses:
            return {
                "file": filepath,
                "freq_mhz": freq_mhz,
                "n_samples": n_samples,
                "duration_ms": round(duration_ms, 2),
                "n_pulses": 0,
                "n_bursts": 0,
                "has_signal": False,
            }

        # Detect bursts
        bursts, ipis = detect_bursts(pulses)

        # Per-pulse stats
        widths = [p["width_us"] for p in pulses]
        snrs = [p["snr_db"] for p in pulses]
        bws = [p["bandwidth_hz"] for p in pulses]
        energies = [p["energy"] for p in pulses]
        inst_freqs = [p["inst_freq_mean_hz"] for p in pulses]

        # Per-burst stats
        burst_features = []
        for burst in bursts:
            b_widths = [p["width_us"] for p in burst]
            b_snrs = [p["snr_db"] for p in burst]
            b_bws = [p["bandwidth_hz"] for p in burst]
            b_start = burst[0]["start_sample"]
            b_end = burst[-1]["start_sample"] + int(burst[-1]["width_us"] * SAMPLE_RATE / 1e6)
            b_duration_us = (b_end - b_start) / SAMPLE_RATE * 1e6

            # Intra-burst IPIs
            b_ipis = []
            for j in range(1, len(burst)):
                gap = (burst[j]["start_sample"] - burst[j - 1]["start_sample"]) / SAMPLE_RATE * 1e6
                b_ipis.append(gap)

            burst_features.append({
                "n_pulses": len(burst),
                "duration_us": round(b_duration_us, 1),
                "mean_width_us": round(float(np.mean(b_widths)), 3),
                "std_width_us": round(float(np.std(b_widths)), 3),
                "mean_snr_db": round(float(np.mean(b_snrs)), 1),
                "mean_bw_hz": round(float(np.mean(b_bws)), 1),
                "mean_ipi_us": round(float(np.mean(b_ipis)), 2) if b_ipis else 0,
                "std_ipi_us": round(float(np.std(b_ipis)), 2) if b_ipis else 0,
                "prf_hz": round(1e6 / float(np.mean(b_ipis)), 0) if b_ipis and np.mean(b_ipis) > 0 else 0,
            })

        # Aggregate features for ML
        total_pulse_duration_us = sum(widths)
        duty_cycle = total_pulse_duration_us / (duration_ms * 1000)

        # Inter-burst intervals
        if len(bursts) >= 2:
            ibi_list = []
            for k in range(1, len(bursts)):
                gap = (bursts[k][0]["start_sample"] - bursts[k - 1][-1]["start_sample"]) / SAMPLE_RATE * 1e6
                ibi_list.append(gap)
            mean_ibi = float(np.mean(ibi_list))
            burst_rep_rate = 1e6 / mean_ibi if mean_ibi > 0 else 0
        else:
            mean_ibi = 0
            burst_rep_rate = 0

        # Modulation index: how much does inst_freq vary across pulses?
        if len(inst_freqs) > 1:
            mod_index = float(np.std(inst_freqs) / (np.mean(np.abs(inst_freqs)) + 1e-10))
        else:
            mod_index = 0

        return {
            "file": filepath,
            "freq_mhz": freq_mhz,
            "n_samples": n_samples,
            "duration_ms": round(duration_ms, 2),
            "has_signal": True,
            # Pulse-level aggregates
            "n_pulses": len(pulses),
            "pulse_width_mean_us": round(float(np.mean(widths)), 3),
            "pulse_width_std_us": round(float(np.std(widths)), 3),
            "pulse_width_median_us": round(float(np.median(widths)), 3),
            "pulse_snr_mean_db": round(float(np.mean(snrs)), 1),
            "pulse_snr_max_db": round(float(np.max(snrs)), 1),
            "pulse_bw_mean_hz": round(float(np.mean(bws)), 1),
            "pulse_bw_std_hz": round(float(np.std(bws)), 1),
            "pulse_bw_max_hz": round(float(np.max(bws)), 1),
            "pulse_energy_mean": round(float(np.mean(energies)), 6),
            "pulse_energy_total": round(float(np.sum(energies)), 4),
            "total_pulse_duration_us": round(total_pulse_duration_us, 1),
            "duty_cycle": round(duty_cycle, 6),
            # IPI stats
            "ipi_mean_us": round(float(np.mean(ipis)), 2) if ipis else 0,
            "ipi_std_us": round(float(np.std(ipis)), 2) if ipis else 0,
            "ipi_median_us": round(float(np.median(ipis)), 2) if ipis else 0,
            "prf_hz": round(1e6 / float(np.median(ipis)), 0) if ipis and np.median(ipis) > 0 else 0,
            # Burst-level
            "n_bursts": len(bursts),
            "burst_rep_rate_hz": round(burst_rep_rate, 1),
            "mean_ibi_us": round(mean_ibi, 1),
            "burst_n_pulses_mean": round(float(np.mean([b["n_pulses"] for b in burst_features])), 1) if burst_features else 0,
            "burst_duration_mean_us": round(float(np.mean([b["duration_us"] for b in burst_features])), 1) if burst_features else 0,
            "burst_prf_mean_hz": round(float(np.mean([b["prf_hz"] for b in burst_features])), 0) if burst_features else 0,
            # Modulation
            "modulation_index": round(mod_index, 4),
            "inst_freq_mean_hz": round(float(np.mean(inst_freqs)), 1) if inst_freqs else 0,
            "inst_freq_std_hz": round(float(np.std(inst_freqs)), 1) if inst_freqs else 0,
            # Noise floor
            "noise_mean": round(noise_mean, 6),
            "noise_std": round(noise_std, 6),
        }
    except Exception as e:
        return {"file": filepath, "error": str(e), "has_signal": False}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pulse-Level Feature Extractor")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Process only N files (0=all)")
    args = parser.parse_args()

    iq_files = sorted(glob.glob(f"{CAPTURES_DIR}/*.iq"))
    if args.limit:
        iq_files = iq_files[:args.limit]

    print(f"Pulse Feature Extraction — {len(iq_files)} IQ files, {args.workers} workers")
    print(f"Output: {OUTPUT_FILE}")

    results = []
    n_signal = 0
    n_empty = 0
    n_error = 0

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(extract_features, f): f for f in iq_files}
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result is None:
                n_error += 1
            elif result.get("has_signal"):
                results.append(result)
                n_signal += 1
            else:
                results.append(result)
                n_empty += 1

            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(iq_files)} — {n_signal} signal, {n_empty} empty, {n_error} errors")

    # Sort by filename
    results.sort(key=lambda x: x.get("file", ""))

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f)

    print(f"\nDone: {len(results)} files processed")
    print(f"  Signal: {n_signal}")
    print(f"  Empty:  {n_empty}")
    print(f"  Errors: {n_error}")
    print(f"Saved to {OUTPUT_FILE}")

    # Quick stats
    signal_files = [r for r in results if r.get("has_signal")]
    if signal_files:
        prfs = [r["prf_hz"] for r in signal_files if r.get("prf_hz", 0) > 0]
        widths = [r["pulse_width_mean_us"] for r in signal_files if r.get("pulse_width_mean_us", 0) > 0]
        bws = [r["pulse_bw_mean_hz"] for r in signal_files if r.get("pulse_bw_mean_hz", 0) > 0]
        n_bursts = [r["n_bursts"] for r in signal_files]
        print(f"\n  PRF: {np.mean(prfs):.0f} ± {np.std(prfs):.0f} Hz (n={len(prfs)})")
        print(f"  Width: {np.mean(widths):.2f} ± {np.std(widths):.2f} μs")
        print(f"  BW: {np.mean(bws):.0f} ± {np.std(bws):.0f} Hz")
        print(f"  Bursts/file: {np.mean(n_bursts):.1f} ± {np.std(n_bursts):.1f}")


if __name__ == "__main__":
    main()

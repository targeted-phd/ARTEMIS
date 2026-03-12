#!/usr/bin/env python3
"""
Post-process scan results: classify and find within-band anomalies.

A signal hiding inside a cellular band would show up as:
  - Power outlier relative to its band neighbors
  - Kurtosis outlier relative to its band neighbors
  - Spectral flatness outlier (different modulation)
"""

import json
import sys
import numpy as np
from pathlib import Path
from known_bands import classify_freq, KNOWN_BANDS


def load_scan(scan_file):
    """Load scan results (flagged + all from JSONL log)."""
    with open(scan_file) as f:
        data = json.load(f)

    # Try to load full JSONL log for all channels (not just flagged)
    all_results = []
    log_path = Path("results/pulse_scan.jsonl")
    if log_path.exists():
        scan_start = data.get("scan_start", "")
        with open(log_path) as f:
            for line in f:
                try:
                    r = json.loads(line.strip())
                    # include results from this scan's timeframe
                    if r.get("timestamp", "") >= scan_start:
                        all_results.append(r)
                except json.JSONDecodeError:
                    continue

    if not all_results:
        all_results = data.get("flagged", [])

    return data, all_results


def within_band_analysis(all_results):
    """Find channels anomalous relative to their own band."""
    # Group all channels by band
    by_band = {}
    for r in all_results:
        freq = r["freq_mhz"]
        band_name, band_type = classify_freq(freq)
        key = band_name or f"unknown_{freq}"
        by_band.setdefault(key, []).append(r)

    anomalies = []

    for band_name, channels in by_band.items():
        if len(channels) < 3:
            continue  # need enough channels to establish band baseline

        kurts = np.array([c["kurtosis"] for c in channels])
        pwrs = np.array([c.get("mean_pwr_db", c.get("mean_power_db", -99)) for c in channels])
        paprs = np.array([c["papr_db"] for c in channels])
        flats = np.array([c.get("spectral_flatness", 0) for c in channels])

        # Robust stats (median + MAD)
        def outlier_score(vals):
            med = np.median(vals)
            mad = np.median(np.abs(vals - med))
            sigma = mad * 1.4826 if mad > 0 else 1e-6
            return (vals - med) / sigma, med, sigma

        k_z, k_med, k_sig = outlier_score(kurts)
        p_z, p_med, p_sig = outlier_score(pwrs)
        papr_z, papr_med, papr_sig = outlier_score(paprs)

        for i, ch in enumerate(channels):
            reasons = []
            if k_z[i] > 3.0:
                reasons.append(f"kurtosis +{k_z[i]:.1f}σ within band "
                              f"({ch['kurtosis']:.1f} vs band median {k_med:.1f})")
            if p_z[i] > 3.0:
                pwr = pwrs[i]
                reasons.append(f"power +{p_z[i]:.1f}σ within band "
                              f"({pwr:.1f}dB vs band median {p_med:.1f}dB)")
            if papr_z[i] > 3.0:
                reasons.append(f"PAPR +{papr_z[i]:.1f}σ within band "
                              f"({ch['papr_db']:.1f}dB vs band median {papr_med:.1f}dB)")
            if reasons:
                anomalies.append({
                    **ch,
                    "band_name": band_name,
                    "within_band_reasons": reasons,
                    "band_kurtosis_median": round(float(k_med), 2),
                    "band_power_median": round(float(p_med), 2),
                    "band_channels": len(channels),
                })

    return anomalies


def analyze(scan_file):
    data, all_results = load_scan(scan_file)
    flagged = data.get("flagged", [])

    # ── Classification ──
    known_flags = []
    unknown_flags = []
    for r in flagged:
        band_name, band_type = classify_freq(r["freq_mhz"])
        r["band_name"] = band_name
        r["band_type"] = band_type
        if band_name:
            known_flags.append(r)
        else:
            unknown_flags.append(r)

    # ── Within-band anomalies ──
    wb_anomalies = within_band_analysis(all_results)

    print(f"\n{'='*72}")
    print(f"  DEEP SCAN ANALYSIS")
    print(f"  {len(all_results)} total channels  |  {len(flagged)} flagged vs baseline")
    print(f"  {len(unknown_flags)} in unallocated spectrum  |  {len(wb_anomalies)} within-band outliers")
    print(f"{'='*72}")

    # ── Section 1: Within-band anomalies (hidden signals) ──
    if wb_anomalies:
        print(f"\n  === WITHIN-BAND ANOMALIES (potential hidden signals) ===")
        print(f"  These channels deviate from their own band's statistics.\n")
        for r in sorted(wb_anomalies, key=lambda x: x["kurtosis"], reverse=True):
            print(f"    {r['freq_mhz']:10.3f} MHz  [{r['band_name']}]")
            print(f"{'':>14}kurt={r['kurtosis']:.1f}  papr={r['papr_db']:.1f}dB  "
                  f"pulses={r['pulse_count']}  "
                  f"(band median kurt={r['band_kurtosis_median']:.1f}  "
                  f"n={r['band_channels']}ch)")
            for reason in r["within_band_reasons"]:
                print(f"{'':>14}  >> {reason}")
            for p in r.get("pulses", [])[:3]:
                print(f"{'':>18}@ {p['offset_ms']:.1f}ms  "
                      f"width={p['width_us']}µs  snr={p['peak_snr_db']}dB")
            print()
    else:
        print("\n  No within-band anomalies detected.")

    # ── Section 2: Unallocated spectrum ──
    if unknown_flags:
        print(f"\n  === UNALLOCATED SPECTRUM DETECTIONS ===\n")
        for r in sorted(unknown_flags, key=lambda x: x["kurtosis"], reverse=True):
            print(f"    {r['freq_mhz']:10.3f} MHz  [NO KNOWN ALLOCATION]")
            print(f"{'':>14}kurt={r['kurtosis']:.1f}  papr={r['papr_db']:.1f}dB  "
                  f"flat={r.get('spectral_flatness', 0):.3f}  "
                  f"pulses={r['pulse_count']}")
            for p in r.get("pulses", [])[:3]:
                print(f"{'':>18}@ {p['offset_ms']:.1f}ms  "
                      f"width={p['width_us']}µs  snr={p['peak_snr_db']}dB")
    else:
        print("\n  No detections in unallocated spectrum.")

    # ── Section 3: Known band summary ──
    print(f"\n  === KNOWN BAND SUMMARY ===\n")
    by_band = {}
    for r in all_results:
        band_name, band_type = classify_freq(r["freq_mhz"])
        key = band_name or "unallocated"
        by_band.setdefault(key, []).append(r)

    for band_name, channels in sorted(by_band.items(),
                                       key=lambda x: x[1][0]["freq_mhz"]):
        if band_name == "unallocated":
            continue
        kurts = [c["kurtosis"] for c in channels]
        pwrs = [c.get("mean_pwr_db", c.get("mean_power_db", -99)) for c in channels]
        freqs = [c["freq_mhz"] for c in channels]
        _, btype = classify_freq(freqs[0])
        n_flagged = sum(1 for c in channels if c.get("flagged", False))
        print(f"    {min(freqs):7.0f}–{max(freqs):.0f} MHz  [{btype:>12}]  {band_name}")
        print(f"{'':>14}{len(channels)} ch  "
              f"kurt: {min(kurts):.1f}–{max(kurts):.1f} (med {np.median(kurts):.1f})  "
              f"pwr: {min(pwrs):.0f} to {max(pwrs):.0f} dB  "
              f"flagged: {n_flagged}")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        scans = sorted(Path("results").glob("scan_*.json"))
        if not scans:
            print("No scan files found.")
            sys.exit(1)
        scan_file = str(scans[-1])
    else:
        scan_file = sys.argv[1]

    print(f"  Analyzing: {scan_file}")
    analyze(scan_file)

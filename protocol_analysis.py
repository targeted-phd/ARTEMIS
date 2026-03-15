#!/usr/bin/env python3
"""
Protocol Elimination Analysis — Test IQ captures against known signal types.

For each capture, measures signal characteristics and compares against
known protocol signatures to rule them out systematically.

Usage:
  python protocol_analysis.py analyze captures/some_file.iq
  python protocol_analysis.py batch [--dir captures/ --limit 50]
  python protocol_analysis.py report
"""

import argparse
import json
import os
import sys
import glob
from pathlib import Path
from collections import Counter

import numpy as np
from scipy import stats as sp_stats
from scipy.signal import welch, find_peaks
from scipy.fft import fft, ifft

SAMPLE_RATE = 2_400_000
SETTLE_SAMPLES = 48_000
DC_NOTCH_BINS = 32
RESULTS_DIR = Path("results")

# ── Known Protocol Signatures ──────────────────────────────────────────────
# Each protocol has characteristic parameters. If the signal matches,
# it's that protocol. If it doesn't match ANY, it's unknown/anomalous.

KNOWN_PROTOCOLS = {
    "LTE_FDD": {
        "description": "LTE Frequency Division Duplex",
        "symbol_rates": [15000, 30720000],  # subcarrier spacing / sample rate
        "frame_duration_ms": 10.0,
        "subframe_duration_ms": 1.0,
        "slot_duration_ms": 0.5,
        "cyclic_prefix_us": [4.69, 5.21, 16.67],
        "bandwidth_mhz": [1.4, 3, 5, 10, 15, 20],
        "modulation": ["QPSK", "16QAM", "64QAM"],
        "expected_bands_mhz": [[869, 894], [1930, 1990], [2110, 2155]],  # downlink
        "NOT_expected": [[824, 849]],  # uplink — towers don't transmit here
    },
    "GSM": {
        "description": "Global System for Mobile Communications",
        "symbol_rate": 270833,
        "timeslot_duration_us": 577,
        "frame_duration_ms": 4.615,
        "bandwidth_khz": 200,
        "modulation": "GMSK",
        "expected_bands_mhz": [[869, 894], [1930, 1990]],
        "guard_period_us": 30.46,
    },
    "CDMA_IS95": {
        "description": "Code Division Multiple Access",
        "chip_rate": 1228800,
        "bandwidth_mhz": 1.25,
        "modulation": "BPSK/QPSK",
        "expected_bands_mhz": [[869, 894]],
    },
    "WiFi_2G": {
        "description": "IEEE 802.11 b/g/n (2.4 GHz)",
        "expected_bands_mhz": [[2400, 2483]],
        "bandwidth_mhz": [20, 40],
        "modulation": "OFDM/DSSS",
    },
    "WiFi_5G": {
        "description": "IEEE 802.11 a/n/ac (5 GHz)",
        "expected_bands_mhz": [[5150, 5825]],
    },
    "Bluetooth": {
        "description": "Bluetooth Classic / BLE",
        "expected_bands_mhz": [[2402, 2480]],
        "bandwidth_mhz": 1,
        "hop_rate_hz": 1600,
    },
    "FM_Broadcast": {
        "description": "FM Radio Broadcasting",
        "expected_bands_mhz": [[88, 108]],
        "bandwidth_khz": 200,
        "modulation": "FM",
    },
    "ATSC_DTV": {
        "description": "Digital Television (ATSC)",
        "expected_bands_mhz": [[470, 698]],
        "bandwidth_mhz": 6,
        "symbol_rate": 10762238,
        "modulation": "8VSB",
    },
    "P25": {
        "description": "Project 25 (public safety radio)",
        "symbol_rate": 4800,
        "bandwidth_khz": 12.5,
        "modulation": "C4FM",
    },
    "DMR": {
        "description": "Digital Mobile Radio",
        "symbol_rate": 4800,
        "bandwidth_khz": 12.5,
        "timeslot_duration_ms": 30,
    },
    "ADS_B": {
        "description": "Aircraft transponder",
        "expected_bands_mhz": [[1090, 1090]],
    },
    "NOAA_Weather": {
        "description": "NOAA Weather Radio",
        "expected_bands_mhz": [[162.4, 162.55]],
    },
    "Radar_ATC": {
        "description": "Air Traffic Control Radar",
        "expected_bands_mhz": [[1215, 1400], [2700, 2900], [9000, 9500]],
        "prf_hz": [200, 4000],  # typical range
        "pulse_width_us": [0.5, 100],
    },
    "Pager_POCSAG": {
        "description": "POCSAG Pager",
        "symbol_rate": [512, 1200, 2400],
        "modulation": "FSK",
    },
}


def load_iq(filepath):
    """Load RTL-SDR raw IQ."""
    raw = np.fromfile(filepath, dtype=np.uint8)
    iq = (raw[0::2].astype(np.float32) - 127.5) + \
         1j * (raw[1::2].astype(np.float32) - 127.5)
    if len(iq) > SETTLE_SAMPLES:
        iq = iq[SETTLE_SAMPLES:]
    if len(iq) > 1024:
        spectrum = fft(iq)
        n = len(spectrum)
        spectrum[:DC_NOTCH_BINS] = 0
        spectrum[n - DC_NOTCH_BINS:] = 0
        iq = ifft(spectrum)
    return iq


def parse_freq_from_filename(fname):
    """Extract frequency in MHz from filename."""
    base = os.path.basename(fname).replace(".iq", "")
    for part in base.split("_"):
        if "MHz" in part:
            try:
                return float(part.replace("MHz", ""))
            except ValueError:
                pass
    return None


def analyze_signal(iq, freq_mhz):
    """Compute signal characteristics for protocol matching."""
    amp = np.abs(iq).astype(np.float32)
    n = len(amp)
    duration_s = n / SAMPLE_RATE

    result = {
        "n_samples": n,
        "duration_ms": round(duration_s * 1000, 2),
        "freq_mhz": freq_mhz,
    }

    # Basic stats
    mu = np.mean(amp)
    sigma = np.std(amp)
    kurt = float(sp_stats.kurtosis(amp, fisher=False))
    result["kurtosis"] = round(kurt, 2)
    result["mean_amplitude"] = round(float(mu), 6)
    result["std_amplitude"] = round(float(sigma), 6)

    # Power spectrum
    f_welch, psd = welch(iq, fs=SAMPLE_RATE, nperseg=min(4096, n // 2),
                         return_onesided=False)
    psd_db = 10 * np.log10(np.abs(psd) + 1e-12)

    # Occupied bandwidth (-20 dB from peak)
    peak_psd = np.max(psd_db)
    bw_mask = psd_db > (peak_psd - 20)
    if np.any(bw_mask):
        occupied_bw = np.sum(bw_mask) * (SAMPLE_RATE / len(psd))
    else:
        occupied_bw = 0
    result["occupied_bw_khz"] = round(occupied_bw / 1000, 1)

    # Spectral flatness
    geo_mean = np.exp(np.mean(np.log(np.abs(psd) + 1e-12)))
    arith_mean = np.mean(np.abs(psd)) + 1e-12
    result["spectral_flatness"] = round(float(geo_mean / arith_mean), 5)

    # Pulse detection
    thresh = mu + 4 * sigma
    above = (amp > thresh).astype(np.int8)
    diffs = np.diff(np.concatenate(([0], above, [0])))
    starts = np.where(diffs == 1)[0]
    ends = np.where(diffs == -1)[0]
    pulses = []
    for s, e in zip(starts, ends):
        w = e - s
        if w >= 3:
            pulses.append({"start": int(s), "width_samples": int(w),
                          "width_us": round(w / SAMPLE_RATE * 1e6, 2),
                          "peak_amp": round(float(np.max(amp[s:e])), 4)})

    result["pulse_count"] = len(pulses)

    if pulses:
        widths = [p["width_us"] for p in pulses]
        result["pulse_width_mean_us"] = round(np.mean(widths), 2)
        result["pulse_width_std_us"] = round(np.std(widths), 2)
        result["pulse_width_min_us"] = round(min(widths), 2)
        result["pulse_width_max_us"] = round(max(widths), 2)

        # PRF from inter-pulse intervals
        if len(pulses) > 1:
            ipis = np.diff([p["start"] for p in pulses]) / SAMPLE_RATE
            ipis = ipis[ipis > 0]
            if len(ipis) > 0:
                prf = 1.0 / np.mean(ipis)
                result["prf_hz"] = round(prf, 0)
                result["prf_regularity_cv"] = round(float(np.std(ipis) / (np.mean(ipis) + 1e-12)), 4)

    # Duty cycle
    if n > 0:
        result["duty_cycle_pct"] = round(float(np.sum(above)) / n * 100, 4)

    # Symbol rate detection (autocorrelation peaks)
    if n > 2000:
        ac = np.correlate(amp[:min(8192, n)], amp[:min(8192, n)], mode='full')
        ac = ac[len(ac) // 2:]
        ac = ac / (ac[0] + 1e-12)
        # Find first significant peak after lag 0
        peaks_ac, props = find_peaks(ac[10:], height=0.1, distance=5, prominence=0.05)
        if len(peaks_ac) > 0:
            first_peak_lag = peaks_ac[0] + 10
            symbol_rate_est = SAMPLE_RATE / first_peak_lag
            result["autocorr_symbol_rate_est"] = round(symbol_rate_est, 0)
            result["autocorr_peak_height"] = round(float(ac[first_peak_lag]), 4)

    # Modulation detection (instantaneous frequency variance)
    if n > 100:
        inst_phase = np.unwrap(np.angle(iq))
        inst_freq = np.diff(inst_phase) * SAMPLE_RATE / (2 * np.pi)
        result["inst_freq_std_hz"] = round(float(np.std(inst_freq)), 0)
        result["inst_freq_mean_hz"] = round(float(np.mean(inst_freq)), 0)

    return result


def match_protocols(sig, freq_mhz):
    """Test signal against all known protocols. Return elimination results."""
    eliminations = {}

    for proto_name, proto in KNOWN_PROTOCOLS.items():
        reasons_eliminated = []
        reasons_possible = []

        # Frequency band check
        expected = proto.get("expected_bands_mhz", [])
        not_expected = proto.get("NOT_expected", [])

        in_expected = any(low <= freq_mhz <= high for low, high in expected)
        in_not_expected = any(low <= freq_mhz <= high for low, high in not_expected)

        if expected and not in_expected:
            reasons_eliminated.append(
                f"Frequency {freq_mhz} MHz outside expected band "
                f"{expected}")

        if in_not_expected:
            reasons_eliminated.append(
                f"Frequency {freq_mhz} MHz is in the WRONG direction "
                f"(e.g., uplink not downlink)")

        # Bandwidth check
        expected_bw = proto.get("bandwidth_khz") or proto.get("bandwidth_mhz")
        if expected_bw:
            if isinstance(expected_bw, list):
                bw_vals = [b * 1000 if proto.get("bandwidth_mhz") else b
                          for b in expected_bw]
            else:
                bw_vals = [expected_bw * 1000 if proto.get("bandwidth_mhz") else expected_bw]

            measured_bw = sig.get("occupied_bw_khz", 0)
            if measured_bw > 0:
                match = any(abs(measured_bw - bv / 1000) / (bv / 1000 + 1e-6) < 0.5
                           for bv in bw_vals)
                if not match:
                    reasons_eliminated.append(
                        f"Bandwidth {measured_bw} kHz doesn't match "
                        f"expected {[b/1000 for b in bw_vals]} kHz")

        # Symbol rate check
        expected_sr = proto.get("symbol_rate")
        if expected_sr and sig.get("autocorr_symbol_rate_est"):
            measured_sr = sig["autocorr_symbol_rate_est"]
            if isinstance(expected_sr, list):
                match = any(abs(measured_sr - esr) / (esr + 1e-6) < 0.3
                           for esr in expected_sr)
            else:
                match = abs(measured_sr - expected_sr) / (expected_sr + 1e-6) < 0.3
            if not match:
                reasons_eliminated.append(
                    f"Symbol rate {measured_sr:.0f} doesn't match "
                    f"expected {expected_sr}")

        # Timing checks
        if proto.get("timeslot_duration_us") and sig.get("pulse_width_mean_us"):
            ts = proto["timeslot_duration_us"]
            pw = sig["pulse_width_mean_us"]
            # Pulse width should be comparable to timeslot duration
            if pw < ts * 0.01 or pw > ts * 10:
                reasons_eliminated.append(
                    f"Pulse width {pw:.1f} μs incompatible with "
                    f"timeslot {ts} μs")

        # PRF check for radar
        if proto.get("prf_hz") and sig.get("prf_hz"):
            prf_range = proto["prf_hz"]
            measured_prf = sig["prf_hz"]
            if measured_prf < prf_range[0] or measured_prf > prf_range[1]:
                reasons_eliminated.append(
                    f"PRF {measured_prf:.0f} Hz outside expected "
                    f"range {prf_range}")

        # Kurtosis check — normal digital signals have kurtosis < 20
        if sig.get("kurtosis", 0) > 50:
            reasons_eliminated.append(
                f"Kurtosis {sig['kurtosis']:.0f} far exceeds normal "
                f"digital signal range (<20)")

        # Duty cycle check
        if sig.get("duty_cycle_pct", 0) < 0.1:
            if proto_name not in ["Radar_ATC"]:
                reasons_eliminated.append(
                    f"Duty cycle {sig['duty_cycle_pct']:.3f}% too low "
                    f"for continuous digital protocol")

        status = "ELIMINATED" if reasons_eliminated else "POSSIBLE"
        eliminations[proto_name] = {
            "status": status,
            "reasons_eliminated": reasons_eliminated,
            "reasons_possible": reasons_possible,
        }

    return eliminations


def analyze_file(fpath, verbose=True):
    """Full protocol analysis of one IQ file."""
    freq_mhz = parse_freq_from_filename(fpath)
    if freq_mhz is None:
        # Try to load from sidecar JSON
        jpath = fpath + ".json"
        if os.path.exists(jpath):
            meta = json.load(open(jpath))
            freq_mhz = meta.get("freq_mhz", 0)
        else:
            freq_mhz = 0

    iq = load_iq(fpath)
    if len(iq) < 1000:
        return {"file": os.path.basename(fpath), "error": "too short"}

    sig = analyze_signal(iq, freq_mhz)
    sig["file"] = os.path.basename(fpath)

    # Run protocol matching
    matches = match_protocols(sig, freq_mhz)
    sig["protocol_analysis"] = matches

    n_eliminated = sum(1 for v in matches.values() if v["status"] == "ELIMINATED")
    n_possible = sum(1 for v in matches.values() if v["status"] == "POSSIBLE")
    n_total = len(matches)

    sig["protocols_eliminated"] = n_eliminated
    sig["protocols_possible"] = n_possible
    sig["protocols_total"] = n_total
    sig["verdict"] = "ANOMALOUS" if n_possible == 0 else "UNRESOLVED"

    if verbose:
        verdict_tag = "ANOMALOUS" if n_possible == 0 else f"{n_possible} POSSIBLE"
        print(f"  {sig['file']:45s} {freq_mhz:7.1f} MHz  "
              f"kurt={sig.get('kurtosis', 0):6.0f}  "
              f"pulses={sig.get('pulse_count', 0):5d}  "
              f"bw={sig.get('occupied_bw_khz', 0):6.0f}kHz  "
              f"elim={n_eliminated}/{n_total}  [{verdict_tag}]")

    return sig


def cmd_batch(args):
    """Analyze all IQ files in directory."""
    iq_dir = Path(args.dir)
    iq_files = sorted(iq_dir.glob("*.iq"))
    limit = args.limit if args.limit else len(iq_files)
    iq_files = iq_files[:limit]

    if not iq_files:
        print(f"  [!] No IQ files in {iq_dir}")
        return

    print(f"\n{'=' * 80}")
    print(f"  PROTOCOL ELIMINATION ANALYSIS — {len(iq_files)} files")
    print(f"{'=' * 80}\n")

    all_results = []
    anomalous = 0
    by_freq = Counter()

    for fpath in iq_files:
        result = analyze_file(str(fpath), verbose=True)
        all_results.append(result)
        if result.get("verdict") == "ANOMALOUS":
            anomalous += 1
        freq = result.get("freq_mhz", 0)
        by_freq[f"{freq:.0f} MHz"] += 1

    print(f"\n{'=' * 80}")
    print(f"  SUMMARY")
    print(f"{'=' * 80}")
    print(f"  Files analyzed: {len(all_results)}")
    print(f"  ANOMALOUS (matches NO known protocol): {anomalous}")
    print(f"  Unresolved: {len(all_results) - anomalous}")
    print(f"\n  By frequency:")
    for freq, count in by_freq.most_common():
        anom_at_freq = sum(1 for r in all_results
                          if f"{r.get('freq_mhz', 0):.0f} MHz" == freq
                          and r.get("verdict") == "ANOMALOUS")
        print(f"    {freq:>10s}: {count:4d} files, {anom_at_freq} anomalous")

    # Most common elimination reasons
    reason_counts = Counter()
    for r in all_results:
        for proto, match in r.get("protocol_analysis", {}).items():
            for reason in match.get("reasons_eliminated", []):
                reason_counts[f"{proto}: {reason[:60]}"] += 1

    print(f"\n  Top elimination reasons:")
    for reason, count in reason_counts.most_common(15):
        print(f"    [{count:4d}] {reason}")

    # Save
    out = RESULTS_DIR / "protocol_analysis.json"
    json.dump(all_results, open(out, "w"), indent=2, default=str)
    print(f"\n  Results: {out}")


def cmd_analyze(args):
    """Analyze single file."""
    result = analyze_file(args.file, verbose=True)

    print(f"\n  Signal characteristics:")
    for k, v in result.items():
        if k not in ["protocol_analysis", "file"]:
            print(f"    {k:35s} = {v}")

    print(f"\n  Protocol elimination results:")
    for proto, match in result.get("protocol_analysis", {}).items():
        status = match["status"]
        tag = "X" if status == "ELIMINATED" else "?"
        print(f"    [{tag}] {proto:20s} {status}")
        for reason in match.get("reasons_eliminated", []):
            print(f"        - {reason}")


def main():
    parser = argparse.ArgumentParser(description="Protocol Elimination Analysis")
    sub = parser.add_subparsers(dest="command")

    p_analyze = sub.add_parser("analyze", help="Analyze single IQ file")
    p_analyze.add_argument("file", help="Path to .iq file")

    p_batch = sub.add_parser("batch", help="Batch analyze IQ files")
    p_batch.add_argument("--dir", default="captures", help="Directory with .iq files")
    p_batch.add_argument("--limit", type=int, default=100, help="Max files to analyze")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "batch":
        cmd_batch(args)


if __name__ == "__main__":
    main()

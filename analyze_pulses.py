#!/usr/bin/env python3
"""
Deep pulse timing analysis on sentinel data and saved IQ captures.

Subcommands:
  intervals  — Pulse Repetition Interval analysis per frequency
  widths     — Pulse width distribution histograms
  iq <file>  — Deep IQ analysis of a single raw capture
  crossfreq  — Cross-frequency pulse timing synchronization test
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats as sp_stats
from scipy.signal import find_peaks

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── Constants ────────────────────────────────────────────────────────────────

SAMPLE_RATE = 2_400_000
SETTLE_SAMPLES = 48_000
DC_NOTCH_BINS = 32
MIN_PULSE_SAMPLES = 3

RESULTS_DIR = Path("results")
CAPTURES_DIR = Path("captures")
PLOTS_DIR = RESULTS_DIR / "plots"

TARGET_FREQS_MHZ = [826, 828, 830, 832, 834, 878]

# Known protocol timings (microseconds)
KNOWN_PROTOCOLS = {
    "LTE subframe":        1000.0,
    "LTE slot":             500.0,
    "LTE symbol (normal)":   66.7,
    "LTE symbol (ext)":      83.3,
    "Bluetooth slot":        625.0,
    "WiFi SIFS (2.4G)":      10.0,
    "WiFi DIFS (2.4G)":      50.0,
    "WiFi slot time":         9.0,
    "WiFi beacon (100ms)": 100000.0,
    "GSM timeslot":          577.0,
    "TDMA frame (GSM)":    4615.0,
}

plt.style.use("dark_background")


# ── Data loading ─────────────────────────────────────────────────────────────

def load_sentinel_logs():
    """Load all sentinel JSONL log files.  Returns list of cycle dicts."""
    log_files = sorted(RESULTS_DIR.glob("sentinel_*.jsonl"))
    if not log_files:
        print("  [!] No sentinel log files found in results/")
        return []

    cycles = []
    for lf in log_files:
        with open(lf) as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    cycles.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # skip corrupt lines
    return cycles


def extract_pulses_by_freq(cycles):
    """From sentinel cycles, extract pulse lists keyed by frequency (MHz).

    Returns:
        dict[float, list[list[dict]]]:  freq -> list of per-capture pulse lists.
        Each inner list is the pulses from one stare capture.
    """
    pulses_by_freq = defaultdict(list)

    for cycle in cycles:
        stare = cycle.get("stare", {})
        for freq_str, results in stare.items():
            try:
                freq_mhz = float(freq_str)
            except ValueError:
                continue
            if not isinstance(results, list):
                continue
            for result in results:
                pulse_list = result.get("pulses", [])
                if pulse_list:
                    pulses_by_freq[freq_mhz].append(pulse_list)

    return dict(pulses_by_freq)


def load_iq_file(filepath):
    """Load raw .iq file (uint8 IQ pairs).  Apply settle discard + DC notch.

    Returns complex64 array and metadata dict.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"  [!] File not found: {filepath}")
        sys.exit(1)

    raw = filepath.read_bytes()
    meta = {}

    # Try to load companion .json metadata
    meta_path = filepath.with_suffix(".iq.json")
    if not meta_path.exists():
        meta_path = filepath.with_suffix(".json")
    if meta_path.exists():
        try:
            with open(meta_path) as f:
                meta = json.load(f)
        except json.JSONDecodeError:
            pass

    # Infer freq and timestamp from filename if no metadata
    # Pattern: sentinel_826MHz_014542.iq  or  watch_826MHz_0.iq
    name = filepath.stem
    freq_match = re.search(r"(\d+)MHz", name)
    ts_match = re.search(r"_(\d{6})\.iq$", str(filepath))

    if "freq_mhz" not in meta and freq_match:
        meta["freq_mhz"] = int(freq_match.group(1))
    if "timestamp" not in meta and ts_match:
        raw_ts = ts_match.group(1)
        meta["timestamp"] = f"{raw_ts[:2]}:{raw_ts[2:4]}:{raw_ts[4:6]}"

    meta.setdefault("sample_rate", SAMPLE_RATE)
    sr = meta["sample_rate"]

    # Convert uint8 to complex
    iq_u8 = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
    iq_u8 = (iq_u8 - 127.5) / 127.5
    z = iq_u8[0::2] + 1j * iq_u8[1::2]

    # Discard settle samples
    if len(z) > SETTLE_SAMPLES:
        z = z[SETTLE_SAMPLES:]

    # DC notch
    Z = np.fft.fft(z)
    h = DC_NOTCH_BINS // 2
    Z[:h] = 0
    Z[-h:] = 0
    z = np.fft.ifft(Z)

    return z, meta


def find_pulses_in_iq(iq, sample_rate=SAMPLE_RATE, sigma_thresh=4.0):
    """Detect pulses in complex IQ data.  Returns list of pulse dicts."""
    amp = np.abs(iq)
    mu = float(np.mean(amp))
    sigma = float(np.std(amp))
    thresh = mu + sigma_thresh * sigma

    above = (amp > thresh).astype(np.int8)
    if not np.any(above):
        return []

    diffs = np.diff(np.concatenate(([0], above, [0])))
    starts = np.where(diffs == 1)[0]
    ends = np.where(diffs == -1)[0]

    pulses = []
    for s, e in zip(starts, ends):
        w = e - s
        if w >= MIN_PULSE_SAMPLES:
            pk = float(np.max(amp[s:e]))
            snr = round(20 * np.log10(pk / mu), 1) if mu > 0 else 0
            pulses.append({
                "start_sample": int(s),
                "offset_us": round(s / sample_rate * 1e6, 1),
                "width_us": round(w / sample_rate * 1e6, 2),
                "snr_db": snr,
            })
    return pulses


# ── Subcommand: intervals ────────────────────────────────────────────────────

def cmd_intervals(args):
    """Pulse Repetition Interval analysis."""
    print(f"\n{'='*72}")
    print(f"  PULSE REPETITION INTERVAL ANALYSIS")
    print(f"{'='*72}")

    cycles = load_sentinel_logs()
    if not cycles:
        return
    print(f"  Loaded {len(cycles)} sentinel cycles")

    pulses_by_freq = extract_pulses_by_freq(cycles)
    if not pulses_by_freq:
        print("  [!] No pulse data found in sentinel logs.")
        return

    results = {}

    for freq_mhz in sorted(pulses_by_freq.keys()):
        capture_pulse_lists = pulses_by_freq[freq_mhz]
        all_intervals_us = []

        for pulse_list in capture_pulse_lists:
            offsets = sorted(p["offset_us"] for p in pulse_list)
            if len(offsets) >= 2:
                intervals = np.diff(offsets)
                all_intervals_us.extend(intervals.tolist())

        if not all_intervals_us:
            continue

        intervals_arr = np.array(all_intervals_us)
        n_captures = len(capture_pulse_lists)
        n_intervals = len(intervals_arr)

        print(f"\n  ── {freq_mhz:.0f} MHz ──")
        print(f"  Captures with pulses: {n_captures}")
        print(f"  Total inter-pulse intervals: {n_intervals}")
        print(f"  Range: {intervals_arr.min():.1f} - {intervals_arr.max():.1f} us")
        print(f"  Mean: {intervals_arr.mean():.1f} us  |  Median: {np.median(intervals_arr):.1f} us")
        print(f"  Std:  {intervals_arr.std():.1f} us")

        # Histogram with automatic peak detection
        # Use log-spaced bins for wide dynamic range
        if intervals_arr.min() > 0:
            log_min = np.log10(max(intervals_arr.min(), 0.1))
            log_max = np.log10(intervals_arr.max() + 1)
            n_bins = min(200, max(50, n_intervals // 20))
            bin_edges = np.logspace(log_min, log_max, n_bins + 1)
        else:
            n_bins = min(200, max(50, n_intervals // 20))
            bin_edges = np.linspace(0, intervals_arr.max(), n_bins + 1)

        hist, edges = np.histogram(intervals_arr, bins=bin_edges)
        bin_centers = (edges[:-1] + edges[1:]) / 2

        # Peak detection on histogram
        # Smooth histogram first to avoid noise peaks
        if len(hist) > 10:
            kernel_size = max(3, len(hist) // 20)
            if kernel_size % 2 == 0:
                kernel_size += 1
            kernel = np.ones(kernel_size) / kernel_size
            hist_smooth = np.convolve(hist, kernel, mode="same")
        else:
            hist_smooth = hist.astype(float)

        prominence = max(hist_smooth.max() * 0.05, 3)
        peaks, peak_props = find_peaks(hist_smooth, prominence=prominence,
                                       distance=max(3, len(hist) // 30))

        dominant_pris = []
        if len(peaks) > 0:
            # Sort peaks by prominence (descending)
            peak_order = np.argsort(peak_props["prominences"])[::-1]
            peaks_sorted = peaks[peak_order]

            print(f"\n  Dominant PRIs (peaks in interval histogram):")
            for rank, pi in enumerate(peaks_sorted[:8]):
                pri_us = bin_centers[pi]
                count = hist[pi]
                # Count intervals within 10% of this PRI
                tol = pri_us * 0.1
                nearby = np.sum(np.abs(intervals_arr - pri_us) < tol)
                pct = nearby / n_intervals * 100

                pri_info = {
                    "pri_us": round(float(pri_us), 1),
                    "count_in_bin": int(count),
                    "count_within_10pct": int(nearby),
                    "pct_of_total": round(pct, 1),
                    "prominence": round(float(peak_props["prominences"][peak_order[rank]]), 1),
                }

                dominant_pris.append(pri_info)

                print(f"    PRI ~{pri_us:.1f} us ({pri_us/1000:.3f} ms)"
                      f"  |  {nearby} intervals ({pct:.1f}%)"
                      f"  |  prominence={pri_info['prominence']:.0f}")

                # Check harmonics
                harmonics_found = []
                for h_mult in [2, 3, 4, 5]:
                    harmonic = pri_us * h_mult
                    h_tol = harmonic * 0.1
                    h_count = np.sum(np.abs(intervals_arr - harmonic) < h_tol)
                    if h_count > n_intervals * 0.01:
                        harmonics_found.append(
                            f"{h_mult}x={harmonic:.0f}us ({h_count})")
                if harmonics_found:
                    print(f"      Harmonics: {', '.join(harmonics_found)}")

                # Check subharmonics (the PRI could be a multiple of a shorter interval)
                for sub in [2, 3, 4]:
                    sub_pri = pri_us / sub
                    s_tol = sub_pri * 0.1
                    s_count = np.sum(np.abs(intervals_arr - sub_pri) < s_tol)
                    if s_count > n_intervals * 0.01:
                        print(f"      Subharmonic: 1/{sub}x = {sub_pri:.1f}us ({s_count} hits)")

        # Check against known protocol timings
        print(f"\n  Protocol timing comparison:")
        protocol_matches = []
        for proto_name, proto_us in sorted(KNOWN_PROTOCOLS.items(),
                                           key=lambda x: x[1]):
            tol = proto_us * 0.05  # 5% tolerance
            match_count = int(np.sum(np.abs(intervals_arr - proto_us) < tol))
            if match_count > 0:
                pct = match_count / n_intervals * 100
                marker = "***" if pct > 2.0 else "   "
                print(f"    {marker} {proto_name:25s}  {proto_us:10.1f} us"
                      f"  |  {match_count:5d} matches ({pct:.1f}%)")
                if pct > 0.5:
                    protocol_matches.append({
                        "protocol": proto_name,
                        "timing_us": proto_us,
                        "matches": match_count,
                        "pct": round(pct, 2),
                    })

        if not protocol_matches:
            print("    (no significant matches to known protocol timings)")

        # Store results
        results[str(int(freq_mhz))] = {
            "freq_mhz": freq_mhz,
            "n_captures": n_captures,
            "n_intervals": n_intervals,
            "min_us": round(float(intervals_arr.min()), 1),
            "max_us": round(float(intervals_arr.max()), 1),
            "mean_us": round(float(intervals_arr.mean()), 1),
            "median_us": round(float(np.median(intervals_arr)), 1),
            "std_us": round(float(intervals_arr.std()), 1),
            "dominant_pris": dominant_pris,
            "protocol_matches": protocol_matches,
        }

    # Save results
    out_path = RESULTS_DIR / "pulse_intervals.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {out_path}")

    # Plot
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    _plot_intervals(pulses_by_freq, results)


def _plot_intervals(pulses_by_freq, results):
    """Generate interval histogram plots."""
    freqs = sorted(pulses_by_freq.keys())
    n_freqs = len(freqs)
    if n_freqs == 0:
        return

    fig, axes = plt.subplots(n_freqs, 1, figsize=(14, 4 * n_freqs))
    if n_freqs == 1:
        axes = [axes]

    fig.suptitle("Pulse Repetition Intervals by Frequency",
                 fontsize=16, fontweight="bold", y=0.995)

    for ax, freq_mhz in zip(axes, freqs):
        capture_pulse_lists = pulses_by_freq[freq_mhz]
        all_intervals = []
        for pulse_list in capture_pulse_lists:
            offsets = sorted(p["offset_us"] for p in pulse_list)
            if len(offsets) >= 2:
                all_intervals.extend(np.diff(offsets).tolist())

        if not all_intervals:
            ax.text(0.5, 0.5, "No interval data", transform=ax.transAxes,
                    ha="center", va="center", fontsize=14, color="#ff6666")
            ax.set_title(f"{freq_mhz:.0f} MHz", fontsize=13)
            continue

        intervals_arr = np.array(all_intervals)

        # Log-scale histogram
        if intervals_arr.min() > 0:
            log_min = np.log10(max(intervals_arr.min(), 0.1))
            log_max = np.log10(intervals_arr.max() + 1)
            bins = np.logspace(log_min, log_max, 150)
        else:
            bins = np.linspace(0, intervals_arr.max(), 150)

        ax.hist(intervals_arr, bins=bins, color="#00ccff", alpha=0.8,
                edgecolor="none")
        ax.set_xscale("log")
        ax.set_xlabel("Inter-pulse interval (us)", fontsize=10)
        ax.set_ylabel("Count", fontsize=10)
        ax.set_title(f"{freq_mhz:.0f} MHz  —  {len(all_intervals)} intervals "
                     f"from {len(capture_pulse_lists)} captures",
                     fontsize=13)

        # Mark known protocol timings
        colors = {"LTE": "#ff4444", "Bluetooth": "#44ff44",
                  "WiFi": "#ffaa00", "GSM": "#ff44ff", "TDMA": "#ff44ff"}
        ymax = ax.get_ylim()[1]
        for proto_name, proto_us in KNOWN_PROTOCOLS.items():
            if bins[0] < proto_us < bins[-1]:
                color = "#888888"
                for prefix, c in colors.items():
                    if prefix in proto_name:
                        color = c
                        break
                ax.axvline(proto_us, color=color, alpha=0.5, linestyle="--",
                           linewidth=0.8)
                ax.text(proto_us, ymax * 0.92, proto_name, fontsize=6,
                        rotation=90, va="top", ha="right", color=color,
                        alpha=0.7)

        # Mark dominant PRIs
        freq_key = str(int(freq_mhz))
        if freq_key in results:
            for pri_info in results[freq_key].get("dominant_pris", [])[:5]:
                pri_us = pri_info["pri_us"]
                ax.axvline(pri_us, color="#ff6600", alpha=0.9, linewidth=1.5,
                           linestyle="-")
                ax.text(pri_us, ymax * 0.75,
                        f"  {pri_us:.0f}us ({pri_info['pct_of_total']:.0f}%)",
                        fontsize=7, color="#ff6600", va="top")

        ax.grid(True, alpha=0.2, which="both")

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out = PLOTS_DIR / "pulse_intervals.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Plot saved to {out}")


# ── Subcommand: widths ───────────────────────────────────────────────────────

def cmd_widths(args):
    """Pulse width distribution analysis."""
    print(f"\n{'='*72}")
    print(f"  PULSE WIDTH DISTRIBUTION ANALYSIS")
    print(f"{'='*72}")

    cycles = load_sentinel_logs()
    if not cycles:
        return
    print(f"  Loaded {len(cycles)} sentinel cycles")

    pulses_by_freq = extract_pulses_by_freq(cycles)
    if not pulses_by_freq:
        print("  [!] No pulse data found in sentinel logs.")
        return

    freqs = sorted(pulses_by_freq.keys())
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    n_freqs = len(freqs)
    fig, axes = plt.subplots(n_freqs, 2, figsize=(16, 3.5 * n_freqs))
    if n_freqs == 1:
        axes = axes.reshape(1, -1)

    fig.suptitle("Pulse Width Distributions", fontsize=16,
                 fontweight="bold", y=0.995)

    for row, freq_mhz in enumerate(freqs):
        capture_pulse_lists = pulses_by_freq[freq_mhz]
        all_widths = []
        for pulse_list in capture_pulse_lists:
            for p in pulse_list:
                w = p.get("width_us", 0)
                if w > 0:
                    all_widths.append(w)

        if not all_widths:
            for c in range(2):
                axes[row, c].text(0.5, 0.5, "No width data",
                                  transform=axes[row, c].transAxes,
                                  ha="center", va="center", fontsize=14,
                                  color="#ff6666")
                axes[row, c].set_title(f"{freq_mhz:.0f} MHz", fontsize=12)
            continue

        widths = np.array(all_widths)
        n = len(widths)

        # Statistics
        mean_w = float(np.mean(widths))
        median_w = float(np.median(widths))
        std_w = float(np.std(widths))
        # Mode via histogram
        hist_mode, edges_mode = np.histogram(widths, bins=min(100, max(20, n // 10)))
        mode_bin = np.argmax(hist_mode)
        mode_w = float((edges_mode[mode_bin] + edges_mode[mode_bin + 1]) / 2)

        # Cluster analysis: look for distinct clusters in width values
        # Use kernel density estimation
        sorted_w = np.sort(widths)
        unique_widths = np.unique(np.round(widths, 2))

        # Check clustering: if widths cluster around specific values,
        # the ratio of unique values to total is low, or std is small
        # relative to range
        width_range = widths.max() - widths.min()
        clustering_score = std_w / (width_range + 1e-6)
        is_clustered = (clustering_score < 0.3 or
                        len(unique_widths) < max(10, n * 0.1))

        print(f"\n  ── {freq_mhz:.0f} MHz ──")
        print(f"  Total pulse widths: {n} from {len(capture_pulse_lists)} captures")
        print(f"  Mean:   {mean_w:.2f} us")
        print(f"  Median: {median_w:.2f} us")
        print(f"  Mode:   ~{mode_w:.2f} us")
        print(f"  Std:    {std_w:.2f} us")
        print(f"  Range:  {widths.min():.2f} - {widths.max():.2f} us")
        print(f"  Unique values (0.01us res): {len(unique_widths)}")
        if is_clustered:
            print(f"  ** CLUSTERED ** — widths concentrate around specific values")
            print(f"     (clustering score={clustering_score:.3f},"
                  f" suggesting a CONTROLLED source)")
        else:
            print(f"     Widths are spread (clustering score={clustering_score:.3f},"
                  f" could be noise-like)")

        # Identify cluster centers via histogram peaks
        n_bins_cluster = min(80, max(20, n // 5))
        hist_c, edges_c = np.histogram(widths, bins=n_bins_cluster)
        centers_c = (edges_c[:-1] + edges_c[1:]) / 2

        if len(hist_c) > 5:
            kernel_c = max(3, len(hist_c) // 15)
            if kernel_c % 2 == 0:
                kernel_c += 1
            smooth = np.convolve(hist_c, np.ones(kernel_c) / kernel_c,
                                 mode="same")
            prom = max(smooth.max() * 0.08, 2)
            cluster_peaks, cp_props = find_peaks(smooth, prominence=prom,
                                                 distance=3)
            if len(cluster_peaks) > 0:
                peak_order = np.argsort(cp_props["prominences"])[::-1]
                print(f"  Width clusters:")
                for ci in peak_order[:6]:
                    cw = centers_c[cluster_peaks[ci]]
                    tol = (edges_c[1] - edges_c[0]) * 1.5
                    cnt = int(np.sum(np.abs(widths - cw) < tol))
                    print(f"    ~{cw:.2f} us  ({cnt} pulses,"
                          f" {cnt/n*100:.1f}%)")

        # Left plot: histogram
        ax_hist = axes[row, 0]
        ax_hist.hist(widths, bins=min(100, max(20, n // 10)),
                     color="#00ccff", alpha=0.85, edgecolor="none")
        ax_hist.axvline(mean_w, color="#ff4444", linestyle="--", linewidth=1.2,
                        label=f"Mean={mean_w:.2f}us")
        ax_hist.axvline(median_w, color="#44ff44", linestyle="--", linewidth=1.2,
                        label=f"Median={median_w:.2f}us")
        ax_hist.set_xlabel("Pulse width (us)", fontsize=10)
        ax_hist.set_ylabel("Count", fontsize=10)
        ax_hist.set_title(
            f"{freq_mhz:.0f} MHz  —  {n} pulses"
            + (" [CLUSTERED]" if is_clustered else ""),
            fontsize=12, color="#ff8800" if is_clustered else "white")
        ax_hist.legend(fontsize=8)
        ax_hist.grid(True, alpha=0.2)

        # Right plot: width vs occurrence (sorted, like a CDF)
        ax_cdf = axes[row, 1]
        sorted_widths = np.sort(widths)
        cdf = np.arange(1, n + 1) / n
        ax_cdf.plot(sorted_widths, cdf, color="#00ff88", linewidth=1.2)
        ax_cdf.axhline(0.5, color="#888888", linestyle=":", linewidth=0.8)
        ax_cdf.axvline(median_w, color="#44ff44", linestyle="--",
                       linewidth=0.8, alpha=0.7)
        ax_cdf.set_xlabel("Pulse width (us)", fontsize=10)
        ax_cdf.set_ylabel("Cumulative fraction", fontsize=10)
        ax_cdf.set_title(f"{freq_mhz:.0f} MHz — CDF  (std={std_w:.2f}us)",
                         fontsize=12)
        ax_cdf.grid(True, alpha=0.2)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out = PLOTS_DIR / "pulse_widths.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Plot saved to {out}")


# ── Subcommand: iq ───────────────────────────────────────────────────────────

def cmd_iq(args):
    """Deep IQ analysis of a single raw capture."""
    filepath = Path(args.filepath)

    print(f"\n{'='*72}")
    print(f"  DEEP IQ ANALYSIS")
    print(f"  File: {filepath}")
    print(f"{'='*72}")

    z, meta = load_iq_file(filepath)
    sr = meta.get("sample_rate", SAMPLE_RATE)
    freq_mhz = meta.get("freq_mhz", "unknown")
    timestamp = meta.get("timestamp", "unknown")

    n_samples = len(z)
    duration_us = n_samples / sr * 1e6
    duration_ms = duration_us / 1000

    print(f"  Frequency: {freq_mhz} MHz")
    print(f"  Timestamp: {timestamp}")
    print(f"  Samples:   {n_samples:,}")
    print(f"  Duration:  {duration_ms:.1f} ms ({duration_us:.0f} us)")
    print(f"  Sample rate: {sr/1e6:.1f} MSPS")

    amp = np.abs(z).astype(np.float64)
    mu = float(np.mean(amp))
    sigma = float(np.std(amp))
    kurt = float(sp_stats.kurtosis(amp, fisher=False))

    print(f"  Kurtosis:  {kurt:.2f}")
    print(f"  Mean amp:  {mu:.6f}")
    print(f"  Std amp:   {sigma:.6f}")

    # Detect pulses
    pulses = find_pulses_in_iq(z, sr)
    print(f"  Pulses detected: {len(pulses)}")
    for p in pulses[:10]:
        print(f"    @ {p['offset_us']:.1f} us  width={p['width_us']:.2f} us"
              f"  snr={p['snr_db']:.1f} dB")
    if len(pulses) > 10:
        print(f"    ... and {len(pulses) - 10} more")

    # ── Plotting ──
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    time_us = np.arange(n_samples) / sr * 1e6
    thresh = mu + 4 * sigma

    freq_label = f"{freq_mhz}" if freq_mhz != "unknown" else "unk"
    ts_label = str(timestamp).replace(":", "")
    out_name = f"iq_analysis_{freq_label}_{ts_label}.png"

    fig = plt.figure(figsize=(18, 20))
    gs = fig.add_gridspec(4, 2, hspace=0.35, wspace=0.3)

    fig.suptitle(
        f"IQ Analysis  —  {freq_mhz} MHz  @  {timestamp}\n"
        f"Kurtosis={kurt:.1f}  |  {len(pulses)} pulses  |  "
        f"{duration_ms:.1f} ms capture",
        fontsize=15, fontweight="bold", y=0.98)

    # ── 1. Full time-domain amplitude ──
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(time_us, amp, color="#00ccff", linewidth=0.3, alpha=0.8)
    ax1.axhline(thresh, color="#ff4444", linestyle="--", linewidth=0.8,
                alpha=0.7, label=f"Threshold (mu+4sigma={thresh:.4f})")
    ax1.axhline(mu, color="#44ff44", linestyle=":", linewidth=0.6,
                alpha=0.5, label=f"Mean={mu:.4f}")

    # Mark pulses
    for p in pulses[:50]:
        ax1.axvspan(p["offset_us"],
                    p["offset_us"] + p["width_us"],
                    color="#ff4444", alpha=0.3)

    ax1.set_xlabel("Time (us)", fontsize=10)
    ax1.set_ylabel("Amplitude", fontsize=10)
    ax1.set_title("Full Capture — Time Domain Amplitude", fontsize=12)
    ax1.legend(fontsize=8, loc="upper right")
    ax1.grid(True, alpha=0.15)

    # ── 2. Zoomed to first pulse region ──
    ax2 = fig.add_subplot(gs[1, :])
    if pulses:
        # Zoom around the first pulse cluster
        first_offset = pulses[0]["offset_us"]
        zoom_start = max(0, first_offset - 50)
        zoom_end = min(time_us[-1], first_offset + 200)

        # If multiple pulses are close, extend window
        for p in pulses[:20]:
            if p["offset_us"] < first_offset + 500:
                zoom_end = max(zoom_end, p["offset_us"] + p["width_us"] + 50)
        zoom_end = min(zoom_end, first_offset + 1000)

        mask = (time_us >= zoom_start) & (time_us <= zoom_end)
        if np.any(mask):
            ax2.plot(time_us[mask], amp[mask], color="#00ccff",
                     linewidth=0.5, alpha=0.9)
            ax2.axhline(thresh, color="#ff4444", linestyle="--",
                        linewidth=0.8, alpha=0.7)
            ax2.axhline(mu, color="#44ff44", linestyle=":",
                        linewidth=0.6, alpha=0.5)
            for p in pulses:
                if zoom_start <= p["offset_us"] <= zoom_end:
                    ax2.axvspan(p["offset_us"],
                                p["offset_us"] + p["width_us"],
                                color="#ff4444", alpha=0.4)
                    ax2.text(p["offset_us"], thresh * 1.05,
                             f"{p['width_us']:.1f}us",
                             fontsize=6, color="#ffaa00", rotation=45)
    else:
        # Just zoom to first 10% of capture
        n_show = min(n_samples, n_samples // 10)
        ax2.plot(time_us[:n_show], amp[:n_show], color="#00ccff",
                 linewidth=0.5, alpha=0.9)
        ax2.axhline(thresh, color="#ff4444", linestyle="--", linewidth=0.8,
                     alpha=0.7)
        ax2.axhline(mu, color="#44ff44", linestyle=":", linewidth=0.6,
                     alpha=0.5)

    ax2.set_xlabel("Time (us)", fontsize=10)
    ax2.set_ylabel("Amplitude", fontsize=10)
    ax2.set_title("Zoomed — Pulse Region Detail", fontsize=12)
    ax2.grid(True, alpha=0.15)

    # ── 3. Spectrogram ──
    ax3 = fig.add_subplot(gs[2, :])
    nperseg = min(256, n_samples // 8)
    if nperseg < 16:
        nperseg = 16
    noverlap = nperseg * 3 // 4

    # Use real part for spectrogram
    ax3.specgram(z.real.astype(np.float64), NFFT=nperseg, Fs=sr / 1e6,
                 noverlap=noverlap, cmap="inferno",
                 scale="dB", mode="magnitude")
    ax3.set_xlabel("Time (s)", fontsize=10)
    ax3.set_ylabel("Frequency (MHz offset)", fontsize=10)
    ax3.set_title(f"Spectrogram  (NFFT={nperseg}, {sr/1e6:.1f} MSPS)",
                  fontsize=12)

    # Mark pulse times on spectrogram
    t_max_s = n_samples / sr
    for p in pulses[:30]:
        t_s = p["offset_us"] / 1e6
        if 0 <= t_s <= t_max_s:
            ax3.axvline(t_s, color="#00ff00", alpha=0.3, linewidth=0.5)

    # ── 4a. Amplitude Probability Distribution (APD) — Rayleigh paper ──
    ax4 = fig.add_subplot(gs[3, 0])

    # APD = complementary CDF = P(amplitude > x)
    sorted_amp = np.sort(amp)
    ccdf = 1.0 - np.arange(1, len(sorted_amp) + 1) / len(sorted_amp)

    # Rayleigh paper: y-axis = -ln(ccdf) should be linear for Rayleigh
    # On Rayleigh paper, plot amplitude (dB relative to RMS) vs Rayleigh scale
    rms = np.sqrt(np.mean(amp ** 2))
    amp_db = 20 * np.log10(sorted_amp / rms + 1e-30)

    # Plot APD as CCDF on log scale
    valid = ccdf > 0
    ax4.semilogy(amp_db[valid], ccdf[valid], color="#00ccff", linewidth=1.0,
                 alpha=0.9, label="Measured")

    # Overlay theoretical Rayleigh CCDF for reference
    # For Rayleigh: CCDF(x) = exp(-x^2 / (2*sigma^2))
    # where sigma^2 = mean(amp^2)/2 = rms^2/2
    rayleigh_sigma = rms / np.sqrt(2)
    x_theory = np.linspace(sorted_amp.min(), sorted_amp.max(), 500)
    x_theory_db = 20 * np.log10(x_theory / rms + 1e-30)
    ccdf_rayleigh = np.exp(-x_theory ** 2 / (2 * rayleigh_sigma ** 2))
    ax4.semilogy(x_theory_db, ccdf_rayleigh, color="#ff4444", linewidth=1.0,
                 linestyle="--", alpha=0.7, label="Rayleigh (theory)")

    ax4.set_xlabel("Amplitude (dB re RMS)", fontsize=10)
    ax4.set_ylabel("P(amp > x)  [CCDF]", fontsize=10)
    ax4.set_title("Amplitude Probability Distribution", fontsize=12)
    ax4.legend(fontsize=8)
    ax4.grid(True, alpha=0.2, which="both")
    ax4.set_ylim(bottom=max(1e-6, 1.0 / len(amp)))

    # ── 4b. Power spectral density ──
    ax5 = fig.add_subplot(gs[3, 1])
    from scipy.signal import welch
    nperseg_psd = min(1024, n_samples // 4)
    f_psd, psd = welch(z, fs=sr, nperseg=nperseg_psd, return_onesided=False)

    # Sort by frequency for clean plotting
    order = np.argsort(f_psd)
    f_psd = f_psd[order] / 1e6  # to MHz offset
    psd = psd[order]
    psd_db = 10 * np.log10(psd + 1e-30)

    ax5.plot(f_psd, psd_db, color="#00ff88", linewidth=0.6, alpha=0.9)
    ax5.set_xlabel("Frequency offset (MHz)", fontsize=10)
    ax5.set_ylabel("PSD (dB/Hz)", fontsize=10)
    ax5.set_title("Power Spectral Density", fontsize=12)
    ax5.grid(True, alpha=0.2)

    fig.savefig(PLOTS_DIR / out_name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Plot saved to {PLOTS_DIR / out_name}")


# ── Subcommand: crossfreq ────────────────────────────────────────────────────

def cmd_crossfreq(args):
    """Cross-frequency pulse timing synchronization analysis."""
    print(f"\n{'='*72}")
    print(f"  CROSS-FREQUENCY PULSE TIMING ANALYSIS")
    print(f"{'='*72}")

    cycles = load_sentinel_logs()
    if not cycles:
        return
    print(f"  Loaded {len(cycles)} sentinel cycles")

    # For each cycle, gather pulse offsets by frequency
    # We want cycles where multiple target freqs have pulses
    uplink_freqs = {826, 828, 830, 832, 834}
    all_target_freqs = {826, 828, 830, 832, 834, 878}

    # Per-cycle data:  cycle_index -> { freq_mhz -> [offset_us, ...] }
    per_cycle_offsets = []

    for ci, cycle in enumerate(cycles):
        stare = cycle.get("stare", {})
        cycle_data = {}
        for freq_str, results in stare.items():
            try:
                freq_mhz = float(freq_str)
            except ValueError:
                continue
            freq_int = int(round(freq_mhz))
            if freq_int not in all_target_freqs:
                continue
            if not isinstance(results, list):
                continue

            offsets = []
            for result in results:
                for p in result.get("pulses", []):
                    offsets.append(p["offset_us"])
            if offsets:
                cycle_data[freq_int] = sorted(offsets)

        if len(cycle_data) >= 2:
            per_cycle_offsets.append(cycle_data)

    print(f"  Cycles with pulses on 2+ target freqs: {len(per_cycle_offsets)}")

    if not per_cycle_offsets:
        print("  [!] Not enough cross-frequency data for analysis.")
        return

    # ── Analysis 1: Co-occurrence matrix ──
    # For each pair of frequencies, count how often they both have pulses in
    # the same cycle
    from itertools import combinations

    freq_list = sorted(all_target_freqs)
    cooccurrence = np.zeros((len(freq_list), len(freq_list)), dtype=int)
    freq_idx = {f: i for i, f in enumerate(freq_list)}
    freq_cycle_counts = defaultdict(int)

    for cycle_data in per_cycle_offsets:
        active_freqs = list(cycle_data.keys())
        for f in active_freqs:
            freq_cycle_counts[f] += 1
        for fa, fb in combinations(active_freqs, 2):
            if fa in freq_idx and fb in freq_idx:
                cooccurrence[freq_idx[fa], freq_idx[fb]] += 1
                cooccurrence[freq_idx[fb], freq_idx[fa]] += 1

    # Fill diagonal with self-counts
    for f, cnt in freq_cycle_counts.items():
        if f in freq_idx:
            cooccurrence[freq_idx[f], freq_idx[f]] = cnt

    print(f"\n  Co-occurrence matrix (cycles with pulses on both freqs):")
    header = "         " + "".join(f"{f:>8d}" for f in freq_list)
    print(header)
    for i, fi in enumerate(freq_list):
        row_str = f"  {fi:>5d}  "
        for j in range(len(freq_list)):
            row_str += f"{cooccurrence[i, j]:>8d}"
        print(row_str)

    # ── Analysis 2: Pulse offset alignment ──
    # For each pair of frequencies in the same cycle, compare pulse offsets.
    # If they fire at similar offsets, they may be synchronized.
    print(f"\n  Pulse offset alignment analysis:")
    print(f"  (comparing pulse offsets within same capture window)")

    alignment_tolerances_us = [5, 10, 25, 50, 100]

    pair_stats = {}
    for fa, fb in combinations(sorted(uplink_freqs), 2):
        aligned_counts = {t: 0 for t in alignment_tolerances_us}
        total_comparisons = 0
        delta_offsets = []

        for cycle_data in per_cycle_offsets:
            if fa not in cycle_data or fb not in cycle_data:
                continue
            offsets_a = np.array(cycle_data[fa])
            offsets_b = np.array(cycle_data[fb])

            # For each pulse on freq A, find nearest pulse on freq B
            for oa in offsets_a:
                if len(offsets_b) == 0:
                    continue
                nearest_idx = np.argmin(np.abs(offsets_b - oa))
                delta = abs(offsets_b[nearest_idx] - oa)
                delta_offsets.append(float(delta))
                total_comparisons += 1

                for tol in alignment_tolerances_us:
                    if delta <= tol:
                        aligned_counts[tol] += 1

        if total_comparisons > 0:
            delta_arr = np.array(delta_offsets)
            print(f"\n  {fa} MHz vs {fb} MHz:")
            print(f"    Total pulse pairs compared: {total_comparisons}")
            print(f"    Mean nearest-neighbor offset delta: "
                  f"{delta_arr.mean():.1f} us")
            print(f"    Median: {np.median(delta_arr):.1f} us")
            print(f"    Alignment within tolerance:")
            for tol in alignment_tolerances_us:
                cnt = aligned_counts[tol]
                pct = cnt / total_comparisons * 100
                bar = "#" * int(pct / 2)
                print(f"      +/-{tol:>4d} us: {cnt:5d} / {total_comparisons}"
                      f"  ({pct:5.1f}%)  {bar}")

            pair_stats[(fa, fb)] = {
                "n_comparisons": total_comparisons,
                "mean_delta_us": round(float(delta_arr.mean()), 1),
                "median_delta_us": round(float(np.median(delta_arr)), 1),
                "alignment": {
                    str(t): round(aligned_counts[t] / total_comparisons * 100, 1)
                    for t in alignment_tolerances_us
                },
            }

    # ── Analysis 3: Statistical test for synchronization ──
    # Null hypothesis: pulse offsets on different frequencies are independent
    # (uniformly distributed within capture window).
    # Test: if pulses are synchronized, the distribution of nearest-neighbor
    # deltas will be concentrated near zero compared to random expectation.

    print(f"\n\n  ── Synchronization Tests ──")

    # Determine typical capture window duration from pulse offsets
    all_max_offsets = []
    for cycle_data in per_cycle_offsets:
        for freq, offsets in cycle_data.items():
            if offsets:
                all_max_offsets.append(max(offsets))

    if all_max_offsets:
        window_us = float(np.median(all_max_offsets)) * 1.2
    else:
        window_us = 200000.0  # 200ms default

    print(f"  Estimated capture window: ~{window_us:.0f} us ({window_us/1000:.1f} ms)")

    for (fa, fb), stats in pair_stats.items():
        n_comp = stats["n_comparisons"]
        observed_mean = stats["mean_delta_us"]

        # Monte Carlo: expected mean nearest-neighbor delta if offsets are
        # independent uniform [0, window_us]
        n_mc = 2000
        mc_means = []
        # Estimate typical pulse count per capture
        a_counts = []
        b_counts = []
        for cycle_data in per_cycle_offsets:
            if fa in cycle_data:
                a_counts.append(len(cycle_data[fa]))
            if fb in cycle_data:
                b_counts.append(len(cycle_data[fb]))

        na_typ = int(np.median(a_counts)) if a_counts else 5
        nb_typ = int(np.median(b_counts)) if b_counts else 5
        na_typ = max(na_typ, 2)
        nb_typ = max(nb_typ, 2)

        rng = np.random.default_rng(42)
        for _ in range(n_mc):
            sim_a = rng.uniform(0, window_us, na_typ)
            sim_b = rng.uniform(0, window_us, nb_typ)
            deltas = []
            for oa in sim_a:
                d = float(np.min(np.abs(sim_b - oa)))
                deltas.append(d)
            mc_means.append(np.mean(deltas))

        mc_arr = np.array(mc_means)
        mc_mean = float(mc_arr.mean())
        mc_std = float(mc_arr.std())

        # Z-score: how many sigma below the random expectation?
        if mc_std > 0:
            z_score = (mc_mean - observed_mean) / mc_std
        else:
            z_score = 0

        # p-value: fraction of MC samples with mean delta <= observed
        p_value = float(np.mean(mc_arr <= observed_mean))

        print(f"\n  {fa} MHz vs {fb} MHz:")
        print(f"    Observed mean delta:    {observed_mean:.1f} us")
        print(f"    Expected (random):      {mc_mean:.1f} +/- {mc_std:.1f} us")
        print(f"    Z-score:                {z_score:.1f} "
              f"({'closer than random' if z_score > 0 else 'farther than random'})")
        print(f"    p-value (MC):           {p_value:.4f}")

        if z_score > 3:
            print(f"    >>> STRONG SYNCHRONIZATION (z={z_score:.1f}, p={p_value:.4f})")
        elif z_score > 2:
            print(f"    >>> MODERATE SYNCHRONIZATION (z={z_score:.1f}, p={p_value:.4f})")
        elif z_score > 1.5:
            print(f"    >>  WEAK EVIDENCE of synchronization")
        else:
            print(f"        Consistent with independent timing")

    # ── Analysis 4: Combined uplink synchronization ──
    # Across all uplink freqs, check if pulses tend to cluster at similar
    # offsets within each cycle
    print(f"\n\n  ── Combined Uplink Synchronization ──")
    print(f"  Testing if pulses across 826/828/830/832/834 fire in unison\n")

    # For each cycle with 3+ uplink freqs active, compute the spread of
    # the earliest pulse offset across frequencies
    first_pulse_spreads = []
    median_offset_spreads = []
    n_multi_freq_cycles = 0

    for cycle_data in per_cycle_offsets:
        uplink_active = {f: offs for f, offs in cycle_data.items()
                         if f in uplink_freqs}
        if len(uplink_active) < 3:
            continue
        n_multi_freq_cycles += 1

        # Spread of first-pulse offsets across frequencies
        first_offsets = [offs[0] for offs in uplink_active.values()]
        spread = max(first_offsets) - min(first_offsets)
        first_pulse_spreads.append(spread)

        # Spread of median offsets
        med_offsets = [float(np.median(offs)) for offs in uplink_active.values()]
        median_offset_spreads.append(max(med_offsets) - min(med_offsets))

    if first_pulse_spreads:
        spreads = np.array(first_pulse_spreads)
        med_spreads = np.array(median_offset_spreads)

        print(f"  Cycles with 3+ uplink freqs active: {n_multi_freq_cycles}")
        print(f"\n  First-pulse offset spread across frequencies:")
        print(f"    Mean:   {spreads.mean():.1f} us")
        print(f"    Median: {np.median(spreads):.1f} us")
        print(f"    Std:    {spreads.std():.1f} us")
        print(f"    Min:    {spreads.min():.1f} us  |  Max: {spreads.max():.1f} us")

        # Compare to random expectation
        # If N freqs have pulses uniformly in [0, W], the spread of the first
        # pulse is related to order statistics.  We use MC again.
        n_mc_combined = 2000
        rng2 = np.random.default_rng(123)
        typical_n_freqs = min(5, n_multi_freq_cycles)
        mc_spreads = []
        typical_counts_per_freq = []
        for cycle_data in per_cycle_offsets:
            uplink_active = {f: offs for f, offs in cycle_data.items()
                             if f in uplink_freqs}
            if len(uplink_active) >= 3:
                for offs in uplink_active.values():
                    typical_counts_per_freq.append(len(offs))

        n_per_freq = int(np.median(typical_counts_per_freq)) if typical_counts_per_freq else 5
        n_per_freq = max(n_per_freq, 2)

        for _ in range(n_mc_combined):
            firsts = []
            for _ in range(typical_n_freqs):
                sim_offs = rng2.uniform(0, window_us, n_per_freq)
                firsts.append(sim_offs.min())
            mc_spreads.append(max(firsts) - min(firsts))

        mc_sp = np.array(mc_spreads)
        mc_sp_mean = float(mc_sp.mean())
        mc_sp_std = float(mc_sp.std())
        obs_sp_mean = float(spreads.mean())

        z_combined = (mc_sp_mean - obs_sp_mean) / mc_sp_std if mc_sp_std > 0 else 0
        p_combined = float(np.mean(mc_sp <= obs_sp_mean))

        print(f"\n  Comparison to independent model:")
        print(f"    Observed mean spread:   {obs_sp_mean:.1f} us")
        print(f"    Expected (random):      {mc_sp_mean:.1f} +/- {mc_sp_std:.1f} us")
        print(f"    Z-score:                {z_combined:.1f}")
        print(f"    p-value (MC):           {p_combined:.4f}")

        if z_combined > 3:
            print(f"\n    >>> STRONG EVIDENCE: Uplink pulses are SYNCHRONIZED")
            print(f"        across multiple channels — likely same source.")
        elif z_combined > 2:
            print(f"\n    >>> MODERATE EVIDENCE of cross-frequency synchronization.")
        elif z_combined > 1.5:
            print(f"\n    >>  WEAK EVIDENCE — possible synchronization, more data needed.")
        else:
            print(f"\n        No significant synchronization detected.")
    else:
        print(f"  Not enough cycles with 3+ uplink frequencies active.")

    # ── Plot ──
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    _plot_crossfreq(per_cycle_offsets, uplink_freqs, freq_list, cooccurrence,
                    pair_stats, first_pulse_spreads, window_us)


def _plot_crossfreq(per_cycle_offsets, uplink_freqs, freq_list, cooccurrence,
                    pair_stats, first_pulse_spreads, window_us):
    """Generate cross-frequency timing plots."""
    fig = plt.figure(figsize=(18, 16))
    gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.3)

    fig.suptitle("Cross-Frequency Pulse Timing Analysis",
                 fontsize=16, fontweight="bold", y=0.98)

    # ── 1. Co-occurrence heatmap ──
    ax1 = fig.add_subplot(gs[0, 0])
    n_f = len(freq_list)
    if n_f > 0 and cooccurrence.max() > 0:
        im = ax1.imshow(cooccurrence, cmap="inferno", aspect="auto")
        ax1.set_xticks(range(n_f))
        ax1.set_xticklabels([f"{f}" for f in freq_list], fontsize=8)
        ax1.set_yticks(range(n_f))
        ax1.set_yticklabels([f"{f}" for f in freq_list], fontsize=8)
        ax1.set_xlabel("Frequency (MHz)", fontsize=10)
        ax1.set_ylabel("Frequency (MHz)", fontsize=10)
        ax1.set_title("Pulse Co-occurrence (cycles)", fontsize=12)
        for i in range(n_f):
            for j in range(n_f):
                val = cooccurrence[i, j]
                if val > 0:
                    ax1.text(j, i, str(val), ha="center", va="center",
                             fontsize=7,
                             color="white" if val < cooccurrence.max() * 0.6
                             else "black")
        plt.colorbar(im, ax=ax1, shrink=0.8)
    else:
        ax1.text(0.5, 0.5, "No co-occurrence data", transform=ax1.transAxes,
                 ha="center", va="center", fontsize=14, color="#ff6666")

    # ── 2. Alignment percentage heatmap ──
    ax2 = fig.add_subplot(gs[0, 1])
    uplink_list = sorted(uplink_freqs)
    n_up = len(uplink_list)
    alignment_matrix = np.full((n_up, n_up), np.nan)
    up_idx = {f: i for i, f in enumerate(uplink_list)}

    tol_for_plot = 50  # 50 us tolerance
    for (fa, fb), stats in pair_stats.items():
        if fa in up_idx and fb in up_idx:
            pct = stats["alignment"].get(str(tol_for_plot), 0)
            alignment_matrix[up_idx[fa], up_idx[fb]] = pct
            alignment_matrix[up_idx[fb], up_idx[fa]] = pct

    # Fill diagonal
    for i in range(n_up):
        alignment_matrix[i, i] = 100.0

    if not np.all(np.isnan(alignment_matrix)):
        im2 = ax2.imshow(alignment_matrix, cmap="YlOrRd", aspect="auto",
                         vmin=0, vmax=100)
        ax2.set_xticks(range(n_up))
        ax2.set_xticklabels([f"{f}" for f in uplink_list], fontsize=9)
        ax2.set_yticks(range(n_up))
        ax2.set_yticklabels([f"{f}" for f in uplink_list], fontsize=9)
        ax2.set_title(f"Pulse Alignment (% within +/-{tol_for_plot}us)",
                      fontsize=12)
        for i in range(n_up):
            for j in range(n_up):
                val = alignment_matrix[i, j]
                if not np.isnan(val):
                    ax2.text(j, i, f"{val:.0f}%", ha="center", va="center",
                             fontsize=8,
                             color="black" if val > 50 else "white")
        plt.colorbar(im2, ax=ax2, shrink=0.8)
    else:
        ax2.text(0.5, 0.5, "No alignment data", transform=ax2.transAxes,
                 ha="center", va="center", fontsize=14, color="#ff6666")

    # ── 3. Pulse offset scatter (first N cycles) ──
    ax3 = fig.add_subplot(gs[1, :])
    colors_map = {826: "#ff4444", 828: "#ff8800", 830: "#ffcc00",
                  832: "#00cc44", 834: "#00ccff", 878: "#cc44ff"}
    max_cycles_plot = min(50, len(per_cycle_offsets))

    for ci, cycle_data in enumerate(per_cycle_offsets[:max_cycles_plot]):
        for freq, offsets in cycle_data.items():
            color = colors_map.get(freq, "#888888")
            ax3.scatter([ci] * len(offsets), offsets,
                        s=3, color=color, alpha=0.6, edgecolors="none")

    # Legend
    legend_handles = []
    for f in sorted(colors_map.keys()):
        legend_handles.append(
            plt.Line2D([0], [0], marker="o", color="none",
                       markerfacecolor=colors_map[f], markersize=6,
                       label=f"{f} MHz"))
    ax3.legend(handles=legend_handles, fontsize=8, ncol=6, loc="upper right")
    ax3.set_xlabel("Cycle index", fontsize=10)
    ax3.set_ylabel("Pulse offset within capture (us)", fontsize=10)
    ax3.set_title(f"Pulse Offsets by Cycle (first {max_cycles_plot} multi-freq cycles)",
                  fontsize=12)
    ax3.grid(True, alpha=0.15)

    # ── 4. First-pulse spread distribution ──
    ax4 = fig.add_subplot(gs[2, 0])
    if first_pulse_spreads:
        spreads = np.array(first_pulse_spreads)
        ax4.hist(spreads, bins=min(50, max(15, len(spreads) // 3)),
                 color="#00ccff", alpha=0.85, edgecolor="none")
        ax4.axvline(np.median(spreads), color="#ff4444", linestyle="--",
                    linewidth=1.2,
                    label=f"Median={np.median(spreads):.0f}us")
        ax4.set_xlabel("First-pulse offset spread (us)", fontsize=10)
        ax4.set_ylabel("Count", fontsize=10)
        ax4.set_title("Cross-Freq First-Pulse Spread\n(lower = more synchronized)",
                      fontsize=12)
        ax4.legend(fontsize=8)
        ax4.grid(True, alpha=0.2)
    else:
        ax4.text(0.5, 0.5, "Not enough data", transform=ax4.transAxes,
                 ha="center", va="center", fontsize=14, color="#ff6666")

    # ── 5. Nearest-neighbor delta distributions (uplink pairs) ──
    ax5 = fig.add_subplot(gs[2, 1])
    from itertools import combinations as iter_comb
    plotted_any = False
    for fa, fb in iter_comb(sorted(uplink_freqs), 2):
        deltas = []
        for cycle_data in per_cycle_offsets:
            if fa not in cycle_data or fb not in cycle_data:
                continue
            offsets_a = np.array(cycle_data[fa])
            offsets_b = np.array(cycle_data[fb])
            for oa in offsets_a:
                if len(offsets_b) > 0:
                    deltas.append(float(np.min(np.abs(offsets_b - oa))))
        if deltas:
            deltas_arr = np.array(deltas)
            bins = np.linspace(0, min(deltas_arr.max(), window_us * 0.3), 80)
            ax5.hist(deltas_arr, bins=bins, alpha=0.4, label=f"{fa}-{fb}",
                     edgecolor="none")
            plotted_any = True

    if plotted_any:
        ax5.set_xlabel("Nearest-neighbor offset delta (us)", fontsize=10)
        ax5.set_ylabel("Count", fontsize=10)
        ax5.set_title("NN Delta Distributions (uplink pairs)", fontsize=12)
        ax5.legend(fontsize=7, ncol=2)
        ax5.grid(True, alpha=0.2)
    else:
        ax5.text(0.5, 0.5, "No pair data", transform=ax5.transAxes,
                 ha="center", va="center", fontsize=14, color="#ff6666")

    out = PLOTS_DIR / "cross_frequency_timing.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Plot saved to {out}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Deep pulse timing analysis on sentinel data and IQ captures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pulse repetition interval analysis
  python analyze_pulses.py intervals

  # Pulse width distributions
  python analyze_pulses.py widths

  # Deep IQ analysis of a single capture
  python analyze_pulses.py iq captures/sentinel_826MHz_014542.iq

  # Cross-frequency synchronization test
  python analyze_pulses.py crossfreq
        """
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("intervals",
                   help="Pulse Repetition Interval analysis per frequency")

    sub.add_parser("widths",
                   help="Pulse width distribution histograms")

    p_iq = sub.add_parser("iq",
                          help="Deep IQ analysis of a single raw capture")
    p_iq.add_argument("filepath", type=str,
                      help="Path to .iq file")

    sub.add_parser("crossfreq",
                   help="Cross-frequency pulse timing synchronization test")

    args = parser.parse_args()

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.command == "intervals":
        cmd_intervals(args)
    elif args.command == "widths":
        cmd_widths(args)
    elif args.command == "iq":
        cmd_iq(args)
    elif args.command == "crossfreq":
        cmd_crossfreq(args)


if __name__ == "__main__":
    main()

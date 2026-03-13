#!/usr/bin/env python3
"""
Plot time-series from RF Sentinel JSONL logs.

Reads all sentinel_*.jsonl files from results/ and generates publication-quality
plots for kurtosis, pulse counts, cross-correlation, anomaly timelines, and more.

Usage:
    python plot_timeseries.py
    python plot_timeseries.py --output-dir results/plots/
    python plot_timeseries.py --results-dir results/
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend, safe for headless / SDR host

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from scipy import stats as sp_stats

# ── Target frequencies ──────────────────────────────────────────────────────
TARGET_FREQS = [826.0, 828.0, 830.0, 832.0, 834.0, 878.0]
BASELINE_MEDIAN_KURT = 7.29

# Colors for each target frequency (colorblind-friendly)
FREQ_COLORS = {
    826.0: "#ff6b6b",
    828.0: "#ffa94d",
    830.0: "#ffd43b",
    832.0: "#69db7c",
    834.0: "#4dabf7",
    878.0: "#da77f2",
}


# ── Data loading ────────────────────────────────────────────────────────────

def load_sentinel_logs(results_dir: Path) -> list[dict]:
    """Load and merge all sentinel JSONL files, sorted chronologically."""
    log_files = sorted(results_dir.glob("sentinel_*.jsonl"))
    if not log_files:
        print(f"  ERROR: No sentinel_*.jsonl files found in {results_dir}")
        sys.exit(1)

    entries = []
    skipped = 0
    for log_file in log_files:
        with open(log_file) as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError:
                    skipped += 1

    # Sort by timestamp
    entries.sort(key=lambda e: e.get("timestamp", ""))

    print(f"  Loaded {len(entries)} cycles from {len(log_files)} files")
    if skipped:
        print(f"  (skipped {skipped} malformed lines)")

    return entries


def parse_timestamp(ts_str: str) -> datetime:
    """Parse ISO 8601 timestamp string to datetime."""
    # Handle the +00:00 timezone suffix
    ts_str = ts_str.replace("+00:00", "+0000").replace("Z", "+0000")
    # Try several formats
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    # Fallback: strip timezone and parse
    return datetime.fromisoformat(ts_str.replace("Z", ""))


def extract_stare_data(entries: list[dict]) -> dict:
    """
    Extract per-cycle, per-frequency stare statistics.

    Returns dict keyed by freq_mhz, each value is a dict with:
        timestamps: list of datetime
        elapsed_h:  list of float (hours)
        mean_kurt:  list of float
        min_kurt:   list of float
        max_kurt:   list of float
        total_pulses: list of int
        mean_papr:  list of float
        mean_pwr:   list of float
    """
    data = {f: defaultdict(list) for f in TARGET_FREQS}

    for entry in entries:
        ts = parse_timestamp(entry["timestamp"])
        elapsed_h = entry.get("elapsed_s", 0) / 3600.0
        stare = entry.get("stare", {})

        for freq in TARGET_FREQS:
            freq_key = str(freq)
            captures = stare.get(freq_key, [])
            if not captures:
                continue

            kurts = [c["kurtosis"] for c in captures]
            pulses = sum(c.get("pulse_count", 0) for c in captures)
            paprs = [c.get("papr_db", 0) for c in captures]
            pwrs = [c.get("mean_pwr_db", -99) for c in captures]

            data[freq]["timestamps"].append(ts)
            data[freq]["elapsed_h"].append(elapsed_h)
            data[freq]["mean_kurt"].append(np.mean(kurts))
            data[freq]["min_kurt"].append(np.min(kurts))
            data[freq]["max_kurt"].append(np.max(kurts))
            data[freq]["total_pulses"].append(pulses)
            data[freq]["mean_papr"].append(np.mean(paprs))
            data[freq]["mean_pwr"].append(np.mean(pwrs))

    return data


def extract_anomalies(entries: list[dict]) -> list[dict]:
    """Extract all sweep anomalies with their timestamps."""
    anomalies = []
    for entry in entries:
        ts = parse_timestamp(entry["timestamp"])
        elapsed_h = entry.get("elapsed_s", 0) / 3600.0
        for anom in entry.get("new_anomalies", []):
            anomalies.append({
                "timestamp": ts,
                "elapsed_h": elapsed_h,
                "freq_mhz": anom.get("freq_mhz", 0),
                "kurtosis": anom.get("kurtosis", 0),
                "pulse_count": anom.get("pulse_count", 0),
                "deviation_sigma": anom.get("deviation_sigma", 0),
                "baseline_kurt": anom.get("baseline_kurt", 0),
            })
    return anomalies


# ── Plot generators ─────────────────────────────────────────────────────────

def plot_kurtosis_timeseries(stare_data: dict, output_dir: Path):
    """(a) Kurtosis over time with mean line and min/max shading."""
    fig, axes = plt.subplots(len(TARGET_FREQS), 1, figsize=(16, 3 * len(TARGET_FREQS)),
                             sharex=True)
    if len(TARGET_FREQS) == 1:
        axes = [axes]

    for ax, freq in zip(axes, TARGET_FREQS):
        d = stare_data[freq]
        if not d["elapsed_h"]:
            ax.set_title(f"{freq:.0f} MHz — no data", fontsize=11)
            continue

        t = np.array(d["elapsed_h"])
        mean_k = np.array(d["mean_kurt"])
        min_k = np.array(d["min_kurt"])
        max_k = np.array(d["max_kurt"])
        color = FREQ_COLORS.get(freq, "#ffffff")

        ax.fill_between(t, min_k, max_k, alpha=0.2, color=color, linewidth=0)
        ax.plot(t, mean_k, color=color, linewidth=0.8, alpha=0.9)
        ax.axhline(BASELINE_MEDIAN_KURT, color="#888888", linestyle="--",
                    linewidth=0.7, alpha=0.6, label=f"baseline ({BASELINE_MEDIAN_KURT})")

        ax.set_ylabel("Kurtosis", fontsize=9)
        ax.set_title(f"{freq:.0f} MHz", fontsize=11, fontweight="bold", loc="left")
        ax.legend(loc="upper right", fontsize=7, framealpha=0.4)
        ax.tick_params(labelsize=8)
        ax.set_ylim(bottom=0)

    axes[-1].set_xlabel("Elapsed time (hours)", fontsize=10)
    fig.suptitle("Kurtosis Time Series — Mean (line) with Min/Max (shading)",
                 fontsize=13, fontweight="bold", y=1.0)
    fig.tight_layout()

    out = output_dir / "kurtosis_timeseries.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def plot_pulse_count_timeseries(stare_data: dict, output_dir: Path):
    """(b) Total pulse count per cycle per frequency."""
    fig, axes = plt.subplots(len(TARGET_FREQS), 1, figsize=(16, 3 * len(TARGET_FREQS)),
                             sharex=True)
    if len(TARGET_FREQS) == 1:
        axes = [axes]

    for ax, freq in zip(axes, TARGET_FREQS):
        d = stare_data[freq]
        if not d["elapsed_h"]:
            ax.set_title(f"{freq:.0f} MHz — no data", fontsize=11)
            continue

        t = np.array(d["elapsed_h"])
        pulses = np.array(d["total_pulses"])
        color = FREQ_COLORS.get(freq, "#ffffff")

        ax.fill_between(t, 0, pulses, alpha=0.25, color=color, linewidth=0)
        ax.plot(t, pulses, color=color, linewidth=0.8, alpha=0.9)

        ax.set_ylabel("Pulse count", fontsize=9)
        ax.set_title(f"{freq:.0f} MHz", fontsize=11, fontweight="bold", loc="left")
        ax.tick_params(labelsize=8)
        ax.set_ylim(bottom=0)

    axes[-1].set_xlabel("Elapsed time (hours)", fontsize=10)
    fig.suptitle("Pulse Count Time Series — Total per Cycle",
                 fontsize=13, fontweight="bold", y=1.0)
    fig.tight_layout()

    out = output_dir / "pulse_count_timeseries.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def plot_kurtosis_heatmap(stare_data: dict, output_dir: Path):
    """(c) Kurtosis heatmap: time x frequency, color = mean kurtosis."""
    # Collect all unique elapsed_h values across all freqs, then build a common grid
    all_times = set()
    for freq in TARGET_FREQS:
        all_times.update(stare_data[freq]["elapsed_h"])
    if not all_times:
        print("  WARN: No stare data for heatmap, skipping.")
        return None

    all_times = sorted(all_times)

    # Build 2D grid: rows = freq, cols = time bins
    n_bins = min(len(all_times), 500)  # cap resolution for readability
    t_min, t_max = min(all_times), max(all_times)
    if t_max == t_min:
        t_max = t_min + 1
    bin_edges = np.linspace(t_min, t_max, n_bins + 1)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    grid = np.full((len(TARGET_FREQS), n_bins), np.nan)

    for i, freq in enumerate(TARGET_FREQS):
        d = stare_data[freq]
        if not d["elapsed_h"]:
            continue
        t = np.array(d["elapsed_h"])
        k = np.array(d["mean_kurt"])
        # Bin-average
        bin_idx = np.digitize(t, bin_edges) - 1
        bin_idx = np.clip(bin_idx, 0, n_bins - 1)
        for b in range(n_bins):
            mask = bin_idx == b
            if np.any(mask):
                grid[i, b] = np.mean(k[mask])

    fig, ax = plt.subplots(figsize=(16, 4))

    # Use a perceptual colormap; clip to emphasize structure
    vmin = BASELINE_MEDIAN_KURT
    vmax_data = np.nanpercentile(grid, 98) if not np.all(np.isnan(grid)) else 100
    vmax = max(vmax_data, vmin + 10)

    im = ax.pcolormesh(bin_edges,
                       np.arange(len(TARGET_FREQS) + 1) - 0.5,
                       grid,
                       cmap="inferno", vmin=vmin, vmax=vmax, shading="flat")

    ax.set_yticks(range(len(TARGET_FREQS)))
    ax.set_yticklabels([f"{f:.0f}" for f in TARGET_FREQS], fontsize=9)
    ax.set_ylabel("Frequency (MHz)", fontsize=10)
    ax.set_xlabel("Elapsed time (hours)", fontsize=10)
    ax.set_title("Kurtosis Heatmap — Mean per Cycle", fontsize=13, fontweight="bold")
    ax.tick_params(labelsize=8)

    cbar = fig.colorbar(im, ax=ax, pad=0.02, aspect=30)
    cbar.set_label("Kurtosis", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    fig.tight_layout()
    out = output_dir / "kurtosis_heatmap.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def plot_cross_correlation(stare_data: dict, output_dir: Path):
    """(d) Scatter plots: kurtosis correlation between every pair of target freqs."""
    freq_pairs = list(combinations(TARGET_FREQS, 2))
    n_pairs = len(freq_pairs)

    # Layout: try to make it roughly square
    ncols = min(5, n_pairs)
    nrows = (n_pairs + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3.5 * nrows))
    if nrows == 1 and ncols == 1:
        axes = np.array([[axes]])
    elif nrows == 1:
        axes = axes[np.newaxis, :]
    elif ncols == 1:
        axes = axes[:, np.newaxis]

    for idx, (f1, f2) in enumerate(freq_pairs):
        row, col = divmod(idx, ncols)
        ax = axes[row, col]

        d1 = stare_data[f1]
        d2 = stare_data[f2]

        if not d1["elapsed_h"] or not d2["elapsed_h"]:
            ax.set_title(f"{f1:.0f} vs {f2:.0f} — no data", fontsize=9)
            continue

        # Align on matching elapsed_h values (cycles should be identical)
        t1 = {round(t, 4): k for t, k in zip(d1["elapsed_h"], d1["mean_kurt"])}
        t2 = {round(t, 4): k for t, k in zip(d2["elapsed_h"], d2["mean_kurt"])}
        common = sorted(set(t1.keys()) & set(t2.keys()))

        if len(common) < 3:
            ax.set_title(f"{f1:.0f} vs {f2:.0f} — too few", fontsize=9)
            continue

        k1 = np.array([t1[t] for t in common])
        k2 = np.array([t2[t] for t in common])

        r_val, p_val = sp_stats.pearsonr(k1, k2)

        ax.scatter(k1, k2, s=3, alpha=0.4, color="#4dabf7", edgecolors="none")
        ax.set_xlabel(f"{f1:.0f} MHz", fontsize=8)
        ax.set_ylabel(f"{f2:.0f} MHz", fontsize=8)
        ax.set_title(f"r = {r_val:.3f}", fontsize=9, fontweight="bold")
        ax.tick_params(labelsize=7)

        # Reference line
        lims = [min(k1.min(), k2.min()), max(k1.max(), k2.max())]
        ax.plot(lims, lims, "--", color="#888888", linewidth=0.5, alpha=0.5)

    # Hide unused subplots
    for idx in range(n_pairs, nrows * ncols):
        row, col = divmod(idx, ncols)
        axes[row, col].set_visible(False)

    fig.suptitle("Kurtosis Cross-Correlation — Frequency Pairs (Pearson r)",
                 fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()

    out = output_dir / "cross_correlation.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def plot_hourly_summary(stare_data: dict, output_dir: Path):
    """(e) Bar chart of mean kurtosis per clock-hour for each frequency."""
    # Bucket kurtosis values by clock hour
    hourly = {f: defaultdict(list) for f in TARGET_FREQS}

    for freq in TARGET_FREQS:
        d = stare_data[freq]
        for ts, kurt in zip(d["timestamps"], d["mean_kurt"]):
            hour = ts.hour
            hourly[freq][hour].append(kurt)

    # Find the range of hours present
    all_hours = set()
    for freq in TARGET_FREQS:
        all_hours.update(hourly[freq].keys())
    if not all_hours:
        print("  WARN: No hourly data, skipping.")
        return None
    hours = sorted(all_hours)

    fig, ax = plt.subplots(figsize=(14, 6))

    n_freqs = len(TARGET_FREQS)
    bar_width = 0.8 / n_freqs
    x = np.arange(len(hours))

    for i, freq in enumerate(TARGET_FREQS):
        means = [np.mean(hourly[freq][h]) if hourly[freq][h] else 0 for h in hours]
        offset = (i - n_freqs / 2 + 0.5) * bar_width
        bars = ax.bar(x + offset, means, bar_width, label=f"{freq:.0f} MHz",
                       color=FREQ_COLORS.get(freq, "#ffffff"), alpha=0.85,
                       edgecolor="none")

    ax.axhline(BASELINE_MEDIAN_KURT, color="#888888", linestyle="--",
               linewidth=0.7, alpha=0.6, label=f"baseline ({BASELINE_MEDIAN_KURT})")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{h:02d}:00" for h in hours], fontsize=8, rotation=45,
                       ha="right")
    ax.set_xlabel("Hour (UTC)", fontsize=10)
    ax.set_ylabel("Mean kurtosis", fontsize=10)
    ax.set_title("Hourly Mean Kurtosis — Diurnal Pattern",
                 fontsize=13, fontweight="bold")
    ax.legend(fontsize=8, loc="upper right", ncol=3, framealpha=0.4)
    ax.tick_params(labelsize=8)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    out = output_dir / "hourly_summary.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def plot_anomaly_timeline(anomalies: list[dict], output_dir: Path):
    """(f) Timeline of sweep anomalies: x=time, y=freq, size=kurtosis."""
    if not anomalies:
        print("  WARN: No anomalies found, generating empty timeline.")

    fig, ax = plt.subplots(figsize=(16, 6))

    if anomalies:
        times = [a["elapsed_h"] for a in anomalies]
        freqs = [a["freq_mhz"] for a in anomalies]
        kurts = [a["kurtosis"] for a in anomalies]

        # Scale marker size: normalize kurtosis to a visible range
        k_arr = np.array(kurts)
        k_min, k_max = k_arr.min(), k_arr.max()
        if k_max > k_min:
            sizes = 15 + 200 * (k_arr - k_min) / (k_max - k_min)
        else:
            sizes = np.full_like(k_arr, 60)

        sc = ax.scatter(times, freqs, s=sizes, c=kurts, cmap="plasma",
                        alpha=0.7, edgecolors="white", linewidths=0.3)
        cbar = fig.colorbar(sc, ax=ax, pad=0.02, aspect=30)
        cbar.set_label("Kurtosis", fontsize=9)
        cbar.ax.tick_params(labelsize=8)

        # Mark target frequencies with horizontal lines
        for freq in TARGET_FREQS:
            ax.axhline(freq, color=FREQ_COLORS.get(freq, "#555555"),
                       linestyle=":", linewidth=0.5, alpha=0.4)

        ax.set_xlim(left=min(times) - 0.1)
    else:
        ax.text(0.5, 0.5, "No anomalies detected", transform=ax.transAxes,
                ha="center", va="center", fontsize=14, alpha=0.5)

    ax.set_xlabel("Elapsed time (hours)", fontsize=10)
    ax.set_ylabel("Frequency (MHz)", fontsize=10)
    ax.set_title("Sweep Anomaly Timeline — Marker size proportional to kurtosis",
                 fontsize=13, fontweight="bold")
    ax.tick_params(labelsize=8)

    fig.tight_layout()
    out = output_dir / "anomaly_timeline.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate time-series plots from RF Sentinel logs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    python plot_timeseries.py
    python plot_timeseries.py --output-dir results/plots/
    python plot_timeseries.py --results-dir /path/to/results/
"""
    )
    parser.add_argument("--results-dir", type=str, default="results",
                        help="Directory containing sentinel_*.jsonl files (default: results/)")
    parser.add_argument("--output-dir", type=str, default="results/plots",
                        help="Directory for output PNG files (default: results/plots/)")

    args = parser.parse_args()
    results_dir = Path(args.results_dir)
    output_dir = Path(args.output_dir)

    print(f"\n{'='*60}")
    print(f"  RF Sentinel — Time-Series Plot Generator")
    print(f"{'='*60}")
    print(f"  Source:  {results_dir.resolve()}")
    print(f"  Output:  {output_dir.resolve()}")
    print()

    # ── Load data ──
    entries = load_sentinel_logs(results_dir)
    if not entries:
        print("  No data to plot.")
        sys.exit(1)

    t0 = parse_timestamp(entries[0]["timestamp"])
    t1 = parse_timestamp(entries[-1]["timestamp"])
    span_h = (t1 - t0).total_seconds() / 3600.0
    print(f"  Time span: {t0.strftime('%Y-%m-%d %H:%M')} to "
          f"{t1.strftime('%Y-%m-%d %H:%M')} ({span_h:.1f}h)")
    print()

    stare_data = extract_stare_data(entries)
    anomalies = extract_anomalies(entries)

    # Summarize what we found
    for freq in TARGET_FREQS:
        n = len(stare_data[freq]["elapsed_h"])
        if n:
            avg_k = np.mean(stare_data[freq]["mean_kurt"])
            print(f"  {freq:.0f} MHz: {n} cycles, mean kurt={avg_k:.1f}")
        else:
            print(f"  {freq:.0f} MHz: no data")
    print(f"  Anomalies: {len(anomalies)} total")
    print()

    # ── Set style and generate plots ──
    plt.style.use("dark_background")
    plt.rcParams.update({
        "font.family": "monospace",
        "axes.grid": True,
        "grid.alpha": 0.15,
        "grid.linewidth": 0.5,
    })

    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    print("  Generating plots...")

    out = plot_kurtosis_timeseries(stare_data, output_dir)
    if out:
        generated.append(out)
        print(f"    [1/6] {out.name}")

    out = plot_pulse_count_timeseries(stare_data, output_dir)
    if out:
        generated.append(out)
        print(f"    [2/6] {out.name}")

    out = plot_kurtosis_heatmap(stare_data, output_dir)
    if out:
        generated.append(out)
        print(f"    [3/6] {out.name}")

    out = plot_cross_correlation(stare_data, output_dir)
    if out:
        generated.append(out)
        print(f"    [4/6] {out.name}")

    out = plot_hourly_summary(stare_data, output_dir)
    if out:
        generated.append(out)
        print(f"    [5/6] {out.name}")

    out = plot_anomaly_timeline(anomalies, output_dir)
    if out:
        generated.append(out)
        print(f"    [6/6] {out.name}")

    print()
    print(f"  {'='*60}")
    print(f"  Generated {len(generated)} plots in {output_dir.resolve()}")
    for p in generated:
        print(f"    {p.name}")
    print(f"  {'='*60}")
    print()


if __name__ == "__main__":
    main()

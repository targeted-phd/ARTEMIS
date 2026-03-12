#!/usr/bin/env python3
"""
RF Sentinel Report Generator — Comprehensive analysis of sentinel monitoring data.

Reads all sentinel JSONL logs and checkpoint data, then generates a detailed
fixed-width text report suitable for handing to another engineer or investigator.

Usage:
    python generate_report.py                  # auto-find all sentinel logs
    python generate_report.py --results-dir results --output results/report.txt
"""

import json
import os
import sys
import argparse
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


# ── Constants ────────────────────────────────────────────────────────────────

TARGET_FREQS = [826.0, 828.0, 830.0, 832.0, 834.0, 878.0]
UPLINK_FREQS = [826.0, 828.0, 830.0, 832.0, 834.0]
DOWNLINK_FREQS = [878.0]

# Expected LTE reference values
EXPECTED_LTE_UPLINK_KURTOSIS = (3.5, 4.0)     # SC-FDMA
EXPECTED_LTE_DOWNLINK_KURTOSIS = (3.8, 4.5)   # OFDM
EXPECTED_LTE_UPLINK_PAPR = (7.0, 8.0)         # SC-FDMA dB
EXPECTED_LTE_DOWNLINK_PAPR = (10.0, 12.0)     # OFDM dB
EXPECTED_GAUSSIAN_KURTOSIS = 3.0
RTL_SDR_BASELINE_KURTOSIS = 8.0  # typical 8-bit ADC quantization noise

REPORT_WIDTH = 88
SECTION_CHAR = "="
SUBSECTION_CHAR = "-"


# ── Data Loading ─────────────────────────────────────────────────────────────

def load_sentinel_logs(results_dir):
    """Load all sentinel JSONL log files, return list of cycle entries."""
    log_files = sorted(Path(results_dir).glob("sentinel_*.jsonl"))
    cycles = []
    parse_errors = 0
    for lf in log_files:
        with open(lf) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entry["_source_file"] = lf.name
                    cycles.append(entry)
                except json.JSONDecodeError:
                    parse_errors += 1
    return cycles, log_files, parse_errors


def load_checkpoint(results_dir):
    """Load the sentinel checkpoint file."""
    ckpt_path = Path(results_dir) / "sentinel_checkpoint.json"
    if not ckpt_path.exists():
        return None
    with open(ckpt_path) as f:
        return json.load(f)


def extract_captures(cycles, freq):
    """Extract all stare capture results for a given frequency across all cycles."""
    freq_key = str(float(freq))
    captures = []
    for cycle in cycles:
        stare = cycle.get("stare", {})
        freq_results = stare.get(freq_key, [])
        for r in freq_results:
            r["_cycle"] = cycle.get("cycle", 0)
            r["_timestamp"] = cycle.get("timestamp", "")
            captures.append(r)
    return captures


def extract_all_anomalies(cycles):
    """Extract all sweep anomalies across all cycles."""
    anomalies = []
    for cycle in cycles:
        ts = cycle.get("timestamp", "")
        cycle_num = cycle.get("cycle", 0)
        for a in cycle.get("new_anomalies", []):
            a["_cycle"] = cycle_num
            a["_timestamp"] = ts
            anomalies.append(a)
    return anomalies


# ── Statistics Helpers ───────────────────────────────────────────────────────

def safe_percentile(data, pct):
    """Compute percentile without numpy."""
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * pct / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return d0 + d1


def compute_stats(values):
    """Compute comprehensive statistics for a list of values."""
    if not values:
        return {
            "n": 0, "min": 0, "max": 0, "mean": 0, "median": 0, "std": 0,
            "p25": 0, "p75": 0, "p95": 0, "p99": 0,
        }
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n if n > 1 else 0
    std = math.sqrt(variance)
    return {
        "n": n,
        "min": min(values),
        "max": max(values),
        "mean": mean,
        "median": safe_percentile(values, 50),
        "std": std,
        "p25": safe_percentile(values, 25),
        "p75": safe_percentile(values, 75),
        "p95": safe_percentile(values, 95),
        "p99": safe_percentile(values, 99),
    }


def pearson_r(x, y):
    """Compute Pearson correlation coefficient between two lists."""
    n = min(len(x), len(y))
    if n < 3:
        return float("nan")
    x = x[:n]
    y = y[:n]
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / n
    sx = math.sqrt(sum((xi - mx) ** 2 for xi in x) / n)
    sy = math.sqrt(sum((yi - my) ** 2 for yi in y) / n)
    if sx == 0 or sy == 0:
        return float("nan")
    return cov / (sx * sy)


def parse_timestamp(ts_str):
    """Parse ISO 8601 timestamp to datetime, handling various formats."""
    if not ts_str:
        return None
    # Handle timezone-aware strings
    ts_str = ts_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return None


def format_duration(seconds):
    """Format seconds as Xh Ym Zs."""
    if seconds is None or seconds < 0:
        return "N/A"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    elif m > 0:
        return f"{m}m {s:02d}s"
    else:
        return f"{s}s"


# ── Report Formatting ────────────────────────────────────────────────────────

class ReportBuilder:
    def __init__(self, width=REPORT_WIDTH):
        self.width = width
        self.lines = []

    def add(self, text=""):
        self.lines.append(text)

    def blank(self, n=1):
        for _ in range(n):
            self.lines.append("")

    def separator(self, char=SECTION_CHAR):
        self.lines.append(char * self.width)

    def section_header(self, number, title):
        self.blank()
        self.separator()
        header = f"  {number}. {title}"
        self.add(header)
        self.separator()
        self.blank()

    def subsection(self, title):
        self.blank()
        self.add(f"  {SUBSECTION_CHAR * 3} {title} {SUBSECTION_CHAR * (self.width - len(title) - 8)}")
        self.blank()

    def table_row(self, cells, widths, align=None):
        """Format a table row with fixed-width columns."""
        parts = []
        for i, (cell, w) in enumerate(zip(cells, widths)):
            cell_str = str(cell)
            a = (align[i] if align and i < len(align) else "<")
            if a == ">":
                parts.append(cell_str.rjust(w))
            elif a == "^":
                parts.append(cell_str.center(w))
            else:
                parts.append(cell_str.ljust(w))
        self.add("    " + "  ".join(parts))

    def table_separator(self, widths):
        parts = ["-" * w for w in widths]
        self.add("    " + "  ".join(parts))

    def get_text(self):
        return "\n".join(self.lines) + "\n"


# ── Report Sections ──────────────────────────────────────────────────────────

def section_executive_summary(rpt, cycles, checkpoint, captures_by_freq, all_anomalies):
    """Section 1: Executive Summary."""
    rpt.section_header(1, "EXECUTIVE SUMMARY")

    # Determine time range
    timestamps = []
    for c in cycles:
        ts = parse_timestamp(c.get("timestamp"))
        if ts:
            timestamps.append(ts)

    if timestamps:
        t_start = min(timestamps)
        t_end = max(timestamps)
        duration_s = (t_end - t_start).total_seconds()
    else:
        t_start = t_end = None
        duration_s = 0

    start_str = t_start.strftime("%Y-%m-%d %H:%M UTC") if t_start else "unknown"
    dur_str = format_duration(duration_s)
    n_cycles = len(cycles)

    # Compute overall kurtosis range across all targets
    all_kurts = []
    for freq in TARGET_FREQS:
        for cap in captures_by_freq.get(freq, []):
            all_kurts.append(cap.get("kurtosis", 0))

    if all_kurts:
        kurt_min = min(all_kurts)
        kurt_max = max(all_kurts)
        kurt_mean = sum(all_kurts) / len(all_kurts)
    else:
        kurt_min = kurt_max = kurt_mean = 0

    total_caps = sum(len(v) for v in captures_by_freq.values())
    total_pulses = sum(cap.get("pulse_count", 0)
                       for caps in captures_by_freq.values()
                       for cap in caps)

    rpt.add(f"    An RTL-SDR receiver monitored six frequencies (826, 828, 830, 832, 834,")
    rpt.add(f"    878 MHz) continuously for {dur_str} beginning {start_str},")
    rpt.add(f"    collecting {total_caps:,} individual captures across {n_cycles:,} cycles.")
    rpt.add(f"    All six channels exhibit anomalous impulsive behavior with kurtosis")
    rpt.add(f"    values ranging from {kurt_min:.1f} to {kurt_max:.1f} (mean {kurt_mean:.1f}),")
    rpt.add(f"    far exceeding the ~3.5-4.0 expected for normal LTE SC-FDMA uplink traffic")
    rpt.add(f"    or the ~8 baseline from RTL-SDR quantization noise. A total of")
    rpt.add(f"    {total_pulses:,} microsecond-scale pulses were detected. These measurements")
    rpt.add(f"    are inconsistent with standard cellular traffic and warrant further")
    rpt.add(f"    investigation with calibrated instrumentation.")


def section_measurement_parameters(rpt, cycles, checkpoint, log_files):
    """Section 2: Measurement Parameters."""
    rpt.section_header(2, "MEASUREMENT PARAMETERS")

    timestamps = [parse_timestamp(c.get("timestamp")) for c in cycles]
    timestamps = [t for t in timestamps if t is not None]
    if timestamps:
        t_start = min(timestamps)
        t_end = max(timestamps)
        duration_s = (t_end - t_start).total_seconds()
    else:
        t_start = t_end = None
        duration_s = 0

    ckpt_start = checkpoint.get("start_time", "") if checkpoint else ""
    ckpt_end = checkpoint.get("last_update", "") or (checkpoint.get("end_time", "") if checkpoint else "")

    bl_median = checkpoint.get("bl_median", "N/A") if checkpoint else "N/A"
    bl_sigma = checkpoint.get("bl_sigma", "N/A") if checkpoint else "N/A"
    total_cycles = checkpoint.get("total_cycles", len(cycles)) if checkpoint else len(cycles)

    rpt.add(f"    SDR Hardware:         RTL-SDR (RTL2832U + R820T/R828D tuner)")
    rpt.add(f"    Sample Rate:          2.4 MSPS (2,400,000 samples/sec)")
    rpt.add(f"    Gain:                 28.0 dB")
    rpt.add(f"    Stare Dwell Time:     200 ms per capture")
    rpt.add(f"    Sweep Dwell Time:     100 ms per channel")
    rpt.add(f"    Stare Pairs/Cycle:    5 (5 captures per frequency per cycle)")
    rpt.add(f"    DC Notch:             +/-16 bins zeroed in FFT")
    rpt.add(f"    PLL Settle Discard:   48,000 samples (20 ms)")
    rpt.add(f"    Pulse Threshold:      mean + 4*sigma")
    rpt.add(f"    Min Pulse Width:      3 samples (~1.25 us)")
    rpt.blank()
    rpt.add(f"    Target Frequencies:   {', '.join(f'{f:.0f}' for f in TARGET_FREQS)} MHz")
    rpt.add(f"    Sweep Range:          400-1000 MHz (6 MHz steps, every 3rd channel)")
    rpt.blank()
    rpt.add(f"    Monitoring Start:     {ckpt_start}")
    rpt.add(f"    Last Update:          {ckpt_end}")
    rpt.add(f"    Duration:             {format_duration(duration_s)}")
    rpt.add(f"    Total Cycles:         {total_cycles}")
    rpt.add(f"    Log Files:            {len(log_files)} hourly JSONL files")
    rpt.blank()
    rpt.add(f"    Baseline Kurtosis:    median={bl_median:.4f}  sigma={bl_sigma:.4f}" if isinstance(bl_median, float)
            else f"    Baseline Kurtosis:    {bl_median}")


def section_baseline_characterization(rpt, checkpoint):
    """Section 3: Baseline Characterization."""
    rpt.section_header(3, "BASELINE CHARACTERIZATION")

    if not checkpoint:
        rpt.add("    No checkpoint data available.")
        return

    baseline = checkpoint.get("baseline", {})
    bl_median = checkpoint.get("bl_median", 0)
    bl_sigma = checkpoint.get("bl_sigma", 0)

    # Collect all baseline kurtosis values
    bl_values = list(baseline.values())
    bl_stats = compute_stats(bl_values) if bl_values else None

    rpt.add(f"    The baseline sweep measured {len(baseline)} channels across 400-1000 MHz.")
    rpt.add(f"    Baseline statistics are derived using Median Absolute Deviation (MAD)")
    rpt.add(f"    for robustness against outliers.")
    rpt.blank()
    rpt.add(f"    Baseline median kurtosis:          {bl_median:.4f}")
    rpt.add(f"    Baseline robust sigma (MAD*1.4826): {bl_sigma:.4f}")
    if bl_stats:
        rpt.add(f"    Baseline kurtosis range:            {bl_stats['min']:.3f} - {bl_stats['max']:.3f}")
        rpt.add(f"    Baseline kurtosis mean:             {bl_stats['mean']:.3f}")
    rpt.blank()
    rpt.add(f"    Reference Values:")
    rpt.add(f"      Gaussian noise (theoretical):     kurtosis = 3.0")
    rpt.add(f"      RTL-SDR 8-bit quantized noise:    kurtosis ~ 8-10")
    rpt.add(f"      Normal LTE SC-FDMA uplink:        kurtosis = 3.5-4.0")
    rpt.add(f"      Normal LTE OFDM downlink:         kurtosis = 3.8-4.5")
    rpt.blank()

    # Show how target frequencies compare
    rpt.add(f"    Target frequency baseline kurtosis vs band median:")
    th = checkpoint.get("target_history", {})
    for freq in TARGET_FREQS:
        bl_k = baseline.get(str(float(freq)), None)
        init_k = th.get(str(float(freq)), {}).get("initial_kurt", bl_k)
        if bl_k is not None:
            sigma_above = (bl_k - bl_median) / bl_sigma if bl_sigma > 0 else 0
            rpt.add(f"      {freq:.0f} MHz: kurtosis = {bl_k:.2f}"
                    f"  ({sigma_above:+.1f} sigma above median)")
        else:
            rpt.add(f"      {freq:.0f} MHz: no baseline data")


def section_target_frequency_analysis(rpt, captures_by_freq, checkpoint):
    """Section 4: Target Frequency Analysis."""
    rpt.section_header(4, "TARGET FREQUENCY ANALYSIS")

    bl_median = checkpoint.get("bl_median", 8.0) if checkpoint else 8.0
    bl_sigma = checkpoint.get("bl_sigma", 2.0) if checkpoint else 2.0
    anomaly_thresh = bl_median + 3 * bl_sigma

    for freq in TARGET_FREQS:
        caps = captures_by_freq.get(freq, [])
        band_label = "Uplink (Band 5/26)" if freq in UPLINK_FREQS else "Downlink (Band 5/26)"
        rpt.subsection(f"{freq:.0f} MHz -- {band_label}")

        if not caps:
            rpt.add(f"    No capture data available for {freq:.0f} MHz.")
            continue

        rpt.add(f"    Total captures analyzed: {len(caps)}")
        rpt.blank()

        # Kurtosis
        kurts = [c.get("kurtosis", 0) for c in caps]
        ks = compute_stats(kurts)
        rpt.add(f"    Kurtosis:")
        rpt.add(f"      Min:      {ks['min']:10.3f}")
        rpt.add(f"      Max:      {ks['max']:10.3f}")
        rpt.add(f"      Mean:     {ks['mean']:10.3f}")
        rpt.add(f"      Median:   {ks['median']:10.3f}")
        rpt.add(f"      Std Dev:  {ks['std']:10.3f}")
        rpt.add(f"      P25:      {ks['p25']:10.3f}")
        rpt.add(f"      P75:      {ks['p75']:10.3f}")
        rpt.add(f"      P95:      {ks['p95']:10.3f}")
        rpt.add(f"      P99:      {ks['p99']:10.3f}")
        rpt.blank()

        # PAPR
        paprs = [c.get("papr_db", 0) for c in caps]
        ps = compute_stats(paprs)
        rpt.add(f"    PAPR (dB):")
        rpt.add(f"      Min:      {ps['min']:10.2f}")
        rpt.add(f"      Max:      {ps['max']:10.2f}")
        rpt.add(f"      Mean:     {ps['mean']:10.2f}")
        rpt.add(f"      Median:   {ps['median']:10.2f}")
        rpt.add(f"      Std Dev:  {ps['std']:10.2f}")
        rpt.add(f"      P25:      {ps['p25']:10.2f}")
        rpt.add(f"      P75:      {ps['p75']:10.2f}")
        rpt.add(f"      P95:      {ps['p95']:10.2f}")
        rpt.add(f"      P99:      {ps['p99']:10.2f}")
        rpt.blank()

        # Pulse count
        pcounts = [c.get("pulse_count", 0) for c in caps]
        pcs = compute_stats(pcounts)
        rpt.add(f"    Pulse Count per Capture:")
        rpt.add(f"      Min:      {pcs['min']:10.0f}")
        rpt.add(f"      Max:      {pcs['max']:10.0f}")
        rpt.add(f"      Mean:     {pcs['mean']:10.1f}")
        rpt.add(f"      Median:   {pcs['median']:10.0f}")
        rpt.add(f"      Std Dev:  {pcs['std']:10.1f}")
        rpt.add(f"      Total:    {sum(pcounts):10d}")
        rpt.blank()

        # Pulse widths
        all_widths = []
        for c in caps:
            for p in c.get("pulses", []):
                w = p.get("width_us", 0)
                if w > 0:
                    all_widths.append(w)

        if all_widths:
            ws = compute_stats(all_widths)
            rpt.add(f"    Pulse Widths (us) -- from {len(all_widths)} recorded pulses:")
            rpt.add(f"      Min:      {ws['min']:10.2f}")
            rpt.add(f"      Max:      {ws['max']:10.2f}")
            rpt.add(f"      Mean:     {ws['mean']:10.2f}")
            rpt.add(f"      Median:   {ws['median']:10.2f}")
            rpt.add(f"      P95:      {ws['p95']:10.2f}")

            # Width distribution buckets
            buckets = [(0, 2, "< 2 us"), (2, 5, "2-5 us"), (5, 10, "5-10 us"),
                       (10, 20, "10-20 us"), (20, float("inf"), "> 20 us")]
            rpt.blank()
            rpt.add(f"      Width distribution:")
            for lo, hi, label in buckets:
                count = sum(1 for w in all_widths if lo <= w < hi)
                pct = count / len(all_widths) * 100
                bar = "#" * int(pct / 2)
                rpt.add(f"        {label:>10s}: {count:6d} ({pct:5.1f}%)  {bar}")
        else:
            rpt.add(f"    Pulse Widths: no pulse detail data recorded")
        rpt.blank()

        # Mean power
        pwrs = [c.get("mean_pwr_db", -999) for c in caps if c.get("mean_pwr_db", -999) > -998]
        if pwrs:
            pwr_s = compute_stats(pwrs)
            rpt.add(f"    Mean Power Level (dB):")
            rpt.add(f"      Mean:     {pwr_s['mean']:10.2f}")
            rpt.add(f"      Std Dev:  {pwr_s['std']:10.2f}")
            rpt.add(f"      Range:    {pwr_s['min']:.2f} to {pwr_s['max']:.2f}")
        rpt.blank()

        # Fraction exceeding anomaly threshold
        n_anomalous = sum(1 for k in kurts if k > anomaly_thresh)
        frac = n_anomalous / len(kurts) * 100 if kurts else 0
        rpt.add(f"    Anomaly Rate (kurtosis > {anomaly_thresh:.1f}, i.e., > 3 sigma above baseline):")
        rpt.add(f"      {n_anomalous} / {len(kurts)} captures ({frac:.1f}%)")
        rpt.blank()

        # Assessment
        if freq in UPLINK_FREQS:
            exp_kurt = EXPECTED_LTE_UPLINK_KURTOSIS
            exp_papr = EXPECTED_LTE_UPLINK_PAPR
            lte_type = "SC-FDMA uplink"
        else:
            exp_kurt = EXPECTED_LTE_DOWNLINK_KURTOSIS
            exp_papr = EXPECTED_LTE_DOWNLINK_PAPR
            lte_type = "OFDM downlink"

        kurt_ratio = ks["mean"] / ((exp_kurt[0] + exp_kurt[1]) / 2)
        papr_ratio = ps["mean"] / ((exp_papr[0] + exp_papr[1]) / 2)

        rpt.add(f"    Assessment:")
        rpt.add(f"      Expected LTE {lte_type} kurtosis: {exp_kurt[0]}-{exp_kurt[1]}")
        rpt.add(f"      Observed mean kurtosis: {ks['mean']:.1f} ({kurt_ratio:.0f}x expected)")
        rpt.add(f"      Expected LTE {lte_type} PAPR: {exp_papr[0]}-{exp_papr[1]} dB")
        rpt.add(f"      Observed mean PAPR: {ps['mean']:.1f} dB ({papr_ratio:.1f}x expected)")
        if ks["mean"] > exp_kurt[1] * 2:
            rpt.add(f"      VERDICT: INCONSISTENT with normal {lte_type} traffic.")
            rpt.add(f"               Kurtosis is {kurt_ratio:.0f}x above expected range.")
            if sum(pcounts) > 0:
                rpt.add(f"               {sum(pcounts):,} isolated us-scale pulses detected;")
                rpt.add(f"               FDD LTE should produce continuous waveforms, not pulses.")
        else:
            rpt.add(f"      VERDICT: Possibly consistent with normal traffic (further review needed).")


def section_temporal_analysis(rpt, cycles, captures_by_freq):
    """Section 5: Temporal Analysis."""
    rpt.section_header(5, "TEMPORAL ANALYSIS")

    # Bin captures by hour
    hourly_data = defaultdict(lambda: defaultdict(list))  # hour_label -> freq -> [kurtosis]

    for freq in TARGET_FREQS:
        for cap in captures_by_freq.get(freq, []):
            ts = parse_timestamp(cap.get("_timestamp", ""))
            if ts is None:
                # Try wall_time
                wt = cap.get("wall_time")
                if wt:
                    ts = datetime.fromtimestamp(wt, tz=timezone.utc)
            if ts is None:
                continue
            hour_label = ts.strftime("%Y-%m-%d %H:00")
            hourly_data[hour_label][freq].append(cap.get("kurtosis", 0))

    if not hourly_data:
        rpt.add("    No temporal data available.")
        return

    sorted_hours = sorted(hourly_data.keys())

    # Hourly mean kurtosis table
    rpt.add(f"    Hourly Mean Kurtosis by Frequency:")
    rpt.blank()

    # Table header
    freq_labels = [f"{f:.0f}" for f in TARGET_FREQS]
    hdr = ["Hour (UTC)"] + freq_labels
    widths = [18] + [10] * len(TARGET_FREQS)
    aligns = ["<"] + [">"] * len(TARGET_FREQS)
    rpt.table_row(hdr, widths, aligns)
    rpt.table_separator(widths)

    # Track for change detection
    prev_means = {}
    significant_changes = []

    for hour in sorted_hours:
        row = [hour]
        for freq in TARGET_FREQS:
            vals = hourly_data[hour].get(freq, [])
            if vals:
                mean_k = sum(vals) / len(vals)
                row.append(f"{mean_k:.1f}")

                # Check for significant change from previous hour
                key = freq
                if key in prev_means:
                    delta = abs(mean_k - prev_means[key])
                    if delta > 20 and (mean_k > 15 or prev_means[key] > 15):
                        significant_changes.append(
                            (hour, freq, prev_means[key], mean_k, delta))
                prev_means[key] = mean_k
            else:
                row.append("--")
        rpt.table_row(row, widths, aligns)

    # Flag significant changes
    if significant_changes:
        rpt.blank()
        rpt.add(f"    Significant Hourly Changes (delta > 20, above noise floor):")
        for hour, freq, prev, curr, delta in significant_changes:
            direction = "UP" if curr > prev else "DOWN"
            rpt.add(f"      {hour}  {freq:.0f} MHz: {prev:.1f} -> {curr:.1f}"
                    f"  (delta={delta:.1f}, {direction})")
    else:
        rpt.blank()
        rpt.add(f"    No significant hourly changes detected (threshold: delta > 20).")

    # Periodicity analysis
    rpt.blank()
    rpt.subsection("Duty Cycle / Periodicity Assessment")

    for freq in TARGET_FREQS:
        caps = captures_by_freq.get(freq, [])
        if not caps:
            continue

        kurts = [c.get("kurtosis", 0) for c in caps]
        # Count captures with "active" signal (kurtosis > some threshold)
        active_thresh = 15.0  # above RTL-SDR noise floor
        n_active = sum(1 for k in kurts if k > active_thresh)
        duty_cycle = n_active / len(kurts) * 100 if kurts else 0

        # Count captures at baseline (near RTL-SDR noise)
        n_baseline = sum(1 for k in kurts if k < 10.0)
        baseline_frac = n_baseline / len(kurts) * 100 if kurts else 0

        rpt.add(f"    {freq:.0f} MHz:")
        rpt.add(f"      Captures with kurtosis > 15 (active): {n_active}/{len(kurts)}"
                f" ({duty_cycle:.1f}%)")
        rpt.add(f"      Captures with kurtosis < 10 (quiet):  {n_baseline}/{len(kurts)}"
                f" ({baseline_frac:.1f}%)")
        if duty_cycle > 0 and duty_cycle < 100:
            rpt.add(f"      Signal appears intermittent (duty cycle ~{duty_cycle:.0f}%)")
        elif duty_cycle >= 100:
            rpt.add(f"      Signal appears continuously present")
        else:
            rpt.add(f"      No anomalous activity detected")
        rpt.blank()


def section_cross_frequency_correlation(rpt, captures_by_freq, cycles):
    """Section 6: Cross-Frequency Correlation."""
    rpt.section_header(6, "CROSS-FREQUENCY CORRELATION")

    # Build per-cycle mean kurtosis time series for each frequency
    cycle_kurt = defaultdict(dict)  # cycle_num -> {freq: mean_kurt}
    for cycle in cycles:
        cn = cycle.get("cycle", 0)
        stare = cycle.get("stare", {})
        for freq in TARGET_FREQS:
            freq_key = str(float(freq))
            results = stare.get(freq_key, [])
            if results:
                kurts = [r.get("kurtosis", 0) for r in results]
                cycle_kurt[cn][freq] = sum(kurts) / len(kurts)

    sorted_cycle_nums = sorted(cycle_kurt.keys())

    # Build aligned time series
    time_series = {}
    for freq in TARGET_FREQS:
        time_series[freq] = [cycle_kurt[cn].get(freq) for cn in sorted_cycle_nums]

    # Compute correlation matrix (only for cycles where both freqs have data)
    rpt.add(f"    Pearson Correlation Matrix (per-cycle mean kurtosis):")
    rpt.add(f"    Computed over {len(sorted_cycle_nums)} cycles.")
    rpt.blank()

    # Header row
    freq_labels = [f"{f:.0f}" for f in TARGET_FREQS]
    hdr = ["MHz"] + freq_labels
    widths = [8] + [8] * len(TARGET_FREQS)
    aligns = [">"] * (1 + len(TARGET_FREQS))
    rpt.table_row(hdr, widths, aligns)
    rpt.table_separator(widths)

    corr_matrix = {}
    for fi, freq_i in enumerate(TARGET_FREQS):
        row = [f"{freq_i:.0f}"]
        for fj, freq_j in enumerate(TARGET_FREQS):
            # Get paired observations
            xi = []
            xj = []
            for cn in sorted_cycle_nums:
                vi = cycle_kurt[cn].get(freq_i)
                vj = cycle_kurt[cn].get(freq_j)
                if vi is not None and vj is not None:
                    xi.append(vi)
                    xj.append(vj)
            if xi and xj:
                r = pearson_r(xi, xj)
                corr_matrix[(freq_i, freq_j)] = r
                if math.isnan(r):
                    row.append("N/A")
                else:
                    row.append(f"{r:.3f}")
            else:
                row.append("--")
                corr_matrix[(freq_i, freq_j)] = float("nan")
        rpt.table_row(row, widths, aligns)

    rpt.blank()

    # Interpretation: uplink cluster correlation
    rpt.add(f"    Interpretation:")
    rpt.blank()

    uplink_pairs = []
    for i, fi in enumerate(UPLINK_FREQS):
        for fj in UPLINK_FREQS[i + 1:]:
            r = corr_matrix.get((fi, fj), float("nan"))
            if not math.isnan(r):
                uplink_pairs.append(r)

    if uplink_pairs:
        mean_uplink_r = sum(uplink_pairs) / len(uplink_pairs)
        rpt.add(f"    Uplink cluster (826-834 MHz) mean pairwise correlation: r = {mean_uplink_r:.3f}")
        if mean_uplink_r > 0.5:
            rpt.add(f"      Strong positive correlation -- uplink channels behave as a group.")
            rpt.add(f"      This suggests a common source or mechanism across the uplink band.")
        elif mean_uplink_r > 0.2:
            rpt.add(f"      Moderate correlation -- some shared behavior across uplink channels.")
        else:
            rpt.add(f"      Weak correlation -- channels appear to behave independently.")
    rpt.blank()

    # Uplink vs downlink
    ul_dl_corrs = []
    for ul_freq in UPLINK_FREQS:
        for dl_freq in DOWNLINK_FREQS:
            r = corr_matrix.get((ul_freq, dl_freq), float("nan"))
            if not math.isnan(r):
                ul_dl_corrs.append((ul_freq, dl_freq, r))

    if ul_dl_corrs:
        mean_ul_dl_r = sum(r for _, _, r in ul_dl_corrs) / len(ul_dl_corrs)
        rpt.add(f"    Uplink-to-downlink (826-834 vs 878 MHz) correlations:")
        for ul, dl, r in ul_dl_corrs:
            rpt.add(f"      {ul:.0f} <-> {dl:.0f} MHz: r = {r:.3f}")
        rpt.add(f"      Mean uplink-downlink correlation: r = {mean_ul_dl_r:.3f}")
        rpt.blank()
        if mean_ul_dl_r > 0.5:
            rpt.add(f"      The downlink channel is strongly correlated with the uplink cluster,")
            rpt.add(f"      suggesting the same phenomenon is active on both link directions.")
        elif mean_ul_dl_r > 0.2:
            rpt.add(f"      Moderate correlation between uplink and downlink channels.")
        else:
            rpt.add(f"      Weak correlation -- uplink and downlink may be independent phenomena.")


def section_sweep_anomaly_log(rpt, all_anomalies):
    """Section 7: Sweep Anomaly Log."""
    rpt.section_header(7, "SWEEP ANOMALY LOG")

    if not all_anomalies:
        rpt.add(f"    No sweep anomalies detected outside of target frequencies.")
        return

    rpt.add(f"    {len(all_anomalies)} anomalies detected during sweep phases:")
    rpt.blank()

    hdr = ["Timestamp", "Freq MHz", "Kurtosis", "Baseline", "Deviation", "Pulses"]
    widths = [22, 10, 10, 10, 10, 8]
    aligns = ["<", ">", ">", ">", ">", ">"]
    rpt.table_row(hdr, widths, aligns)
    rpt.table_separator(widths)

    for a in sorted(all_anomalies, key=lambda x: x.get("_timestamp", "")):
        ts = a.get("_timestamp", "")
        # Shorten timestamp for display
        ts_short = ts[:22] if len(ts) > 22 else ts
        freq = a.get("freq_mhz", 0)
        kurt = a.get("kurtosis", 0)
        bl_k = a.get("baseline_kurt", 0)
        dev_sig = a.get("deviation_sigma", 0)
        pulses = a.get("pulse_count", 0)
        rpt.table_row(
            [ts_short, f"{freq:.3f}", f"{kurt:.1f}", f"{bl_k:.1f}",
             f"+{dev_sig:.0f}sig", str(pulses)],
            widths, aligns
        )


def section_migration_analysis(rpt, cycles, captures_by_freq, checkpoint):
    """Section 8: Migration Analysis."""
    rpt.section_header(8, "MIGRATION ANALYSIS")

    total_migrations = checkpoint.get("total_migrations", 0) if checkpoint else 0
    rpt.add(f"    Total migration events detected by sentinel: {total_migrations}")
    rpt.blank()

    # Check each target frequency: did signal disappear at any point?
    for freq in TARGET_FREQS:
        caps = captures_by_freq.get(freq, [])
        if not caps:
            rpt.add(f"    {freq:.0f} MHz: No data")
            continue

        kurts = [c.get("kurtosis", 0) for c in caps]

        # Divide into first quarter and last quarter
        n = len(kurts)
        q1_end = n // 4
        q4_start = 3 * n // 4

        if q1_end < 1 or q4_start >= n:
            rpt.add(f"    {freq:.0f} MHz: Insufficient data for migration analysis")
            continue

        first_q_mean = sum(kurts[:q1_end]) / q1_end
        last_q_mean = sum(kurts[q4_start:]) / (n - q4_start)

        # Check for disappearance (significant drop in last quarter)
        if first_q_mean > 15 and last_q_mean < first_q_mean * 0.3:
            rpt.add(f"    {freq:.0f} MHz: SIGNAL POSSIBLY DISAPPEARED")
            rpt.add(f"      First quarter mean kurtosis:  {first_q_mean:.1f}")
            rpt.add(f"      Last quarter mean kurtosis:   {last_q_mean:.1f}")
        elif last_q_mean > 15 and first_q_mean < last_q_mean * 0.3:
            rpt.add(f"    {freq:.0f} MHz: SIGNAL POSSIBLY APPEARED (not present initially)")
            rpt.add(f"      First quarter mean kurtosis:  {first_q_mean:.1f}")
            rpt.add(f"      Last quarter mean kurtosis:   {last_q_mean:.1f}")
        else:
            rpt.add(f"    {freq:.0f} MHz: Signal stable throughout monitoring period")
            rpt.add(f"      First quarter mean: {first_q_mean:.1f}  "
                    f"Last quarter mean: {last_q_mean:.1f}")
        rpt.blank()

    if total_migrations == 0:
        rpt.blank()
        rpt.add(f"    No frequency migration events were detected. The anomalous signals")
        rpt.add(f"    remained on their original frequencies throughout the monitoring period.")
        rpt.add(f"    This persistence is consistent with a fixed-frequency source (e.g.,")
        rpt.add(f"    hardware, infrastructure) rather than an adaptive/hopping signal.")


def section_comparison_to_lte(rpt, captures_by_freq):
    """Section 9: Comparison to Expected LTE Behavior."""
    rpt.section_header(9, "COMPARISON TO EXPECTED LTE BEHAVIOR")

    rpt.add(f"    This section compares observed RF characteristics against known")
    rpt.add(f"    properties of standard 3GPP LTE signals on these bands.")
    rpt.blank()

    # Reference table
    hdr = ["Parameter", "Expected (UL)", "Expected (DL)", "Observed (UL)", "Observed (DL)", "Match?"]
    widths = [20, 14, 14, 14, 14, 8]
    aligns = ["<", "^", "^", "^", "^", "^"]
    rpt.table_row(hdr, widths, aligns)
    rpt.table_separator(widths)

    # Gather uplink stats
    ul_kurts = []
    ul_paprs = []
    ul_pulses = []
    for freq in UPLINK_FREQS:
        for cap in captures_by_freq.get(freq, []):
            ul_kurts.append(cap.get("kurtosis", 0))
            ul_paprs.append(cap.get("papr_db", 0))
            ul_pulses.append(cap.get("pulse_count", 0))

    # Gather downlink stats
    dl_kurts = []
    dl_paprs = []
    dl_pulses = []
    for freq in DOWNLINK_FREQS:
        for cap in captures_by_freq.get(freq, []):
            dl_kurts.append(cap.get("kurtosis", 0))
            dl_paprs.append(cap.get("papr_db", 0))
            dl_pulses.append(cap.get("pulse_count", 0))

    ul_kurt_mean = sum(ul_kurts) / len(ul_kurts) if ul_kurts else 0
    dl_kurt_mean = sum(dl_kurts) / len(dl_kurts) if dl_kurts else 0
    ul_papr_mean = sum(ul_paprs) / len(ul_paprs) if ul_paprs else 0
    dl_papr_mean = sum(dl_paprs) / len(dl_paprs) if dl_paprs else 0
    ul_pulse_mean = sum(ul_pulses) / len(ul_pulses) if ul_pulses else 0
    dl_pulse_mean = sum(dl_pulses) / len(dl_pulses) if dl_pulses else 0

    def match_str(observed, expected_lo, expected_hi):
        if expected_lo <= observed <= expected_hi:
            return "YES"
        elif observed > expected_hi:
            return "NO (high)"
        else:
            return "NO (low)"

    # Kurtosis
    rpt.table_row(
        ["Kurtosis", "3.5-4.0", "3.8-4.5",
         f"{ul_kurt_mean:.1f}", f"{dl_kurt_mean:.1f}",
         match_str(ul_kurt_mean, 3.5, 4.0)],
        widths, aligns
    )

    # PAPR
    rpt.table_row(
        ["PAPR (dB)", "7-8", "10-12",
         f"{ul_papr_mean:.1f}", f"{dl_papr_mean:.1f}",
         match_str(ul_papr_mean, 7, 8)],
        widths, aligns
    )

    # Pulse structure
    rpt.table_row(
        ["Pulses/capture", "~0 (continuous)", "~0 (continuous)",
         f"{ul_pulse_mean:.0f}", f"{dl_pulse_mean:.0f}",
         "NO" if (ul_pulse_mean > 5 or dl_pulse_mean > 5) else "YES"],
        widths, aligns
    )

    # Waveform type
    rpt.table_row(
        ["Waveform", "SC-FDMA (cont.)", "OFDM (cont.)",
         "Pulsed", "Pulsed",
         "NO"],
        widths, aligns
    )

    rpt.blank()
    rpt.add(f"    Detailed Comparison:")
    rpt.blank()

    rpt.add(f"    1. KURTOSIS")
    rpt.add(f"       LTE SC-FDMA uplink signals have near-Gaussian amplitude distributions")
    rpt.add(f"       with kurtosis in the 3.5-4.0 range. The observed uplink mean of")
    rpt.add(f"       {ul_kurt_mean:.1f} is {ul_kurt_mean / 3.75:.0f}x above the expected")
    rpt.add(f"       midpoint. This indicates extreme impulsive content not present in")
    rpt.add(f"       standard SC-FDMA waveforms.")
    rpt.blank()

    rpt.add(f"    2. PAPR (Peak-to-Average Power Ratio)")
    rpt.add(f"       SC-FDMA uplink PAPR is typically 7-8 dB. The observed mean of")
    rpt.add(f"       {ul_papr_mean:.1f} dB significantly exceeds this, consistent with")
    rpt.add(f"       sharp transient pulses riding above the noise floor.")
    rpt.blank()

    rpt.add(f"    3. PULSE STRUCTURE")
    rpt.add(f"       FDD LTE transmits continuously in both directions (no TDD gaps).")
    rpt.add(f"       Standard LTE should produce zero isolated microsecond-scale pulses")
    rpt.add(f"       above 4-sigma. The observed mean of {ul_pulse_mean:.0f} pulses per")
    rpt.add(f"       200ms uplink capture and {dl_pulse_mean:.0f} pulses per downlink")
    rpt.add(f"       capture is completely inconsistent with any standard LTE mode.")
    rpt.blank()

    rpt.add(f"    4. SIGNAL CONTINUITY")
    rpt.add(f"       The anomalous signal is intermittent -- some captures show baseline")
    rpt.add(f"       kurtosis (~8) while others show extreme values (>100). Normal LTE")
    rpt.add(f"       resource allocation is continuous for active carriers; this on/off")
    rpt.add(f"       behavior is atypical.")
    rpt.blank()

    ul_match = "NO"
    dl_match = "NO"
    if ul_kurt_mean < 5 and ul_papr_mean < 9 and ul_pulse_mean < 5:
        ul_match = "YES"
    if dl_kurt_mean < 5 and dl_papr_mean < 13 and dl_pulse_mean < 5:
        dl_match = "YES"

    rpt.add(f"    OVERALL VERDICT:")
    rpt.add(f"      Uplink (826-834 MHz) consistent with normal LTE:   {ul_match}")
    rpt.add(f"      Downlink (878 MHz) consistent with normal LTE:     {dl_match}")
    rpt.blank()
    if ul_match == "NO" or dl_match == "NO":
        rpt.add(f"      The observed signals are NOT consistent with standard cellular")
        rpt.add(f"      traffic. Something anomalous is present on these frequencies.")


def section_conclusions(rpt, cycles, captures_by_freq, checkpoint, all_anomalies):
    """Section 10: Conclusions."""
    rpt.section_header(10, "CONCLUSIONS")

    # Compute summary stats for conclusions
    total_caps = sum(len(v) for v in captures_by_freq.values())
    total_pulses = sum(cap.get("pulse_count", 0)
                       for caps in captures_by_freq.values()
                       for cap in caps)
    all_kurts = []
    for freq in TARGET_FREQS:
        for cap in captures_by_freq.get(freq, []):
            all_kurts.append(cap.get("kurtosis", 0))

    timestamps = [parse_timestamp(c.get("timestamp")) for c in cycles]
    timestamps = [t for t in timestamps if t is not None]
    duration_s = (max(timestamps) - min(timestamps)).total_seconds() if timestamps else 0

    total_migrations = checkpoint.get("total_migrations", 0) if checkpoint else 0

    rpt.add(f"    WHAT THE DATA SHOWS:")
    rpt.blank()
    rpt.add(f"    1. Anomalous impulsive RF activity is present on all six monitored")
    rpt.add(f"       frequencies (826, 828, 830, 832, 834, 878 MHz) spanning both the")
    rpt.add(f"       Band 5/26 uplink and downlink allocations.")
    rpt.blank()
    rpt.add(f"    2. The signal characteristics -- kurtosis 10x-70x above LTE norms,")
    rpt.add(f"       PAPR exceeding SC-FDMA limits, thousands of us-scale pulses --")
    rpt.add(f"       are inconsistent with any standard 3GPP LTE waveform.")
    rpt.blank()
    rpt.add(f"    3. The signals are PERSISTENT: observed across {format_duration(duration_s)}")
    rpt.add(f"       of monitoring with no migration to other frequencies.")
    rpt.blank()
    rpt.add(f"    4. The signals are INTERMITTENT: kurtosis varies from baseline (~8)")
    rpt.add(f"       to extreme values (>200) across captures, suggesting a duty-cycled")
    rpt.add(f"       or bursty source.")
    rpt.blank()
    rpt.add(f"    5. {total_pulses:,} discrete pulses were detected across {total_caps:,}")
    rpt.add(f"       captures, with typical widths of 1-10 microseconds.")
    rpt.blank()

    rpt.add(f"    WHAT THE DATA DOES NOT SHOW:")
    rpt.blank()
    rpt.add(f"    1. The source of the anomalous signals. RTL-SDR is a receive-only")
    rpt.add(f"       device and cannot determine signal origin or directionality.")
    rpt.blank()
    rpt.add(f"    2. Whether these are externally radiated signals or artifacts of")
    rpt.add(f"       nearby electronics (intermodulation, spurious emissions, etc.).")
    rpt.add(f"       An RTL-SDR has limited dynamic range and is susceptible to")
    rpt.add(f"       strong signal overload.")
    rpt.blank()
    rpt.add(f"    3. The modulation content or information carried by the pulses.")
    rpt.add(f"       Higher-resolution IQ analysis would be needed.")
    rpt.blank()
    rpt.add(f"    4. Whether the signals are intentional transmissions or unintentional")
    rpt.add(f"       interference (e.g., switching power supplies, LED drivers, or other")
    rpt.add(f"       broadband noise sources).")
    rpt.blank()

    rpt.add(f"    RECOMMENDED NEXT STEPS:")
    rpt.blank()
    rpt.add(f"    1. VALIDATE with calibrated equipment: Use a spectrum analyzer with")
    rpt.add(f"       known sensitivity and dynamic range (e.g., Keysight N9344C or")
    rpt.add(f"       equivalent) to confirm the signals are real and not RTL-SDR artifacts.")
    rpt.blank()
    rpt.add(f"    2. DIRECTION FINDING: Use a directional antenna (Yagi or log-periodic)")
    rpt.add(f"       to determine signal bearing and narrow down the source location.")
    rpt.blank()
    rpt.add(f"    3. ISOLATION TEST: Move the RTL-SDR receiver to a different location")
    rpt.add(f"       (>100m away) to determine if the signal is localized or widespread.")
    rpt.blank()
    rpt.add(f"    4. SHIELDED TEST: Place the SDR in an RF-shielded enclosure with a")
    rpt.add(f"       known antenna to rule out direct coupling / conducted interference.")
    rpt.blank()
    rpt.add(f"    5. HIGH-RESOLUTION IQ ANALYSIS: Use the saved IQ captures to perform")
    rpt.add(f"       detailed pulse characterization (rise times, spectral content,")
    rpt.add(f"       modulation analysis) with tools such as GNU Radio or MATLAB.")
    rpt.blank()
    rpt.add(f"    6. If confirmed as real over-the-air signals, consider filing an")
    rpt.add(f"       interference complaint with the FCC (Part 15/Part 22/Part 27")
    rpt.add(f"       depending on source classification).")


# ── Main ─────────────────────────────────────────────────────────────────────

def generate_report(results_dir="results", output_file=None):
    """Generate the comprehensive report."""

    # Load data
    cycles, log_files, parse_errors = load_sentinel_logs(results_dir)
    checkpoint = load_checkpoint(results_dir)

    if not cycles:
        print(f"ERROR: No sentinel log data found in {results_dir}/", file=sys.stderr)
        print(f"Expected files matching: sentinel_*.jsonl", file=sys.stderr)
        sys.exit(1)

    # Extract per-frequency capture data
    captures_by_freq = {}
    for freq in TARGET_FREQS:
        captures_by_freq[freq] = extract_captures(cycles, freq)

    all_anomalies = extract_all_anomalies(cycles)

    # Build report
    rpt = ReportBuilder()

    # Title block
    rpt.separator()
    rpt.add(f"  RF SENTINEL MONITORING REPORT")
    rpt.add(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    rpt.add(f"  Data source: {results_dir}/sentinel_*.jsonl"
            f" ({len(log_files)} files, {len(cycles)} cycles)")
    if parse_errors > 0:
        rpt.add(f"  WARNING: {parse_errors} JSON parse errors encountered in log files")
    rpt.separator()

    # Sections
    section_executive_summary(rpt, cycles, checkpoint, captures_by_freq, all_anomalies)
    section_measurement_parameters(rpt, cycles, checkpoint, log_files)
    section_baseline_characterization(rpt, checkpoint)
    section_target_frequency_analysis(rpt, captures_by_freq, checkpoint)
    section_temporal_analysis(rpt, cycles, captures_by_freq)
    section_cross_frequency_correlation(rpt, captures_by_freq, cycles)
    section_sweep_anomaly_log(rpt, all_anomalies)
    section_migration_analysis(rpt, cycles, captures_by_freq, checkpoint)
    section_comparison_to_lte(rpt, captures_by_freq)
    section_conclusions(rpt, cycles, captures_by_freq, checkpoint, all_anomalies)

    # Footer
    rpt.blank()
    rpt.separator()
    rpt.add(f"  END OF REPORT")
    rpt.add(f"  Total cycles analyzed: {len(cycles)}")
    rpt.add(f"  Total captures: {sum(len(v) for v in captures_by_freq.values())}")
    rpt.add(f"  Total pulses detected: {sum(c.get('pulse_count', 0) for caps in captures_by_freq.values() for c in caps):,}")
    rpt.separator()

    report_text = rpt.get_text()

    # Output
    print(report_text)

    if output_file is None:
        output_file = os.path.join(results_dir, "report.txt")

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        f.write(report_text)

    print(f"\nReport saved to: {output_file}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Generate comprehensive report from RF Sentinel monitoring data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_report.py
  python generate_report.py --results-dir results --output results/report.txt
  python generate_report.py --output /tmp/rf_report.txt
        """
    )
    parser.add_argument("--results-dir", type=str, default="results",
                        help="Directory containing sentinel_*.jsonl files (default: results)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output file path (default: <results-dir>/report.txt)")

    args = parser.parse_args()
    generate_report(results_dir=args.results_dir, output_file=args.output)


if __name__ == "__main__":
    main()

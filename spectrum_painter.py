#!/usr/bin/env python3
"""
Spectrum Painter — Waterfall spectrogram + pulse structure analysis of IQ captures.

Generates:
  1. Waterfall spectrogram (time vs frequency vs power)
  2. Pulse envelope with detected pulses annotated
  3. Instantaneous frequency during pulses (modulation fingerprint)
  4. Pulse statistics summary (PRF, duty cycle, bandwidth)

Usage:
  python spectrum_painter.py captures/sentinel_826MHz_014542.iq
  python spectrum_painter.py --freq 826 --all          # all captures for a freq
  python spectrum_painter.py --freq 826 --top 10       # top 10 by kurtosis
  python spectrum_painter.py --batch                   # top captures per freq
"""

import os
import sys
import json
import argparse
import numpy as np
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from scipy import signal as sp_signal
from scipy import stats as sp_stats

SAMPLE_RATE = 2_400_000
SETTLE_SAMPLES = 48_000
DC_NOTCH_BINS = 32
CAPTURES_DIR = os.environ.get("IQ_DUMP_DIR", "captures")
OUTPUT_DIR = "results/spectrograms"

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


def load_iq(filepath):
    """Load RTL-SDR IQ capture, strip settle time, DC notch."""
    raw = np.fromfile(filepath, dtype=np.uint8)
    iq = (raw.astype(np.float32) - 127.5) / 127.5
    z = iq[0::2] + 1j * iq[1::2]
    z = z[SETTLE_SAMPLES:]

    # DC notch
    Z = np.fft.fft(z)
    h = DC_NOTCH_BINS // 2
    Z[:h] = 0
    Z[-h:] = 0
    z = np.fft.ifft(Z)
    return z


def extract_freq_from_name(filename):
    """Extract center frequency from filename like sentinel_826MHz_014542.iq"""
    name = Path(filename).stem
    for part in name.split("_"):
        if "MHz" in part:
            return float(part.replace("MHz", ""))
    return 0


def detect_pulses(amp, threshold_sigma=4):
    """Detect pulses above threshold, return list of (start, end, peak_amp)."""
    mu = np.mean(amp)
    sigma = np.std(amp)
    thresh = mu + threshold_sigma * sigma

    above = (amp > thresh).astype(np.int8)
    diffs = np.diff(np.concatenate(([0], above, [0])))
    starts = np.where(diffs == 1)[0]
    ends = np.where(diffs == -1)[0]

    pulses = []
    for s, e in zip(starts, ends):
        if e - s >= 3:  # min 3 samples
            pk = float(np.max(amp[s:e]))
            pulses.append((s, e, pk))
    return pulses, thresh


def compute_inst_freq(z, pulses):
    """Compute instantaneous frequency during each pulse."""
    phase = np.unwrap(np.angle(z))
    inst_freq = np.diff(phase) / (2 * np.pi) * SAMPLE_RATE

    pulse_freqs = []
    for s, e, _ in pulses:
        if e - s > 2:
            pf = inst_freq[s:e-1]
            pulse_freqs.append({
                "start": s,
                "end": e,
                "mean_freq_hz": float(np.mean(pf)),
                "std_freq_hz": float(np.std(pf)),
                "min_freq_hz": float(np.min(pf)),
                "max_freq_hz": float(np.max(pf)),
                "bandwidth_hz": float(np.max(pf) - np.min(pf)),
                "samples": pf,
            })
    return pulse_freqs


def paint(iq_path, output_path=None):
    """Generate full spectrogram analysis for one IQ file."""
    z = load_iq(iq_path)
    amp = np.abs(z)
    freq_mhz = extract_freq_from_name(iq_path)
    basename = Path(iq_path).stem
    n_samples = len(z)
    duration_ms = n_samples / SAMPLE_RATE * 1000

    if output_path is None:
        output_path = f"{OUTPUT_DIR}/{basename}_spectrogram.png"

    # Detect pulses
    pulses, thresh = detect_pulses(amp)
    pulse_freqs = compute_inst_freq(z, pulses)

    # Stats
    kurt = float(sp_stats.kurtosis(amp, fisher=False))
    papr = float(10 * np.log10(np.max(amp**2) / np.mean(amp**2))) if np.mean(amp**2) > 0 else 0

    # PRF estimate
    if len(pulses) >= 2:
        centers = [(s + e) / 2 for s, e, _ in pulses]
        intervals = np.diff(centers) / SAMPLE_RATE
        prf_hz = 1.0 / np.median(intervals) if np.median(intervals) > 0 else 0
        duty_cycle = sum(e - s for s, e, _ in pulses) / n_samples
    else:
        prf_hz = 0
        duty_cycle = 0

    # ── Figure: 4 panels ──
    fig = plt.figure(figsize=(16, 14))
    fig.suptitle(f"ARTEMIS Spectrum Analysis — {freq_mhz:.0f} MHz\n"
                 f"{basename}  |  kurt={kurt:.1f}  PAPR={papr:.1f}dB  "
                 f"pulses={len(pulses)}  PRF≈{prf_hz:.0f}Hz",
                 fontsize=13, fontweight="bold")
    gs = GridSpec(4, 1, height_ratios=[2, 1.2, 1.2, 0.8], hspace=0.35)

    time_ms = np.arange(n_samples) / SAMPLE_RATE * 1000

    # Panel 1: Waterfall spectrogram
    ax1 = fig.add_subplot(gs[0])
    nfft = 1024
    noverlap = 768
    Pxx, freqs, bins, im = ax1.specgram(
        z, NFFT=nfft, Fs=SAMPLE_RATE/1e6, noverlap=noverlap,
        cmap="inferno", scale="dB",
        Fc=freq_mhz if freq_mhz else 0
    )
    ax1.set_ylabel("Frequency (MHz)")
    ax1.set_xlabel("Time (s)")
    ax1.set_title("Waterfall Spectrogram")
    plt.colorbar(im, ax=ax1, label="Power (dB)")

    # Panel 2: Pulse envelope
    ax2 = fig.add_subplot(gs[1])
    # Downsample for plotting if too many samples
    if n_samples > 50000:
        step = n_samples // 50000
        ax2.plot(time_ms[::step], amp[::step], linewidth=0.3, color="steelblue", alpha=0.8)
    else:
        ax2.plot(time_ms, amp, linewidth=0.3, color="steelblue", alpha=0.8)
    ax2.axhline(thresh, color="red", linestyle="--", linewidth=0.8, label=f"4σ thresh={thresh:.4f}")
    ax2.axhline(np.mean(amp), color="orange", linestyle=":", linewidth=0.8, label=f"mean={np.mean(amp):.4f}")

    # Annotate pulses
    for i, (s, e, pk) in enumerate(pulses[:30]):
        t_start = s / SAMPLE_RATE * 1000
        t_end = e / SAMPLE_RATE * 1000
        width_us = (e - s) / SAMPLE_RATE * 1e6
        ax2.axvspan(t_start, t_end, alpha=0.3, color="red")
        if i < 15:
            ax2.annotate(f"{width_us:.1f}μs", (t_start, pk),
                        fontsize=6, color="red", rotation=45)

    ax2.set_ylabel("Amplitude")
    ax2.set_xlabel("Time (ms)")
    ax2.set_title(f"Pulse Envelope — {len(pulses)} pulses detected (4σ threshold)")
    ax2.legend(fontsize=8, loc="upper right")

    # Panel 3: Instantaneous frequency during pulses
    ax3 = fig.add_subplot(gs[2])
    if pulse_freqs:
        colors = plt.cm.tab10(np.linspace(0, 1, min(len(pulse_freqs), 10)))
        for i, pf in enumerate(pulse_freqs[:20]):
            t = np.arange(pf["start"], pf["end"]-1) / SAMPLE_RATE * 1000
            ax3.plot(t, pf["samples"] / 1e3, linewidth=0.8,
                    color=colors[i % len(colors)],
                    label=f"P{i}: BW={pf['bandwidth_hz']/1e3:.1f}kHz" if i < 8 else None)
        ax3.set_ylabel("Inst. Frequency (kHz)")
        ax3.set_xlabel("Time (ms)")
        ax3.set_title("Instantaneous Frequency During Pulses (modulation fingerprint)")
        if len(pulse_freqs) <= 8:
            ax3.legend(fontsize=7, loc="upper right")
    else:
        ax3.text(0.5, 0.5, "No pulses detected", transform=ax3.transAxes,
                ha="center", va="center", fontsize=14, color="gray")
        ax3.set_title("Instantaneous Frequency During Pulses")

    # Panel 4: Pulse width histogram + stats text
    ax4 = fig.add_subplot(gs[3])
    if pulses:
        widths_us = [(e - s) / SAMPLE_RATE * 1e6 for s, e, _ in pulses]
        ax4.hist(widths_us, bins=min(50, len(widths_us)), color="steelblue",
                edgecolor="navy", alpha=0.8)
        ax4.set_xlabel("Pulse Width (μs)")
        ax4.set_ylabel("Count")

        stats_text = (
            f"Pulses: {len(pulses)}  |  "
            f"Width: {np.mean(widths_us):.1f} ± {np.std(widths_us):.1f} μs  |  "
            f"PRF: {prf_hz:.0f} Hz  |  "
            f"Duty: {duty_cycle*100:.2f}%  |  "
            f"Kurtosis: {kurt:.1f}  |  "
            f"PAPR: {papr:.1f} dB"
        )
        if pulse_freqs:
            bws = [pf["bandwidth_hz"] for pf in pulse_freqs]
            stats_text += f"  |  BW: {np.mean(bws)/1e3:.1f} ± {np.std(bws)/1e3:.1f} kHz"

        ax4.set_title(stats_text, fontsize=9)
    else:
        ax4.text(0.5, 0.5, "No pulses — clean noise floor", transform=ax4.transAxes,
                ha="center", va="center", fontsize=14, color="gray")

    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

    # Save JSON summary
    summary = {
        "file": str(iq_path),
        "freq_mhz": freq_mhz,
        "n_samples": n_samples,
        "duration_ms": round(duration_ms, 2),
        "kurtosis": round(kurt, 3),
        "papr_db": round(papr, 2),
        "pulse_count": len(pulses),
        "prf_hz": round(prf_hz, 1),
        "duty_cycle": round(duty_cycle, 6),
        "threshold": round(float(thresh), 6),
        "pulse_widths_us": [round((e-s)/SAMPLE_RATE*1e6, 2) for s, e, _ in pulses],
        "pulse_bandwidths_khz": [round(pf["bandwidth_hz"]/1e3, 2) for pf in pulse_freqs],
        "spectrogram": str(output_path),
    }
    json_path = output_path.replace(".png", ".json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"  {basename}: kurt={kurt:.1f} pulses={len(pulses)} "
          f"PRF={prf_hz:.0f}Hz duty={duty_cycle*100:.2f}% → {output_path}")
    return summary


def get_captures_for_freq(freq_mhz, top_n=None):
    """Get IQ capture paths for a frequency, optionally sorted by kurtosis."""
    pattern = f"*{int(freq_mhz)}MHz*.iq"
    files = sorted(Path(CAPTURES_DIR).glob(pattern))

    if top_n and top_n < len(files):
        # Quick kurtosis scan to find the most interesting captures
        print(f"  Scanning {len(files)} captures for top {top_n} by kurtosis...")
        scored = []
        for f in files:
            z = load_iq(str(f))
            k = float(sp_stats.kurtosis(np.abs(z), fisher=False))
            scored.append((k, f))
        scored.sort(reverse=True)
        files = [f for _, f in scored[:top_n]]
        print(f"  Selected: kurtosis range {scored[0][0]:.1f} — {scored[top_n-1][0]:.1f}")

    return [str(f) for f in files]


def main():
    parser = argparse.ArgumentParser(
        description="ARTEMIS Spectrum Painter — IQ waterfall analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("iq_file", nargs="?", help="Single IQ file to analyze")
    parser.add_argument("--freq", type=float, help="Analyze all captures for this freq (MHz)")
    parser.add_argument("--top", type=int, help="Only top N captures by kurtosis")
    parser.add_argument("--all", action="store_true", help="Process all captures for --freq")
    parser.add_argument("--batch", action="store_true",
                        help="Top 5 captures per target frequency")

    args = parser.parse_args()

    if args.iq_file:
        paint(args.iq_file)
    elif args.freq:
        files = get_captures_for_freq(args.freq, top_n=args.top)
        print(f"\nProcessing {len(files)} captures at {args.freq:.0f} MHz...")
        for f in files:
            paint(f)
    elif args.batch:
        targets = [826, 828, 830, 832, 834, 878]
        for freq in targets:
            files = get_captures_for_freq(freq, top_n=5)
            if files:
                print(f"\n{'='*60}")
                print(f"  {freq} MHz — top 5 captures")
                print(f"{'='*60}")
                for f in files:
                    paint(f)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

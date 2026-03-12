#!/usr/bin/env python3
"""
RF Pulse Monitor — Long-duration pulse timing logger + cross-band correlator.

Two modes:
  watch:      Monitor a single frequency, log every pulse with precise timing.
              Run for hours, look for patterns in the pulse train.

  correlate:  Rapidly alternate between two frequencies, check if pulses
              on uplink and downlink coincide in time. RTL-SDR can only
              tune one freq at a time, so we interleave captures.
"""

import subprocess
import sys
import json
import signal
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats as sp_stats

SAMPLE_RATE = 2_400_000
SETTLE_SAMPLES = 48_000       # 20ms settle
DC_NOTCH_BINS = 32
MIN_PULSE_SAMPLES = 3
RESULTS_DIR = "results"
IQ_DUMP_DIR = "captures"

Path(RESULTS_DIR).mkdir(exist_ok=True)
Path(IQ_DUMP_DIR).mkdir(exist_ok=True)

_stop = False


def capture_iq(freq_hz, num_samples, gain, sample_rate=SAMPLE_RATE):
    """Capture raw IQ, return complex array or None."""
    total = num_samples + SETTLE_SAMPLES
    nbytes = total * 2
    cmd = ["rtl_sdr", "-f", str(int(freq_hz)), "-s", str(sample_rate),
           "-g", str(gain), "-n", str(nbytes), "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=15)
        if len(r.stdout) < nbytes:
            return None
        raw = r.stdout[:nbytes]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    iq = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
    iq = (iq - 127.5) / 127.5
    z = iq[0::2] + 1j * iq[1::2]
    z = z[SETTLE_SAMPLES:]

    # DC notch
    Z = np.fft.fft(z)
    h = DC_NOTCH_BINS // 2
    Z[:h] = 0
    Z[-h:] = 0
    z = np.fft.ifft(Z)

    return z, raw


def find_pulses(iq, sample_rate=SAMPLE_RATE, min_samples=MIN_PULSE_SAMPLES,
                sigma_thresh=4.0):
    """Find pulses in IQ capture. Returns list of pulse dicts."""
    amp = np.abs(iq)
    mu = np.mean(amp)
    sigma = np.std(amp)
    thresh = mu + sigma_thresh * sigma

    above = (amp > thresh).astype(np.int8)
    if not np.any(above):
        return [], float(sp_stats.kurtosis(amp, fisher=False)), mu, sigma

    diffs = np.diff(np.concatenate(([0], above, [0])))
    starts = np.where(diffs == 1)[0]
    ends = np.where(diffs == -1)[0]

    pulses = []
    for s, e in zip(starts, ends):
        width = e - s
        if width >= min_samples:
            peak_amp = float(np.max(amp[s:e]))
            peak_snr = round(20 * np.log10(peak_amp / mu), 1) if mu > 0 else 0
            energy = float(np.sum(amp[s:e] ** 2))
            pulses.append({
                "start_sample": int(s),
                "offset_us": round(s / sample_rate * 1e6, 1),
                "width_samples": int(width),
                "width_us": round(width / sample_rate * 1e6, 2),
                "peak_snr_db": peak_snr,
                "energy": round(energy, 4),
            })

    kurt = float(sp_stats.kurtosis(amp, fisher=False))
    return pulses, kurt, float(mu), float(sigma)


# ── Watch mode ──────────────────────────────────────────────────────────────

def watch(freq_mhz, duration_s, gain, dwell_ms):
    freq_hz = int(freq_mhz * 1e6)
    num_samples = int(SAMPLE_RATE * dwell_ms / 1000)
    n_captures = int(duration_s * 1000 / dwell_ms)

    ts_start = datetime.now()
    log_file = f"{RESULTS_DIR}/watch_{freq_mhz:.0f}MHz_{ts_start.strftime('%Y%m%d_%H%M%S')}.jsonl"

    print(f"\n{'='*72}")
    print(f"  PULSE WATCH — {freq_mhz:.3f} MHz")
    print(f"  Duration: {duration_s}s  |  Dwell: {dwell_ms}ms  |  Gain: {gain}dB")
    print(f"  Captures: {n_captures}  |  Log: {log_file}")
    print(f"  Started: {ts_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*72}\n")

    # Build baseline from first 10 captures
    baseline_kurts = []
    total_pulses = 0
    capture_times = []
    pulse_timeline = []  # (wall_time_s, pulse_offset_us, width_us, snr)

    for i in range(n_captures):
        if _stop:
            break

        wall_time = time.time()
        elapsed = wall_time - ts_start.timestamp()
        result = capture_iq(freq_hz, num_samples, gain)
        if result is None:
            continue
        iq, raw = result

        pulses, kurt, mu, sigma = find_pulses(iq)
        ts_now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        entry = {
            "capture": i,
            "wall_time": wall_time,
            "elapsed_s": round(elapsed, 2),
            "kurtosis": round(kurt, 3),
            "mean_amp": round(mu, 6),
            "std_amp": round(sigma, 6),
            "pulse_count": len(pulses),
            "pulses": pulses,
        }

        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Track for summary
        baseline_kurts.append(kurt)
        total_pulses += len(pulses)
        capture_times.append(elapsed)
        for p in pulses:
            # absolute time of pulse = capture wall time + pulse offset
            abs_time_us = elapsed * 1e6 + p["offset_us"]
            pulse_timeline.append((abs_time_us, p["width_us"], p["peak_snr_db"]))

        # Display
        if len(pulses) > 0:
            widths = [p["width_us"] for p in pulses]
            snrs = [p["peak_snr_db"] for p in pulses]
            print(f"  {ts_now}  [{elapsed:7.1f}s]  "
                  f"kurt={kurt:8.2f}  pulses={len(pulses):4d}  "
                  f"width={min(widths):.1f}–{max(widths):.1f}µs  "
                  f"snr={min(snrs):.0f}–{max(snrs):.0f}dB")

            # Save IQ for first occurrence or very high kurtosis
            if total_pulses == len(pulses) or kurt > 50:
                iq_file = f"{IQ_DUMP_DIR}/watch_{freq_mhz:.0f}MHz_{i}.iq"
                with open(iq_file, "wb") as f:
                    f.write(raw)
        else:
            if i % 20 == 0:  # periodic heartbeat even when quiet
                print(f"  {ts_now}  [{elapsed:7.1f}s]  "
                      f"kurt={kurt:8.2f}  pulses=   0  (quiet)")

    # ── Summary ──
    elapsed_total = time.time() - ts_start.timestamp()
    print(f"\n{'='*72}")
    print(f"  WATCH COMPLETE — {freq_mhz:.3f} MHz — {elapsed_total:.0f}s")
    print(f"{'='*72}")

    if baseline_kurts:
        kurts = np.array(baseline_kurts)
        print(f"\n  Kurtosis:  min={kurts.min():.2f}  max={kurts.max():.2f}  "
              f"mean={kurts.mean():.2f}  std={kurts.std():.2f}")
        print(f"  Total pulses: {total_pulses} across {len(baseline_kurts)} captures")

        if pulse_timeline:
            # Look for periodicity in pulse timing
            times_us = np.array([p[0] for p in pulse_timeline])
            if len(times_us) > 2:
                intervals = np.diff(times_us)
                intervals_ms = intervals / 1000
                print(f"\n  Pulse interval stats:")
                print(f"    min={intervals_ms.min():.3f}ms  "
                      f"max={intervals_ms.max():.1f}ms  "
                      f"mean={intervals_ms.mean():.3f}ms  "
                      f"median={np.median(intervals_ms):.3f}ms")

                # Check for periodic repetition
                # Use autocorrelation of pulse occurrence times
                if len(times_us) > 20:
                    # Histogram of intervals to find peaks
                    hist, edges = np.histogram(intervals_ms, bins=100)
                    peak_bin = np.argmax(hist)
                    peak_interval = (edges[peak_bin] + edges[peak_bin + 1]) / 2
                    print(f"    Most common interval: ~{peak_interval:.2f}ms "
                          f"({hist[peak_bin]} occurrences)")

                    # Check for harmonic structure
                    if peak_interval > 0:
                        expected_2nd = peak_interval * 2
                        expected_3rd = peak_interval * 3
                        near_2nd = np.sum(np.abs(intervals_ms - expected_2nd) < peak_interval * 0.1)
                        near_3rd = np.sum(np.abs(intervals_ms - expected_3rd) < peak_interval * 0.1)
                        if near_2nd > 5 or near_3rd > 5:
                            print(f"    Harmonic structure detected: "
                                  f"2x={near_2nd} hits, 3x={near_3rd} hits")

    print(f"\n  Full log: {log_file}")
    print()


# ── Correlate mode ──────────────────────────────────────────────────────────

def correlate(freq_a_mhz, freq_b_mhz, duration_s, gain, dwell_ms):
    """Rapidly alternate between two frequencies, look for coincident pulses."""
    freq_a_hz = int(freq_a_mhz * 1e6)
    freq_b_hz = int(freq_b_mhz * 1e6)
    num_samples = int(SAMPLE_RATE * dwell_ms / 1000)
    n_pairs = int(duration_s * 1000 / (dwell_ms * 2))  # each pair = 2 captures

    ts_start = datetime.now()
    log_file = (f"{RESULTS_DIR}/correlate_{freq_a_mhz:.0f}_{freq_b_mhz:.0f}MHz"
                f"_{ts_start.strftime('%Y%m%d_%H%M%S')}.jsonl")

    print(f"\n{'='*72}")
    print(f"  CROSS-BAND CORRELATOR")
    print(f"  Freq A: {freq_a_mhz:.3f} MHz  |  Freq B: {freq_b_mhz:.3f} MHz")
    print(f"  Duration: {duration_s}s  |  Dwell: {dwell_ms}ms each  |  Gain: {gain}dB")
    print(f"  Pairs: {n_pairs}  |  Log: {log_file}")
    print(f"{'='*72}\n")

    a_pulse_counts = []
    b_pulse_counts = []
    both_active = 0
    a_only = 0
    b_only = 0
    neither = 0

    for i in range(n_pairs):
        if _stop:
            break

        wall_time = time.time()
        elapsed = wall_time - ts_start.timestamp()

        # Capture A
        result_a = capture_iq(freq_a_hz, num_samples, gain)
        # Capture B immediately after
        result_b = capture_iq(freq_b_hz, num_samples, gain)

        if result_a is None or result_b is None:
            continue

        iq_a, _ = result_a
        iq_b, _ = result_b

        pulses_a, kurt_a, _, _ = find_pulses(iq_a)
        pulses_b, kurt_b, _, _ = find_pulses(iq_b)

        has_a = len(pulses_a) > 0
        has_b = len(pulses_b) > 0

        a_pulse_counts.append(len(pulses_a))
        b_pulse_counts.append(len(pulses_b))

        if has_a and has_b:
            both_active += 1
        elif has_a:
            a_only += 1
        elif has_b:
            b_only += 1
        else:
            neither += 1

        entry = {
            "pair": i,
            "elapsed_s": round(elapsed, 2),
            "freq_a_mhz": freq_a_mhz,
            "freq_b_mhz": freq_b_mhz,
            "kurt_a": round(kurt_a, 3),
            "kurt_b": round(kurt_b, 3),
            "pulses_a": len(pulses_a),
            "pulses_b": len(pulses_b),
            "coincident": has_a and has_b,
            "pulse_details_a": pulses_a[:10],
            "pulse_details_b": pulses_b[:10],
        }

        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        ts_now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        marker = "***BOTH***" if (has_a and has_b) else ""
        print(f"  {ts_now}  [{elapsed:6.1f}s]  "
              f"A:{len(pulses_a):3d} pulses (k={kurt_a:.1f})  "
              f"B:{len(pulses_b):3d} pulses (k={kurt_b:.1f})  {marker}")

    # ── Summary ──
    total = both_active + a_only + b_only + neither
    print(f"\n{'='*72}")
    print(f"  CORRELATOR RESULTS — {total} capture pairs")
    print(f"{'='*72}")

    if total > 0:
        print(f"\n  Coincidence table:")
        print(f"    Both have pulses:  {both_active:4d}  ({both_active/total*100:.1f}%)")
        print(f"    Only A ({freq_a_mhz:.0f} MHz):  {a_only:4d}  ({a_only/total*100:.1f}%)")
        print(f"    Only B ({freq_b_mhz:.0f} MHz):  {b_only:4d}  ({b_only/total*100:.1f}%)")
        print(f"    Neither:           {neither:4d}  ({neither/total*100:.1f}%)")

        # Statistical test for independence
        # If pulses on A and B are independent, P(both) ≈ P(A) × P(B)
        p_a = (both_active + a_only) / total
        p_b = (both_active + b_only) / total
        expected_both = p_a * p_b * total
        print(f"\n  Independence test:")
        print(f"    P(A has pulses) = {p_a:.3f}")
        print(f"    P(B has pulses) = {p_b:.3f}")
        print(f"    Expected coincident (if independent): {expected_both:.1f}")
        print(f"    Observed coincident:                  {both_active}")

        if expected_both > 0:
            ratio = both_active / expected_both
            print(f"    Ratio observed/expected: {ratio:.2f}x")
            if ratio > 2.0:
                print(f"    >>> SIGNALS APPEAR CORRELATED (ratio > 2x)")
            elif ratio > 1.5:
                print(f"    >>> POSSIBLE CORRELATION (ratio > 1.5x)")
            else:
                print(f"    >>> Consistent with independence")

        # Correlation coefficient on pulse counts
        if len(a_pulse_counts) > 5:
            corr = np.corrcoef(a_pulse_counts, b_pulse_counts)[0, 1]
            print(f"\n  Pulse count correlation (Pearson r): {corr:.3f}")
            if abs(corr) > 0.5:
                print(f"    >>> NOTABLE CORRELATION between A and B pulse activity")

    print(f"\n  Full log: {log_file}")
    print()


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="RF Pulse Monitor — long-duration timing + cross-band correlation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Watch 878 MHz for 1 hour
  python pulse_monitor.py watch --freq 878 --duration 3600

  # Correlate uplink (828) vs downlink (878) for 10 minutes
  python pulse_monitor.py correlate --freq-a 828 --freq-b 878 --duration 600

  # Watch with shorter dwell for finer time resolution
  python pulse_monitor.py watch --freq 878 --dwell 100 --duration 300
        """
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_watch = sub.add_parser("watch", help="Monitor single freq, log all pulses")
    p_watch.add_argument("--freq", type=float, required=True, help="Frequency MHz")
    p_watch.add_argument("--duration", type=int, default=300, help="Duration seconds (default: 300)")
    p_watch.add_argument("--gain", type=float, default=28.0, help="Gain dB (default: 28)")
    p_watch.add_argument("--dwell", type=int, default=250, help="Dwell ms (default: 250)")

    p_corr = sub.add_parser("correlate", help="Cross-band correlation")
    p_corr.add_argument("--freq-a", type=float, required=True, help="First frequency MHz")
    p_corr.add_argument("--freq-b", type=float, required=True, help="Second frequency MHz")
    p_corr.add_argument("--duration", type=int, default=300, help="Duration seconds (default: 300)")
    p_corr.add_argument("--gain", type=float, default=28.0, help="Gain dB (default: 28)")
    p_corr.add_argument("--dwell", type=int, default=200, help="Dwell ms per freq (default: 200)")

    args = parser.parse_args()

    global _stop
    signal.signal(signal.SIGINT, lambda s, f: (
        print("\n  [Ctrl-C] Stopping..."), setattr(sys.modules[__name__], '_stop', True)
    ))

    if args.command == "watch":
        watch(args.freq, args.duration, args.gain, args.dwell)
    elif args.command == "correlate":
        correlate(args.freq_a, args.freq_b, args.duration, args.gain, args.dwell)


if __name__ == "__main__":
    main()

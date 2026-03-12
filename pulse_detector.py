#!/usr/bin/env python3
"""
RF Pulse Detector v2 — Calibrated statistical analysis for finding short RF pulses.

Two-pass approach:
  Pass 1 (calibrate): Quick sweep to establish per-band baseline kurtosis/PAPR
  Pass 2 (detect):    Flag channels that deviate significantly from baseline

Handles RTL-SDR artifacts:
  - 8-bit ADC quantization noise (non-Gaussian baseline kurtosis ~10.5)
  - DC spike at center frequency (notched out)
  - PLL settling transient (first N ms of each capture discarded)
  - Single-sample ADC spikes (minimum pulse width filter)
"""

import subprocess
import sys
import os
import json
import signal
import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats as sp_stats
from scipy.signal import welch

# ── Defaults ────────────────────────────────────────────────────────────────

SAMPLE_RATE = 2_400_000           # 2.4 MSPS
DWELL_MS = 250                    # ms per frequency step
SETTLE_MS = 20                    # ms to discard after retune (PLL settling)
GAIN = 28.0                      # dB — moderate, avoids clipping
FREQ_START = 400_000_000          # 400 MHz
FREQ_STOP = 1_766_000_000        # 1766 MHz (R828D limit)
FREQ_STEP = 2_000_000            # 2 MHz steps (≈ sample BW)
DC_NOTCH_BINS = 32               # bins around DC to zero in FFT
MIN_PULSE_SAMPLES = 3            # minimum consecutive samples for a "pulse" (~1.25 µs)
OUTLIER_SIGMA = 3.5              # flag if kurtosis > median + N * MAD-based sigma
PAPR_OUTLIER_SIGMA = 3.5         # same for PAPR
IQ_DUMP_DIR = "captures"
RESULTS_DIR = "results"
LOG_FILE = "pulse_scan.jsonl"


class PulseDetector:
    def __init__(self, sample_rate=SAMPLE_RATE, gain=GAIN, dwell_ms=DWELL_MS,
                 settle_ms=SETTLE_MS, outlier_sigma=OUTLIER_SIGMA,
                 min_pulse_samples=MIN_PULSE_SAMPLES,
                 save_iq=True, device_index=0):
        self.sample_rate = sample_rate
        self.gain = gain
        self.dwell_ms = dwell_ms
        self.settle_ms = settle_ms
        self.outlier_sigma = outlier_sigma
        self.min_pulse_samples = min_pulse_samples
        self.save_iq = save_iq
        self.device_index = device_index

        self.settle_samples = int(sample_rate * settle_ms / 1000)
        self.useful_samples = int(sample_rate * dwell_ms / 1000) - self.settle_samples
        self.total_samples = int(sample_rate * dwell_ms / 1000)
        self.num_bytes = self.total_samples * 2

        Path(IQ_DUMP_DIR).mkdir(exist_ok=True)
        Path(RESULTS_DIR).mkdir(exist_ok=True)

        self._stop = False
        self._baseline = None  # set during calibration

    # ── IQ capture ──────────────────────────────────────────────────────────

    def _capture_iq(self, freq_hz):
        """Raw IQ capture from rtl_sdr. Returns bytes or None."""
        cmd = [
            "rtl_sdr", "-f", str(int(freq_hz)), "-s", str(self.sample_rate),
            "-g", str(self.gain), "-d", str(self.device_index),
            "-n", str(self.num_bytes), "-"
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=15)
            if len(r.stdout) < self.num_bytes:
                return None
            return r.stdout[:self.num_bytes]
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"  [!] rtl_sdr error: {e}", file=sys.stderr)
            return None

    def _raw_to_complex(self, raw):
        """uint8 IQ → complex64, with settle discard + DC notch."""
        iq = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        iq = (iq - 127.5) / 127.5
        z = iq[0::2] + 1j * iq[1::2]

        # discard PLL settling period
        z = z[self.settle_samples:]

        # DC notch: zero center bins in frequency domain
        Z = np.fft.fft(z)
        n = len(Z)
        half = DC_NOTCH_BINS // 2
        Z[:half] = 0
        Z[-half:] = 0
        z = np.fft.ifft(Z)

        return z

    # ── Analysis ────────────────────────────────────────────────────────────

    def _analyze(self, iq, freq_hz):
        """Compute statistical measures on IQ capture."""
        amp = np.abs(iq)
        pwr = amp ** 2
        avg_pwr = np.mean(pwr)
        peak_pwr = np.max(pwr)

        # Kurtosis (regular, not excess — Gaussian = 3.0 for truly Gaussian)
        kurt = float(sp_stats.kurtosis(amp, fisher=False))

        # PAPR
        papr_db = float(10 * np.log10(peak_pwr / avg_pwr)) if avg_pwr > 0 else 0.0

        # Mean power (relative dB)
        mean_pwr_db = float(10 * np.log10(avg_pwr)) if avg_pwr > 0 else -999.0

        # Pulse detection: contiguous runs of samples > threshold
        sigma = np.std(amp)
        mu = np.mean(amp)
        thresh = mu + 4 * sigma
        above = (amp > thresh).astype(np.int8)

        # find contiguous runs
        pulses = []
        if np.any(above):
            diffs = np.diff(np.concatenate(([0], above, [0])))
            starts = np.where(diffs == 1)[0]
            ends = np.where(diffs == -1)[0]
            for s, e in zip(starts, ends):
                width = e - s
                if width >= self.min_pulse_samples:
                    width_us = round(width / self.sample_rate * 1e6, 2)
                    peak_amp = float(np.max(amp[s:e]))
                    peak_snr = round(20 * np.log10(peak_amp / mu), 1) if mu > 0 else 0
                    pulses.append({
                        "offset_ms": round(s / self.sample_rate * 1000, 3),
                        "width_us": width_us,
                        "peak_snr_db": peak_snr,
                    })

        # Spectral flatness (1.0 = white noise, lower = tonal content)
        f, psd = welch(iq, fs=self.sample_rate, nperseg=min(1024, len(iq)),
                       return_onesided=False)
        # exclude DC region from flatness calc
        mask = np.abs(f) > self.sample_rate * 0.02  # skip ±2% around DC
        psd_use = psd[mask]
        if np.mean(psd_use) > 0:
            geo_mean = np.exp(np.mean(np.log(psd_use + 1e-30)))
            spectral_flatness = float(geo_mean / np.mean(psd_use))
        else:
            spectral_flatness = 0.0

        return {
            "freq_mhz": round(freq_hz / 1e6, 3),
            "kurtosis": round(kurt, 4),
            "papr_db": round(papr_db, 2),
            "mean_pwr_db": round(mean_pwr_db, 2),
            "spectral_flatness": round(spectral_flatness, 4),
            "pulse_count": len(pulses),
            "pulses": pulses[:25],
            "n_samples": len(iq),
        }

    # ── Calibration ─────────────────────────────────────────────────────────

    def calibrate(self, freq_start, freq_stop, freq_step):
        """Pass 1: quick sweep to establish baseline statistics."""
        freqs = np.arange(freq_start, freq_stop + 1, freq_step)
        n = len(freqs)

        print(f"\n  CALIBRATING baseline ({n} channels)...")
        kurtosis_vals = []
        papr_vals = []
        flatness_vals = []

        for i, freq in enumerate(freqs):
            if self._stop:
                break
            pct = (i + 1) / n * 100
            sys.stdout.write(f"\r    [{pct:5.1f}%] calibrating {freq/1e6:.0f} MHz")
            sys.stdout.flush()

            raw = self._capture_iq(freq)
            if raw is None:
                continue
            iq = self._raw_to_complex(raw)
            r = self._analyze(iq, freq)
            kurtosis_vals.append(r["kurtosis"])
            papr_vals.append(r["papr_db"])
            flatness_vals.append(r["spectral_flatness"])

        if len(kurtosis_vals) < 3:
            print("\n  [!] Not enough data to calibrate. Aborting.")
            sys.exit(1)

        # Use median + MAD (robust to outliers) as baseline
        k_arr = np.array(kurtosis_vals)
        p_arr = np.array(papr_vals)
        f_arr = np.array(flatness_vals)

        k_med = float(np.median(k_arr))
        k_mad = float(np.median(np.abs(k_arr - k_med)))
        k_sigma = k_mad * 1.4826  # MAD to σ conversion

        p_med = float(np.median(p_arr))
        p_mad = float(np.median(np.abs(p_arr - p_med)))
        p_sigma = p_mad * 1.4826

        f_med = float(np.median(f_arr))
        f_mad = float(np.median(np.abs(f_arr - f_med)))
        f_sigma = f_mad * 1.4826

        self._baseline = {
            "kurtosis_median": k_med,
            "kurtosis_sigma": max(k_sigma, 0.01),  # floor to prevent div/0
            "papr_median": p_med,
            "papr_sigma": max(p_sigma, 0.01),
            "flatness_median": f_med,
            "flatness_sigma": max(f_sigma, 0.001),
            "n_channels": len(kurtosis_vals),
        }

        print(f"\n\n  Baseline established ({len(kurtosis_vals)} channels):")
        print(f"    Kurtosis:  median={k_med:.3f}  σ={k_sigma:.3f}"
              f"  (flag > {k_med + self.outlier_sigma * k_sigma:.3f})")
        print(f"    PAPR:      median={p_med:.2f}dB  σ={p_sigma:.2f}dB"
              f"  (flag > {p_med + self.outlier_sigma * p_sigma:.2f}dB)")
        print(f"    Flatness:  median={f_med:.4f}  σ={f_sigma:.4f}"
              f"  (flag < {f_med - self.outlier_sigma * f_sigma:.4f})")
        print()

        return self._baseline

    # ── Detection ───────────────────────────────────────────────────────────

    def _is_anomalous(self, result):
        """Check if a result deviates from calibrated baseline."""
        if self._baseline is None:
            return False, []

        b = self._baseline
        reasons = []

        # kurtosis outlier (high = impulsive)
        k_z = (result["kurtosis"] - b["kurtosis_median"]) / b["kurtosis_sigma"]
        if k_z > self.outlier_sigma:
            reasons.append(f"kurtosis +{k_z:.1f}σ ({result['kurtosis']:.3f})")

        # PAPR outlier (high = spiky)
        p_z = (result["papr_db"] - b["papr_median"]) / b["papr_sigma"]
        if p_z > self.outlier_sigma:
            reasons.append(f"PAPR +{p_z:.1f}σ ({result['papr_db']:.1f}dB)")

        # spectral flatness outlier (low = tonal/narrowband content)
        f_z = (b["flatness_median"] - result["spectral_flatness"]) / b["flatness_sigma"]
        if f_z > self.outlier_sigma:
            reasons.append(f"flatness -{f_z:.1f}σ ({result['spectral_flatness']:.4f})")

        # real multi-sample pulses detected
        if result["pulse_count"] > 0:
            reasons.append(f"{result['pulse_count']} pulses (≥{self.min_pulse_samples} samples)")

        # elevated mean power vs band median (strong signal)
        # We check this relative to neighbors, but a rough +10dB flag is useful
        # (this is supplementary, not primary)

        return len(reasons) > 0, reasons

    def _save_iq(self, raw, freq_hz, result, reasons):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{IQ_DUMP_DIR}/{ts}_{result['freq_mhz']}MHz.iq"
        with open(fname, "wb") as f:
            f.write(raw)
        meta = {
            **result, "iq_file": fname, "sample_rate": self.sample_rate,
            "flag_reasons": reasons, "baseline": self._baseline,
        }
        with open(fname + ".json", "w") as f:
            json.dump(meta, f, indent=2, default=str)
        return fname

    def _log(self, result):
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(f"{RESULTS_DIR}/{LOG_FILE}", "a") as f:
            f.write(json.dumps(result, default=str) + "\n")

    # ── Band scan ───────────────────────────────────────────────────────────

    def scan_band(self, freq_start=None, freq_stop=None, freq_step=None,
                  skip_cal=False):
        freq_start = freq_start or FREQ_START
        freq_stop = freq_stop or FREQ_STOP
        freq_step = freq_step or FREQ_STEP

        freqs = np.arange(freq_start, freq_stop + 1, freq_step)
        n = len(freqs)
        t0 = datetime.now()

        print(f"\n{'='*72}")
        print(f"  RF PULSE DETECTOR v2 — Calibrated Band Scan")
        print(f"  {freq_start/1e6:.0f} – {freq_stop/1e6:.0f} MHz"
              f"  |  {freq_step/1e6:.1f} MHz steps  |  {n} channels")
        print(f"  Dwell: {self.dwell_ms}ms (settle: {self.settle_ms}ms)"
              f"  |  {self.sample_rate/1e6:.1f} MSPS  |  Gain: {self.gain}dB")
        print(f"  Min pulse width: {self.min_pulse_samples} samples"
              f" ({self.min_pulse_samples/self.sample_rate*1e6:.1f}µs)"
              f"  |  Outlier: {self.outlier_sigma}σ")
        print(f"  DC notch: ±{DC_NOTCH_BINS//2} bins")
        print(f"  Started: {t0.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*72}")

        # ── Pass 1: Calibrate ──
        if not skip_cal:
            # Use wider steps for faster calibration
            cal_step = max(freq_step, int(10e6))  # at least 10 MHz steps
            self.calibrate(freq_start, freq_stop, cal_step)

        # ── Pass 2: Detect ──
        print(f"  SCANNING ({n} channels)...\n")
        all_results = []
        flagged = []

        for i, freq in enumerate(freqs):
            if self._stop:
                print("\n  [!] Stopped by user.")
                break

            pct = (i + 1) / n * 100
            mhz = freq / 1e6
            sys.stdout.write(f"\r  [{pct:5.1f}%] {mhz:10.3f} MHz  ")
            sys.stdout.flush()

            raw = self._capture_iq(freq)
            if raw is None:
                sys.stdout.write("SKIP")
                print()
                continue

            iq = self._raw_to_complex(raw)
            result = self._analyze(iq, freq)
            anomalous, reasons = self._is_anomalous(result)

            result["flagged"] = anomalous
            if anomalous:
                result["flag_reasons"] = reasons
            self._log(result)
            all_results.append(result)

            if anomalous:
                sys.stdout.write(f"*** FLAGGED: {'; '.join(reasons)} ***")
                flagged.append(result)
                if self.save_iq:
                    f = self._save_iq(raw, freq, result, reasons)
                    sys.stdout.write(f"\n{'':>18}[saved: {f}]")
            else:
                sys.stdout.write(
                    f"kurt={result['kurtosis']:.2f}  "
                    f"papr={result['papr_db']:.1f}dB  "
                    f"pwr={result['mean_pwr_db']:.1f}dB  "
                    f"flat={result['spectral_flatness']:.3f}"
                )
            print()

        elapsed = (datetime.now() - t0).total_seconds()

        # ── Summary ──
        print(f"\n{'='*72}")
        print(f"  SCAN COMPLETE — {len(all_results)} channels in {elapsed:.0f}s")
        if self._baseline:
            b = self._baseline
            print(f"  Baseline: kurtosis={b['kurtosis_median']:.3f}±{b['kurtosis_sigma']:.3f}"
                  f"  PAPR={b['papr_median']:.1f}±{b['papr_sigma']:.1f}dB")
        print(f"{'='*72}")

        if flagged:
            print(f"\n  *** {len(flagged)} ANOMALOUS FREQUENCIES ***\n")
            for r in sorted(flagged, key=lambda x: x["kurtosis"], reverse=True):
                reasons = "; ".join(r.get("flag_reasons", []))
                print(f"    {r['freq_mhz']:10.3f} MHz  |  "
                      f"kurt={r['kurtosis']:.3f}  papr={r['papr_db']:.1f}dB  "
                      f"flat={r['spectral_flatness']:.4f}  "
                      f"pulses={r['pulse_count']}")
                print(f"{'':>26}{reasons}")
                for p in r.get("pulses", [])[:5]:
                    print(f"{'':>28}@ {p['offset_ms']:.1f}ms  "
                          f"width={p['width_us']}µs  snr={p['peak_snr_db']}dB")
        else:
            print("\n  No anomalous frequencies detected.")

        # save summary
        summary = {
            "scan_start": t0.isoformat(),
            "elapsed_s": round(elapsed, 1),
            "baseline": self._baseline,
            "channels_scanned": len(all_results),
            "channels_flagged": len(flagged),
            "flagged": flagged,
        }
        ts = t0.strftime("%Y%m%d_%H%M%S")
        sf = f"{RESULTS_DIR}/scan_{ts}.json"
        with open(sf, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"\n  Results: {sf}")
        print(f"  Captures: {IQ_DUMP_DIR}/")
        print(f"  Log: {RESULTS_DIR}/{LOG_FILE}\n")

        return summary

    # ── Single-frequency monitor ────────────────────────────────────────────

    def monitor_freq(self, freq_hz, duration_s=60):
        """Watch one frequency, establish its own baseline, flag transients."""
        mhz = freq_hz / 1e6
        n_captures = int(duration_s * 1000 / self.dwell_ms)

        print(f"\n{'='*72}")
        print(f"  MONITORING {mhz:.3f} MHz — {duration_s}s ({n_captures} captures)")
        print(f"  Building baseline from first 10 captures, then detecting...")
        print(f"{'='*72}\n")

        results = []
        baseline_kurts = []
        baseline_paprs = []
        baseline_ready = False

        for i in range(n_captures):
            if self._stop:
                break

            raw = self._capture_iq(freq_hz)
            if raw is None:
                continue

            iq = self._raw_to_complex(raw)
            r = self._analyze(iq, freq_hz)

            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            if not baseline_ready:
                baseline_kurts.append(r["kurtosis"])
                baseline_paprs.append(r["papr_db"])
                if len(baseline_kurts) >= 10:
                    k_med = np.median(baseline_kurts)
                    k_sig = max(np.median(np.abs(np.array(baseline_kurts) - k_med)) * 1.4826, 0.01)
                    p_med = np.median(baseline_paprs)
                    p_sig = max(np.median(np.abs(np.array(baseline_paprs) - p_med)) * 1.4826, 0.01)
                    self._baseline = {
                        "kurtosis_median": float(k_med), "kurtosis_sigma": float(k_sig),
                        "papr_median": float(p_med), "papr_sigma": float(p_sig),
                        "flatness_median": 0.5, "flatness_sigma": 0.1,
                        "n_channels": 10,
                    }
                    baseline_ready = True
                    print(f"  {ts}  --- baseline set: kurt={k_med:.3f}±{k_sig:.3f}"
                          f"  papr={p_med:.1f}±{p_sig:.1f}dB ---")
                else:
                    print(f"  {ts}  [cal {len(baseline_kurts)}/10]  "
                          f"kurt={r['kurtosis']:.3f}  papr={r['papr_db']:.1f}dB")
                continue

            anomalous, reasons = self._is_anomalous(r)
            r["flagged"] = anomalous
            self._log(r)
            results.append(r)

            marker = ">>>" if anomalous else "   "
            line = (f"  {ts}  {marker}  kurt={r['kurtosis']:.3f}  "
                    f"papr={r['papr_db']:.1f}dB  "
                    f"pulses={r['pulse_count']}")
            if anomalous:
                line += f"  | {'; '.join(reasons)}"
                if self.save_iq:
                    self._save_iq(raw, freq_hz, r, reasons)
            print(line)

        if results:
            kurts = [r["kurtosis"] for r in results]
            n_flag = sum(1 for r in results if r.get("flagged"))
            print(f"\n  Kurtosis range: {min(kurts):.3f} – {max(kurts):.3f}"
                  f"  (mean={np.mean(kurts):.3f})")
            print(f"  Flagged: {n_flag}/{len(results)}")

        return results

    def stop(self):
        self._stop = True


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="RF Pulse Detector v2 — calibrated statistical pulse detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full band scan with auto-calibration
  python pulse_detector.py scan

  # Scan a narrower range
  python pulse_detector.py scan --start 800 --stop 1000

  # Monitor a single frequency for 5 minutes
  python pulse_detector.py monitor --freq 915.0 --duration 300

  # More sensitive detection (lower sigma threshold)
  python pulse_detector.py scan --sigma 2.5

  # Longer dwell for better statistics per channel
  python pulse_detector.py scan --dwell 500
        """
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ── scan ──
    p_scan = sub.add_parser("scan", help="Calibrate + sweep band, flag anomalies")
    p_scan.add_argument("--start", type=float, default=400,
                        help="Start freq MHz (default: 400)")
    p_scan.add_argument("--stop", type=float, default=1766,
                        help="Stop freq MHz (default: 1766)")
    p_scan.add_argument("--step", type=float, default=2.0,
                        help="Step MHz (default: 2.0)")
    p_scan.add_argument("--gain", type=float, default=GAIN,
                        help=f"Gain dB (default: {GAIN})")
    p_scan.add_argument("--dwell", type=int, default=DWELL_MS,
                        help=f"Dwell ms (default: {DWELL_MS})")
    p_scan.add_argument("--sigma", type=float, default=OUTLIER_SIGMA,
                        help=f"Outlier threshold in σ (default: {OUTLIER_SIGMA})")
    p_scan.add_argument("--min-pulse", type=int, default=MIN_PULSE_SAMPLES,
                        help=f"Min pulse width in samples (default: {MIN_PULSE_SAMPLES})")
    p_scan.add_argument("--no-save-iq", action="store_true",
                        help="Don't save raw IQ for flagged freqs")

    # ── monitor ──
    p_mon = sub.add_parser("monitor", help="Watch single frequency over time")
    p_mon.add_argument("--freq", type=float, required=True,
                       help="Frequency MHz")
    p_mon.add_argument("--duration", type=int, default=60,
                       help="Duration seconds (default: 60)")
    p_mon.add_argument("--gain", type=float, default=GAIN)
    p_mon.add_argument("--dwell", type=int, default=DWELL_MS)
    p_mon.add_argument("--sigma", type=float, default=OUTLIER_SIGMA)
    p_mon.add_argument("--min-pulse", type=int, default=MIN_PULSE_SAMPLES)
    p_mon.add_argument("--no-save-iq", action="store_true")

    args = parser.parse_args()

    det = PulseDetector(
        gain=args.gain,
        dwell_ms=args.dwell,
        outlier_sigma=args.sigma,
        min_pulse_samples=args.min_pulse,
        save_iq=not args.no_save_iq,
    )

    signal.signal(signal.SIGINT, lambda s, f: (
        print("\n\n  [Ctrl-C] Stopping..."), det.stop()
    ))

    if args.command == "scan":
        det.scan_band(
            freq_start=int(args.start * 1e6),
            freq_stop=int(args.stop * 1e6),
            freq_step=int(args.step * 1e6),
        )
    elif args.command == "monitor":
        det.monitor_freq(
            freq_hz=int(args.freq * 1e6),
            duration_s=args.duration,
        )


if __name__ == "__main__":
    main()

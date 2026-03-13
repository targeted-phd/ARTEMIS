#!/usr/bin/env python3
"""
Microwave Pulse Demodulator & Speech Pattern Detector

Demodulates pulse trains from RTL-SDR IQ captures and analyzes for
speech-like patterns using ML and fuzzy logic methods.

Demodulation methods:
  1. ENVELOPE — Amplitude envelope of IQ signal, lowpassed and downsampled
     to audio rate. This is the physically correct model for the Frey effect:
     tissue absorbs RF power proportional to |E|², so the power envelope
     IS the thermoelastic forcing function.
  2. BURST PRF — Detects pulse bursts, computes burst repetition frequency
     over time. If burst rate is modulated in audio band → perceived tone.
  3. BURST PAM — Peak energy of each burst over time. Amplitude modulation
     of burst envelope encodes speech waveform.

Speech analysis pipeline:
  - Modulation spectrum analysis (2-8 Hz syllable rate detection)
  - LPC formant detection (F1/F2/F3 resonance structure)
  - YIN pitch tracking (F0 fundamental frequency)
  - MFCC feature extraction
  - Energy + zero-crossing rate VAD
  - Fuzzy logic fusion → speech confidence score (0.0-1.0)

References:
  Frey (1961) Aerospace Medicine 32:1140
  Lin & Wang (2007) Health Physics 92(6):621
  Elder & Chou (2003) Bioelectromagnetics 24(S6):S162
  Guy et al (1975) Ann NY Acad Sci 247:194
  de Cheveigne & Kawahara (2002) JASA 111(4):1917

Usage:
  python demod_pulses.py analyze <iq_file>         # Single file
  python demod_pulses.py analyze <iq_file> --concat 5  # Concat 5 sequential captures
  python demod_pulses.py batch [--top N]           # Batch all captures
  python demod_pulses.py summary                   # Aggregate results
"""

import os
import sys
import json
import glob
import argparse
import struct
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy import signal as sig
from scipy.fft import dct
from scipy.interpolate import interp1d
from scipy.linalg import solve_toeplitz

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ── Hardware / capture constants ────────────────────────────────────────
SAMPLE_RATE = 2_400_000       # RTL-SDR sample rate (Hz)
DC_NOTCH_BINS = 16            # FFT bins to zero around DC
PLL_SETTLE_SAMPLES = 48_000   # 20 ms settle discard
MIN_PULSE_SAMPLES = 3         # 1.25 µs minimum pulse

# ── Audio / speech constants ────────────────────────────────────────────
AUDIO_RATE = 16_000           # Speech processing rate
FRAME_LEN_S = 0.025           # 25 ms analysis frames
FRAME_HOP_S = 0.010           # 10 ms hop
PRE_EMPHASIS = 0.97
LPC_ORDER = 12
N_MFCC = 13
N_MEL_FILTERS = 40
NFFT = 512

# Pitch
YIN_THRESHOLD = 0.15
F0_MIN = 80
F0_MAX = 400

# Modulation spectrum
SYLLABLE_RATE_RANGE = (1.0, 8.0)    # Hz — speech syllable rate
PITCH_MOD_RANGE = (80.0, 255.0)     # Hz — voice F0 range

# Formant ranges (Hz)
FORMANT_RANGES = {"F1": (200, 1000), "F2": (800, 2800), "F3": (1800, 3500)}
FORMANT_MAX_BW = 400

# Burst detection
BURST_GAP_SAMPLES = 240      # 100 µs gap = new burst (at 2.4 MSPS)

# Output
RESULTS_DIR = "results/demod"
CAPTURES_DIR = "captures"


# ═══════════════════════════════════════════════════════════════════════════
#  IQ LOADING
# ═══════════════════════════════════════════════════════════════════════════

def load_iq(filepath):
    """Load RTL-SDR raw IQ (unsigned 8-bit interleaved I/Q)."""
    raw = np.fromfile(filepath, dtype=np.uint8)
    iq = (raw[0::2].astype(np.float32) - 127.5) + \
         1j * (raw[1::2].astype(np.float32) - 127.5)

    if len(iq) > PLL_SETTLE_SAMPLES:
        iq = iq[PLL_SETTLE_SAMPLES:]

    # DC notch
    if len(iq) > 1024:
        spectrum = np.fft.fft(iq)
        n = len(spectrum)
        spectrum[:DC_NOTCH_BINS] = 0
        spectrum[n - DC_NOTCH_BINS:] = 0
        iq = np.fft.ifft(spectrum)

    return iq


def load_iq_concat(filepath, n_concat=1):
    """
    Load an IQ file and optionally concatenate sequential captures
    from the same frequency for longer analysis windows.
    """
    base_dir = os.path.dirname(filepath)
    base_name = os.path.basename(filepath)

    # Parse frequency from filename: sentinel_826MHz_014542.iq
    parts = base_name.split("_")
    freq_part = [p for p in parts if "MHz" in p]
    if not freq_part:
        return load_iq(filepath)

    freq_str = freq_part[0]

    # Find all files for this frequency, sorted by timestamp
    pattern = os.path.join(base_dir, f"sentinel_{freq_str}_*.iq")
    all_files = sorted(glob.glob(pattern))

    if filepath not in all_files:
        return load_iq(filepath)

    idx = all_files.index(filepath)
    files_to_load = all_files[idx:idx + n_concat]

    segments = []
    for f in files_to_load:
        segments.append(load_iq(f))

    return np.concatenate(segments)


# ═══════════════════════════════════════════════════════════════════════════
#  PULSE & BURST DETECTION
# ═══════════════════════════════════════════════════════════════════════════

def detect_pulses(iq, threshold_sigma=4.0):
    """Detect individual pulses in IQ data."""
    amplitude = np.abs(iq)
    mean_a = np.mean(amplitude)
    std_a = np.std(amplitude)
    threshold = mean_a + threshold_sigma * std_a

    above = amplitude > threshold
    if not np.any(above):
        return [], amplitude

    edges = np.diff(above.astype(np.int8))
    starts = np.where(edges == 1)[0] + 1
    stops = np.where(edges == -1)[0] + 1

    if above[0]:
        starts = np.concatenate([[0], starts])
    if above[-1]:
        stops = np.concatenate([stops, [len(above)]])

    min_len = min(len(starts), len(stops))
    starts, stops = starts[:min_len], stops[:min_len]
    widths = stops - starts
    valid = widths >= MIN_PULSE_SAMPLES
    starts, stops, widths = starts[valid], stops[valid], widths[valid]

    pulses = []
    for i in range(len(starts)):
        seg = amplitude[starts[i]:stops[i]]
        pulses.append({
            "start": int(starts[i]),
            "stop": int(stops[i]),
            "time_s": starts[i] / SAMPLE_RATE,
            "amplitude": float(np.max(seg)),
            "energy": float(np.sum(seg ** 2)),
            "width_samples": int(widths[i]),
            "width_us": widths[i] / SAMPLE_RATE * 1e6,
        })

    return pulses, amplitude


def detect_bursts(pulses, gap_samples=BURST_GAP_SAMPLES):
    """
    Group pulses into bursts. A burst is a cluster of pulses separated
    from the next cluster by at least gap_samples.

    Returns list of burst dicts with aggregate properties.
    """
    if len(pulses) < 2:
        return [{"pulses": pulses, "n_pulses": len(pulses),
                 "start_s": pulses[0]["time_s"] if pulses else 0,
                 "end_s": pulses[0]["time_s"] if pulses else 0,
                 "duration_us": 0, "peak_amplitude": pulses[0]["amplitude"] if pulses else 0,
                 "total_energy": pulses[0]["energy"] if pulses else 0}] if pulses else []

    bursts = []
    current_burst = [pulses[0]]

    for i in range(1, len(pulses)):
        gap = pulses[i]["start"] - pulses[i - 1]["stop"]
        if gap > gap_samples:
            bursts.append(current_burst)
            current_burst = [pulses[i]]
        else:
            current_burst.append(pulses[i])

    if current_burst:
        bursts.append(current_burst)

    result = []
    for burst_pulses in bursts:
        start_s = burst_pulses[0]["time_s"]
        end_s = burst_pulses[-1]["time_s"] + burst_pulses[-1]["width_us"] * 1e-6
        result.append({
            "n_pulses": len(burst_pulses),
            "start_s": start_s,
            "end_s": end_s,
            "duration_us": (end_s - start_s) * 1e6,
            "peak_amplitude": max(p["amplitude"] for p in burst_pulses),
            "mean_amplitude": np.mean([p["amplitude"] for p in burst_pulses]),
            "total_energy": sum(p["energy"] for p in burst_pulses),
            "mean_width_us": np.mean([p["width_us"] for p in burst_pulses]),
        })

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  DEMODULATION — THREE METHODS
# ═══════════════════════════════════════════════════════════════════════════

def demod_envelope(iq, target_sr=AUDIO_RATE):
    """
    Envelope demodulation — the physically correct Frey effect model.

    The tissue absorbs RF power ∝ |E|². The instantaneous power envelope
    drives thermoelastic expansion. This envelope, lowpassed to audio
    bandwidth, IS the acoustic forcing function.

    Steps:
      1. Compute power envelope: |IQ|²
      2. Lowpass to audio bandwidth (anti-alias)
      3. Decimate to target audio sample rate
      4. Remove DC, normalize
    """
    if len(iq) < 100:
        return None, {}

    # Power envelope (proportional to specific absorption rate)
    power_env = np.abs(iq) ** 2

    # Decimation factor
    decimate_factor = SAMPLE_RATE // target_sr
    if decimate_factor < 1:
        decimate_factor = 1

    # Anti-alias lowpass then decimate
    # Use scipy decimate which applies Chebyshev type I anti-alias filter
    try:
        # Multi-stage decimation for large factors (2.4M → 16k = 150x)
        audio = power_env.copy()
        remaining = decimate_factor
        # Factor into stages ≤ 13 (scipy recommendation)
        stages = []
        temp = remaining
        for factor in [10, 10, 5, 3, 2]:
            if temp >= factor:
                stages.append(factor)
                temp //= factor
                if temp <= 1:
                    break
        if temp > 1:
            stages.append(temp)

        for stage_factor in stages:
            if stage_factor > 1 and len(audio) > stage_factor * 10:
                audio = sig.decimate(audio, stage_factor, ftype="fir",
                                      zero_phase=True)
    except Exception:
        # Fallback: simple averaging decimation
        n = len(power_env) // decimate_factor * decimate_factor
        audio = power_env[:n].reshape(-1, decimate_factor).mean(axis=1)

    if len(audio) < 10:
        return None, {}

    # Effective sample rate after decimation
    effective_sr = SAMPLE_RATE
    for s in stages:
        effective_sr //= s

    # Remove DC
    audio = audio - np.mean(audio)

    # Normalize
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    stats = {
        "method": "ENVELOPE",
        "decimate_factor": decimate_factor,
        "decimate_stages": stages,
        "effective_sr": int(effective_sr),
        "audio_samples": len(audio),
        "audio_duration_s": len(audio) / effective_sr,
        "input_samples": len(iq),
        "input_duration_s": len(iq) / SAMPLE_RATE,
    }

    return audio.astype(np.float32), stats


def demod_burst_prf(bursts, target_sr=AUDIO_RATE):
    """
    Burst PRF demodulation.

    The inter-burst interval determines perceived tone frequency.
    If burst rate modulates in audio range → that IS the audio signal.
    """
    if len(bursts) < 3:
        return None, {}

    # Burst center times and inter-burst intervals
    centers = np.array([(b["start_s"] + b["end_s"]) / 2 for b in bursts])
    intervals = np.diff(centers)

    # Remove outliers
    median_int = np.median(intervals)
    valid = (intervals > 0) & (intervals < 5 * median_int)
    if np.sum(valid) < 3:
        return None, {}

    mid_times = (centers[:-1] + centers[1:]) / 2
    mid_times = mid_times[valid]
    intervals = intervals[valid]

    inst_brf = 1.0 / intervals  # instantaneous burst repetition frequency

    stats = {
        "method": "BURST_PRF",
        "mean_brf_hz": float(np.mean(inst_brf)),
        "std_brf_hz": float(np.std(inst_brf)),
        "min_brf_hz": float(np.min(inst_brf)),
        "max_brf_hz": float(np.max(inst_brf)),
        "n_bursts": len(bursts),
        "duration_s": float(centers[-1] - centers[0]),
    }

    if mid_times[-1] - mid_times[0] < 1e-5:
        return None, stats

    # Interpolate to uniform grid
    t_uniform = np.arange(mid_times[0], mid_times[-1], 1.0 / target_sr)
    if len(t_uniform) < 10:
        return None, stats

    try:
        interp_fn = interp1d(mid_times, inst_brf, kind="linear",
                              bounds_error=False, fill_value="extrapolate")
        audio = interp_fn(t_uniform)
    except Exception:
        return None, stats

    audio = audio - np.mean(audio)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    stats["audio_samples"] = len(audio)
    stats["audio_duration_s"] = len(audio) / target_sr

    return audio.astype(np.float32), stats


def demod_burst_pam(bursts, target_sr=AUDIO_RATE):
    """
    Burst amplitude modulation demodulation.

    The energy/amplitude of each burst encodes the audio signal.
    """
    if len(bursts) < 3:
        return None, {}

    times = np.array([(b["start_s"] + b["end_s"]) / 2 for b in bursts])
    energies = np.array([b["total_energy"] for b in bursts])

    stats = {
        "method": "BURST_PAM",
        "mean_energy": float(np.mean(energies)),
        "std_energy": float(np.std(energies)),
        "dynamic_range_db": float(10 * np.log10(
            np.max(energies) / (np.min(energies) + 1e-10))),
        "n_bursts": len(bursts),
        "duration_s": float(times[-1] - times[0]),
    }

    if times[-1] - times[0] < 1e-5:
        return None, stats

    t_uniform = np.arange(times[0], times[-1], 1.0 / target_sr)
    if len(t_uniform) < 10:
        return None, stats

    try:
        interp_fn = interp1d(times, energies, kind="linear",
                              bounds_error=False, fill_value="extrapolate")
        audio = interp_fn(t_uniform)
    except Exception:
        return None, stats

    audio = audio - np.mean(audio)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    stats["audio_samples"] = len(audio)
    stats["audio_duration_s"] = len(audio) / target_sr

    return audio.astype(np.float32), stats


# ═══════════════════════════════════════════════════════════════════════════
#  SPEECH FEATURE EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

def frame_signal(audio, sr, frame_len_s=FRAME_LEN_S, hop_s=FRAME_HOP_S):
    """Split into overlapping frames."""
    frame_len = int(round(frame_len_s * sr))
    hop_len = int(round(hop_s * sr))
    n = max(1, 1 + (len(audio) - frame_len) // hop_len)
    frames = np.zeros((n, frame_len))
    for i in range(n):
        s = i * hop_len
        e = min(s + frame_len, len(audio))
        frames[i, :e - s] = audio[s:e]
    return frames


def compute_mfcc(audio, sr, n_mfcc=N_MFCC, n_filt=N_MEL_FILTERS, nfft=NFFT):
    """Mel-Frequency Cepstral Coefficients."""
    if len(audio) < nfft:
        return np.zeros((1, n_mfcc - 1))

    emphasized = np.append(audio[0], audio[1:] - PRE_EMPHASIS * audio[:-1])
    frames = frame_signal(emphasized, sr)
    if len(frames) == 0:
        return np.zeros((1, n_mfcc - 1))

    window = np.hamming(frames.shape[1])
    frames = frames * window
    mag = np.abs(np.fft.rfft(frames, nfft))
    power = (1.0 / nfft) * mag ** 2

    # Mel filterbank
    low_mel = 2595 * np.log10(1 + 0 / 700)
    high_mel = 2595 * np.log10(1 + (sr / 2) / 700)
    mel_pts = np.linspace(low_mel, high_mel, n_filt + 2)
    hz_pts = 700 * (10 ** (mel_pts / 2595) - 1)
    bins = np.floor((nfft + 1) * hz_pts / sr).astype(int)

    fbank = np.zeros((n_filt, nfft // 2 + 1))
    for i in range(n_filt):
        for j in range(bins[i], bins[i + 1]):
            if bins[i + 1] > bins[i]:
                fbank[i, j] = (j - bins[i]) / (bins[i + 1] - bins[i])
        for j in range(bins[i + 1], bins[i + 2]):
            if bins[i + 2] > bins[i + 1]:
                fbank[i, j] = (bins[i + 2] - j) / (bins[i + 2] - bins[i + 1])

    fb = np.dot(power, fbank.T)
    fb = np.where(fb == 0, np.finfo(float).eps, fb)
    fb = np.log(fb)

    mfcc = dct(fb, type=2, axis=1, norm="ortho")[:, 1:n_mfcc]
    mfcc -= np.mean(mfcc, axis=0, keepdims=True)
    return mfcc


def analyze_harmonic_structure(pulses, amplitude, sample_rate=SAMPLE_RATE):
    """
    Second harmonic detection — from KG: Kellnberger et al. (2013).

    CW RF fields induce frequency-domain acoustic responses in conductive tissue.
    Detection via harmonic analysis rather than time-domain pulse detection.

    Analyzes pulse amplitude sequence for harmonic relationships (f, 2f, 3f).
    High harmonic scores suggest structured/intentional modulation rather
    than random interference.

    Returns harmonic analysis dict with scores and detected harmonics.
    """
    if len(pulses) < 4:
        return {"harmonic_score": 0.0, "n_harmonics": 0, "fundamental_hz": 0.0,
                "harmonics": [], "spectral_entropy": 1.0}

    # Extract pulse amplitudes as a time series
    pulse_amps = np.array([p["amplitude"] for p in pulses])
    pulse_times = np.array([p["time_s"] for p in pulses])

    # Compute mean pulse rate
    if len(pulse_times) > 1:
        dt = np.diff(pulse_times)
        dt_valid = dt[dt > 0]
        if len(dt_valid) == 0:
            return {"harmonic_score": 0.0, "n_harmonics": 0, "fundamental_hz": 0.0,
                    "harmonics": [], "spectral_entropy": 1.0}
        mean_rate = 1.0 / np.mean(dt_valid)
    else:
        return {"harmonic_score": 0.0, "n_harmonics": 0, "fundamental_hz": 0.0,
                "harmonics": [], "spectral_entropy": 1.0}

    # FFT of pulse amplitude sequence
    n = len(pulse_amps)
    if n < 8:
        return {"harmonic_score": 0.0, "n_harmonics": 0, "fundamental_hz": 0.0,
                "harmonics": [], "spectral_entropy": 1.0}

    # Remove DC, window, FFT
    pulse_amps_centered = pulse_amps - np.mean(pulse_amps)
    window = np.hamming(n)
    spectrum = np.abs(np.fft.rfft(pulse_amps_centered * window))
    freqs = np.fft.rfftfreq(n, d=1.0 / mean_rate)

    if len(spectrum) < 4 or np.max(spectrum) == 0:
        return {"harmonic_score": 0.0, "n_harmonics": 0, "fundamental_hz": 0.0,
                "harmonics": [], "spectral_entropy": 1.0}

    # Normalize spectrum
    spectrum_norm = spectrum / (np.max(spectrum) + 1e-10)

    # Find peaks (above 20% of max)
    peak_threshold = 0.2
    peaks = []
    for i in range(1, len(spectrum_norm) - 1):
        if (spectrum_norm[i] > spectrum_norm[i - 1] and
                spectrum_norm[i] > spectrum_norm[i + 1] and
                spectrum_norm[i] > peak_threshold):
            peaks.append((freqs[i], float(spectrum_norm[i]), i))

    if not peaks:
        return {"harmonic_score": 0.0, "n_harmonics": 0, "fundamental_hz": 0.0,
                "harmonics": [], "spectral_entropy": 1.0}

    # Sort by amplitude, take strongest as fundamental candidate
    peaks.sort(key=lambda x: x[1], reverse=True)
    f0_candidate = peaks[0][0]

    if f0_candidate <= 0:
        return {"harmonic_score": 0.0, "n_harmonics": 0, "fundamental_hz": 0.0,
                "harmonics": [], "spectral_entropy": 1.0}

    # Check for harmonics (2f, 3f, 4f, 5f)
    harmonics = [{"order": 1, "freq_hz": float(f0_candidate),
                  "amplitude": float(peaks[0][1])}]
    tolerance = f0_candidate * 0.15  # 15% tolerance

    for order in range(2, 6):
        expected = f0_candidate * order
        # Find closest peak
        best_match = None
        best_dist = tolerance
        for f, amp, _ in peaks[1:]:
            dist = abs(f - expected)
            if dist < best_dist:
                best_dist = dist
                best_match = (f, amp)
        if best_match:
            harmonics.append({"order": order, "freq_hz": float(best_match[0]),
                              "amplitude": float(best_match[1])})

    n_harmonics = len(harmonics)

    # Harmonic score: weighted by number of harmonics and their amplitudes
    if n_harmonics >= 3:
        harmonic_score = min(1.0, 0.3 * n_harmonics +
                           0.2 * np.mean([h["amplitude"] for h in harmonics]))
    elif n_harmonics >= 2:
        harmonic_score = 0.3 + 0.2 * np.mean([h["amplitude"] for h in harmonics])
    else:
        harmonic_score = 0.1

    # Spectral entropy (low = structured, high = noise-like)
    spectrum_pdf = spectrum_norm / (np.sum(spectrum_norm) + 1e-10)
    spectral_entropy = float(-np.sum(spectrum_pdf * np.log2(spectrum_pdf + 1e-10)))
    max_entropy = np.log2(len(spectrum_pdf))
    spectral_entropy_norm = spectral_entropy / (max_entropy + 1e-10)

    # Also analyze the full amplitude waveform for harmonic content
    # This catches CW-induced harmonics that pulse analysis might miss
    if len(amplitude) > 1024:
        amp_spectrum = np.abs(np.fft.rfft(
            (amplitude[:8192] - np.mean(amplitude[:8192])) * np.hamming(min(8192, len(amplitude)))))
        amp_freqs = np.fft.rfftfreq(min(8192, len(amplitude)), d=1.0 / sample_rate)

        # Look for strong narrow peaks (harmonic structure in raw signal)
        amp_norm = amp_spectrum / (np.max(amp_spectrum) + 1e-10)
        strong_bins = np.sum(amp_norm > 0.3)
        total_bins = len(amp_norm)
        # Few strong bins relative to total = harmonic (vs broadband noise)
        if total_bins > 0:
            narrowband_ratio = strong_bins / total_bins
            if narrowband_ratio < 0.05:  # Very narrow peaks
                harmonic_score = min(1.0, harmonic_score + 0.2)

    return {
        "harmonic_score": round(float(harmonic_score), 4),
        "n_harmonics": n_harmonics,
        "fundamental_hz": round(float(f0_candidate), 2),
        "harmonics": harmonics,
        "spectral_entropy": round(float(spectral_entropy_norm), 4),
    }


def extract_formants_lpc(frame, sr, order=LPC_ORDER):
    """Extract formant frequencies via LPC polynomial roots."""
    if len(frame) < order + 1:
        return []

    emphasized = np.append(frame[0], frame[1:] - 0.63 * frame[:-1])
    windowed = emphasized * np.hamming(len(emphasized))

    try:
        autocorr = np.correlate(windowed, windowed, mode="full")
        autocorr = autocorr[len(autocorr) // 2:][:order + 1]
        a_coeffs = solve_toeplitz(autocorr[:order], autocorr[1:order + 1])
        a = np.concatenate([[1.0], -a_coeffs])
    except Exception:
        return []

    roots = np.roots(a)
    roots = roots[np.imag(roots) > 0]
    if len(roots) == 0:
        return []

    angles = np.arctan2(np.imag(roots), np.real(roots))
    freqs = angles * (sr / (2 * np.pi))
    bws = -0.5 * (sr / (2 * np.pi)) * np.log(np.abs(roots))

    formants = [(float(f), float(bw)) for f, bw in zip(freqs, bws)
                if 90 < f < sr / 2 and 0 < bw < FORMANT_MAX_BW]
    formants.sort(key=lambda x: x[0])
    return formants


def detect_pitch_yin(audio, sr, fmin=F0_MIN, fmax=F0_MAX, threshold=YIN_THRESHOLD):
    """YIN pitch detection (de Cheveigne & Kawahara, 2002)."""
    tau_min = max(1, int(sr / fmax))
    tau_max = min(len(audio) // 2 - 1, int(sr / fmin))
    if tau_min >= tau_max or len(audio) < tau_max * 2:
        return 0.0, 0.0

    w = len(audio) // 2
    d = np.zeros(tau_max + 1)
    for tau in range(1, tau_max + 1):
        d[tau] = np.sum((audio[:w] - audio[tau:tau + w]) ** 2)

    # Cumulative mean normalized difference
    d_prime = np.ones(tau_max + 1)
    running = 0.0
    for tau in range(1, tau_max + 1):
        running += d[tau]
        d_prime[tau] = d[tau] * tau / running if running > 0 else 1.0

    # Find first dip below threshold
    best_tau = 0
    for tau in range(tau_min, tau_max):
        if d_prime[tau] < threshold:
            while tau + 1 < tau_max and d_prime[tau + 1] < d_prime[tau]:
                tau += 1
            best_tau = tau
            break

    if best_tau == 0:
        best_tau = tau_min + np.argmin(d_prime[tau_min:tau_max + 1])
        if d_prime[best_tau] > 0.5:
            return 0.0, 0.0

    # Parabolic interpolation
    if 0 < best_tau < len(d_prime) - 1:
        a, b, g = d_prime[best_tau - 1], d_prime[best_tau], d_prime[best_tau + 1]
        denom = 2 * (a - 2 * b + g)
        refined = best_tau + (a - g) / denom if abs(denom) > 1e-10 else best_tau
    else:
        refined = best_tau

    if refined <= 0:
        return 0.0, 0.0

    f0 = sr / refined
    conf = max(0, min(1, 1.0 - d_prime[best_tau]))
    return (float(f0), float(conf)) if fmin <= f0 <= fmax else (0.0, 0.0)


def pitch_track(audio, sr, frame_len_s=0.040, hop_s=0.010):
    """Track pitch over time."""
    fl = int(round(frame_len_s * sr))
    hl = int(round(hop_s * sr))
    n = max(1, 1 + (len(audio) - fl) // hl)
    f0s, confs = np.zeros(n), np.zeros(n)
    for i in range(n):
        s = i * hl
        frame = audio[s:min(s + fl, len(audio))]
        if len(frame) >= int(sr / F0_MAX) * 2:
            f0s[i], confs[i] = detect_pitch_yin(frame, sr)
    return f0s, confs


def modulation_spectrum_score(audio, sr):
    """
    Score signal for speech-like temporal modulation.

    Speech has strong modulation at 2-8 Hz (syllable rate).
    Returns modulation ratio and speech-likeness score.
    """
    if len(audio) < int(sr * 0.05):
        return {"syllable_mod_ratio": 0.0, "score": 0.0}

    # Amplitude envelope via Hilbert
    envelope = np.abs(sig.hilbert(audio))

    # Lowpass envelope to < 50 Hz
    nyq = sr / 2
    if nyq > 50:
        try:
            b, a = sig.butter(4, 50 / nyq, btype="low")
            envelope = sig.filtfilt(b, a, envelope)
        except Exception:
            pass

    mod_fft = np.abs(np.fft.rfft(envelope))
    mod_freqs = np.fft.rfftfreq(len(envelope), 1.0 / sr)

    lo, hi = SYLLABLE_RATE_RANGE
    speech_band = (mod_freqs >= lo) & (mod_freqs <= hi)
    ref_band = (mod_freqs >= 15) & (mod_freqs <= 30)
    total_band = mod_freqs > 0.5

    sp = np.mean(mod_fft[speech_band] ** 2) if np.any(speech_band) else 0
    rp = np.mean(mod_fft[ref_band] ** 2) if np.any(ref_band) else 1e-10
    tp = np.mean(mod_fft[total_band] ** 2) if np.any(total_band) else 1e-10

    ratio = sp / (rp + 1e-10)
    fraction = sp / (tp + 1e-10)

    return {
        "syllable_mod_ratio": float(ratio),
        "syllable_mod_fraction": float(fraction),
        "score": float(min(1.0, ratio / 10.0)),
    }


def energy_zcr_vad(audio, sr):
    """Voice activity detection via energy + zero-crossing rate."""
    frames = frame_signal(audio, sr)
    n = len(frames)
    energies, zcrs = np.zeros(n), np.zeros(n)

    for i in range(n):
        frame = frames[i]
        energies[i] = 10 * np.log10(np.mean(frame ** 2) + 1e-20)
        zm = frame - np.mean(frame)
        zcrs[i] = np.sum(np.abs(np.diff(np.sign(zm)))) / (2 * len(frame))

    # Adaptive threshold
    e_med = np.median(energies)
    e_mad = np.median(np.abs(energies - e_med)) * 1.4826
    e_thresh = e_med + 0.5 * e_mad
    zcr_med = np.median(zcrs)

    vad = energies > e_thresh
    voiced = vad & (zcrs < zcr_med)

    return {
        "active_ratio": float(np.mean(vad)),
        "voiced_ratio": float(np.mean(voiced)),
        "unvoiced_ratio": float(np.mean(vad & ~voiced)),
        "energy_mean_db": float(np.mean(energies)),
        "energy_std_db": float(np.std(energies)),
        "zcr_mean": float(np.mean(zcrs)),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  FUZZY LOGIC SPEECH CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════

def gaussian_mf(x, mean, sigma):
    return float(np.exp(-0.5 * ((x - mean) / (sigma + 1e-10)) ** 2))


def sigmoid_mf(x, center, steepness):
    return float(1.0 / (1.0 + np.exp(-steepness * (x - center))))


def fuzzy_speech_score(features):
    """
    Fuse multiple weak speech indicators via fuzzy logic.

    Weights from speech detection literature:
      Modulation spectrum — strongest single discriminator
      Formant structure  — very strong (unique to vocal tract)
      Pitch detection    — good but absent in whispered speech
      Voiced ratio       — supplementary
      MFCC structure     — spectral shape indicator
      Energy dynamics    — necessary but not sufficient
    """
    mu_mod = sigmoid_mf(features.get("mod_ratio", 0), 3.0, 1.5)
    mu_fmt = gaussian_mf(features.get("formant_score", 0), 0.8, 0.25)
    mu_pit = gaussian_mf(features.get("pitch_confidence", 0), 0.7, 0.25) * \
             features.get("pitch_in_range", 0)
    mu_voi = gaussian_mf(features.get("voiced_ratio", 0), 0.5, 0.2)
    mu_mfc = sigmoid_mf(features.get("mfcc_structure", 0), 0.5, 3.0)
    mu_eng = sigmoid_mf(features.get("energy_variance", 0), 5.0, 0.5)

    score = (0.30 * mu_mod + 0.25 * mu_fmt + 0.15 * mu_pit +
             0.10 * mu_voi + 0.10 * mu_mfc + 0.10 * mu_eng)

    return float(np.clip(score, 0, 1))


def classify_confidence(score):
    if score >= 0.7:
        return "LIKELY SPEECH"
    elif score >= 0.4:
        return "POSSIBLE SPEECH"
    elif score >= 0.2:
        return "WEAK INDICATORS"
    return "NO SPEECH DETECTED"


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYSIS PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

def analyze_audio(audio, sr, method_name):
    """Run full speech analysis on demodulated audio."""
    if audio is None or len(audio) < int(sr * 0.01):
        return {"method": method_name, "error": "insufficient_data",
                "speech_score": 0.0, "classification": "NO SPEECH DETECTED"}

    result = {"method": method_name, "n_samples": len(audio),
              "duration_s": len(audio) / sr}

    # 1. Modulation spectrum
    mod = modulation_spectrum_score(audio, sr)
    result["modulation"] = mod

    # 2. Formants (sample frames across the signal)
    frames = frame_signal(audio, sr, 0.030, 0.015)
    n_check = min(200, len(frames))
    formant_counts = []
    all_f1, all_f2, all_f3 = [], [], []

    for frame in frames[:n_check]:
        formants = extract_formants_lpc(frame, sr)
        in_range = 0
        for f, bw in formants:
            for lo, hi in FORMANT_RANGES.values():
                if lo <= f <= hi:
                    in_range += 1
                    break
        formant_counts.append(in_range)
        freqs = [f for f, bw in formants if 90 < f < sr / 2]
        if len(freqs) >= 1: all_f1.append(freqs[0])
        if len(freqs) >= 2: all_f2.append(freqs[1])
        if len(freqs) >= 3: all_f3.append(freqs[2])

    mean_fc = np.mean(formant_counts) if formant_counts else 0
    formant_score = min(1.0, mean_fc / 3.0)

    result["formants"] = {
        "score": float(formant_score),
        "mean_per_frame": float(mean_fc),
        "frames_with_2plus": int(sum(1 for c in formant_counts if c >= 2)),
        "total_frames": len(formant_counts),
        "f1_mean": float(np.mean(all_f1)) if all_f1 else 0,
        "f2_mean": float(np.mean(all_f2)) if all_f2 else 0,
        "f3_mean": float(np.mean(all_f3)) if all_f3 else 0,
    }

    # 3. Pitch
    f0s, confs = pitch_track(audio, sr)
    voiced_f0 = f0s[confs > 0.3]
    mean_conf = float(np.mean(confs)) if len(confs) > 0 else 0
    mean_f0 = float(np.mean(voiced_f0)) if len(voiced_f0) > 0 else 0
    f0_std = float(np.std(voiced_f0)) if len(voiced_f0) > 2 else 0
    in_range = 1 if F0_MIN <= mean_f0 <= F0_MAX else 0

    result["pitch"] = {
        "mean_f0_hz": mean_f0,
        "std_f0_hz": f0_std,
        "mean_confidence": mean_conf,
        "voiced_frames": int(np.sum(confs > 0.3)),
        "total_frames": len(f0s),
        "in_human_range": bool(in_range),
        "varies_like_speech": f0_std > 5.0,
    }

    # 4. VAD
    vad = energy_zcr_vad(audio, sr)
    result["vad"] = {k: v for k, v in vad.items()
                     if not isinstance(v, np.ndarray)}

    # 5. MFCCs
    mfcc = compute_mfcc(audio, sr)
    mfcc_var = float(np.mean(np.var(mfcc, axis=0))) if mfcc.shape[0] > 1 else 0

    result["mfcc"] = {
        "structure_variance": mfcc_var,
        "n_frames": mfcc.shape[0],
    }

    # 6. Fuzzy fusion
    fuzzy_in = {
        "mod_ratio": mod["syllable_mod_ratio"],
        "formant_score": formant_score,
        "pitch_confidence": mean_conf,
        "pitch_in_range": in_range,
        "voiced_ratio": vad["voiced_ratio"],
        "mfcc_structure": min(1.0, mfcc_var / 2.0),
        "energy_variance": vad["energy_std_db"],
    }

    score = fuzzy_speech_score(fuzzy_in)
    result["speech_score"] = score
    result["classification"] = classify_confidence(score)
    result["fuzzy_inputs"] = fuzzy_in

    # 7. Harmonic structure analysis (from KG: Kellnberger et al. 2013)
    # Note: harmonic analysis on the audio signal itself (not raw IQ)
    # Full IQ harmonic analysis happens in cmd_analyze when pulses are available
    audio_spectrum = np.abs(np.fft.rfft(audio[:min(len(audio), 8192)]))
    audio_freqs = np.fft.rfftfreq(min(len(audio), 8192), d=1.0 / sr)
    if len(audio_spectrum) > 4 and np.max(audio_spectrum) > 0:
        spec_norm = audio_spectrum / np.max(audio_spectrum)
        # Spectral entropy of demodulated audio (low = tonal, high = noise)
        spec_pdf = spec_norm / (np.sum(spec_norm) + 1e-10)
        s_entropy = float(-np.sum(spec_pdf * np.log2(spec_pdf + 1e-10)))
        max_entropy = np.log2(len(spec_pdf))
        result["audio_spectral_entropy"] = round(s_entropy / (max_entropy + 1e-10), 4)
    else:
        result["audio_spectral_entropy"] = 1.0

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  WAV OUTPUT
# ═══════════════════════════════════════════════════════════════════════════

def save_wav(filepath, audio, sr):
    """Write 16-bit mono WAV (no external deps)."""
    audio_16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    data_size = len(audio_16) * 2
    with open(filepath, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVEfmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, sr, sr * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(audio_16.tobytes())


# ═══════════════════════════════════════════════════════════════════════════
#  VISUALIZATION
# ═══════════════════════════════════════════════════════════════════════════

def plot_analysis(audio, sr, analysis, method, output_path):
    """Multi-panel analysis plot."""
    if audio is None or len(audio) < 100:
        return

    plt.style.use("dark_background")
    fig, axes = plt.subplots(4, 1, figsize=(14, 12))
    fig.patch.set_facecolor("#1a1a2e")

    score = analysis.get("speech_score", 0)
    classification = analysis.get("classification", "N/A")
    color = "#ff4444" if score >= 0.7 else "#ffaa00" if score >= 0.4 else \
            "#aaaaaa" if score >= 0.2 else "#44ff44"

    t = np.arange(len(audio)) / sr

    # 1. Waveform
    ax = axes[0]
    ax.plot(t, audio, color="#4fc3f7", linewidth=0.3, alpha=0.7)
    ax.set_title(f"{method} — Score: {score:.3f} [{classification}]",
                 fontsize=12, color=color, fontweight="bold")
    ax.set_ylabel("Amplitude")
    ax.set_facecolor("#0d1117")

    # 2. Spectrogram
    ax = axes[1]
    nperseg = min(NFFT, len(audio) // 4)
    if nperseg > 16:
        f_s, t_s, Sxx = sig.spectrogram(audio, sr, nperseg=nperseg,
                                          noverlap=nperseg // 2)
        Sxx_db = 10 * np.log10(Sxx + 1e-20)
        ax.pcolormesh(t_s, f_s, Sxx_db, shading="gouraud", cmap="magma",
                      vmin=np.percentile(Sxx_db, 5),
                      vmax=np.percentile(Sxx_db, 99))
        ax.set_ylim(0, min(4000, sr / 2))
        # Mark formant regions
        for name, (lo, hi) in FORMANT_RANGES.items():
            if hi < sr / 2:
                ax.axhline(y=(lo + hi) / 2, color="#fff", alpha=0.12,
                           linestyle="--", linewidth=0.5)
                ax.text(t_s[-1] * 1.01, (lo + hi) / 2, name,
                        fontsize=8, color="#fff", alpha=0.4, va="center")
    ax.set_ylabel("Hz")
    ax.set_title("Spectrogram — formant bands would appear as horizontal ridges",
                 fontsize=10, color="#aaa")
    ax.set_facecolor("#0d1117")

    # 3. Modulation spectrum
    ax = axes[2]
    envelope = np.abs(sig.hilbert(audio))
    nyq = sr / 2
    if nyq > 50:
        try:
            b, a = sig.butter(4, 50 / nyq, btype="low")
            envelope = sig.filtfilt(b, a, envelope)
        except Exception:
            pass
    mf = np.abs(np.fft.rfft(envelope))
    mfreqs = np.fft.rfftfreq(len(envelope), 1.0 / sr)
    mask = mfreqs <= 30
    ax.semilogy(mfreqs[mask], mf[mask] ** 2 + 1e-20, color="#4fc3f7", lw=0.8)
    lo, hi = SYLLABLE_RATE_RANGE
    ax.axvspan(lo, hi, alpha=0.15, color="#ff4444",
               label=f"Speech band ({lo}-{hi} Hz)")
    mr = analysis.get("modulation", {}).get("syllable_mod_ratio", 0)
    ax.set_title(f"Modulation Spectrum — ratio: {mr:.1f} (>3 = speech-like)",
                 fontsize=10, color="#aaa")
    ax.set_xlabel("Modulation Freq (Hz)")
    ax.legend(fontsize=8)
    ax.set_facecolor("#0d1117")

    # 4. Pitch track
    ax = axes[3]
    f0s, confs = pitch_track(audio, sr)
    t_p = np.arange(len(f0s)) * FRAME_HOP_S
    vm = confs > 0.3
    if np.any(vm):
        ax.scatter(t_p[vm], f0s[vm], c=confs[vm], cmap="coolwarm",
                   s=3, alpha=0.7, vmin=0, vmax=1)
    ax.axhspan(F0_MIN, F0_MAX, alpha=0.08, color="#44ff44",
               label=f"Voice range ({F0_MIN}-{F0_MAX} Hz)")
    mf0 = analysis.get("pitch", {}).get("mean_f0_hz", 0)
    ax.set_title(f"Pitch (YIN) — F0: {mf0:.1f} Hz", fontsize=10, color="#aaa")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("F0 (Hz)")
    ax.set_ylim(0, F0_MAX + 50)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_facecolor("#0d1117")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()


def plot_batch_summary(all_results, output_dir):
    """Summary plots from batch analysis."""
    if not all_results:
        return

    plt.style.use("dark_background")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor("#1a1a2e")

    methods = ["ENVELOPE", "BURST_PRF", "BURST_PAM"]
    colors = {"ENVELOPE": "#ff6b6b", "BURST_PRF": "#4ecdc4",
              "BURST_PAM": "#ffd93d"}

    # 1. Score distribution
    ax = axes[0, 0]
    for m in methods:
        scores = [r["speech_score"] for r in all_results
                  if r.get("method") == m and "speech_score" in r]
        if scores:
            ax.hist(scores, bins=20, alpha=0.5, label=m,
                    color=colors.get(m, "#aaa"), range=(0, 1))
    ax.axvline(0.4, color="#ffaa00", ls="--", alpha=0.5, label="Possible")
    ax.axvline(0.7, color="#ff4444", ls="--", alpha=0.5, label="Likely")
    ax.set_xlabel("Speech Score")
    ax.set_title("Score Distribution")
    ax.legend(fontsize=7)
    ax.set_facecolor("#0d1117")

    # 2. Modulation ratio
    ax = axes[0, 1]
    for m in methods:
        rs = [r.get("modulation", {}).get("syllable_mod_ratio", 0)
              for r in all_results if r.get("method") == m]
        rs = [x for x in rs if x > 0]
        if rs:
            ax.hist(rs, bins=30, alpha=0.5, label=m, color=colors.get(m, "#aaa"))
    ax.axvline(3.0, color="#ff4444", ls="--", alpha=0.5)
    ax.set_xlabel("Syllable Modulation Ratio")
    ax.set_title("Modulation Ratio Distribution")
    ax.legend(fontsize=7)
    ax.set_facecolor("#0d1117")

    # 3. Pitch
    ax = axes[1, 0]
    for m in methods:
        f0s = [r.get("pitch", {}).get("mean_f0_hz", 0)
               for r in all_results if r.get("method") == m]
        f0s = [x for x in f0s if x > 0]
        if f0s:
            ax.hist(f0s, bins=30, alpha=0.5, label=m, color=colors.get(m, "#aaa"))
    ax.axvspan(85, 180, alpha=0.1, color="#4444ff", label="Male")
    ax.axvspan(165, 255, alpha=0.1, color="#ff44ff", label="Female")
    ax.set_xlabel("Mean F0 (Hz)")
    ax.set_title("Pitch Distribution")
    ax.legend(fontsize=7)
    ax.set_facecolor("#0d1117")

    # 4. Formant vs speech score
    ax = axes[1, 1]
    for m in methods:
        fs = [r.get("formants", {}).get("score", 0)
              for r in all_results if r.get("method") == m and "speech_score" in r]
        ss = [r["speech_score"] for r in all_results
              if r.get("method") == m and "speech_score" in r]
        if fs:
            ax.scatter(fs, ss, alpha=0.3, s=10, label=m,
                       color=colors.get(m, "#aaa"))
    ax.set_xlabel("Formant Score")
    ax.set_ylabel("Speech Score")
    ax.set_title("Formant vs Speech Confidence")
    ax.legend(fontsize=7)
    ax.set_facecolor("#0d1117")

    plt.tight_layout()
    plt.savefig(f"{output_dir}/batch_summary.png", dpi=150,
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"    Plot: {output_dir}/batch_summary.png")


# ═══════════════════════════════════════════════════════════════════════════
#  CLI — ANALYZE
# ═══════════════════════════════════════════════════════════════════════════

def cmd_analyze(args):
    filepath = args.file
    if not os.path.exists(filepath):
        print(f"  Error: {filepath} not found")
        return

    n_concat = getattr(args, "concat", 1) or 1
    output_dir = RESULTS_DIR
    os.makedirs(output_dir, exist_ok=True)
    basename = Path(filepath).stem

    print(f"\n{'=' * 72}")
    print(f"  MICROWAVE PULSE DEMODULATOR & SPEECH PATTERN DETECTOR")
    print(f"{'=' * 72}")
    print(f"  File:        {filepath}")
    print(f"  Concat:      {n_concat} captures")
    print(f"  Sample rate: {SAMPLE_RATE / 1e6:.1f} MSPS")

    # Load
    if n_concat > 1:
        iq = load_iq_concat(filepath, n_concat)
        print(f"  Concatenated {n_concat} captures")
    else:
        iq = load_iq(filepath)

    dur_ms = len(iq) / SAMPLE_RATE * 1000
    print(f"  Samples:     {len(iq)} ({dur_ms:.1f} ms)")

    # Detect pulses & bursts
    pulses, amplitude = detect_pulses(iq)
    print(f"  Pulses:      {len(pulses)}")

    if len(pulses) >= 2:
        bursts = detect_bursts(pulses)
        print(f"  Bursts:      {len(bursts)} (gap threshold: "
              f"{BURST_GAP_SAMPLES / SAMPLE_RATE * 1e6:.0f} µs)")

        for i, b in enumerate(bursts[:5]):
            print(f"    Burst {i}: {b['n_pulses']} pulses, "
                  f"{b['duration_us']:.0f} µs, "
                  f"peak={b['peak_amplitude']:.2f}, "
                  f"energy={b['total_energy']:.0f}")
        if len(bursts) > 5:
            print(f"    ... ({len(bursts) - 5} more)")
    else:
        bursts = []

    # ── Harmonic structure analysis (from KG: Kellnberger et al. 2013) ──
    if len(pulses) >= 4:
        harmonics = analyze_harmonic_structure(pulses, amplitude)
        print(f"\n  ── Harmonic Analysis (2nd harmonic detection) ──")
        print(f"    Score:        {harmonics['harmonic_score']:.3f}")
        print(f"    Harmonics:    {harmonics['n_harmonics']} "
              f"(f0={harmonics['fundamental_hz']:.1f} Hz)")
        print(f"    Entropy:      {harmonics['spectral_entropy']:.3f} "
              f"(0=structured, 1=noise)")
        for h in harmonics.get("harmonics", [])[:5]:
            print(f"      {h['order']}× {h['freq_hz']:.1f} Hz  "
                  f"amp={h['amplitude']:.3f}")
    else:
        harmonics = {"harmonic_score": 0.0, "n_harmonics": 0,
                     "fundamental_hz": 0.0, "harmonics": [],
                     "spectral_entropy": 1.0}

    # ── Demodulate ──
    print(f"\n  ── Demodulation ──")

    demod_results = []

    # Method 1: Envelope (always works — uses full IQ)
    print(f"\n  [ENVELOPE] Power envelope demodulation...")
    audio_env, stats_env = demod_envelope(iq)
    if audio_env is not None:
        effective_sr = stats_env.get("effective_sr", AUDIO_RATE)
        print(f"    Audio: {len(audio_env)} samples "
              f"({len(audio_env) / effective_sr * 1000:.1f} ms @ "
              f"{effective_sr} Hz)")

        wav_path = f"{output_dir}/{basename}_envelope.wav"
        save_wav(wav_path, audio_env, effective_sr)
        print(f"    WAV:   {wav_path}")

        analysis = analyze_audio(audio_env, effective_sr, "ENVELOPE")
        demod_results.append(("ENVELOPE", audio_env, effective_sr, analysis, stats_env))

        _print_score_box(analysis)

        plot_path = f"{output_dir}/{basename}_envelope.png"
        plot_analysis(audio_env, effective_sr, analysis, "ENVELOPE", plot_path)
        print(f"    Plot:  {plot_path}")

    # Method 2: Burst PRF
    if len(bursts) >= 4:
        print(f"\n  [BURST PRF] Burst repetition frequency demodulation...")
        audio_bprf, stats_bprf = demod_burst_prf(bursts)
        if audio_bprf is not None:
            print(f"    Audio: {len(audio_bprf)} samples "
                  f"({len(audio_bprf) / AUDIO_RATE * 1000:.1f} ms)")
            print(f"    Mean BRF: {stats_bprf.get('mean_brf_hz', 0):.0f} Hz")

            wav_path = f"{output_dir}/{basename}_burst_prf.wav"
            save_wav(wav_path, audio_bprf, AUDIO_RATE)

            analysis = analyze_audio(audio_bprf, AUDIO_RATE, "BURST_PRF")
            demod_results.append(("BURST_PRF", audio_bprf, AUDIO_RATE,
                                  analysis, stats_bprf))
            _print_score_box(analysis)

            plot_path = f"{output_dir}/{basename}_burst_prf.png"
            plot_analysis(audio_bprf, AUDIO_RATE, analysis,
                         "BURST_PRF", plot_path)
            print(f"    Plot:  {plot_path}")
        else:
            print(f"    Insufficient burst span for PRF demod")
    else:
        print(f"\n  [BURST PRF] Skipped — need ≥4 bursts (have {len(bursts)})")

    # Method 3: Burst PAM
    if len(bursts) >= 4:
        print(f"\n  [BURST PAM] Burst amplitude modulation demodulation...")
        audio_bpam, stats_bpam = demod_burst_pam(bursts)
        if audio_bpam is not None:
            print(f"    Audio: {len(audio_bpam)} samples "
                  f"({len(audio_bpam) / AUDIO_RATE * 1000:.1f} ms)")

            wav_path = f"{output_dir}/{basename}_burst_pam.wav"
            save_wav(wav_path, audio_bpam, AUDIO_RATE)

            analysis = analyze_audio(audio_bpam, AUDIO_RATE, "BURST_PAM")
            demod_results.append(("BURST_PAM", audio_bpam, AUDIO_RATE,
                                  analysis, stats_bpam))
            _print_score_box(analysis)

            plot_path = f"{output_dir}/{basename}_burst_pam.png"
            plot_analysis(audio_bpam, AUDIO_RATE, analysis,
                         "BURST_PAM", plot_path)
            print(f"    Plot:  {plot_path}")
        else:
            print(f"    Insufficient burst span for PAM demod")
    else:
        print(f"\n  [BURST PAM] Skipped — need ≥4 bursts (have {len(bursts)})")

    # Save results
    json_results = {}
    for method, audio, sr, analysis, stats in demod_results:
        json_results[method] = {
            "stats": {k: v for k, v in stats.items()
                      if not isinstance(v, np.ndarray)},
            "analysis": {k: v for k, v in analysis.items()
                         if not isinstance(v, (np.ndarray, np.floating))},
        }

    json_path = f"{output_dir}/{basename}_results.json"
    with open(json_path, "w") as f:
        json.dump({"file": filepath, "n_pulses": len(pulses),
                    "n_bursts": len(bursts),
                    "timestamp": datetime.now().isoformat(),
                    "methods": json_results}, f, indent=2, default=str)
    print(f"\n  Results: {json_path}")

    # Verdict
    if demod_results:
        best = max(demod_results, key=lambda x: x[3].get("speech_score", 0))
        print(f"\n  ── VERDICT ──")
        print(f"  Best: {best[0]} — score {best[3]['speech_score']:.3f} "
              f"[{best[3]['classification']}]")
    print(f"{'=' * 72}\n")


def _print_score_box(analysis):
    score = analysis.get("speech_score", 0)
    cl = analysis.get("classification", "N/A")
    mr = analysis.get("modulation", {}).get("syllable_mod_ratio", 0)
    fs = analysis.get("formants", {}).get("score", 0)
    f0 = analysis.get("pitch", {}).get("mean_f0_hz", 0)
    pc = analysis.get("pitch", {}).get("mean_confidence", 0)
    vr = analysis.get("vad", {}).get("voiced_ratio", 0)

    print(f"    ┌──────────────────────────────────────────────────┐")
    print(f"    │ SPEECH SCORE: {score:.3f}  [{cl:^20s}]  │")
    print(f"    ├──────────────────────────────────────────────────┤")
    print(f"    │ Modulation ratio:    {mr:>8.2f}  (>3 = speech)      │")
    print(f"    │ Formant score:       {fs:>8.2f}  (>0.5 = resonant)  │")
    print(f"    │ Pitch F0:            {f0:>7.1f} Hz (80-400 = voice)  │")
    print(f"    │ Pitch confidence:    {pc:>8.2f}  (>0.5 = strong)    │")
    print(f"    │ Voiced ratio:        {vr:>8.2f}  (>0.3 = active)    │")
    print(f"    └──────────────────────────────────────────────────┘")


# ═══════════════════════════════════════════════════════════════════════════
#  CLI — BATCH
# ═══════════════════════════════════════════════════════════════════════════

def cmd_batch(args):
    capture_dir = args.dir or CAPTURES_DIR
    top_n = args.top or 20
    n_concat = getattr(args, "concat", 1) or 1

    iq_files = sorted(glob.glob(f"{capture_dir}/sentinel_*.iq"))
    if not iq_files:
        print(f"  No IQ files found in {capture_dir}/")
        return

    output_dir = RESULTS_DIR
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'=' * 72}")
    print(f"  BATCH SPEECH PATTERN ANALYSIS")
    print(f"{'=' * 72}")
    print(f"  Captures: {len(iq_files)} files")
    print(f"  Analyzing top {top_n} by size, concat={n_concat}")

    iq_files.sort(key=lambda f: os.path.getsize(f), reverse=True)
    iq_files = iq_files[:top_n]

    all_results = []
    summary = []

    for idx, fp in enumerate(iq_files):
        bn = Path(fp).stem
        sz = os.path.getsize(fp)
        print(f"\n  [{idx + 1}/{len(iq_files)}] {bn} ({sz / 1024:.0f} KB)")

        try:
            if n_concat > 1:
                iq = load_iq_concat(fp, n_concat)
            else:
                iq = load_iq(fp)

            pulses, amp = detect_pulses(iq)
            if len(pulses) < 5:
                print(f"    Skipped: {len(pulses)} pulses")
                continue

            bursts = detect_bursts(pulses)

            # Envelope (always)
            audio, stats = demod_envelope(iq)
            if audio is not None:
                sr = stats.get("effective_sr", AUDIO_RATE)
                a = analyze_audio(audio, sr, "ENVELOPE")
                a["file"] = bn
                all_results.append(a)

                s = a["speech_score"]
                mr = a.get("modulation", {}).get("syllable_mod_ratio", 0)
                tag = " ***" if s >= 0.7 else " *" if s >= 0.4 else ""
                summary.append((s, f"    ENV: {bn} score={s:.3f} mod={mr:.1f}{tag}"))

                if s >= 0.4:
                    save_wav(f"{output_dir}/{bn}_envelope.wav", audio, sr)

            # Burst methods
            if len(bursts) >= 4:
                for name, fn in [("BURST_PRF", demod_burst_prf),
                                  ("BURST_PAM", demod_burst_pam)]:
                    audio, stats = fn(bursts)
                    if audio is not None and len(audio) > 100:
                        a = analyze_audio(audio, AUDIO_RATE, name)
                        a["file"] = bn
                        all_results.append(a)

                        s = a["speech_score"]
                        if s >= 0.4:
                            save_wav(f"{output_dir}/{bn}_{name.lower()}.wav",
                                     audio, AUDIO_RATE)

            # Per-file best
            file_res = [r for r in all_results if r.get("file") == bn]
            if file_res:
                best = max(file_res, key=lambda r: r.get("speech_score", 0))
                bs = best["speech_score"]
                bm = best["method"]
                tag = " <<<" if bs >= 0.4 else ""
                print(f"    Best: {bm} score={bs:.3f}{tag}")

        except Exception as e:
            print(f"    Error: {e}")

    # Summary
    print(f"\n{'=' * 72}")
    print(f"  TOP SCORES")
    print(f"{'=' * 72}")
    summary.sort(reverse=True)
    for _, line in summary[:30]:
        print(line)

    if all_results:
        scores = [r.get("speech_score", 0) for r in all_results]
        likely = sum(1 for s in scores if s >= 0.7)
        possible = sum(1 for s in scores if 0.4 <= s < 0.7)
        weak = sum(1 for s in scores if 0.2 <= s < 0.4)
        none_ = sum(1 for s in scores if s < 0.2)

        print(f"\n  Breakdown ({len(scores)} analyses):")
        print(f"    LIKELY SPEECH:   {likely:4d}  ({100 * likely / len(scores):.1f}%)")
        print(f"    POSSIBLE:        {possible:4d}  ({100 * possible / len(scores):.1f}%)")
        print(f"    WEAK:            {weak:4d}  ({100 * weak / len(scores):.1f}%)")
        print(f"    NONE:            {none_:4d}  ({100 * none_ / len(scores):.1f}%)")

        plot_batch_summary(all_results, output_dir)

    # Save JSON
    clean = []
    for r in all_results:
        c = {}
        for k, v in r.items():
            if isinstance(v, dict):
                c[k] = {sk: sv for sk, sv in v.items()
                        if not isinstance(sv, np.ndarray)}
            elif not isinstance(v, np.ndarray):
                c[k] = v
        clean.append(c)

    with open(f"{output_dir}/batch_results.json", "w") as f:
        json.dump({"timestamp": datetime.now().isoformat(),
                    "n_files": len(iq_files), "results": clean},
                  f, indent=2, default=str)
    print(f"\n  Results: {output_dir}/batch_results.json")
    print(f"{'=' * 72}\n")


def cmd_summary(args):
    jp = f"{RESULTS_DIR}/batch_results.json"
    if not os.path.exists(jp):
        print("  No batch results. Run: python demod_pulses.py batch")
        return

    with open(jp) as f:
        data = json.load(f)

    results = data.get("results", [])
    if not results:
        print("  No results.")
        return

    print(f"\n{'=' * 72}")
    print(f"  DEMODULATION SUMMARY — {data.get('n_files', '?')} files")
    print(f"{'=' * 72}")

    for method in ["ENVELOPE", "BURST_PRF", "BURST_PAM"]:
        mr = [r for r in results if r.get("method") == method]
        if not mr:
            continue

        scores = [r.get("speech_score", 0) for r in mr]
        mods = [r.get("modulation", {}).get("syllable_mod_ratio", 0) for r in mr]
        f0s = [r.get("pitch", {}).get("mean_f0_hz", 0) for r in mr]
        f0v = [f for f in f0s if f > 0]

        print(f"\n  ── {method} ──")
        print(f"    Analyzed:  {len(mr)}")
        print(f"    Score:     mean={np.mean(scores):.3f}  "
              f"max={np.max(scores):.3f}")
        print(f"    Mod ratio: mean={np.mean(mods):.2f}  max={np.max(mods):.2f}")
        if f0v:
            print(f"    F0:        mean={np.mean(f0v):.0f} Hz  "
                  f"range={np.min(f0v):.0f}-{np.max(f0v):.0f}")

        likely = sum(1 for s in scores if s >= 0.7)
        possible = sum(1 for s in scores if 0.4 <= s < 0.7)
        print(f"    Likely: {likely}  Possible: {possible}")

    print(f"{'=' * 72}\n")


# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Microwave Pulse Demodulator & Speech Pattern Detector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demod_pulses.py analyze captures/sentinel_826MHz_014542.iq
  python demod_pulses.py analyze captures/sentinel_826MHz_014542.iq --concat 10
  python demod_pulses.py batch --top 50
  python demod_pulses.py batch --top 100 --concat 5
  python demod_pulses.py summary
        """)

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("analyze", help="Analyze single IQ file")
    p.add_argument("file", help="Path to .iq file")
    p.add_argument("--concat", type=int, default=1,
                   help="Concatenate N sequential captures (default: 1)")

    p = sub.add_parser("batch", help="Batch analyze captures")
    p.add_argument("--dir", default=None)
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--concat", type=int, default=1,
                   help="Concatenate N sequential captures per analysis")

    sub.add_parser("summary", help="Summarize batch results")

    args = parser.parse_args()
    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "summary":
        cmd_summary(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

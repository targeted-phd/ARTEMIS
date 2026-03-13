#!/usr/bin/env python3
"""
Forward Model: Speech → Microwave Pulse Encoding → Simulated RTL-SDR Capture

Takes known speech, applies published encoding transforms from the microwave
auditory effect literature, simulates RTL-SDR capture, and compares features
with real observed data to determine if observed signals match any known
encoding scheme.

This is a forensic analysis tool for RF signal identification.

Encoding methods implemented (from published literature):
  1. AM Envelope — pulse amplitudes ∝ |s(t)|
  2. PRF Modulation — pulse rate = f(s(t))
  3. Lin/MEDUSA derivative — perceived audio ∝ dP/dt, so P(t) ∝ ∫s(t)dt
  4. Thermoelastic inverse — full physical model with skull transfer function

References:
  Foster et al. (2021) Frontiers in Public Health 9:788613
  Watanabe et al. (2000) IEEE Trans MTT 48(11):2126
  Chou & Guy (1979) Radio Science 14(6S):193
  Lin (2002) IEEE Microwave Magazine, June 2002
  Hubler et al. (2020) Frontiers in Neurology 11:753

Usage:
  python forward_model.py test                    # Built-in test speech
  python forward_model.py encode <speech.wav>     # Encode specific audio
  python forward_model.py compare                 # Compare all methods vs real
  python forward_model.py all                     # Full pipeline
"""

import os
import sys
import json
import struct
import argparse
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
from scipy import signal as sig
from scipy.fft import rfft, rfftfreq

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ── Physical constants from literature ───────────────────────────────────

# Foster et al. (2021) Table 1 — tissue parameters at ~900 MHz
TISSUE = {
    "density_kg_m3": 1050,          # soft tissue
    "specific_heat_J_kgC": 3860,    # C_h
    "thermal_expansion_1C": 4.1e-5, # α (60% of water)
    "sound_speed_m_s": 1500,        # v_s in soft tissue
    "gruneisen": 0.2,               # Γ = β·v_s²/C_p
    "conductivity_S_m": 0.772,      # σ at 915 MHz (brain)
    "permittivity_rel": 45.7,       # ε_r at 915 MHz (brain)
}

# Frequency-dependent parameters from Foster Table 1
FREQ_PARAMS = {
    900: {"L_m": 0.0195, "T_tr": 0.47, "tau_s_us": 13, "p0_Pa": 10,
           "f_acoustic_kHz": 12},
    1000: {"L_m": 0.0041, "T_tr": 0.48, "tau_s_us": 3, "p0_Pa": 23,
            "f_acoustic_kHz": 58},
}

# Skull resonance
SKULL_RESONANCE_HZ = 8000   # 7-9 kHz (Watanabe 2000, human head 14cm)
SKULL_Q = 3                 # Quality factor (estimated from Fig 14)

# Chou & Guy (1979) — threshold data
PERCEPTION_THRESHOLD = {
    "energy_density_mJ_kg": 6.0,     # For pulses < 30 µs
    "peak_power_mW_cm2": 93.6,       # For pulses > 70 µs
}

# RTL-SDR capture parameters
SAMPLE_RATE = 2_400_000   # 2.4 MSPS
AUDIO_RATE = 16_000
RTL_BITS = 8
RTL_NOISE_FLOOR_DB = -30  # Relative noise floor

# Pulse parameters (from observed data)
PULSE_WIDTH_US = 5.0       # Typical observed pulse width
PULSE_WIDTH_SAMPLES = int(PULSE_WIDTH_US * 1e-6 * SAMPLE_RATE)

# Output
RESULTS_DIR = "results/forward_model"
CAPTURES_DIR = "captures"


# ═══════════════════════════════════════════════════════════════════════════
#  SPEECH GENERATION / LOADING
# ═══════════════════════════════════════════════════════════════════════════

def generate_test_speech(duration_s=2.0, sr=AUDIO_RATE):
    """
    Generate synthetic speech-like signal for testing.
    Concatenates vowel-like formant patterns with pitch modulation.
    """
    t = np.arange(int(sr * duration_s)) / sr

    # Fundamental frequency (pitch) — varies like natural speech
    f0_base = 120  # Hz, male voice
    f0_mod = 20 * np.sin(2 * np.pi * 3 * t)  # 3 Hz vibrato
    f0 = f0_base + f0_mod

    # Glottal pulse train (impulse-like source)
    phase = np.cumsum(f0 / sr) * 2 * np.pi
    glottal = np.sin(phase) * 0.5 + np.sin(2 * phase) * 0.3 + \
              np.sin(3 * phase) * 0.1

    # Vowel sequence: /a/ → /i/ → /u/ → /a/
    # Formant frequencies for each vowel
    vowels = [
        {"F1": 730, "F2": 1090, "F3": 2440},  # /a/ as in "father"
        {"F1": 270, "F2": 2290, "F3": 3010},  # /i/ as in "heed"
        {"F1": 300, "F2": 870, "F3": 2240},   # /u/ as in "who"
        {"F1": 730, "F2": 1090, "F3": 2440},  # /a/ again
    ]

    n_vowels = len(vowels)
    segment_len = len(t) // n_vowels
    audio = np.zeros_like(t)

    for i, vowel in enumerate(vowels):
        start = i * segment_len
        end = start + segment_len if i < n_vowels - 1 else len(t)
        seg_t = t[start:end] - t[start]

        # Resonant filter (2nd order for each formant)
        seg = glottal[start:end].copy()
        for fname, freq in vowel.items():
            bw = 80  # bandwidth Hz
            nyq = sr / 2
            if freq < nyq:
                low = max(1, freq - bw / 2) / nyq
                high = min(0.999, (freq + bw / 2) / nyq)
                if low < high:
                    try:
                        b, a = sig.butter(2, [low, high], btype="band")
                        filtered = sig.lfilter(b, a, seg)
                        audio[start:end] += filtered * 0.3
                    except Exception:
                        pass

    # Add syllable-rate amplitude modulation (3-5 Hz)
    syllable_env = 0.5 + 0.5 * np.sin(2 * np.pi * 4 * t)
    audio *= syllable_env

    # Add some silence gaps (like natural speech pauses)
    for gap_start in [0.45, 1.05, 1.55]:
        gap_center = int(gap_start * sr)
        gap_width = int(0.08 * sr)
        s = max(0, gap_center - gap_width // 2)
        e = min(len(audio), gap_center + gap_width // 2)
        fade = np.linspace(1, 0, (e - s) // 2)
        audio[s:s + len(fade)] *= fade
        audio[e - len(fade):e] *= fade[::-1]
        audio[s + len(fade):e - len(fade)] = 0

    # Normalize
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    return audio, sr


def load_wav(filepath):
    """Load WAV file (16-bit mono)."""
    with open(filepath, "rb") as f:
        riff = f.read(4)
        if riff != b"RIFF":
            raise ValueError("Not a WAV file")
        f.read(4)  # file size
        f.read(4)  # WAVE

        # Find fmt chunk
        while True:
            chunk_id = f.read(4)
            chunk_size = struct.unpack("<I", f.read(4))[0]
            if chunk_id == b"fmt ":
                fmt_data = f.read(chunk_size)
                fmt_code = struct.unpack("<H", fmt_data[0:2])[0]
                n_channels = struct.unpack("<H", fmt_data[2:4])[0]
                sr = struct.unpack("<I", fmt_data[4:8])[0]
                bits = struct.unpack("<H", fmt_data[14:16])[0]
                break
            else:
                f.read(chunk_size)

        # Find data chunk
        while True:
            chunk_id = f.read(4)
            if not chunk_id:
                raise ValueError("No data chunk found")
            chunk_size = struct.unpack("<I", f.read(4))[0]
            if chunk_id == b"data":
                raw = f.read(chunk_size)
                break
            else:
                f.read(chunk_size)

    if bits == 16:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    elif bits == 8:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128
    else:
        raise ValueError(f"Unsupported bit depth: {bits}")

    if n_channels > 1:
        samples = samples[::n_channels]  # Take first channel

    return samples, sr


def resample_audio(audio, sr_in, sr_out):
    """Resample audio to target rate."""
    if sr_in == sr_out:
        return audio
    ratio = sr_out / sr_in
    n_out = int(len(audio) * ratio)
    return sig.resample(audio, n_out)


# ═══════════════════════════════════════════════════════════════════════════
#  ENCODING TRANSFORMS
# ═══════════════════════════════════════════════════════════════════════════

def skull_transfer_function(n_samples, sr):
    """
    Model skull as bandpass resonator at ~8 kHz.
    Watanabe (2000): dominant frequency 7-9 kHz.
    Returns frequency-domain transfer function.
    """
    freqs = rfftfreq(n_samples, 1.0 / sr)
    # Bandpass centered at skull resonance
    f0 = SKULL_RESONANCE_HZ
    Q = SKULL_Q
    bw = f0 / Q
    H = 1.0 / (1.0 + 1j * Q * (freqs / f0 - f0 / (freqs + 1e-10)))
    H[0] = 0  # No DC
    return H


def encode_am_envelope(speech, sr, pulse_rate_hz=10000, pulse_width_us=5.0,
                       duration_s=None):
    """
    AM Envelope encoding: pulse amplitudes ∝ |s(t)|

    Simplest encoding — the speech waveform directly modulates the
    amplitude of a fixed-rate pulse train.

    Returns: pulse_times (s), pulse_amplitudes, pulse_widths (s)
    """
    if duration_s is None:
        duration_s = len(speech) / sr

    # Resample speech to pulse rate for amplitude lookup
    n_pulses = int(duration_s * pulse_rate_hz)
    pulse_times = np.arange(n_pulses) / pulse_rate_hz

    # Interpolate speech envelope at pulse times
    speech_times = np.arange(len(speech)) / sr
    speech_env = np.abs(speech)  # Rectified speech = amplitude envelope

    # Smooth envelope
    env_sr = sr
    cutoff = min(pulse_rate_hz / 4, sr / 2 - 1)
    if cutoff > 1:
        try:
            b, a = sig.butter(4, cutoff / (env_sr / 2), btype="low")
            speech_env = sig.filtfilt(b, a, speech_env)
        except Exception:
            pass

    # Interpolate to pulse times
    from scipy.interpolate import interp1d
    interp_fn = interp1d(speech_times, speech_env, kind="linear",
                         bounds_error=False, fill_value=0)
    amplitudes = interp_fn(pulse_times)

    # Normalize amplitudes to [0.1, 1.0] (never zero — always transmitting)
    amp_max = np.max(amplitudes)
    if amp_max > 0:
        amplitudes = 0.1 + 0.9 * amplitudes / amp_max

    widths = np.full(n_pulses, pulse_width_us * 1e-6)

    return pulse_times, amplitudes, widths, {
        "method": "AM_ENVELOPE",
        "pulse_rate_hz": pulse_rate_hz,
        "n_pulses": n_pulses,
        "duration_s": duration_s,
    }


def encode_prf_modulation(speech, sr, f_base_hz=7000, mod_depth_hz=3000,
                          pulse_width_us=5.0, duration_s=None):
    """
    PRF Modulation: pulse repetition rate encodes the speech signal.

    The perceived audio frequency = PRF. So modulating the PRF with
    speech produces perceived speech audio.

    PRF(t) = f_base + mod_depth * s(t)

    Lin (2002): "a train of microwave pulses to the head can be sensed
    as an audible tune, with a pitch corresponding to the pulse repetition rate"
    """
    if duration_s is None:
        duration_s = len(speech) / sr

    speech_times = np.arange(len(speech)) / sr
    from scipy.interpolate import interp1d
    interp_fn = interp1d(speech_times, speech, kind="linear",
                         bounds_error=False, fill_value=0)

    # Generate pulses with variable spacing
    pulse_times = []
    t = 0
    while t < duration_s:
        pulse_times.append(t)
        # Current speech value
        s_val = float(interp_fn(t))
        # Instantaneous PRF
        prf = f_base_hz + mod_depth_hz * np.clip(s_val, -1, 1)
        prf = max(100, prf)  # Floor at 100 Hz
        t += 1.0 / prf

    pulse_times = np.array(pulse_times)
    amplitudes = np.ones(len(pulse_times))  # Constant amplitude
    widths = np.full(len(pulse_times), pulse_width_us * 1e-6)

    return pulse_times, amplitudes, widths, {
        "method": "PRF_MODULATION",
        "f_base_hz": f_base_hz,
        "mod_depth_hz": mod_depth_hz,
        "n_pulses": len(pulse_times),
        "mean_prf": len(pulse_times) / duration_s,
        "duration_s": duration_s,
    }


def encode_lin_medusa(speech, sr, pulse_rate_hz=10000, pulse_width_us=5.0,
                      duration_s=None):
    """
    Lin/MEDUSA Time-Derivative Encoding.

    The key insight from Lin's thermoelastic theory:
      perceived_audio ∝ dP/dt  (time derivative of pressure)

    Therefore, to encode speech s(t), the power envelope must follow
    the INTEGRAL of s(t):
      P(t) ∝ ∫₀ᵗ s(τ) dτ

    After thermoelastic transduction and the tissue's natural
    differentiation (dP/dt), the perceived audio = s(t).

    Additionally, the skull acts as a bandpass filter at 7-9 kHz,
    which naturally limits the bandwidth.
    """
    if duration_s is None:
        duration_s = len(speech) / sr

    # Step 1: Pre-filter speech through inverse skull transfer function
    # (compensate for skull bandpass to get flat response at cochlea)
    n = len(speech)
    H_skull = skull_transfer_function(n, sr)
    H_inv = np.conj(H_skull) / (np.abs(H_skull) ** 2 + 0.01)  # Wiener inverse
    speech_compensated = np.real(np.fft.irfft(
        rfft(speech) * H_inv, n=n))

    # Step 2: Integrate speech to get power envelope
    # P(t) = P_base + k * ∫s(t)dt
    integral = np.cumsum(speech_compensated) / sr

    # Remove drift (high-pass the integral to prevent DC buildup)
    if len(integral) > sr:
        b_hp, a_hp = sig.butter(2, 1.0 / (sr / 2), btype="high")
        integral = sig.filtfilt(b_hp, a_hp, integral)

    # Normalize to [0.1, 1.0]
    int_range = np.max(integral) - np.min(integral)
    if int_range > 0:
        integral = (integral - np.min(integral)) / int_range
        integral = 0.1 + 0.9 * integral

    # Step 3: Sample at pulse rate
    n_pulses = int(duration_s * pulse_rate_hz)
    pulse_times = np.arange(n_pulses) / pulse_rate_hz

    from scipy.interpolate import interp1d
    speech_times = np.arange(len(integral)) / sr
    interp_fn = interp1d(speech_times, integral, kind="linear",
                         bounds_error=False, fill_value=0.1)
    amplitudes = interp_fn(pulse_times)

    widths = np.full(n_pulses, pulse_width_us * 1e-6)

    return pulse_times, amplitudes, widths, {
        "method": "LIN_MEDUSA",
        "pulse_rate_hz": pulse_rate_hz,
        "n_pulses": n_pulses,
        "duration_s": duration_s,
        "skull_resonance_hz": SKULL_RESONANCE_HZ,
        "encoding": "P(t) = integral(s(t)), perceived = dP/dt = s(t)",
    }


def encode_thermoelastic_inverse(speech, sr, carrier_freq_mhz=900,
                                 pulse_rate_hz=10000, pulse_width_us=5.0,
                                 duration_s=None):
    """
    Full Thermoelastic Inverse Model.

    Given desired acoustic pressure at cochlea, back-calculate the
    required incident RF power using the full Foster (2021) model:

      p(x) = Γ · ρ · SAR(x) · τ
      SAR(x) = I₀ · T_tr / (ρ · L) · e^(-x/L)

    With skull transfer function applied.
    """
    if duration_s is None:
        duration_s = len(speech) / sr

    # Get frequency-dependent parameters
    params = FREQ_PARAMS.get(carrier_freq_mhz, FREQ_PARAMS[900])
    L = params["L_m"]           # penetration depth
    T_tr = params["T_tr"]       # transmission coefficient
    Gamma = TISSUE["gruneisen"]  # Grüneisen parameter
    rho = TISSUE["density_kg_m3"]
    tau = pulse_width_us * 1e-6

    # Step 1: Desired acoustic pressure = speech (scaled to µPa range)
    # Scale speech to realistic cochlea pressure range (0-100 µPa)
    p_desired = speech * 100e-6  # µPa

    # Step 2: Apply inverse skull transfer function
    n = len(p_desired)
    H_skull = skull_transfer_function(n, sr)
    H_inv = np.conj(H_skull) / (np.abs(H_skull) ** 2 + 0.01)
    p_pre_skull = np.real(np.fft.irfft(rfft(p_desired) * H_inv, n=n))

    # Step 3: Invert thermoelastic equation
    # p = Γ · ρ · SAR · τ  →  SAR = p / (Γ · ρ · τ)
    SAR_required = p_pre_skull / (Gamma * rho * tau + 1e-30)

    # Step 4: SAR → incident power
    # SAR(surface) = I₀ · T_tr / (ρ · L)  →  I₀ = SAR · ρ · L / T_tr
    I0_required = SAR_required * rho * L / (T_tr + 1e-10)

    # Step 5: Normalize to valid amplitude range
    I0_abs = np.abs(I0_required)
    I0_max = np.max(I0_abs)
    if I0_max > 0:
        amplitudes_continuous = I0_abs / I0_max
        amplitudes_continuous = 0.1 + 0.9 * amplitudes_continuous

    # Step 6: Sample at pulse rate
    n_pulses = int(duration_s * pulse_rate_hz)
    pulse_times = np.arange(n_pulses) / pulse_rate_hz

    from scipy.interpolate import interp1d
    speech_times = np.arange(len(amplitudes_continuous)) / sr
    interp_fn = interp1d(speech_times, amplitudes_continuous, kind="linear",
                         bounds_error=False, fill_value=0.1)
    amplitudes = interp_fn(pulse_times)

    widths = np.full(n_pulses, pulse_width_us * 1e-6)

    return pulse_times, amplitudes, widths, {
        "method": "THERMOELASTIC_INVERSE",
        "carrier_freq_mhz": carrier_freq_mhz,
        "pulse_rate_hz": pulse_rate_hz,
        "n_pulses": n_pulses,
        "L_m": L,
        "T_tr": T_tr,
        "Gamma": Gamma,
        "duration_s": duration_s,
        "encoding": "p_desired → SAR → I₀ via Foster (2021) model",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  RTL-SDR CAPTURE SIMULATION
# ═══════════════════════════════════════════════════════════════════════════

def simulate_rtl_capture(pulse_times, pulse_amplitudes, pulse_widths,
                         duration_s=None, capture_len_ms=200):
    """
    Simulate an RTL-SDR IQ capture of the pulse train.

    Generates 8-bit IQ data matching the RTL-SDR Blog V4 format:
    - 2.4 MSPS
    - 8-bit unsigned, interleaved I/Q
    - Realistic noise floor
    - DC offset
    """
    if duration_s is None:
        duration_s = float(np.max(pulse_times)) + 0.01

    # Take a capture_len_ms window from the middle of the signal
    capture_duration = capture_len_ms / 1000.0
    n_samples = int(capture_duration * SAMPLE_RATE)

    # Window center
    center_time = duration_s / 2
    start_time = max(0, center_time - capture_duration / 2)

    # Generate IQ baseband — pulses at carrier appear as amplitude bursts
    iq = np.zeros(n_samples, dtype=np.complex64)

    # Add noise floor (Gaussian, matched to RTL-SDR characteristics)
    noise_power = 10 ** (RTL_NOISE_FLOOR_DB / 10)
    noise = np.sqrt(noise_power / 2) * (
        np.random.randn(n_samples) + 1j * np.random.randn(n_samples))
    iq += noise

    # Add pulses
    for i in range(len(pulse_times)):
        t_pulse = pulse_times[i]
        if t_pulse < start_time or t_pulse > start_time + capture_duration:
            continue

        sample_idx = int((t_pulse - start_time) * SAMPLE_RATE)
        width_samples = max(1, int(pulse_widths[i] * SAMPLE_RATE))
        amp = pulse_amplitudes[i]

        # Pulse shape: raised cosine (realistic)
        end_idx = min(sample_idx + width_samples, n_samples)
        if sample_idx < 0:
            continue
        actual_width = end_idx - sample_idx
        if actual_width <= 0:
            continue

        pulse_shape = amp * np.ones(actual_width)
        # Smooth edges
        if actual_width > 4:
            taper = min(actual_width // 4, 3)
            pulse_shape[:taper] *= np.linspace(0, 1, taper)
            pulse_shape[-taper:] *= np.linspace(1, 0, taper)

        # Add as I component (carrier at 0 Hz in baseband)
        iq[sample_idx:end_idx] += pulse_shape

    # Quantize to 8-bit (RTL-SDR format)
    i_part = np.real(iq)
    q_part = np.imag(iq)

    # Scale to use 8-bit range
    max_val = max(np.max(np.abs(i_part)), np.max(np.abs(q_part)), 1e-10)
    scale = 100 / max_val  # Use ~80% of dynamic range
    i_quant = np.clip(np.round(i_part * scale + 127.5), 0, 255).astype(np.uint8)
    q_quant = np.clip(np.round(q_part * scale + 127.5), 0, 255).astype(np.uint8)

    # Interleave I/Q
    raw = np.empty(2 * n_samples, dtype=np.uint8)
    raw[0::2] = i_quant
    raw[1::2] = q_quant

    return raw, {
        "n_samples": n_samples,
        "start_time": start_time,
        "capture_duration": capture_duration,
        "sample_rate": SAMPLE_RATE,
    }


def load_iq_from_raw(raw_data):
    """Convert raw 8-bit RTL-SDR data to complex IQ."""
    iq = (raw_data[0::2].astype(np.float32) - 127.5) + \
         1j * (raw_data[1::2].astype(np.float32) - 127.5)
    return iq


# ═══════════════════════════════════════════════════════════════════════════
#  FEATURE EXTRACTION (matching demod_pulses.py analysis)
# ═══════════════════════════════════════════════════════════════════════════

def compute_features(iq):
    """
    Extract features from IQ capture — same metrics as the real data analysis.
    """
    amplitude = np.abs(iq)

    # Kurtosis
    mean_a = np.mean(amplitude)
    std_a = np.std(amplitude)
    kurtosis = float(np.mean(((amplitude - mean_a) / (std_a + 1e-10)) ** 4))

    # PAPR
    peak_power = float(np.max(amplitude ** 2))
    mean_power = float(np.mean(amplitude ** 2))
    papr_db = float(10 * np.log10(peak_power / (mean_power + 1e-20)))

    # Pulse detection
    threshold = mean_a + 4 * std_a
    above = amplitude > threshold
    n_above = int(np.sum(above))

    # Burst detection (simplified)
    edges = np.diff(above.astype(np.int8))
    starts = np.where(edges == 1)[0]
    stops = np.where(edges == -1)[0]

    if len(starts) > 0 and len(stops) > 0:
        if starts[0] > stops[0]:
            stops = stops[1:]
        min_len = min(len(starts), len(stops))
        starts = starts[:min_len]
        stops = stops[:min_len]
        widths = stops - starts
        valid = widths >= 3
        n_pulses = int(np.sum(valid))

        # Group into bursts (gap > 100 µs = 240 samples)
        if n_pulses > 1:
            valid_starts = starts[valid]
            valid_stops = stops[valid]
            gaps = np.diff(valid_starts)
            burst_boundaries = np.where(gaps > 240)[0]
            n_bursts = len(burst_boundaries) + 1
        else:
            n_bursts = 1 if n_pulses > 0 else 0
    else:
        n_pulses = 0
        n_bursts = 0

    # Spectral flatness
    spectrum = np.abs(np.fft.rfft(amplitude))
    spectrum = spectrum[1:]  # Skip DC
    geo_mean = np.exp(np.mean(np.log(spectrum + 1e-20)))
    arith_mean = np.mean(spectrum)
    spectral_flatness = float(geo_mean / (arith_mean + 1e-20))

    return {
        "kurtosis": kurtosis,
        "papr_db": papr_db,
        "n_pulses": n_pulses,
        "n_bursts": n_bursts,
        "spectral_flatness": spectral_flatness,
        "mean_amplitude": float(mean_a),
        "std_amplitude": float(std_a),
    }


def compute_windowed_features(iq, n_windows=3):
    """
    Temporal windowing analysis — from KG: EEG microwave studies.

    From "Changes in human EEG caused by low level modulated microwave
    stimulation": "The possibility of detection of a small effect depends
    a great deal on the method of EEG analysis. Results might differ
    depending on whether comparison intervals from the beginning, the
    middle, or the end of the stimulation segments are selected."

    Splits the capture into temporal windows and computes features for each.
    Non-stationary features (features that change across windows) suggest
    intentional modulation rather than constant interference.

    Returns per-window features and stationarity metrics.
    """
    n = len(iq)
    win_size = n // n_windows
    if win_size < 1000:
        return {"windows": [], "stationarity": {}}

    windows = []
    for i in range(n_windows):
        start = i * win_size
        end = start + win_size if i < n_windows - 1 else n
        segment = iq[start:end]
        features = compute_features(segment)
        features["window"] = i
        features["window_label"] = ["beginning", "middle", "end"][i] if n_windows == 3 else f"w{i}"
        features["start_ms"] = round(start / SAMPLE_RATE * 1000, 2)
        features["end_ms"] = round(end / SAMPLE_RATE * 1000, 2)
        windows.append(features)

    # Stationarity analysis: how much do features vary across windows?
    keys = ["kurtosis", "papr_db", "n_pulses", "n_bursts",
            "spectral_flatness", "mean_amplitude", "std_amplitude"]
    stationarity = {}
    for key in keys:
        values = [w[key] for w in windows if key in w]
        if len(values) >= 2:
            arr = np.array(values)
            mean_val = float(np.mean(arr))
            std_val = float(np.std(arr))
            cv = std_val / (abs(mean_val) + 1e-10)  # coefficient of variation
            # Range ratio: (max-min)/mean
            range_ratio = float((np.max(arr) - np.min(arr)) / (abs(mean_val) + 1e-10))
            stationarity[key] = {
                "mean": round(mean_val, 4),
                "std": round(std_val, 4),
                "cv": round(cv, 4),
                "range_ratio": round(range_ratio, 4),
                "values": [round(v, 4) for v in values],
            }

    # Overall non-stationarity score (high = features change across windows)
    # Weighted average of coefficient of variation across key features
    cv_weights = {"kurtosis": 0.3, "papr_db": 0.2, "n_pulses": 0.2,
                  "spectral_flatness": 0.15, "std_amplitude": 0.15}
    weighted_cv = 0.0
    total_weight = 0.0
    for key, weight in cv_weights.items():
        if key in stationarity:
            weighted_cv += stationarity[key]["cv"] * weight
            total_weight += weight
    if total_weight > 0:
        nonstationarity_score = min(1.0, weighted_cv / total_weight)
    else:
        nonstationarity_score = 0.0

    return {
        "windows": windows,
        "stationarity": stationarity,
        "nonstationarity_score": round(float(nonstationarity_score), 4),
        "n_windows": n_windows,
    }


def run_demod_analysis(iq):
    """
    Run the demod_pulses.py analysis pipeline on simulated IQ data.
    Returns speech scores for each demod method.
    """
    try:
        # Import from demod_pulses.py
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from demod_pulses import (demod_envelope, detect_pulses, detect_bursts,
                                  demod_burst_prf, demod_burst_pam,
                                  analyze_audio)

        results = {}

        # Envelope demod
        audio_env, stats_env = demod_envelope(iq)
        if audio_env is not None:
            effective_sr = stats_env.get("effective_sr", AUDIO_RATE)
            analysis = analyze_audio(audio_env, effective_sr, "ENVELOPE")
            results["ENVELOPE"] = analysis

        # Pulse/burst methods
        pulses, amplitude = detect_pulses(iq)
        if len(pulses) >= 2:
            bursts = detect_bursts(pulses)
            if len(bursts) >= 4:
                # Burst PRF
                audio_bprf, stats_bprf = demod_burst_prf(bursts)
                if audio_bprf is not None and len(audio_bprf) > 100:
                    analysis = analyze_audio(audio_bprf, AUDIO_RATE, "BURST_PRF")
                    results["BURST_PRF"] = analysis

                # Burst PAM
                audio_bpam, stats_bpam = demod_burst_pam(bursts)
                if audio_bpam is not None and len(audio_bpam) > 100:
                    analysis = analyze_audio(audio_bpam, AUDIO_RATE, "BURST_PAM")
                    results["BURST_PAM"] = analysis

        return results

    except ImportError as e:
        print(f"    Warning: Could not import demod_pulses: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════════════════
#  COMPARISON WITH REAL DATA
# ═══════════════════════════════════════════════════════════════════════════

def load_real_data_features():
    """Load features from real batch analysis."""
    batch_path = "results/demod/batch_results.json"
    if not os.path.exists(batch_path):
        return None

    with open(batch_path) as f:
        data = json.load(f)

    results = data.get("results", [])
    if not results:
        return None

    # Aggregate real data features
    real_features = {
        "speech_scores": [],
        "mod_ratios": [],
        "formant_scores": [],
        "pitch_f0s": [],
        "voiced_ratios": [],
    }

    for r in results:
        if "speech_score" in r:
            real_features["speech_scores"].append(r["speech_score"])
        mod = r.get("modulation", {})
        if "syllable_mod_ratio" in mod:
            real_features["mod_ratios"].append(mod["syllable_mod_ratio"])
        fmt = r.get("formants", {})
        if "score" in fmt:
            real_features["formant_scores"].append(fmt["score"])
        pit = r.get("pitch", {})
        if "mean_f0_hz" in pit:
            real_features["pitch_f0s"].append(pit["mean_f0_hz"])
        vad = r.get("vad", {})
        if "voiced_ratio" in vad:
            real_features["voiced_ratios"].append(vad["voiced_ratio"])

    # Compute summary statistics
    summary = {}
    for key, values in real_features.items():
        if values:
            arr = np.array(values)
            summary[key] = {
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "median": float(np.median(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
            }

    return summary


def compute_similarity(synthetic_features, real_summary):
    """
    Compute similarity between synthetic and real features.
    Returns 0-1 score where 1 = perfect match.
    """
    if real_summary is None:
        return 0.0, {}

    scores = {}

    # Compare speech scores
    if "speech_scores" in real_summary and "speech_score" in synthetic_features:
        real_mean = real_summary["speech_scores"]["mean"]
        real_std = max(real_summary["speech_scores"]["std"], 0.01)
        syn_val = synthetic_features["speech_score"]
        z_score = abs(syn_val - real_mean) / real_std
        scores["speech_score"] = float(np.exp(-0.5 * z_score ** 2))

    # Compare modulation ratios
    if "mod_ratios" in real_summary:
        real_mean = real_summary["mod_ratios"]["mean"]
        real_std = max(real_summary["mod_ratios"]["std"], 0.1)
        syn_val = synthetic_features.get("modulation", {}).get(
            "syllable_mod_ratio", 0)
        z_score = abs(syn_val - real_mean) / real_std
        scores["mod_ratio"] = float(np.exp(-0.5 * z_score ** 2))

    # Compare formant scores
    if "formant_scores" in real_summary:
        real_mean = real_summary["formant_scores"]["mean"]
        real_std = max(real_summary["formant_scores"]["std"], 0.01)
        syn_val = synthetic_features.get("formants", {}).get("score", 0)
        z_score = abs(syn_val - real_mean) / real_std
        scores["formant_score"] = float(np.exp(-0.5 * z_score ** 2))

    # Compare voiced ratios
    if "voiced_ratios" in real_summary:
        real_mean = real_summary["voiced_ratios"]["mean"]
        real_std = max(real_summary["voiced_ratios"]["std"], 0.01)
        syn_val = synthetic_features.get("vad", {}).get("voiced_ratio", 0)
        z_score = abs(syn_val - real_mean) / real_std
        scores["voiced_ratio"] = float(np.exp(-0.5 * z_score ** 2))

    if scores:
        overall = float(np.mean(list(scores.values())))
    else:
        overall = 0.0

    return overall, scores


# ═══════════════════════════════════════════════════════════════════════════
#  VISUALIZATION
# ═══════════════════════════════════════════════════════════════════════════

def plot_encoding_comparison(all_results, output_dir):
    """Plot comparison of all encoding methods."""
    plt.style.use("dark_background")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.patch.set_facecolor("#1a1a2e")
    fig.suptitle("Forward Model: Encoding Method Comparison",
                 fontsize=14, color="#ffffff", fontweight="bold")

    colors = {
        "AM_ENVELOPE": "#ff6b6b",
        "PRF_MODULATION": "#4ecdc4",
        "LIN_MEDUSA": "#ffd93d",
        "THERMOELASTIC_INVERSE": "#a78bfa",
    }

    methods = list(all_results.keys())

    # Panel 1: Pulse amplitude patterns (first 5ms)
    ax = axes[0, 0]
    for method in methods:
        r = all_results[method]
        times = r["pulse_times"][:500]
        amps = r["pulse_amplitudes"][:500]
        ax.plot(times * 1000, amps, color=colors.get(method, "#aaa"),
                linewidth=0.5, alpha=0.8, label=method)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Pulse Amplitude")
    ax.set_title("Pulse Amplitude Pattern (first 50ms)")
    ax.legend(fontsize=7)
    ax.set_facecolor("#0d1117")

    # Panel 2: Inter-pulse interval histogram
    ax = axes[0, 1]
    for method in methods:
        r = all_results[method]
        times = r["pulse_times"]
        if len(times) > 1:
            ipis = np.diff(times) * 1e6  # µs
            ipis = ipis[ipis < 500]
            if len(ipis) > 0:
                ax.hist(ipis, bins=50, alpha=0.4, label=method,
                        color=colors.get(method, "#aaa"))
    ax.set_xlabel("Inter-Pulse Interval (µs)")
    ax.set_ylabel("Count")
    ax.set_title("IPI Distribution")
    ax.legend(fontsize=7)
    ax.set_facecolor("#0d1117")

    # Panel 3: Kurtosis comparison
    ax = axes[0, 2]
    kurt_vals = []
    method_labels = []
    for method in methods:
        r = all_results[method]
        if "iq_features" in r:
            kurt_vals.append(r["iq_features"]["kurtosis"])
            method_labels.append(method)
    if kurt_vals:
        bars = ax.bar(range(len(kurt_vals)), kurt_vals,
                      color=[colors.get(m, "#aaa") for m in method_labels])
        ax.set_xticks(range(len(method_labels)))
        ax.set_xticklabels([m.replace("_", "\n") for m in method_labels],
                           fontsize=7)
        ax.set_ylabel("Kurtosis")
        ax.set_title("Simulated Capture Kurtosis")
        # Add real data reference line
        ax.axhline(y=70, color="#ff4444", linestyle="--", alpha=0.5,
                   label="Real data mean (~70)")
        ax.legend(fontsize=7)
    ax.set_facecolor("#0d1117")

    # Panel 4: Speech scores by demod method
    ax = axes[1, 0]
    bar_data = {}
    for method in methods:
        r = all_results[method]
        demod = r.get("demod_analysis", {})
        for dm, analysis in demod.items():
            score = analysis.get("speech_score", 0)
            if dm not in bar_data:
                bar_data[dm] = {}
            bar_data[dm][method] = score

    x = np.arange(len(methods))
    width = 0.25
    for i, (dm, scores_dict) in enumerate(bar_data.items()):
        vals = [scores_dict.get(m, 0) for m in methods]
        ax.bar(x + i * width, vals, width, label=f"Demod: {dm}", alpha=0.7)
    ax.set_xticks(x + width)
    ax.set_xticklabels([m.replace("_", "\n") for m in methods], fontsize=7)
    ax.set_ylabel("Speech Score")
    ax.set_title("Speech Detection Scores")
    ax.axhline(y=0.6, color="#ffaa00", linestyle="--", alpha=0.5,
               label="Real data (~0.60)")
    ax.legend(fontsize=6)
    ax.set_facecolor("#0d1117")

    # Panel 5: Similarity to real data
    ax = axes[1, 1]
    sim_vals = []
    sim_labels = []
    for method in methods:
        r = all_results[method]
        sim = r.get("similarity_overall", 0)
        sim_vals.append(sim)
        sim_labels.append(method)
    if sim_vals:
        bars = ax.barh(range(len(sim_vals)), sim_vals,
                       color=[colors.get(m, "#aaa") for m in sim_labels])
        ax.set_yticks(range(len(sim_labels)))
        ax.set_yticklabels([m.replace("_", "\n") for m in sim_labels],
                           fontsize=8)
        ax.set_xlabel("Similarity to Real Data")
        ax.set_title("Feature-Space Similarity (0=different, 1=match)")
        ax.set_xlim(0, 1)
    ax.set_facecolor("#0d1117")

    # Panel 6: Summary text
    ax = axes[1, 2]
    ax.axis("off")
    ax.set_facecolor("#0d1117")
    text_lines = ["FORWARD MODEL SUMMARY\n"]
    for method in methods:
        r = all_results[method]
        sim = r.get("similarity_overall", 0)
        demod = r.get("demod_analysis", {})
        best_score = max((a.get("speech_score", 0)
                         for a in demod.values()), default=0)
        kurt = r.get("iq_features", {}).get("kurtosis", 0)
        text_lines.append(f"{method}:")
        text_lines.append(f"  Similarity: {sim:.3f}")
        text_lines.append(f"  Best speech: {best_score:.3f}")
        text_lines.append(f"  Kurtosis: {kurt:.1f}")
        text_lines.append("")

    ax.text(0.05, 0.95, "\n".join(text_lines), transform=ax.transAxes,
            fontsize=9, fontfamily="monospace", color="#ffffff",
            verticalalignment="top")

    plt.tight_layout()
    plt.savefig(f"{output_dir}/encoding_comparison.png", dpi=150,
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"    Plot: {output_dir}/encoding_comparison.png")


def plot_method_detail(method_name, speech, sr, pulse_times, pulse_amps,
                       iq, features, demod_results, output_dir):
    """Detailed plot for a single encoding method."""
    plt.style.use("dark_background")
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    fig.patch.set_facecolor("#1a1a2e")
    fig.suptitle(f"Forward Model: {method_name}", fontsize=14,
                 color="#ffffff", fontweight="bold")

    # 1. Original speech
    ax = axes[0, 0]
    t_speech = np.arange(len(speech)) / sr
    ax.plot(t_speech, speech, color="#4fc3f7", linewidth=0.5)
    ax.set_title("Input Speech Signal")
    ax.set_xlabel("Time (s)")
    ax.set_facecolor("#0d1117")

    # 2. Pulse amplitude pattern
    ax = axes[0, 1]
    n_show = min(1000, len(pulse_times))
    ax.stem(pulse_times[:n_show] * 1000, pulse_amps[:n_show],
            linefmt="#ff6b6b", markerfmt=".", basefmt="")
    ax.set_title(f"Encoded Pulse Train ({len(pulse_times)} pulses)")
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Amplitude")
    ax.set_facecolor("#0d1117")

    # 3. Simulated IQ amplitude
    ax = axes[1, 0]
    iq_amp = np.abs(iq)
    t_iq = np.arange(len(iq)) / SAMPLE_RATE * 1000
    ax.plot(t_iq, iq_amp, color="#4ecdc4", linewidth=0.2)
    ax.set_title(f"Simulated RTL-SDR Capture (kurtosis={features['kurtosis']:.1f})")
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("|IQ|")
    ax.set_facecolor("#0d1117")

    # 4. IQ amplitude histogram
    ax = axes[1, 1]
    ax.hist(iq_amp, bins=100, color="#ffd93d", alpha=0.7)
    ax.set_title("Amplitude Distribution")
    ax.set_xlabel("Amplitude")
    ax.set_yscale("log")
    ax.set_facecolor("#0d1117")

    # 5-6. Best demod result
    if demod_results:
        best_method = max(demod_results.keys(),
                         key=lambda k: demod_results[k].get("speech_score", 0))
        best = demod_results[best_method]

        ax = axes[2, 0]
        # Modulation info
        mr = best.get("modulation", {}).get("syllable_mod_ratio", 0)
        fs = best.get("formants", {}).get("score", 0)
        f0 = best.get("pitch", {}).get("mean_f0_hz", 0)
        ss = best.get("speech_score", 0)
        cl = best.get("classification", "N/A")

        info_text = (f"Best demod: {best_method}\n"
                     f"Speech score: {ss:.3f} [{cl}]\n"
                     f"Mod ratio: {mr:.2f}\n"
                     f"Formant score: {fs:.2f}\n"
                     f"Pitch F0: {f0:.1f} Hz")
        ax.text(0.1, 0.5, info_text, transform=ax.transAxes,
                fontsize=12, fontfamily="monospace", color="#ffffff",
                verticalalignment="center")
        ax.set_title(f"Demod Analysis — {best_method}")
        ax.axis("off")
        ax.set_facecolor("#0d1117")

        ax = axes[2, 1]
        # Score breakdown
        demod_names = list(demod_results.keys())
        demod_scores = [demod_results[k].get("speech_score", 0)
                       for k in demod_names]
        ax.barh(demod_names, demod_scores, color="#a78bfa")
        ax.axvline(x=0.6, color="#ffaa00", linestyle="--", alpha=0.5,
                   label="Real data")
        ax.set_xlabel("Speech Score")
        ax.set_title("Demod Method Scores")
        ax.set_xlim(0, 1)
        ax.legend(fontsize=8)
        ax.set_facecolor("#0d1117")
    else:
        axes[2, 0].set_facecolor("#0d1117")
        axes[2, 1].set_facecolor("#0d1117")

    plt.tight_layout()
    fname = f"{output_dir}/{method_name.lower()}_detail.png"
    plt.savefig(fname, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"    Plot: {fname}")


# ═══════════════════════════════════════════════════════════════════════════
#  CLI COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

def run_single_method(method_name, encode_fn, speech, sr, output_dir):
    """Run a single encoding method through the full pipeline."""
    print(f"\n  [{method_name}] Encoding speech...")
    pulse_times, pulse_amps, pulse_widths, stats = encode_fn(speech, sr)
    print(f"    Pulses: {len(pulse_times)}")
    print(f"    Duration: {stats.get('duration_s', 0):.3f}s")

    for k, v in stats.items():
        if k not in ("method", "n_pulses", "duration_s"):
            print(f"    {k}: {v}")

    # Simulate RTL-SDR capture
    print(f"    Simulating RTL-SDR capture...")
    raw_iq, capture_info = simulate_rtl_capture(
        pulse_times, pulse_amps, pulse_widths, capture_len_ms=200)
    iq = load_iq_from_raw(raw_iq)

    # Extract IQ features
    features = compute_features(iq)
    print(f"    Kurtosis: {features['kurtosis']:.1f}")
    print(f"    PAPR: {features['papr_db']:.1f} dB")
    print(f"    Pulses detected: {features['n_pulses']}")
    print(f"    Bursts detected: {features['n_bursts']}")

    # Temporal windowing analysis (from KG: EEG microwave studies)
    print(f"    Running temporal window analysis...")
    windowed = compute_windowed_features(iq, n_windows=3)
    ns_score = windowed.get("nonstationarity_score", 0)
    print(f"    Non-stationarity: {ns_score:.3f} "
          f"({'VARYING' if ns_score > 0.3 else 'STABLE'})")
    for w in windowed.get("windows", []):
        print(f"      {w['window_label']:>9}: kurt={w['kurtosis']:.1f}  "
              f"papr={w['papr_db']:.1f}dB  "
              f"pulses={w['n_pulses']}")

    # Run demod analysis
    print(f"    Running demod analysis...")
    demod_results = run_demod_analysis(iq)

    for dm_name, dm_result in demod_results.items():
        score = dm_result.get("speech_score", 0)
        cl = dm_result.get("classification", "N/A")
        mr = dm_result.get("modulation", {}).get("syllable_mod_ratio", 0)
        print(f"      {dm_name}: score={score:.3f} [{cl}] mod={mr:.1f}")

    # Similarity to real data
    real_summary = load_real_data_features()
    similarities = {}
    overall_sim = 0.0
    if real_summary:
        # Compare each demod result
        best_sim = 0
        for dm_name, dm_result in demod_results.items():
            sim, sim_detail = compute_similarity(dm_result, real_summary)
            similarities[dm_name] = {"overall": sim, "detail": sim_detail}
            best_sim = max(best_sim, sim)
        overall_sim = best_sim
        print(f"    Similarity to real data: {overall_sim:.3f}")

    # Generate detail plot
    plot_method_detail(method_name, speech, sr, pulse_times, pulse_amps,
                      iq, features, demod_results, output_dir)

    # Save IQ capture
    iq_path = f"{output_dir}/{method_name.lower()}_simulated.iq"
    raw_iq.tofile(iq_path)
    print(f"    Simulated IQ: {iq_path}")

    return {
        "method": method_name,
        "encoding_stats": stats,
        "pulse_times": pulse_times,
        "pulse_amplitudes": pulse_amps,
        "iq_features": features,
        "windowed_analysis": {
            "nonstationarity_score": windowed.get("nonstationarity_score", 0),
            "windows": [{k: v for k, v in w.items()
                        if not isinstance(v, np.ndarray)}
                       for w in windowed.get("windows", [])],
            "stationarity": windowed.get("stationarity", {}),
        },
        "demod_analysis": {k: {kk: vv for kk, vv in v.items()
                              if not isinstance(vv, np.ndarray)}
                          for k, v in demod_results.items()},
        "similarity_overall": overall_sim,
        "similarity_detail": similarities,
    }


def cmd_test(args):
    """Test with synthetic speech."""
    output_dir = RESULTS_DIR
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'=' * 72}")
    print(f"  FORWARD MODEL — SYNTHETIC SPEECH TEST")
    print(f"{'=' * 72}")

    # Generate test speech
    print(f"\n  Generating synthetic speech (2s, vowel sequence)...")
    speech, sr = generate_test_speech(duration_s=2.0)
    print(f"  Samples: {len(speech)} @ {sr} Hz")

    # Save test speech as WAV
    from demod_pulses import save_wav
    wav_path = f"{output_dir}/test_speech.wav"
    save_wav(wav_path, speech, sr)
    print(f"  Saved: {wav_path}")

    # Run all encoding methods
    all_results = {}

    encoders = [
        ("AM_ENVELOPE", lambda s, sr: encode_am_envelope(s, sr)),
        ("PRF_MODULATION", lambda s, sr: encode_prf_modulation(s, sr)),
        ("LIN_MEDUSA", lambda s, sr: encode_lin_medusa(s, sr)),
        ("THERMOELASTIC_INVERSE",
         lambda s, sr: encode_thermoelastic_inverse(s, sr)),
    ]

    for method_name, encode_fn in encoders:
        result = run_single_method(method_name, encode_fn, speech, sr,
                                   output_dir)
        all_results[method_name] = result

    # Generate comparison plot
    print(f"\n  Generating comparison plot...")
    plot_encoding_comparison(all_results, output_dir)

    # Save results
    json_results = {}
    for method, r in all_results.items():
        json_results[method] = {
            "encoding_stats": {k: v for k, v in r["encoding_stats"].items()
                              if not isinstance(v, np.ndarray)},
            "iq_features": r["iq_features"],
            "demod_analysis": r["demod_analysis"],
            "similarity_overall": r["similarity_overall"],
        }

    json_path = f"{output_dir}/forward_model_results.json"
    with open(json_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "speech_source": "synthetic_test",
            "speech_duration_s": 2.0,
            "methods": json_results,
        }, f, indent=2, default=str)

    # Print ranking
    print(f"\n  {'=' * 72}")
    print(f"  ENCODING METHOD RANKING")
    print(f"  {'=' * 72}")

    ranked = sorted(all_results.items(),
                   key=lambda x: x[1].get("similarity_overall", 0),
                   reverse=True)

    for rank, (method, r) in enumerate(ranked, 1):
        sim = r.get("similarity_overall", 0)
        kurt = r["iq_features"]["kurtosis"]
        demod = r.get("demod_analysis", {})
        best_score = max((a.get("speech_score", 0)
                         for a in demod.values()), default=0)
        best_method = max(demod.keys(),
                         key=lambda k: demod[k].get("speech_score", 0)) \
            if demod else "N/A"

        print(f"\n  #{rank} {method}")
        print(f"      Similarity to real data: {sim:.3f}")
        print(f"      Kurtosis:                {kurt:.1f}")
        print(f"      Best speech score:       {best_score:.3f} ({best_method})")
        print(f"      Encoding:                {r['encoding_stats'].get('encoding', r['encoding_stats'].get('method', ''))}")

    print(f"\n  Results: {json_path}")
    print(f"  {'=' * 72}\n")


def cmd_encode(args):
    """Encode specific audio file."""
    filepath = args.file
    if not os.path.exists(filepath):
        print(f"  Error: {filepath} not found")
        return

    output_dir = RESULTS_DIR
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'=' * 72}")
    print(f"  FORWARD MODEL — ENCODE: {filepath}")
    print(f"{'=' * 72}")

    speech, sr = load_wav(filepath)
    speech = resample_audio(speech, sr, AUDIO_RATE)
    sr = AUDIO_RATE
    print(f"  Audio: {len(speech)} samples @ {sr} Hz "
          f"({len(speech) / sr:.2f}s)")

    all_results = {}
    encoders = [
        ("AM_ENVELOPE", lambda s, sr: encode_am_envelope(s, sr)),
        ("PRF_MODULATION", lambda s, sr: encode_prf_modulation(s, sr)),
        ("LIN_MEDUSA", lambda s, sr: encode_lin_medusa(s, sr)),
        ("THERMOELASTIC_INVERSE",
         lambda s, sr: encode_thermoelastic_inverse(s, sr)),
    ]

    for method_name, encode_fn in encoders:
        result = run_single_method(method_name, encode_fn, speech, sr,
                                   output_dir)
        all_results[method_name] = result

    plot_encoding_comparison(all_results, output_dir)

    ranked = sorted(all_results.items(),
                   key=lambda x: x[1].get("similarity_overall", 0),
                   reverse=True)
    print(f"\n  RANKING:")
    for rank, (method, r) in enumerate(ranked, 1):
        sim = r.get("similarity_overall", 0)
        print(f"  #{rank} {method} — similarity: {sim:.3f}")

    print(f"{'=' * 72}\n")


def cmd_compare(args):
    """Compare forward model results with real data."""
    results_path = f"{RESULTS_DIR}/forward_model_results.json"
    if not os.path.exists(results_path):
        print("  No forward model results. Run: python forward_model.py test")
        return

    real_summary = load_real_data_features()
    if real_summary is None:
        print("  No real data results. Run: python demod_pulses.py batch")
        return

    with open(results_path) as f:
        data = json.load(f)

    print(f"\n{'=' * 72}")
    print(f"  FORWARD MODEL vs REAL DATA COMPARISON")
    print(f"{'=' * 72}")

    print(f"\n  Real data summary:")
    for key, stats in real_summary.items():
        print(f"    {key}: mean={stats['mean']:.3f} "
              f"std={stats['std']:.3f} range=[{stats['min']:.3f}, "
              f"{stats['max']:.3f}]")

    print(f"\n  Synthetic data comparison:")
    methods = data.get("methods", {})
    for method, r in methods.items():
        print(f"\n  [{method}]")
        sim = r.get("similarity_overall", 0)
        print(f"    Overall similarity: {sim:.3f}")
        demod = r.get("demod_analysis", {})
        for dm, analysis in demod.items():
            ss = analysis.get("speech_score", 0)
            mr = analysis.get("modulation", {}).get("syllable_mod_ratio", 0)
            print(f"    {dm}: score={ss:.3f} mod={mr:.1f}")

    print(f"{'=' * 72}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Forward model: speech → MW encoding → RTL-SDR simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python forward_model.py test
  python forward_model.py encode speech.wav
  python forward_model.py compare
  python forward_model.py all
        """)

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("test", help="Test with synthetic speech")

    p = sub.add_parser("encode", help="Encode specific audio file")
    p.add_argument("file", help="Path to .wav file")

    sub.add_parser("compare", help="Compare with real data")
    sub.add_parser("all", help="Full pipeline (test + compare)")

    args = parser.parse_args()

    if args.command == "test":
        cmd_test(args)
    elif args.command == "encode":
        cmd_encode(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "all":
        cmd_test(args)
        cmd_compare(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

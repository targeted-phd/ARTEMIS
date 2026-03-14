#!/usr/bin/env python3
"""
Speech Pattern Analyzer — Statistical analysis of WAV files for speech-like
temporal structure, formant content, rhythm metrics, and phoneme classification.

Subcommands:
  analyze <file.wav>        Single file analysis
  batch [--dir audio/]      Analyze all WAVs in directory
  compare <file1> <file2>   Compare two files
  report                    Generate full report from batch results

Usage:
  python speech_analysis.py analyze results/audio/some_file.wav
  python speech_analysis.py batch --dir results/audio/
  python speech_analysis.py report
"""

import argparse
import json
import os
import sys
from pathlib import Path
from collections import Counter

import numpy as np
from scipy.io import wavfile
from scipy import stats as sp_stats
from scipy.signal import spectrogram, find_peaks, butter, filtfilt, hilbert

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.style.use("dark_background")
plt.rcParams.update({"font.family": "monospace", "axes.grid": True,
                     "grid.alpha": 0.15, "grid.linewidth": 0.5})

RESULTS_DIR = Path("results/audio")
PLOTS_DIR = RESULTS_DIR / "plots"


# ── Core Analysis ──────────────────────────────────────────────────────────

def analyze_wav(fpath, verbose=True):
    """Full speech pattern analysis of a single WAV file.
    Returns dict of all computed features."""

    sr, data = wavfile.read(fpath)
    if data.ndim > 1:
        data = data[:, 0]
    data = data.astype(np.float64)
    max_amp = np.max(np.abs(data))
    if max_amp > 0:
        data = data / max_amp

    duration = len(data) / sr
    fname = os.path.basename(fpath)

    if duration < 0.05:
        return {"file": fname, "duration_s": duration, "error": "too short", "speech_score": 0}

    result = {
        "file": fname,
        "path": str(fpath),
        "duration_s": round(duration, 4),
        "sample_rate": sr,
        "n_samples": len(data),
    }

    # ── 1. Basic signal statistics ──
    rms = np.sqrt(np.mean(data ** 2))
    peak = np.max(np.abs(data))
    crest_db = 20 * np.log10(peak / (rms + 1e-12))
    kurt = float(sp_stats.kurtosis(data, fisher=False))
    skew = float(sp_stats.skew(data))
    zcr = np.sum(np.abs(np.diff(np.sign(data)))) / (2 * len(data))

    result.update({
        "rms": round(float(rms), 6),
        "peak": round(float(peak), 6),
        "crest_factor_db": round(crest_db, 2),
        "kurtosis": round(kurt, 3),
        "skewness": round(skew, 3),
        "zero_crossing_rate": round(float(zcr), 5),
    })

    # ── 2. Spectrogram ──
    nperseg = min(512, len(data) // 4)
    if nperseg < 64:
        result["error"] = "too short for spectrogram"
        result["speech_score"] = 0
        return result

    f, t_spec, Sxx = spectrogram(data, sr, nperseg=nperseg, noverlap=nperseg // 2)
    mean_spec = np.mean(Sxx, axis=1)

    # ── 3. Spectral features ──
    # Spectral centroid
    total_energy = np.sum(mean_spec) + 1e-12
    spectral_centroid = np.sum(f * mean_spec) / total_energy

    # Spectral centroid over time (variation = speech indicator)
    sc_time = np.sum(f[:, None] * Sxx, axis=0) / (np.sum(Sxx, axis=0) + 1e-12)
    sc_cv = np.std(sc_time) / (np.mean(sc_time) + 1e-12)

    # Spectral flatness (noise ~1.0, tonal <0.3)
    geo_mean = np.exp(np.mean(np.log(mean_spec + 1e-12)))
    arith_mean = np.mean(mean_spec) + 1e-12
    spectral_flatness = geo_mean / arith_mean

    # Spectral rolloff (85%)
    cumspec = np.cumsum(mean_spec)
    cumspec = cumspec / (cumspec[-1] + 1e-12)
    rolloff_idx = np.searchsorted(cumspec, 0.85)
    spectral_rolloff = f[min(rolloff_idx, len(f) - 1)]

    # Spectral bandwidth
    spectral_bw = np.sqrt(np.sum(((f - spectral_centroid) ** 2) * mean_spec) / total_energy)

    result.update({
        "spectral_centroid_hz": round(float(spectral_centroid), 1),
        "spectral_centroid_cv": round(float(sc_cv), 4),
        "spectral_flatness": round(float(spectral_flatness), 5),
        "spectral_rolloff_hz": round(float(spectral_rolloff), 1),
        "spectral_bandwidth_hz": round(float(spectral_bw), 1),
    })

    # ── 4. Formant band energy ──
    f1_mask = (f >= 200) & (f <= 900)
    f2_mask = (f >= 800) & (f <= 2500)
    f3_mask = (f >= 1800) & (f <= 3500)
    hf_mask = f >= 4000

    f1_energy = np.sum(mean_spec[f1_mask]) if f1_mask.any() else 0
    f2_energy = np.sum(mean_spec[f2_mask]) if f2_mask.any() else 0
    f3_energy = np.sum(mean_spec[f3_mask]) if f3_mask.any() else 0
    hf_energy = np.sum(mean_spec[hf_mask]) if hf_mask.any() else 0

    formant_ratio = (f1_energy + f2_energy + f3_energy) / total_energy
    f1_ratio = f1_energy / total_energy
    f2_ratio = f2_energy / total_energy
    f3_ratio = f3_energy / total_energy
    hf_ratio = hf_energy / total_energy

    result.update({
        "formant_band_ratio": round(float(formant_ratio), 4),
        "f1_ratio": round(float(f1_ratio), 4),
        "f2_ratio": round(float(f2_ratio), 4),
        "f3_ratio": round(float(f3_ratio), 4),
        "hf_ratio": round(float(hf_ratio), 4),
    })

    # ── 5. Modulation spectrum (syllable rate detection) ──
    frame_len = int(0.025 * sr)
    hop_len = int(0.010 * sr)
    n_frames = max(1, (len(data) - frame_len) // hop_len)
    envelope = np.array([np.sqrt(np.mean(data[i * hop_len:i * hop_len + frame_len] ** 2))
                        for i in range(n_frames)])

    if len(envelope) > 20:
        env_centered = envelope - np.mean(envelope)
        env_fft = np.abs(np.fft.rfft(env_centered))
        env_freqs = np.fft.rfftfreq(len(env_centered), d=hop_len / sr)

        # Syllable rate band (2-8 Hz)
        syl_mask = (env_freqs >= 2) & (env_freqs <= 8)
        syl_energy = np.sum(env_fft[syl_mask] ** 2) if syl_mask.any() else 0
        total_env = np.sum(env_fft ** 2) + 1e-12
        syl_ratio = syl_energy / total_env

        # Sub-syllabic (8-20 Hz, phoneme transitions)
        phon_mask = (env_freqs >= 8) & (env_freqs <= 20)
        phon_energy = np.sum(env_fft[phon_mask] ** 2) if phon_mask.any() else 0
        phon_ratio = phon_energy / total_env

        # Peak modulation frequency
        if len(env_fft) > 1:
            peak_idx = np.argmax(env_fft[1:]) + 1
            peak_mod_freq = env_freqs[peak_idx] if peak_idx < len(env_freqs) else 0
        else:
            peak_mod_freq = 0
    else:
        syl_ratio, phon_ratio, peak_mod_freq = 0, 0, 0

    result.update({
        "syllable_rate_ratio": round(float(syl_ratio), 5),
        "phoneme_transition_ratio": round(float(phon_ratio), 5),
        "peak_modulation_freq_hz": round(float(peak_mod_freq), 2),
    })

    # ── 6. Voiced segment detection ──
    energy_db = 10 * np.log10(envelope + 1e-12)
    thresh = np.percentile(energy_db, 30)
    voiced = energy_db > thresh

    segments = []
    in_seg = False
    seg_start = 0
    for i in range(len(voiced)):
        if voiced[i] and not in_seg:
            seg_start = i
            in_seg = True
        elif not voiced[i] and in_seg:
            dur_ms = (i - seg_start) * (hop_len / sr * 1000)
            if dur_ms > 30:
                segments.append({"start_ms": round(seg_start * hop_len / sr * 1000, 1),
                                "dur_ms": round(dur_ms, 1)})
            in_seg = False
    if in_seg:
        dur_ms = (len(voiced) - seg_start) * (hop_len / sr * 1000)
        if dur_ms > 30:
            segments.append({"start_ms": round(seg_start * hop_len / sr * 1000, 1),
                            "dur_ms": round(dur_ms, 1)})

    durs = [s["dur_ms"] for s in segments]
    syllable_length = sum(1 for d in durs if 80 < d < 400)

    result.update({
        "n_voiced_segments": len(segments),
        "syllable_length_segments": syllable_length,
        "segment_dur_mean_ms": round(float(np.mean(durs)), 1) if durs else 0,
        "segment_dur_std_ms": round(float(np.std(durs)), 1) if len(durs) > 1 else 0,
        "segments": segments[:50],  # cap for JSON size
    })

    # ── 7. Per-segment vowel classification (F1/F2 mapping) ──
    vowel_counts = Counter()
    segment_vowels = []
    for seg in segments[:50]:
        s_start = int(seg["start_ms"] * sr / 1000)
        s_end = s_start + int(seg["dur_ms"] * sr / 1000)
        s_end = min(s_end, len(data))
        seg_data = data[s_start:s_end]
        if len(seg_data) < 128:
            continue

        spec_seg = np.abs(np.fft.rfft(seg_data))
        freqs_seg = np.fft.rfftfreq(len(seg_data), 1 / sr)

        # F1 and F2 peak frequencies
        f1_band = spec_seg[(freqs_seg >= 200) & (freqs_seg <= 900)]
        f1_freqs = freqs_seg[(freqs_seg >= 200) & (freqs_seg <= 900)]
        f2_band = spec_seg[(freqs_seg >= 800) & (freqs_seg <= 2500)]
        f2_freqs = freqs_seg[(freqs_seg >= 800) & (freqs_seg <= 2500)]

        f1 = f1_freqs[np.argmax(f1_band)] if len(f1_band) > 0 else 0
        f2 = f2_freqs[np.argmax(f2_band)] if len(f2_band) > 0 else 0

        vowel = classify_vowel(f1, f2)
        vowel_counts[vowel] += 1
        segment_vowels.append({"start_ms": seg["start_ms"], "dur_ms": seg["dur_ms"],
                               "f1": round(float(f1), 0), "f2": round(float(f2), 0),
                               "vowel": vowel})

    result.update({
        "vowel_distribution": dict(vowel_counts.most_common()),
        "dominant_vowel": vowel_counts.most_common(1)[0][0] if vowel_counts else "none",
        "vowel_diversity": len(vowel_counts),
        "segment_vowels": segment_vowels[:30],
    })

    # ── 8. Stress timing / rhythm metrics ──
    peaks_idx, peak_props = find_peaks(envelope, distance=int(80 / (hop_len / sr * 1000)),
                                       height=0.15, prominence=0.08)

    if len(peaks_idx) > 2:
        isis = np.diff(peaks_idx) * (hop_len / sr * 1000)  # ms
        isi_mean = np.mean(isis)
        isi_std = np.std(isis)
        isi_cv = isi_std / (isi_mean + 1e-12)

        # nPVI — rhythm metric
        if len(isis) > 1:
            npvi = 100 * np.mean(np.abs(np.diff(isis)) / ((isis[:-1] + isis[1:]) / 2 + 1e-12))
        else:
            npvi = 0

        stress_rate = len(peaks_idx) / duration

        # Rhythm classification
        if npvi > 50 and isi_cv > 0.35:
            rhythm = "stress-timed (English-like)"
        elif npvi > 40:
            rhythm = "mixed-timing (English-compatible)"
        elif npvi > 30:
            rhythm = "syllable-timed (Spanish/Italian-like)"
        else:
            rhythm = "mora-timed (Japanese-like)"
    else:
        isi_mean, isi_std, isi_cv, npvi, stress_rate = 0, 0, 0, 0, 0
        rhythm = "insufficient data"

    result.update({
        "n_stress_peaks": len(peaks_idx) if len(peaks_idx) > 2 else 0,
        "stress_rate_per_s": round(float(stress_rate), 2),
        "isi_mean_ms": round(float(isi_mean), 1),
        "isi_std_ms": round(float(isi_std), 1),
        "isi_cv": round(float(isi_cv), 3),
        "npvi": round(float(npvi), 1),
        "rhythm_classification": rhythm,
    })

    # ── 9. Autocorrelation pitch detection ──
    if len(data) > 2000:
        ac_len = min(8192, len(data))
        ac_data = data[:ac_len]
        ac = np.correlate(ac_data, ac_data, mode='full')
        ac = ac[len(ac) // 2:]
        ac = ac / (ac[0] + 1e-12)

        min_lag = int(sr / 400)  # 400 Hz
        max_lag = min(int(sr / 50), len(ac))  # 50 Hz
        if max_lag > min_lag:
            ac_range = ac[min_lag:max_lag]
            if len(ac_range) > 0:
                ac_peak = np.max(ac_range)
                ac_peak_lag = np.argmax(ac_range) + min_lag
                ac_pitch = sr / ac_peak_lag if ac_peak_lag > 0 else 0
            else:
                ac_peak, ac_pitch = 0, 0
        else:
            ac_peak, ac_pitch = 0, 0
    else:
        ac_peak, ac_pitch = 0, 0

    result.update({
        "autocorr_pitch_peak": round(float(ac_peak), 4),
        "autocorr_pitch_hz": round(float(ac_pitch), 1),
    })

    # ── 10. Harmonic-to-noise ratio ──
    if len(data) > 2000:
        spec_full = np.abs(np.fft.rfft(data[:min(16384, len(data))]))
        sorted_spec = np.sort(spec_full)
        noise_est = np.mean(sorted_spec[:len(sorted_spec) // 2])
        harmonic_est = np.mean(sorted_spec[-len(sorted_spec) // 10:])
        hnr = 20 * np.log10(harmonic_est / (noise_est + 1e-12))
    else:
        hnr = 0

    result["hnr_db"] = round(float(hnr), 1)

    # ── 11. Word-level grouping ──
    if len(segments) > 2:
        words = []
        current_word = [segments[0]]
        for i in range(1, len(segments)):
            gap = segments[i]["start_ms"] - (segments[i-1]["start_ms"] + segments[i-1]["dur_ms"])
            if gap > 80:  # 80ms gap = word boundary
                words.append(current_word)
                current_word = [segments[i]]
            else:
                current_word.append(segments[i])
        words.append(current_word)

        word_info = []
        for wi, w in enumerate(words[:20]):
            w_dur = sum(s["dur_ms"] for s in w)
            w_syls = len(w)
            word_info.append({"word_idx": wi, "n_syllables": w_syls,
                             "duration_ms": round(w_dur, 1),
                             "start_ms": w[0]["start_ms"]})
        result["n_words"] = len(words)
        result["words"] = word_info
        result["mean_word_syllables"] = round(np.mean([w["n_syllables"] for w in word_info]), 1)
    else:
        result["n_words"] = 0
        result["words"] = []
        result["mean_word_syllables"] = 0

    # ── 12. Composite speech score (0-15) ──
    score = 0
    reasons = []

    if syl_ratio > 0.05:
        score += 1; reasons.append("syllable-rate modulation present")
    if syl_ratio > 0.15:
        score += 1; reasons.append("strong syllable-rate modulation")
    if syl_ratio > 0.30:
        score += 1; reasons.append("very strong syllable-rate modulation")
    if formant_ratio > 0.3:
        score += 1; reasons.append("energy in formant bands")
    if formant_ratio > 0.6:
        score += 1; reasons.append("dominant formant band energy")
    if sc_cv > 0.2:
        score += 1; reasons.append("spectral centroid varies over time")
    if sc_cv > 0.5:
        score += 1; reasons.append("high spectral variation")
    if spectral_flatness < 0.3:
        score += 1; reasons.append("tonal (not noise-like)")
    if spectral_flatness < 0.05:
        score += 1; reasons.append("highly tonal")
    if ac_peak > 0.3:
        score += 1; reasons.append("pitch periodicity detected")
    if hnr > 5:
        score += 1; reasons.append("harmonics above noise")
    if hnr > 20:
        score += 1; reasons.append("strong harmonic structure")
    if len(vowel_counts) >= 3:
        score += 1; reasons.append("multiple vowel types")
    if 3 <= stress_rate <= 8:
        score += 1; reasons.append(f"stress rate {stress_rate:.1f}/s in speech range")
    if npvi > 40:
        score += 1; reasons.append(f"nPVI={npvi:.0f} (stress-timed)")

    if score >= 10:
        classification = "SPEECH-LIKE"
    elif score >= 6:
        classification = "STRUCTURED"
    elif score >= 3:
        classification = "WEAK-STRUCTURE"
    else:
        classification = "NOISE-LIKE"

    result.update({
        "speech_score": score,
        "speech_max_score": 15,
        "speech_classification": classification,
        "speech_reasons": reasons,
    })

    if verbose:
        print(f"  {fname:50s} {duration:6.2f}s  score={score:2d}/15 [{classification:12s}]  "
              f"syl={syl_ratio:.3f}  fmt={formant_ratio:.3f}  flat={spectral_flatness:.4f}  "
              f"nPVI={npvi:.0f}  pitch={ac_pitch:.0f}Hz  HNR={hnr:.0f}dB  "
              f"vowels={len(vowel_counts)}  words={result.get('n_words', 0)}")

    return result


def classify_vowel(f1, f2):
    """Map F1/F2 peaks to IPA vowel."""
    if f1 > 600 and f2 < 1200:
        return "/ɑ/ (ah)"
    elif f1 > 500 and f2 > 1500:
        return "/æ/ (a)"
    elif f1 < 400 and f2 > 2000:
        return "/i/ (ee)"
    elif f1 < 400 and f2 < 1000:
        return "/u/ (oo)"
    elif 400 < f1 < 600 and 1000 < f2 < 1800:
        return "/ɛ/ (eh)"
    elif 300 < f1 < 500 and 800 < f2 < 1200:
        return "/ʌ/ (uh)"
    elif f1 > 400 and 1200 < f2 < 1800:
        return "/e/ (ay)"
    elif f1 > 500 and 1000 < f2 < 1500:
        return "/ɔ/ (aw)"
    elif f1 < 350 and 1200 < f2 < 2000:
        return "/ɪ/ (ih)"
    elif f1 < 450 and 1000 < f2 < 1400:
        return "/ʊ/ (oo-short)"
    else:
        return "?"


# ── Plotting ───────────────────────────────────────────────────────────────

def plot_analysis(result, data, sr, output_dir):
    """Generate analysis plots for a single file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fname = result["file"].replace(".wav", "")

    fig, axes = plt.subplots(4, 1, figsize=(16, 12), sharex=False)

    # 1. Waveform
    t = np.arange(len(data)) / sr
    axes[0].plot(t, data, linewidth=0.3, color="#4dabf7", alpha=0.7)
    axes[0].set_ylabel("Amplitude")
    axes[0].set_title(f"{result['file']} — speech_score={result['speech_score']}/15 "
                     f"[{result['speech_classification']}]", fontweight="bold")

    # 2. Spectrogram
    nperseg = min(512, len(data) // 4)
    if nperseg >= 64:
        f_spec, t_spec, Sxx = spectrogram(data, sr, nperseg=nperseg, noverlap=nperseg // 2)
        axes[1].pcolormesh(t_spec, f_spec, 10 * np.log10(Sxx + 1e-12),
                          cmap="inferno", shading="auto")
        axes[1].set_ylabel("Frequency (Hz)")
        axes[1].set_ylim(0, min(sr // 2, 5000))
        axes[1].set_title("Spectrogram (0-5 kHz)")

    # 3. Energy envelope with stress peaks
    hop_len = int(0.010 * sr)
    frame_len = int(0.025 * sr)
    n_frames = max(1, (len(data) - frame_len) // hop_len)
    envelope = np.array([np.sqrt(np.mean(data[i * hop_len:i * hop_len + frame_len] ** 2))
                        for i in range(n_frames)])
    env_t = np.arange(n_frames) * hop_len / sr
    axes[2].plot(env_t, envelope, color="#69db7c", linewidth=0.8)
    axes[2].set_ylabel("Energy")
    axes[2].set_title(f"Envelope — syl_ratio={result.get('syllable_rate_ratio', 0):.3f}  "
                     f"nPVI={result.get('npvi', 0):.0f}  rhythm={result.get('rhythm_classification', '?')}")

    # Mark stress peaks
    peaks_idx, _ = find_peaks(envelope, distance=int(80 / (hop_len / sr * 1000)),
                              height=0.15, prominence=0.08)
    if len(peaks_idx) > 0:
        axes[2].scatter(peaks_idx * hop_len / sr, envelope[peaks_idx],
                       color="#ff4444", s=20, zorder=5)

    # 4. Vowel sequence
    vowels = result.get("segment_vowels", [])
    if vowels:
        starts = [v["start_ms"] / 1000 for v in vowels]
        f1s = [v["f1"] for v in vowels]
        f2s = [v["f2"] for v in vowels]
        axes[3].scatter(starts, f1s, c="#ff6b6b", s=15, label="F1", alpha=0.8)
        axes[3].scatter(starts, f2s, c="#4dabf7", s=15, label="F2", alpha=0.8)
        axes[3].set_ylabel("Frequency (Hz)")
        axes[3].set_xlabel("Time (s)")
        axes[3].legend(fontsize=8)
        axes[3].set_title(f"Formant tracks — dominant={result.get('dominant_vowel', '?')}  "
                         f"diversity={result.get('vowel_diversity', 0)}")
    else:
        axes[3].set_title("No formant data")

    fig.tight_layout()
    out = output_dir / f"{fname}_analysis.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return str(out)


# ── CLI ────────────────────────────────────────────────────────────────────

def cmd_analyze(args):
    """Analyze a single WAV file."""
    fpath = args.file
    if not os.path.exists(fpath):
        print(f"  [!] File not found: {fpath}")
        return

    print(f"\n{'=' * 70}")
    print(f"  SPEECH PATTERN ANALYSIS")
    print(f"{'=' * 70}\n")

    result = analyze_wav(fpath, verbose=True)

    # Print detailed results
    print(f"\n  Duration: {result['duration_s']:.3f}s  Sample rate: {result['sample_rate']} Hz")
    print(f"  RMS: {result['rms']:.6f}  Crest: {result['crest_factor_db']:.1f} dB  "
          f"Kurtosis: {result['kurtosis']:.2f}")
    print(f"\n  Spectral:")
    print(f"    Centroid: {result['spectral_centroid_hz']:.0f} Hz  "
          f"Bandwidth: {result['spectral_bandwidth_hz']:.0f} Hz  "
          f"Rolloff: {result['spectral_rolloff_hz']:.0f} Hz")
    print(f"    Flatness: {result['spectral_flatness']:.5f}  "
          f"Centroid CV: {result['spectral_centroid_cv']:.4f}")
    print(f"\n  Formant energy: {result['formant_band_ratio']:.3f} "
          f"(F1={result['f1_ratio']:.3f}  F2={result['f2_ratio']:.3f}  F3={result['f3_ratio']:.3f})")
    print(f"\n  Modulation: syl_ratio={result['syllable_rate_ratio']:.4f}  "
          f"peak_mod={result['peak_modulation_freq_hz']:.1f} Hz")
    print(f"\n  Rhythm: nPVI={result['npvi']:.1f}  ISI={result['isi_mean_ms']:.0f}±{result['isi_std_ms']:.0f}ms  "
          f"CV={result['isi_cv']:.3f}  → {result['rhythm_classification']}")
    print(f"\n  Pitch: {result['autocorr_pitch_hz']:.0f} Hz (autocorr peak={result['autocorr_pitch_peak']:.3f})")
    print(f"  HNR: {result['hnr_db']:.1f} dB")
    print(f"\n  Segments: {result['n_voiced_segments']} voiced, {result.get('n_words', 0)} word-groups")
    print(f"  Vowels: {result.get('vowel_distribution', {})}")
    print(f"\n  SCORE: {result['speech_score']}/{result['speech_max_score']} [{result['speech_classification']}]")
    print(f"  Reasons: {', '.join(result.get('speech_reasons', []))}")

    # Generate plot
    sr, data = wavfile.read(fpath)
    if data.ndim > 1: data = data[:, 0]
    data = data.astype(np.float64)
    if np.max(np.abs(data)) > 0: data = data / np.max(np.abs(data))

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    plot_path = plot_analysis(result, data, sr, PLOTS_DIR)
    print(f"\n  Plot: {plot_path}")

    # Save JSON
    out_json = RESULTS_DIR / f"{Path(fpath).stem}_analysis.json"
    json.dump(result, open(out_json, "w"), indent=2, default=str)
    print(f"  JSON: {out_json}")


def cmd_batch(args):
    """Analyze all WAV files in a directory."""
    wav_dir = Path(args.dir)
    wav_files = sorted(wav_dir.glob("*.wav"))

    if not wav_files:
        print(f"  [!] No WAV files in {wav_dir}")
        return

    print(f"\n{'=' * 70}")
    print(f"  BATCH SPEECH ANALYSIS — {len(wav_files)} files")
    print(f"{'=' * 70}\n")

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    all_results = {}

    for fpath in wav_files:
        result = analyze_wav(str(fpath), verbose=True)
        all_results[result["file"]] = result

        # Generate plot for each
        sr, data = wavfile.read(str(fpath))
        if data.ndim > 1: data = data[:, 0]
        data = data.astype(np.float64)
        if np.max(np.abs(data)) > 0: data = data / np.max(np.abs(data))
        plot_analysis(result, data, sr, PLOTS_DIR)

    # Summary
    scores = [r.get("speech_score", 0) for r in all_results.values()]
    speech_like = sum(1 for s in scores if s >= 10)
    structured = sum(1 for s in scores if 6 <= s < 10)
    weak = sum(1 for s in scores if 3 <= s < 6)
    noise = sum(1 for s in scores if s < 3)

    print(f"\n{'=' * 70}")
    print(f"  SUMMARY")
    print(f"{'=' * 70}")
    print(f"  SPEECH-LIKE (>=10/15): {speech_like}")
    print(f"  STRUCTURED  (6-9/15):  {structured}")
    print(f"  WEAK        (3-5/15):  {weak}")
    print(f"  NOISE-LIKE  (<3/15):   {noise}")

    # Aggregate vowel distribution
    all_vowels = Counter()
    for r in all_results.values():
        for v, c in r.get("vowel_distribution", {}).items():
            all_vowels[v] += c
    print(f"\n  Aggregate vowel distribution:")
    for v, c in all_vowels.most_common():
        bar = "#" * min(c, 50)
        print(f"    {v:15s} {c:4d} {bar}")

    # Aggregate rhythm
    rhythms = Counter(r.get("rhythm_classification", "?") for r in all_results.values())
    print(f"\n  Rhythm classifications:")
    for rhythm, count in rhythms.most_common():
        print(f"    {rhythm:40s} {count}")

    # Save
    out = RESULTS_DIR / "batch_analysis.json"
    json.dump(all_results, open(out, "w"), indent=2, default=str)
    print(f"\n  Results: {out}")
    print(f"  Plots:   {PLOTS_DIR}/")


def main():
    parser = argparse.ArgumentParser(description="Speech Pattern Analyzer")
    sub = parser.add_subparsers(dest="command")

    p_analyze = sub.add_parser("analyze", help="Analyze single WAV")
    p_analyze.add_argument("file", help="Path to WAV file")

    p_batch = sub.add_parser("batch", help="Analyze all WAVs in directory")
    p_batch.add_argument("--dir", default="results/audio", help="Directory with WAV files")

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

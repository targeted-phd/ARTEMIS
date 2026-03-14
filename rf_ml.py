#!/usr/bin/env python3
"""
RF Signal ML Analysis Pipeline — Feature extraction, symptom correlation,
signal fingerprinting, operational mode detection, and KG-augmented evidence.

Subcommands:
  features     Extract 190+ features per cycle + 27 per IQ + autoencoder embeddings
  correlate    Statistical symptom-RF correlation with permutation testing
  fingerprint  Cluster IQ captures by modulation type, find signal templates
  modes        Discover operational modes (scan/lock-on/track/burst)
  report       Generate evidence report with all findings
  all          Run everything sequentially

Usage:
  python rf_ml.py features
  python rf_ml.py correlate
  python rf_ml.py fingerprint
  python rf_ml.py modes
  python rf_ml.py report
  python rf_ml.py all
"""

import argparse
import json
import os
import sys
import glob
import hashlib
import time
import warnings
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy import stats as sp_stats
from scipy.signal import find_peaks, correlate as sig_correlate
from scipy.fft import fft, ifft

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Config ─────────────────────────────────────────────────────────────────

SAMPLE_RATE = 2_400_000
SETTLE_SAMPLES = 48_000
DC_NOTCH_BINS = 32
MIN_PULSE_SAMPLES = 3

RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", "results"))
CAPTURES_DIR = Path(os.environ.get("IQ_DUMP_DIR", "captures"))
ML_DIR = RESULTS_DIR / "ml"
PLOTS_DIR = ML_DIR / "plots"
MODELS_DIR = ML_DIR / "models"
SYMPTOM_LOG = RESULTS_DIR / "evidence" / "symptom_log.jsonl"

ALL_TARGET_FREQS = [622.0, 624.0, 628.0, 630.0, 632.0, 634.0, 636.0,
                    826.0, 828.0, 830.0, 832.0, 834.0, 878.0]
ZONE_A = [622.0, 624.0, 628.0, 630.0, 632.0, 634.0, 636.0]
ZONE_B = [826.0, 828.0, 830.0, 832.0, 834.0, 878.0]

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

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AUTH = (os.environ.get("NEO4J_USER", "neo4j"),
              os.environ.get("NEO4J_PASSWORD", "rfmonitor2026"))

FREQ_COLORS = {
    622.0: "#ff4444", 624.0: "#ff6644", 628.0: "#ff8844",
    630.0: "#ffaa44", 632.0: "#ffcc44", 634.0: "#ffee44", 636.0: "#eeff44",
    826.0: "#ff6b6b", 828.0: "#ffa94d", 830.0: "#ffd43b",
    832.0: "#69db7c", 834.0: "#4dabf7", 878.0: "#da77f2",
}

plt.style.use("dark_background")
plt.rcParams.update({
    "font.family": "monospace",
    "axes.grid": True,
    "grid.alpha": 0.15,
    "grid.linewidth": 0.5,
})


# ── Data Loading ───────────────────────────────────────────────────────────

MASTER_DATASET = RESULTS_DIR / "ml_master_dataset.json"


def load_master_dataset():
    """Load the consolidated master dataset (preferred) or fall back to raw JSONL."""
    if MASTER_DATASET.exists():
        ds = json.load(open(MASTER_DATASET))
        print(f"  Loaded master dataset: {len(ds.get('timeline', []))} timeline rows, "
              f"{len(ds.get('symptoms', []))} symptoms, "
              f"{len(ds.get('iq_captures', []))} IQ captures, "
              f"{len(ds.get('spectrograms', []))} spectrograms, "
              f"{len(ds.get('wideband_survey', []))} survey points")
        return ds
    print("  [!] Master dataset not found, falling back to raw JSONL")
    return None


def load_sentinel_logs():
    """Load all sentinel JSONL files, sorted chronologically."""
    log_files = sorted(RESULTS_DIR.glob("sentinel_*.jsonl"))
    if not log_files:
        print("  [!] No sentinel log files found")
        return []
    cycles = []
    for lf in log_files:
        for line in open(lf):
            line = line.strip()
            if not line:
                continue
            try:
                cycles.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    cycles.sort(key=lambda c: c.get("timestamp", ""))
    print(f"  Loaded {len(cycles)} cycles from {len(log_files)} files")
    return cycles


def load_symptom_events():
    """Load symptom log entries."""
    if not SYMPTOM_LOG.exists():
        print("  [!] No symptom log found")
        return []
    events = []
    for line in open(SYMPTOM_LOG):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    print(f"  Loaded {len(events)} symptom events")
    return events


def load_iq(filepath):
    """Load RTL-SDR raw IQ (unsigned 8-bit interleaved I/Q)."""
    raw = np.fromfile(filepath, dtype=np.uint8)
    iq = (raw[0::2].astype(np.float32) - 127.5) + \
         1j * (raw[1::2].astype(np.float32) - 127.5)
    if len(iq) > SETTLE_SAMPLES:
        iq = iq[SETTLE_SAMPLES:]
    # DC notch
    if len(iq) > 1024:
        spectrum = fft(iq)
        n = len(spectrum)
        spectrum[:DC_NOTCH_BINS] = 0
        spectrum[n - DC_NOTCH_BINS:] = 0
        iq = ifft(spectrum)
    return iq


def load_iq_metadata(filepath):
    """Load companion .json sidecar for an IQ file."""
    json_path = filepath + ".json" if not filepath.endswith(".json") else filepath
    if os.path.exists(json_path):
        try:
            return json.load(open(json_path))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def parse_timestamp(ts_str):
    """Parse ISO 8601 timestamp."""
    ts_str = ts_str.replace("+00:00", "+0000").replace("Z", "+0000")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(ts_str.replace("Z", "").replace("+0000", ""))


def parse_iq_filename(fname):
    """Extract timestamp and frequency from IQ filename."""
    base = os.path.basename(fname).replace(".iq", "")
    parts = base.split("_")
    freq = None
    ts_str = None
    for p in parts:
        if "MHz" in p:
            try:
                freq = float(p.replace("MHz", ""))
            except ValueError:
                pass
    # Try to get timestamp from first parts
    if len(parts) >= 2:
        ts_str = f"{parts[0]}_{parts[1]}"
    return freq, ts_str


# ── Feature Engineering ────────────────────────────────────────────────────

def extract_features_from_master(ds):
    """Extract feature matrix directly from master dataset timeline.
    This is preferred over re-parsing JSONL since the master dataset
    already has integrated metrics (NDP, pulse durations, exposure index)."""
    from tqdm import tqdm

    timeline = ds.get("timeline", [])
    if not timeline:
        return None, None, None

    # Discover all numeric fields from first non-gap row
    sample = next((r for r in timeline if r.get("type") != "GAP_NO_DATA"), timeline[0])
    # Exclude metadata fields
    skip = {"cst", "type", "day_of_week", "has_zone_a"}
    numeric_fields = []
    for k, v in sample.items():
        if k in skip:
            continue
        if isinstance(v, (int, float)):
            numeric_fields.append(k)

    numeric_fields = sorted(numeric_fields)
    print(f"  Master dataset: {len(timeline)} rows, {len(numeric_fields)} numeric features")
    print(f"  Features: {', '.join(numeric_fields[:10])}...")

    X = np.full((len(timeline), len(numeric_fields)), np.nan, dtype=np.float32)
    meta = []

    for i, row in enumerate(tqdm(timeline, desc="  Extracting master features", ncols=80)):
        meta.append({
            "index": i,
            "cst": row.get("cst", ""),
            "type": row.get("type", ""),
            "has_zone_a": row.get("has_zone_a", False),
        })
        if row.get("type") == "GAP_NO_DATA":
            continue
        for j, field in enumerate(numeric_fields):
            val = row.get(field)
            if val is not None and isinstance(val, (int, float)):
                X[i, j] = float(val)

    return X, numeric_fields, meta


def extract_cycle_features(cycles):
    """Extract feature matrix from sentinel cycles.
    Returns (feature_matrix, feature_names, cycle_meta)."""
    from tqdm import tqdm

    # Discover all frequencies present
    all_freqs = set()
    for c in cycles:
        stare = c.get("stare", {})
        for fstr in stare:
            try:
                all_freqs.add(float(fstr))
            except ValueError:
                pass
    freq_list = sorted(all_freqs)
    if not freq_list:
        freq_list = ALL_TARGET_FREQS

    feature_names = []
    # Per-frequency features (18 per freq)
    for f in freq_list:
        fn = f"{f:.0f}"
        feature_names.extend([
            f"kurt_mean_{fn}", f"kurt_max_{fn}", f"kurt_min_{fn}", f"kurt_std_{fn}",
            f"papr_mean_{fn}", f"papr_max_{fn}",
            f"pwr_mean_{fn}", f"pwr_max_{fn}",
            f"pulse_count_{fn}", f"pulse_max_snr_{fn}",
            f"pulse_width_mean_{fn}", f"pulse_width_std_{fn}",
            f"ipi_mean_{fn}", f"ipi_std_{fn}",
            # New: integrated power metrics from backfill agent
            f"mean_pulse_width_us_{fn}", f"total_pulse_duration_us_{fn}",
            f"ndp_{fn}",             # non-dimensional power: kurt * total_pulse_duration
            f"jitter_spread_{fn}",   # frequency jitter range within cycle
        ])
    # Global features
    feature_names.extend([
        "n_active_freqs", "n_active_zone_a", "n_active_zone_b",
        "total_pulses", "max_kurt_any", "mean_kurt_all",
        "zone_a_mean_kurt", "zone_b_mean_kurt",
        "zone_ab_correlation",
        "hour_of_day", "minute_of_hour",
        "exposure_index", "ei_zone_a", "ei_zone_b",
        # Derived global
        "total_pulse_duration_all",  # sum of all pulse durations across freqs
        "ndp_total",                 # total non-dimensional power across all freqs
        "max_ndp_any",               # max NDP on any single freq
        "zone_a_ndp", "zone_b_ndp",  # NDP per zone
    ])

    n_per_freq = 18
    n_global = 19
    n_features = len(freq_list) * n_per_freq + n_global

    X = np.full((len(cycles), n_features), np.nan, dtype=np.float32)
    meta = []

    for i, c in enumerate(tqdm(cycles, desc="  Extracting cycle features", ncols=80)):
        stare = c.get("stare", {})
        ts = c.get("timestamp", "")
        cycle_num = c.get("cycle", i)

        try:
            dt = parse_timestamp(ts)
            hour = dt.hour + dt.minute / 60.0
            minute = dt.minute
        except Exception:
            hour = np.nan
            minute = np.nan

        meta.append({
            "cycle": cycle_num,
            "timestamp": ts,
            "index": i,
        })

        all_kurts = []
        zone_a_kurts = []
        zone_b_kurts = []
        total_pulses = 0
        all_ndps = []
        all_total_pd = 0
        zone_a_ndp_sum = 0
        zone_b_ndp_sum = 0

        for fi, freq in enumerate(freq_list):
            fstr = str(freq)
            readings = stare.get(fstr, [])
            if not readings or not isinstance(readings, list):
                continue

            kurts = [r.get("kurtosis", 0) for r in readings if isinstance(r, dict)]
            paprs = [r.get("papr_db", 0) for r in readings if isinstance(r, dict)]
            pwrs = [r.get("mean_pwr_db", -99) for r in readings if isinstance(r, dict)]
            pcounts = [r.get("pulse_count", 0) for r in readings if isinstance(r, dict)]
            pulses_flat = []
            for r in readings:
                if isinstance(r, dict):
                    pulses_flat.extend(r.get("pulses", []))

            if not kurts:
                continue

            offset = fi * n_per_freq
            X[i, offset + 0] = np.mean(kurts)
            X[i, offset + 1] = np.max(kurts)
            X[i, offset + 2] = np.min(kurts)
            X[i, offset + 3] = np.std(kurts) if len(kurts) > 1 else 0
            X[i, offset + 4] = np.mean(paprs) if paprs else 0
            X[i, offset + 5] = np.max(paprs) if paprs else 0
            X[i, offset + 6] = np.mean(pwrs) if pwrs else -99
            X[i, offset + 7] = np.max(pwrs) if pwrs else -99
            X[i, offset + 8] = sum(pcounts)
            X[i, offset + 9] = max((p.get("snr_db", 0) for p in pulses_flat), default=0)

            # Pulse widths
            widths = [p.get("width_us", 0) for p in pulses_flat if p.get("width_us", 0) > 0]
            X[i, offset + 10] = np.mean(widths) if widths else 0
            X[i, offset + 11] = np.std(widths) if len(widths) > 1 else 0

            # Inter-pulse intervals
            offsets_us = sorted([p.get("offset_us", 0) for p in pulses_flat])
            if len(offsets_us) > 1:
                ipis = np.diff(offsets_us)
                ipis = ipis[ipis > 0]
                if len(ipis) > 0:
                    X[i, offset + 12] = np.mean(ipis)
                    X[i, offset + 13] = np.std(ipis) if len(ipis) > 1 else 0

            # New backfill fields: mean_pulse_width_us, total_pulse_duration_us
            mpw_vals = [r.get("mean_pulse_width_us", 0) for r in readings if isinstance(r, dict)]
            tpd_vals = [r.get("total_pulse_duration_us", 0) for r in readings if isinstance(r, dict)]
            X[i, offset + 14] = np.mean(mpw_vals) if mpw_vals else 0
            total_pd = sum(tpd_vals)
            X[i, offset + 15] = total_pd

            # Non-dimensional power: kurtosis × total pulse duration (integrated energy proxy)
            mean_kurt = np.mean(kurts)
            ndp = mean_kurt * total_pd
            X[i, offset + 16] = ndp

            # Jitter spread: range of actual jitter offsets within this cycle
            jitter_vals = [r.get("jitter_mhz", 0) for r in readings if isinstance(r, dict)]
            X[i, offset + 17] = (max(jitter_vals) - min(jitter_vals)) if jitter_vals else 0

            all_kurts.extend(kurts)
            total_pulses += sum(pcounts)
            all_ndps.append(ndp)
            all_total_pd += total_pd
            if freq in ZONE_A:
                zone_a_kurts.extend(kurts)
                zone_a_ndp_sum += ndp
            elif freq in ZONE_B:
                zone_b_kurts.extend(kurts)
                zone_b_ndp_sum += ndp

        # Global features
        goffset = len(freq_list) * n_per_freq
        n_active = sum(1 for k in all_kurts if k > 20) if all_kurts else 0
        n_active_a = sum(1 for k in zone_a_kurts if k > 20)
        n_active_b = sum(1 for k in zone_b_kurts if k > 20)

        X[i, goffset + 0] = n_active
        X[i, goffset + 1] = n_active_a
        X[i, goffset + 2] = n_active_b
        X[i, goffset + 3] = total_pulses
        X[i, goffset + 4] = max(all_kurts) if all_kurts else 0
        X[i, goffset + 5] = np.mean(all_kurts) if all_kurts else 0
        X[i, goffset + 6] = np.mean(zone_a_kurts) if zone_a_kurts else 0
        X[i, goffset + 7] = np.mean(zone_b_kurts) if zone_b_kurts else 0

        # Cross-zone correlation (per-cycle)
        if zone_a_kurts and zone_b_kurts and len(zone_a_kurts) > 2 and len(zone_b_kurts) > 2:
            # Use mean of each zone for this cycle
            X[i, goffset + 8] = 1.0 if np.mean(zone_a_kurts) > 20 and np.mean(zone_b_kurts) > 20 else 0.0
        else:
            X[i, goffset + 8] = 0.0

        X[i, goffset + 9] = hour
        X[i, goffset + 10] = minute
        X[i, goffset + 11] = c.get("exposure_index", 0)
        X[i, goffset + 12] = c.get("ei_zone_a", 0)
        X[i, goffset + 13] = c.get("ei_zone_b", 0)
        X[i, goffset + 14] = all_total_pd
        X[i, goffset + 15] = sum(all_ndps) if all_ndps else 0
        X[i, goffset + 16] = max(all_ndps) if all_ndps else 0
        X[i, goffset + 17] = zone_a_ndp_sum
        X[i, goffset + 18] = zone_b_ndp_sum

    return X, feature_names, meta, freq_list


def extract_iq_features(iq_files):
    """Extract 27 handcrafted features from each IQ capture.
    Returns (feature_matrix, feature_names, file_meta)."""
    from tqdm import tqdm

    feature_names = [
        "spectral_centroid", "spectral_bandwidth", "spectral_rolloff",
        "spectral_flatness",
        "env_kurtosis", "env_skewness", "env_papr", "modulation_depth",
        "burst_rate", "burst_regularity", "prf_estimate",
        "energy_mean", "energy_std", "energy_kurtosis",
        "cepstral_0", "cepstral_1", "cepstral_2", "cepstral_3",
        "cepstral_4", "cepstral_5", "cepstral_6", "cepstral_7",
        "cepstral_8", "cepstral_9", "cepstral_10", "cepstral_11",
        "cepstral_12",
    ]

    X = np.full((len(iq_files), len(feature_names)), np.nan, dtype=np.float32)
    meta = []

    for i, fpath in enumerate(tqdm(iq_files, desc="  Extracting IQ features", ncols=80)):
        try:
            iq = load_iq(fpath)
            if len(iq) < 1000:
                meta.append({"file": fpath, "valid": False})
                continue

            freq, ts_str = parse_iq_filename(fpath)
            jmeta = load_iq_metadata(fpath)
            meta.append({
                "file": fpath,
                "freq_mhz": freq or jmeta.get("freq_mhz", 0),
                "kurtosis": jmeta.get("kurtosis", 0),
                "valid": True,
            })

            amp = np.abs(iq).astype(np.float32)
            n = len(amp)

            # Power spectrum
            pspec = np.abs(fft(iq)) ** 2
            pspec = pspec[:n // 2]
            pspec_norm = pspec / (pspec.sum() + 1e-12)
            freqs_hz = np.arange(len(pspec)) * SAMPLE_RATE / n

            # Spectral features
            X[i, 0] = np.sum(freqs_hz * pspec_norm)  # centroid
            X[i, 1] = np.sqrt(np.sum(((freqs_hz - X[i, 0]) ** 2) * pspec_norm))  # bandwidth
            cumspec = np.cumsum(pspec_norm)
            X[i, 2] = freqs_hz[np.searchsorted(cumspec, 0.85)]  # rolloff
            geo_mean = np.exp(np.mean(np.log(pspec + 1e-12)))
            arith_mean = np.mean(pspec) + 1e-12
            X[i, 3] = geo_mean / arith_mean  # flatness

            # Envelope features
            X[i, 4] = float(sp_stats.kurtosis(amp, fisher=False))
            X[i, 5] = float(sp_stats.skew(amp))
            peak_pwr = np.max(amp ** 2)
            avg_pwr = np.mean(amp ** 2)
            X[i, 6] = 10 * np.log10(peak_pwr / (avg_pwr + 1e-12))  # PAPR
            X[i, 7] = peak_pwr / (avg_pwr + 1e-12)  # modulation depth

            # Burst detection (simple threshold)
            mu, sigma = np.mean(amp), np.std(amp)
            thresh = mu + 3 * sigma
            above = (amp > thresh).astype(np.int8)
            diffs = np.diff(np.concatenate(([0], above, [0])))
            starts = np.where(diffs == 1)[0]
            ends = np.where(diffs == -1)[0]
            burst_count = len(starts)
            duration_s = n / SAMPLE_RATE
            X[i, 8] = burst_count / duration_s  # burst rate

            if burst_count > 1:
                burst_centers = (starts[:len(ends)] + ends[:len(starts)]) / 2
                if len(burst_centers) > 1:
                    ibis = np.diff(burst_centers) / SAMPLE_RATE
                    X[i, 9] = np.std(ibis) / (np.mean(ibis) + 1e-12)  # regularity (CV)
                    X[i, 10] = 1.0 / (np.mean(ibis) + 1e-12)  # PRF

            # Short-time energy
            hop = n // 64
            if hop > 0:
                n_frames = n // hop
                ste = np.array([np.mean(amp[j*hop:(j+1)*hop] ** 2) for j in range(n_frames)])
                X[i, 11] = np.mean(ste)
                X[i, 12] = np.std(ste)
                X[i, 13] = float(sp_stats.kurtosis(ste, fisher=False)) if len(ste) > 3 else 0

            # Cepstral coefficients (13)
            log_pspec = np.log(pspec + 1e-12)
            cepstrum = np.real(ifft(log_pspec))
            n_cep = min(13, len(cepstrum))
            X[i, 14:14 + n_cep] = cepstrum[:n_cep]

        except Exception as e:
            meta.append({"file": fpath, "valid": False, "error": str(e)})
            continue

    return X, feature_names, meta


def train_autoencoder(iq_files, embed_dim=64, epochs=30, batch_size=32):
    """Train 1D CNN autoencoder on IQ spectrograms, return embeddings."""
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    from tqdm import tqdm

    # GTX 1080 (sm_61) not supported by torch 2.10+ CUDA kernels
    # Force CPU — still fast: ~3 min for 2896 spectrograms
    device = torch.device("cpu")
    print(f"  Autoencoder device: {device}")

    # Compute spectrograms
    print("  Computing spectrograms...")
    specs = []
    valid_idx = []
    for i, fpath in enumerate(tqdm(iq_files, desc="  Spectrograms", ncols=80)):
        try:
            iq = load_iq(fpath)
            if len(iq) < 4096:
                continue
            amp = np.abs(iq).astype(np.float32)
            # Simple spectrogram: reshape into frames, compute FFT
            fft_size = 256
            hop = 128
            n_frames = (len(amp) - fft_size) // hop
            if n_frames < 10:
                continue
            # Limit to 256 frames for uniform input
            n_frames = min(n_frames, 256)
            frames = np.array([amp[j*hop:j*hop+fft_size] for j in range(n_frames)])
            spec = np.abs(np.fft.rfft(frames * np.hanning(fft_size), axis=1))
            # spec shape: (n_frames, fft_size//2+1) = (256, 129)
            # Pad or truncate to exactly 256 frames
            if spec.shape[0] < 256:
                pad = np.zeros((256 - spec.shape[0], spec.shape[1]))
                spec = np.vstack([spec, pad])
            spec = spec[:256]
            # Log scale
            spec = np.log1p(spec)
            specs.append(spec)
            valid_idx.append(i)
        except Exception:
            continue

    if len(specs) < 50:
        print(f"  [!] Only {len(specs)} valid spectrograms, skipping autoencoder")
        return None, None, valid_idx

    specs_arr = np.array(specs, dtype=np.float32)
    # Shape: (N, 256, 129) -> treat as (N, 129, 256) for Conv1d (channels=129, length=256)
    specs_arr = np.transpose(specs_arr, (0, 2, 1))

    n_channels = specs_arr.shape[1]  # 129
    seq_len = specs_arr.shape[2]     # 256

    # Split train/val
    n = len(specs_arr)
    perm = np.random.permutation(n)
    n_train = int(0.8 * n)
    train_data = torch.FloatTensor(specs_arr[perm[:n_train]])
    val_data = torch.FloatTensor(specs_arr[perm[n_train:]])

    train_loader = DataLoader(TensorDataset(train_data), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(val_data), batch_size=batch_size)

    # Autoencoder architecture
    class Encoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(n_channels, 64, 5, stride=2, padding=2),
                nn.BatchNorm1d(64), nn.ReLU(),
                nn.Conv1d(64, 32, 5, stride=2, padding=2),
                nn.BatchNorm1d(32), nn.ReLU(),
                nn.Conv1d(32, 16, 3, stride=2, padding=1),
                nn.BatchNorm1d(16), nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.fc = nn.Linear(16, embed_dim)

        def forward(self, x):
            h = self.conv(x).squeeze(-1)
            return self.fc(h)

    class Decoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc = nn.Linear(embed_dim, 16 * 32)
            self.deconv = nn.Sequential(
                nn.ConvTranspose1d(16, 32, 4, stride=2, padding=1),
                nn.BatchNorm1d(32), nn.ReLU(),
                nn.ConvTranspose1d(32, 64, 4, stride=2, padding=1),
                nn.BatchNorm1d(64), nn.ReLU(),
                nn.ConvTranspose1d(64, n_channels, 4, stride=2, padding=1),
            )

        def forward(self, z):
            h = self.fc(z).view(-1, 16, 32)
            out = self.deconv(h)
            return out[:, :, :seq_len]

    class Autoencoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = Encoder()
            self.decoder = Decoder()

        def forward(self, x):
            z = self.encoder(x)
            return self.decoder(z), z

    model = Autoencoder().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    print(f"  Training autoencoder ({n_train} train, {n - n_train} val)...")
    best_val_loss = float("inf")
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for (batch,) in train_loader:
            batch = batch.to(device)
            recon, _ = model(batch)
            loss = criterion(recon, batch)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * batch.size(0)
        train_loss /= n_train

        model.eval()
        val_loss = 0
        with torch.no_grad():
            for (batch,) in val_loader:
                batch = batch.to(device)
                recon, _ = model(batch)
                val_loss += criterion(recon, batch).item() * batch.size(0)
        val_loss /= max(n - n_train, 1)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), MODELS_DIR / "autoencoder.pt")

        if (epoch + 1) % 5 == 0:
            print(f"    Epoch {epoch+1:3d}: train={train_loss:.6f} val={val_loss:.6f}")

    # Extract embeddings for all samples
    model.load_state_dict(torch.load(MODELS_DIR / "autoencoder.pt", weights_only=True))
    model.eval()
    all_data = torch.FloatTensor(specs_arr).to(device)
    embeddings = []
    with torch.no_grad():
        for start in range(0, len(all_data), batch_size):
            batch = all_data[start:start + batch_size]
            _, z = model(batch)
            embeddings.append(z.cpu().numpy())
    embeddings = np.vstack(embeddings)

    print(f"  Autoencoder done: {embeddings.shape[0]} × {embeddings.shape[1]} embeddings")
    return model, embeddings, valid_idx


# ── KG Integration ─────────────────────────────────────────────────────────

def kg_search(query, mode="deep", top_k=5):
    """Search knowledge graph for relevant literature."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
        with driver.session() as session:
            if mode == "deep":
                # Vector similarity search on chunk embeddings
                result = session.run("""
                    CALL db.index.vector.queryNodes('chunk_embedding', $k, $query_embedding)
                    YIELD node, score
                    MATCH (p:Paper)-[:HAS_CHUNK]->(node)
                    RETURN p.title AS title, node.text AS text,
                           node.section AS section, score
                    ORDER BY score DESC LIMIT $k
                """, k=top_k, query_embedding=_embed_text(query))
                return [dict(r) for r in result]
            elif mode == "concept":
                result = session.run("""
                    CALL db.index.vector.queryNodes('entity_embedding', $k, $query_embedding)
                    YIELD node, score
                    RETURN node.name AS entity, node.type AS type,
                           node.context AS context, score
                    ORDER BY score DESC LIMIT $k
                """, k=top_k, query_embedding=_embed_text(query))
                return [dict(r) for r in result]
            else:
                # Paper-level search
                result = session.run("""
                    CALL db.index.vector.queryNodes('paper_embedding', $k, $query_embedding)
                    YIELD node, score
                    RETURN node.title AS title, node.year AS year,
                           node.abstract AS abstract, score
                    ORDER BY score DESC LIMIT $k
                """, k=top_k, query_embedding=_embed_text(query))
                return [dict(r) for r in result]
        driver.close()
    except Exception as e:
        print(f"  [KG] Search failed: {e}")
        return []


def _embed_text(text):
    """Get embedding vector from Ollama."""
    import requests
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    try:
        r = requests.post(f"{url}/api/embeddings",
                         json={"model": "mxbai-embed-large", "prompt": text},
                         timeout=30)
        return r.json().get("embedding", [0.0] * 1024)
    except Exception:
        return [0.0] * 1024


def kg_literature_for_symptoms():
    """Search KG for literature matching each symptom type."""
    queries = {
        "headache": "headache microwave RF exposure pulsed radiation health effects",
        "paresthesia": "paresthesia tingling skin sensation microwave RF directed energy",
        "tinnitus": "tinnitus auditory perception microwave hearing Frey effect",
        "speech": "speech perception microwave auditory effect voice modulation",
        "pressure": "head pressure microwave RF exposure intracranial",
        "nausea": "nausea vestibular microwave RF biological effects",
        "sleep": "sleep disruption insomnia microwave RF circadian melatonin",
    }
    results = {}
    for symptom, query in queries.items():
        print(f"  [KG] Searching for: {symptom}")
        papers = kg_search(query, mode="deep", top_k=8)
        concepts = kg_search(query, mode="concept", top_k=5)
        results[symptom] = {"papers": papers, "concepts": concepts}
    return results


def kg_detection_methods():
    """Search KG for RF detection and measurement methods."""
    queries = [
        "RF signal detection measurement technique spectrum analysis",
        "pulsed microwave detection kurtosis statistical method",
        "directed energy weapon detection countermeasure",
        "electromagnetic surveillance detection sweep",
        "spread spectrum signal detection concealment cellular",
        "frequency hopping detection analysis technique",
    ]
    results = []
    for q in queries:
        print(f"  [KG] Detection methods: {q[:50]}...")
        hits = kg_search(q, mode="deep", top_k=5)
        results.extend(hits)
    # Deduplicate by text
    seen = set()
    unique = []
    for r in results:
        key = r.get("text", "")[:100]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# ── Subcommand: features ───────────────────────────────────────────────────

def cmd_features(args):
    """Extract all features."""
    print(f"\n{'='*60}")
    print("  FEATURE EXTRACTION")
    print(f"{'='*60}\n")

    ML_DIR.mkdir(parents=True, exist_ok=True)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Cycle features — prefer master dataset, fall back to raw JSONL
    print("  [1/3] Cycle-level features...")
    ds = load_master_dataset()
    if ds:
        # Use master dataset (already has integrated metrics)
        X_cycle, feat_names, cycle_meta = extract_features_from_master(ds)
        if X_cycle is not None:
            np.savez_compressed(ML_DIR / "features_cycle.npz", X=X_cycle)
            json.dump({"feature_names": feat_names,
                        "n_cycles": X_cycle.shape[0],
                        "source": "ml_master_dataset.json",
                        "meta": cycle_meta[:5]},
                      open(ML_DIR / "features_cycle_meta.json", "w"), indent=2, default=str)
            print(f"    -> {X_cycle.shape[0]} cycles × {X_cycle.shape[1]} features (master)")
            nan_pct = np.isnan(X_cycle).mean() * 100
            print(f"    -> NaN rate: {nan_pct:.1f}% (gaps = expected NaN)")
    else:
        # Fallback to raw JSONL parsing
        cycles = load_sentinel_logs()
        if cycles:
            X_cycle, feat_names, cycle_meta, freq_list = extract_cycle_features(cycles)
            np.savez_compressed(ML_DIR / "features_cycle.npz", X=X_cycle)
            json.dump({"feature_names": feat_names, "n_cycles": len(cycles),
                        "frequencies": freq_list, "source": "sentinel_*.jsonl",
                        "meta": cycle_meta[:5]},
                      open(ML_DIR / "features_cycle_meta.json", "w"), indent=2, default=str)
            print(f"    -> {X_cycle.shape[0]} cycles × {X_cycle.shape[1]} features (JSONL)")
            nan_pct = np.isnan(X_cycle).mean() * 100
            print(f"    -> NaN rate: {nan_pct:.1f}%")
        else:
            X_cycle = None

    # 2. IQ features
    print("\n  [2/3] IQ-level features...")
    iq_files = sorted(glob.glob(str(CAPTURES_DIR / "*.iq")))
    print(f"    Found {len(iq_files)} IQ files")
    if iq_files:
        X_iq, iq_feat_names, iq_meta = extract_iq_features(iq_files)
        valid = sum(1 for m in iq_meta if m.get("valid", False))
        np.savez_compressed(ML_DIR / "features_iq.npz", X=X_iq)
        json.dump({"feature_names": iq_feat_names, "n_files": len(iq_files),
                    "n_valid": valid},
                  open(ML_DIR / "features_iq_meta.json", "w"), indent=2)
        print(f"    -> {X_iq.shape[0]} files × {X_iq.shape[1]} features ({valid} valid)")
    else:
        X_iq = None

    # 3. Autoencoder embeddings
    print("\n  [3/3] Autoencoder embeddings (GPU)...")
    if iq_files and len(iq_files) > 50:
        _, embeddings, valid_idx = train_autoencoder(iq_files)
        if embeddings is not None:
            np.savez_compressed(ML_DIR / "iq_embeddings.npz",
                               embeddings=embeddings, valid_idx=valid_idx)
            print(f"    -> {embeddings.shape[0]} × {embeddings.shape[1]} embeddings")
    else:
        print("    Skipped (not enough IQ files)")

    print(f"\n  Features saved to {ML_DIR}/")


# ── Subcommand: correlate ─────────────────────────────────────────────────

def cmd_correlate(args):
    """Statistical symptom-RF correlation analysis."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import roc_auc_score, roc_curve, precision_recall_curve
    from sklearn.model_selection import LeaveOneOut, StratifiedKFold
    import joblib

    print(f"\n{'='*60}")
    print("  SYMPTOM-RF CORRELATION ANALYSIS")
    print(f"{'='*60}\n")

    ML_DIR.mkdir(parents=True, exist_ok=True)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Load data — prefer master dataset
    ds = load_master_dataset()
    if ds:
        symptoms = ds.get("symptoms", [])
        cycles = ds.get("timeline", [])
    else:
        cycles = load_sentinel_logs()
        symptoms = load_symptom_events()

    if not cycles or not symptoms:
        print("  [!] Need both cycles and symptoms")
        return

    # Extract features if not already done
    feat_file = ML_DIR / "features_cycle.npz"
    meta_file = ML_DIR / "features_cycle_meta.json"
    if feat_file.exists():
        X_cycle = np.load(feat_file)["X"]
        meta = json.load(open(meta_file))
        feat_names = meta["feature_names"]
    else:
        print("  Extracting features first...")
        X_cycle, feat_names, cycle_meta, _ = extract_cycle_features(cycles)

    # Build cycle lookup by cycle number
    cycle_lookup = {}
    for i, c in enumerate(cycles):
        cycle_lookup[c.get("cycle", i)] = i

    # Align symptoms to cycles
    symptom_indices = []
    symptom_types = []
    for ev in symptoms:
        cycle_num = ev.get("alert_cycle")
        if cycle_num is not None and cycle_num in cycle_lookup:
            idx = cycle_lookup[cycle_num]
            symptom_indices.append(idx)
            symptom_types.append(ev.get("symptom", ev.get("type", "unknown")))

    if not symptom_indices:
        # Fallback: match by timestamp proximity
        print("  No cycle-aligned symptoms, matching by timestamp...")
        cycle_times = []
        for c in cycles:
            try:
                ct = parse_timestamp(c["timestamp"]).timestamp()
            except Exception:
                ct = 0
            cycle_times.append(ct)
        cycle_times = np.array(cycle_times)

        for ev in symptoms:
            ts = ev.get("timestamp", "")
            try:
                et = parse_timestamp(ts).timestamp()
            except Exception:
                continue
            diffs = np.abs(cycle_times - et)
            nearest = np.argmin(diffs)
            if diffs[nearest] < 300:  # within 5 minutes
                symptom_indices.append(nearest)
                symptom_types.append(ev.get("symptom", ev.get("type", "unknown")))

    print(f"  Aligned {len(symptom_indices)} symptom events to cycles")
    print(f"  Types: {Counter(symptom_types)}")

    if len(symptom_indices) < 5:
        print("  [!] Too few aligned symptoms for statistical analysis")
        return

    # Create ±5 cycle windows around symptoms
    symptom_window = set()
    for idx in symptom_indices:
        for offset in range(-5, 6):
            if 0 <= idx + offset < len(X_cycle):
                symptom_window.add(idx + offset)

    # Null distribution: random non-symptom cycles
    non_symptom = [i for i in range(len(X_cycle)) if i not in symptom_window]
    n_null = min(1000, len(non_symptom))
    null_indices = np.random.choice(non_symptom, n_null, replace=False)

    # Get feature vectors
    X_sym = X_cycle[symptom_indices]
    X_null = X_cycle[null_indices]

    # Impute NaN with column median
    all_X = np.vstack([X_sym, X_null])
    for col in range(all_X.shape[1]):
        mask = np.isnan(all_X[:, col])
        if mask.any():
            med = np.nanmedian(all_X[:, col])
            all_X[mask, col] = med if not np.isnan(med) else 0

    X_sym = all_X[:len(symptom_indices)]
    X_null = all_X[len(symptom_indices):]

    # ── Mann-Whitney U tests ──
    print("\n  Running Mann-Whitney U tests...")
    stats_results = []
    for j, fname in enumerate(feat_names):
        sym_vals = X_sym[:, j]
        null_vals = X_null[:, j]
        sym_vals = sym_vals[~np.isnan(sym_vals)]
        null_vals = null_vals[~np.isnan(null_vals)]
        if len(sym_vals) < 3 or len(null_vals) < 3:
            continue
        if np.std(sym_vals) == 0 and np.std(null_vals) == 0:
            continue
        try:
            u_stat, p_val = sp_stats.mannwhitneyu(sym_vals, null_vals, alternative="two-sided")
            # Effect size: rank-biserial
            n1, n2 = len(sym_vals), len(null_vals)
            r_rb = 1 - (2 * u_stat) / (n1 * n2)
            # Cohen's d
            pooled_std = np.sqrt((np.var(sym_vals) + np.var(null_vals)) / 2)
            d = (np.mean(sym_vals) - np.mean(null_vals)) / (pooled_std + 1e-12)
            stats_results.append({
                "feature": fname,
                "p_value": float(p_val),
                "p_bonferroni": float(min(p_val * len(feat_names), 1.0)),
                "effect_size_d": float(d),
                "rank_biserial": float(r_rb),
                "sym_mean": float(np.mean(sym_vals)),
                "null_mean": float(np.mean(null_vals)),
                "sym_std": float(np.std(sym_vals)),
                "null_std": float(np.std(null_vals)),
            })
        except Exception:
            continue

    stats_results.sort(key=lambda x: x["p_value"])
    print(f"  Top features by significance:")
    for s in stats_results[:15]:
        sig = "***" if s["p_bonferroni"] < 0.001 else "**" if s["p_bonferroni"] < 0.01 else "*" if s["p_bonferroni"] < 0.05 else ""
        print(f"    {s['feature']:35s} p={s['p_bonferroni']:.4e}  d={s['effect_size_d']:+.2f}  "
              f"sym={s['sym_mean']:.1f} null={s['null_mean']:.1f} {sig}")

    # ── Logistic Regression with LOO CV ──
    print("\n  Logistic regression (LOO-CV)...")
    # Use top 10 significant features
    top_feats = [s["feature"] for s in stats_results[:10]]
    top_idx = [feat_names.index(f) for f in top_feats if f in feat_names]

    y = np.array([1] * len(symptom_indices) + [0] * n_null)
    X_lr = all_X[:, top_idx]

    scaler = StandardScaler()
    X_lr_scaled = scaler.fit_transform(X_lr)

    # 5-fold stratified CV (LOO is too slow for 1000+ samples)
    skf_main = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    y_pred_proba = np.zeros(len(y))
    for train_idx, test_idx in skf_main.split(X_lr_scaled, y):
        clf = LogisticRegression(C=1.0, penalty="l2", max_iter=1000, solver="lbfgs")
        clf.fit(X_lr_scaled[train_idx], y[train_idx])
        y_pred_proba[test_idx] = clf.predict_proba(X_lr_scaled[test_idx])[:, 1]

    auc = roc_auc_score(y, y_pred_proba)
    print(f"  5-fold CV ROC-AUC: {auc:.4f}")

    # Train final model on all data
    clf_final = LogisticRegression(C=1.0, penalty="l2", max_iter=1000, solver="lbfgs")
    clf_final.fit(X_lr_scaled, y)
    joblib.dump(clf_final, MODELS_DIR / "logistic_symptom.joblib")
    joblib.dump(scaler, MODELS_DIR / "scaler_cycle.joblib")

    # Feature importances
    coefs = dict(zip(top_feats, clf_final.coef_[0]))

    # ── Permutation test ──
    # Use stratified shuffle split instead of full LOO for each permutation
    # 500 perms × 5-fold CV is statistically valid and 200x faster than 10K × LOO
    from sklearn.model_selection import StratifiedKFold
    from tqdm import tqdm
    n_perms = 2000
    perm_aucs = np.zeros(n_perms)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    print(f"\n  Permutation test ({n_perms} iterations, 5-fold CV)...")
    for pi in tqdm(range(n_perms), desc="  Permutations", ncols=80):
        y_perm = np.random.permutation(y)
        y_pp = np.zeros(len(y))
        for train_idx, test_idx in skf.split(X_lr_scaled, y_perm):
            clf_p = LogisticRegression(C=1.0, penalty="l2", max_iter=500, solver="lbfgs")
            try:
                clf_p.fit(X_lr_scaled[train_idx], y_perm[train_idx])
                y_pp[test_idx] = clf_p.predict_proba(X_lr_scaled[test_idx])[:, 1]
            except Exception:
                y_pp[test_idx] = 0.5
        try:
            perm_aucs[pi] = roc_auc_score(y_perm, y_pp)
        except Exception:
            perm_aucs[pi] = 0.5

    perm_p = (np.sum(perm_aucs >= auc) + 1) / (n_perms + 1)
    print(f"  Permutation p-value: {perm_p:.6f}")
    print(f"  (Observed AUC {auc:.4f} vs permutation mean {np.mean(perm_aucs):.4f})")

    # ── Temporal lag cross-correlation ──
    print("\n  Temporal lag analysis...")
    # Binary symptom time series
    sym_ts = np.zeros(len(cycles))
    for idx in symptom_indices:
        sym_ts[idx] = 1

    # RF feature time series (max kurtosis)
    goffset_maxk = feat_names.index("max_kurt_any") if "max_kurt_any" in feat_names else -1
    if goffset_maxk >= 0:
        rf_ts = X_cycle[:, goffset_maxk].copy()
        rf_ts[np.isnan(rf_ts)] = 0
        # Cross-correlation
        max_lag = 30  # cycles
        lags = range(-max_lag, max_lag + 1)
        xcorr = []
        for lag in lags:
            if lag >= 0:
                r = np.corrcoef(rf_ts[:len(rf_ts)-lag], sym_ts[lag:])[0, 1]
            else:
                r = np.corrcoef(rf_ts[-lag:], sym_ts[:len(sym_ts)+lag])[0, 1]
            xcorr.append(r if not np.isnan(r) else 0)
        peak_lag = lags[np.argmax(np.abs(xcorr))]
        peak_r = xcorr[np.argmax(np.abs(xcorr))]
    else:
        lags, xcorr, peak_lag, peak_r = [], [], 0, 0

    # ── KG Literature Correlation ──
    print("\n  Searching KG for symptom literature...")
    kg_lit = {}
    try:
        kg_lit = kg_literature_for_symptoms()
    except Exception as e:
        print(f"  [KG] Failed: {e}")

    # ── Save results ──
    corr_results = {
        "n_symptoms": len(symptom_indices),
        "n_null": n_null,
        "symptom_types": Counter(symptom_types),
        "mann_whitney": stats_results[:30],
        "logistic_auc": float(auc),
        "logistic_coefs": {k: float(v) for k, v in coefs.items()},
        "permutation_p": float(perm_p),
        "permutation_mean_auc": float(np.mean(perm_aucs)),
        "lag_analysis": {
            "peak_lag_cycles": int(peak_lag),
            "peak_correlation": float(peak_r),
        },
        "kg_literature": {k: {"n_papers": len(v.get("papers", [])),
                               "n_concepts": len(v.get("concepts", [])),
                               "top_paper": v["papers"][0].get("title", "") if v.get("papers") else ""}
                          for k, v in kg_lit.items()},
    }
    json.dump(corr_results, open(ML_DIR / "correlation_stats.json", "w"),
              indent=2, default=str)

    # ── Plots ──
    print("\n  Generating correlation plots...")

    # 1. Symptom vs null distribution (top 6 features)
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for ax, s in zip(axes.flat, stats_results[:6]):
        fname = s["feature"]
        fi = feat_names.index(fname)
        sym_v = X_sym[:, fi]
        null_v = X_null[:, fi]
        sym_v = sym_v[~np.isnan(sym_v)]
        null_v = null_v[~np.isnan(null_v)]
        parts = ax.violinplot([null_v, sym_v], positions=[0, 1], showmedians=True)
        for pc in parts['bodies']:
            pc.set_alpha(0.5)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Null", "Symptom"])
        p_str = f"p={s['p_bonferroni']:.2e}" if s['p_bonferroni'] < 0.05 else f"p={s['p_bonferroni']:.2f}"
        ax.set_title(f"{fname}\n{p_str}, d={s['effect_size_d']:+.2f}", fontsize=9)
    fig.suptitle("Symptom vs Null Distribution — Top Features", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "symptom_rf_distribution.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 2. ROC curve with permutation null
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fpr, tpr, _ = roc_curve(y, y_pred_proba)
    ax1.plot(fpr, tpr, color="#4dabf7", linewidth=2, label=f"AUC = {auc:.3f}")
    ax1.plot([0, 1], [0, 1], "--", color="#888888", linewidth=0.8)
    ax1.set_xlabel("False Positive Rate")
    ax1.set_ylabel("True Positive Rate")
    ax1.set_title("ROC Curve (LOO-CV)")
    ax1.legend()

    ax2.hist(perm_aucs, bins=50, color="#888888", alpha=0.7, label="Permutation null")
    ax2.axvline(auc, color="#ff4444", linewidth=2, label=f"Observed AUC={auc:.3f}")
    ax2.set_xlabel("AUC")
    ax2.set_ylabel("Count")
    ax2.set_title(f"Permutation Test (p={perm_p:.4f})")
    ax2.legend()
    fig.suptitle("Symptom-RF Correlation — Statistical Validation", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "logistic_roc.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 3. Feature importance
    fig, ax = plt.subplots(figsize=(10, 5))
    sorted_coefs = sorted(coefs.items(), key=lambda x: abs(x[1]), reverse=True)
    names = [c[0] for c in sorted_coefs]
    vals = [c[1] for c in sorted_coefs]
    colors = ["#ff4444" if v > 0 else "#4dabf7" for v in vals]
    ax.barh(range(len(names)), vals, color=colors, alpha=0.8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("Logistic Regression Coefficient")
    ax.set_title("Feature Importance — Symptom Prediction", fontsize=13, fontweight="bold")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "feature_importance.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 4. Lag correlation
    if lags:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(lags, xcorr, color="#4dabf7", alpha=0.7, width=0.8)
        ax.axvline(peak_lag, color="#ff4444", linewidth=1.5, linestyle="--",
                   label=f"Peak lag={peak_lag} cycles (r={peak_r:.3f})")
        ax.set_xlabel("Lag (cycles)")
        ax.set_ylabel("Cross-correlation")
        ax.set_title("RF Activity → Symptom Onset Lag", fontsize=13, fontweight="bold")
        ax.legend()
        fig.tight_layout()
        fig.savefig(PLOTS_DIR / "symptom_lag_correlation.png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)

    print(f"\n  Correlation analysis complete. Results in {ML_DIR}/")


# ── Subcommand: fingerprint ───────────────────────────────────────────────

def cmd_fingerprint(args):
    """Signal modulation fingerprinting via clustering."""
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.mixture import GaussianMixture
    from sklearn.metrics import silhouette_score

    print(f"\n{'='*60}")
    print("  SIGNAL FINGERPRINTING")
    print(f"{'='*60}\n")

    ML_DIR.mkdir(parents=True, exist_ok=True)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load IQ features
    feat_file = ML_DIR / "features_iq.npz"
    if not feat_file.exists():
        print("  [!] Run 'features' first")
        return
    X_iq = np.load(feat_file)["X"]
    iq_meta = json.load(open(ML_DIR / "features_iq_meta.json"))
    feat_names = iq_meta["feature_names"]

    # Filter valid rows (no all-NaN)
    valid_mask = ~np.all(np.isnan(X_iq), axis=1)
    X = X_iq[valid_mask].copy()
    print(f"  Valid IQ features: {X.shape[0]} / {X_iq.shape[0]}")

    # Impute remaining NaN
    for col in range(X.shape[1]):
        mask = np.isnan(X[:, col])
        if mask.any():
            med = np.nanmedian(X[:, col])
            X[mask, col] = med if not np.isnan(med) else 0

    # Scale (float64 for numerical stability in GMM)
    X = X.astype(np.float64)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # PCA
    pca = PCA(n_components=min(20, X.shape[1]))
    X_pca = pca.fit_transform(X_scaled)
    print(f"  PCA: {pca.n_components_} components, "
          f"{pca.explained_variance_ratio_.sum()*100:.1f}% variance")

    # GMM clustering with BIC selection
    print("  GMM model selection (BIC)...")
    bics = []
    k_range = range(2, 9)
    for k in k_range:
        gmm = GaussianMixture(n_components=k, n_init=3, random_state=42, reg_covar=1e-4, covariance_type="diag")
        gmm.fit(X_pca)
        bics.append(gmm.bic(X_pca))
    best_k = list(k_range)[np.argmin(bics)]
    print(f"  Best k={best_k} (by BIC)")

    gmm_best = GaussianMixture(n_components=best_k, n_init=5, random_state=42, reg_covar=1e-4, covariance_type="diag")
    labels = gmm_best.fit_predict(X_pca)
    sil = silhouette_score(X_pca, labels) if len(set(labels)) > 1 else 0
    print(f"  Silhouette score: {sil:.3f}")

    # Cluster characterization
    cluster_info = []
    for k in range(best_k):
        mask = labels == k
        centroid = X[mask].mean(axis=0)
        info = {
            "cluster": k,
            "n_samples": int(mask.sum()),
            "pct": float(mask.sum() / len(labels) * 100),
        }
        for fi, fn in enumerate(feat_names):
            info[f"mean_{fn}"] = float(centroid[fi])
        cluster_info.append(info)
        print(f"    Cluster {k}: {mask.sum()} samples ({info['pct']:.1f}%)")
        print(f"      env_kurt={centroid[4]:.1f}  burst_rate={centroid[8]:.0f}/s  "
              f"prf={centroid[10]:.0f}Hz  flatness={centroid[3]:.3f}")

    # Protocol matching
    print("\n  Matching clusters to known protocols...")
    for ci in cluster_info:
        prf = ci.get("mean_prf_estimate", 0)
        if prf > 0:
            pri_us = 1e6 / prf
            matches = []
            for proto, timing in KNOWN_PROTOCOLS.items():
                ratio = pri_us / timing
                if 0.8 < ratio < 1.2 or 1.8 < ratio < 2.2:
                    matches.append(f"{proto} ({timing:.0f}μs)")
            if matches:
                ci["protocol_matches"] = matches
                print(f"    Cluster {ci['cluster']} PRI={pri_us:.0f}μs -> {', '.join(matches)}")
            else:
                ci["protocol_matches"] = ["No known match"]
                print(f"    Cluster {ci['cluster']} PRI={pri_us:.0f}μs -> No known protocol match")

    # KG signal characterization search
    print("\n  Searching KG for signal characteristics...")
    kg_matches = {}
    try:
        for ci in cluster_info:
            brate = ci.get("mean_burst_rate", 0)
            query = f"pulsed signal burst rate {brate:.0f} Hz modulation spread spectrum"
            hits = kg_search(query, mode="deep", top_k=3)
            kg_matches[ci["cluster"]] = hits
            if hits:
                print(f"    Cluster {ci['cluster']}: {hits[0].get('title', 'N/A')[:60]}")
    except Exception as e:
        print(f"  [KG] Failed: {e}")

    # Save results
    fp_results = {
        "n_clusters": best_k,
        "silhouette": float(sil),
        "bic_scores": {str(k): float(b) for k, b in zip(k_range, bics)},
        "clusters": cluster_info,
        "pca_variance": pca.explained_variance_ratio_.tolist(),
        "kg_matches": {str(k): [h.get("title", "") for h in v] for k, v in kg_matches.items()},
    }
    json.dump(fp_results, open(ML_DIR / "fingerprint_clusters.json", "w"),
              indent=2, default=str)

    # ── Plots ──
    print("\n  Generating fingerprint plots...")

    # 1. PCA scatter
    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], c=labels, cmap="Set1",
                        s=8, alpha=0.6, edgecolors="none")
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)")
    ax.set_title(f"Signal Fingerprint Clusters (k={best_k}, sil={sil:.3f})",
                fontsize=13, fontweight="bold")
    plt.colorbar(scatter, ax=ax, label="Cluster")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "fingerprint_pca.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 2. BIC curve
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(list(k_range), bics, "o-", color="#4dabf7")
    ax.axvline(best_k, color="#ff4444", linestyle="--", label=f"Best k={best_k}")
    ax.set_xlabel("Number of clusters")
    ax.set_ylabel("BIC")
    ax.set_title("Model Selection — BIC", fontsize=13, fontweight="bold")
    ax.legend()
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "fingerprint_bic.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 3. Autoencoder embedding plot (if available)
    emb_file = ML_DIR / "iq_embeddings.npz"
    if emb_file.exists():
        data = np.load(emb_file)
        embeddings = data["embeddings"]
        valid_idx = data["valid_idx"]

        # t-SNE on embeddings
        from sklearn.manifold import TSNE
        print("  Running t-SNE on embeddings...")
        tsne = TSNE(n_components=2, perplexity=30, random_state=42)
        emb_2d = tsne.fit_transform(embeddings)

        # Map labels to embedding indices
        emb_labels = np.zeros(len(embeddings), dtype=int)
        valid_set = set(valid_idx)
        label_map = {}
        vi_counter = 0
        for orig_i, is_valid in enumerate(valid_mask):
            if is_valid and orig_i in valid_set:
                if vi_counter < len(labels):
                    label_map[list(valid_set).index(orig_i) if orig_i in valid_idx else -1] = labels[vi_counter]
                vi_counter += 1

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.scatter(emb_2d[:, 0], emb_2d[:, 1], s=8, alpha=0.6,
                  c=range(len(emb_2d)), cmap="viridis", edgecolors="none")
        ax.set_xlabel("t-SNE 1")
        ax.set_ylabel("t-SNE 2")
        ax.set_title("Autoencoder Embeddings (t-SNE)", fontsize=13, fontweight="bold")
        fig.tight_layout()
        fig.savefig(PLOTS_DIR / "fingerprint_embeddings.png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)

    print(f"\n  Fingerprinting complete. Results in {ML_DIR}/")


# ── Subcommand: modes ─────────────────────────────────────────────────────

def cmd_modes(args):
    """Operational mode detection."""
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.mixture import GaussianMixture
    from sklearn.metrics import silhouette_score
    import joblib

    print(f"\n{'='*60}")
    print("  OPERATIONAL MODE DETECTION")
    print(f"{'='*60}\n")

    ML_DIR.mkdir(parents=True, exist_ok=True)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Load cycle features
    feat_file = ML_DIR / "features_cycle.npz"
    if not feat_file.exists():
        print("  [!] Run 'features' first")
        return
    X = np.load(feat_file)["X"]
    meta = json.load(open(ML_DIR / "features_cycle_meta.json"))
    feat_names = meta["feature_names"]

    cycles = load_sentinel_logs()
    symptoms = load_symptom_events()

    # Impute NaN
    for col in range(X.shape[1]):
        mask = np.isnan(X[:, col])
        if mask.any():
            med = np.nanmedian(X[:, col])
            X[mask, col] = med if not np.isnan(med) else 0

    # Scale and PCA
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    pca = PCA(n_components=0.95)
    X_pca = pca.fit_transform(X_scaled)
    print(f"  PCA: {X_pca.shape[1]} components retain 95% variance")

    # GMM with BIC
    print("  GMM model selection...")
    k_range = range(2, 9)
    bics = []
    for k in k_range:
        gmm = GaussianMixture(n_components=k, n_init=3, random_state=42, reg_covar=1e-4, covariance_type="diag")
        gmm.fit(X_pca)
        bics.append(gmm.bic(X_pca))

    best_k = list(k_range)[np.argmin(bics)]
    print(f"  Best k={best_k}")

    gmm = GaussianMixture(n_components=best_k, n_init=5, random_state=42, reg_covar=1e-4, covariance_type="diag")
    labels = gmm.fit_predict(X_pca)
    joblib.dump(gmm, MODELS_DIR / "gmm_modes.joblib")

    sil = silhouette_score(X_pca, labels) if len(set(labels)) > 1 else 0
    print(f"  Silhouette: {sil:.3f}")

    # Characterize modes
    mode_info = []
    for k in range(best_k):
        mask = labels == k
        centroid = X[mask].mean(axis=0)

        # Find key features
        max_kurt_idx = feat_names.index("max_kurt_any") if "max_kurt_any" in feat_names else -1
        n_active_idx = feat_names.index("n_active_freqs") if "n_active_freqs" in feat_names else -1
        total_pulses_idx = feat_names.index("total_pulses") if "total_pulses" in feat_names else -1
        za_idx = feat_names.index("zone_a_mean_kurt") if "zone_a_mean_kurt" in feat_names else -1
        zb_idx = feat_names.index("zone_b_mean_kurt") if "zone_b_mean_kurt" in feat_names else -1

        max_k = centroid[max_kurt_idx] if max_kurt_idx >= 0 else 0
        n_act = centroid[n_active_idx] if n_active_idx >= 0 else 0
        tot_p = centroid[total_pulses_idx] if total_pulses_idx >= 0 else 0
        za_k = centroid[za_idx] if za_idx >= 0 else 0
        zb_k = centroid[zb_idx] if zb_idx >= 0 else 0

        # Auto-label
        if max_k < 15 and n_act < 2:
            label_name = "QUIET"
        elif max_k > 150 and n_act >= 6:
            label_name = "BURST"
        elif max_k > 60:
            if n_act <= 3:
                label_name = "LOCK-ON"
            else:
                label_name = "TRACKING"
        else:
            label_name = "SCANNING"

        info = {
            "mode": k,
            "label": label_name,
            "n_cycles": int(mask.sum()),
            "pct": float(mask.sum() / len(labels) * 100),
            "max_kurtosis": float(max_k),
            "n_active_freqs": float(n_act),
            "total_pulses": float(tot_p),
            "zone_a_kurt": float(za_k),
            "zone_b_kurt": float(zb_k),
        }
        mode_info.append(info)
        print(f"    Mode {k} [{label_name:10s}]: {mask.sum():5d} cycles ({info['pct']:.1f}%)  "
              f"maxK={max_k:.0f}  active={n_act:.0f}  pulses={tot_p:.0f}")

    # Transition matrix
    trans = np.zeros((best_k, best_k))
    for i in range(len(labels) - 1):
        trans[labels[i], labels[i + 1]] += 1
    # Normalize
    row_sums = trans.sum(axis=1, keepdims=True)
    trans_norm = trans / (row_sums + 1e-12)

    print("\n  Transition matrix:")
    for i in range(best_k):
        row = " ".join(f"{trans_norm[i, j]:.2f}" for j in range(best_k))
        print(f"    {mode_info[i]['label']:10s} -> {row}")

    # Change-point detection
    changes = []
    for i in range(1, len(labels)):
        if labels[i] != labels[i - 1]:
            changes.append({
                "cycle_index": i,
                "from_mode": int(labels[i - 1]),
                "to_mode": int(labels[i]),
                "from_label": mode_info[labels[i - 1]]["label"],
                "to_label": mode_info[labels[i]]["label"],
                "timestamp": cycles[i].get("timestamp", "") if i < len(cycles) else "",
            })
    print(f"\n  Mode transitions: {len(changes)}")

    # Symptom-mode cross-tab
    symptom_by_mode = Counter()
    sym_indices = set()
    for ev in symptoms:
        cycle_num = ev.get("alert_cycle")
        if cycle_num is not None:
            for ci, c in enumerate(cycles):
                if c.get("cycle") == cycle_num and ci < len(labels):
                    symptom_by_mode[mode_info[labels[ci]]["label"]] += 1
                    sym_indices.add(ci)
                    break

    if symptom_by_mode:
        print("\n  Symptoms by mode:")
        for mode_label, count in symptom_by_mode.most_common():
            pct = count / sum(symptom_by_mode.values()) * 100
            print(f"    {mode_label:10s}: {count} ({pct:.0f}%)")

    # KG operational modes search
    print("\n  Searching KG for operational mode literature...")
    kg_modes = {}
    try:
        kg_modes = {
            "electronic_warfare": kg_search("electronic warfare operational modes scanning tracking", mode="deep", top_k=5),
            "directed_energy": kg_search("directed energy weapon modes continuous pulsed", mode="deep", top_k=5),
            "surveillance": kg_search("RF surveillance modes monitoring targeting tracking", mode="deep", top_k=5),
        }
    except Exception as e:
        print(f"  [KG] Failed: {e}")

    # Save
    modes_results = {
        "n_modes": best_k,
        "silhouette": float(sil),
        "modes": mode_info,
        "transition_matrix": trans_norm.tolist(),
        "n_transitions": len(changes),
        "symptom_by_mode": dict(symptom_by_mode),
        "kg_operational_modes": {k: [h.get("title", "") for h in v[:3]]
                                 for k, v in kg_modes.items()},
    }
    json.dump(modes_results, open(ML_DIR / "modes.json", "w"), indent=2, default=str)

    # ── Plots ──
    print("\n  Generating mode plots...")

    # 1. Modes PCA
    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], c=labels, cmap="Set1",
                        s=5, alpha=0.5, edgecolors="none")
    # Mark symptom cycles
    sym_list = list(sym_indices)
    if sym_list:
        ax.scatter(X_pca[sym_list, 0], X_pca[sym_list, 1],
                  c="white", s=40, marker="x", linewidths=1.5, label="Symptom events")
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)")
    ax.set_title(f"Operational Modes (k={best_k})", fontsize=13, fontweight="bold")
    ax.legend()
    plt.colorbar(scatter, ax=ax, label="Mode")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "modes_pca.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 2. Mode timeline
    fig, ax = plt.subplots(figsize=(16, 4))
    mode_colors = plt.cm.Set1(np.linspace(0, 1, best_k))
    for k in range(best_k):
        mask = labels == k
        ax.scatter(np.where(mask)[0], labels[mask], c=[mode_colors[k]],
                  s=3, alpha=0.7, label=mode_info[k]["label"])
    # Symptom markers
    if sym_list:
        ax.scatter(sym_list, labels[sym_list], c="white", s=50, marker="|",
                  linewidths=2, label="Symptom", zorder=5)
    ax.set_xlabel("Cycle index")
    ax.set_ylabel("Mode")
    ax.set_yticks(range(best_k))
    ax.set_yticklabels([m["label"] for m in mode_info])
    ax.set_title("Operational Mode Timeline", fontsize=13, fontweight="bold")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "modes_timeline.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 3. Transition matrix heatmap
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(trans_norm, cmap="YlOrRd", vmin=0, vmax=1)
    ax.set_xticks(range(best_k))
    ax.set_yticks(range(best_k))
    ax.set_xticklabels([m["label"] for m in mode_info], rotation=45, ha="right")
    ax.set_yticklabels([m["label"] for m in mode_info])
    ax.set_xlabel("To mode")
    ax.set_ylabel("From mode")
    ax.set_title("Mode Transition Probabilities", fontsize=13, fontweight="bold")
    for i in range(best_k):
        for j in range(best_k):
            ax.text(j, i, f"{trans_norm[i,j]:.2f}", ha="center", va="center",
                   color="white" if trans_norm[i, j] > 0.5 else "black", fontsize=9)
    plt.colorbar(im, ax=ax, label="Probability")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "modes_transition.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 4. BIC curve
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(list(k_range), bics, "o-", color="#4dabf7")
    ax.axvline(best_k, color="#ff4444", linestyle="--", label=f"Best k={best_k}")
    ax.set_xlabel("Number of modes")
    ax.set_ylabel("BIC")
    ax.set_title("Mode Count Selection — BIC", fontsize=13, fontweight="bold")
    ax.legend()
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "modes_bic.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    print(f"\n  Mode detection complete. Results in {ML_DIR}/")


# ── Subcommand: report ─────────────────────────────────────────────────────

def cmd_report(args):
    """Generate evidence report from all ML results."""
    print(f"\n{'='*60}")
    print("  EVIDENCE REPORT GENERATION")
    print(f"{'='*60}\n")

    ML_DIR.mkdir(parents=True, exist_ok=True)

    # Load all results
    corr = {}
    if (ML_DIR / "correlation_stats.json").exists():
        corr = json.load(open(ML_DIR / "correlation_stats.json"))

    fp = {}
    if (ML_DIR / "fingerprint_clusters.json").exists():
        fp = json.load(open(ML_DIR / "fingerprint_clusters.json"))

    modes = {}
    if (ML_DIR / "modes.json").exists():
        modes = json.load(open(ML_DIR / "modes.json"))

    # Search KG for detection methods
    print("  Searching KG for detection methods...")
    kg_detection = []
    try:
        kg_detection = kg_detection_methods()
    except Exception as e:
        print(f"  [KG] Detection methods search failed: {e}")

    # Generate report
    report = []
    report.append("# RF Signal ML Analysis — Evidence Report")
    report.append(f"\nGenerated: {datetime.utcnow().isoformat()}Z")
    report.append(f"Pipeline: rf_ml.py")
    report.append("")

    report.append("## Executive Summary\n")
    if corr:
        auc = corr.get("logistic_auc", 0)
        perm_p = corr.get("permutation_p", 1)
        n_sym = corr.get("n_symptoms", 0)
        report.append(f"- **Symptom-RF correlation**: AUC={auc:.3f}, permutation p={perm_p:.4f} "
                     f"(n={n_sym} symptom events)")
        if perm_p < 0.05:
            report.append(f"  - **STATISTICALLY SIGNIFICANT** at α=0.05")
        report.append(f"  - Top predictor: {corr.get('mann_whitney', [{}])[0].get('feature', 'N/A')}")

    if modes:
        n_modes = modes.get("n_modes", 0)
        report.append(f"- **Operational modes**: {n_modes} distinct modes identified")
        for m in modes.get("modes", []):
            report.append(f"  - {m['label']}: {m['n_cycles']} cycles ({m['pct']:.1f}%), "
                         f"maxK={m['max_kurtosis']:.0f}")

    if fp:
        n_clusters = fp.get("n_clusters", 0)
        report.append(f"- **Signal fingerprints**: {n_clusters} distinct modulation types")

    report.append("")
    report.append("---")
    report.append("")

    # Correlation details
    if corr:
        report.append("## Symptom-RF Correlation\n")
        report.append(f"### Statistical Tests\n")
        report.append(f"| Feature | p (Bonferroni) | Effect Size (d) | Symptom Mean | Null Mean |")
        report.append(f"|---------|---------------|-----------------|-------------|-----------|")
        for s in corr.get("mann_whitney", [])[:15]:
            sig = "***" if s["p_bonferroni"] < 0.001 else "**" if s["p_bonferroni"] < 0.01 else "*" if s["p_bonferroni"] < 0.05 else ""
            report.append(f"| {s['feature']} | {s['p_bonferroni']:.2e} {sig} | "
                         f"{s['effect_size_d']:+.2f} | {s['sym_mean']:.1f} | {s['null_mean']:.1f} |")

        report.append(f"\n### Logistic Regression\n")
        report.append(f"- ROC-AUC (LOO-CV): **{corr.get('logistic_auc', 0):.3f}**")
        report.append(f"- Permutation p-value: **{corr.get('permutation_p', 1):.4f}**")
        report.append(f"- Permutation null mean AUC: {corr.get('permutation_mean_auc', 0.5):.3f}")

        lag = corr.get("lag_analysis", {})
        if lag:
            report.append(f"\n### Temporal Lag Analysis\n")
            report.append(f"- Peak lag: {lag.get('peak_lag_cycles', 0)} cycles")
            report.append(f"- Peak correlation: r={lag.get('peak_correlation', 0):.3f}")

        kg_lit = corr.get("kg_literature", {})
        if kg_lit:
            report.append(f"\n### KG Literature — Symptom-RF Correlation\n")
            for symptom, info in kg_lit.items():
                if info.get("n_papers", 0) > 0:
                    report.append(f"- **{symptom}**: {info['n_papers']} papers, "
                                 f"{info['n_concepts']} concepts")
                    if info.get("top_paper"):
                        report.append(f"  - Top match: {info['top_paper'][:80]}")

        report.append("")

    # Fingerprint details
    if fp:
        report.append("## Signal Fingerprinting\n")
        report.append(f"- Clusters: {fp.get('n_clusters', 0)}")
        report.append(f"- Silhouette score: {fp.get('silhouette', 0):.3f}")
        for ci in fp.get("clusters", []):
            report.append(f"\n### Cluster {ci['cluster']} ({ci['n_samples']} samples, {ci['pct']:.1f}%)\n")
            report.append(f"- Envelope kurtosis: {ci.get('mean_env_kurtosis', 0):.1f}")
            report.append(f"- Burst rate: {ci.get('mean_burst_rate', 0):.0f}/s")
            report.append(f"- PRF estimate: {ci.get('mean_prf_estimate', 0):.0f} Hz")
            protos = ci.get("protocol_matches", [])
            if protos:
                report.append(f"- Protocol matches: {', '.join(protos)}")

    # Mode details
    if modes:
        report.append("\n## Operational Modes\n")
        report.append(f"- Modes discovered: {modes.get('n_modes', 0)}")
        report.append(f"- Silhouette: {modes.get('silhouette', 0):.3f}")
        report.append(f"- Mode transitions: {modes.get('n_transitions', 0)}")
        sym_by_mode = modes.get("symptom_by_mode", {})
        if sym_by_mode:
            report.append(f"\n### Symptoms by Operational Mode\n")
            report.append("| Mode | Symptom Count | % |")
            report.append("|------|--------------|---|")
            total = sum(sym_by_mode.values())
            for mode, count in sorted(sym_by_mode.items(), key=lambda x: -x[1]):
                report.append(f"| {mode} | {count} | {count/total*100:.0f}% |")

    # KG detection methods
    if kg_detection:
        report.append("\n## KG Literature — Detection Methods\n")
        for hit in kg_detection[:10]:
            title = hit.get("title", "Unknown")
            text = hit.get("text", "")[:200]
            report.append(f"- **{title}**")
            report.append(f"  > {text}...")

    # Plots index
    report.append("\n## Plots\n")
    for p in sorted(PLOTS_DIR.glob("*.png")):
        report.append(f"- [{p.name}](plots/{p.name})")

    report.append("\n## Methodology\n")
    report.append("- Feature extraction: 190+ features per sentinel cycle, 27 features per IQ capture")
    report.append("- Symptom correlation: Mann-Whitney U, logistic regression (LOO-CV), 10K permutation test")
    report.append("- Signal fingerprinting: PCA + GMM clustering on IQ features")
    report.append("- Mode detection: PCA + GMM with BIC model selection on cycle features")
    report.append("- KG integration: semantic search across 739 papers, 22K chunks, 1.7K entities")
    report.append("- All analysis local (GTX 1080), no cloud dependencies")

    report.append(f"\n## Integrity\n")
    report.append(f"- Report hash: (computed after generation)")
    report.append(f"- Generated by rf_ml.py")
    report.append(f"- Timestamp: {datetime.utcnow().isoformat()}Z")

    report_text = "\n".join(report)
    report_path = ML_DIR / "evidence_report.md"
    with open(report_path, "w") as f:
        f.write(report_text)

    # Hash the report
    h = hashlib.sha256(report_text.encode()).hexdigest()
    report_text = report_text.replace("(computed after generation)", h)
    with open(report_path, "w") as f:
        f.write(report_text)

    # Machine-readable summary
    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "report_hash": h,
        "correlation": {
            "auc": corr.get("logistic_auc", 0),
            "permutation_p": corr.get("permutation_p", 1),
            "n_symptoms": corr.get("n_symptoms", 0),
            "significant": corr.get("permutation_p", 1) < 0.05,
        },
        "fingerprints": {
            "n_clusters": fp.get("n_clusters", 0),
            "silhouette": fp.get("silhouette", 0),
        },
        "modes": {
            "n_modes": modes.get("n_modes", 0),
            "symptom_by_mode": modes.get("symptom_by_mode", {}),
        },
    }
    json.dump(summary, open(ML_DIR / "evidence_report.json", "w"), indent=2, default=str)

    print(f"  Report: {report_path}")
    print(f"  Hash: {h}")
    print(f"  JSON: {ML_DIR / 'evidence_report.json'}")


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="RF Signal ML Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Subcommands:
  features     Extract features from sentinel logs + IQ captures
  correlate    Statistical symptom-RF correlation analysis
  fingerprint  Cluster IQ captures by modulation type
  modes        Discover operational modes
  report       Generate evidence report
  all          Run entire pipeline
        """
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("features", help="Extract features")
    sub.add_parser("correlate", help="Symptom-RF correlation")
    sub.add_parser("fingerprint", help="Signal fingerprinting")
    sub.add_parser("modes", help="Operational mode detection")
    sub.add_parser("report", help="Generate evidence report")
    sub.add_parser("all", help="Run entire pipeline")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    t0 = time.time()

    if args.command == "all":
        cmd_features(args)
        cmd_correlate(args)
        cmd_fingerprint(args)
        cmd_modes(args)
        cmd_report(args)
    elif args.command == "features":
        cmd_features(args)
    elif args.command == "correlate":
        cmd_correlate(args)
    elif args.command == "fingerprint":
        cmd_fingerprint(args)
    elif args.command == "modes":
        cmd_modes(args)
    elif args.command == "report":
        cmd_report(args)

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()

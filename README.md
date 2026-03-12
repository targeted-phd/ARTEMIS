# RF Monitor

Statistical RF pulse detection toolkit using RTL-SDR. Detects short (µs-scale) pulses that averaging-based tools like `rtl_power` would miss, using kurtosis analysis, PAPR, and amplitude probability distributions.

## Architecture

```
pulse_detector.py    Calibrated band scanner — two-pass (baseline + detect)
sentinel.py          24h hardened stare + sweep monitor with migration detection
pulse_monitor.py     Single-freq watch + cross-band correlator
analyze_scan.py      Post-process scans — within-band anomaly detection
analyze_pulses.py    Pulse timing: PRIs, width distributions, cross-freq sync
plot_timeseries.py   Time-series visualization (6 plot types)
generate_report.py   Comprehensive text report with LTE comparison
known_bands.py       US RF allocation database (400-1766 MHz)
```

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install numpy scipy matplotlib

# Band scan with auto-calibration
python pulse_detector.py scan --start 400 --stop 1000

# Analyze results
python analyze_scan.py

# 24h sentinel monitoring
python sentinel.py --targets 826,828,830,832,834,878 --duration 86400

# After collection — analysis
python generate_report.py
python plot_timeseries.py
python analyze_pulses.py intervals
python analyze_pulses.py widths
python analyze_pulses.py crossfreq
```

## Detection Method

Standard spectrum analyzers average power over time, burying low-duty-cycle pulses. A 10 µs pulse in a 10s integration window is attenuated by -60 dB — invisible.

This toolkit captures raw IQ and computes:
- **Kurtosis**: Gaussian noise = ~3.0 (RTL-SDR baseline ~8-10 due to 8-bit ADC). Impulsive signals push kurtosis much higher.
- **PAPR**: Peak-to-average power ratio. Gaussian ≈ 10-12 dB. Pulses push higher.
- **Spectral flatness**: 1.0 = white noise. Tonal/narrowband content reduces it.

Two-pass calibration establishes per-band baseline statistics, then flags channels that deviate using robust median + MAD estimators.

## Hardware

- RTL-SDR Blog V4 (R828D tuner, 24 MHz - 1.766 GHz)
- Whip antenna (included with SDR)
- Any Linux machine (tested on WSL2)

## Requirements

- `rtl-sdr` package (`sudo apt install rtl-sdr`)
- Python 3.10+ with numpy, scipy, matplotlib

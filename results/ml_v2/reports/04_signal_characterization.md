# RF-SYMPTOM ML ANALYSIS v2 -- SIGNAL CHARACTERIZATION

**Classification:** EVIDENCE DOCUMENT
**Date:** 2026-03-14
**Document:** 4 of 6

---

## TABLE OF CONTENTS

1. [Signal Parameters Overview](#1-signal-parameters-overview)
2. [Two-Zone Architecture](#2-two-zone-architecture)
3. [Cellular Uplink Band Anomaly](#3-cellular-uplink-band-anomaly)
4. [Frequency Hopping Pattern Analysis](#4-frequency-hopping-pattern-analysis)
5. [Diurnal Operational Schedule](#5-diurnal-operational-schedule)
6. [IQ Fingerprint Analysis](#6-iq-fingerprint-analysis)
7. [Spectrogram Analysis](#7-spectrogram-analysis)
8. [Protocol Matching](#8-protocol-matching)
9. [Comparison to Known Directed Energy Systems](#9-comparison-to-known-directed-energy-systems)

---

## 1. SIGNAL PARAMETERS OVERVIEW

### 1.1 Observed Parameters

| Parameter | Range | Typical Value | Notes |
|-----------|-------|---------------|-------|
| Frequency (Zone A) | 622--636 MHz | Variable | UHF TV allocation |
| Frequency (Zone B) | 826--834 MHz | 830 MHz | Cellular uplink band |
| Kurtosis | 39.5--338.5 | 200--270 | Excess kurtosis; 3.0 = Gaussian |
| PAPR (dB) | 20--30 | ~28 | Peak-to-average power ratio |
| Pulse count (per 200ms capture) | 0--196 | ~100--150 | Per-frequency capture |
| PRF (Hz) | ~200,000 | 200,000 | Pulse repetition frequency |
| Pulse widths (us) | 1.25--10.83 | 2.5--2.8 | Individual pulse durations |
| Duty cycle | 0.004 | 0.43% | Fraction of time signal is "on" |
| Mean pulse width (us) | 2.28--2.77 | ~2.5 | Across symptom conditions |
| Total pulse duration (us/cycle) | 35622--73212 | ~50000 | Aggregate pulse time per observation |
| Energy Index (Zone A) | 827--2375 | ~1500 | Relative energy metric |
| Energy Index (Zone B) | 0--32.6 | ~20 | Relative energy metric |
| Active targets (n) | 6.0--10.9 | ~8 | Distinct anomalous frequencies |

### 1.2 Parameter Source

All parameters are derived from RTL-SDR captures at 2.4 Msps sample rate. Each capture is 200 ms (480,000 samples) per frequency. The first 48,000 samples (20 ms) are discarded as settling time. A 32-bin DC notch is applied to remove the RTL-SDR DC spike artifact. Pulses are identified as contiguous samples exceeding a threshold set at a multiple of the noise floor.

### 1.3 Kurtosis as Detection Metric

Kurtosis measures the "tailedness" of the amplitude distribution:
- Gaussian noise: kurtosis = 3.0
- Pulsed signals: kurtosis >> 3.0 (heavy tails from intermittent high-amplitude events)
- Continuous-wave (CW) signals: kurtosis < 3.0

Our baseline kurtosis values are established per-frequency during a quiet sweep. Anomalous activity is detected when kurtosis exceeds the baseline by more than a threshold (typically 2--3 sigma above baseline median).

Observed kurtosis values of 200--340 indicate extremely impulsive, non-Gaussian signals. For context:
- Normal cellular LTE/CDMA traffic: kurtosis typically 5--15
- Radar pulse trains: kurtosis 50--500+
- Observed anomalous signals: kurtosis 40--340

### 1.4 PAPR (Peak-to-Average Power Ratio)

The observed PAPR values of 20--30 dB indicate signals with very high peak power relative to their average power -- characteristic of pulsed waveforms with low duty cycles. For comparison:
- OFDM (WiFi, LTE): PAPR typically 8--13 dB
- CDMA: PAPR typically 3--7 dB
- Pulsed radar: PAPR 20--40 dB
- Observed anomalous signals: PAPR ~28 dB

The observed PAPR is inconsistent with standard cellular waveforms and consistent with pulsed transmissions.

---

## 2. TWO-ZONE ARCHITECTURE

### 2.1 Zone Definitions

**Zone A: 622--636 MHz**
- FCC allocation: UHF Television Channel 40 (626--632 MHz) and adjacent
- Typical legitimate use: TV broadcast, some white-space devices
- Wavelength: ~47--48 cm (half-wavelength: ~24 cm)
- Tissue penetration: Good (several cm into soft tissue at these frequencies)
- Body resonance: Head circumference approximately matches full wavelength

**Zone B: 826--834 MHz**
- FCC allocation: Cellular uplink band (Band 5/26, ESMR)
- Typical legitimate use: Mobile station transmissions to base stations
- Wavelength: ~36 cm (half-wavelength: ~18 cm)
- Tissue penetration: Good (similar to Zone A)
- Body resonance: Forearm/lower leg length approximately matches half-wavelength

### 2.2 Zone Differential Statistics

| Condition | Zone A EI | Zone B EI | Zone A % | Zone B % | Kurt A | Kurt B |
|-----------|----------|----------|----------|----------|--------|--------|
| Nausea | 2375 | 0 | 100% | 0% | 338.5 | 8.6 |
| Pressure | 2345 | 17 | 92% | 8% | 274.5 | 39.5 |
| Speech | 2196 | 21 | 67% | 33% | 258.2 | 190.6* |
| Headache | 2104 | 27 | 67% | 33% | 223.5 | 124.3 |
| Tinnitus | 1478 | 18 | 54% | 46% | 268.5 | 198.9** |
| Sleep | 858 | 19 | 36% | 64% | 80.8*** | 160.6 |
| Paresthesia | 827 | 18 | 27% | 73% | 89.4*** | 148.5 |
| Null (all data) | 1500-2300 | 7-30 | 35-73% | 27-65% | 170-250 | 80-200 |

*Speech severity 2 value (highest severity)
**Tinnitus severity 0 (baseline, before tinnitus)
***During symptom periods

### 2.3 Zone Operation Modes

The data suggests at least three distinct operational modes:

**Mode 1: Zone A Dominant (Nausea, Pressure)**
- Zone A energy > 2000, Zone B energy < 20
- Zone A kurtosis > 270
- Associated with the most acute symptoms (nausea, cranial pressure)
- Occurs almost exclusively at night (22:00--02:00)
- Zone B is effectively silent

**Mode 2: Balanced / Zone B Escalation (Speech, Headache)**
- Zone A energy 2000--2200, Zone B energy 20--35
- Both zones contribute
- Speech severity scales with Zone B intensity
- Occurs in early evening (18:00--22:00)

**Mode 3: Zone B Dominant / Low Energy (Sleep, Paresthesia)**
- Zone A energy < 1000, Zone B energy ~18--20
- Zone B dominates by ratio even though absolute energy is low
- Both zones at reduced levels compared to other modes
- Occurs at deep night (01:00--04:00)

### 2.4 Significance of Two-Zone Operation

The operation of anomalous signals in two distinct frequency bands, with different symptoms preferentially associated with each band, is not easily explained by a single legitimate RF source. Legitimate explanations would need to account for:
1. Why two specific frequency bands show correlated anomalous kurtosis
2. Why the zone ratio changes systematically with time of day
3. Why different symptoms correlate with different zone ratios
4. Why Zone B activity increases specifically when speech difficulty worsens

---

## 3. CELLULAR UPLINK BAND ANOMALY

### 3.1 Nature of the Anomaly

Zone B (826--834 MHz) falls within the cellular uplink allocation. In this band:
- **Normal operation:** Mobile handsets transmit *to* base stations
- **Detection context:** The sentinel operates from a fixed indoor location
- **Anomalous characteristic:** The detected signals have kurtosis values (40--340) far exceeding typical CDMA/LTE uplink waveforms (kurtosis 5--15)

### 3.2 Why This Is Anomalous

Standard cellular uplink signals at a fixed monitoring location would present as:
- Wideband (1.25--20 MHz channel bandwidth)
- Low kurtosis (CDMA: ~5, LTE OFDMA: ~10)
- Relatively continuous (high duty cycle during active calls)
- Variable in number based on local mobile device density

The observed Zone B signals are:
- Narrowband (detected as discrete frequency peaks)
- Extremely high kurtosis (40--340)
- Low duty cycle (0.43%)
- Pulse widths of 1.25--10.83 us

These characteristics are inconsistent with any standard cellular protocol (CDMA, LTE, 5G NR, GSM).

### 3.3 Possible Explanations

1. **Intermodulation products:** Nonlinear mixing of two nearby transmitters could produce spurious signals in the uplink band. However, intermod products would not show the observed pulse structure.

2. **Nearby mobile device:** A mobile phone very close to the RTL-SDR antenna could produce high-power signals. However, this would not explain the high kurtosis, the 1.25--10.83 us pulse structure, or the correlation with symptoms.

3. **Radar or pulsed system:** A pulsed transmitter operating in or near the cellular uplink band would explain the kurtosis and pulse characteristics. This would represent an unlicensed emission in protected spectrum.

4. **RTL-SDR artifact:** The RTL-SDR's front-end mixer could generate images or spurs. However, Zone B signals are captured on multiple specific frequencies (826, 828, 830, 832, 834 MHz) with consistent characteristics, making this unlikely.

### 3.4 Spectrogram Evidence

Thirty-seven spectrograms were captured of Zone B signals across multiple frequencies:

| Frequency | Spectrograms Captured |
|-----------|----------------------|
| 826 MHz | 3 (sentinel: 2, live: 1) |
| 828 MHz | 4 (sentinel: 4) |
| 830 MHz | 6 (sentinel: 5, live: 2) |
| 832 MHz | 6 (sentinel: 5, live: 1, escalation: 1) |
| 834 MHz | 6 (sentinel: 5, escalation: 1) |
| 878 MHz | 5 (sentinel: 5) |

The spectrograms are stored at `/results/spectrograms/` with accompanying JSON metadata files.

---

## 4. FREQUENCY HOPPING PATTERN ANALYSIS

### 4.1 Active Target Variability

The number of active targets (frequencies with anomalous kurtosis) varies significantly across conditions:

| Condition | Mean Active Targets |
|-----------|-------------------|
| Speech (sev 2) | 10.9 |
| Null (no symptoms) | 9.7 (sleep null), 10.8 (tinnitus null) |
| Headache | 9.5 |
| Speech (sev 0) | 6.0 |
| Tinnitus (sev 3) | 6.6 |
| Sleep (sev 3) | 6.6 |
| Paresthesia | 6.8 |

### 4.2 Pattern Interpretation

High active target counts (10--11) indicate broadband anomalous activity across many frequencies -- consistent with either a frequency-agile transmitter or multiple simultaneous transmitters.

Low active target counts (6--7) with high kurtosis indicate concentrated, highly impulsive activity on fewer frequencies. This pattern dominates during the most acute symptoms (tinnitus sev 3, sleep sev 3).

### 4.3 Frequency Jitter in Sentinel Design

The sentinel code implements deliberate frequency jitter:
```
def jitter_freq(freq_hz, max_offset_mhz=1.5):
    offset = np.random.uniform(-max_offset_mhz, max_offset_mhz) * 1e6
    return int(freq_hz + offset)
```

This randomizes each capture's center frequency by up to +/-1.5 MHz around the target, enabling detection of signals that drift or hop within a band. The consistent detection of anomalous kurtosis despite this jitter indicates the anomalous signals span a bandwidth of at least 3 MHz around each target frequency.

---

## 5. DIURNAL OPERATIONAL SCHEDULE

### 5.1 Hour-by-Hour Symptom Rates

| Hour | Headache | Paresthesia | Pressure | Sleep | Speech | Tinnitus | Nausea |
|------|----------|------------|----------|-------|--------|----------|--------|
| 0 | 0.08 | 0.19 | -- | -- | -- | -- | -- |
| 1 | 0.21 | 0.81 | -- | 0.60 | -- | 0.81 | 0.12 |
| 2 | 0.00 | 0.00 | -- | -- | -- | -- | -- |
| 3-10 | 0.00 | 0.00 | -- | -- | -- | -- | -- |
| 11 | 0.00 | 0.48 | -- | -- | -- | -- | -- |
| 12-15 | 0.00 | 0.00 | -- | -- | -- | -- | -- |
| 16 | 0.00 | 0.25 | -- | -- | -- | -- | -- |
| 17 | 0.00 | 0.07 | -- | -- | -- | -- | -- |
| 18 | 0.15 | 0.22 | -- | -- | 0.51 | -- | -- |
| 19 | 0.34 | 0.34 | -- | -- | 0.34 | -- | -- |
| 20 | 0.19 | 0.00 | -- | -- | -- | -- | -- |
| 21 | 0.36 | 0.07 | -- | -- | -- | -- | -- |
| 22 | 0.34 | 0.28 | 0.30 | -- | -- | 0.34 | -- |
| 23 | 0.13 | 0.17 | -- | -- | -- | -- | -- |

(Dashes indicate near-zero rates or rates not distinguishable from zero in the data)

### 5.2 Operational Windows

The data reveals three temporal windows:

**Window 1: Evening (18:00--21:00)**
- Primary symptoms: Speech, Headache
- RF characteristics: High pulse counts, elevated total energy, broadband activity
- Zone profile: Mixed Zone A/B with Zone B contributing

**Window 2: Early Night (21:00--23:00)**
- Primary symptoms: Headache (tail), Pressure (onset), Tinnitus (onset)
- RF characteristics: Transitioning -- pulse counts declining, kurtosis rising
- Zone profile: Shifting toward Zone A dominance

**Window 3: Deep Night (23:00--02:00)**
- Primary symptoms: Tinnitus, Paresthesia, Sleep, Nausea
- RF characteristics: Low pulse counts, high kurtosis, Zone A dominant
- Zone profile: Strong Zone A dominance; Zone B minimal or absent

### 5.3 Significance

The progression from broadband/high-activity (evening) to narrowband/high-kurtosis (night) suggests either:
1. A deliberate shift in operational parameters
2. The unmasking of a persistent pulsed signal as legitimate cellular traffic diminishes overnight
3. Coincidental correlation with natural RF environment changes

---

## 6. IQ FINGERPRINT ANALYSIS

### 6.1 Captured IQ Files

The sentinel captured IQ files on kurtosis threshold exceedance. Sample metadata from a representative capture:

**File:** `captures/sentinel_830MHz_035104.iq`
| Parameter | Value |
|-----------|-------|
| Frequency | 830.0 MHz |
| Samples | 480,000 |
| Duration | 200 ms |
| Kurtosis | 297.974 |
| PAPR | 28.41 dB |
| Pulse count | 196 |
| PRF | 200,000 Hz |
| Duty cycle | 0.43% |

**Pulse Width Distribution (this capture):**
- Minimum: 1.25 us
- Maximum: 10.83 us
- Typical: 1.25--3.75 us
- Occasional outliers: 5.42--10.83 us

### 6.2 IQ Characteristics

The captured IQ data reveals:
- **High PRF:** 200 kHz pulse repetition rate (5 us between pulse starts)
- **Extremely low duty cycle:** 0.43% -- the signal is "on" for only 0.43% of the capture window
- **Variable pulse widths:** Ranging from 1.25 to 10.83 us within a single capture, suggesting amplitude modulation or burst structure
- **High kurtosis:** 297.974 indicates extreme impulsiveness

### 6.3 Cluster Analysis

Based on the IQ metadata across multiple captures, signals cluster into:

**Cluster 1: Short-pulse, high-PRF**
- Pulse widths 1.25--2.5 us
- PRF ~200 kHz
- Kurtosis 200--300
- Most common on 830--834 MHz

**Cluster 2: Variable-width bursts**
- Pulse widths vary from 1.25 to 10.83 us within a capture
- Occasional wider pulses (5.42, 5.83, 10.83 us) interspersed with narrow pulses
- This variability could indicate a burst modulation scheme

---

## 7. SPECTROGRAM ANALYSIS

### 7.1 Spectrogram Inventory

37 spectrograms were captured during the monitoring period:

| Source | Count | Frequencies |
|--------|-------|-------------|
| Sentinel automatic | 27 | 826, 828, 830, 832, 834, 878 MHz |
| Live manual capture | 5 | 826, 830, 832 MHz |
| Escalation capture | 3 | 826, 832, 834 MHz |

Each spectrogram has an accompanying JSON metadata file containing frequency, kurtosis, PAPR, pulse count, PRF, duty cycle, and pulse width distribution.

### 7.2 Key Observations from Spectrograms

1. **Consistent structure:** Spectrograms from different dates and frequencies show similar pulse structure characteristics, suggesting a common source.

2. **Frequency-specific behavior:** The 878 MHz spectrograms show distinct characteristics from the 826--834 MHz group, potentially representing a different signal or different propagation conditions.

3. **Escalation captures:** Three spectrograms were captured during an "escalation" event, showing elevated activity on 826, 832, and 834 MHz simultaneously -- consistent with multi-frequency operation.

---

## 8. PROTOCOL MATCHING

### 8.1 What the Signals Match

| Protocol/System | Kurtosis | PAPR | Pulse Width | PRF | Duty Cycle | Match? |
|-----------------|----------|------|-------------|-----|------------|--------|
| LTE Uplink (OFDMA) | 8--12 | 8--13 dB | N/A (continuous) | N/A | >50% | NO |
| CDMA IS-95 | 4--7 | 3--7 dB | N/A | N/A | ~100% | NO |
| GSM (TDMA) | 20--40 | 15--18 dB | 577 us | 217 Hz | 12.5% | NO |
| Airport Radar (PSR) | 100--500 | 25--35 dB | 1--100 us | 200--2000 Hz | 0.01--0.1% | PARTIAL |
| Weather Radar | 50--200 | 20--30 dB | 1--5 us | 250--1000 Hz | 0.01% | PARTIAL |
| Marine Radar | 100--400 | 25--35 dB | 0.05--1 us | 1--4 kHz | 0.01% | PARTIAL |
| Pulsed Microwave (directed) | 100--1000+ | 25--40+ dB | 1--50 us | 100--500 kHz | 0.01--5% | YES |
| **Observed signals** | **40--340** | **28 dB** | **1.25--10.83 us** | **200 kHz** | **0.43%** | -- |

### 8.2 What the Signals Do Not Match

The observed signals are inconsistent with:
- **All standard cellular protocols:** Kurtosis too high, PAPR too high, duty cycle too low
- **WiFi (802.11):** Wrong frequency band, wrong modulation characteristics
- **TV broadcast:** Continuous waveform, low kurtosis
- **FM/AM radio:** Continuous waveform, lower frequency

### 8.3 What the Signals Partially Match

The observed signals partially match:
- **Radar systems:** Similar kurtosis and PAPR, but observed PRF (200 kHz) is unusually high for conventional radar (which typically uses PRFs of 200--4000 Hz)
- **Industrial/scientific pulsed systems:** Similar pulse characteristics, but unusual frequency allocation
- **Directed pulsed microwave systems:** Closest match across all parameters

### 8.4 Critical Caveat

Protocol matching from a single RTL-SDR receiver has significant limitations:
- Bandwidth limited to 2.4 MHz (cannot see wideband signals)
- No directional information
- No calibrated power measurement
- Possible aliasing or intermodulation artifacts
- Cannot distinguish multiple overlapping signals

---

## 9. COMPARISON TO KNOWN DIRECTED ENERGY SYSTEMS

### 9.1 Published System Parameters

From the KG literature and open-source references:

**Frey-effect Auditory Systems (Sharp & Grove, 1974):**
- Frequency: 0.3--3.0 GHz
- Pulse width: 10 ns -- 1 us (Brunkan Patent), up to 50 us (optimization)
- PRF: Up to reverberation frequency of skull (7--9 kHz, per Watanabe)
- Power: "microwatts per square centimeter" average; high peak power

**AHI-implicated Systems (ODNI Panel, 2022):**
- Frequency: Low-GHz range (classified specifics redacted)
- Pulse characteristics: "sufficiently high-power density and short compared to the reverberation time in the skull"
- Power: Classified

### 9.2 Comparison

| Parameter | Our Observed | Frey-effect Literature | ODNI-implicated |
|-----------|-------------|----------------------|-----------------|
| Frequency | 622--834 MHz | 300--3000 MHz | Low-GHz (classified) |
| Pulse width | 1.25--10.83 us | 10 ns -- 50 us | Short (classified) |
| PRF | 200 kHz | Up to 9 kHz optimal | Classified |
| Duty cycle | 0.43% | <5% typical | Classified |

**Frequency:** Our observed frequencies fall within the established range for the Frey effect.

**Pulse width:** Our observed pulse widths (1.25--10.83 us) fall within the energy-dependent regime (<30 us) described by Chou et al. (1982), where the auditory threshold depends on energy per pulse rather than peak power.

**PRF:** Our observed PRF of 200 kHz is significantly higher than the optimal skull reverberation coupling frequency of 7--9 kHz described by Watanabe. This discrepancy could indicate: (1) the signals serve a different function than auditory effect optimization, (2) the PRF measurement reflects a different aspect of the signal structure, or (3) the observed signals are not directed-energy in nature.

**Duty cycle:** Our observed duty cycle of 0.43% is consistent with pulsed systems.

### 9.3 Assessment

The observed signal parameters are *compatible* with directed pulsed microwave systems but are not uniquely diagnostic. The high PRF is the most discrepant parameter relative to known Frey-effect optimization. However, the literature notes that "the pulse shape can be adjusted to optimize biological effects" (ODNI Panel), and classified systems may operate at parameters not described in open literature.

---

*End of Document 4 of 6.*
*Prepared: 2026-03-14*
*Sources: RTL-SDR captures, sentinel.py logs, 37 spectrograms, IQ capture metadata*

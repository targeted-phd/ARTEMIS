# RF-SYMPTOM ML ANALYSIS v2 -- METHODOLOGY AND LIMITATIONS

**Classification:** EVIDENCE DOCUMENT
**Date:** 2026-03-14
**Document:** 5 of 6

---

## TABLE OF CONTENTS

1. [Data Collection Methodology](#1-data-collection-methodology)
2. [Symptom Collection Methodology](#2-symptom-collection-methodology)
3. [Three-State Labeling System](#3-three-state-labeling-system)
4. [Interpolation Methodology](#4-interpolation-methodology)
5. [Feature Engineering](#5-feature-engineering)
6. [ML Methodology](#6-ml-methodology)
7. [Dose-Response Methodology](#7-dose-response-methodology)
8. [Statistical Corrections](#8-statistical-corrections)
9. [Confounders](#9-confounders)
10. [Limitations](#10-limitations)
11. [Requirements for a Rigorous Study](#11-requirements-for-a-rigorous-study)
12. [Known Caveats and Overclaiming Risks](#12-known-caveats-and-overclaiming-risks)

---

## 1. DATA COLLECTION METHODOLOGY

### 1.1 Hardware

**RTL-SDR v3 (R820T2 tuner)**
- Sample rate: 2,400,000 samples/second (2.4 Msps)
- Frequency range: 500 kHz -- 1.766 GHz
- ADC resolution: 8-bit I + 8-bit Q
- Sensitivity: approximately -90 dBm (uncalibrated)
- Dynamic range: approximately 45--50 dB (limited by 8-bit ADC)
- Known artifacts: DC spike (mitigated by 32-bin notch), LO leakage, image response

**Antenna:** Standard omnidirectional whip antenna (supplied with RTL-SDR v3). No directional capability. No calibrated gain.

### 1.2 Software: sentinel.py

The sentinel daemon (`sentinel.py`) implements a continuous monitoring cycle:

**Cycle Structure:**
1. **STARE phase:** Rapid alternating captures on target frequencies
   - Each capture: 200 ms (480,000 samples at 2.4 Msps)
   - Settling time: 20 ms (48,000 samples discarded)
   - Effective capture: 180 ms (432,000 samples)
   - Target frequencies: Zone A (622--636 MHz) and Zone B (826--834 MHz)
   - Frequency jitter: +/- 1.5 MHz random offset per capture
   - Multiple stare pairs per cycle

2. **SWEEP phase:** Full-band kurtosis scan
   - Frequency range: 600--900 MHz (configurable)
   - Step size: 2 MHz
   - Brief capture at each step for kurtosis measurement
   - Purpose: Detect frequency migration outside target bands

**Per-Capture Processing:**
1. Read raw IQ samples from RTL-SDR via `rtl_sdr` subprocess
2. Compute complex amplitude: `z = I + jQ` (normalized to float)
3. Apply DC notch: Zero the central 32 FFT bins
4. Compute power spectrum and time-domain statistics:
   - Excess kurtosis: `scipy.stats.kurtosis(|z|)`
   - PAPR: `10 * log10(max(|z|^2) / mean(|z|^2))`
   - Mean power: `10 * log10(mean(|z|^2))`
5. Pulse detection:
   - Threshold: Set adaptively based on noise floor
   - Minimum pulse width: 3 samples (1.25 us at 2.4 Msps)
   - Pulse characterization: offset, width, SNR

**Data Integrity:**
- SHA-256 hash computed for each data entry: `hashlib.sha256(data_str.encode()).hexdigest()[:16]`
- Data written to hourly-rotated JSONL files
- `fsync` called after every write to prevent corruption
- Periodic checkpoint saves (baseline + state)

### 1.3 Trigger and Alert System

When the stare phase detects kurtosis exceeding a threshold:
1. **IQ capture:** Raw IQ data saved to disk (budget-limited)
2. **Spectrogram generation:** Time-frequency plot computed and saved
3. **ntfy push notification:** Alert sent with:
   - Alert severity level (detect, high, critical)
   - Maximum kurtosis value
   - Active frequency list
   - Unique alert ID (SHA-256 nonce)
   - Button URLs for symptom tagging

### 1.4 Data Output

Each observation cycle produces one JSON row containing:
- Timestamp (UTC)
- Per-frequency kurtosis values
- Aggregate statistics (max_kurt, total_pulses, etc.)
- Zone-specific metrics (ei_zone_a, ei_zone_b, max_kurt_zone_a, etc.)
- SHA-256 hash of the data record
- Reference to any IQ captures or spectrograms

---

## 2. SYMPTOM COLLECTION METHODOLOGY

### 2.1 Notification System

Symptoms are collected through the ntfy push notification system:

1. **Trigger:** RF detection events send push notifications to the subject's phone
2. **Notification content:** Alert severity, kurtosis value, active frequencies, cycle number
3. **Response mechanism:** "Tag Symptoms" button opens the tag server web interface
4. **Tag server:** HTTP endpoint at `100.96.113.92:8091` accepts symptom reports

### 2.2 Symptom Types

Seven symptoms are tracked:

| Symptom | Description | Severity Scale |
|---------|-------------|---------------|
| headache | Cranial pain | 0--3 |
| paresthesia | Tingling/pins-and-needles | 0--3 |
| pressure | Cranial pressure sensation | 0--3 |
| sleep | Sleep disruption (difficulty falling/staying asleep) | 0--3 |
| speech | Difficulty speaking or word-finding | 0--3 |
| tinnitus | Ringing/buzzing in ears | 0--3 |
| nausea | Nausea/stomach distress | 0--3 |

### 2.3 Severity Scale

| Level | Meaning |
|-------|---------|
| 0 | Absent |
| 1 | Mild (noticeable but not disruptive) |
| 2 | Moderate (disruptive to normal activities) |
| 3 | Severe (incapacitating or requiring intervention) |

### 2.4 Response Protocol

- Subject responds to notifications by tapping "Tag Symptoms" button
- Symptom tagging includes the RF context from the notification
- Each tag carries the alert_id nonce linking it to a specific RF observation cycle
- Response rate: 65 / 1903 = 3.4%

---

## 3. THREE-STATE LABELING SYSTEM

### 3.1 Label States

Each observation cycle receives one of three labels per symptom:

| State | Meaning | Source |
|-------|---------|--------|
| Positive | Symptom is present at this cycle | Direct report or interpolation |
| Negative | Symptom is confirmed absent at this cycle | Direct report of no symptoms, or bracketed by negative reports |
| Unknown | No information about symptom at this cycle | No response, not interpolable |

### 3.2 Rationale

The three-state system avoids the common error of treating unreported periods as symptom-free. In a notification-triggered system:
- Absence of a response does NOT mean absence of symptoms
- The subject may be asleep, away from phone, or unable to respond
- Only periods explicitly bracketed by responses are labeled

### 3.3 Impact on Analysis

Unknown-labeled cycles are excluded from classification. This means:
- Only 65 directly responded + 233 interpolated = ~298 labeled cycles (of 1903 total) contribute to classification
- The effective sample sizes per symptom range from 70 (nausea) to 184 (paresthesia)

---

## 4. INTERPOLATION METHODOLOGY

### 4.1 Exponential Back-Fill with Forward Rolloff

When two responded time points bracket an unreported interval, the intermediate cycles are labeled using exponential interpolation:

**Back-fill (from a positive report backward):**
- If cycle `t` has a positive report at severity `s`, then cycles `t-1, t-2, ...` receive severity values `s * exp(-lambda * dt)` where `dt` is the time distance from the report
- The decay rate `lambda` is tuned such that severity drops below 0.1 within approximately 5 cycles
- This reflects the assumption that symptoms were present before being reported, with declining confidence in earlier cycles

**Forward rolloff:**
- After a positive report at cycle `t`, subsequent unreported cycles receive declining severity values
- The rolloff reflects the assumption that symptoms persist for some time after reporting but eventually resolve

**Boundary conditions:**
- If a negative report follows a positive report, interpolation fills the gap with a smooth decay from the positive severity to zero
- If two positive reports bracket an interval, interpolation maintains the severity through the gap

### 4.2 Known Issues with Interpolation

1. **Autocorrelation injection:** Interpolation creates temporally correlated labels, which violates the independence assumption of standard cross-validation. This is partially mitigated by 5-fold CV with sufficient separation.

2. **Phantom dose-response:** If severity values are interpolated smoothly, and RF features also vary smoothly, the interpolation can create artificial dose-response correlations that do not exist in the raw data.

3. **Temporal smearing:** The exponential kernel smooths the true onset and offset times of symptoms, reducing temporal resolution.

4. **Assumption dependence:** The interpolation assumes symptoms vary smoothly between reports, which may not hold for acute symptoms like nausea.

---

## 5. FEATURE ENGINEERING

### 5.1 Feature Matrix Construction

The feature matrix is constructed as: `X[n_cycles, n_features] = [1903, 50]`

**RF Features (11):**
Computed from the raw sentinel data for each cycle:
- `ei_total`: Sum of energy indices across all active frequencies
- `ei_zone_a`: Sum of energy indices for frequencies 622--636 MHz
- `ei_zone_b`: Sum of energy indices for frequencies 826--834 MHz
- `max_kurt`: Maximum kurtosis value across all frequencies
- `max_kurt_zone_a`: Maximum kurtosis in Zone A
- `max_kurt_zone_b`: Maximum kurtosis in Zone B
- `max_kurt_ul`: Maximum kurtosis in uplink band
- `n_active_targets`: Count of frequencies with kurtosis exceeding threshold
- `total_pulses`: Sum of pulse counts across all frequencies
- `mean_pulse_width_us`: Mean pulse width in microseconds
- `total_pulse_duration_us`: Sum of (pulse_count * mean_pulse_width) across frequencies

**Temporal Features (3):**
- `hour`: Hour of day (0--23), from timestamp
- `minute`: Minute of hour (0--59)
- `is_night`: Binary indicator, 1 if hour in {22, 23, 0, 1, 2, 3, 4, 5}

**Lag Features (22):**
- `lag1_X`: Value of feature X from the previous cycle (11 features)
- `lag2_X`: Value of feature X from two cycles ago (11 features)

**Rolling Features (8):**
- `roll5_X`: 5-cycle rolling mean of feature X (4 features: ei_total, max_kurt, total_pulses, total_pulse_duration_us)
- `roll10_X`: 10-cycle rolling mean of feature X (same 4 features)

**Delta Features (3):**
- `delta_X`: `X[t] - X[t-1]` (3 features: ei_total, max_kurt, n_active_targets)

**Zone Differential Features (3):**
- `zone_ratio_kurt`: `max_kurt_zone_a / max_kurt_zone_b` (with epsilon to avoid division by zero)
- `zone_ratio_ei`: `ei_zone_a / ei_zone_b` (with epsilon)
- `zone_b_dominant`: Binary, 1 if `max_kurt_zone_b > max_kurt_zone_a`

### 5.2 Missing Value Handling

- NaN values occur in lag/rolling features at the beginning of the dataset
- NaN values are imputed by the Random Forest internally (scikit-learn handles NaN in recent versions) or by median imputation prior to fitting

---

## 6. ML METHODOLOGY

### 6.1 Classification

**Algorithm:** Random Forest Classifier (scikit-learn `RandomForestClassifier`)
- Default hyperparameters (100 trees, no max_depth limit)
- No hyperparameter tuning (to avoid overfitting with small samples)

**Validation:** 5-fold stratified cross-validation
- Stratification ensures each fold has approximately the same positive/negative ratio
- AUC computed per fold, then averaged

**Metric:** Area Under the Receiver Operating Characteristic Curve (AUC-ROC)
- Threshold-independent measure of discrimination ability
- AUC = 0.5: random; AUC = 1.0: perfect discrimination

### 6.2 Permutation Testing

**Purpose:** Determine whether the observed AUC is statistically significant (i.e., not achievable by chance with the given feature matrix and label distribution).

**Procedure:**
1. Fit the Random Forest on the real (X, y) data, compute AUC = AUC_observed
2. Repeat 500 times:
   a. Shuffle y labels randomly (breaking the X-y association)
   b. Fit Random Forest on (X, y_shuffled), compute AUC_null
3. p-value = (number of AUC_null >= AUC_observed + 1) / (500 + 1)

**Interpretation:**
- p = 0.002 means none of the 500 permutations achieved the observed AUC
- The minimum achievable p-value with 500 permutations is 1/501 = 0.001996... which rounds to 0.002

### 6.3 Feature Significance (Mann-Whitney U)

**Purpose:** Identify individual features that differ significantly between symptom-positive and symptom-negative periods.

**Procedure:**
1. For each of 50 features:
   a. Split feature values into positive-label and negative-label groups
   b. Compute Mann-Whitney U statistic and p-value (two-sided)
   c. Compute Cohen's d effect size
2. Apply Bonferroni correction: p_bonf = min(p_raw * 50, 1.0)
3. Features with p_bonf < 0.05 are considered significant

### 6.4 Feature Importance

**Method:** Gini importance (mean decrease in impurity) from the trained Random Forest
- Each feature's contribution to reducing prediction error across all trees
- Normalized to sum to 1.0

### 6.5 Severity Regression

**Algorithm:** Gradient Boosting Regressor (scikit-learn `GradientBoostingRegressor`)
- Predicts continuous severity (0--3) from RF features
- Evaluated by MAE (Mean Absolute Error) and R^2 (coefficient of determination)
- 5-fold cross-validation

---

## 7. DOSE-RESPONSE METHODOLOGY

### 7.1 Spearman Rank Correlation

For each symptom x feature pair where the symptom is positive:
1. Group observation cycles by symptom severity level (0, 1, 2, 3)
2. Compute the Spearman rank correlation between severity and feature value
3. Report rho (correlation coefficient) and p-value
4. Also compute mean feature value per severity level to visualize the dose-response curve

### 7.2 Interpretation

- Positive rho: Higher RF feature values correlate with worse symptoms
- Negative rho: Lower RF feature values correlate with worse symptoms (potentially paradoxical)
- Only correlations with p < 0.05 are reported as significant

### 7.3 Limitations of Dose-Response Analysis

- Severity values include interpolated data, potentially inflating correlations
- Only a few severity levels exist (typically 0, 1, 2; rarely 3), limiting the resolution of the dose-response curve
- Confounders (especially time of day) affect both RF features and symptom severity simultaneously

---

## 8. STATISTICAL CORRECTIONS

### 8.1 Bonferroni Correction

Applied to the per-feature Mann-Whitney U tests:
- Number of tests per symptom: 50 (one per feature)
- Corrected alpha: 0.05 / 50 = 0.001
- Reported p-values are multiplied by 50 (capped at 1.0)

### 8.2 What Is Not Corrected

The following analyses do NOT have family-wise error correction:
- **Cross-symptom testing:** 7 symptoms are analyzed independently without correction for the 7 comparisons
- **Dose-response correlations:** Reported at p < 0.05 without Bonferroni correction
- **Temporal analysis:** No correction for multiple temporal comparisons
- **Zone differential analysis:** No correction applied

### 8.3 Total Number of Statistical Tests

| Analysis Type | Tests per Symptom | Symptoms | Total Tests |
|---------------|------------------|----------|-------------|
| Mann-Whitney U (Bonferroni) | 50 | 7 | 350 |
| Dose-response (Spearman) | 11 | 7 | 77 |
| Temporal (peak hour) | 1 | 7 | 7 |
| Lag analysis | 41 | 7 | 287 |
| Zone differential | 1 | 7 | 7 |
| Permutation test | 1 | 7 | 7 |
| **Total** | | | **735** |

At alpha = 0.05 without correction, approximately 37 tests would be expected to achieve significance by chance. This underscores the importance of focusing on the most robust findings (highest AUC, lowest p-values, multiple supporting analyses).

---

## 9. CONFOUNDERS

### 9.1 Notification Bias

**Description:** Symptom reports are solicited by RF-triggered notifications. The notification is only sent when RF activity exceeds a threshold. Therefore:
- Symptom data exists only for cycles with sufficient RF activity to trigger a notification
- Periods of low RF activity have no symptom reports (labeled "unknown")
- This creates a selection bias: the labeled dataset is conditioned on high RF activity

**Impact:** Inflates the apparent RF-symptom association. If we only ask about symptoms when RF is active, we will find symptoms correlated with RF activity regardless of any true causal relationship.

**Mitigation:** The three-state labeling system partially addresses this by not treating non-responses as negative. However, the fundamental bias remains: the dataset over-represents high-RF conditions.

### 9.2 Temporal Coverage Bias

**Description:** The subject is available to respond to notifications during specific hours (primarily evenings and nights). Daytime hours have few responses.

**Impact:** The dataset is dominated by nighttime observations. Since RF activity characteristics change with time of day, the temporal coverage bias conflates time-of-day effects with RF effects.

### 9.3 Zone B Suppression During Reporting Window

**Description:** Zone B energy is very low (often near zero) during the hours when most symptom reports occur (22:00--02:00). This could be because:
1. Zone B signals are genuinely reduced at night
2. The RTL-SDR was tuned to Zone A frequencies during reporting periods
3. Zone B is deliberately inactive during nighttime operation

**Impact:** The apparent Zone A dominance for several symptoms may be partly an artifact of temporal coverage.

### 9.4 Nocebo Effect

**Description:** Receiving RF detection alerts could induce anxiety and symptom reporting through psychological mechanisms, regardless of any biological RF effect.

**Impact:** Cannot be assessed in a non-blinded, single-subject study. The subject's awareness of the monitoring system could produce all observed symptoms through expectation effects alone.

### 9.5 Expectation Bias

**Description:** The subject expects to experience symptoms during high RF activity and may be more likely to notice or report symptoms during these periods.

**Impact:** Could inflate classification AUC and dose-response correlations even in the absence of a genuine RF biological effect.

### 9.6 Circadian Confound

**Description:** Many symptoms (headache, tinnitus, sleep disruption) have natural circadian patterns independent of RF exposure. The `is_night` feature being the most significant predictor for multiple symptoms could reflect this confound.

**Impact:** Difficult to separate genuine RF effects from circadian symptom variation without a controlled study.

---

## 10. LIMITATIONS

### 10.1 Single Subject (n=1)

This is a case study, not a population study. All findings apply only to one individual and cannot be generalized. Individual susceptibility to RF effects varies widely, and this subject may have idiosyncratic responses.

### 10.2 Non-Blinded

The subject knows when RF alerts are sent and can see the monitoring equipment. This introduces expectation bias and nocebo effects that cannot be separated from genuine biological effects.

### 10.3 Uncalibrated Power

The RTL-SDR provides relative measurements only. No absolute power density (W/m2), specific absorption rate (SAR, W/kg), or electric field strength (V/m) can be determined. This means:
- No comparison to FCC/ICNIRP exposure limits is possible
- No comparison to published biological effect thresholds is possible
- No determination of whether the detected signals have sufficient power to produce biological effects

### 10.4 Low Response Rate

Only 65 of 1903 cycles (3.4%) received direct symptom responses. The remaining labeled data comes from interpolation. The small effective sample sizes (70--184 per symptom) limit statistical power.

### 10.5 No Directional Information

The omnidirectional antenna cannot determine the direction of arrival of detected signals. Without directional information:
- The source cannot be localized
- Multiple overlapping sources cannot be distinguished
- Reflections and multipath cannot be separated from direct signals

### 10.6 Limited Bandwidth

The RTL-SDR's 2.4 MHz instantaneous bandwidth can only observe one narrow frequency band at a time. Wideband signals spanning more than 2.4 MHz are not fully captured.

### 10.7 No Baseline Control Period

The study lacks a control period where the monitoring system was active but the subject was in a location without anomalous RF activity. This prevents determining the subject's baseline symptom rate.

### 10.8 Temporal Resolution

The cycle-based observation structure means the temporal resolution is limited to the cycle duration. Events occurring between cycles are not captured.

### 10.9 Self-Report Bias

All symptoms are self-reported. No objective physiological measurements (EEG, heart rate variability, blood markers) are available to validate the symptom reports.

---

## 11. REQUIREMENTS FOR A RIGOROUS STUDY

To establish a causal RF-symptom relationship, the following would be needed:

### 11.1 Study Design

- **Double-blind:** Neither the subject nor the evaluator knows when RF exposure is occurring
- **Controlled exposure:** Calibrated RF source with known parameters (frequency, power, modulation)
- **Sham control:** Periods with the apparatus active but no RF emission
- **Crossover design:** Each subject experiences both exposure and sham in random order
- **Multiple subjects:** Minimum 20--30 subjects for adequate statistical power

### 11.2 Measurement

- **Calibrated dosimetry:** Calibrated field probes measuring E-field, H-field, and power density at the subject's location
- **SAR estimation:** Computational dosimetry using anatomical models
- **Objective biomarkers:** EEG, heart rate variability, cortisol levels, melatonin levels, auditory brainstem response, otoacoustic emissions
- **Environmental controls:** RF-shielded room, controlled ambient conditions (temperature, noise, lighting)

### 11.3 Analysis

- **Pre-registered analysis plan:** Specified before data collection
- **Adequate sample size:** Determined by power analysis
- **Appropriate statistical corrections:** Family-wise error rate control across all comparisons
- **Replication:** Independent replication by a second laboratory

### 11.4 What This Study Provides Instead

This study provides:
- A detailed characterization of anomalous RF signals in a residential environment
- Evidence of statistical associations between RF parameters and symptoms
- Dose-response relationships for specific symptoms
- A temporal analysis suggesting RF precedes speech difficulty
- A two-zone architecture with differential symptom associations

These findings are hypothesis-generating, not hypothesis-confirming. They establish grounds for a controlled investigation but do not themselves constitute proof of a causal relationship.

---

## 12. KNOWN CAVEATS AND OVERCLAIMING RISKS

### 12.1 Risk: Interpreting AUC as Evidence of Causation

High AUC values indicate that RF features can *discriminate* between symptom-present and symptom-absent periods. This does not establish causation. Any confounder that co-varies with both RF activity and symptoms would produce high AUC without a causal link. The most obvious confounder is time of day.

### 12.2 Risk: Interpreting Dose-Response as Biological

The dose-response correlations (especially for speech: rho = +0.726) are impressive but could be confounded. If both RF activity volume and speech difficulty increase during active evening hours, a spurious dose-response would result even without a biological mechanism.

### 12.3 Risk: Interpreting Lag = -3 as Temporal Causation

The speech lag result (RF precedes symptom by 3 cycles) is suggestive but not definitive. Cross-correlation can identify the most aligned temporal offset between two signals, but this alignment could reflect:
- True causal sequence (RF causes speech difficulty with ~3 cycle latency)
- Shared external driver with different latencies
- Statistical artifact of a small negative-class sample (n=5)

### 12.4 Risk: Zone-Differential Over-Interpretation

The two-zone differential is a novel and unexpected finding. However, it could reflect:
- Genuine dual-band operation
- Receiver artifact (RTL-SDR tuning sequence affects which zone is observed during symptom periods)
- Coincidental correlation between legitimate RF environment variation and symptom timing

### 12.5 Risk: Small Sample Sizes for Rare Symptoms

Nausea (n=7) and speech-negative (n=5) sample sizes are extremely small. Statistical results for these conditions should be considered preliminary.

### 12.6 Risk: Post-Hoc Hypothesis Generation

The analysis was not pre-registered. Feature selection, zone definitions, temporal windows, and analysis methods were developed iteratively during the investigation. This means the findings are susceptible to researcher degrees of freedom and should be treated as hypothesis-generating.

### 12.7 Appropriate Interpretation

The appropriate interpretation of these findings is:

*"We observe statistically significant associations between anomalous RF signal parameters and seven neurological symptoms in a single subject. These associations survive permutation testing and show symptom-specific patterns (zone differential, dose-response, temporal profile). However, the study design (single subject, non-blinded, notification-triggered symptom collection) cannot rule out confounders including nocebo effects, circadian variation, notification bias, and expectation bias. The findings are hypothesis-generating and warrant controlled investigation."*

---

*End of Document 5 of 6.*
*Prepared: 2026-03-14*

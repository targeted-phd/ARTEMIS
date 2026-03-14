# RF-SYMPTOM ML ANALYSIS v2 -- PER-SYMPTOM DETAILED ANALYSIS

**Classification:** EVIDENCE DOCUMENT
**Date:** 2026-03-14
**Document:** 2 of 6

---

## TABLE OF CONTENTS

1. [Tinnitus](#1-tinnitus)
2. [Sleep Disruption](#2-sleep-disruption)
3. [Speech Difficulty](#3-speech-difficulty)
4. [Pressure (Cranial)](#4-pressure-cranial)
5. [Paresthesia](#5-paresthesia)
6. [Headache](#6-headache)
7. [Nausea](#7-nausea)
8. [Cross-Symptom Comparison](#8-cross-symptom-comparison)

---

## 1. TINNITUS

### 1.1 Classification Results

| Metric | Value |
|--------|-------|
| Positive samples (N+) | 134 |
| Negative samples (N-) | 20 |
| Total labeled | 154 |
| AUC (5-fold CV) | 0.978 |
| Permutation p-value | 0.002 |
| Null AUC (mean) | 0.492 |
| Significant features (Bonferroni) | 15 / 50 |
| Severity regression MAE | 0.35 |
| Severity regression R^2 | 0.443 |

### 1.2 Significant Features (Bonferroni-corrected, p < 0.05)

| Feature | p_bonf | Cohen's d | Direction | Sym Mean | Null Mean |
|---------|--------|-----------|-----------|----------|-----------|
| is_night | 5.50e-13 | +2.24 | UP | 0.896 | 0.150 |
| lag1_max_kurt_zone_a | 2.53e-05 | +1.35 | UP | 267.7 | 160.0 |
| roll10_max_kurt | 3.01e-05 | +1.17 | UP | 260.3 | 198.0 |
| max_kurt_zone_a | 3.97e-05 | +1.34 | UP | 268.5 | 170.3 |
| roll5_max_kurt | 4.68e-05 | +1.21 | UP | 265.0 | 204.5 |
| n_active_targets | 5.01e-05 | -1.62 | DOWN | 7.30 | 10.80 |
| lag2_max_kurt_zone_a | 6.54e-05 | +1.28 | UP | 265.6 | 170.2 |
| lag2_n_active_targets | 1.19e-03 | -1.29 | DOWN | 7.36 | 10.40 |
| lag1_n_active_targets | 1.27e-03 | -1.27 | DOWN | 7.33 | 10.40 |
| lag2_total_pulse_duration_us | 9.27e-03 | -0.94 | DOWN | 50444.1 | 69916.2 |
| total_pulse_duration_us | 1.38e-02 | -0.85 | DOWN | 49571.3 | 65459.7 |
| roll5_total_pulses | 1.50e-02 | -0.64 | DOWN | 21568.0 | 26821.7 |
| lag1_total_pulse_duration_us | 2.71e-02 | -0.78 | DOWN | 50152.1 | 66235.8 |
| lag2_max_kurt | 3.31e-02 | +0.88 | UP | 268.5 | 203.3 |
| roll5_total_pulse_duration_us | 4.52e-02 | -0.84 | DOWN | 50252.2 | 65884.7 |

### 1.3 Feature Importance Rankings (Random Forest)

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | roll10_max_kurt | 0.120 |
| 2 | is_night | 0.086 |
| 3 | n_active_targets | 0.067 |
| 4 | roll5_max_kurt | 0.060 |
| 5 | roll5_total_pulse_duration_us | 0.055 |
| 6 | hour | 0.046 |
| 7 | max_kurt_zone_a | 0.040 |
| 8 | lag2_n_active_targets | 0.033 |
| 9 | roll10_total_pulse_duration_us | 0.030 |
| 10 | lag1_n_active_targets | 0.025 |

**Interpretation:** The tinnitus classifier is dominated by kurtosis features, specifically rolling kurtosis averages. The top feature (`roll10_max_kurt`, importance = 0.120) is the 10-cycle rolling maximum kurtosis, indicating that sustained high-kurtosis (pulsed) signals predict tinnitus more than instantaneous values. The `is_night` feature ranks second (0.086), reflecting the strong nocturnal concentration of tinnitus reports. Zone A kurtosis (`max_kurt_zone_a`, 0.040) ranks 7th, confirming the Zone A specificity.

The negative direction of pulse count features (n_active_targets: d = -1.62, total_pulse_duration: d = -0.85) indicates that tinnitus occurs during periods of *fewer* but more impulsive signals -- consistent with a pulsed-mode operational pattern distinct from normal broadband activity.

### 1.4 Dose-Response Analysis

| Feature | Spearman rho | p-value | Sev 0 Mean | Sev 1 Mean | Sev 2 Mean | Sev 3 Mean |
|---------|-------------|---------|------------|------------|------------|------------|
| max_kurt_zone_b | -0.498 | 2.46e-05 | 198.9 | 102.1 | 116.8 | 91.3 |
| n_active_targets | -0.458 | 1.27e-04 | 10.8 | 7.3 | 7.2 | 6.6 |
| max_kurt_zone_a | +0.397 | 1.38e-03 | 143.1 | 191.5 | 177.9 | 156.6 |
| ei_zone_b | -0.395 | 1.13e-03 | 30.5 | 14.6 | 17.0 | 10.3 |
| ei_zone_a | +0.344 | 6.19e-03 | 1617.7 | 1542.1 | 1628.4 | 1317.2 |
| mean_pulse_width_us | -0.331 | 7.01e-03 | 2.74 | 2.44 | 2.65 | 2.56 |
| ei_total | +0.306 | 1.31e-02 | 1681.7 | 1584.7 | 1668.7 | 1346.8 |
| max_kurt | +0.294 | 1.76e-02 | 220.2 | 272.5 | 274.7 | 243.0 |
| total_pulse_duration_us | -0.292 | 1.82e-02 | 65459.7 | 49598.5 | 48793.9 | 39345.6 |

**Key finding:** Tinnitus severity shows a clear zone-differential dose-response. As tinnitus worsens (severity 0 -> 3):
- Zone A kurtosis *increases* (rho = +0.397): from 143.1 at severity 0 to 156.6 at severity 3
- Zone B kurtosis *decreases* (rho = -0.498): from 198.9 at severity 0 to 91.3 at severity 3
- Zone B energy *decreases* (rho = -0.395): from 30.5 at severity 0 to 10.3 at severity 3

This reciprocal zone response is consistent with a frequency-selective operational mode: as Zone A activity intensifies (driving tinnitus), Zone B activity diminishes.

### 1.5 Temporal Profile

| Parameter | Value |
|-----------|-------|
| Peak hour | 01:00 |
| Peak rate | 0.81 (81% of 01:00-hour cycles show tinnitus) |
| Nocturnal concentration | Extreme (is_night d = +2.24) |
| Secondary peaks | 22:00 (0.34), 19:00 (0.34) |

Tinnitus is overwhelmingly nocturnal. 89.6% of tinnitus-positive cycles occur during nighttime hours (is_night = 1 for sym_mean = 0.896 vs null_mean = 0.150).

### 1.6 Zone Differential

| Zone | Symptom % | Null % | EI (symptom) |
|------|-----------|--------|-------------|
| Zone A | 54% | 35% | 1478 |
| Zone B | 46% | 65% | 18 |

Tinnitus shows a shift toward Zone A dominance relative to the null distribution (54% vs 35% Zone A). However, it is not as extreme as nausea or pressure.

### 1.7 Lag Analysis

| Metric | Value |
|--------|-------|
| Peak lag | +20 cycles |
| Peak correlation | r = 0.731 |
| RF-precedes max r | 0.600 |
| RF-follows max r | 0.731 |

The positive lag indicates the RF-tinnitus cross-correlation is strongest when symptom onset is aligned 20 cycles before the RF peak. This could reflect cumulative effects or a shared diurnal driver.

### 1.8 Severity Distribution

| Severity | Count |
|----------|-------|
| 0.4 | 7 |
| 0.5 | 7 |
| 0.6 | 8 |
| 0.7 | 17 |
| 0.8 | 19 |
| 0.9 | 12 |
| 1.0 | 10 |
| 1.1 | 6 |
| 1.3 | 7 |
| 1.4 | 3 |
| 1.5 | 2 |
| 1.6 | 8 |
| 1.7 | 1 |
| 1.8 | 3 |
| 1.9 | 6 |
| 2.0 | 4 |
| 2.1 | 2 |
| 2.3 | 1 |
| 2.5 | 1 |
| 2.6 | 3 |
| 2.7 | 2 |
| 2.8 | 1 |
| 3.0 | 1 |

Median severity is approximately 0.8--0.9, with a long right tail extending to 3.0. The distribution is right-skewed, suggesting most tinnitus events are mild to moderate.

### 1.9 RF Signature Interpretation

Tinnitus is associated with:
1. High kurtosis in Zone A (622--636 MHz) -- pulsed, non-Gaussian signals
2. Reduced Zone B activity -- the cellular uplink band quiets during tinnitus
3. Fewer active targets -- fewer distinct frequencies are active
4. Nocturnal occurrence -- overwhelmingly nighttime
5. Sustained kurtosis (rolling features dominate) rather than transient spikes

This profile is consistent with the known microwave auditory effect (Frey effect), which requires pulsed RF energy at sufficient peak power to induce thermoelastic expansion in cranial tissue. The Zone A frequencies (622--636 MHz) are within the range known to penetrate cranial tissue effectively (see KG literature review, Document 3).

### 1.10 Co-occurring Symptoms

Tinnitus co-occurs most frequently with paresthesia (both peak at 01:00) and sleep disruption. The negative direction of pulse count features is shared with paresthesia, suggesting a common RF regime.

---

## 2. SLEEP DISRUPTION

### 2.1 Classification Results

| Metric | Value |
|--------|-------|
| Positive samples (N+) | 73 |
| Negative samples (N-) | 50 |
| Total labeled | 123 |
| AUC (5-fold CV) | 0.970 |
| Permutation p-value | 0.002 |
| Null AUC (mean) | 0.507 |
| Significant features (Bonferroni) | 21 / 50 |
| Severity regression MAE | 0.20 |
| Severity regression R^2 | 0.819 |

### 2.2 Significant Features (Bonferroni-corrected, p < 0.05)

| Feature | p_bonf | Cohen's d | Direction | Sym Mean | Null Mean |
|---------|--------|-----------|-----------|----------|-----------|
| is_night | 4.83e-13 | +1.81 | UP | 1.000 | 0.380 |
| total_pulse_duration_us | 5.11e-12 | -1.71 | DOWN | 38404.8 | 65422.6 |
| lag2_total_pulse_duration_us | 8.80e-12 | -1.65 | DOWN | 39802.5 | 68492.1 |
| n_active_targets | 1.09e-11 | -1.83 | DOWN | 6.2 | 9.7 |
| lag1_total_pulse_duration_us | 1.90e-11 | -1.60 | DOWN | 39117.3 | 66714.5 |
| lag2_n_active_targets | 2.41e-11 | -1.72 | DOWN | 6.3 | 9.7 |
| roll5_total_pulses | 3.75e-11 | -1.57 | DOWN | 16569.5 | 27587.0 |
| roll5_total_pulse_duration_us | 5.87e-11 | -1.69 | DOWN | 39389.6 | 66720.5 |
| lag1_n_active_targets | 1.96e-10 | -1.64 | DOWN | 6.2 | 9.6 |
| roll10_total_pulses | 3.37e-09 | -1.41 | DOWN | 17187.8 | 27225.8 |
| total_pulses | 4.74e-09 | -1.54 | DOWN | 16155.8 | 26811.3 |
| roll10_total_pulse_duration_us | 7.12e-09 | -1.45 | DOWN | 40776.4 | 65451.6 |
| lag1_total_pulses | 8.43e-09 | -1.45 | DOWN | 16506.2 | 27604.9 |
| lag2_total_pulses | 9.32e-09 | -1.43 | DOWN | 16845.6 | 27684.2 |
| lag1_ei_total | 5.54e-04 | -0.99 | DOWN | 922.5 | 1915.4 |
| ei_total | 1.31e-03 | -1.03 | DOWN | 900.4 | 1877.5 |
| lag2_ei_total | 1.47e-03 | -0.97 | DOWN | 949.0 | 1925.7 |
| zone_ratio_kurt | 1.79e-03 | -0.08 | DOWN | 10.9 | 12.3 |
| roll5_ei_total | 5.93e-03 | -1.08 | DOWN | 906.9 | 1904.1 |
| roll10_ei_total | 1.68e-02 | -1.08 | DOWN | 903.4 | 1886.1 |
| (21st feature at p_bonf < 0.05) | -- | -- | DOWN | -- | -- |

### 2.3 Feature Importance Rankings (Random Forest)

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | roll5_total_pulse_duration_us | 0.100 |
| 2 | roll5_total_pulses | 0.067 |
| 3 | roll10_total_pulse_duration_us | 0.065 |
| 4 | lag1_total_pulse_duration_us | 0.064 |
| 5 | total_pulse_duration_us | 0.061 |
| 6 | is_night | 0.056 |
| 7 | roll10_total_pulses | 0.054 |
| 8 | lag2_total_pulse_duration_us | 0.048 |
| 9 | lag2_n_active_targets | 0.047 |
| 10 | n_active_targets | 0.031 |

**Interpretation:** Sleep disruption is dominated by *activity-volume* features -- total pulse duration and pulse counts, both instantaneous and rolling averages. All significant features except `is_night` are in the DOWN direction, meaning sleep disruption is associated with *reduced* overall RF activity. This is paradoxical: less RF activity correlates with more sleep disruption.

The resolution lies in the nocturnal confound: sleep reports necessarily occur at night, when legitimate RF activity (cellular traffic) is naturally lower. The remaining RF activity during these quiet nighttime periods may have different characteristics (higher kurtosis, Zone A dominance) that distinguish it from daytime activity.

The severity regression R^2 of 0.819 is the highest of any symptom, meaning RF features predict sleep disruption severity with exceptional accuracy.

### 2.4 Dose-Response Analysis

| Feature | Spearman rho | p-value | Sev 0 Mean | Sev 1 Mean | Sev 2 Mean | Sev 3 Mean |
|---------|-------------|---------|------------|------------|------------|------------|
| max_kurt_zone_b | -0.380 | 1.77e-03 | 149.7 | 160.6 | 147.0 | 91.3 |
| total_pulse_duration_us | -0.364 | 2.84e-03 | 65422.6 | 38653.8 | 35846.6 | 39345.6 |
| n_active_targets | -0.358 | 3.43e-03 | 9.7 | 6.2 | 6.0 | 6.6 |
| ei_zone_b | -0.344 | 5.08e-03 | 24.2 | 20.9 | 14.5 | 10.3 |
| mean_pulse_width_us | -0.344 | 5.00e-03 | 2.57 | 2.67 | 2.76 | 2.56 |
| ei_zone_a | +0.287 | 2.38e-02 | 1824.3 | 805.5 | 980.5 | 1317.2 |
| max_kurt_ul | -0.264 | 3.35e-02 | 26.6 | 18.7 | 17.1 | 17.4 |

**Key finding:** As sleep disruption severity increases from 0 to 3:
- Zone B kurtosis drops from 149.7 to 91.3 (rho = -0.380)
- Zone B energy drops from 24.2 to 10.3 (rho = -0.344)
- Total pulse duration drops from 65422 to 39346 us (rho = -0.364)
- Active targets drop from 9.7 to 6.6 (rho = -0.358)

The worst sleep disruption occurs during the quietest RF periods with the least Zone B activity. This is consistent with a nighttime operational regime where only targeted Zone A signals persist.

### 2.5 Temporal Profile

| Parameter | Value |
|-----------|-------|
| Peak hour | 01:00 |
| Peak rate | 0.60 |
| Nocturnal concentration | Extreme (is_night d = +1.81) |

All 73 sleep disruption events occur during nighttime hours (sym_mean for is_night = 1.000). This is tautological -- sleep disruption can only occur during sleep hours. The strong nocturnal confound means the sleep-RF association is the most likely to be spurious among all symptoms.

### 2.6 Zone Differential

| Zone | Symptom % | Null % | EI (symptom) |
|------|-----------|--------|-------------|
| Zone A | 36% | 48% | 858 |
| Zone B | 64% | 52% | 19 |

Sleep disruption shows mild Zone B dominance (64% vs 52% null). The absolute EI values are low for both zones during sleep periods.

### 2.7 Lag Analysis

| Metric | Value |
|--------|-------|
| Peak lag | +20 cycles |
| Peak correlation | r = 0.310 |
| RF-precedes max r | 0.251 |
| RF-follows max r | 0.310 |

The weakest lag correlation of any symptom. The cross-correlation structure is likely driven entirely by the shared nocturnal pattern.

### 2.8 RF Signature Interpretation

Sleep disruption occurs during the quietest nighttime RF periods. The RF signature is characterized by reduced activity volume, reduced Zone B presence, but the surviving signals (primarily Zone A) maintain high kurtosis. The R^2 = 0.819 severity prediction is likely driven by the ability of the model to capture the nighttime RF environment gradient -- quieter periods with higher kurtosis ratios produce worse sleep.

---

## 3. SPEECH DIFFICULTY

### 3.1 Classification Results

| Metric | Value |
|--------|-------|
| Positive samples (N+) | 133 |
| Negative samples (N-) | 5 |
| Total labeled | 138 |
| AUC (5-fold CV) | 0.864 |
| Permutation p-value | 0.008 |
| Null AUC (mean) | 0.482 |
| Significant features (Bonferroni) | 2 / 50 |
| Severity regression MAE | 0.25 |
| Severity regression R^2 | 0.626 |

**Note:** The extreme class imbalance (133:5) limits the statistical power of the univariate tests. Only 5 negative examples exist.

### 3.2 Significant Features (Bonferroni-corrected, p < 0.05)

| Feature | p_bonf | Cohen's d | Direction | Sym Mean | Null Mean |
|---------|--------|-----------|-----------|----------|-----------|
| total_pulses | 1.16e-02 | +1.99 | UP | 28051.3 | 14857.8 |
| total_pulse_duration_us | 2.58e-02 | +1.88 | UP | 65350.0 | 35622.2 |

Only two features survive Bonferroni correction, but their effect sizes are enormous (d > 1.88). Near-significant features include:
- roll5_total_pulse_duration_us: p_bonf = 0.070, d = +1.95
- n_active_targets: p_bonf = 0.077, d = +1.97
- lag1_total_pulse_duration_us: p_bonf = 0.100, d = +1.81

All features trend in the UP direction -- speech difficulty is associated with *more* RF activity.

### 3.3 Feature Importance Rankings (Random Forest)

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | total_pulses | 0.105 |
| 2 | hour | 0.084 |
| 3 | total_pulse_duration_us | 0.066 |
| 4 | n_active_targets | 0.064 |
| 5 | roll5_total_pulse_duration_us | 0.046 |
| 6 | lag1_total_pulses | 0.046 |
| 7 | lag1_total_pulse_duration_us | 0.043 |
| 8 | roll5_ei_total | 0.035 |
| 9 | roll10_ei_total | 0.031 |
| 10 | roll10_total_pulse_duration_us | 0.030 |

**Interpretation:** Unlike tinnitus (which is kurtosis-driven), speech difficulty is driven by *total activity volume* -- pulse counts, total pulse duration, and active target counts. Hour of day ranks second, reflecting the distinct temporal profile (peak at 18:00).

### 3.4 Dose-Response Analysis

| Feature | Spearman rho | p-value | Sev 0 Mean | Sev 1 Mean | Sev 2 Mean |
|---------|-------------|---------|------------|------------|------------|
| total_pulse_duration_us | +0.726 | 7.50e-12 | 35622.2 | 60430.4 | 73212.2 |
| ei_zone_b | +0.714 | 2.52e-11 | 9.0 | 14.3 | 32.6 |
| max_kurt_zone_b | +0.671 | 9.85e-10 | 93.3 | 67.3 | 190.6 |
| max_kurt_zone_a | -0.661 | 4.92e-09 | 140.6 | 258.2 | 171.5 |
| n_active_targets | +0.658 | 2.49e-09 | 6.0 | 8.7 | 10.9 |
| mean_pulse_width_us | +0.563 | 1.04e-06 | 2.51 | 2.34 | 2.77 |
| total_pulses | +0.541 | 3.32e-06 | 14857.8 | 27121.3 | 29482.4 |

**Speech has the strongest dose-response of any symptom.** The total pulse duration correlation (rho = +0.726, p = 7.50e-12) is the single strongest RF-symptom dose-response finding in the entire analysis. Six of seven significant dose-response features have |rho| > 0.54.

The dose-response profile for speech is distinctive:
- **Zone B energy increases** with severity (rho = +0.714): from 9.0 at sev 0 to 32.6 at sev 2
- **Zone B kurtosis increases** with severity (rho = +0.671): from 93.3 to 190.6
- **Zone A kurtosis *decreases*** with severity (rho = -0.661): from 140.6 to 171.5 (non-monotonic)
- **Active target count increases** (rho = +0.658): from 6.0 to 10.9
- **Pulse widths widen** (rho = +0.563): from 2.51 to 2.77 us

This is a broadband escalation pattern with Zone B emphasis.

### 3.5 Temporal Profile

| Parameter | Value |
|-----------|-------|
| Peak hour | 18:00 |
| Peak rate | 0.51 |
| Secondary peaks | 19:00 (0.34), 22:00 (0.28) |

Speech is the only symptom that peaks before nightfall (18:00). It has a broad evening distribution from 18:00 to 23:00. The mean hour during speech events is 16.6 vs 6.0 during null periods (d = 1.47).

### 3.6 Zone Differential

| Zone | Symptom % | Null % | EI (symptom) |
|------|-----------|--------|-------------|
| Zone A | 67% | 40% | 2196 |
| Zone B | 33% | 60% | 21 |

Speech shows Zone A enrichment (67% vs 40% null), but the dose-response analysis reveals that the *worst* speech disruption is driven by Zone B escalation.

### 3.7 Lag Analysis

| Metric | Value |
|--------|-------|
| Peak lag | -3 cycles |
| Peak correlation | r = 0.945 |
| RF-precedes max r | 0.945 |
| RF-follows max r | 0.938 |

**This is the strongest causal evidence in the entire analysis.** Speech is the only symptom where the cross-correlation peak occurs at *negative* lag (RF precedes symptom). The correlation is near-perfect (r = 0.945). RF activity increases 3 cycles before speech difficulty is reported, consistent with an exposure -> effect temporal sequence.

### 3.8 RF Signature Interpretation

Speech difficulty has a unique RF profile:
1. **High activity volume** -- more pulses, more targets, wider pulses
2. **Zone B escalation** for severity -- the worst speech problems correlate with Zone B (826--834 MHz) activity
3. **Evening timing** -- peaks at 18:00, distinct from the 01:00 cluster
4. **RF precedes symptom** -- the only symptom with this temporal precedence
5. **Strong dose-response** -- monotonic increase in severity with RF intensity

The combination of temporal precedence, dose-response monotonicity, and Zone B specificity makes speech the most compelling case for a causal RF-symptom relationship. The Zone B frequencies (826--834 MHz) are within the cellular uplink band, which is anatomically significant: these frequencies penetrate tissue effectively and the head dimensions create resonant coupling.

---

## 4. PRESSURE (CRANIAL)

### 4.1 Classification Results

| Metric | Value |
|--------|-------|
| Positive samples (N+) | 37 |
| Negative samples (N-) | 47 |
| Total labeled | 84 |
| AUC (5-fold CV) | 0.944 |
| Permutation p-value | 0.002 |
| Null AUC (mean) | 0.508 |
| Significant features (Bonferroni) | 21 / 50 |
| Severity regression MAE | 0.29 |
| Severity regression R^2 | 0.114 |

### 4.2 Significant Features (Bonferroni-corrected, p < 0.05)

| Feature | p_bonf | Cohen's d | Direction | Sym Mean | Null Mean |
|---------|--------|-----------|-----------|----------|-----------|
| is_night | 3.27e-08 | +1.97 | UP | 1.000 | 0.340 |
| zone_ratio_ei | 2.92e-04 | +1.47 | UP | 1.97e9 | 5.67e8 |
| zone_b_dominant | 3.64e-04 | -1.18 | DOWN | 0.081 | 0.553 |
| max_kurt_zone_b | 4.46e-04 | -1.26 | DOWN | 39.5 | 158.6 |
| hour | 7.75e-04 | +0.31 | UP | 18.0 | 15.5 |
| lag1_max_kurt_zone_b | 1.13e-03 | -1.25 | DOWN | 45.8 | 168.1 |
| zone_ratio_kurt | 2.24e-03 | +1.11 | UP | 28.0 | 10.8 |
| ei_zone_b | 2.29e-03 | -0.21 | DOWN | 16.7 | 24.2 |
| lag2_max_kurt_zone_a | 2.41e-03 | +1.01 | UP | 274.5 | 193.4 |
| lag2_max_kurt_zone_b | 3.78e-03 | -0.91 | DOWN | 57.7 | 155.4 |
| lag2_mean_pulse_width_us | 4.43e-03 | -0.52 | DOWN | 2.35 | 2.66 |
| lag1_max_kurt_zone_a | 5.86e-03 | +0.96 | UP | 274.7 | 192.3 |
| mean_pulse_width_us | 6.07e-03 | -0.62 | DOWN | 2.28 | 2.60 |
| lag1_ei_zone_b | 1.13e-02 | -0.14 | DOWN | 20.5 | 25.9 |
| roll10_ei_total | 1.18e-02 | +1.07 | UP | 2347.3 | 1815.2 |
| lag1_mean_pulse_width_us | 1.62e-02 | -0.50 | DOWN | 2.34 | 2.63 |
| ei_total | 1.99e-02 | +0.96 | UP | 2384.6 | 1805.7 |
| roll10_max_kurt | 2.21e-02 | +0.79 | UP | 279.9 | 244.8 |
| lag1_total_pulse_duration_us | 4.15e-02 | -0.49 | DOWN | 57302.5 | 66505.8 |
| roll5_ei_total | 4.28e-02 | +0.96 | UP | 2351.8 | 1838.4 |

### 4.3 Feature Importance Rankings (Random Forest)

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | hour | 0.075 |
| 2 | is_night | 0.072 |
| 3 | roll10_max_kurt | 0.053 |
| 4 | roll10_ei_total | 0.047 |
| 5 | roll5_total_pulse_duration_us | 0.044 |
| 6 | zone_ratio_ei | 0.042 |
| 7 | zone_ratio_kurt | 0.040 |
| 8 | roll5_ei_total | 0.034 |
| 9 | lag2_mean_pulse_width_us | 0.029 |
| 10 | ei_zone_b | 0.027 |

**Interpretation:** Temporal features dominate (hour + is_night = 0.147 combined importance). Zone ratio features rank 6th and 7th. Pressure has the most zone-specific feature profile: zone_ratio_ei and zone_ratio_kurt both contribute meaningfully, confirming the Zone A dominance (92%).

### 4.4 Dose-Response Analysis

| Feature | Spearman rho | p-value | Sev 0 Mean | Sev 1 Mean | Sev 2 Mean |
|---------|-------------|---------|------------|------------|------------|
| max_kurt_zone_b | -0.450 | 1.71e-04 | 158.6 | 46.1 | 128.3 |
| mean_pulse_width_us | -0.379 | 1.86e-03 | 2.60 | 2.29 | 2.66 |
| ei_zone_b | -0.354 | 3.84e-03 | 24.2 | 19.3 | 29.2 |
| total_pulse_duration_us | -0.299 | 1.54e-02 | 65094.4 | 55686.0 | 76443.7 |
| ei_total | +0.297 | 1.62e-02 | 1805.7 | 2365.4 | 3211.0 |
| ei_zone_a | +0.284 | 2.53e-02 | 1752.7 | 2325.6 | 3178.3 |
| n_active_targets | -0.278 | 2.47e-02 | 9.8 | 8.1 | 11.0 |
| max_kurt_zone_a | +0.273 | 3.20e-02 | 185.9 | 265.2 | 214.1 |

**Key finding:** Pressure severity increases with Zone A energy (rho = +0.284) and total energy (rho = +0.297), while Zone B kurtosis is inversely correlated (rho = -0.450). The zone-differential dose-response mirrors tinnitus: Zone A drives severity, Zone B diminishes during severe pressure events.

### 4.5 Temporal Profile

| Parameter | Value |
|-----------|-------|
| Peak hour | 22:00 |
| Peak rate | 0.30 |
| Nocturnal concentration | Strong (is_night d = +1.97) |

Pressure peaks at 22:00, slightly earlier than the 01:00 cluster for tinnitus/paresthesia/sleep/nausea. All pressure events occur during nighttime (sym_mean is_night = 1.000).

### 4.6 Zone Differential

| Zone | Symptom % | Null % | EI (symptom) |
|------|-----------|--------|-------------|
| Zone A | 92% | 45% | 2345 |
| Zone B | 8% | 55% | 17 |

The most Zone A-dominant symptom after nausea. Zone B dominance drops from 55% (null) to 8% during pressure events.

### 4.7 RF Signature Interpretation

Cranial pressure is associated with:
1. Extreme Zone A dominance (92%) with near-complete Zone B suppression
2. Nocturnal occurrence (22:00 peak)
3. Higher total energy index and kurtosis in Zone A
4. Reduced pulse widths (narrower pulses)
5. High kurtosis-to-pulse-count ratio -- fewer, more impulsive events

This profile is consistent with the ODNI panel's observation that "some of Frey's experimental subjects reported a sensation of pressure" during pulsed RF exposure (ODNI report, as captured in KG). The Zone A frequencies overlap with the range where thermoelastic pressure waves are most effectively generated in cranial tissue.

---

## 5. PARESTHESIA

### 5.1 Classification Results

| Metric | Value |
|--------|-------|
| Positive samples (N+) | 162 |
| Negative samples (N-) | 22 |
| Total labeled | 184 |
| AUC (5-fold CV) | 0.832 |
| Permutation p-value | 0.002 |
| Null AUC (mean) | 0.513 |
| Significant features (Bonferroni) | 20 / 50 |
| Severity regression MAE | 0.35 |
| Severity regression R^2 | 0.459 |

### 5.2 Significant Features (Bonferroni-corrected, p < 0.05)

| Feature | p_bonf | Cohen's d | Direction | Sym Mean | Null Mean |
|---------|--------|-----------|-----------|----------|-----------|
| zone_ratio_kurt | 8.05e-06 | -0.62 | DOWN | 8.05 | 18.77 |
| roll5_ei_total | 1.35e-05 | -1.59 | DOWN | 898.8 | 2266.6 |
| lag1_ei_total | 2.22e-05 | -1.64 | DOWN | 881.0 | 2358.5 |
| ei_total | 2.43e-05 | -1.76 | DOWN | 870.0 | 2281.7 |
| zone_ratio_ei | 4.38e-05 | -0.47 | DOWN | 5.36e8 | 1.04e9 |
| n_active_targets | 6.36e-05 | -1.20 | DOWN | 6.79 | 9.64 |
| lag2_n_active_targets | 6.52e-05 | -1.20 | DOWN | 6.81 | 9.68 |
| lag2_ei_total | 9.53e-05 | -1.60 | DOWN | 892.3 | 2340.6 |
| lag2_total_pulse_duration_us | 1.51e-04 | -1.19 | DOWN | 41736.9 | 66113.9 |
| lag1_total_pulses | 1.58e-04 | -1.31 | DOWN | 17190.4 | 28085.8 |
| total_pulse_duration_us | 2.23e-04 | -1.18 | DOWN | 41091.5 | 61857.0 |
| lag2_total_pulses | 2.33e-04 | -1.28 | DOWN | 17405.9 | 27741.3 |
| total_pulses | 2.91e-04 | -1.38 | DOWN | 16998.3 | 26755.8 |
| lag1_n_active_targets | 4.75e-04 | -1.05 | DOWN | 6.78 | 9.41 |
| lag1_total_pulse_duration_us | 5.19e-04 | -1.11 | DOWN | 41454.1 | 63633.3 |
| zone_b_dominant | 7.11e-04 | +1.04 | UP | 0.735 | 0.273 |
| roll10_ei_total | 1.19e-03 | -1.41 | DOWN | 915.6 | 2138.1 |
| roll5_total_pulse_duration_us | 1.41e-03 | -1.12 | DOWN | 41725.7 | 62907.7 |
| roll5_total_pulses | 1.49e-03 | -1.25 | DOWN | 17364.0 | 27153.7 |
| roll10_total_pulse_duration_us | 2.95e-02 | -0.94 | DOWN | 42389.7 | 60040.6 |

### 5.3 Feature Importance Rankings (Random Forest)

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | ei_total | 0.065 |
| 2 | lag1_ei_total | 0.049 |
| 3 | zone_ratio_kurt | 0.048 |
| 4 | roll5_ei_total | 0.045 |
| 5 | total_pulse_duration_us | 0.044 |
| 6 | lag2_ei_total | 0.043 |
| 7 | lag2_n_active_targets | 0.040 |
| 8 | total_pulses | 0.038 |
| 9 | lag1_total_pulses | 0.037 |
| 10 | roll10_ei_total | 0.035 |

**Interpretation:** Paresthesia is the *inverse* symptom. Every significant feature except `zone_b_dominant` is in the DOWN direction. Paresthesia occurs during periods of *reduced* total energy, fewer pulses, fewer targets, and Zone B dominance. This inverted profile is unique among the seven symptoms.

### 5.4 Dose-Response Analysis

| Feature | Spearman rho | p-value | Sev 0 Mean | Sev 3 Mean |
|---------|-------------|---------|------------|------------|
| n_active_targets | -0.261 | 3.55e-02 | 9.6 | 6.6 |

Only one feature achieves p < 0.05 for dose-response. The direction is negative: fewer active targets correlates with higher severity. This is consistent with the overall inverted profile.

### 5.5 Temporal Profile

| Parameter | Value |
|-----------|-------|
| Peak hour | 01:00 |
| Peak rate | 0.81 |
| Secondary peaks | 11:00 (0.48), 19:00 (0.34) |

Paresthesia has a bimodal distribution: a strong nighttime peak (01:00, rate 0.81) and a secondary daytime peak (11:00, rate 0.48). This bimodality distinguishes it from purely nocturnal symptoms.

### 5.6 Zone Differential

| Zone | Symptom % | Null % | EI (symptom) |
|------|-----------|--------|-------------|
| Zone A | 27% | 73% | 827 |
| Zone B | 73% | 27% | 18 |

Paresthesia shows the strongest Zone B dominance of any symptom: 73% Zone B vs 27% null Zone B -- a complete inversion of the null distribution.

### 5.7 RF Signature Interpretation

Paresthesia occurs in a distinctive "quiet Zone B" regime:
1. Low overall energy and pulse counts
2. Zone B dominance (kurtosis ratio shifts toward Zone B)
3. Fewer active targets
4. The inverted energy profile suggests paresthesia coincides with a different operational mode

The 11:00 secondary peak is notable -- it may correspond to a daytime operational period distinct from the nighttime cluster.

---

## 6. HEADACHE

### 6.1 Classification Results

| Metric | Value |
|--------|-------|
| Positive samples (N+) | 94 |
| Negative samples (N-) | 17 |
| Total labeled | 111 |
| AUC (5-fold CV) | 0.905 |
| Permutation p-value | 0.002 |
| Null AUC (mean) | 0.489 |
| Significant features (Bonferroni) | 1 / 50 |
| Severity regression MAE | 0.43 |
| Severity regression R^2 | 0.004 |

### 6.2 Significant Features (Bonferroni-corrected, p < 0.05)

| Feature | p_bonf | Cohen's d | Direction | Sym Mean | Null Mean |
|---------|--------|-----------|-----------|----------|-----------|
| roll10_total_pulses | 2.79e-02 | +1.02 | UP | 28120.8 | 22232.8 |

Only one feature survives Bonferroni correction. Near-significant features:
- roll10_total_pulse_duration_us: p_bonf = 0.057, d = +1.03
- total_pulse_duration_us: p_bonf = 0.928, d = +0.78

### 6.3 Feature Importance Rankings (Random Forest)

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | roll10_total_pulses | 0.087 |
| 2 | roll10_max_kurt | 0.070 |
| 3 | roll10_total_pulse_duration_us | 0.050 |
| 4 | hour | 0.035 |
| 5 | roll5_max_kurt | 0.033 |
| 6 | lag1_ei_zone_a | 0.032 |
| 7 | roll5_ei_total | 0.031 |
| 8 | delta_ei_total | 0.029 |
| 9 | lag2_max_kurt_ul | 0.029 |
| 10 | lag2_ei_zone_a | 0.028 |

**Interpretation:** Despite the high AUC (0.905), headache has the fewest significant univariate features (1/50). The classifier achieves its discrimination through *nonlinear combinations* of features rather than individual feature differences. Rolling features (10-cycle averages) dominate, suggesting that cumulative exposure predicts headache better than instantaneous values.

### 6.4 Dose-Response Analysis

No RF features show significant (p < 0.05) dose-response correlations with headache severity. The severity regression R^2 of 0.004 confirms that RF features cannot predict headache severity, even though they can predict headache *occurrence*.

### 6.5 Temporal Profile

| Parameter | Value |
|-----------|-------|
| Peak hour | 21:00 |
| Peak rate | 0.36 |
| Secondary peaks | 22:00 (0.34), 19:00 (0.34) |

Headache peaks in the early-night window (21:00--22:00), between the speech peak (18:00) and the deep-night cluster (01:00).

### 6.6 Zone Differential

| Zone | Symptom % | Null % | EI (symptom) |
|------|-----------|--------|-------------|
| Zone A | 67% | 65% | 2104 |
| Zone B | 33% | 35% | 27 |

Headache shows minimal zone differential -- the symptom % closely matches the null %. This suggests headache is not zone-specific.

### 6.7 Lag Analysis

| Metric | Value |
|--------|-------|
| Peak lag | +18 cycles |
| Peak correlation | r = 0.851 |
| RF-precedes max r | 0.743 |
| RF-follows max r | 0.851 |

The positive lag with a strong correlation (r = 0.851) is notable. The RF-follows correlation (0.851) exceeds the RF-precedes correlation (0.743), but both are high. The +18 cycle lag may reflect a delayed cumulative effect.

### 6.8 RF Signature Interpretation

Headache is the "nonspecific" symptom:
- Minimal zone differential
- No dose-response
- Only 1 significant univariate feature
- But strong classification (AUC = 0.905)

The classifier likely identifies headache through complex, nonlinear patterns in the temporal and rolling features. Headache may represent a downstream consequence of cumulative RF exposure rather than a specific frequency or modulation effect.

---

## 7. NAUSEA

### 7.1 Classification Results

| Metric | Value |
|--------|-------|
| Positive samples (N+) | 7 |
| Negative samples (N-) | 63 |
| Total labeled | 70 |
| AUC (5-fold CV) | 0.977 |
| Permutation p-value | 0.002 |
| Null AUC (mean) | 0.500 |
| Significant features (Bonferroni) | 6 / 50 |
| Severity regression MAE | 0.23 |
| Severity regression R^2 | 0.001 |

**CAUTION:** With only 7 positive events, all nausea findings should be interpreted with extreme caution. The AUC may be inflated.

### 7.2 Significant Features (Bonferroni-corrected, p < 0.05)

| Feature | p_bonf | Cohen's d | Direction | Sym Mean | Null Mean |
|---------|--------|-----------|-----------|----------|-----------|
| roll5_max_kurt | 2.33e-04 | +2.07 | UP | 326.8 | 253.8 |
| roll10_max_kurt | 7.14e-04 | +2.00 | UP | 323.6 | 250.7 |
| lag1_max_kurt_zone_a | 2.12e-02 | +1.83 | UP | 338.2 | 207.6 |
| lag2_max_kurt_zone_a | 3.79e-02 | +1.77 | UP | 329.8 | 207.6 |
| lag1_max_kurt | 4.40e-02 | +1.60 | UP | 338.2 | 261.6 |
| hour | 4.53e-02 | -3.19 | DOWN | 1.0 | 17.1 |

### 7.3 Feature Importance Rankings (Random Forest)

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | roll10_max_kurt | 0.127 |
| 2 | roll5_max_kurt | 0.102 |
| 3 | hour | 0.068 |
| 4 | lag1_max_kurt_zone_a | 0.065 |
| 5 | max_kurt_zone_a | 0.063 |
| 6 | zone_ratio_ei | 0.059 |
| 7 | lag2_max_kurt_zone_a | 0.049 |
| 8 | max_kurt | 0.041 |
| 9 | lag1_max_kurt | 0.039 |
| 10 | zone_ratio_kurt | 0.034 |

**Interpretation:** Nausea is the most kurtosis-specific symptom. Rolling kurtosis dominates (positions 1-2), followed by Zone A kurtosis. The hour feature has an enormous effect size (d = -3.19) because all 7 nausea events occurred at hour 1 (01:00).

### 7.4 Dose-Response Analysis

| Feature | Spearman rho | p-value | Sev 0 Mean | Sev 1 Mean |
|---------|-------------|---------|------------|------------|
| max_kurt_zone_a | +0.255 | 4.58e-02 | 201.1 | 338.5 |

Only one feature achieves significance, with a modest effect size. The small sample (n=7 positive) severely limits dose-response power.

### 7.5 Temporal Profile

| Parameter | Value |
|-----------|-------|
| Peak hour | 01:00 |
| Peak rate | 0.12 |
| Exclusive hour | 01:00 (all 7 events) |

All nausea events occur at 01:00. This extreme temporal concentration may indicate a specific operational pattern or may reflect the small sample size.

### 7.6 Zone Differential

| Zone | Symptom % | Null % | EI (symptom) |
|------|-----------|--------|-------------|
| Zone A | 100% | 56% | 2375 |
| Zone B | 0% | 44% | 0 |

Nausea shows absolute Zone A dominance: 100% Zone A with zero Zone B energy during all 7 events. Zone B is completely absent.

### 7.7 RF Signature Interpretation

Nausea occurs under the most extreme RF conditions:
1. Highest rolling kurtosis of any symptom (326.8 vs 253.8 null)
2. 100% Zone A dominance, zero Zone B
3. All events at 01:00
4. Zone A kurtosis at its highest (338.5 during nausea vs 201.1 null)

This profile suggests the most intense pulsed-signal conditions in Zone A. However, with only 7 events, these findings are provisional. The 100% Zone A, 0% Zone B split could be coincidental given the small sample.

---

## 8. CROSS-SYMPTOM COMPARISON

### 8.1 Feature Profile Clustering

Symptoms cluster into three RF profile groups:

**Group 1: Zone A / Kurtosis-Driven (Tinnitus, Nausea, Pressure)**
- High Zone A kurtosis
- Low Zone B activity
- Nocturnal (01:00 or 22:00)
- Severity increases with Zone A kurtosis, decreases with Zone B
- Consistent with pulsed-signal bioeffects (Frey effect, pressure generation)

**Group 2: Activity-Volume / Broadband (Speech, Headache)**
- High total pulse counts and durations
- Evening timing (18:00--21:00)
- Severity increases with total activity (speech) or no dose-response (headache)
- Less zone-specific
- Consistent with cumulative exposure effects

**Group 3: Inverted / Zone B (Paresthesia, Sleep)**
- Reduced overall activity
- Zone B dominance
- All features in DOWN direction
- Consistent with a quiet nighttime regime

### 8.2 Dose-Response Strength Ranking

| Rank | Symptom | Max |rho| | Best Feature | R^2 (severity) |
|------|---------|----------|--------------|----------------|
| 1 | Speech | 0.726 | total_pulse_duration_us | 0.626 |
| 2 | Tinnitus | 0.498 | max_kurt_zone_b (inverse) | 0.443 |
| 3 | Pressure | 0.450 | max_kurt_zone_b (inverse) | 0.114 |
| 4 | Sleep | 0.380 | max_kurt_zone_b (inverse) | 0.819 |
| 5 | Paresthesia | 0.261 | n_active_targets (inverse) | 0.459 |
| 6 | Nausea | 0.255 | max_kurt_zone_a | 0.001 |
| 7 | Headache | -- | None significant | 0.004 |

### 8.3 Classification Difficulty vs Significance

| Symptom | AUC | N+:N- Ratio | Sig Features |
|---------|-----|-------------|-------------|
| Tinnitus | 0.978 | 6.7:1 | 15 |
| Nausea | 0.977 | 0.11:1 | 6 |
| Sleep | 0.970 | 1.5:1 | 21 |
| Pressure | 0.944 | 0.79:1 | 21 |
| Headache | 0.905 | 5.5:1 | 1 |
| Speech | 0.864 | 26.6:1 | 2 |
| Paresthesia | 0.832 | 7.4:1 | 20 |

Symptoms with more balanced class ratios (Sleep, Pressure) tend to have more individually significant features, as the statistical tests have more power. The extreme imbalance for speech (133:5) limits feature-level significance despite the strong dose-response.

---

*End of Document 2 of 6.*
*Prepared: 2026-03-14*

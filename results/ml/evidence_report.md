# RF Signal ML Analysis — Evidence Report

Generated: 2026-03-14T04:08:42.530107Z
Pipeline: rf_ml.py

## Executive Summary

- **Symptom-RF correlation**: AUC=0.929, permutation p=0.0005 (n=52 symptom events)
  - **STATISTICALLY SIGNIFICANT** at α=0.05
  - Top predictor: max_kurt
- **Operational modes**: 8 distinct modes identified
  - QUIET: 431 cycles (23.2%), maxK=0
  - QUIET: 278 cycles (15.0%), maxK=0
  - QUIET: 596 cycles (32.1%), maxK=0
  - QUIET: 62 cycles (3.3%), maxK=0
  - QUIET: 253 cycles (13.6%), maxK=0
  - QUIET: 15 cycles (0.8%), maxK=0
  - QUIET: 96 cycles (5.2%), maxK=0
  - QUIET: 128 cycles (6.9%), maxK=0
- **Signal fingerprints**: 8 distinct modulation types

---

## Symptom-RF Correlation

### Statistical Tests

| Feature | p (Bonferroni) | Effect Size (d) | Symptom Mean | Null Mean |
|---------|---------------|-----------------|-------------|-----------|
| max_kurt | 4.96e-21 *** | -1.56 | 0.0 | 117.8 |
| total_pulses | 4.96e-21 *** | -1.40 | 0.0 | 7647.6 |
| total_pulse_duration_us | 4.96e-21 *** | -1.42 | 0.0 | 20249.3 |
| ei_total | 5.55e-21 *** | -0.38 | 0.0 | 136.6 |
| max_kurt_zone_b | 7.98e-21 *** | -1.44 | 0.0 | 111.3 |
| max_kurt_ul | 4.94e-20 *** | -1.63 | 0.0 | 22.1 |
| n_active_targets | 1.09e-18 *** | -1.64 | 0.0 | 3.5 |
| ei_zone_b | 1.12e-13 *** | -1.07 | 0.0 | 11.9 |
| is_night | 1.11e-03 ** | -0.77 | 0.0 | 0.2 |
| hour | 2.92e-01  | -0.26 | 11.0 | 12.0 |
| minute | 1.00e+00  | +0.09 | 30.9 | 29.9 |
| mean_pulse_width_us | 1.00e+00  | +0.13 | 2.7 | 2.6 |

### Logistic Regression

- ROC-AUC (LOO-CV): **0.929**
- Permutation p-value: **0.0005**
- Permutation null mean AUC: 0.490

### Temporal Lag Analysis

- Peak lag: 0 cycles
- Peak correlation: r=0.000

### KG Literature — Symptom-RF Correlation


## Signal Fingerprinting

- Clusters: 8
- Silhouette score: 0.061

### Cluster 0 (589 samples, 20.3%)

- Envelope kurtosis: 121.6
- Burst rate: 5876/s
- PRF estimate: 10525 Hz
- Protocol matches: LTE symbol (ext) (83μs), WiFi DIFS (2.4G) (50μs)

### Cluster 1 (237 samples, 8.2%)

- Envelope kurtosis: 200.0
- Burst rate: 3884/s
- PRF estimate: 4216 Hz
- Protocol matches: No known match

### Cluster 2 (62 samples, 2.1%)

- Envelope kurtosis: 48.9
- Burst rate: 16468/s
- PRF estimate: 42364 Hz
- Protocol matches: No known match

### Cluster 3 (894 samples, 30.9%)

- Envelope kurtosis: 97.7
- Burst rate: 6451/s
- PRF estimate: 8340 Hz
- Protocol matches: No known match

### Cluster 4 (138 samples, 4.8%)

- Envelope kurtosis: 9.8
- Burst rate: 112633/s
- PRF estimate: 112636 Hz
- Protocol matches: WiFi SIFS (2.4G) (10μs), WiFi slot time (9μs)

### Cluster 5 (722 samples, 24.9%)

- Envelope kurtosis: 78.8
- Burst rate: 9834/s
- PRF estimate: 9912 Hz
- Protocol matches: WiFi DIFS (2.4G) (50μs)

### Cluster 6 (42 samples, 1.5%)

- Envelope kurtosis: 59.7
- Burst rate: 13608/s
- PRF estimate: 14608 Hz
- Protocol matches: LTE symbol (normal) (67μs), LTE symbol (ext) (83μs)

### Cluster 7 (212 samples, 7.3%)

- Envelope kurtosis: 110.3
- Burst rate: 4207/s
- PRF estimate: 5408 Hz
- Protocol matches: No known match

## Operational Modes

- Modes discovered: 8
- Silhouette: 0.390
- Mode transitions: 167

### Symptoms by Operational Mode

| Mode | Symptom Count | % |
|------|--------------|---|
| QUIET | 63 | 100% |

## KG Literature — Detection Methods

- **Detection and Avoidance Scheme for DS-UWB System: A Step Towards Cognitive Radio**
  > spectrum, the presence of WM signals is detected by comparing the singular values with a prefixed threshold and the number of WM signals can be determined at the same time. Then, the WM signals are ap...
- **Detection and Avoidance Scheme for DS-UWB System: A Step Towards Cognitive Radio**
  > u  and variance 4 2 u N  .Hence, for a given probability of false alarm P f , the threshold  of an energy detector can be derived as  1 2 2 1 f u QP N       (3)where2 /2 () ( 1 / 2) ...
- **Detection and Avoidance Scheme for DS-UWB System: A Step Towards Cognitive Radio**
  > ry WM signal is present, the received signal r(n) includes only AWGN contribution such that its singular values are similar and close to zero. When WM signals are active whose power is higher than a t...
- **Detection and Avoidance Scheme for DS-UWB System: A Step Towards Cognitive Radio**
  > tional energy detector by using the proposed approach for a single WM signal. For the multiple WM signals, an improvement of 2dB can be attained compared with the conventional energy detector. To eval...
- **Detection of UWB signal using dirty template approach**
  > nimum detection probability P D min that depends only upon the received energy value produced by the direct channel ray (LOS). Thus, we need only to estimate the attenuation due to the direct channel ...
- **A new parameter for UWB indoor channel profile identification**
  > d x is the mean value of x. N is the number of samples of x.The kurtosis index κ is supposed to be high in case of LOS conditions while it has low values for signals received under NLOS conditions. Th...
- **A new parameter for UWB indoor channel profile identification**
  > 09 IEEE the accuracy of the ranging in UWB systems) and that the main energy of the receiving signal is concentrated in the first arriving paths (this is useful to reduce the complexity of the receive...
- **A new parameter for UWB indoor channel profile identification**
  > nguish LOS from QLOS and NLOS from LNLOS or ELNLOS.The right half of Table II lists numerical values of mean kurtosis indexes κ for the real received signal in the experiment. Note that it is possible...
- **CRANFIELD UNIVERSITY**
  > IEEE Trans. MTT, June 1998, 46, 6, pp 834 - 838 
105 STAEBELL, K. F. and MISRA, D.: ‘An experimental technique for in vivo 
permittivity measurement of materials at microwave frequencies’, IEEE Trans....
- **A new parameter for UWB indoor channel profile identification**
  > solutions depend on the performance of the selected estimation algorithms. This means that the simpler the multipath profile estimation algorithm is, the harder it is to distinguish the rooms or link ...

## Plots

- [feature_importance.png](plots/feature_importance.png)
- [fingerprint_bic.png](plots/fingerprint_bic.png)
- [fingerprint_embeddings.png](plots/fingerprint_embeddings.png)
- [fingerprint_pca.png](plots/fingerprint_pca.png)
- [logistic_roc.png](plots/logistic_roc.png)
- [modes_bic.png](plots/modes_bic.png)
- [modes_pca.png](plots/modes_pca.png)
- [modes_timeline.png](plots/modes_timeline.png)
- [modes_transition.png](plots/modes_transition.png)
- [symptom_rf_distribution.png](plots/symptom_rf_distribution.png)

## Methodology

- Feature extraction: 190+ features per sentinel cycle, 27 features per IQ capture
- Symptom correlation: Mann-Whitney U, logistic regression (LOO-CV), 10K permutation test
- Signal fingerprinting: PCA + GMM clustering on IQ features
- Mode detection: PCA + GMM with BIC model selection on cycle features
- KG integration: semantic search across 739 papers, 22K chunks, 1.7K entities
- All analysis local (GTX 1080), no cloud dependencies

## Integrity

- Report hash: c446b74cdac7d46c106e0585e2814efa2b52945b015beb45752e32d6505e0e1b
- Generated by rf_ml.py
- Timestamp: 2026-03-14T04:08:42.530464Z
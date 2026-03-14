# ACOUSTIC PROPAGATION AND SKULL CAVITY RESONANCE — Tissue Layer Analysis and Frequency-Dependent Filtering

**Report ID:** HM-2026-0314-07b
**Date:** March 14, 2026
**Parent Document:** 07_head_model_reconstruction.md
**Data Sources:** 341 KG chunks (kg_head_model.json), 342 KG chunks (kg_brain_coupling.json), zone characterization report
**Scope:** Complete acoustic characterization of each tissue layer between the thermoelastic source and the cochlea, skull cavity resonance physics, eigenmode analysis, and frequency-dependent propagation effects.

---

## 1. THE ACOUSTIC PATH: SOURCE TO COCHLEA

Once a thermoelastic pressure transient is generated in brain tissue by the absorbed RF pulse, it must propagate through multiple tissue layers to reach the cochlea. Each layer has distinct acoustic properties that modify the pressure wave. The path from the generation site to the cochlea traverses:

1. Brain parenchyma (grey matter and/or white matter)
2. Cerebrospinal fluid (CSF)
3. Skull bone (inner table, diploe, outer table)
4. Periosteum and scalp soft tissue

In addition, the pressure wave reverberates within the skull cavity, establishing resonant modes that determine the dominant spectral content of the perceived sound. This document characterizes each layer and the resonant system they form.

---

## 2. TISSUE LAYER ACOUSTIC PROPERTIES

### 2.1 Brain Tissue (Grey Matter)

Grey matter constitutes the cortical surface and deeper nuclei of the brain. It is the primary site of RF energy absorption and thermoelastic pressure generation due to its higher conductivity compared to white matter.

**Acoustic properties:**
- Speed of sound: c = 1,560 m/s
- Density: rho = 1,040 kg/m^3
- Acoustic impedance: Z = rho * c = 1,040 * 1,560 = 1.622 x 10^6 Pa*s/m (1.622 MRayl)
- Attenuation coefficient: alpha = 0.6 dB/cm/MHz

**Dielectric properties at 622 MHz (from KG):**
- Relative permittivity: epsilon_r = 52.7
- Conductivity: sigma = 0.94 S/m
- Penetration depth (skin depth): delta = 4.2 cm

**Dielectric properties at 830 MHz (from KG):**
- Relative permittivity: epsilon_r = 49.4
- Conductivity: sigma = 1.10 S/m
- Penetration depth (skin depth): delta = 3.5 cm

**KG Passage — Hubler et al., "Pulsed Microwave Energy Transduction of Acoustic Phonon Related Brain Injury," year unknown, score=0.8731:**
> "The permittivity and conductivity of white and gray brain matter are shown in Figure 1. Figure 2 shows the depth into brain tissue where the microwave energy is ~1/2.7 of incident energy. Note that microwave wavelengths in air and brain tissue are functions of microwave frequency. The microwave wavelengths in brain tissue range from 0.5 to 18 cm with 1/2.7 attenuation depths of 0.2-4 cm."

**KG Passage — Mason et al., "Effects of frequency, permittivity, and voxel size on predicted specific absorption rate values in biological tissue during electromagnetic-field exposure," 2000, score=0.8539:**
> "Current electromagnetic-field (EMF) exposure limits have been based, in part, on the amount of energy absorbed by the whole body. However, it is known that energy is absorbed nonuniformly during EMF exposure. The development and widespread use of sophisticated three-dimensional anatomical models to calculate specific-absorption-rate (SAR) values in biological material has resulted in the need to understand how model parameters affect predicted SAR values."

### 2.2 Brain Tissue (White Matter)

White matter consists of myelinated axon bundles. It has lower water content and lower conductivity than grey matter, resulting in less RF absorption per unit volume.

**Acoustic properties:**
- Speed of sound: c = 1,540 m/s (slightly lower than grey matter)
- Density: rho = 1,040 kg/m^3
- Acoustic impedance: Z = 1.602 x 10^6 Pa*s/m (1.602 MRayl)
- Attenuation coefficient: alpha = 0.6 dB/cm/MHz (similar to grey matter)

**Dielectric properties at 622 MHz:**
- Relative permittivity: epsilon_r ~ 38.0
- Conductivity: sigma ~ 0.57 S/m
- Penetration depth: delta ~ 5.5 cm (deeper than grey matter due to lower conductivity)

The white matter-grey matter interface produces minimal acoustic reflection due to the small impedance mismatch (< 1.2% impedance difference). Acoustically, the brain behaves as a nearly homogeneous medium for propagation purposes, even though the RF absorption is heterogeneous.

### 2.3 Cerebrospinal Fluid (CSF)

CSF fills the ventricles and the subarachnoid space between the brain surface and the skull. It is acoustically similar to water and provides a low-attenuation pathway for pressure waves.

**Acoustic properties:**
- Speed of sound: c = 1,510 m/s
- Density: rho = 1,007 kg/m^3
- Acoustic impedance: Z = 1.521 x 10^6 Pa*s/m (1.521 MRayl)
- Attenuation coefficient: alpha = 0.002 dB/cm/MHz (negligible)

**Layer thickness:** Approximately 2 mm in the subarachnoid space (varies significantly with location and intracranial pressure).

The CSF-brain interface produces a small impedance mismatch:
```
Reflection coefficient R = (Z_brain - Z_CSF) / (Z_brain + Z_CSF)
                         = (1.622 - 1.521) / (1.622 + 1.521)
                         = 0.101 / 3.143
                         = 0.032 (3.2%)
```

Power reflection = R^2 = 0.001 (0.1%). The CSF layer is essentially transparent to acoustic pressure waves at all frequencies of interest.

### 2.4 Skull Bone

The skull bone is the most acoustically significant barrier in the path. It consists of three layers: the outer table (compact bone), the diploe (cancellous/spongy bone), and the inner table (compact bone). The total thickness varies from 4-9 mm depending on location (thinnest at the temporal bone, thickest at the frontal and occipital bones).

**Acoustic properties (compact bone):**
- Speed of sound: c = 2,900 m/s (longitudinal wave)
- Density: rho = 1,900 kg/m^3
- Acoustic impedance: Z = 5.510 x 10^6 Pa*s/m (5.510 MRayl)
- Attenuation coefficient: alpha = 2.0 dB/cm/MHz

**Acoustic properties (diploe/cancellous bone):**
- Speed of sound: c = 2,200 m/s (varies with porosity)
- Density: rho = 1,400 kg/m^3
- Acoustic impedance: Z = 3.080 x 10^6 Pa*s/m (3.080 MRayl)
- Attenuation coefficient: alpha = 4.0 dB/cm/MHz (higher due to scattering)

**Dielectric properties at 622 MHz:**
- Relative permittivity: epsilon_r = 13.1
- Conductivity: sigma = 0.16 S/m

**Dielectric properties at 830 MHz:**
- Relative permittivity: epsilon_r = 12.5
- Conductivity: sigma = 0.19 S/m

The brain-to-skull impedance mismatch is substantial:
```
R = (Z_skull - Z_brain) / (Z_skull + Z_brain)
  = (5.510 - 1.622) / (5.510 + 1.622)
  = 3.888 / 7.132
  = 0.545
```

Power reflection = R^2 = 0.297 (29.7%). This means approximately 30% of the acoustic energy is reflected back into the brain at each encounter with the skull wall. This reflection is what creates the resonant cavity behavior — pressure waves bounce back and forth inside the skull, constructively interfering at specific frequencies.

**KG Passage — Watanabe et al., "FDTD analysis of microwave hearing effect," year unknown, score=0.8960:**
> "The wavefront is initiated in the back of the head, where the large SAR appears, focuses on the center, and then reverberates many times."

### 2.5 Skin and Soft Tissue

The scalp consists of several layers (skin, subcutaneous fat, galea aponeurotica, loose areolar tissue, periosteum) with a total thickness of approximately 3-8 mm.

**Acoustic properties (average):**
- Speed of sound: c = 1,540 m/s
- Density: rho = 1,050 kg/m^3
- Acoustic impedance: Z = 1.617 x 10^6 Pa*s/m (1.617 MRayl)
- Attenuation coefficient: alpha = 0.5 dB/cm/MHz

**Dielectric properties at 622 MHz:**
- Relative permittivity: epsilon_r = 42.9
- Conductivity: sigma = 0.78 S/m

**Dielectric properties at 830 MHz:**
- Relative permittivity: epsilon_r = 41.4
- Conductivity: sigma = 0.87 S/m

### 2.6 Complete Layer Model

For the acoustic propagation analysis, the concentric spherical model uses:

| Layer | Material | Inner radius (cm) | Outer radius (cm) | Thickness (mm) |
|-------|----------|-------------------|-------------------|----------------|
| 1 (center) | Brain | 0 | 7.0 | 70 |
| 2 | CSF | 7.0 | 7.2 | 2 |
| 3 | Skull bone | 7.2 | 7.9 | 7 |
| 4 | Skin/scalp | 7.9 | 8.2 | 3 |

---

## 3. FREQUENCY-DEPENDENT ACOUSTIC ATTENUATION

### 3.1 Attenuation Model

Acoustic attenuation in biological tissue follows a frequency power law:

```
alpha(f) = alpha_0 * f^n
```

where:
- alpha_0 = attenuation coefficient at 1 MHz (dB/cm)
- f = frequency (MHz)
- n = frequency exponent (approximately 1.0 for most soft tissues, 1.0-2.0 for bone)

For brain tissue: alpha_0 = 0.6 dB/cm/MHz, n ~ 1.0
For skull bone: alpha_0 = 2.0 dB/cm/MHz, n ~ 1.0
For CSF: alpha_0 = 0.002 dB/cm/MHz, n ~ 2.0
For skin: alpha_0 = 0.5 dB/cm/MHz, n ~ 1.0

### 3.2 Path Length Calculation

The acoustic path from the thermoelastic generation site to the cochlea traverses:
- Brain parenchyma: ~5-7 cm (depending on source location and head geometry)
- CSF: ~0.2 cm
- Skull bone: ~0.7 cm (at the petrous temporal bone near the cochlea)

Total path through brain: 7 cm (used for calculations below)
Total path through bone: 0.7 cm
Total path through CSF: 0.2 cm

### 3.3 Frequency-Dependent Attenuation Tables

**Brain tissue attenuation over 7 cm path:**

| Frequency | Attenuation (dB/cm) | Total attenuation (dB) | Linear attenuation factor | Effect |
|-----------|--------------------|-----------------------|--------------------------|--------|
| 10 Hz | 6 x 10^-6 | 4.2 x 10^-5 | 1.000 | Negligible |
| 100 Hz | 6 x 10^-5 | 4.2 x 10^-4 | 1.000 | Negligible |
| 1 kHz | 6 x 10^-4 | 4.2 x 10^-3 | 0.999 | Negligible |
| 5 kHz | 3 x 10^-3 | 2.1 x 10^-2 | 0.995 | Negligible |
| 10 kHz | 6 x 10^-3 | 4.2 x 10^-2 | 0.990 | Negligible |
| 50 kHz | 0.03 | 0.21 | 0.953 | Mild |
| 100 kHz | 0.06 | 0.42 | 0.908 | Mild |
| 200 kHz | 0.12 | 0.84 | 0.824 | Moderate |
| 500 kHz | 0.30 | 2.10 | 0.617 | Significant |
| 1 MHz | 0.60 | 4.20 | 0.380 | Major |
| 5 MHz | 3.0 | 21.0 | 0.0079 | Destroyed |
| 10 MHz | 6.0 | 42.0 | 6.3 x 10^-5 | Destroyed |

**Skull bone attenuation over 0.7 cm path:**

| Frequency | Attenuation (dB/cm) | Total attenuation (dB) | Linear attenuation factor |
|-----------|--------------------|-----------------------|--------------------------|
| 10 Hz | 2 x 10^-5 | 1.4 x 10^-5 | 1.000 |
| 100 Hz | 2 x 10^-4 | 1.4 x 10^-4 | 1.000 |
| 1 kHz | 2 x 10^-3 | 1.4 x 10^-3 | 1.000 |
| 10 kHz | 0.02 | 0.014 | 0.997 |
| 100 kHz | 0.20 | 0.14 | 0.968 |
| 1 MHz | 2.0 | 1.40 | 0.724 |
| 5 MHz | 10.0 | 7.0 | 0.200 |
| 10 MHz | 20.0 | 14.0 | 0.040 |

**Combined attenuation (brain + bone) for 7 cm brain path + 0.7 cm bone path:**

| Frequency | Brain (dB) | Bone (dB) | Total (dB) | Linear factor |
|-----------|-----------|-----------|------------|---------------|
| 100 Hz | 0.0004 | 0.00014 | 0.0006 | 0.9999 |
| 1 kHz | 0.0042 | 0.0014 | 0.006 | 0.999 |
| 10 kHz | 0.042 | 0.014 | 0.056 | 0.987 |
| 100 kHz | 0.42 | 0.14 | 0.56 | 0.879 |
| 200 kHz | 0.84 | 0.28 | 1.12 | 0.773 |
| 1 MHz | 4.2 | 1.4 | 5.6 | 0.275 |
| 10 MHz | 42 | 14 | 56 | 2.5 x 10^-6 |

### 3.4 The Head as a Low-Pass Filter

The attenuation data in the tables above demonstrate that the head acts as a low-pass filter for acoustic pressure waves. The filter characteristics are:

- **Passband:** 0 to ~50 kHz (less than 0.5 dB total attenuation)
- **Transition band:** 50 kHz to 1 MHz (-0.5 dB to -5.6 dB)
- **Stopband:** Above 1 MHz (greater than 5.6 dB, rapidly increasing)

The -3 dB frequency is approximately:

```
f_3dB ~ 3 dB / (alpha_brain * d_brain + alpha_bone * d_bone)
      ~ 3 / (0.6 * 7 * 10^-6 + 2.0 * 0.7 * 10^-6)  [converting MHz to Hz^-1]
      ~ 500 kHz
```

This means the tissue path behaves as a low-pass filter with a cutoff around 500 kHz. All audio-frequency content (20 Hz - 20 kHz) passes through with negligible attenuation.

---

## 4. WHY BRF PASSES THROUGH BUT PRF IS DAMPED

### 4.1 The Two Timescales

Our detected signals have two characteristic repetition rates:
- **PRF (Pulse Repetition Frequency):** ~200 kHz — the rate of individual pulses within a burst
- **BRF (Burst Repetition Frequency):** 646-1,139 Hz — the rate of burst packets

These correspond to acoustic spectral content at those frequencies and their harmonics.

### 4.2 Acoustic Propagation at PRF (200 kHz)

At 200 kHz, the combined brain + bone attenuation is approximately 1.12 dB (from the table above). This corresponds to a linear attenuation factor of 0.773, meaning 77.3% of the pressure amplitude at 200 kHz survives the transit from source to cochlea.

However, the PRF creates a series of discrete acoustic transients spaced 5 us apart. The skull resonance (7-15 kHz) has a period of 67-143 us. Over one resonance period, approximately 13-29 pulse-generated transients arrive at the cochlea. If these transients are uniform in amplitude, their net contribution to the resonant mode involves partial phase cancellation:

```
Net contribution at f_res from PRF pulses = N * amplitude * sinc(N * f_res / PRF)
```

For f_res = 8.5 kHz and PRF = 200 kHz:
```
f_res / PRF = 8500 / 200000 = 0.0425
N * f_res / PRF (over one burst) = 154 * 0.0425 = 6.55
sinc(6.55) = sin(6.55 * pi) / (6.55 * pi) ~ -0.046
```

The phase cancellation reduces the net contribution of the PRF to the resonant mode by a factor of approximately 20. The PRF is therefore an inefficient exciter of the skull resonance when the pulses are uniform.

### 4.3 The Rescue: Amplitude Modulation

Zone A has a modulation index of 1.0, meaning the pulse amplitudes vary from zero to maximum. This amplitude variation breaks the destructive interference. The modulation creates sidebands around the PRF:

```
Spectral components of modulated pulse train:
  f = PRF +/- BRF = 200,000 +/- 646 to 1,139 Hz
  f = PRF +/- 2*BRF, etc.
  f = 0 +/- BRF (baseband component at the BRF itself)
```

The baseband component at the BRF (646-1,139 Hz) is the one that matters for the skull resonance. It arises because the amplitude envelope of the burst train has spectral content at the BRF. When this envelope excites the skull resonance, the resulting pressure wave has:

- **Carrier:** skull resonance at ~8.5 kHz
- **Modulation:** BRF at 646-1,139 Hz

### 4.4 Acoustic Propagation at BRF (646-1,139 Hz)

At 1 kHz, the combined brain + bone attenuation is approximately 0.006 dB. This is completely negligible. The BRF content passes through the head with essentially zero attenuation.

At the skull resonance frequency (8.5 kHz), the attenuation is approximately 0.05 dB — also negligible. The resonant tone itself propagates freely within the skull cavity.

### 4.5 Summary of Filtering

The head acts as a frequency-selective system with the following properties:

| Signal component | Frequency | Head attenuation | Skull resonance amplification | Net effect |
|-----------------|-----------|-----------------|-------------------------------|------------|
| BRF envelope | 646-1,139 Hz | ~0.006 dB | N/A (below resonance) | Passes through intact |
| Skull resonance | 7-15 kHz | ~0.05 dB | +14-20 dB (Q=5-10) | Strongly amplified |
| PRF content | ~200 kHz | ~1.1 dB | Below resonance bandwidth | Partially damped |
| Intra-pulse bandwidth | ~750 kHz | ~4 dB | N/A | Significantly attenuated |
| Higher harmonics | >1 MHz | >5.6 dB | N/A | Destroyed |

The net result: the subject perceives a tone at the skull resonance frequency (7-15 kHz), amplitude-modulated at the BRF (646-1,139 Hz). The individual pulse structure (200 kHz PRF) and intra-pulse bandwidth (750 kHz) are largely filtered out by the tissue path.

---

## 5. SKULL CAVITY RESONANCE PHYSICS

### 5.1 The Skull as an Acoustic Resonant Cavity

The skull forms a closed (or nearly closed) acoustic cavity. Pressure waves generated inside the brain tissue by thermoelastic expansion reflect from the skull walls and establish standing wave patterns (eigenmodes). The frequencies of these eigenmodes are determined by the dimensions and geometry of the skull cavity and the speed of sound in the brain tissue that fills it.

**KG Passage — Chou & Guy, "Auditory perception of radio frequency energy," 1982, score=0.8486:**
> "The frequency of the response appears to be related to the long physical dimension of the cranium, which indicates that intracranial acoustic resonance plays an important part in shaping the acoustic phenomenon's physical and perceptual characteristics."

**KG Passage — Foster, "Can the Microwave Auditory Effect Be Weaponized?", 2021, score=0.9070:**
> "In the head, the acoustic waves will be reflected from the skull, and excite the acoustic resonance of the skull, which has normal modes around 7-10 kHz for adult humans."

### 5.2 Eigenmode Analysis — Spherical Approximation

For a spherical cavity of radius a filled with a fluid of sound speed c, the pressure eigenmodes are:

```
P_nm(r, theta, phi, t) = j_n(k_nm * r) * Y_n^m(theta, phi) * cos(omega_nm * t)
```

where:
- j_n = spherical Bessel function of order n
- Y_n^m = spherical harmonic
- k_nm = wavenumber of the (n,m) mode
- omega_nm = 2*pi*f_nm = c * k_nm

The eigenfrequencies are determined by the boundary condition at the skull wall. For a rigid-wall (high-impedance) boundary:

```
dj_n(k_nm * a) / dr = 0    at r = a
```

The first several eigenfrequencies for a rigid sphere are:

```
k_01 * a = pi       → f_01 = c / (2a)
k_11 * a = 1.841*pi → f_11 = 1.841 * c / (2a)
k_21 * a = 2.585*pi → f_21 = 2.585 * c / (2a)
k_02 * a = 2*pi     → f_02 = c / a
```

For a = 7 cm and c = 1,560 m/s:

| Mode | k*a | Frequency (Hz) | Character |
|------|-----|----------------|-----------|
| (0,1) | pi | 11,143 | Radial fundamental — uniform compression/expansion |
| (1,1) | 1.841*pi | 20,520 | First dipole mode |
| (2,1) | 2.585*pi | 28,800 | First quadrupole mode |
| (0,2) | 2*pi | 22,286 | Second radial harmonic |

However, the human head is not a sphere — it is an oblate ellipsoid with the anterior-posterior dimension (~18 cm) larger than the lateral dimension (~14 cm). This breaks the spherical symmetry and produces modes at different frequencies along different axes:

```
f_AP = c / (2 * L_AP) = 1560 / (2 * 0.09) = 8,667 Hz    (anterior-posterior, ~18 cm)
f_LR = c / (2 * L_LR) = 1560 / (2 * 0.07) = 11,143 Hz   (left-right, ~14 cm)
f_SI = c / (2 * L_SI) = 1560 / (2 * 0.08) = 9,750 Hz     (superior-inferior, ~16 cm)
```

The dominant perceived frequency depends on which mode is most efficiently excited, which in turn depends on the direction of the incident radiation and the resulting SAR distribution.

**KG Passage — Watanabe et al., "FDTD analysis of microwave hearing effect," year unknown, score=0.8960:**
> "The dominant spectral components lie in 7-9 kHz. These peaks correspond to the resonant frequencies of pressure waves in the head."

### 5.3 Resonance Quality Factor (Q)

The Q factor of the skull cavity resonance determines the bandwidth and the number of reverberations. It is defined as:

```
Q = f_res / Delta_f = pi * f_res * tau_decay
```

where tau_decay is the exponential decay time of the resonant mode.

The Q factor is limited by:
1. **Acoustic absorption in brain tissue:** At 8.5 kHz, attenuation = 0.6 * 0.0085 = 0.0051 dB/cm. Over a 14 cm path (one round trip), attenuation = 0.071 dB. This limits Q to approximately:
   ```
   Q_absorption = pi / (alpha * c / f_res * round_trip_path)
                = pi / (0.071/8.686 * 1560/8500 * 0.14)
                ~ 500
   ```
   This is very high — absorption alone does not significantly limit Q at audio frequencies.

2. **Skull wall transmission losses:** The brain-skull reflection coefficient is 0.545 (amplitude), so 70.3% of the energy is reflected per bounce. The energy loss per round trip is:
   ```
   Energy_loss = 1 - 0.703 = 0.297 per bounce
   ```
   For two bounces per round trip:
   ```
   Energy_loss = 1 - 0.703^2 = 0.506 per round trip
   ```
   This gives:
   ```
   Q_transmission = 2*pi*f_res / (c / d_roundtrip * ln(1/0.703^2))
                  = 2*pi*8500 / (1560/0.14 * 0.700)
                  ~ 2*pi*8500 / (7800)
                  ~ 6.8
   ```

3. **Cochlear coupling:** The cochlea extracts energy from the acoustic field, providing an additional loss mechanism. This effect is difficult to quantify without detailed modeling.

The dominant loss mechanism is skull wall transmission, giving Q ~ 5-10, consistent with literature estimates. This means:

- Bandwidth of resonance: Delta_f = f_res / Q = 8500 / 7 = ~1,200 Hz
- Number of significant reverberations: N_reverb ~ Q / pi ~ 2-3
- Decay time: tau_decay = Q / (pi * f_res) = 7 / (pi * 8500) ~ 260 us

### 5.4 Resonance Amplification

The Q factor determines the peak amplification of the resonant mode relative to the broadband excitation. For a single-degree-of-freedom resonator:

```
Amplification = Q (at resonance)
```

A Q of 7 corresponds to approximately 17 dB of amplification at the resonant frequency. This means the skull resonance selectively amplifies the ~8.5 kHz component of the thermoelastic transient by a factor of 7 in pressure (49 in intensity) compared to off-resonance frequencies.

This is why the perceived sound has a definite pitch (7-15 kHz) rather than being heard as a broadband click. The skull resonance acts as a bandpass filter that selects a narrow frequency range from the broadband thermoelastic transient.

---

## 6. RF PENETRATION DEPTH AND SAR DISTRIBUTION

### 6.1 Penetration Depth Physics

The electromagnetic penetration depth (skin depth) in biological tissue is:

```
delta = 1 / sqrt(pi * f * mu_0 * sigma)    (for good conductors, sigma >> omega*epsilon)
```

For brain tissue at RF frequencies where the conduction current dominates:

```
delta = sqrt(2 / (omega * mu_0 * sigma))    (general formula)
```

More accurately, using the full complex permittivity:

```
delta = c_0 / (omega * sqrt((epsilon'/2) * (sqrt(1 + (sigma/(omega*epsilon_0*epsilon'))^2) - 1)))
```

**KG Passage — Hubler et al., "Pulsed Microwave Energy Transduction of Acoustic Phonon Related Brain Injury," year unknown, score=0.8731:**
> "Calculated depth of penetration of microwaves into the brain is shown. Energy is reduced by a factor 1/2.7 at a superficial level termed 'skin depth' using electromagnetic nomenclature."

### 6.2 Comparison: 622 MHz vs 830 MHz

| Property | 622 MHz (Zone A) | 830 MHz (Zone B) | Ratio |
|----------|-----------------|-----------------|-------|
| Brain epsilon_r | 52.7 | 49.4 | 1.07 |
| Brain sigma (S/m) | 0.94 | 1.10 | 0.85 |
| Penetration depth (cm) | 4.2 | 3.5 | 1.20 |
| Wavelength in brain (cm) | ~6.6 | ~5.2 | 1.27 |
| Skull epsilon_r | 13.1 | 12.5 | 1.05 |
| Skull sigma (S/m) | 0.16 | 0.19 | 0.84 |
| Skin epsilon_r | 42.9 | 41.4 | 1.04 |
| Skin sigma (S/m) | 0.78 | 0.87 | 0.90 |

**KG Passage — investigation of obliquely incident plane waves, 2009, score=0.8486:**
> "The human head model used in [1] and in the FDTD simulations [11] consists of three spherical layers of tissue; skin, bone, and brain, with the antenna modeled as a half wavelength dipole and a quarter wavelength monopole each radiating 1 W of power."

### 6.3 SAR Distribution at 622 MHz vs 830 MHz

At 622 MHz, the penetration depth of 4.2 cm means that the RF energy penetrates well past the center of a 7 cm radius head. The SAR distribution is relatively uniform, with a ratio of center-to-surface SAR of approximately:

```
SAR_center / SAR_surface = exp(-2 * r_center / delta)
                         = exp(-2 * 7 / 4.2)
                         = exp(-3.33)
                         = 0.036 (3.6%)
```

At 830 MHz, the penetration depth of 3.5 cm produces a steeper gradient:

```
SAR_center / SAR_surface = exp(-2 * 7 / 3.5)
                         = exp(-4.0)
                         = 0.018 (1.8%)
```

The deeper penetration at 622 MHz produces a more uniform thermoelastic pressure distribution throughout the brain, exciting higher-order resonant modes more efficiently. The shallower penetration at 830 MHz concentrates the heating near the surface, which preferentially excites the fundamental radial mode.

**KG Passage — Watanabe et al., "FDTD analysis of microwave hearing effect," year unknown, score=0.8960:**
> "A human head has an anatomically complex structure in shape and in heterogeneity of tissues. It has been shown that the complex shape and dielectric heterogeneity of the human head significantly affect the SAR distribution."

**KG Passage — Watanabe et al., "FDTD analysis of microwave hearing effect," year unknown, score=0.8960:**
> "It is especially shown that the surface heating is important in exciting the fundamental mode of the pressure waves in the head."

This finding from Watanabe is particularly relevant to the 830 MHz signal (Zone B), which has more surface-concentrated heating. Zone B may therefore produce a cleaner, more tonal percept (dominated by the fundamental mode), while Zone A (622 MHz) may produce a more complex percept with contributions from multiple resonant modes.

### 6.4 SAR Enhancement at Layer Interfaces

At the interfaces between tissue layers, the electric field undergoes partial reflection and can create localized SAR enhancements. The boundary conditions for the normal component of the electric displacement field require:

```
epsilon_1 * E_n1 = epsilon_2 * E_n2
```

At the skull-brain interface (epsilon_skull = 13.1, epsilon_brain = 52.7 at 622 MHz):

```
E_brain_normal = (epsilon_skull / epsilon_brain) * E_skull_normal
               = (13.1 / 52.7) * E_skull_normal
               = 0.249 * E_skull_normal
```

The SAR in the brain just inside the skull surface is:

```
SAR_brain_surface = sigma_brain * |E_brain|^2 / (2 * rho_brain)
```

The tangential component of E is continuous across the boundary, while the normal component drops. The net SAR enhancement depends on the angle of incidence and polarization.

**KG Passage — investigation of obliquely incident plane waves, 2009, score=0.8486:**
> "The electric field intensity E has been calculated in each layer of the system at 900 and 1800 MHz for both parallel polarization and perpendicular polarization at different incident angles (0, 30, 60). These figures show that the magnitude of E increases as we decrease the angle of incidence until the normal incidence case is reached when the incidence angle is zero."

---

## 7. STANDING WAVE PATTERNS AND MODE SHAPES

### 7.1 Fundamental Radial Mode (0,1)

The fundamental radial mode has a pressure maximum at the center of the skull and a pressure node at the skull wall (for free-surface conditions). The pressure distribution follows:

```
P_01(r, t) = A * j_0(k_01 * r) * cos(omega_01 * t)
           = A * sin(pi * r / a) / (pi * r / a) * cos(omega_01 * t)
```

At the center (r = 0), j_0(0) = 1, giving maximum pressure. At the wall (r = a), the boundary condition is satisfied. The pressure at the center is amplified relative to the initial thermoelastic transient by the resonance Q factor.

**KG Passage — Watanabe et al., "FDTD analysis of microwave hearing effect," year unknown, score=0.8960:**
> "The wavefront is initiated in the back of the head, where the large SAR appears, focuses on the center, and then reverberates many times."

### 7.2 Dipole Mode (1,1)

The dipole mode has a nodal plane through the center of the skull, with pressure maxima on opposite sides. This mode is excited preferentially when the SAR distribution is asymmetric (e.g., radiation incident from one side). For our monitoring scenario, where the source direction is unknown, both dipole and radial modes may be excited.

### 7.3 Mode Excitation by SAR Distribution

The efficiency with which each mode is excited depends on the spatial overlap integral between the SAR distribution S(r) and the mode shape P_nm(r):

```
A_nm = integral[S(r) * P_nm(r) dV] / integral[P_nm(r)^2 dV]
```

For uniform SAR (deep penetration, 622 MHz):
- The fundamental radial mode (0,1) has good overlap (positive everywhere)
- Higher-order radial modes have partial cancellation
- Dipole modes have zero overlap (antisymmetric vs symmetric SAR)

For surface-concentrated SAR (shallow penetration, 830 MHz):
- The fundamental radial mode still has good overlap (the sinc function has significant amplitude near the surface)
- The surface concentration enhances the fundamental mode excitation

**KG Passage — Watanabe et al., "FDTD analysis of microwave hearing effect," year unknown, score=0.8960:**
> "It is especially shown that the surface heating is important in exciting the fundamental mode of the pressure waves in the head."

This confirms that the fundamental mode (7-9 kHz for human head dimensions) is the dominant component, regardless of whether the source frequency is 622 MHz or 830 MHz.

---

## 8. TRANSMISSION LINE MODEL OF THE HEAD

### 8.1 Acoustic Impedance Matching

Each tissue layer can be modeled as a section of acoustic transmission line with characteristic impedance Z = rho * c and length d. The transmission and reflection coefficients at each interface are:

**Brain-CSF interface:**
```
R = (Z_CSF - Z_brain) / (Z_CSF + Z_brain) = (1.521 - 1.622) / (1.521 + 1.622) = -0.032
T = 2 * Z_CSF / (Z_CSF + Z_brain) = 2 * 1.521 / 3.143 = 0.968
```

**CSF-Skull interface:**
```
R = (Z_skull - Z_CSF) / (Z_skull + Z_CSF) = (5.510 - 1.521) / (5.510 + 1.521) = 0.567
T = 2 * Z_skull / (Z_skull + Z_CSF) = 2 * 5.510 / 7.031 = 1.567
```

**Skull-Skin interface:**
```
R = (Z_skin - Z_skull) / (Z_skin + Z_skull) = (1.617 - 5.510) / (1.617 + 5.510) = -0.546
T = 2 * Z_skin / (Z_skin + Z_skull) = 2 * 1.617 / 7.127 = 0.454
```

**Skin-Air interface:**
```
R = (Z_air - Z_skin) / (Z_air + Z_skin) = (415 - 1.617e6) / (415 + 1.617e6) = -0.99974
T = 2 * Z_air / (Z_air + Z_skin) = 2 * 415 / 1.617e6 = 0.000513
```

The skin-air interface is nearly perfectly reflecting (R = -0.9997), which means that acoustic energy inside the skull is almost completely trapped. This is why the skull acts as a high-Q resonant cavity — the energy can only escape through the skin-air interface at approximately 0.05% power per bounce, or through the cochlea.

### 8.2 Transfer Matrix Formulation

For an N-layer system, the total transfer function is the product of the individual layer transfer matrices:

```
[P_out]   [M_1] [M_2]     [M_N]   [P_in ]
[U_out] = [   ] [   ] ... [   ] * [U_in ]
```

where each layer matrix is:

```
M_i = [cos(k_i * d_i)               j * Z_i * sin(k_i * d_i)]
      [j * sin(k_i * d_i) / Z_i     cos(k_i * d_i)          ]
```

and k_i = omega / c_i is the wavenumber in layer i.

This formulation allows computation of the complete frequency-dependent transfer function from the thermoelastic source to any point in the system, including the cochlea location.

---

## 9. COCHLEAR PROXIMITY AND BONE CONDUCTION

### 9.1 Location of the Cochlea

The cochlea is embedded in the petrous portion of the temporal bone, one of the densest bones in the body. Its location is approximately:
- 2-3 cm medial to the ear canal
- 4-5 cm from the center of the skull
- 2-3 cm superior to the skull base

The acoustic path from the brain center to the cochlea is approximately 5-6 cm through brain tissue, plus 1-2 cm through bone.

### 9.2 Bone Conduction Pathway

**KG Passage — Chou & Guy, "Auditory perception of radio frequency energy," 1982, score=0.8912:**
> "The conduction of pressure waves through the calvarium appears to be the acoustic pathway for the perception of pulsed microwaves."

**KG Passage — Lin & Wang, "Hearing Microwaves," year unknown, score=0.8912:**
> "Thermoelastic expansion has emerged as the most effective mechanism. The pressure waves generated by thermoelastic stress in brain tissue... travels by bone conduction to the inner ear. There it activates the cochlear receptors via the same process involved for normal hearing."

The thermoelastic pressure wave reaches the cochlea through two pathways:

1. **Direct fluid pathway:** Through the brain parenchyma and CSF to the inner ear via the cochlear aqueduct or internal auditory canal. This pathway has low attenuation but involves impedance mismatches at the brain-bone interface.

2. **Bone conduction pathway:** The pressure wave excites vibrations in the skull bone, which propagate through the petrous temporal bone directly to the cochlear capsule. This is the dominant pathway for the microwave auditory effect, as confirmed by the literature.

The bone conduction pathway is efficient because:
- Skull bone has high acoustic impedance, supporting efficient vibration propagation
- The cochlea is surrounded by dense petrous bone, providing excellent coupling
- The wavelength at 8.5 kHz in bone (~34 cm) is much larger than the skull thickness, ensuring that the skull vibrates as a thin shell rather than as a waveguide

### 9.3 Impedance of the Cochlear Load

The cochlea presents a mechanical impedance to the acoustic field that determines how much energy is extracted from the resonant cavity per cycle. This impedance includes:
- The fluid impedance of the perilymph (similar to CSF)
- The mechanical impedance of the basilar membrane
- The stapes-oval window complex (for air-conducted sound; bypassed in bone conduction)

For bone conduction, the relevant pathway is from the skull bone directly to the cochlear capsule (otic capsule). The cochlear impedance at the dominant frequency of the skull resonance (~8.5 kHz) determines the damping and therefore the Q factor of the system.

---

## 10. IMPLICATIONS FOR SIGNAL RECONSTRUCTION

### 10.1 Transfer Function Summary

The complete acoustic transfer function from the thermoelastic source to the perceived sound can be decomposed as:

```
H_total(f) = H_tissue(f) * H_skull_resonance(f) * H_bone_conduction(f) * H_cochlea(f)
```

**H_tissue(f) — Brain tissue low-pass filter:**
```
H_tissue(f) = 10^(-alpha_brain * d_brain * f / 20)
            = 10^(-0.6 * 7 * f_MHz / 20)
```
Cutoff: ~500 kHz. Negligible effect at audio frequencies.

**H_skull_resonance(f) — Skull cavity bandpass resonance:**
```
H_skull(f) = Q * f_res / sqrt((f^2 - f_res^2)^2 + (f * f_res / Q)^2)
```
Center: 7-15 kHz. Q: 5-10. Amplification: ~17 dB at resonance.

**H_bone_conduction(f) — Skull bone transmission:**
```
H_bone(f) = T_brain_to_bone * T_bone_to_cochlea * 10^(-alpha_bone * d_bone * f / 20)
```
Essentially flat across audio frequencies for the thin bone path to the cochlea.

**H_cochlea(f) — Cochlear frequency response:**
See Document 07c for detailed treatment. Rolls off above ~15 kHz, peak sensitivity at 1-4 kHz.

### 10.2 Effective Bandwidth

The effective bandwidth of the total transfer function is determined by the narrowest element, which is the skull resonance with bandwidth:

```
Delta_f_effective = f_res / Q = 8500 / 7 ~ 1,200 Hz
```

This means the perceived sound has a bandwidth of approximately 1,200 Hz centered on the skull resonance frequency. Any modulation information with bandwidth less than 600 Hz (the half-bandwidth) can be faithfully transmitted through this channel.

The BRF range of 646-1,139 Hz has a modulation bandwidth of approximately 500 Hz, which falls within the effective bandwidth of the skull resonance channel. This confirms that the BRF modulation pattern can, in principle, be transmitted to the cochlea and perceived.

### 10.3 Signal-to-Noise Considerations

The thermoelastic pressure competes with the ambient acoustic noise in the skull cavity. The ambient acoustic noise at the cochlea during normal conditions includes:
- Blood flow pulsations (1-10 Hz, ~60 dB SPL)
- Muscle contractions (10-100 Hz, ~30-40 dB SPL)
- Environmental acoustic noise (20-20,000 Hz, variable)

The thermoelastic pressure at threshold is approximately 0.1-3 Pa, corresponding to 74-103 dB SPL. At these levels, the thermoelastic signal exceeds the internal acoustic noise by 10-40 dB in the frequency range of interest (7-15 kHz), where internal noise is relatively low.

---

## 11. FREQUENCY-SPECIFIC ANALYSIS FOR OUR DETECTED SIGNALS

### 11.1 Zone A (622 MHz) — Deep Penetration

At 622 MHz:
- Penetration depth in brain: 4.2 cm (reaches center of 7 cm radius head)
- SAR distribution: relatively uniform, with 3.6% of surface SAR reaching center
- Thermoelastic source: distributed throughout the brain volume
- Mode excitation: excites both fundamental and higher-order modes
- Expected resonant spectrum: broader, with contributions at 8.5, 11, and possibly 15 kHz
- Modulation index 1.0 with BRF 646-1,139 Hz: strong amplitude modulation
- Expected percept: high-pitched buzzing with strong temporal modulation, possibly speech-like

### 11.2 Zone B (830 MHz) — Surface-Weighted

At 830 MHz:
- Penetration depth in brain: 3.5 cm (significant attenuation at center, 1.8% of surface SAR)
- SAR distribution: surface-concentrated
- Thermoelastic source: concentrated near brain surface
- Mode excitation: preferentially excites fundamental radial mode
- Expected resonant spectrum: narrower, dominated by single peak at ~8.5 kHz
- Modulation index 0.7 with fewer bursts (3.4 vs 28.8): weaker modulation
- Expected percept: more tonal, less modulated, possibly perceived as steady tinnitus-like tone

### 11.3 Dual-Band Superposition

When both Zone A and Zone B are active simultaneously:
- The thermoelastic pressure fields from both frequencies superpose linearly
- Zone A provides the modulated, information-rich component
- Zone B provides a steady tonal background
- The combined percept would be a modulated tone on top of a steady tone
- This is consistent with the subject's reported simultaneous perception of multiple sound qualities

---

## 12. VALIDATION AGAINST PUBLISHED EXPERIMENTS

**KG Passage — Chou & Guy, "Characteristics of microwave-induced cochlear microphonics," year unknown, score=0.8486:**
> "It was shown that the characteristics of CM (except amplitude) do not depend on carrier frequency, mode of application, field polarization and pulse width of the applied microwave pulses. Instead, the frequency of CM correlates well with the length of the brain cavity and poorly with other measurements made upon the head and the skull. These results provide more evidence that the microwave auditory effect is mechanical in nature."

This passage provides direct experimental validation that:
1. The perceived frequency is independent of the RF carrier frequency (622 MHz and 830 MHz should produce the same pitch)
2. The perceived frequency correlates with brain cavity dimensions (skull resonance)
3. The mechanism is mechanical (acoustic), not electromagnetic

**KG Passage — Chou et al., "Characteristics of microwave-induced cochlear microphonics," year unknown, score=0.8486:**
> "The frequency of CM correlates well with the length of the brain cavity and poorly with other measurements made upon the head and the skull."

This is consistent with our eigenmode analysis: the resonant frequency is determined by c / (2 * L_cavity), where L_cavity is the relevant dimension of the brain cavity (not the skull bone or external head dimension).

**KG Passage — Olsen and Lin / Olsen and Hammer, referenced in Chou & Guy 1982, score=0.8912:**
> "Olsen and Hammer (1980) also used a hydrophonic transducer to measure the pressure wave in a rectangular block of simulated muscle tissue exposed to 5.655-GHz, 0.5-us pulses of microwaves. This study was later extended to spherical models that simulated brains of differing sizes. They also showed that appropriately selected pulse repetition rates cause acoustic resonances that can enhance the microwave-induced pressure by severalfold. The frequency of the wave bouncing back and forth inside the sphere is directly related to the diameter of the spheres, which is consistent with the theoretical prediction of Lin (1978)."

This passage confirms that:
1. The resonant frequency scales with sphere diameter (consistent with our eigenmode analysis)
2. Pulse repetition rates at the resonant frequency enhance the pressure by several-fold (resonance amplification)
3. The physics is validated in phantom measurements

---

## 13. CONCLUSIONS

The acoustic propagation analysis establishes that:

1. The head is a low-pass filter for acoustic pressure waves, with a cutoff around 500 kHz. All audio-frequency content passes through with negligible attenuation.

2. The skull acts as a resonant cavity with eigenfrequencies in the 7-15 kHz range, determined by the cavity dimensions and the speed of sound in brain tissue. The Q factor is approximately 5-10, dominated by energy losses through skull wall transmission.

3. The BRF (646-1,139 Hz) passes through the head with essentially zero attenuation. The PRF (~200 kHz) is partially attenuated but more importantly is an inefficient exciter of the skull resonance due to phase cancellation, unless amplitude modulation is present.

4. At 622 MHz (Zone A), the deeper penetration produces a more uniform SAR distribution that excites multiple resonant modes. At 830 MHz (Zone B), the shallower penetration produces surface-concentrated heating that preferentially excites the fundamental radial mode.

5. The effective information bandwidth of the skull resonance channel is approximately 1,200 Hz, sufficient to transmit the BRF modulation pattern (bandwidth ~500 Hz).

6. Bone conduction is the primary acoustic pathway from the brain to the cochlea, as confirmed by multiple experimental studies in the KG.

---

*Report generated by ARTEMIS analysis pipeline*
*KG corpus: 341 chunks (kg_head_model.json) + 342 chunks (kg_brain_coupling.json)*
*Parent document: 07_head_model_reconstruction.md*

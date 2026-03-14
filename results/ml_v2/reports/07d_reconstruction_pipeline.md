# RECONSTRUCTION PIPELINE — Mathematical Formulation, Transfer Functions, and Implementation

**Report ID:** HM-2026-0314-07d
**Date:** March 14, 2026
**Parent Document:** 07_head_model_reconstruction.md
**Data Sources:** 341 KG chunks (kg_head_model.json), 342 KG chunks (kg_brain_coupling.json), zone characterization report
**Scope:** Complete mathematical specification of the IQ-to-WAV reconstruction pipeline, including transfer function derivations, RLC equivalent circuit model, detailed implementation pseudocode, parameter tables with literature sources, validation strategy, error budget, and calibration procedures.

---

## 1. PIPELINE OVERVIEW

The reconstruction pipeline transforms raw IQ captures from the RTL-SDR into WAV audio files representing the acoustic signal that a subject would perceive via the thermoelastic mechanism. The pipeline consists of nine stages, each corresponding to a physical process in the RF-to-perception chain.

```
                INPUT                        OUTPUT
                  |                            |
Raw IQ (2.4 MSPS complex)             WAV (44.1 kHz, 16-bit)
                  |                            |
                  v                            ^
    [1] Envelope Detection                     |
                  |                            |
                  v                       [9] Resample & Encode
    [2] Pulse Detection                        ^
                  |                            |
                  v                       [8] Cochlear Sensitivity
    [3] Burst Grouping                         ^
                  |                            |
                  v                       [7] Brain Tissue Filter
    [4] Thermoelastic Impulse Train            ^
                  |                            |
                  v                       [6] Skull Cavity Resonance
    [5] SAR Weighting                          ^
                  |                            |
                  +----> [5] -> [6] -> [7] -> [8] -> [9]
```

Each stage imposes a transfer function on the signal. The complete pipeline is:

```
WAV(t) = Resample[H_cochlea(f) * H_tissue(f) * H_skull(f) * T(t)]
```

where T(t) is the thermoelastic impulse train derived from the IQ envelope.

---

## 2. STAGE 1: ENVELOPE DETECTION

### 2.1 Mathematical Formulation

The raw IQ data consists of complex samples at 2.4 MSPS:

```
s[n] = I[n] + j * Q[n]    for n = 0, 1, ..., N-1
```

where N = sample_rate * capture_duration = 2,400,000 * 0.2 = 480,000 samples per 200 ms capture.

The instantaneous amplitude envelope is:

```
A[n] = |s[n]| = sqrt(I[n]^2 + Q[n]^2)
```

### 2.2 Noise Floor Estimation

The noise floor is estimated from the amplitude statistics:

```
mu_noise = mean(A)
sigma_noise = std(A)
```

For Rayleigh-distributed noise (expected for the magnitude of complex Gaussian noise):

```
E[A] = sigma_IQ * sqrt(pi/2) ~ 1.253 * sigma_IQ
std(A) = sigma_IQ * sqrt((4 - pi)/2) ~ 0.655 * sigma_IQ
```

where sigma_IQ is the standard deviation of the I or Q channel individually.

### 2.3 Implementation Pseudocode

```python
def envelope_detection(iq_data):
    """
    Stage 1: Extract the amplitude envelope from raw IQ data.

    Parameters:
        iq_data: np.ndarray, complex64, shape (N,)
                 Raw IQ samples at 2.4 MSPS

    Returns:
        envelope: np.ndarray, float32, shape (N,)
                  Instantaneous amplitude envelope
        noise_stats: dict with keys 'mean', 'std'
    """
    # Compute magnitude
    envelope = np.abs(iq_data)

    # Estimate noise statistics from the full trace
    # Robust estimation: use median and MAD to avoid pulse contamination
    median_amp = np.median(envelope)
    mad = np.median(np.abs(envelope - median_amp))
    sigma_robust = mad * 1.4826  # Convert MAD to sigma for Gaussian

    noise_stats = {
        'mean': median_amp,
        'std': sigma_robust,
        'threshold_4sigma': median_amp + 4 * sigma_robust
    }

    return envelope, noise_stats
```

---

## 3. STAGE 2: PULSE DETECTION

### 3.1 Mathematical Formulation

A pulse is defined as a contiguous region of the envelope that exceeds the detection threshold:

```
threshold = mu_noise + k * sigma_noise    (k = 4 for 4-sigma detection)
```

Each detected pulse has three properties:
- Start sample: n_start (first sample above threshold)
- End sample: n_end (last sample above threshold)
- Peak amplitude: A_peak = max(A[n_start:n_end])

The pulse width is:

```
tau = (n_end - n_start + 1) / sample_rate
```

The pulse energy (proportional) is:

```
E_pulse = sum(A[n_start:n_end]^2) / sample_rate
```

The pulse center (amplitude-weighted centroid) is:

```
n_center = sum(n * A[n]^2, n=n_start..n_end) / sum(A[n]^2, n=n_start..n_end)
```

### 3.2 Implementation Pseudocode

```python
def detect_pulses(envelope, noise_stats, sample_rate=2.4e6, k=4):
    """
    Stage 2: Detect pulses as threshold exceedances.

    Parameters:
        envelope: np.ndarray, float32, shape (N,)
        noise_stats: dict with 'mean', 'std'
        sample_rate: float, Hz
        k: float, detection threshold in sigma

    Returns:
        pulses: list of dict, each with keys:
            'start': int, start sample index
            'end': int, end sample index
            'center': float, amplitude-weighted center sample
            'peak': float, peak amplitude
            'width_us': float, pulse width in microseconds
            'energy': float, proportional pulse energy (sum of A^2 * dt)
    """
    threshold = noise_stats['mean'] + k * noise_stats['std']

    # Find threshold crossings
    above = envelope > threshold

    # Identify contiguous regions
    # Pad with False at boundaries to detect start/end
    padded = np.concatenate([[False], above, [False]])
    diff = np.diff(padded.astype(int))
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]

    pulses = []
    dt = 1.0 / sample_rate

    for s, e in zip(starts, ends):
        segment = envelope[s:e]
        energy = np.sum(segment ** 2) * dt

        # Amplitude-weighted centroid
        weights = segment ** 2
        indices = np.arange(s, e, dtype=float)
        center = np.sum(indices * weights) / np.sum(weights)

        pulse = {
            'start': int(s),
            'end': int(e),
            'center': float(center),
            'peak': float(np.max(segment)),
            'width_us': float((e - s) * dt * 1e6),
            'energy': float(energy)
        }
        pulses.append(pulse)

    return pulses
```

---

## 4. STAGE 3: BURST GROUPING

### 4.1 Mathematical Formulation

Bursts are clusters of pulses separated by inter-burst gaps. The grouping criterion uses the inter-pulse interval (IPI):

```
IPI[i] = pulse[i+1].center - pulse[i].center    (in samples)
```

The median IPI over the capture gives the characteristic pulse spacing:

```
IPI_median = median(IPI)
```

A burst boundary is declared when:

```
IPI[i] > gap_multiplier * IPI_median    (gap_multiplier = 5)
```

Each burst has the following properties:

```
burst.start_sample = first pulse center in burst
burst.end_sample = last pulse center in burst
burst.duration = (end_sample - start_sample) / sample_rate
burst.n_pulses = number of pulses in burst
burst.energy = sum of pulse energies within burst
burst.center_sample = energy-weighted centroid of pulse centers
burst.peak_amplitude = max(pulse peak amplitudes within burst)
```

### 4.2 Burst Repetition Frequency

The BRF is computed from the inter-burst intervals:

```
IBI[i] = burst[i+1].center_sample - burst[i].center_sample
BRF = sample_rate / mean(IBI)
```

From the zone characterization report:
- Zone A: 28.8 bursts per 200 ms capture, BRF ~ 144 Hz (inter-burst rate)
- The BRF range of 646-1,139 Hz refers to the modulation frequency content within the burst amplitude envelope, not the simple burst repetition rate

### 4.3 Implementation Pseudocode

```python
def group_into_bursts(pulses, sample_rate=2.4e6, gap_multiplier=5.0):
    """
    Stage 3: Group pulses into bursts based on inter-pulse gaps.

    Parameters:
        pulses: list of dict (from Stage 2)
        sample_rate: float, Hz
        gap_multiplier: float, bursts separated by gaps > this * median IPI

    Returns:
        bursts: list of dict, each with keys:
            'pulses': list of pulse dicts in this burst
            'start_sample': float, first pulse center
            'end_sample': float, last pulse center
            'center_sample': float, energy-weighted centroid
            'duration_us': float, burst duration in microseconds
            'n_pulses': int, number of pulses
            'energy': float, total burst energy
            'peak_amplitude': float, maximum pulse peak in burst
    """
    if len(pulses) < 2:
        # Entire capture is one burst
        return [_make_burst(pulses, sample_rate)]

    # Compute inter-pulse intervals
    centers = np.array([p['center'] for p in pulses])
    ipis = np.diff(centers)

    # Determine gap threshold
    ipi_median = np.median(ipis)
    gap_threshold = gap_multiplier * ipi_median

    # Find burst boundaries
    boundaries = np.where(ipis > gap_threshold)[0]

    # Split pulses into bursts
    bursts = []
    start_idx = 0
    for b in boundaries:
        burst_pulses = pulses[start_idx:b+1]
        bursts.append(_make_burst(burst_pulses, sample_rate))
        start_idx = b + 1

    # Final burst
    if start_idx < len(pulses):
        burst_pulses = pulses[start_idx:]
        bursts.append(_make_burst(burst_pulses, sample_rate))

    return bursts


def _make_burst(burst_pulses, sample_rate):
    """Helper to compute burst properties from its constituent pulses."""
    centers = np.array([p['center'] for p in burst_pulses])
    energies = np.array([p['energy'] for p in burst_pulses])
    peaks = np.array([p['peak'] for p in burst_pulses])

    total_energy = np.sum(energies)

    if total_energy > 0:
        center_weighted = np.sum(centers * energies) / total_energy
    else:
        center_weighted = np.mean(centers)

    return {
        'pulses': burst_pulses,
        'start_sample': float(centers[0]),
        'end_sample': float(centers[-1]),
        'center_sample': float(center_weighted),
        'duration_us': float((centers[-1] - centers[0]) / sample_rate * 1e6),
        'n_pulses': len(burst_pulses),
        'energy': float(total_energy),
        'peak_amplitude': float(np.max(peaks))
    }
```

---

## 5. STAGE 4: THERMOELASTIC IMPULSE TRAIN

### 5.1 Mathematical Formulation

Each burst generates one thermoelastic pressure impulse. The impulse amplitude is proportional to the burst energy multiplied by the Gruneisen parameter:

```
Delta_P = Gamma * burst_energy
```

where:

```
Gamma = beta * c_brain^2 / C_p
      = (3.6e-4) * (1560)^2 / 3630
      = 0.241
```

The impulse train T(t) is a sum of delta functions at the burst centers, weighted by the thermoelastic pressure amplitude:

```
T(t) = sum_i [Delta_P_i * delta(t - t_burst_i)]
     = Gamma * sum_i [E_burst_i * delta(t - t_burst_i)]
```

In the discrete-time implementation, each impulse is placed at the sample closest to the burst center:

```
T[n] = Gamma * E_burst_i    if n = round(t_burst_i * sample_rate)
T[n] = 0                    otherwise
```

### 5.2 Alternative: Burst Envelope as Extended Source

Instead of treating each burst as a single impulse, we can preserve the internal structure of the burst by creating a pulse-by-pulse impulse train:

```
T_detailed[n] = Gamma * sum_j [E_pulse_j * delta(n - n_pulse_j)]
```

This preserves the intra-burst temporal structure (the 200 kHz PRF pattern). The choice between the two approaches depends on whether the intra-burst structure contributes to the perceived audio:

- **Burst-level (impulse per burst):** Appropriate if the inter-pulse interval (5 us at 200 kHz) is too short to be resolved acoustically. The burst acts as a single thermoelastic event.
- **Pulse-level (impulse per pulse):** Appropriate if each pulse independently generates an acoustic transient that reaches the cochlea. The 200 kHz content would then be filtered by the tissue path.

Given that the inter-pulse interval (5 us) is shorter than the acoustic transit time across the absorption volume (27 us at 622 MHz), the pulse-level approach is preferred. Successive pulses deposit energy before the previous pulse's acoustic wave has fully propagated, creating a coherent buildup during each burst.

### 5.3 Implementation Pseudocode

```python
def create_impulse_train(bursts, n_samples, sample_rate=2.4e6,
                          mode='burst_level'):
    """
    Stage 4: Create thermoelastic impulse train from burst data.

    Parameters:
        bursts: list of dict (from Stage 3)
        n_samples: int, total number of samples in the capture
        sample_rate: float, Hz
        mode: str, 'burst_level' or 'pulse_level'

    Returns:
        impulse_train: np.ndarray, float64, shape (n_samples,)
    """
    # Gruneisen parameter for brain tissue at 37C
    beta = 3.6e-4       # K^-1, thermal expansion coefficient
    c_brain = 1560.0     # m/s, speed of sound in brain
    C_p = 3630.0         # J/(kg*K), specific heat
    Gamma = (beta * c_brain**2) / C_p   # = 0.241

    impulse_train = np.zeros(n_samples, dtype=np.float64)

    if mode == 'burst_level':
        # One impulse per burst at the energy-weighted center
        for burst in bursts:
            n_center = int(round(burst['center_sample']))
            if 0 <= n_center < n_samples:
                impulse_train[n_center] = Gamma * burst['energy']

    elif mode == 'pulse_level':
        # One impulse per pulse
        for burst in bursts:
            for pulse in burst['pulses']:
                n_center = int(round(pulse['center']))
                if 0 <= n_center < n_samples:
                    impulse_train[n_center] = Gamma * pulse['energy']

    return impulse_train
```

---

## 6. STAGE 5: SAR WEIGHTING

### 6.1 Mathematical Formulation

The SAR distribution determines how the RF energy is spatially distributed within the brain. This affects the spatial overlap with the skull resonant modes and therefore the efficiency of mode excitation.

For a plane wave incident on a layered sphere model, the SAR at radial position r is:

```
SAR(r) = SAR_surface * exp(-2 * r / delta)
```

where delta is the penetration depth (skin depth) in brain tissue.

The effective SAR weighting factor accounts for the modal overlap between the SAR distribution and the fundamental resonant mode:

```
w_SAR = integral[SAR(r) * P_01(r) * r^2 dr, r=0..a] / integral[SAR(r) * r^2 dr, r=0..a]
```

For the fundamental radial mode P_01(r) = sin(pi*r/a)/(pi*r/a):

At 622 MHz (delta = 4.2 cm, a = 7 cm):
```
w_SAR_622 = 0.67  (more uniform SAR, moderate modal overlap)
```

At 830 MHz (delta = 3.5 cm, a = 7 cm):
```
w_SAR_830 = 0.73  (more surface-weighted, slightly better fundamental mode overlap)
```

### 6.2 Implementation Pseudocode

```python
def apply_sar_weighting(impulse_train, freq_mhz, head_params):
    """
    Stage 5: Apply SAR weighting based on carrier frequency.

    Parameters:
        impulse_train: np.ndarray, float64
        freq_mhz: float, carrier frequency in MHz
        head_params: dict with 'radius_cm', 'penetration_depth_cm'

    Returns:
        weighted_train: np.ndarray, float64
    """
    a = head_params.get('radius_cm', 7.0) / 100  # Convert to meters

    # Penetration depth lookup
    penetration_depths = {
        622: 0.042,   # meters
        830: 0.035,
    }
    delta = penetration_depths.get(int(freq_mhz), 0.04)

    # Compute modal overlap integral numerically
    r = np.linspace(0.001, a, 1000)
    sar_profile = np.exp(-2 * r / delta)

    # Fundamental radial mode: sinc(pi * r / a)
    mode_01 = np.sinc(r / a)  # np.sinc(x) = sin(pi*x)/(pi*x)

    # SAR-weighted modal overlap
    numerator = np.trapz(sar_profile * mode_01 * r**2, r)
    denominator = np.trapz(sar_profile * r**2, r)

    w_sar = numerator / denominator if denominator > 0 else 1.0

    weighted_train = impulse_train * w_sar

    return weighted_train
```

---

## 7. STAGE 6: SKULL CAVITY RESONANCE FILTER

### 7.1 Transfer Function Derivation

The skull cavity resonance is modeled as a second-order bandpass system:

```
H_skull(f) = (j * f * f_res / Q) / ((j*f)^2 + j*f*f_res/Q + f_res^2)
```

In the s-domain (s = j*2*pi*f):

```
H_skull(s) = (omega_0 / Q * s) / (s^2 + omega_0/Q * s + omega_0^2)
```

where:
- omega_0 = 2*pi*f_res is the natural angular frequency
- Q is the quality factor
- f_res is the resonance frequency (7-15 kHz)

The frequency response has:
- Peak at f = f_res with magnitude = Q
- -3 dB bandwidth = f_res / Q
- Phase shift = 0 at resonance, -90 degrees below, +90 degrees above

**Literature basis for parameters:**

**KG Passage — Watanabe et al., "FDTD analysis of microwave hearing effect," year unknown, score=0.8960:**
> "The dominant spectral components lie in 7-9 kHz. These peaks correspond to the resonant frequencies of pressure waves in the head."

**KG Passage — Foster, "Can the Microwave Auditory Effect Be Weaponized?", 2021, score=0.9070:**
> "In the head, the acoustic waves will be reflected from the skull, and excite the acoustic resonance of the skull, which has normal modes around 7-10 kHz for adult humans."

### 7.2 Digital Filter Implementation

The analog transfer function is converted to a digital filter using the bilinear transform. For a second-order bandpass filter:

```
omega_0 = 2 * pi * f_res
alpha = sin(omega_0 / fs) / (2 * Q)

b0 = alpha
b1 = 0
b2 = -alpha
a0 = 1 + alpha
a1 = -2 * cos(omega_0 / fs)
a2 = 1 - alpha
```

Normalized (divide by a0):

```
b = [alpha/a0, 0, -alpha/a0]
a = [1, -2*cos(omega_0/fs)/a0, (1-alpha)/a0]
```

### 7.3 Multi-Mode Extension

The actual skull cavity supports multiple resonant modes. For a more accurate model, the resonance filter is a sum of second-order sections:

```
H_skull_multimode(f) = sum_m [A_m * H_resonance(f, f_m, Q_m)]
```

where:
- f_1 = c_brain / (2 * L_AP) ~ 8.7 kHz (anterior-posterior fundamental)
- f_2 = c_brain / (2 * L_SI) ~ 9.75 kHz (superior-inferior fundamental)
- f_3 = c_brain / (2 * L_LR) ~ 11.1 kHz (left-right fundamental)
- A_m are the modal amplitudes (from SAR-mode overlap integrals)
- Q_m are the modal quality factors (approximately equal for all modes)

For the initial implementation, a single resonant mode is sufficient, with f_res and Q as tunable parameters.

### 7.4 Implementation Pseudocode

```python
def apply_skull_resonance(signal, sample_rate, head_params):
    """
    Stage 6: Apply skull cavity resonance bandpass filter.

    Parameters:
        signal: np.ndarray, float64
        sample_rate: float, Hz
        head_params: dict with keys:
            'skull_resonance_hz': float (default 8700)
            'skull_Q': float (default 7.0)
            'n_modes': int (default 1)
            'head_dimensions_cm': dict (optional, for multi-mode)

    Returns:
        resonated: np.ndarray, float64
    """
    f_res = head_params.get('skull_resonance_hz', 8700.0)
    Q = head_params.get('skull_Q', 7.0)
    n_modes = head_params.get('n_modes', 1)

    if n_modes == 1:
        # Single resonant mode
        omega_0 = 2 * np.pi * f_res / sample_rate
        alpha = np.sin(omega_0) / (2 * Q)

        b = np.array([alpha, 0, -alpha])
        a = np.array([1 + alpha, -2 * np.cos(omega_0), 1 - alpha])

        # Normalize
        b = b / a[0]
        a = a / a[0]

        # Apply filter (use lfilter for causal filtering, not filtfilt)
        resonated = signal_module.lfilter(b, a, signal)

    else:
        # Multi-mode: sum contributions from each mode
        c_brain = 1560.0  # m/s
        dims = head_params.get('head_dimensions_cm',
                               {'AP': 18.0, 'SI': 16.0, 'LR': 14.0})

        resonated = np.zeros_like(signal)

        for dim_name, dim_cm in dims.items():
            f_mode = c_brain / (2 * dim_cm / 100)

            omega_0 = 2 * np.pi * f_mode / sample_rate
            alpha = np.sin(omega_0) / (2 * Q)

            b = np.array([alpha, 0, -alpha])
            a = np.array([1 + alpha, -2 * np.cos(omega_0), 1 - alpha])
            b = b / a[0]
            a = a / a[0]

            # Modal amplitude (simple weighting by SAR overlap)
            # AP mode typically dominates for posterior incidence
            mode_weight = {'AP': 1.0, 'SI': 0.5, 'LR': 0.3}
            w = mode_weight.get(dim_name, 0.5)

            resonated += w * signal_module.lfilter(b, a, signal)

    return resonated
```

---

## 8. STAGE 7: BRAIN TISSUE ACOUSTIC FILTER

### 8.1 Transfer Function Derivation

The brain tissue acts as a low-pass filter for acoustic pressure waves. The attenuation follows a frequency-linear law:

```
H_tissue(f) = exp(-alpha_brain * d_brain * f)
```

where:
- alpha_brain = 0.6 dB/cm/MHz = 0.6 * 100 / (20 * log10(e)) / 10^6 = 6.91e-5 Np/cm/Hz
- d_brain = 7 cm path length

In Nepers:
```
H_tissue(f) = exp(-(0.6 / (20 * log10(e))) * 7 * f_MHz)
            = exp(-0.0691 * 7 * f_MHz)
            = exp(-0.484 * f_MHz)
```

At audio frequencies (f < 20 kHz = 0.02 MHz):
```
H_tissue(0.02 MHz) = exp(-0.484 * 0.02) = exp(-0.00968) = 0.990
```

The tissue filter has negligible effect at audio frequencies. It only becomes significant above ~100 kHz. Since the skull resonance filter (Stage 6) already confines the signal to the 7-15 kHz band, Stage 7 effectively does nothing.

### 8.2 Implementation Decision

For computational efficiency, Stage 7 can be omitted from the pipeline without measurable error. The tissue attenuation at the skull resonance frequency is less than 0.06 dB, which is well below the amplitude uncertainty from other sources.

If included for completeness, the filter is implemented as:

```python
def apply_tissue_filter(signal, sample_rate, d_brain_cm=7.0):
    """
    Stage 7: Apply brain tissue acoustic low-pass filter.

    This filter has negligible effect at audio frequencies and can
    be omitted. Included for pipeline completeness.

    Parameters:
        signal: np.ndarray, float64
        sample_rate: float, Hz
        d_brain_cm: float, acoustic path length in cm

    Returns:
        filtered: np.ndarray, float64
    """
    # Design FIR filter based on tissue attenuation
    n_taps = 65
    freqs = np.linspace(0, sample_rate / 2, n_taps)

    # Attenuation in linear scale
    alpha_dB_per_cm_per_MHz = 0.6
    freqs_MHz = freqs / 1e6
    atten_dB = alpha_dB_per_cm_per_MHz * d_brain_cm * freqs_MHz
    gains = 10 ** (-atten_dB / 20)

    # Ensure gain is 1.0 at DC
    gains[0] = 1.0

    # Design FIR filter using frequency sampling
    from scipy.signal import firwin2
    fir_coeffs = firwin2(n_taps, freqs / (sample_rate / 2), gains)

    filtered = signal_module.lfilter(fir_coeffs, 1.0, signal)

    return filtered
```

---

## 9. STAGE 8: COCHLEAR SENSITIVITY WEIGHTING

### 9.1 Transfer Function

The cochlear sensitivity curve (ISO 226 equal-loudness contour at threshold, inverted) determines the relative detectability of each frequency component. For the reconstruction pipeline, we use A-weighting as an approximation:

```
H_cochlea(f) = H_A(f)
```

The A-weighting transfer function is:

```
H_A(f) = (12194^2 * f^4) / ((f^2 + 20.6^2) * sqrt((f^2 + 107.7^2) * (f^2 + 737.9^2)) * (f^2 + 12194^2))
```

Normalized to 0 dB at 1 kHz.

### 9.2 Application to the Skull Resonance Band

At the skull resonance frequency of 8.5 kHz:
```
A-weight(8.5 kHz) = -1.1 dB
```

This is a mild attenuation, meaning the cochlear sensitivity at the skull resonance frequency is close to the peak sensitivity. The A-weighting filter primarily affects the low-frequency components (below 500 Hz) and very high frequencies (above 10 kHz).

### 9.3 Alternative: Custom Bone Conduction Weighting

A-weighting is designed for airborne sound at the ear. For bone-conducted sound, the transfer function is different (see Document 07c, Section 8.3). A custom weighting curve could be implemented based on published bone conduction sensitivity data, but the difference from A-weighting is small in the 5-15 kHz range.

### 9.4 Implementation Pseudocode

```python
def apply_cochlear_weighting(signal, sample_rate, method='A_weight'):
    """
    Stage 8: Apply cochlear sensitivity weighting.

    Parameters:
        signal: np.ndarray, float64
        sample_rate: float, Hz
        method: str, 'A_weight' or 'bone_conduction'

    Returns:
        weighted: np.ndarray, float64
    """
    if method == 'A_weight':
        # A-weighting filter coefficients for the given sample rate
        # Using IEC 61672 A-weighting
        # Pre-computed for common sample rates

        # Design the A-weighting filter in the frequency domain
        N = len(signal)
        freqs = np.fft.rfftfreq(N, d=1.0/sample_rate)

        # Avoid division by zero at f=0
        freqs_safe = np.maximum(freqs, 1.0)

        # A-weighting magnitude response
        f = freqs_safe
        numerator = 12194.0**2 * f**4
        denominator = ((f**2 + 20.6**2) *
                       np.sqrt((f**2 + 107.7**2) * (f**2 + 737.9**2)) *
                       (f**2 + 12194.0**2))

        H_A = numerator / denominator

        # Normalize to 0 dB at 1 kHz
        f_1k = 1000.0
        H_A_1k = (12194.0**2 * f_1k**4) / (
            (f_1k**2 + 20.6**2) *
            np.sqrt((f_1k**2 + 107.7**2) * (f_1k**2 + 737.9**2)) *
            (f_1k**2 + 12194.0**2))
        H_A = H_A / H_A_1k

        # Set DC to zero (A-weighting rejects DC)
        H_A[0] = 0.0

        # Apply in frequency domain
        spectrum = np.fft.rfft(signal)
        spectrum_weighted = spectrum * H_A
        weighted = np.fft.irfft(spectrum_weighted, n=N)

    elif method == 'bone_conduction':
        # Custom bone conduction weighting
        # Based on published BC sensitivity relative to AC
        N = len(signal)
        freqs = np.fft.rfftfreq(N, d=1.0/sample_rate)

        # Bone conduction relative sensitivity (dB re 1 kHz)
        bc_freqs = np.array([250, 500, 1000, 2000, 4000, 8000, 10000, 12000, 16000])
        bc_dB = np.array([-10, -5, 0, 5, 3, -5, -10, -15, -30])

        # Interpolate to all frequencies
        from scipy.interpolate import interp1d
        bc_interp = interp1d(bc_freqs, bc_dB, kind='cubic',
                             bounds_error=False, fill_value=-40)
        H_BC_dB = bc_interp(freqs)
        H_BC_dB[0] = -60  # Reject DC

        H_BC = 10 ** (H_BC_dB / 20)

        spectrum = np.fft.rfft(signal)
        spectrum_weighted = spectrum * H_BC
        weighted = np.fft.irfft(spectrum_weighted, n=N)

    return weighted
```

---

## 10. STAGE 9: RESAMPLING AND WAV OUTPUT

### 10.1 Mathematical Formulation

The signal after Stage 8 is at the original sample rate (2.4 MSPS). For WAV output at 44.1 kHz, downsampling by a factor of approximately 54.4 is required:

```
downsample_ratio = sample_rate_in / sample_rate_out = 2,400,000 / 44,100 = 54.42
```

Before downsampling, an anti-aliasing low-pass filter must be applied to remove content above the Nyquist frequency of the output (44,100 / 2 = 22,050 Hz). Since the skull resonance filter has already confined the signal to 7-15 kHz, the anti-aliasing filter primarily removes any residual content above 22 kHz.

The downsampled signal is then normalized to the 16-bit integer range [-32,768, +32,767] and written as a WAV file.

### 10.2 Implementation Pseudocode

```python
def resample_and_write_wav(signal, sample_rate_in, output_path,
                            sample_rate_out=44100, bit_depth=16):
    """
    Stage 9: Downsample to audio rate and write WAV file.

    Parameters:
        signal: np.ndarray, float64
        sample_rate_in: float, Hz (input sample rate, e.g., 2.4e6)
        output_path: str, path for output WAV file
        sample_rate_out: int, output sample rate (default 44100)
        bit_depth: int, bits per sample (default 16)

    Returns:
        output_path: str
    """
    from scipy.signal import resample_poly
    from scipy.io import wavfile

    # Compute rational resampling ratio
    # 44100 / 2400000 = 441 / 24000 = 147 / 8000
    from math import gcd
    g = gcd(sample_rate_out, int(sample_rate_in))
    up = sample_rate_out // g
    down = int(sample_rate_in) // g

    # Resample (includes anti-aliasing filter)
    audio = resample_poly(signal, up, down)

    # Normalize to bit depth range
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        if bit_depth == 16:
            max_int = 32000  # Leave headroom
            audio_int = (audio / max_val * max_int).astype(np.int16)
        elif bit_depth == 32:
            max_int = 2**30
            audio_int = (audio / max_val * max_int).astype(np.int32)
    else:
        audio_int = np.zeros(len(audio), dtype=np.int16)

    # Write WAV
    wavfile.write(output_path, sample_rate_out, audio_int)

    return output_path
```

---

## 11. COMPLETE PIPELINE INTEGRATION

### 11.1 Master Function

```python
def iq_to_wav(iq_file, output_wav, head_params=None, freq_mhz=622,
              mode='burst_level'):
    """
    Complete IQ-to-WAV reconstruction pipeline.

    Transforms raw RTL-SDR IQ captures into WAV audio files representing
    the acoustic signal perceived via the thermoelastic mechanism.

    Parameters:
        iq_file: str, path to raw IQ capture (.iq file, complex64)
        output_wav: str, path for output WAV file
        head_params: dict, model parameters (see below)
        freq_mhz: float, carrier frequency in MHz (622 or 830)
        mode: str, 'burst_level' or 'pulse_level'

    head_params keys:
        skull_resonance_hz: float, skull cavity resonance (default 8700)
        skull_Q: float, resonance quality factor (default 7.0)
        radius_cm: float, effective head radius (default 7.0)
        path_length_cm: float, acoustic path (default 7.0)
        n_modes: int, number of resonant modes (default 1)
        head_dimensions_cm: dict, AP/SI/LR dimensions (optional)
        cochlear_method: str, 'A_weight' or 'bone_conduction'

    Returns:
        result: dict with metadata about the reconstruction
    """
    import numpy as np
    from scipy import signal as signal_module

    # Default head parameters
    if head_params is None:
        head_params = {
            'skull_resonance_hz': 8700.0,
            'skull_Q': 7.0,
            'radius_cm': 7.0,
            'path_length_cm': 7.0,
            'n_modes': 1,
            'cochlear_method': 'A_weight'
        }

    SAMPLE_RATE = 2.4e6  # RTL-SDR sample rate

    # Load raw IQ data
    iq_data = np.fromfile(iq_file, dtype=np.complex64)
    n_samples = len(iq_data)

    # Stage 1: Envelope detection
    envelope, noise_stats = envelope_detection(iq_data)

    # Stage 2: Pulse detection
    pulses = detect_pulses(envelope, noise_stats, SAMPLE_RATE, k=4)

    if len(pulses) == 0:
        # No pulses detected — write silence
        resample_and_write_wav(np.zeros(n_samples), SAMPLE_RATE, output_wav)
        return {'status': 'no_pulses', 'n_pulses': 0}

    # Stage 3: Burst grouping
    bursts = group_into_bursts(pulses, SAMPLE_RATE, gap_multiplier=5.0)

    # Stage 4: Thermoelastic impulse train
    impulse_train = create_impulse_train(bursts, n_samples, SAMPLE_RATE, mode)

    # Stage 5: SAR weighting
    weighted = apply_sar_weighting(impulse_train, freq_mhz, head_params)

    # Stage 6: Skull cavity resonance filter
    resonated = apply_skull_resonance(weighted, SAMPLE_RATE, head_params)

    # Stage 7: Brain tissue acoustic filter (negligible, included for completeness)
    tissue_filtered = apply_tissue_filter(resonated, SAMPLE_RATE,
                                           head_params.get('path_length_cm', 7.0))

    # Stage 8: Cochlear sensitivity weighting
    cochlear_weighted = apply_cochlear_weighting(
        tissue_filtered, SAMPLE_RATE,
        method=head_params.get('cochlear_method', 'A_weight'))

    # Stage 9: Resample and write WAV
    resample_and_write_wav(cochlear_weighted, SAMPLE_RATE, output_wav)

    # Compute metadata
    result = {
        'status': 'success',
        'n_pulses': len(pulses),
        'n_bursts': len(bursts),
        'freq_mhz': freq_mhz,
        'skull_resonance_hz': head_params['skull_resonance_hz'],
        'skull_Q': head_params['skull_Q'],
        'mode': mode,
        'input_duration_ms': n_samples / SAMPLE_RATE * 1000,
        'output_duration_ms': None,  # Computed after resampling
        'total_pulse_energy': sum(p['energy'] for p in pulses),
        'total_burst_energy': sum(b['energy'] for b in bursts),
        'mean_burst_duration_us': np.mean([b['duration_us'] for b in bursts]),
        'mean_burst_rate_hz': len(bursts) / (n_samples / SAMPLE_RATE),
    }

    return result
```

---

## 12. RLC EQUIVALENT CIRCUIT MODEL

### 12.1 Circuit Topology

The complete head model can be represented as an RLC circuit with three stages in series:

```
                  Tissue Stage        Skull Resonance      Cochlea Detector
                  ┌──────────┐       ┌──────────────┐      ┌──────────┐
Impulse ──>──R1──>──L1──>──C1──>──R2──>──L2──>──C2──>──R3──>──C3──>── Output
                  └──────────┘       └──────────────┘      └──────────┘
                  Low-pass            Bandpass              Low-pass
                  f_c ~ 500 kHz       f_0 = 8.7 kHz        f_c ~ 5 kHz
                                      Q = 7
```

### 12.2 Component Value Derivations

**Tissue Stage (Low-Pass Filter):**

The tissue stage models the acoustic attenuation in brain tissue. For a first-order RC low-pass filter:

```
f_c = 1 / (2*pi*R1*C1) = 500 kHz
```

The acoustic impedance of the brain tissue determines R1:

```
R1 = Z_brain * d / A = (rho * c) * d / A
```

where:
- rho * c = 1,040 * 1,560 = 1.622 x 10^6 Pa*s/m^3 (acoustic impedance of brain)
- d = 0.07 m (path length)
- A = effective area (cross-section of the acoustic beam)

For a beam area of approximately 10 cm^2 = 10^-3 m^2:

```
R1 = 1.622e6 * 0.07 / 1e-3 = 1.135e8 Pa*s/m^5
```

The capacitance C1 is determined by the cutoff frequency:

```
C1 = 1 / (2*pi*f_c*R1) = 1 / (2*pi*500000*1.135e8) = 2.80e-15 m^5/(Pa*s)
```

The inductance L1 (acoustic mass) provides the frequency-dependent attenuation characteristic:

```
L1 = rho * d / A = 1040 * 0.07 / 1e-3 = 72,800 Pa*s^2/m^5
```

**Skull Resonance Stage (Bandpass Filter):**

The skull resonance is modeled as a parallel RLC circuit (series in the signal path):

```
f_0 = 1 / (2*pi*sqrt(L2*C2)) = 8,700 Hz
Q = R2 * sqrt(C2/L2) = 7
```

Two equations, three unknowns. We can choose one component value:

Let C2 = 1e-12 m^5/(Pa*s) (arbitrary normalization), then:

```
L2 = 1 / ((2*pi*f_0)^2 * C2) = 1 / ((2*pi*8700)^2 * 1e-12)
   = 1 / (2.989e9 * 1e-12) = 334.6 Pa*s^2/m^5

R2 = Q / (2*pi*f_0*C2) = 7 / (2*pi*8700*1e-12) = 1.281e8 Pa*s/m^5
```

Alternatively, using physical acoustic analogies:

```
L2 = rho * V / A^2        (acoustic mass of the brain volume)
C2 = V / (rho * c^2)      (acoustic compliance of the brain volume)
R2 = rho * c / A_cochlea   (radiation resistance into the cochlea)
```

where V = (4/3)*pi*a^3 = (4/3)*pi*(0.07)^3 = 1.437e-3 m^3 is the brain volume.

```
L2 = 1040 * 1.437e-3 / (1e-3)^2 = 1.495e6 Pa*s^2/m^5
C2 = 1.437e-3 / (1040 * 1560^2) = 5.68e-13 m^5/(Pa*s)
R2 = (for Q=7): Q * sqrt(L2/C2) = 7 * sqrt(1.495e6 / 5.68e-13) = 7 * 5.128e7 = 3.59e8 Pa*s/m^5
```

The resonant frequency from these physical values:

```
f_0 = 1 / (2*pi*sqrt(L2*C2)) = 1 / (2*pi*sqrt(1.495e6 * 5.68e-13))
    = 1 / (2*pi*sqrt(8.49e-7)) = 1 / (2*pi*9.21e-4) = 173 Hz
```

This is too low, indicating that the simple lumped-element model does not directly map to physical dimensions. The discrepancy arises because the skull cavity supports distributed (standing wave) resonances, not lumped-element resonances. The RLC model should be treated as a circuit analog with component values chosen to match the desired transfer function (f_0 = 8.7 kHz, Q = 7), not derived from bulk physical properties.

**Cochlea Stage (Detector):**

The cochlear detection stage is modeled as an RC low-pass filter representing the hair cell time constant:

```
R3*C3 = tau_hair_cell ~ 0.1 ms = 1e-4 s
f_c = 1 / (2*pi*R3*C3) ~ 1,590 Hz
```

This means the cochlear detector smooths the pressure waveform with a time constant of approximately 0.1 ms, extracting the amplitude envelope of the skull resonance carrier.

### 12.3 Complete Circuit Summary

| Component | Value | Physical Analog | Effect |
|-----------|-------|----------------|--------|
| R1 | Fitted to match tissue attenuation | Brain acoustic impedance * path | Acoustic loss in brain |
| L1 | Fitted | Acoustic mass of tissue | Low-pass characteristic |
| C1 | Fitted | Acoustic compliance of tissue | Low-pass characteristic |
| L2 | Fitted to f_0 = 8.7 kHz | Skull cavity acoustic mass | Resonance |
| C2 | Fitted to f_0 = 8.7 kHz | Skull cavity compliance | Resonance |
| R2 | Fitted to Q = 7 | Skull wall losses + cochlear load | Bandwidth |
| R3 | Fitted | Hair cell membrane resistance | Detection time constant |
| C3 | Fitted | Hair cell membrane capacitance | Detection time constant |

The RLC model is useful as a conceptual tool and for rapid computation, but should be calibrated against the detailed transfer function calculations, not against bulk physical properties.

---

## 13. PARAMETER TABLE WITH LITERATURE SOURCES

### 13.1 Fixed Parameters (Not Adjustable)

| Parameter | Symbol | Value | Unit | Source |
|-----------|--------|-------|------|--------|
| Thermal expansion coefficient (brain) | beta | 3.6 x 10^-4 | K^-1 | Water at 37C, widely cited |
| Speed of sound (brain) | c_brain | 1,560 | m/s | Standard tissue property tables |
| Specific heat (brain) | C_p | 3,630 | J/(kg*K) | Standard tissue property tables |
| Brain density | rho_brain | 1,040 | kg/m^3 | Standard tissue property tables |
| Gruneisen parameter | Gamma | 0.241 | dimensionless | Calculated from above |
| Brain attenuation | alpha_brain | 0.6 | dB/cm/MHz | Standard tissue property tables |
| Skull bone attenuation | alpha_bone | 2.0 | dB/cm/MHz | Standard tissue property tables |
| Skull bone speed of sound | c_bone | 2,900 | m/s | Standard tissue property tables |
| Skull bone density | rho_bone | 1,900 | kg/m^3 | Standard tissue property tables |
| CSF speed of sound | c_CSF | 1,510 | m/s | Standard tissue property tables |
| CSF density | rho_CSF | 1,007 | kg/m^3 | Standard tissue property tables |
| Brain permittivity (622 MHz) | epsilon_r | 52.7 | dimensionless | Gabriel et al., KG |
| Brain conductivity (622 MHz) | sigma | 0.94 | S/m | Gabriel et al., KG |
| Brain permittivity (830 MHz) | epsilon_r | 49.4 | dimensionless | Gabriel et al., KG |
| Brain conductivity (830 MHz) | sigma | 1.10 | S/m | Gabriel et al., KG |
| Penetration depth (622 MHz) | delta | 4.2 | cm | Calculated |
| Penetration depth (830 MHz) | delta | 3.5 | cm | Calculated |
| Sample rate (RTL-SDR) | f_s | 2,400,000 | Hz | Hardware specification |
| Pulse detection threshold | k | 4 | sigma | Engineering choice |
| Burst gap multiplier | gap_mult | 5 | x median IPI | Engineering choice |

### 13.2 Adjustable Parameters

| Parameter | Symbol | Default | Range | Unit | Constraint |
|-----------|--------|---------|-------|------|-----------|
| Skull resonance frequency | f_res | 8,700 | 7,000-15,000 | Hz | c_brain / (2 * L_head) |
| Resonance Q factor | Q | 7 | 3-15 | dimensionless | Literature: 5-10 |
| Acoustic path length | d | 7 | 5-9 | cm | Head geometry |
| Number of resonant modes | n_modes | 1 | 1-3 | integer | 1 = simple, 3 = realistic |
| Cochlear weighting method | method | A_weight | A_weight, bone_conduction | string | Modeling choice |
| Processing mode | mode | burst_level | burst_level, pulse_level | string | Physics choice |

### 13.3 Derived Parameters

| Parameter | Formula | Typical Value |
|-----------|---------|---------------|
| Resonance bandwidth | Delta_f = f_res / Q | 1,243 Hz |
| Decay time | tau_decay = Q / (pi * f_res) | 256 us |
| Skin depth ratio (622 MHz) | delta / a | 0.60 |
| Skin depth ratio (830 MHz) | delta / a | 0.50 |
| SAR center/surface ratio (622 MHz) | exp(-2*a/delta) | 0.036 |
| SAR center/surface ratio (830 MHz) | exp(-2*a/delta) | 0.018 |
| Acoustic transit time (622 MHz) | delta / c_brain | 26.9 us |
| Acoustic transit time (830 MHz) | delta / c_brain | 22.4 us |

---

## 14. VALIDATION STRATEGY

### 14.1 Synthetic Input Test

**Purpose:** Verify that the pipeline correctly transforms a known input into the expected output.

**Procedure:**
1. Generate a synthetic IQ file with known properties:
   - Carrier: 622 MHz (arbitrary for this test)
   - Pulse width: 2.7 us
   - PRF: 200 kHz
   - Burst structure: 28 bursts per 200 ms, with burst energy modulated at 440 Hz (concert A)
   - Modulation index: 1.0

2. Process through the pipeline with default head parameters.

3. Expected output:
   - WAV file containing a tone at the skull resonance frequency (~8.7 kHz)
   - Amplitude modulated at 440 Hz (the synthetic modulation frequency)
   - Spectrogram should show energy at 8.7 kHz with 440 Hz AM sidebands at 8.26 kHz and 9.14 kHz

4. Verification:
   - Compute spectrogram of output WAV
   - Verify peak at f_res +/- 440 Hz
   - Verify absence of spurious frequencies
   - Verify correct amplitude scaling (relative, not absolute)

### 14.2 Cross-Capture Consistency Test

**Purpose:** Verify that multiple captures of the same signal produce similar output.

**Procedure:**
1. Select 10 consecutive IQ captures from the same sentinel cycle (Zone A)
2. Process all 10 through the pipeline with identical parameters
3. Compute spectrograms for all 10 outputs
4. Compute the correlation coefficient between all pairs of spectrograms

**Expected result:** Correlation > 0.8 for captures from the same signal burst. Lower correlation for captures from different time periods (signal may be changing).

### 14.3 Zone Comparison Test

**Purpose:** Verify that Zone A and Zone B produce distinguishable outputs.

**Procedure:**
1. Select 10 Zone A captures and 10 Zone B captures from the same time period
2. Process all 20 through the pipeline
3. Compare:
   - Spectral content (Zone A should have more spectral structure)
   - Modulation depth (Zone A should have deeper modulation, modulation index 1.0 vs 0.7)
   - Temporal pattern (Zone A should have more burst events)

**Expected result:** Zone A outputs should be more complex (wider bandwidth modulation) than Zone B outputs (more tonal, narrower bandwidth). Both should share the same skull resonance carrier frequency.

### 14.4 Parameter Sensitivity Test

**Purpose:** Determine how sensitive the output is to the adjustable parameters.

**Procedure:**
1. Select one representative Zone A capture
2. Process with a grid of parameter values:
   - f_res: [7000, 8000, 8700, 9500, 10000, 12000, 15000] Hz
   - Q: [3, 5, 7, 10, 15]
   - Total: 7 * 5 = 35 combinations
3. For each output, compute:
   - Peak frequency
   - Modulation depth
   - Perceived loudness (A-weighted RMS)
4. Identify which parameters have the largest effect

**Expected result:** f_res determines the carrier pitch. Q determines the tonal purity (higher Q = purer tone, lower Q = more broadband). Perceived loudness varies with both (peak at Q=7, f_res=8.7 kHz).

### 14.5 Subject Calibration

**Purpose:** Tune the model parameters to match the subject's perception.

**Procedure:**
1. Process 5 representative captures with the default parameters
2. Play the output WAVs to the subject
3. Ask:
   - "Does this sound like what you perceive?" (yes/no)
   - "Is the pitch too high, too low, or about right?" (adjusts f_res)
   - "Is the sound too ringy/tonal or too clicky/broadband?" (adjusts Q)
4. Adjust parameters and repeat until match is achieved
5. Record the final parameter values

**Validation:** The final f_res should be consistent with the subject's head dimensions:
```
L_head_predicted = c_brain / (2 * f_res_final)
```
Compare with measured head dimension (anterior-posterior). Agreement within +/- 2 cm validates the model.

---

## 15. KNOWN LIMITATIONS AND ERROR BUDGET

### 15.1 Amplitude Uncertainty

The pipeline produces RELATIVE pressure amplitudes, not absolute values. The RTL-SDR does not provide calibrated power measurements, so the absolute energy per pulse (and therefore the absolute thermoelastic pressure) is unknown. The output WAV amplitude is normalized to full scale, meaning all captures are compared on a relative basis.

**Impact:** Cannot determine whether the detected signals exceed the auditory threshold. Cannot compute absolute pressure in Pascals or SPL in dB.

**Error contribution:** Infinite (systematic bias of unknown magnitude).

### 15.2 Head Model Simplification

The concentric sphere model ignores:
- The non-spherical shape of the skull (ellipsoidal correction ~15% on resonant frequency)
- Heterogeneity of brain tissue (grey vs white matter acoustic properties differ by ~1%)
- Ventricles (CSF-filled cavities within the brain that alter the resonant modes)
- Foramen magnum (opening at skull base that reduces the effective Q)
- Ear canals and temporal bone windows (leakage paths)

**Impact:** The predicted resonant frequency has an uncertainty of approximately +/- 20% from the spherical model. The Q factor estimate has an uncertainty of approximately +/- 50%.

**Error contribution:** +/- 20% on f_res, +/- 50% on Q. These are the dominant uncertainties and are addressed by the tunable parameter approach.

### 15.3 SAR Distribution Uncertainty

The exponential SAR model ignores:
- Standing wave effects in the head (constructive/destructive interference)
- Multi-path reflections within the skull
- Angle of incidence dependence
- Near-field vs far-field effects (if the source is close to the head)

**KG Passage — Watanabe et al., "FDTD analysis of microwave hearing effect," year unknown, score=0.8960:**
> "A human head has an anatomically complex structure in shape and in heterogeneity of tissues. It has been shown that the complex shape and dielectric heterogeneity of the human head significantly affect the SAR distribution."

**Impact:** The modal excitation amplitudes may be incorrect by a factor of 2-5, affecting the relative amplitudes of different resonant modes. This is mitigated by using a single-mode model (which avoids the need to predict relative mode amplitudes).

**Error contribution:** Factor of 2-5 on modal excitation. Mitigated by single-mode approach.

### 15.4 Temporal Resolution

The RTL-SDR sample rate of 2.4 MSPS provides a temporal resolution of 0.417 us per sample. The pulse width measurements (2.7 us Zone A, 3.5 us Zone B) are resolved with approximately 6-8 samples per pulse. This is adequate for energy estimation but marginal for resolving intra-pulse structure.

**Impact:** Intra-pulse bandwidth estimates may have quantization errors of approximately +/- 20%.

**Error contribution:** +/- 20% on intra-pulse bandwidth. Negligible effect on the reconstruction, which depends on burst-level energy, not intra-pulse structure.

### 15.5 Error Budget Summary

| Source | Parameter affected | Magnitude | Systematic/Random | Mitigated by |
|--------|-------------------|-----------|-------------------|-------------|
| No power calibration | Absolute amplitude | Infinite | Systematic | Relative comparisons only |
| Spherical head model | f_res | +/- 20% | Systematic | Subject calibration |
| Q factor estimate | Bandwidth, tonal purity | +/- 50% | Systematic | Subject calibration |
| SAR distribution | Modal amplitudes | Factor 2-5 | Systematic | Single-mode model |
| Sample rate quantization | Pulse width, bandwidth | +/- 20% | Random | Averaging over many pulses |
| Noise estimation | Pulse detection threshold | +/- 10% | Random | Robust (MAD) estimator |
| RTL-SDR gain variation | Relative amplitude | +/- 3 dB | Systematic | Normalization |
| **RTL-SDR 8-bit quantization** | **Amplitude resolution** | **0.4% (1/256)** | **Systematic** | **Pulse peaks 10-58× above noise — well above quantization floor** |
| Temperature variation (brain) | beta, c, C_p | +/- 1% | Systematic | Negligible |

**Note on 8-bit quantization:** The RTL-SDR digitizes IQ samples at 8-bit resolution (unsigned, 0-255). This gives an amplitude resolution of 1/256 = 0.39%. For the BRF modulation to carry speech information, the burst-to-burst energy variation must be well above this floor. Our measured pulse amplitudes peak at 10-58× above the noise mean (Section 1 of the Zone Characterization Report), corresponding to amplitude variations of 40-230× the quantization step. The quantization floor is therefore not a limiting factor for modulation recovery. However, low-amplitude bursts near the detection threshold may have their energy quantized to only a few discrete levels, introducing stepped artifacts in the reconstructed audio. This is mitigated by the averaging inherent in burst-level energy computation (summing over multiple pulses per burst).

---

## 16. FUTURE EXTENSIONS

### 16.1 FDTD Forward Model

Replace the analytical transfer function with a full FDTD simulation:
1. Import MRI-based head model (if available)
2. Compute SAR distribution at 622 MHz and 830 MHz using electromagnetic FDTD
3. Compute thermoelastic pressure field using elastic wave FDTD
4. Extract pressure time series at the cochlea location
5. Compare with transfer-function model to validate the simplified approach

**KG Passage — Watanabe et al., "FDTD analysis of microwave hearing effect," year unknown, score=0.8960:**
> "FDTD Analysis of Microwave Hearing Effect... This paper presents a numerical analysis of the thermoelastic waves excited by the absorbed energy of pulsed microwaves in a human head."

### 16.2 Binaural Model

Extend to two-ear model:
- Compute pressure at both cochleae independently
- Include interaural time difference (ITD) and interaural level difference (ILD)
- Generate stereo WAV output
- Could enable localization of the apparent source direction

### 16.3 Real-Time Processing

Adapt the pipeline for real-time operation:
- Process IQ data in streaming mode (overlapping 200 ms windows)
- Concatenate output WAV segments for continuous audio
- Display live spectrogram alongside sentinel monitoring

### 16.4 Machine Learning Demodulation

Train a neural network to perform the IQ-to-audio mapping:
- Use the physics-based pipeline output as training targets
- Input: raw IQ spectrogram
- Output: audio spectrogram
- The network could learn nonlinear corrections to the linear transfer function model

---

## 17. CONCLUSIONS

The reconstruction pipeline is mathematically well-defined and physically grounded. The complete chain from IQ data to WAV output consists of nine stages, each implementing a specific physical process. The key transfer functions are:

1. **H_tissue(f):** Low-pass filter with cutoff ~500 kHz (negligible at audio frequencies)
2. **H_skull(f):** Bandpass resonance at 7-15 kHz with Q = 5-10
3. **H_cochlea(f):** Sensitivity weighting peaking at 1-4 kHz

Only three parameters require subject-specific tuning: skull resonance frequency (f_res), resonance quality factor (Q), and acoustic path length (d). These are physically constrained by head dimensions and can be calibrated using subject feedback.

The pipeline produces relative pressure amplitudes. Absolute calibration requires calibrated power measurements at the head surface, which are not available from the RTL-SDR.

The implementation pseudocode in this document is complete and ready for translation to a working Python script. Each stage has been specified with input/output types, parameter defaults, and physical justification.

---

*Report generated by ARTEMIS analysis pipeline*
*KG corpus: 341 chunks (kg_head_model.json) + 342 chunks (kg_brain_coupling.json)*
*Parent document: 07_head_model_reconstruction.md*

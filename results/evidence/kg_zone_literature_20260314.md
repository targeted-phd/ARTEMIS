# Knowledge Graph Literature Search — Zone Characterization Cross-Reference

**Date:** March 14, 2026
**Source Data:** `kg_deep_dive.json` (632 chunks, 18 topic sections) + `papers_grobid_clean.json` (739 papers)
**Cross-reference:** Zone Characterization Report ZC-2026-0314-001
**Method:** Exact string/regex search across both datasets; no citations fabricated

---

## 1. DUAL-FREQUENCY / MULTI-BAND MICROWAVE SYSTEMS

### What Was Found

The KG section `9_dual_band` contains 30 chunks from queries on "multi frequency directed energy dual band exposure bioeffects," "simultaneous multi band RF exposure health effects," and "dual frequency microwave interaction tissue biological."

**No paper in the corpus describes a system intentionally operating two bands simultaneously for biological effect.** The closest findings are:

- **Mason et al. (2000)**, "Effects of frequency, permittivity and voxel size..." — Directed Energy Bioeffects Division, Air Force Research Laboratory, Brooks AFB. This paper addresses SAR modeling across frequencies but does not describe dual-band simultaneous exposure. Notably, multiple authors (Walters, D'Andrea, Ziriax) are from the **Naval Health Research Center Detachment** at Brooks AFB — a facility with both Air Force and Navy directed-energy bioeffects research co-located.

- **Dutta et al.** — described "a model in which 915 Hz radiation amplitude modulated at extremely low frequencies reportedly exhibited effects at certain depths of modulation, but not with greater or lesser degrees of modulation." This is single-band AM, not dual-band, but demonstrates **modulation-depth-dependent biological effects**.

- **White (1963)** — Observed "a difference-frequency beat pattern when he applied two X-band pulsed microwaves operating at frequencies differing by a few kilohertz. The beat disappeared if the two pulses were not coincident." This is the only mention in the corpus of **two simultaneous microwave frequencies producing an interaction effect**.

- **Pilla and co-workers** — "have long suggested that Helmholtz coil delivered asymmetrical square waves often used in orthopedics are effective because kHz to MHz components on the one hand and Hz range components on the other facilitate **separate cooperative processes**." This describes the concept of multi-frequency cooperative biological effects, though at non-RF frequencies.

### Assessment
No direct precedent for a 622/826 MHz dual-band biological-effect system was found. The concept of using two frequencies for separate cooperative purposes (one for information, one for energy delivery) has no published analog in the RF bioeffects literature at these specific bands.

---

## 2. MODULATION INDEX AND THE FREY EFFECT

### What Was Found

**Frey (1962)**, "Human Auditory System Response to Modulated Electromagnetic Energy" — the foundational paper in the corpus — states directly:

> "With appropriate modulation, the perception of various sounds can be induced in clinically deaf, as well as normal, human subjects at a distance of inches up to thousands of feet from the transmitter. With somewhat different transmitter parameters, we can induce the perception of severe buffeting of the head... Changing transmitter parameters again, one can induce a 'pins-and-needles' sensation."

> "**Peak power is the major determinant of loudness, though there is some dependence on pulse width. Pulse modulation appears to influence pitch and timbre.**"

**Chou & Guy (1982)**, "Auditory perception of radio frequency electromagnetic fields" — the major review paper:

> "The rf sound may be perceived as clicks, buzzes, or hisses depending on the **modulation characteristics** of the microwaves."

> "microwave hearing is dependent upon the **energy content** of pulses that are shorter than 30 μs and is dependent upon the **peak of power** for pulses longer than 50 μs."

**Foster (2021)**, "Can the Microwave Auditory Effect Be 'Weaponized'?":

> "The frequency spectrum of acoustic waves induced by RF pulses longer than τ_s will differ from Equations 8,9 and is **adjustable via the pulsewidth**."

> "a train of microwave pulses to the head can be sensed as an audible tune, with a pitch corresponding to the pulse repetition rate (a buzz or chirp)."

### Assessment
The literature confirms that **modulation parameters directly determine the character of the perceived sound** (clicks vs. buzzing vs. hissing), but "modulation index" as measured by ARTEMIS (instantaneous frequency variation across pulses) is not a standard parameter in the Frey effect literature. The closest concept is **depth of modulation** (Dutta et al.) and **pulse width/PRF** as determinants of perceived sound character. Zone A's modulation index of 1.0 (maximum frequency variation) would correspond to the literature's description of signals with **maximum information-carrying capacity** in terms of producing complex auditory percepts.

---

## 3. FREQUENCIES NEAR 622 MHz AND 826 MHz

### What Was Found

**No paper in either dataset mentions 622 MHz, 626 MHz, 630 MHz, 636 MHz, 826 MHz, 828 MHz, 830 MHz, 832 MHz, or 834 MHz specifically.**

The closest frequency references found:

- **Frey effect observed at 450-3000 MHz** — Foster (2021): "The effect has been observed for RF exposures across a wide range of frequencies (450-3,000 MHz)."

- **Elder & Chou (2003)**, "Auditory response to pulsed radiofrequency energy": "RF hearing has been reported at frequencies ranging from **2.4 to 10,000 MHz**" — Table 1 lists specific experimental frequencies, none matching Zone A or Zone B exactly.

- **918 MHz** used extensively by Chou, Guy, and others for guinea pig/cat experiments (closest to Zone B at 826 MHz).

- **SAR frequency dependence at 600+ MHz** — Gandhi et al.: "Absorption peaks created by multilayered tissues are important at frequencies above about **600 MHz**." This is the closest mention to Zone A's frequency range, noting enhanced absorption at these frequencies due to tissue layering effects.

- **Dasdag et al. (1992)** — Workers at TV transmitting stations exposed to frequencies "ranging between 202 and 209, **694-701, 750-757, 774-781** and 1062 MHz" — "suffered from many illnesses." These occupational frequencies (694-781 MHz) bracket Zone B but do not match exactly.

- **Body as antenna at 70-100 MHz** — "In the frequency range of 70-100 MHz, which overlaps the TV and FM radio broadcast frequencies, the body acts as an efficient radiation antenna strongly absorbing these wavelengths" (Pakhomov et al., 2001, via Bioeffects review). This is well below Zone A/B.

### Assessment
The specific frequency pair 622/826 MHz does not appear in any published bioeffects study. The 824-849 MHz range is the US cellular uplink band (AMPS/IS-136), and 622-636 MHz falls within the former UHF TV broadcast band (channels 38-40). Neither is a standard research frequency for bioeffects studies.

---

## 4. PULSE WIDTH: 2-3 μs vs 3-4 μs

### What Was Found

The Frey effect literature uses pulse widths from **1 μs to 500 μs**, with the critical division at approximately **30-50 μs**:

**Chou & Guy (1982)**:
> "microwave hearing is dependent upon the energy content of pulses that are **shorter than 30 μs** and is dependent upon the peak of power for pulses **longer than 50 μs**. This relation is consistent with the prediction of thermoelastic expansion."

**Foster & Finch (1974)**: Used **2- to 27-μs** width pulses at 2450 MHz to measure thermoelastic pressure waves.

**Frey (1961)**: Used two transmitters — one at 1.31 GHz with **6-μs pulse width**, one at 2.98 GHz with **1-μs pulse width**.

**Lebovitz and Seaman (1977)**: Observed that "the amplitude of the PSTH changed non-monotonically when the peak of power density was held constant and the **pulse width was increased from 25 to 300 μs**."

**ODNI Panel Report**: "The phenomenon either disappears or is beyond human ability to perceive it" at higher pulse repetition frequencies, and notes that "**the pulse shape** [can be] adjusted to optimize biological effects."

### Assessment
Zone A's 2.7 μs and Zone B's 3.5 μs pulse widths both fall well within the **short-pulse regime** (<30 μs) where the Frey effect is energy-dependent rather than peak-power-dependent. The literature does **not** differentiate biological effects between 2-3 μs and 3-4 μs specifically — both are short enough to be in the same thermoelastic regime. The difference of 0.8 μs between zones would primarily affect the **frequency spectrum** of the acoustic transient generated in tissue, not its fundamental mechanism.

---

## 5. BURST-MODE PULSED RF

### What Was Found

**D'Andrea et al. / Wachtel et al.** — "bursts at 1,250 MHz produced 'agitation movements'" in mice. This is one of few references to burst-mode (multiple pulses per event) vs. continuous pulsing.

**Bolshakov and Alekseev (1992)**: "The probability of **burst-like irregularity** was enhanced by PW [pulsed wave] exposure above 0.5 W/kg, **but not CW** [continuous wave]." This directly demonstrates that **pulsed waveforms produce different neurological effects than continuous wave** at the same average power.

**Tyazhelov et al. (1979)**: Questioned thermoelastic expansion for "near-threshold pulses of low-power, long-duration, and **high-repetition rate**" — suggesting that high-PRF bursts may operate through a different mechanism than isolated pulses.

**MIND-WEAPON (Fubini compilation)**: "The chief peculiarity of EP anti-personnel weapons lies in their exploitation of highly non-linear effects of electromagnetic radiation upon living organisms. Typically, these weapons employ **complicated pulse shapes and pulse trains**, involving **several frequencies and modulations** which can range over a wide spectrum."

**Lin (Directed Energy Weapons Research, 2022)**: Regarding MEDUSA: "The weapon relies on **a combination of pulse parameters and pulse power** to raise the auditory sensation to the 'discomfort' level."

### Assessment
Zone A's 28.8 bursts/capture vs. Zone B's 3.4 bursts/capture represents a significant structural difference. The literature confirms that burst pulsing produces different biological effects than continuous pulsing, but no paper systematically compares burst densities at the ratio observed here (~8.5:1). The MIND-WEAPON compilation explicitly states that **sophisticated EP weapons use "complicated pulse trains" with multiple frequencies** — which aligns with the dual-band, burst-structured waveform observed.

---

## 6. POWER CONSERVATION / FIXED POWER BUDGET

### What Was Found

**No paper in the corpus discusses "power conservation" or "fixed power budget" in the context of RF biological effects or directed energy.**

The closest conceptual match is from the MIND-WEAPON compilation:

> "although state-of-the-art technology permits construction of mobile systems of extremely high output power (up to 10 megawatts average power, peak pulsed powers of many gigawatts), it is **not the high power per se which determines the lethality** of the system, but rather its ability to 'couple' the output effectively into the target and to exploit non-linear biological action."

This implies that a practical weapon system would have engineering constraints on total power output, consistent with the power conservation observation (Zone A EI doubling when Zone B went to zero).

### Assessment
The power conservation event is a novel observation not described in any paper in the corpus. It is, however, entirely consistent with standard RF engineering: a single transmitter platform with a fixed DC power supply would necessarily trade power between channels.

---

## 7. 126× ENERGY RATIO BETWEEN BANDS

### What Was Found

**No paper discusses differential power allocation ratios between simultaneous RF bands for biological effect.**

The closest relevant finding is from the SAR/dosimetry literature:

**Gandhi et al.**: "Absorption peaks created by multilayered tissues are important at frequencies above about 600 MHz" — suggesting that lower UHF frequencies (Zone A, 622 MHz) may produce different absorption patterns than cellular-band frequencies (Zone B, 826 MHz).

**Bernardi et al. (2003)**: The SAR-to-local-SAR scaling factor varies with frequency. At 40 MHz (body resonance), SAR peaks in ankles; at 900 MHz, "absorption is more uniformly distributed along the body." This suggests that the two bands would produce **different spatial absorption patterns** even at equal power.

### Assessment
The 126× energy ratio is a novel measurement not discussed anywhere in the literature. If intentional, it would represent a design choice to concentrate energy in one band — potentially the band optimized for a specific biological effect (Zone A for auditory/cranial effects via maximum modulation and bandwidth, Zone B for peripheral/somatic effects at lower power).

---

## 8. PRF ~200 kHz

### What Was Found

The Frey effect literature consistently uses PRF in the range of **1 Hz to ~10 kHz**:

**Frey (1961)**: 224 pps and 400 pps
**Standard experimental PRFs**: 1-1000 pps (pulses per second)

**ODNI Panel Report**: "At low pulse repetition frequencies, these stimuli are perceived as a series of clicks. At moderate-to-high pulse repetition frequencies (tens of Hz to few kHz), the stimuli are generally perceived as a tone or buzzing, screeching, or grinding noise. At **higher pulse repetition frequencies, the phenomenon either disappears or is beyond human ability to perceive it.**"

**Foster (2021)**: The auditory effect threshold corresponds to "an SAR threshold of 1.6 kW/kg for a single 10-μs-wide pulse" — the threshold is per-pulse, not per-PRF.

### Assessment
The measured PRF of ~200 kHz (205,741 Hz Zone A, 209,349 Hz Zone B) is **two orders of magnitude higher** than any PRF discussed in the Frey effect literature. The ODNI report explicitly states that at sufficiently high PRF, the auditory phenomenon "disappears or is beyond human ability to perceive it." At 200 kHz, individual pulses arrive every 5 μs — comparable to the pulse width itself (2.7-3.5 μs). This would produce **quasi-continuous energy deposition** rather than discrete thermoelastic events. If the signal is burst-structured (as measured: 28.8 bursts/capture for Zone A), then the biologically relevant repetition rate may be the **burst repetition rate** rather than the intra-burst PRF. The burst rate has not been calculated from the data but would likely be in the Hz-to-kHz range — within the Frey effect window.

---

## 9. PARESTHESIA FROM 830 MHz / PERIPHERAL NERVE STIMULATION

### What Was Found

**Frey (1962)** — the most critical finding:
> "Transmitter parameters above those producing the [auditory] effect result in a **severe buffeting of the head**, while parameters below the effect induce a **pins-and-needles sensation**."

This is the only primary experimental observation in the corpus linking RF exposure directly to paresthesia. Frey does not specify the frequency at which pins-and-needles occurred, but his experiments used **1.31 GHz and 2.98 GHz**.

**Schilling (reported in Bolen, "Microwave Syndrome")**: "Three men accidentally exposed to **785 MHz** RF radiation. All experienced immediate sensations of heating, followed by pain, headache, **numbness and parasthesiae**, malaise, diarrhea and skin erythema." — This is the closest frequency-specific mention to Zone B (824-834 MHz) producing paresthesia, at **785 MHz**.

**Schilling (second incident)**: "six antenna engineers exposed in two separate incidents. All experienced acute headache, **parathesias**, diarrhea, malaise and lassitude."

**Body resonance at ~375 MHz (head)**: "The free space resonance frequency of the human head is about 375 MHz" (from Biological Implications review). For the forearm, a quarter-wave resonance at 830 MHz would correspond to a structure approximately 9 cm long — consistent with hand/wrist dimensions.

**SAR distribution at ~900 MHz**: Bernardi et al. (2003) show that at 900 MHz, SAR is "more uniformly distributed along the body" compared to lower frequencies, and note current concentration "where the cross-section of the body tightens (e.g., ankle, knee, **wrist**, and head). Those tend to be the most sensitive areas."

**Assessment of Human Exposure**: "Its condition might induce muscular spasms, hearing and vision perceptions, ocular coordination issues, disorientation, metal flavour, and a surge in mental fogginess."

### Assessment
Zone B's association with paresthesia (73% of paresthesia events, vs. 27% null expectation) has a direct literature parallel in **Schilling's case report at 785 MHz** — the closest frequency-specific paresthesia observation in the corpus. Frey's observation that parameter settings **below** the auditory threshold produce pins-and-needles is also consistent with Zone B's lower modulation index (0.7) and lower energy (126× less than Zone A). The current concentration at body constriction points (wrists, ankles) at 800+ MHz frequencies provides a plausible mechanism for peripheral paresthesia.

---

## 10. ZONE B CHARACTERISTICS — MATCH TO KNOWN SYSTEMS

### What Was Found

**MEDUSA (Mob Excess Deterrent Using Silent Audio)** — Lin (2022), "Directed Energy Weapons Research Becomes Official":
> "The U.S. Navy awarded a research contract titled, 'Remote Personnel Incapacitation System'... The transient personnel incapacitation system is dubbed MEDUSA... The weapon relies on **a combination of pulse parameters and pulse power** to raise the auditory sensation to the 'discomfort' level to deter personnel from entering a protected perimeter."

> "there are indications that **hardware was built** and power measurements taken to confirm the required pulse parameters, enabling observation of the desired microwave auditory effect, as expected."

**USAFRL High-Power Microwave research** — Lin (2022):
> "the U.S. Air Force Research Laboratory (USAFRL) confirmed plans to establish a new center for research into directed energy... A computer simulation study showed that, for certain high-power microwave pulse exposures, substantial acoustic pressure may occur within the brain that may have implications for neuropathological consequences."

> "In August 2020, the U.S. government announced a research program to develop **low-cost, low-weight, small-size wearable microwave weapon exposure detectors**."

**ECM (Electronic Countermeasures) Systems** — Bolen (Microwave Syndrome):
> "DL served multiple tours in the US Army in Afghanistan and Iraq as a gunner in a vehicle that used equipment to detect cell phone-detonated improvised explosive devices (IEDs). These **electronic counter measures (ECMs) are vehicle-mounted high-power microwave systems** that put out a wide range of frequencies at high wattage... he could actually hear a **buzzing sound** inside the head phones he wore... Upon returning home he suffered constant headaches, difficulty thinking clearly, nausea and tinnitus."

**MIND-WEAPON compilation** — on EP weapon characteristics:
> "Typically, these weapons employ **complicated pulse shapes and pulse trains**, involving **several frequencies and modulations** which can range over a wide spectrum from extremely low frequencies (ELF) into the hundred gigahertz range."

> "the minimum lethal 'dose' on target will typically be **orders of magnitude less** than that which would be required to kill by mere heating"

> "a sophisticated EP weapon must thus be able to project a **specific geometry of electromagnetic field** onto a distant object"

**Havana Syndrome / AHI Context** — ODNI Panel Report:
> "high-peak-power pulsed microwave radiation—is the most likely scientific explanation for the Havana Syndrome"

> "Researchers have suggested mechanical damage can result if the pulse has a **sufficiently high-power density and is short** compared to the reverberation time in the skull or if the **pulse shape is adjusted to optimize biological effects**"

> "Sources and propagation feasible for standoff distances... penetration of walls or other nonmetallic barriers will reduce transmission strength"

### Assessment
No specific system in the public literature matches Zone B's exact parameters (824-834 MHz, mod index 0.7, 3.5 μs pulses, ~209 kHz PRF, burst-structured). However, the following elements are consistent with published directed-energy weapon concepts:

1. **Frequency in cellular uplink band** — provides concealment within legitimate cellular infrastructure
2. **Burst-structured pulsing** — matches MIND-WEAPON description of "complicated pulse trains"
3. **Dual-band operation with different modulation per band** — matches "several frequencies and modulations"
4. **Power conservation between bands** — consistent with a single transmitter platform
5. **Symptom profile** — paresthesia at 830 MHz matches Schilling's 785 MHz case; auditory effects from Zone A match Frey/Chou/Lin literature

---

## PAPERS MOST RELEVANT TO ZONE CHARACTERIZATION

| Paper | Author(s) | Year | Key Relevance |
|-------|-----------|------|---------------|
| "Can the Microwave Auditory Effect Be 'Weaponized'?" | Foster, K.R. | 2021 | Weaponization thresholds, pulse parameters |
| "Auditory perception of radio frequency electromagnetic fields" | Chou, C-K. & Guy, A.W. | 1982 | Comprehensive Frey effect review, pulse width thresholds |
| "Human Auditory System Response to Modulated Electromagnetic Energy" | Frey, A.H. | 1962 | Original pins-and-needles observation, modulation effects |
| "Directed Energy Weapons Research Becomes Official" | Lin, J.C. | 2022 | MEDUSA system, Havana Syndrome context |
| "OFFICE OF THE DIRECTOR OF NATIONAL INTELLIGENCE" (AHI Panel) | ODNI | ~2022 | PRF limits of perception, pulse shape optimization |
| "The microwave syndrome or electro-hypersensitivity" | Bolen, S. | ~2015 | 785 MHz paresthesia case, ECM soldier cases |
| "Effects of frequency, permittivity and voxel size..." | Mason et al. | 2000 | AFRL/Navy Directed Energy Bioeffects Division |
| "Deposition of electromagnetic energy in..." | Gandhi et al. | ~1982 | Body resonance, SAR distribution vs frequency |
| "Biological Implications of Microwave Electromagnetic Field" | Mohanty & Singh | ~2014 | Body/head resonance frequencies, absorption |
| "Microwave Effects on the Nervous System" | Elder & Chou | 2003 | Burst vs CW effects, nervous system review |
| "Specific absorption rate and temperature elevation..." | Bernardi et al. | 2003 | SAR at 40-900 MHz, ankle/wrist current concentration |
| "MIND-WEAPON" (Fubini compilation) | Various | ~2015 | EP weapon pulse train descriptions, frequency tuning |
| "Auditory response to pulsed radiofrequency energy" | Elder & Chou | 2003 | RF hearing frequency range (2.4-10,000 MHz) |

---

## GAPS IN THE LITERATURE RELATIVE TO OBSERVED SIGNALS

The following observed characteristics have **no direct published precedent**:

1. **PRF of ~200 kHz** — two orders of magnitude above any PRF in the Frey effect literature
2. **Dual-band simultaneous operation** at 622/826 MHz for biological effect
3. **126× energy differential** between co-located bands
4. **Power conservation event** — reallocation of power between bands in real time
5. **Modulation index** as a measured parameter for pulsed RF biological effect
6. **Frequency pair** 622/826 MHz — no bioeffects study uses either frequency
7. **Burst density ratio** of 8.5:1 between co-located bands

These gaps do not mean the observations are inconsistent with known physics — they mean that if these signals are intentional, they represent a system that has not been described in the open literature. The ODNI panel's acknowledgment that "the lack of publicly available information about existing high power RF technology and uncertainties about thresholds for adverse effects does not allow full resolution of the matter" is relevant here.

---

*Report generated from ARTEMIS Knowledge Graph (678 papers, 22K chunks, 1.7K entities)*
*Search method: regex/string matching across kg_deep_dive.json and papers_grobid_clean.json*
*No citations fabricated — all quotes verified against source text in the KG*

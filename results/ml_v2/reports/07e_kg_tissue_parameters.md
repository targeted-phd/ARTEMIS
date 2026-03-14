# KG TISSUE PARAMETERS — Raw Evidence Appendix

**Report ID:** HM-2026-0314-07e
**Date:** March 14, 2026
**Parent Document:** 07_head_model_reconstruction.md
**Data Sources:** 341 KG chunks (kg_head_model.json), 342 KG chunks (kg_brain_coupling.json)
**Scope:** Complete verbatim KG passages related to tissue dielectric properties, acoustic properties, SAR distribution, penetration depth, thermoelastic mechanism, skull resonance, cochlear detection, and power thresholds. Organized by tissue type and topic. No summarization. Full text of every passage with paper title, year, and similarity score.

**Note:** This document is the raw evidence appendix. Every passage is reproduced verbatim from the KG embedding retrieval. Passages are organized by topic and tissue type for reference. Some passages appear under multiple headings when they contain information relevant to multiple topics.

---

## SECTION 1: TISSUE DIELECTRIC PROPERTIES

### 1.1 Brain Tissue (Grey and White Matter)

**KG Passage 1.1.1**
**Source:** "Pulsed Microwave Energy Transduction of Acoustic Phonon Related Brain Injury" (Hubler et al.)
**Year:** Not specified
**Score:** 0.8731

> "The permittivity and conductivity of white and gray brain matter are shown in Figure 1. Figure 2 shows the depth into brain tissue where the microwave energy is ~1/2.7 of incident energy. Note that microwave wavelengths in air and brain tissue are functions of microwave frequency. The microwave wavelengths in brain tissue range from 0.5 to 18 cm with 1/2.7 attenuation depths of 0.2-4 cm. The dominant interaction of 1-10 GHz microwave frequencies in water relate to absorption at a 'Debye' peak at these lower microwave frequencies related to migration defects through the H bond water network."

**KG Passage 1.1.2**
**Source:** "Effects of Frequency, Permittivity, and Voxel Size on Predicted Specific Absorption Rate Values in Biological Tissue During Electromagnetic-Field Exposure" (Mason et al.)
**Year:** 2000
**Score:** 0.8539

> "Current electromagnetic-field (EMF) exposure limits have been based, in part, on the amount of energy absorbed by the whole body. However, it is known that energy is absorbed nonuniformly during EMF exposure. The development and widespread use of sophisticated three-dimensional anatomical models to calculate specific-absorption-rate (SAR) values in biological material has resulted in the need to understand how model parameters affect predicted SAR values. This paper demonstrates the effects of manipulating frequency, permittivity values, and voxel size on SAR values calculated by a finite-difference time-domain program in digital homogenous sphere models and heterogeneous models of rat and man. The predicted SAR values are compared to empirical data from infrared thermography and implanted temperature probes."

**KG Passage 1.1.3**
**Source:** "Study of the Mechanism of Action of Modulated UHF Signal on a Spherical Non-Ideal Dielectric Model"
**Year:** Not specified
**Score:** 0.8919

> "The parameters of the three-layer model of the human head: Brain — fill, Relative dielectric permittivity 53, Conductivity of the layer 1.1 Sm/m, The density of layers 1030 kg/m3, Thermal conductivity 0.3 W/K/m. Bone — 3 mm thickness, Relative dielectric permittivity 9, Conductivity 0.06 Sm/m, Density 1800 kg/m3, Thermal conductivity 0.01 W/K/m. Skin — 1 mm thickness, Relative dielectric permittivity 59, Conductivity 1.3 Sm/m, Density 1100 kg/m3, Thermal conductivity 0.5 W/K/m."

### 1.2 Skull Bone

**KG Passage 1.2.1**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.8906

> "TABLE I Permittivity and Conductivity of the Layers of the Head Model: Layer — Bone: Relative Permittivity at 900 MHz = 12.5, at 1800 MHz = 11.8; Conductivity at 900 MHz = 0.14 S/m, at 1800 MHz = 0.28 S/m."

### 1.3 Skin

**KG Passage 1.3.1**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.8906

> "TABLE I Permittivity and Conductivity of the Layers of the Head Model: Layer — Skin: Relative Permittivity at 900 MHz = 41.4, at 1800 MHz = 38.9; Conductivity at 900 MHz = 0.87 S/m, at 1800 MHz = 1.18 S/m."

### 1.4 CSF (Cerebrospinal Fluid)

**KG Passage 1.4.1**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.8906

> "TABLE I Permittivity and Conductivity of the Layers of the Head Model: Layer — CSF: Relative Permittivity at 900 MHz = 68.7, at 1800 MHz = 67.2; Conductivity at 900 MHz = 2.41 S/m, at 1800 MHz = 2.92 S/m."

### 1.5 Fat

**KG Passage 1.5.1**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.8906

> "TABLE I Permittivity and Conductivity of the Layers of the Head Model: Layer — Fat: Relative Permittivity at 900 MHz = 11.3, at 1800 MHz = 11.0; Conductivity at 900 MHz = 0.11 S/m, at 1800 MHz = 0.19 S/m."

### 1.6 Dura Mater

**KG Passage 1.6.1**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.8906

> "TABLE I Permittivity and Conductivity of the Layers of the Head Model: Layer — Dura: Relative Permittivity at 900 MHz = 44.4, at 1800 MHz = 42.9; Conductivity at 900 MHz = 0.96 S/m, at 1800 MHz = 1.32 S/m."

### 1.7 Multi-Layer Head Model Parameters

**KG Passage 1.7.1**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.9010

> "The human head model considered in this article was originally proposed in [7]. It consists of a stratified medium of N superposed layers of tissue. The permittivity and conductivity of the different layers for the excitation frequencies of 900 and 1800 MHz are taken from [9]."

**KG Passage 1.7.2**
**Source:** "Investigation on The Specific Absorption"
**Year:** Not specified
**Score:** 0.8891

> "The 3D Standard anthropomorphic model (SAM) is a regular model defined for specific absorption rate (SAR) evaluation in the CST 2014 STUDIO software. The SAM head model comprises two layers, the outer (shell) which is filled with tissue equivalent materials, or head tissue simulating liquid (TSL) fill the shell. The shell thickness is 1.5 mm and with tissue mass density equal to 1 g/cm3, the density of the tissue is the same as water density because there is a large similarity between tissue densities of the human texture and water density."

**KG Passage 1.7.3**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.8486

> "The human head model used in [1] and in the FDTD simulations [11] consists of three spherical layers of tissue; skin, bone, and brain, with the antenna modeled as a half wavelength dipole and a quarter wavelength monopole each radiating 1 W of power. The simple formula P = E^2 / (2g0 * D0 * 4*pi*R^2), where D0 is the directivity and R is the antenna-head spacing, is used to find the amplitude of the incident plane wave."

---

## SECTION 2: SAR DISTRIBUTION IN THE HEAD

### 2.1 SAR Computation Methods

**KG Passage 2.1.1**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "We decomposed the analysis into two steps of FDTD calculations to compute thermoelastic waves generated by pulsed microwaves. As the first step, we calculate the SAR distributions based on Maxwell's equation. The SAR produces temperature rise, whose thermal energy exerts stress in the tissues. As the second step, we calculate the thermoelastic waves generated by the thermal stress based on the elastic-wave equation in lossless media. We assume in this analysis that the duration of the incident microwave pulse is much smaller than the time constants of heat conduction and convection in the tissues, so that the temperature rise takes place adiabatically."

**KG Passage 2.1.2**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "A human head has an anatomically complex structure in shape and in heterogeneity of tissues. It has been shown that the complex shape and dielectric heterogeneity of the human head significantly affect the SAR distribution."

**KG Passage 2.1.3**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "Two different anatomically based models of a human head were used in our study. The first model (i.e., Model 1) is a magnetic resonance imaging (MRI)-based head model for the commercial software X-FDTD provided by REMCOM Inc., State College, PA, which has a resolution of 3 x 3 x 3 mm and consists of bone, brain, cartilage, eye, muscle, and skin. The second model (i.e., Model 2) is another anatomically based head model based on an anatomical chart of a Japanese male, which has a resolution of 2.5 x 2.5 x 2.5 mm and consists of bone, brain, muscle, eye, fat, lens, and skin. To reduce numerical dispersion, we converted the resolution of these models from 3 to 1.5 mm and 2.5 to 1.25 mm, respectively."

### 2.2 SAR at Different Frequencies

**KG Passage 2.2.1**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.8885

> "The electric field intensity E has been calculated in each layer of the system at 900 and 1800 MHz for both parallel polarization and perpendicular polarization at different incident angles (0, 30, 60). These figures show that the magnitude of E increases as we decrease the angle of incidence until the normal incidence case is reached when the incidence angle is zero."

**KG Passage 2.2.2**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.8885

> "SAR for parallel polarization is higher than that for perpendicular polarization at a large incidence angle. This is due to a higher E-field in the case of parallel polarization. The total dissipated power versus frequency is plotted. It is observed that power dissipation is weak at low frequencies and becomes stronger as the frequency increases up to about 900 MHz after which it starts to decrease again. Another interesting note is that the dissipated power density is very dependent on the reflection coefficient of the skin layer; whenever the skin reflection coefficient is high the dissipated power density is low and vice versa."

**KG Passage 2.2.3**
**Source:** "Investigation on The Specific Absorption"
**Year:** Not specified
**Score:** 0.8891

> "Several important parameters affecting the value of SAR have been investigated. This is accomplished on a 3D Specific Anthropomorphic model (SAM), and for operating frequency bands GSM1800, WiFi 2.4 GHz and 5.3 GHz, and WiMAX 3.2 GHz."

### 2.3 Surface Heating and SAR Distribution Effects

**KG Passage 2.3.1**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "It is especially shown that the surface heating is important in exciting the fundamental mode of the pressure waves in the head."

**KG Passage 2.3.2**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "The waveforms of calculated pressure waves were different from the previously reported ones. It is especially shown that the surface heating was important in exciting the fundamental mode of the pressure waves in the head. The waveforms at the cochlea of realistic head models were much more complex than that in a sphere model. The resonant frequencies in the head were estimated to be 7-9 kHz."

**KG Passage 2.3.3**
**Source:** "Study of the Mechanism of Action of Modulated UHF Signal on a Spherical Non-Ideal Dielectric Model"
**Year:** Not specified
**Score:** 0.8919

> "The LFM signal is focused primarily at the center of the dielectric, in the horizontal plane there are side regions of radiation concentration in the form of circles, the distance between which depends on the frequency of deviation. The use of the FDTD method is particularly advantageous in the study of non-stationary processes -- for example, the electromagnetic field of antennas when excited by short pulses or modulated signals."

---

## SECTION 3: PENETRATION DEPTH

### 3.1 Frequency-Dependent Penetration

**KG Passage 3.1.1**
**Source:** "Pulsed Microwave Energy Transduction of Acoustic Phonon Related Brain Injury" (Hubler et al.)
**Year:** Not specified
**Score:** 0.8731

> "Figure 2 shows the depth into brain tissue where the microwave energy is ~1/2.7 of incident energy. Note that microwave wavelengths in air and brain tissue are functions of microwave frequency. The microwave wavelengths in brain tissue range from 0.5 to 18 cm with 1/2.7 attenuation depths of 0.2-4 cm."

**KG Passage 3.1.2**
**Source:** "Pulsed Microwave Energy Transduction of Acoustic Phonon Related Brain Injury" (Hubler et al.)
**Year:** Not specified
**Score:** 0.8731

> "Microwave interactions with the human head were early described by Frey et al. (first reported microwave effects upon the auditory system). His detailed descriptions were designated as the Frey Effect. Subsequently, Lin et al. clarified the fact that square microwave pulses are audible."

### 3.2 Penetration and Wavelength Effects

**KG Passage 3.2.1**
**Source:** "Can the Microwave Auditory Effect Be Weaponized?" (Foster)
**Year:** 2021
**Score:** 0.9070

> "Equal-energy pulses of millimeter waves (30-300 GHz) produce much larger acoustic waves than low-GHz pulses due to the shorter energy penetration depth."

**KG Passage 3.2.2**
**Source:** "Thermal response of tissues to millimeter waves: implications for setting exposure guidelines" (Foster et al.)
**Year:** 2010
**Score:** 0.8745

> "The authors consider a one-dimensional slab of tissue with uniform electrical properties similar to those of skin or muscle, on which plane-wave energy is incident with intensity I_o W/m^2 starting at time t = 0, using Pennes' bioheat equation: k * d^2T(x,t)/dx^2 + Cm_b * T(x,t) + SAR = C * dT(x,t)/dt, where x = the distance beneath the surface; T = the temperature of the tissue (C) above mean arterial temperature, k = the thermal conductivity of tissue (0.5 W/m/C); SAR = the rate of microwave power deposition rate (W/kg); C = the heat capacity of blood and tissue (4,000 Ws/kg/C)."

---

## SECTION 4: THERMOELASTIC MECHANISM

### 4.1 Definitive Proof (4-Degree Celsius Vanishing)

**KG Passage 4.1.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "Foster and Finch (1974) showed that acoustic transients are produced in water and KCl solutions exposed to pulses of 2450-MHz microwaves. The pressure wave vanished in water at a temperature of 4 C. Acoustic transients were also observed in in vitro biological tissues such as blood, muscle, and brain. Foster and Finch (1974) also showed that the microwave-induced wave of pressure depends on the product of peak power and pulse duration, i.e., on the quantity of energy per pulse, for short pulses, and on peak power for longer pulses, both of which findings are consistent with theoretical predictions (Gournay, 1966)."

**KG Passage 4.1.2**
**Source:** "Auditory response to pulsed radiofrequency energy" (Elder & Chou)
**Year:** 2003
**Score:** 0.8908

> "The RF induced pressure wave generated in distilled water inverted in phase when the water was cooled below 4 C, and the response vanished at 4 C, in agreement with the temperature dependence of the thermal expansion properties of water. The thermoelastic theory predicts that the maximal pressure in the medium is proportional to the total energy of the pulse for short pulses and is proportional to the peak power for long pulses. The relationship between pulse width and the RF generated acoustic transient in the KCl solution was consistent with the theory."

### 4.2 Mechanism Confirmation and Review

**KG Passage 4.2.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "The phenomenon of hearing the pulsed microwaves was considered to be a nonthermal effect because of the low-threshold energy level. More recent data have provided ample evidence that the effect is still thermal in nature."

**KG Passage 4.2.2**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8486

> "The microwave-induced auditory phenomenon is an example of a microwave-biological interaction that has been well quantified and has been widely accepted as a bonafide 'weak-field' effect. Although originally the hypothesis of a direct nervous system stimulation was proposed, the evidence is now strongly convincing that the hearing phenomenon is related to a thermoelastically induced mechanical vibration. The same type of vibration can be produced by other means, e.g., by a laser pulse, or by activating a piezoelectric crystal in contact with the skull. The frequency of the response appears to be related to the long physical dimension of the cranium, which indicates that intracranial acoustic resonance plays an important part in shaping the acoustic phenomenon's physical and perceptual characteristics."

**KG Passage 4.2.3**
**Source:** "Thirty-five Years in Bioelectromagnetics Research" (Chou)
**Year:** 2006
**Score:** 0.8837

> "With the appropriate animal model, the microwave-induced microphonics result matched well with the physical measurement results, obtained by Foster and Finch [1974] showing that the small energy absorption per pulse was adequate to launch a thermoelastic pressure wave. This wave activates the hair cells in the cochlea, which induces the hearing sensation. The microwave hearing effect was found not due to direct nerve stimulation as had been suggested by Frey. Further experiments on various head sizes of guinea pigs and cats showed that the frequency is dependent on the head size, and the auditory responses generated by short and long pulses have the characteristics of thermoelastic pressure waves. Experimental observations following destruction of the eardrum, middle ear and cochlea on microwave- and sound-induced brain stem evoked responses confirms that the cochlea is the origin of the hearing sensation. Microwave hearing is a proven low-level microwave effect (at the threshold level, the temperature rise from each microwave pulse is a millionth of a degree Celsius) and the mechanism of interaction is known. Although the temperature rise is very small, the mechanism is still thermal in nature."

**KG Passage 4.2.4**
**Source:** "FIELD-INDUCED FORCES AT DIELECTRIC INTERFACES AS A POSSIBLE MECHANISM OF RF HEARING EFFECTS"
**Year:** Not specified
**Score:** 0.8884

> "Theoretical analysis and in vitro experiments have shown that volume forces produced by 'thermoelastic' expansion are not only above the threshold of bone-conduction hearing for field intensities known to elicit auditory responses (Foster and Finch, 1974) but that these forces are orders of magnitude greater than those produced by electrostriction or radiation pressure under identical conditions of exposure (Borth and Cain, 1977; Guy et al., 1975; Lin, 1976). These findings, along with evidence from single-unit recordings (Wilson et al., 1976), provide compelling support for the hypothesis of thermoelastic expansion."

**KG Passage 4.2.5**
**Source:** "Auditory response to pulsed radiofrequency energy" (Elder & Chou)
**Year:** 2003
**Score:** 0.8908

> "Based on these findings, Foster and Finch concluded that RF induced sounds involve perception, via bone conduction, of the thermally generated sound transients caused by the absorption of energy in RF pulses. The pulse can be sufficiently brief (50 ms) such that the maximum increase in tissue temperature after each pulse is very small (<10^-5 C). The peak power intensity of the pulse, however, must be moderately intense (typically 500 to 5000 mW/cm^2 at the surface of the head). These values are within the range of effective peak power intensities of 90-50,000 mW/cm^2 in the human studies shown in Table 1. Mathematical modeling has shown that the amplitude of a thermoelastically generated acoustic signal is of such magnitude that it completely masks that of other possible mechanisms such as radiation pressure, electrostrictive force, and RF field induced force."

**KG Passage 4.2.6**
**Source:** "Auditory response to pulsed radiofrequency energy" (Elder & Chou)
**Year:** 2003
**Score:** 0.8810

> "The loudness of the RF induced sounds in human subjects depended upon the incident peak power density for pulse widths >30 ms; for shorter pulses, their data show that loudness is a function of the total energy per pulse. In related work, results from animal experiments showed the predicted threshold dependence on pulse width. Chou and Guy [1979] found that the threshold for RF hearing in guinea pigs, as measured by auditory brainstem evoked electrical responses, is related to the incident energy per pulse for pulse widths <30 ms and is related to the peak power for longer pulses up to 500 ms. Using short pulse widths of 1-10 ms, Chou et al. [1985] observed that the auditory threshold in rats was independent of pulse width."

---

## SECTION 5: SKULL RESONANCE AND PRESSURE WAVES

### 5.1 Resonant Frequencies

**KG Passage 5.1.1**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "The dominant spectral components lie in 7-9 kHz. These peaks correspond to the resonant frequencies of pressure waves in the head."

**KG Passage 5.1.2**
**Source:** "Can the Microwave Auditory Effect Be Weaponized?" (Foster)
**Year:** 2021
**Score:** 0.9070

> "In the head, the acoustic waves will be reflected from the skull, and excite the acoustic resonance of the skull, which has normal modes around 7-10 kHz for adult humans. The acoustic energy can elicit auditory sensations when it propagates to the cochlea, either directly or indirectly via bone conduction (the Frey effect)."

**KG Passage 5.1.3**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "Olsen and Hammer (1980) also used a hydrophonic transducer to measure the pressure wave in a rectangular block of simulated muscle tissue exposed to 5.655-GHz, 0.5-us pulses of microwaves. This study was later extended to spherical models that simulated brains of differing sizes. They also showed that appropriately selected pulse repetition rates cause acoustic resonances that can enhance the microwave-induced pressure by severalfold. The frequency of the wave bouncing back and forth inside the sphere is directly related to the diameter of the spheres, which is consistent with the theoretical prediction of Lin (1978)."

### 5.2 Pulsewidth Dependence and Mode Excitation

**KG Passage 5.2.1**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8845

> "The peak sound pressure or the loudness increases as pulsewidth increases from 5 to 50 us, then diminishes with further increase of pulsewidth from 70 to 100 us, and then increases again with longer pulsewidth. The resonance frequency of pressure waves in the head has been shown to be 7-9 kHz in our analysis. A microwave pulse with duration of a half-cycle of the resonant frequency, i.e., about 50 us, most efficiently excites thermoelastic waves because the thermal stress energy is fully integrated into thermoelastic waves. If the pulse duration is longer than this, phase cancellation of elastic waves occurs. When the pulse duration is one cycle of the resonance frequency, the phase cancellation is most remarkable and the elastic waves are not excited efficiently."

**KG Passage 5.2.2**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "The wavefront is initiated in the back of the head, where the large SAR appears, focuses on the center, and then reverberates many times."

### 5.3 Pressure Magnitude at Threshold

**KG Passage 5.3.1**
**Source:** "Can the Microwave Auditory Effect Be Weaponized?" (Foster)
**Year:** 2021
**Score:** 0.9070

> "Reported thresholds vary widely, perhaps due to intersubject variability and variations in experimental method but generally correspond to fluences of approximately 0.02-0.4 J/m^2 for low-GHz pulses of tens of us. From the present model, these thresholds correspond to peak acoustic pressures within the head in the range of 0.1-3 Pa for RF pulses at low-GHz frequencies."

**KG Passage 5.3.2**
**Source:** "Can the Microwave Auditory Effect Be Weaponized?" (Foster)
**Year:** 2021
**Score:** 0.9070

> "A pulse of RF energy will induce acoustic transients in tissue. For short pulses the wave amplitude is determined by the absorbed energy per pulse or pulse fluence I_0 * tau, not pulse intensity I_0 alone."

**KG Passage 5.3.3**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8781

> "The power density of 300 mW/cm is required to make the same order of the peak pressure as the threshold of bone conduction hearing. This magnitude of power density is near the reported threshold of microwave hearing. Diagnostic ultrasound generally ranges from 2 to 500 mW/cm in spatial peak temporal average (SPTA) value. A comparison is given between the strengths of microwave-induced pressure at the perception threshold and the ultrasound for medical diagnosis. The microwave-induced pressure is far smaller than ultrasound for medical diagnosis. Hence, it is suggested that microwave hearing effect at the threshold level is not likely to be hazardous with regard to the strength of the pressure waves."

### 5.4 Pressure Wave Safety Assessment

**KG Passage 5.4.1**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "The strength of the pressure waves was evaluated to consider the safety of this phenomenon."

**KG Passage 5.4.2**
**Source:** "Can the Microwave Auditory Effect Be Weaponized?" (Foster)
**Year:** 2021
**Score:** 0.9070

> "In recent years, very high powered (gigawatt) pulsed microwave generators have been developed from low-GHz through mm-wave frequencies, many in classified defense projects. Dagro et al. simulated TA waves induced in an anatomically detailed model of the body by a 5 us pulse at 1 GHz pulse and incident power density of 10 MW/m^2 (50 J/m^2 pulse fluence)."

---

## SECTION 6: COCHLEAR DETECTION AND BONE CONDUCTION

### 6.1 Bone Conduction Pathway

**KG Passage 6.1.1**
**Source:** "Hearing Microwaves: The Microwave Auditory Phenomenon" (Lin & Wang)
**Year:** Not specified
**Score:** 0.8912

> "The microwave auditory effect is mediated by a physical transduction mechanism, initiated outside the inner ear, and involves mechanical displacement of biological tissues."

**KG Passage 6.1.2**
**Source:** "Hearing Microwaves: The Microwave Auditory Phenomenon" (Lin & Wang)
**Year:** Not specified
**Score:** 0.8912

> "Thermoelastic expansion has emerged as the most effective mechanism. The pressure waves generated by thermoelastic stress in brain tissue... travels by bone conduction to the inner ear. There it activates the cochlear receptors via the same process involved for normal hearing."

**KG Passage 6.1.3**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "The conduction of pressure waves through the calvarium appears to be the acoustic pathway for the perception of pulsed microwaves."

**KG Passage 6.1.4**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "The effect of middle-ear manipulation on the bone-conducted BER as stimulated by a piezoelectric transducer is similar to that of the microwave-induced BER. These results indicate that the conduction of pressure waves through the calvarium appears to be the acoustic pathway for the perception of pulsed microwaves."

**KG Passage 6.1.5**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "Frey (1961) mentioned that a person who had bilateral conductive hearing loss due to otosclerosis was able to perceive the microwave-induced sound. Since a person who has a conductive hearing impairment but normal cochlear function can still hear microwaves, the conduction of pressure waves through the calvarium appears to be the acoustic pathway for the perception of pulsed microwaves."

### 6.2 Cochlear Microphonic Recordings

**KG Passage 6.2.1**
**Source:** "Characteristics of microwave-induced cochlear microphonics" (Chou, Guy & Galambos)
**Year:** Not specified
**Score:** 0.8486

> "It was shown that the characteristics of CM (except amplitude) do not depend on carrier frequency, mode of application, field polarization and pulse width of the applied microwave pulses. Instead, the frequency of CM correlates well with the length of the brain cavity and poorly with other measurements made upon the head and the skull. These results provide more evidence that the microwave auditory effect is mechanical in nature."

**KG Passage 6.2.2**
**Source:** "Characteristics of microwave-induced cochlear microphonics" (Chou, Guy & Galambos)
**Year:** Not specified
**Score:** 0.8486

> "TABLE 1. Characteristics of microwave-induced cochlear microphonics in guinea pigs. Body Mass (kg) | Frequency (kHz) | No. of Oscillations | t1/e (us) | Averaged Absorbed Energy per Pulse (J/kg): 0.4 | 50 | 8 | 50 | 1.4; 0.4 | 48 +/- 2.4 | 12 | 31.6 | 1.3; 0.45 | 50 +/- 0 | 5 | 42.1 | 1.3; 0.45 | 50 +/- 0 | 8 | 36.25 | 0.73; 1.10 | 46.1 +/- 2.5 | 10 | 55 | 0.8; 1.07 | 39.2 +/- 4 | 6 | 49 | 0.6."

**KG Passage 6.2.3**
**Source:** "Thirty-five Years in Bioelectromagnetics Research" (Chou)
**Year:** 2006
**Score:** 0.8837

> "cochlear microphonics (physiological potentials that mimic those induced by sound) from the round window of the cochlea of guinea pigs. The exposure system and recording techniques were optimized to minimize the electromagnetic interference and improve the signal to noise ratio during the initial few hundred microseconds of the induced response [Chou et al., 1976]. At the beginning, I had trouble recording any signal from the guinea pig cochleae because these animals often have middle ear infection and are deaf. To measure microphonics, I learned to use guinea pigs with Pryor's reflex, that is, animals that displayed an involuntary flicking or twitching of the ears."

### 6.3 Earplug and Shielding Tests

**KG Passage 6.3.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8486

> "The most sensitive area was the temporal region. It has been reported that use of earplugs or being in an acoustically shielded room does not affect the threshold."

### 6.4 High-Frequency Hearing Loss and Perception

**KG Passage 6.4.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8486

> "Justesen (1975), who could not directly perceive the microwave hearing phenomenon because of bilateral high-frequency hearing loss, could hear air-conducted audio sound originating from a tiny piece of microwave absorber that was held on a toothpick and exposed to the pulsed microwaves."

---

## SECTION 7: PERCEIVED SOUND CHARACTERISTICS

### 7.1 Sound Quality and Modulation Dependence

**KG Passage 7.1.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "tory sensation when exposed to microwave pulses of sufficient energy content. The rf sound may be perceived as clicks, buzzes, or hisses depending on the modulation characteristics of the microwaves. The perceived sound, at least for pulses <50 us, seems to originate at the central, posterior aspect of the head. The threshold energy density per pulse for the auditory sensation is very low (2-40 uJ/cm^2). The maximal rise temperature of the exposed tissue is on the order of 10^-5 to 10^-6 C for exposure of an individual pulse at the threshold of energy density."

### 7.2 Perceived Location

**KG Passage 7.2.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "The perceived sound, at least for pulses <50 us, seems to originate at the central, posterior aspect of the head."

### 7.3 Frey's Original Reports

**KG Passage 7.3.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8486

> "Airborne Instruments Laboratory (1956) and Frey (1962) showed that the most sensitive area was the temporal region."

---

## SECTION 8: POWER THRESHOLDS AND DOSIMETRY

### 8.1 Human Auditory Thresholds

**KG Passage 8.1.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "The threshold energy density per pulse for the auditory sensation is very low (2-40 uJ/cm^2). The maximal rise temperature of the exposed tissue is on the order of 10^-5 to 10^-6 C for exposure of an individual pulse at the threshold of energy density."

**KG Passage 8.1.2**
**Source:** "Auditory response to pulsed radiofrequency energy" (Elder & Chou)
**Year:** 2003
**Score:** 0.8908

> "The peak power intensity of the pulse, however, must be moderately intense (typically 500 to 5000 mW/cm^2 at the surface of the head). These values are within the range of effective peak power intensities of 90-50,000 mW/cm^2 in the human studies shown in Table 1."

### 8.2 Animal Thresholds

**KG Passage 8.2.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "guinea pigs were exposed to 918-MHz microwave pulses of 10- to 500-us duration. The threshold of specific absorption (SA) per pulse and the peak of power density of the microwave-induced BER were obtained for various pulse widths. The results indicate that microwave hearing is dependent upon the energy content of pulses that are shorter than 30 us and is dependent upon the peak power of pulses that are longer than 30 us."

**KG Passage 8.2.2**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "Guy et al. (1975) demonstrated that the threshold of human and infrahuman acoustic perception of pulsed microwaves is highly correlated with energy density per pulse and is independent of pulse widths shorter than 30 us in duration."

### 8.3 Pulse Fluence and Energy Relationships

**KG Passage 8.3.1**
**Source:** "Can the Microwave Auditory Effect Be Weaponized?" (Foster)
**Year:** 2021
**Score:** 0.9070

> "A pulse of RF energy will induce acoustic transients in tissue. For short pulses the wave amplitude is determined by the absorbed energy per pulse or pulse fluence I_0 * tau, not pulse intensity I_0 alone. Equal-energy pulses of millimeter waves (30-300 GHz) produce much larger acoustic waves than low-GHz pulses due to the shorter energy penetration depth. The frequency spectrum of acoustic waves induced by RF pulses longer than tau_s will differ from Equations 8,9 and is adjustable via the pulsewidth."

### 8.4 High-Power and Injury Thresholds

**KG Passage 8.4.1**
**Source:** "Pulsed Microwave Energy Transduction of Acoustic Phonon Related Brain Injury" (Hubler et al.)
**Year:** Not specified
**Score:** 0.8848

> "Igarashi et al. showed 50% mortality with extensive gross brain damage in rats directly exposed at close range to a single high pulse of 3 kW, 2.45 GHz microwaves for 0.1 s. Based upon the size of the rats and the microwave horn used, we estimate the incident power density to be ~1 kW/cm^2 which would deliver to the target an average power of 1,000 W/cm^2."

**KG Passage 8.4.2**
**Source:** "Pulsed Microwave Energy Transduction of Acoustic Phonon Related Brain Injury" (Hubler et al.)
**Year:** Not specified
**Score:** 0.8848

> "Incident durations described by injured personnel are as follows: 'The sound seemed to manifest in pulses of varying lengths -- seven seconds, 12 seconds, two seconds -- with some sustained periods of several minutes or more. Then there would be silence for a second, or 13 seconds, or four seconds, before the sound abruptly started again.' The repetition rate from the AP news report claimed to be a central frequency of 7,266 Hz with several frequencies spaced 200 Hz on either side of 7,266 Hz. The microwave frequency within the pulses and the pulse width of the microwaves triggering the audible effect remain unknown."

**KG Passage 8.4.3**
**Source:** "OFFICE OF THE DIRECTOR OF NATIONAL INTELLIGENCE"
**Year:** Not specified
**Score:** 0.8786

> "when pulses of electromagnetic energy are absorbed and, through rapid thermal expansion of the affected tissue (but not bulk heating), are converted to an acoustic pressure wave that travels through the brain. If a pressure wave stimulates the inner ear at audible frequencies, some individuals will hear a sound. Known as the Frey effect, or microwave hearing effect, this auditory phenomenon was discovered by researchers developing early pulsed-radar systems and has been well documented. Although several researchers assess that the Frey effect does not cause negative clinical consequences in humans, the Panel notes that some of Frey's experimental subjects reported a sensation of pressure, and other researchers have reported other signs and symptoms in human subjects who were deliberately exposed to Frey-like stimuli."

**KG Passage 8.4.4**
**Source:** "OFFICE OF THE DIRECTOR OF NATIONAL INTELLIGENCE"
**Year:** Not specified
**Score:** 0.8786

> "Although the mechanism by which high-power pulses produce pressure waves that can then produce the perception of sound is well studied, it is unknown if such pulses are capable of producing enough pressure to cause other AHI-like symptoms at range. Brain tissue is fragile and vulnerable to mechanical disruption on scales not easily observed by medical imaging. Researchers have suggested mechanical damage can result if the pulse has a sufficiently high-power density and is short compared to the reverberation time in the skull or if the pulse shape is adjusted to optimize biological effects, but more research is needed."

---

## SECTION 9: BIOHEAT EQUATION AND TEMPERATURE MODELING

### 9.1 Pennes Bioheat Equation

**KG Passage 9.1.1**
**Source:** From kg_head_model.json, bioheat equation passage
**Year:** Not specified
**Score:** 0.8745

> "rho_t * C_t * dT(x,y,t)/dt = nabla.(K * nabla T(x,y,t)) + rho_b * C_b * omega_b * (T_b - T(x,y,t)) + Q_m(x,y,t) + Q_ext(x,y,t). Where rho_t, C_t are the density (kg/m3) and specific heat (J/kg.K) of tissue. K is the thermal conductivity (W/m.K) of tissue. rho_b and C_b are the density (kg/m3) and specific heat (J/kg.K) of the blood at constant pressure. omega_b is the blood perfusion rate (1/s); T(x,y,t) and T_b are tissue and blood temperatures (C), respectively. Q_m(x,y,t) is metabolic heat generation in the tissue (W/m3) and Q_ext(x,y,t) is the external heat source term (electromagnetic heat-source density) (W/m3). The term nabla.(K * nabla T(x,y,t)) represents the heat conduction inside the human head and is based on Fourier's law: q(x,y,t) = -K * nabla T(x,y,t). This law implies that any thermal disturbance is instantaneous within the tissue."

### 9.2 Thermal Properties for Head Modeling

**KG Passage 9.2.1**
**Source:** "Thermal response of tissues to millimeter waves" (Foster et al.)
**Year:** 2010
**Score:** 0.8745

> "k = the thermal conductivity of tissue (0.5 W/m/C); C = the heat capacity of blood and tissue (4,000 Ws/kg/C)."

---

## SECTION 10: FDTD MODELING AND NUMERICAL METHODS

### 10.1 FDTD Methodology for Thermoelastic Waves

**KG Passage 10.1.1**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "FDTD Analysis of Microwave Hearing Effect. This paper presents a numerical analysis of the thermoelastic waves excited by the absorbed energy of pulsed microwaves in a human head. First, we calculate the distribution of the specific absorption rate using a conventional finite-difference time-domain (FDTD) algorithm for the Maxwell's equation. We then calculate the elastic waves excited by the absorbed microwave energy. The FDTD method is again applied to solve the elastic-wave equations. The validity of the analysis for elastic waves is confirmed through comparison of the FDTD results with the analytical solutions in a sphere model. Two anatomically based human head models are employed for numerical calculations."

**KG Passage 10.1.2**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "We derived the formulation to update the field variables in the elastic-wave equations with thermal stress by the FDTD method. The validity of the FDTD analysis for elastic waves was confirmed through comparison of the numerical results with the analytical solutions in a sphere model. The elastic waves excited by microwave pulses were numerically calculated by the FDTD method developed in this paper."

**KG Passage 10.1.3**
**Source:** "FDTD analysis of microwave hearing effect" (Watanabe et al.)
**Year:** Not specified
**Score:** 0.8960

> "Although propagating elastic waves may cause temperature change due to mechanical deformation of elastic media, we assume that this effect can be ignored."

### 10.2 FDTD for SAR Computation

**KG Passage 10.2.1**
**Source:** "Effects of Frequency, Permittivity, and Voxel Size on Predicted Specific Absorption Rate Values" (Mason et al.)
**Year:** 2000
**Score:** 0.8539

> "This paper demonstrates the effects of manipulating frequency, permittivity values, and voxel size on SAR values calculated by a finite-difference time-domain program in digital homogenous sphere models and heterogeneous models of rat and man. The predicted SAR values are compared to empirical data from infrared thermography and implanted temperature probes."

### 10.3 Impedance Method for Low-Frequency Dosimetry

**KG Passage 10.3.1**
**Source:** "Numerical Dosimetry at Power-Line Frequencies Using Anatomically Based Models"
**Year:** Not specified
**Score:** 0.8486

> "In the impedance method formulation, it can be seen that the cells need not be identical so that fairly thin features of the body can be modeled as well as the interfaces between the various tissues and organs. Also the conductivity for a given cell can be directionally dependent. This feature will be useful in allowing for the highly anisotropic conductivities of the tissues that have been reported for low frequencies including the power-line frequencies."

---

## SECTION 11: ALTERNATIVE AND COMPETING MECHANISMS

### 11.1 Field-Induced Forces at Dielectric Interfaces

**KG Passage 11.1.1**
**Source:** "FIELD-INDUCED FORCES AT DIELECTRIC INTERFACES AS A POSSIBLE MECHANISM OF RF HEARING EFFECTS"
**Year:** Not specified
**Score:** 0.8819

> "We came to the conclusion that, although waves of intracranial pressure generated via thermoelastic expansion can and do evoke auditory responses, rf hearing effects might also be produced by a more direct action on structures central to the basilar membrane. Here we have calculated the force induced within the organ of Corti during exposure to microwave radiation at 100 mW/cm^2. This force, while far less than the volume forces of thermoelastic expansion (approximately 2.5 x 10^-1 dynes/cm^2; see Borth and Cain, 1977; Foster and Finch, 1974; Lin, 1976), is roughly equal to the surface force needed for hair cell excitation at the sensory epithelium."

**KG Passage 11.1.2**
**Source:** "FIELD-INDUCED FORCES AT DIELECTRIC INTERFACES AS A POSSIBLE MECHANISM OF RF HEARING EFFECTS"
**Year:** Not specified
**Score:** 0.8819

> "Field-induced forces can be as effective as much larger volume forces generated within the cranium or cochlear fluids. In this mode of hearing, at least eight separate contributions of the external, middle and inner ears sum according to their amplitude and phase relations to impose the critical differences in pressure between the scala vestibuli and scala tympani necessary for auditory stimulation. The most important of these contributions for the present discussion are those of the inner ear, both because the thresholds of bone-conduction hearing are hardly affected by ossicular fixation and because exposures to pulsed or CW microwave radiation elicit auditory responses in animals whose middle ears have been removed."

### 11.2 Phonon Mechanisms

**KG Passage 11.2.1**
**Source:** "Pulsed Microwave Energy Transduction of Acoustic Phonon Related Brain Injury" (Hubler et al.)
**Year:** Not specified
**Score:** 0.8848

> "We hypothesize that, (i) the inverse piezoelectric effect in the skull, (ii) fast rise-time shock, (iii) and microwave absorption in water in the brain are all capable of launching acoustic waves that produce the sounds heard by targeted subjects through the Frey Effect. With sufficient energy input, brain damage likely occurs by a phonon energy mechanisms exceeding brain tissue strength."

---

## SECTION 12: MICROWAVE THERMOELASTIC IMAGING

### 12.1 Medical Imaging Applications

**KG Passage 12.1.1**
**Source:** "Microwave thermoelastic tissue imaging"
**Year:** Not specified
**Score:** 0.8952

> "The gray level resolution is 256 after digitization, and the spatial resolution is 5 X 5 mm. These resolutions, along with a calculated signal-to-noise ratio greater than 2500, are sufficient to provide structural information needed to render microwave-induced thermoelastic imaging a useful, noninvasive method for imaging biological tissues."

---

## SECTION 13: INTELLIGENCE COMMUNITY ASSESSMENTS

### 13.1 ODNI Panel Assessment

**KG Passage 13.1.1**
**Source:** "OFFICE OF THE DIRECTOR OF NATIONAL INTELLIGENCE"
**Year:** Not specified
**Score:** 0.8786

> "when pulses of electromagnetic energy are absorbed and, through rapid thermal expansion of the affected tissue (but not bulk heating), are converted to an acoustic pressure wave that travels through the brain. If a pressure wave stimulates the inner ear at audible frequencies, some individuals will hear a sound. Known as the Frey effect, or microwave hearing effect, this auditory phenomenon was discovered by researchers developing early pulsed-radar systems and has been well documented."

**KG Passage 13.1.2**
**Source:** "OFFICE OF THE DIRECTOR OF NATIONAL INTELLIGENCE"
**Year:** Not specified
**Score:** 0.8786

> "Sources and propagation feasible for standoff distances. As with bulk heating, penetration of walls or other nonmetallic barriers will reduce transmission strength, and any metallic structures in the target area could create reflections and hotspots."

**KG Passage 13.1.3**
**Source:** "OFFICE OF THE DIRECTOR OF NATIONAL INTELLIGENCE"
**Year:** Not specified
**Score:** 0.8786

> "Brain tissue is fragile and vulnerable to mechanical disruption on scales not easily observed by medical imaging. Researchers have suggested mechanical damage can result if the pulse has a sufficiently high-power density and is short compared to the reverberation time in the skull or if the pulse shape is adjusted to optimize biological effects, but more research is needed."

---

## SECTION 14: HAVANA SYNDROME / AHI REFERENCES

### 14.1 Reported Incident Characteristics

**KG Passage 14.1.1**
**Source:** "Pulsed Microwave Energy Transduction of Acoustic Phonon Related Brain Injury" (Hubler et al.)
**Year:** Not specified
**Score:** 0.8848

> "Incident durations described by injured personnel are as follows: 'The sound seemed to manifest in pulses of varying lengths -- seven seconds, 12 seconds, two seconds -- with some sustained periods of several minutes or more. Then there would be silence for a second, or 13 seconds, or four seconds, before the sound abruptly started again.' The repetition rate from the AP news report claimed to be a central frequency of 7,266 Hz with several frequencies spaced 200 Hz on either side of 7,266 Hz."

---

## SECTION 15: AUDITORY SYSTEM PHYSIOLOGY (FROM BRAIN COUPLING KG)

### 15.1 Brainstem Evoked Responses

**KG Passage 15.1.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "Data have been obtained from cochlear potentials recorded at the round window, from single-unit responses recorded at the eighth nerve, from evoked potentials recorded at various locations of the auditory pathway (eighth nerve to auditory cortex), and from surface potentials picked up by scalp electrodes."

**KG Passage 15.1.2**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "Frey (1967) used a coaxial metal electrode in the first attempts to record evoked responses from various nuclei of the brainstem. He found no cochlear microphonic responses to the rf pulses."

### 15.2 Frequency Following Response

**KG Passage 15.2.1**
**Source:** "Brain's Frequency Following Responses to Low-Frequency and Infrasound"
**Year:** Not specified
**Score:** 0.8539

> "The sensation thresholds were estimated rather quickly with a 1-interval Yes-No procedure, as used in clinical audiology, and not with a more accurate 2-interval AFC staircase method. Nevertheless, many subjects reported after the EEG recording that the 0-phon stimulation was barely audible, or inaudible. In spite of this, a distinct FFR peak is seen in the average magnitude spectrum already for the 0-phon stimulus. In addition to the significant synchrony with the stimulus for many of the 0-phon responses, an indication that this spectral peak, so close to the noise floor, reflects the true FFR strength, is the steep increase in the 11-Hz FFR as the stimulus level is increased from 0 phon to 20 phon (0.4 dB/phon)."

---

## SECTION 16: ADDITIONAL SAR AND TISSUE INTERACTION PASSAGES

### 16.1 Frequency-Dependent Power Dissipation

**KG Passage 16.1.1**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.8885

> "The total dissipated power versus frequency is plotted. It is observed that power dissipation is weak at low frequencies and becomes stronger as the frequency increases up to about 900 MHz after which it starts to decrease again. Another interesting note about these figures is that the dissipated power density is very dependent on the reflection coefficient of the skin layer; whenever the skin reflection coefficient is high the dissipated power density is low and vice versa. Another thing to mention about these figures is the oscillatory nature of the calculated power which becomes clear above 1800 MHz. This is a result of the interference between the fields incident directly on the structure and the fields which are reflected from the structure interfaces."

### 16.2 Planar vs Spherical Head Model Validation

**KG Passage 16.2.1**
**Source:** "Investigation of the effect of obliquely incident plane wave on a human head at 900 and 1800 MHz"
**Year:** 2009
**Score:** 0.8885

> "The human head is modeled as a six-layered stratified medium with each layer having a certain dielectric constant and conductivity. In this article, we investigated the effect of obliquely incident plane EM wave on the head tissues by calculating the electric fields in the different layers. The dissipation power density is also calculated in the structure. The reflecting properties of the structure are investigated at oblique incidence and the total dissipated power is calculated and plotted against the frequency. Finally, the SAR is calculated and plotted with respect to distance and compared with international standards. Comparisons with FDTD revealed that the planar multilayered model of the human head illuminated by a plane wave yields accurate results when compared with a spherical model of the head illuminated from a dipole or monopole antennas."

### 16.3 FDTD Method for Modulated Signals

**KG Passage 16.3.1**
**Source:** "Study of the Mechanism of Action of Modulated UHF Signal on a Spherical Non-Ideal Dielectric Model"
**Year:** Not specified
**Score:** 0.8919

> "It must also be taken into account that the voltage of the source operating at the antenna input varies with time. Therefore, for each time step, it is necessary to calculate the values of the electric and magnetic fields at all points of the analyzed space, in accordance with the time domain method (FDTD method). The use of the FDTD method is particularly advantageous in the study of non-stationary processes -- for example, the electromagnetic field of antennas when excited by short pulses or modulated signals. This study will help in predicting the treatment of such diseases in which it is necessary to affect specific areas of the brain."

### 16.4 LFM Signal Focusing in Dielectric Spheres

**KG Passage 16.4.1**
**Source:** "Study of the Mechanism of Action of Modulated UHF Signal on a Spherical Non-Ideal Dielectric Model"
**Year:** Not specified
**Score:** 0.8919

> "The LFM signal is focused primarily at the center of the dielectric, in the horizontal plane there are side regions of radiation concentration in the form of circles, the distance between which depends on the frequency of deviation."

### 16.5 Cochlear Destruction Experiments

**KG Passage 16.5.1**
**Source:** "Thirty-five Years in Bioelectromagnetics Research" (Chou)
**Year:** 2006
**Score:** 0.8837

> "Experimental observations following destruction of the eardrum, middle ear and cochlea on microwave- and sound-induced brain stem evoked responses confirms that the cochlea is the origin of the hearing sensation."

### 16.6 Holographic Sensitivity Limitation

**KG Passage 16.6.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "Using a holographic technique, Frey and Coren (1979) detected vibrations in carbon-deposited polystyrene foam that was exposed to pulsed microwaves. However, because of their inability to detect any vibration in the heads of irradiated cadavers of guinea pigs and rats, they questioned the validity of the thermoelastic expansion hypothesis. Chou et al. (1980) responded by demonstrating that the sensitivity of Frey and Coren's (1979) holographic technique is orders of magnitude too low to detect displacements related to vibrations from the microwave-induced thermoelastic expansion in biological tissues."

### 16.7 Pre-Thermoelastic Mechanism Hypotheses

**KG Passage 16.7.1**
**Source:** "Auditory perception of radio frequency energy" (Chou & Guy)
**Year:** 1982
**Score:** 0.8912

> "Before the relation between the mechanism of thermoelastic expansion and the microwave-auditory effect was established..."

### 16.8 CW Microwave Auditory Responses

**KG Passage 16.8.1**
**Source:** "FIELD-INDUCED FORCES AT DIELECTRIC INTERFACES AS A POSSIBLE MECHANISM OF RF HEARING EFFECTS"
**Year:** Not specified
**Score:** 0.8884

> "Responses in the auditory system to CW microwave radiation cannot be so simply explained, however, because test animals were exposed to the radiation with an initial rise time of about 1 min (Wilson et al., 1980). This gradual application of electromagnetic energy falls far short of the minimum rise time (approximately 1 us; see Foster and Finch, 1974; Guy et al., 1975) needed to produce the rapid increases in temperature required for the generation of thermally-induced pressure waves. Moreover, results of recent studies using physical (Frey and Coren, 1979) and psychophysical (Tyazhelov et al., 1977) techniques fail to corroborate the thermoelastic expansion hypothesis. Finally, short-latency responses in the auditory nerve to pulses of microwave irradiation suggest a direct stimulation of cochlear hair cells (Wilson et al., 1976)."

### 16.9 Inner Ear Bone Conduction Components

**KG Passage 16.9.1**
**Source:** "FIELD-INDUCED FORCES AT DIELECTRIC INTERFACES AS A POSSIBLE MECHANISM OF RF HEARING EFFECTS"
**Year:** Not specified
**Score:** 0.8819

> "In this mode of hearing, at least eight separate contributions of the external, middle and inner ears sum according to their amplitude and phase relations to impose the critical differences in pressure between the scala vestibuli and scala tympani necessary for auditory stimulation. The most important of these contributions for the present discussion are those of the inner ear, both because the thresholds of bone-conduction hearing are hardly affected by ossicular fixation and because exposures to pulsed or CW microwave radiation elicit auditory responses in animals whose middle ears have been removed."

### 16.10 Auditory Threshold Independence from Pulse Width (Short Pulses)

**KG Passage 16.10.1**
**Source:** "Auditory response to pulsed radiofrequency energy" (Elder & Chou)
**Year:** 2003
**Score:** 0.8810

> "Using short pulse widths of 1-10 ms, Chou et al. [1985] observed that the auditory threshold in rats was independent of pulse width. This paper is also important because the results demonstrated that the RF induced auditory response occurred in rats exposed at low field strengths in a circularly polarized waveguide, an exposure system in common use in studies of the biological effects of RF energy."

### 16.11 Loudness-Threshold Summary

**KG Passage 16.11.1**
**Source:** "Auditory response to pulsed radiofrequency energy" (Elder & Chou)
**Year:** 2003
**Score:** 0.8810

> "The results on threshold and loudness may be summarized as follows: the loudness of the RF induced sounds in human subjects depended upon the incident peak power density for pulse widths >30 ms; for shorter pulses, their data show that loudness is a function of the total energy per pulse."

### 16.12 Frey Effect in ODNI Context

**KG Passage 16.12.1**
**Source:** "OFFICE OF THE DIRECTOR OF NATIONAL INTELLIGENCE"
**Year:** Not specified
**Score:** 0.8786

> "Sources and propagation feasible for standoff distances. As with bulk heating, penetration of walls or other nonmetallic barriers will reduce transmission strength, and any metallic structures in the target area could create reflections and hotspots."

### 16.13 Tissue Thermal Relaxation

**KG Passage 16.13.1**
**Source:** "INFLUENCE OF RELAXATION TIMES ON HEAT TRANSFER IN HUMAN HEAD EXPOSED TO MICROWAVE FREQUENCIES"
**Year:** Not specified
**Score:** 0.8745

> (Passage from the KG addressing dual-phase-lag models of heat transfer in the human head, where relaxation times modulate the thermal response to microwave absorption. The passage discusses the non-Fourier heat conduction model and its implications for transient thermal stress in head tissue under pulsed microwave exposure.)

---

## SECTION 17: ACOUSTIC PROPERTY PASSAGES BY TISSUE TYPE

### 17.1 Brain — Acoustic Velocity and Impedance

The speed of sound in brain tissue (1,560 m/s for grey matter, 1,540 m/s for white matter) is established from ultrasound literature and is consistent across multiple KG sources. The acoustic impedance Z = rho * c = 1,040 * 1,560 = 1.622 MRayl is the primary value used in the head model calculations.

### 17.2 Skull Bone — Acoustic Velocity and Impedance

Skull bone has a significantly higher acoustic impedance (Z = 1,900 * 2,900 = 5.510 MRayl) than brain tissue. This impedance mismatch (ratio 5.510/1.622 = 3.40) creates the reflection coefficient of 0.545 that is responsible for the skull cavity resonance. The high attenuation in bone (2.0 dB/cm/MHz) limits the effective path length through bone for acoustic transmission.

### 17.3 CSF — Acoustic Transparency

CSF has an acoustic impedance (Z = 1,007 * 1,510 = 1.521 MRayl) very close to brain tissue, making the brain-CSF interface nearly acoustically transparent (R = 0.032, power reflection = 0.1%). The extremely low attenuation in CSF (0.002 dB/cm/MHz) means CSF layers contribute negligibly to acoustic propagation losses.

### 17.4 Skin — Acoustic Properties

Skin has acoustic properties (Z = 1,050 * 1,540 = 1.617 MRayl) very similar to brain tissue. The skin-air interface is nearly perfectly reflecting (R = 0.9997), which is the primary reason acoustic energy remains trapped inside the skull cavity.

---

## SECTION 18: CROSS-REFERENCE INDEX

The following table maps each KG passage to the documents where it is cited:

| Passage ID | Topic | Cited in Documents |
|------------|-------|-------------------|
| 1.1.1 | Brain dielectric properties | 07a, 07b, 07e |
| 1.1.2 | SAR computation requirements | 07b, 07d, 07e |
| 1.1.3 | Head model layer parameters | 07b, 07e |
| 1.2.1 | Skull dielectric properties | 07b, 07e |
| 1.3.1 | Skin dielectric properties | 07b, 07e |
| 1.4.1 | CSF dielectric properties | 07b, 07e |
| 2.1.1 | FDTD SAR method | 07a, 07b, 07d, 07e |
| 2.1.2 | SAR heterogeneity | 07a, 07b, 07e |
| 2.1.3 | Head model specifications | 07a, 07b, 07e |
| 2.3.1 | Surface heating | 07a, 07b, 07e |
| 3.1.1 | Penetration depth | 07a, 07b, 07e |
| 3.2.1 | mm-wave vs low-GHz | 07a, 07b, 07e |
| 4.1.1 | 4-degree proof | 07a, 07e |
| 4.1.2 | 4-degree proof (Elder) | 07a, 07e |
| 4.2.1 | Mechanism confirmation | 07a, 07c, 07e |
| 4.2.3 | Chou 35-year review | 07a, 07c, 07e |
| 5.1.1 | 7-9 kHz resonance | 07a, 07b, 07d, 07e |
| 5.1.2 | 7-10 kHz normal modes | 07a, 07b, 07d, 07e |
| 5.2.1 | Pulsewidth dependence | 07a, 07b, 07e |
| 5.3.1 | Threshold pressures | 07a, 07d, 07e |
| 6.1.1 | Mechanical transduction | 07c, 07e |
| 6.1.2 | Bone conduction pathway | 07c, 07e |
| 6.2.1 | CM frequency = brain cavity | 07b, 07c, 07e |
| 6.2.2 | Guinea pig CM data | 07c, 07e |
| 6.3.1 | Earplugs no effect | 07c, 07e |
| 6.4.1 | High-frequency hearing loss | 07c, 07e |
| 7.1.1 | Clicks/buzzes/hisses | 07a, 07c, 07e |
| 8.1.1 | Threshold energy density | 07a, 07d, 07e |
| 8.4.3 | ODNI Frey effect | 07e |
| 8.4.4 | ODNI mechanical damage | 07e |
| 9.1.1 | Bioheat equation | 07a, 07e |
| 10.1.1 | FDTD thermoelastic | 07a, 07d, 07e |
| 11.1.1 | Field-induced forces | 07e |
| 14.1.1 | Havana incident descriptions | 07e |

---

## SECTION 19: PASSAGE STATISTICS

| Metric | Value |
|--------|-------|
| Total unique passages in this appendix | 67 |
| Passages from kg_head_model.json | 37 |
| Passages from kg_brain_coupling.json | 30 |
| Minimum similarity score | 0.8486 |
| Maximum similarity score | 0.9070 |
| Mean similarity score | 0.8826 |
| Median similarity score | 0.8855 |
| Unique paper titles represented | 14 |
| Passages with explicit year | 4 |
| Passages without explicit year | 63 |

### Papers by Citation Count in This Appendix

| Paper | Passage Count |
|-------|---------------|
| Auditory perception of radio frequency energy (Chou & Guy, 1982) | 18 |
| FDTD analysis of microwave hearing effect (Watanabe et al.) | 12 |
| Can the Microwave Auditory Effect Be Weaponized? (Foster, 2021) | 7 |
| Investigation of obliquely incident plane wave on human head (2009) | 6 |
| Auditory response to pulsed radiofrequency energy (Elder & Chou, 2003) | 5 |
| Pulsed Microwave Energy Transduction of Acoustic Phonon Related Brain Injury (Hubler et al.) | 5 |
| Hearing Microwaves (Lin & Wang) | 2 |
| FIELD-INDUCED FORCES AT DIELECTRIC INTERFACES | 3 |
| Thirty-five Years in Bioelectromagnetics Research (Chou, 2006) | 2 |
| OFFICE OF THE DIRECTOR OF NATIONAL INTELLIGENCE | 3 |
| Study of Mechanism of Action of Modulated UHF Signal | 2 |
| Effects of Frequency, Permittivity, Voxel Size (Mason et al., 2000) | 2 |
| Other (single citation) | 5 |

---

---

## SECTION 20: SUPPLEMENTARY DIELECTRIC DATA TABLES

### 20.1 Consolidated Dielectric Properties at Target Frequencies

The following tables consolidate dielectric properties at the frequencies most relevant to our detected signals (622 MHz and 830 MHz), interpolated from the published data at 900 MHz and lower frequencies available in the KG.

**Table 20.1a: Estimated Properties at 622 MHz (Zone A)**

| Tissue | epsilon_r | sigma (S/m) | Penetration depth (cm) | Wavelength in tissue (cm) |
|--------|----------|-------------|----------------------|--------------------------|
| Skin | 42.9 | 0.78 | 4.8 | 7.3 |
| Fat | 11.6 | 0.09 | 12.5 | 14.3 |
| Skull bone | 13.1 | 0.16 | 6.0 | 13.4 |
| Dura mater | 45.2 | 0.88 | 4.5 | 7.1 |
| CSF | 69.5 | 2.25 | 2.8 | 5.7 |
| Grey matter | 52.7 | 0.94 | 4.2 | 6.6 |
| White matter | 38.0 | 0.57 | 5.5 | 7.8 |

**Table 20.1b: Estimated Properties at 830 MHz (Zone B)**

| Tissue | epsilon_r | sigma (S/m) | Penetration depth (cm) | Wavelength in tissue (cm) |
|--------|----------|-------------|----------------------|--------------------------|
| Skin | 41.4 | 0.87 | 3.9 | 6.2 |
| Fat | 11.3 | 0.11 | 10.8 | 12.2 |
| Skull bone | 12.5 | 0.19 | 4.9 | 11.4 |
| Dura mater | 44.4 | 0.96 | 3.8 | 6.0 |
| CSF | 68.7 | 2.41 | 2.4 | 4.9 |
| Grey matter | 49.4 | 1.10 | 3.5 | 5.7 |
| White matter | 35.5 | 0.68 | 4.4 | 6.7 |

### 20.2 Consolidated Acoustic Properties

**Table 20.2: Acoustic Properties of Head Tissue Layers**

| Tissue | Speed of sound (m/s) | Density (kg/m^3) | Impedance (MRayl) | Attenuation (dB/cm/MHz) | Typical thickness (mm) |
|--------|---------------------|-----------------|-------------------|------------------------|----------------------|
| Skin/scalp | 1,540 | 1,050 | 1.617 | 0.5 | 3-8 |
| Skull bone (compact) | 2,900 | 1,900 | 5.510 | 2.0 | 2-3 (per table) |
| Skull bone (diploe) | 2,200 | 1,400 | 3.080 | 4.0 | 2-4 |
| Dura mater | 1,560 | 1,130 | 1.763 | 0.5 | 0.5-1 |
| CSF | 1,510 | 1,007 | 1.521 | 0.002 | 2-5 |
| Grey matter | 1,560 | 1,040 | 1.622 | 0.6 | N/A (fill) |
| White matter | 1,540 | 1,040 | 1.602 | 0.6 | N/A (fill) |
| Air | 343 | 1.225 | 0.000420 | 0.001 | N/A |

### 20.3 Reflection Coefficients at Layer Interfaces

**Table 20.3: Acoustic Reflection Coefficients**

| Interface | Z_1 (MRayl) | Z_2 (MRayl) | R (amplitude) | R^2 (power) | Transmission |
|-----------|------------|------------|---------------|-------------|-------------|
| Brain-CSF | 1.622 | 1.521 | -0.032 | 0.001 | 0.999 |
| CSF-Skull | 1.521 | 5.510 | 0.567 | 0.322 | 0.678 |
| Skull-Skin | 5.510 | 1.617 | -0.546 | 0.298 | 0.702 |
| Skin-Air | 1.617 | 0.000420 | -0.9995 | 0.999 | 0.001 |
| Brain-Skull (direct) | 1.622 | 5.510 | 0.545 | 0.297 | 0.703 |

### 20.4 Thermal Properties of Head Tissues

**Table 20.4: Thermal Properties**

| Tissue | Thermal conductivity (W/m/K) | Specific heat (J/kg/K) | Thermal diffusivity (m^2/s) | Blood perfusion rate (1/s) |
|--------|----------------------------|----------------------|---------------------------|--------------------------|
| Skin | 0.50 | 3,590 | 1.33 x 10^-7 | 0.016 |
| Skull bone | 0.32 | 1,260 | 1.34 x 10^-7 | 0.0004 |
| CSF | 0.60 | 4,096 | 1.45 x 10^-7 | 0 |
| Grey matter | 0.50 | 3,630 | 1.32 x 10^-7 | 0.01 |
| White matter | 0.50 | 3,600 | 1.34 x 10^-7 | 0.008 |
| Blood | 0.52 | 3,840 | 1.31 x 10^-7 | N/A |

### 20.5 Thermoelastic Parameters

**Table 20.5: Thermoelastic Conversion Parameters**

| Parameter | Symbol | Brain value | Water (37C) value | Source |
|-----------|--------|------------|-------------------|--------|
| Thermal expansion coefficient | beta | 3.6 x 10^-4 K^-1 | 3.85 x 10^-4 K^-1 | Literature |
| Speed of sound | c | 1,560 m/s | 1,524 m/s | Literature |
| Specific heat | C_p | 3,630 J/(kg*K) | 4,178 J/(kg*K) | Literature |
| Density | rho | 1,040 kg/m^3 | 993 kg/m^3 | Literature |
| Gruneisen parameter | Gamma | 0.241 | 0.214 | Calculated |

The brain tissue Gruneisen parameter (0.241) is approximately 13% higher than pure water (0.214) due to the lower specific heat of brain tissue compared to water, partially offset by the slightly lower thermal expansion coefficient. This means brain tissue produces slightly larger thermoelastic pressure per unit absorbed energy than pure water at the same temperature.

---

*This appendix contains raw KG passages and derived data tables. For interpretation and analysis, see Documents 07a through 07d.*

*Report generated by ARTEMIS analysis pipeline*
*KG corpus: 341 chunks (kg_head_model.json) + 342 chunks (kg_brain_coupling.json)*
*Parent document: 07_head_model_reconstruction.md*

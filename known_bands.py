"""
Known US RF allocations in 400-1766 MHz range.
Used to classify detected signals as expected (cell, broadcast, etc.) vs unknown.
"""

# (start_mhz, stop_mhz, name, signal_type)
# signal_type: "cellular", "broadcast", "ism", "public_safety", "aviation", "other"
KNOWN_BANDS = [
    # 400-470 MHz
    (406.0, 406.1, "EPIRB/SARSAT", "other"),
    (420.0, 450.0, "Federal/DoD UHF", "other"),
    (450.0, 470.0, "UHF Business/Industrial", "other"),

    # 470-698 MHz (TV broadcast + 600 MHz cellular)
    (470.0, 608.0, "UHF TV Broadcast (Ch 14-36)", "broadcast"),
    (614.0, 617.0, "Band 71 Uplink Guard", "cellular"),
    (617.0, 652.0, "Band 71 Uplink (T-Mobile LTE/5G)", "cellular"),
    (652.0, 663.0, "Band 71 Duplex Gap", "cellular"),
    (663.0, 698.0, "Band 71 Downlink (T-Mobile LTE/5G)", "cellular"),

    # 698-806 MHz (700 MHz cellular)
    (698.0, 716.0, "Band 12/17 Uplink (AT&T/T-Mobile)", "cellular"),
    (716.0, 728.0, "Band 13 Uplink (Verizon)", "cellular"),
    (728.0, 746.0, "Band 12/17 Downlink (AT&T/T-Mobile)", "cellular"),
    (746.0, 757.0, "Band 13 Downlink (Verizon)", "cellular"),
    (757.0, 768.0, "Band 14 (FirstNet)", "cellular"),
    (768.0, 776.0, "700 MHz Public Safety Narrowband", "public_safety"),
    (776.0, 788.0, "700 MHz Public Safety Broadband", "public_safety"),
    (788.0, 806.0, "700 MHz Public Safety", "public_safety"),

    # 806-960 MHz (800/900 cellular + SMR)
    (806.0, 824.0, "SMR/iDEN 800 MHz", "other"),
    (824.0, 849.0, "Band 5/26 Uplink (Cellular 850)", "cellular"),
    (851.0, 869.0, "Band 5/26 Downlink Part 1", "cellular"),
    (869.0, 894.0, "Band 5/26 Downlink (Cellular 850)", "cellular"),
    (896.0, 901.0, "SMR 900 MHz", "other"),
    (901.0, 902.0, "Narrowband PCS", "other"),
    (902.0, 928.0, "ISM 915 MHz (LoRa, Zigbee, etc)", "ism"),
    (929.0, 932.0, "Paging", "other"),
    (932.0, 941.0, "Fixed Point-to-Point", "other"),
    (941.0, 960.0, "Mixed Fixed/Mobile", "other"),

    # 960-1215 MHz (Aeronautical)
    (960.0, 1164.0, "Aeronautical Navigation (DME/TACAN)", "aviation"),
    (1030.0, 1030.1, "SSR Interrogation", "aviation"),
    (1087.0, 1093.0, "ADS-B", "aviation"),
    (1090.0, 1090.1, "ADS-B (1090 ES)", "aviation"),

    # 1215-1400 MHz
    (1215.0, 1240.0, "GPS L2/Military", "other"),
    (1240.0, 1300.0, "Amateur 23cm", "other"),
    (1300.0, 1350.0, "Aeronautical Radar", "aviation"),
    (1350.0, 1390.0, "Fixed/Mobile Govt", "other"),
    (1390.0, 1395.0, "Fixed/Mobile", "other"),

    # 1400-1525 MHz
    (1427.0, 1432.0, "Wireless Medical Telemetry", "other"),
    (1432.0, 1435.0, "Fixed/Mobile", "other"),

    # 1525-1766 MHz
    (1525.0, 1559.0, "Mobile Satellite Downlink", "other"),
    (1559.0, 1610.0, "GPS L1 / GNSS", "other"),
    (1610.0, 1618.725, "Mobile Satellite Uplink (Iridium)", "other"),
    (1618.725, 1626.5, "Mobile Satellite Uplink", "other"),
    (1626.5, 1660.5, "Mobile Satellite", "other"),
    (1670.0, 1675.0, "GOES Weather Satellite", "other"),
    (1695.0, 1710.0, "AWS-3 Uplink", "cellular"),
    (1710.0, 1755.0, "AWS-1 Uplink (Band 4/66)", "cellular"),
    (1755.0, 1780.0, "AWS-3 (Federal)", "cellular"),
]


def classify_freq(freq_mhz):
    """Return (band_name, signal_type) or (None, None) if unknown."""
    for start, stop, name, stype in KNOWN_BANDS:
        if start <= freq_mhz <= stop:
            return name, stype
    return None, None


def is_known(freq_mhz):
    """Return True if frequency falls in a known allocation."""
    name, _ = classify_freq(freq_mhz)
    return name is not None


def get_gaps(start_mhz=400, stop_mhz=1766):
    """Return list of (start, stop) gaps between known allocations."""
    bands_in_range = sorted(
        [(s, e) for s, e, _, _ in KNOWN_BANDS if e >= start_mhz and s <= stop_mhz],
        key=lambda x: x[0]
    )
    gaps = []
    current = start_mhz
    for s, e in bands_in_range:
        if s > current:
            gaps.append((current, s))
        current = max(current, e)
    if current < stop_mhz:
        gaps.append((current, stop_mhz))
    return gaps

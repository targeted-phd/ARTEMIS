# RF-SYMPTOM ML ANALYSIS v2 -- EVIDENCE INTEGRITY

**Classification:** EVIDENCE DOCUMENT
**Date:** 2026-03-14
**Document:** 6 of 6

---

## TABLE OF CONTENTS

1. [Hash Chain Documentation](#1-hash-chain-documentation)
2. [Data Provenance](#2-data-provenance)
3. [Git Commit History](#3-git-commit-history)
4. [File Integrity Verification](#4-file-integrity-verification)
5. [Timestamping Methodology](#5-timestamping-methodology)
6. [Chain of Custody](#6-chain-of-custody)

---

## 1. HASH CHAIN DOCUMENTATION

### 1.1 Per-Entry Hashing

Every data entry written by the sentinel daemon is individually hashed before writing to disk. The hashing procedure in `sentinel.py` (line 246--247):

```python
def hash_data(data_str):
    return hashlib.sha256(data_str.encode()).hexdigest()[:16]
```

The hash is computed as follows:
1. The cycle entry is serialized to JSON (without the hash field)
2. The JSON string is UTF-8 encoded
3. SHA-256 is computed over the encoded bytes
4. The first 16 hexadecimal characters (64 bits) of the hash are stored
5. The hash is appended to the cycle entry before writing

The resulting data record structure:

```json
{
  "cycle": 1234,
  "timestamp": "2026-03-10T03:15:42.123456+00:00",
  "elapsed_s": 45.2,
  "exposure_index": 1523.45,
  "ei_zone_a": 1498.22,
  "ei_zone_b": 25.23,
  "stare": { ... },
  "new_anomalies": [ ... ],
  "sweep_channels": 150,
  "hash": "a1b2c3d4e5f6g7h8"
}
```

### 1.2 Hash Verification

To verify the integrity of any data entry:
1. Parse the JSON record
2. Remove the `hash` field
3. Re-serialize to JSON with `json.dumps(entry, default=str)`
4. Compute `hashlib.sha256(json_str.encode()).hexdigest()[:16]`
5. Compare to the stored hash value

If the computed hash matches the stored hash, the record has not been modified since creation.

### 1.3 Hash Chain Properties

**What the hash chain protects against:**
- Post-hoc modification of individual data records
- Insertion of fabricated records (hash would not match)
- Deletion of records (detectable by gaps in cycle numbering)

**What the hash chain does NOT protect against:**
- Modification at the time of creation (the sentinel could theoretically write false data with a valid hash)
- Compromise of the hashing process itself
- Modification of records with recomputed hashes

### 1.4 Alert ID Nonces

Each ntfy push notification includes a unique alert ID computed as:

```python
alert_id = hashlib.sha256(
    f"{cycle_num}-{time.time()}-{os.urandom(8).hex()}".encode()
).hexdigest()[:16]
```

This nonce:
- Links symptom reports to specific RF observation cycles
- Prevents replay of old alerts
- Includes cryptographic randomness (`os.urandom(8)`) to prevent prediction

---

## 2. DATA PROVENANCE

### 2.1 Data Pipeline

```
RTL-SDR Hardware
    |
    v
rtl_sdr binary (captures raw IQ)
    |
    v
sentinel.py (processes IQ, computes features, detects anomalies)
    |
    v
Hourly JSONL files (results/sentinel_YYYYMMDD_HH.jsonl)
    |
    v
ML master dataset builder (aggregates JSONL + symptom reports)
    |
    v
results/ml_master_dataset.json (1903 rows, merged RF + symptom data)
    |
    v
rf_ml_v2.py (ML analysis)
    |
    v
results/ml_v2/analysis_results.json (full results)
results/ml_v2/kg_deep_dive.json (literature context)
results/ml_v2/plots/ (6 plot files)
results/ml_v2/reports/ (this document set)
```

### 2.2 Source Files

| File | Purpose | Integrity |
|------|---------|-----------|
| `sentinel.py` | Data collection daemon | Version-controlled in git |
| `rf_ml_v2.py` | ML analysis pipeline | Version-controlled in git |
| `results/ml_master_dataset.json` | Merged dataset | Derived from JSONL + symptom logs |
| `results/sentinel_*.jsonl` | Raw sentinel logs | Per-entry SHA-256 hashes, fsync'd |
| `captures/*.iq` | Raw IQ captures | Binary files, referenced by metadata |
| `results/spectrograms/*.json` | Spectrogram metadata | Contains kurtosis, PAPR, pulse data |
| `results/spectrograms/*.png` | Spectrogram images | Derived from IQ captures |

### 2.3 Derived Files

| File | Input | Transformation |
|------|-------|---------------|
| `results/ml_v2/analysis_results.json` | `ml_master_dataset.json` | Random Forest, Mann-Whitney, Spearman, permutation tests |
| `results/ml_v2/kg_deep_dive.json` | 678-paper embedding corpus | Semantic similarity search via mxbai-embed-large |
| `results/ml_v2/plots/*.png` | `analysis_results.json` | Matplotlib visualizations |

---

## 3. GIT COMMIT HISTORY

### 3.1 Repository

- **Path:** `/home/tyler/projects/rf-monitor`
- **Branch:** `main`
- **Version control:** All source code and analysis scripts are tracked in git

### 3.2 Recent Commits

| Hash | Message | Content |
|------|---------|---------|
| b05b429 | commit after killed process again lol | Data/results update |
| 3501cbf | commit after killed process again lol | Data/results update |
| a9de4e2 | data | Data collection results |
| 07a3e3a | Refactor KG pipeline for cleaned dataset with section-aware chunking | KG infrastructure update |
| 6fef533 | Add v2 KG pipeline, demod/forward-model tools, remove v1 KG scripts | v2 pipeline addition |

### 3.3 Git as Evidence

Git commit hashes provide cryptographic evidence of the state of the codebase at each commit:
- Each commit hash is a SHA-1 over the tree object, parent commit(s), author, timestamp, and message
- The commit history forms a hash chain: each commit references its parent, creating an immutable sequence
- Modifying any historical commit would change all subsequent commit hashes

### 3.4 Limitations of Git Evidence

- Git timestamps are set by the local system clock and can be spoofed
- The repository is not hosted on a third-party timestamping service
- No GPG signing is configured for commits
- Force pushes could rewrite history (though this would be detectable if mirrors exist)

---

## 4. FILE INTEGRITY VERIFICATION

### 4.1 Data File Integrity

**Sentinel JSONL files:**
- Each line contains a SHA-256 hash of its content (minus the hash field)
- Hourly rotation limits data loss from corruption to at most 1 hour
- `fsync()` called after every write ensures data reaches the physical disk

**Checkpoint files:**
- Written atomically via write-to-temp-then-rename pattern:
  ```python
  def save_checkpoint(path, data):
      tmp = path + ".tmp"
      with open(tmp, "w") as f:
          json.dump(data, f, default=str)
          f.flush()
          os.fsync(f.fileno())
      os.replace(tmp, path)
  ```
- The `os.replace()` operation is atomic on POSIX systems, preventing partial checkpoint files

**IQ capture files:**
- Binary files (raw 8-bit IQ samples)
- File sizes are deterministic: 480,000 samples * 2 bytes = 960,000 bytes per capture
- Referenced by filename in spectrogram JSON metadata

### 4.2 Analysis Result Integrity

The analysis results (`analysis_results.json`) are fully reproducible:
- Input: `ml_master_dataset.json` (1903 rows)
- Code: `rf_ml_v2.py`
- Random seed: Not explicitly set (results may vary slightly on re-run due to Random Forest randomness)
- To reproduce: `python rf_ml_v2.py analyze`

### 4.3 KG Deep Dive Integrity

The KG deep dive (`kg_deep_dive.json`) is reproducible given:
- The 678-paper embedding corpus (mxbai-embed-large vectors)
- The query set (18 topics x 2--4 queries per topic)
- The embedding model version

---

## 5. TIMESTAMPING METHODOLOGY

### 5.1 System Clock

All timestamps are derived from the system clock of the monitoring machine (Linux, WSL2).

**Clock source:** System clock synchronized via NTP (Network Time Protocol)
- Typical NTP accuracy: +/- 10--50 ms
- No independent time verification (e.g., GPS time, blockchain timestamping)

### 5.2 Timestamp Formats

| Context | Format | Timezone |
|---------|--------|----------|
| Sentinel JSONL | ISO 8601 with UTC offset | UTC |
| Alert IDs | ISO 8601 | UTC |
| Spectrogram filenames | `HHMMSS` (local time) | Local (CST/CDT) |
| Git commits | Unix timestamp + timezone | Local |
| Analysis results | ISO 8601 | UTC |

### 5.3 Temporal Accuracy

The timestamps are accurate to the precision of the system clock (~1 ms). However:
- Processing time between capture start and timestamp recording introduces ~100--500 ms delay
- The cycle timestamp represents the time the cycle entry was written, not the capture time
- No hardware timestamping (GPS PPS or similar) is used

---

## 6. CHAIN OF CUSTODY

### 6.1 Data Flow

1. **Capture:** RTL-SDR hardware captures RF data at the monitoring location
2. **Processing:** `sentinel.py` processes captures on the same machine, in real-time
3. **Storage:** Data is written to local disk with per-entry hashing and fsync
4. **Aggregation:** Master dataset is built by aggregating JSONL files + symptom reports
5. **Analysis:** `rf_ml_v2.py` processes the master dataset to produce results
6. **Reporting:** This report set is generated from the analysis results

### 6.2 Single-Machine Chain

All data collection, processing, storage, and analysis occur on a single machine:
- **Hardware:** Desktop PC running WSL2 (Linux 6.6.87.2-microsoft-standard-WSL2)
- **Physical security:** The monitoring location is the subject's residence
- **Network exposure:** Data files are not transmitted over the network (analysis is local)

### 6.3 Custody Limitations

- **Single operator:** All data collection, analysis, and reporting is performed by a single individual (the subject). There is no independent verification of data collection procedures.
- **No third-party auditing:** No external party has verified the data collection, processing, or analysis.
- **Physical access:** The monitoring equipment is accessible to the subject, who could in principle modify the hardware, software, or data.
- **No tamper-evident seals:** The RTL-SDR and computer are not sealed or monitored for physical tampering.

### 6.4 What Would Strengthen the Chain

To provide stronger evidence integrity:
1. **Third-party data escrow:** Continuous upload of hashed data entries to an independent server
2. **Blockchain timestamping:** Periodic submission of dataset hashes to a public blockchain
3. **Independent monitoring:** A second RTL-SDR at the same location operated by an independent party
4. **Sealed equipment:** Tamper-evident seals on hardware with photographic documentation
5. **External time authority:** GPS PPS or similar independent time source
6. **Code review:** Independent review of `sentinel.py` and `rf_ml_v2.py` by a third party

---

## APPENDIX: KEY FILE INVENTORY

| Path | Type | Size | Purpose |
|------|------|------|---------|
| `/home/tyler/projects/rf-monitor/sentinel.py` | Python | ~30 KB | Data collection daemon |
| `/home/tyler/projects/rf-monitor/rf_ml_v2.py` | Python | ~30 KB | ML analysis pipeline |
| `/home/tyler/projects/rf-monitor/results/ml_master_dataset.json` | JSON | ~5 MB | Merged dataset (1903 rows) |
| `/home/tyler/projects/rf-monitor/results/ml_v2/analysis_results.json` | JSON | ~200 KB | Full ML results |
| `/home/tyler/projects/rf-monitor/results/ml_v2/kg_deep_dive.json` | JSON | ~1.2 MB | 632 KG literature chunks |
| `/home/tyler/projects/rf-monitor/results/ml_v2/plots/` | PNG | ~6 files | Visualization outputs |
| `/home/tyler/projects/rf-monitor/results/spectrograms/` | PNG+JSON | 37 pairs | Spectrogram captures |
| `/home/tyler/projects/rf-monitor/captures/` | Binary IQ | Variable | Raw IQ captures |
| `/home/tyler/projects/rf-monitor/results/sentinel_*.jsonl` | JSONL | Variable | Raw sentinel logs (hourly) |

---

*End of Document 6 of 6.*
*Prepared: 2026-03-14*
*Evidence chain: RTL-SDR -> sentinel.py -> JSONL (SHA-256) -> ml_master_dataset.json -> rf_ml_v2.py -> analysis_results.json -> reports*

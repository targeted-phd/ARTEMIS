#!/usr/bin/env python3
"""
Evidence integrity verifier.

Checks:
  1. All JSONL files parse cleanly (no truncation/corruption)
  2. Cycle numbers are sequential within each file
  3. Timestamps are monotonically increasing
  4. Internal hashes are consistent
  5. No unexpected keys (metadata injection)
  6. No null bytes, BOM, or encoding anomalies
  7. Compares against saved hash manifest if available

Usage:
  python verify_integrity.py [--results-dir results] [--manifest evidence_hashes.txt]
"""

import json
import hashlib
import sys
import os
from pathlib import Path
from datetime import datetime


EXPECTED_KEYS = {"cycle", "timestamp", "elapsed_s", "stare", "new_anomalies",
                 "sweep_channels", "hash"}

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_jsonl(filepath):
    """Verify a single JSONL file. Returns (ok, issues)."""
    issues = []
    path = Path(filepath)

    # Binary checks
    raw = path.read_bytes()
    if b"\x00" in raw:
        issues.append(f"NULL BYTES detected ({raw.count(b'\x00')} occurrences)")
    if raw[:3] == b"\xef\xbb\xbf":
        issues.append("BOM detected at file start")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as e:
        issues.append(f"Encoding error: {e}")

    # Extended attributes
    try:
        xattrs = os.listxattr(str(path))
        if xattrs:
            issues.append(f"Extended attributes found: {xattrs}")
    except (OSError, AttributeError):
        pass

    # Parse each line
    lines = raw.decode("utf-8", errors="replace").strip().split("\n")
    prev_cycle = None
    prev_ts = None

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        try:
            d = json.loads(line)
        except json.JSONDecodeError as e:
            issues.append(f"Line {i}: JSON parse error: {e}")
            continue

        # Key injection check
        extra = set(d.keys()) - EXPECTED_KEYS
        if extra:
            issues.append(f"Line {i}: unexpected keys: {extra}")

        # Cycle continuity
        cyc = d.get("cycle")
        if prev_cycle is not None and cyc is not None:
            if cyc != prev_cycle + 1:
                issues.append(f"Line {i}: cycle gap: {prev_cycle} -> {cyc}")
        prev_cycle = cyc

        # Timestamp monotonicity
        ts = d.get("timestamp", "")
        if prev_ts and ts <= prev_ts:
            issues.append(f"Line {i}: timestamp not monotonic: {prev_ts} -> {ts}")
        prev_ts = ts

        # Internal hash verification
        stored_hash = d.get("hash", "")
        d_copy = {k: v for k, v in d.items() if k != "hash"}
        recomputed = hashlib.sha256(
            json.dumps(d_copy, default=str).encode()
        ).hexdigest()[:len(stored_hash)]
        if stored_hash and recomputed != stored_hash:
            issues.append(f"Line {i}: hash mismatch (stored={stored_hash}, "
                         f"computed={recomputed})")

    return len(issues) == 0, issues, len(lines)


def verify_manifest(results_dir, manifest_path):
    """Compare current file hashes against a saved manifest."""
    if not Path(manifest_path).exists():
        return None, ["Manifest file not found"]

    mismatches = []
    matches = 0
    with open(manifest_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("  ", 1)
            if len(parts) != 2:
                continue
            saved_hash, filename = parts
            filepath = Path(results_dir) / Path(filename).name
            if not filepath.exists():
                # Try as-is
                filepath = Path(filename)
            if not filepath.exists():
                mismatches.append(f"MISSING: {filename}")
                continue
            current = hash_file(filepath)
            if current != saved_hash:
                mismatches.append(f"CHANGED: {filename} "
                                 f"(was {saved_hash[:16]}..., "
                                 f"now {current[:16]}...)")
            else:
                matches += 1

    return matches, mismatches


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verify evidence integrity")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--manifest", default=None,
                       help="Hash manifest file to verify against")
    parser.add_argument("--generate-manifest", action="store_true",
                       help="Generate new hash manifest")
    parser.add_argument("--output", default=None,
                       help="Output manifest path")
    args = parser.parse_args()

    results = Path(args.results_dir)
    jsonl_files = sorted(results.glob("sentinel_*.jsonl"))

    if not jsonl_files:
        print(f"{YELLOW}No JSONL files found in {results}{RESET}")
        sys.exit(1)

    # Generate manifest mode
    if args.generate_manifest:
        out = args.output or f"results/evidence/hashes_{datetime.now():%Y%m%d_%H%M%S}.txt"
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            f.write(f"# Evidence hash manifest generated {datetime.utcnow().isoformat()}Z\n")
            for fp in sorted(results.rglob("*")):
                if fp.is_file():
                    h = hash_file(fp)
                    f.write(f"{h}  {fp}\n")
        # Hash of hashes
        manifest_hash = hash_file(out)
        print(f"{GREEN}Manifest written: {out}{RESET}")
        print(f"Manifest SHA-256: {manifest_hash}")
        return

    # Verification mode
    print(f"\n{'='*60}")
    print(f"  EVIDENCE INTEGRITY VERIFICATION")
    print(f"  {datetime.utcnow().isoformat()}Z")
    print(f"  Files: {len(jsonl_files)} JSONL")
    print(f"{'='*60}\n")

    total_cycles = 0
    all_ok = True

    for fp in jsonl_files:
        ok, issues, n_lines = verify_jsonl(fp)
        total_cycles += n_lines
        status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {fp.name:40s} {n_lines:4d} cycles  [{status}]")
        if issues:
            all_ok = False
            for issue in issues[:5]:
                print(f"    {RED}! {issue}{RESET}")
            if len(issues) > 5:
                print(f"    ... and {len(issues)-5} more issues")

    print(f"\n  Total cycles verified: {total_cycles}")

    # Manifest check
    if args.manifest:
        matches, mismatches = verify_manifest(args.results_dir, args.manifest)
        if matches is not None:
            print(f"\n  Manifest check: {matches} files match")
            if mismatches:
                all_ok = False
                for m in mismatches:
                    print(f"    {RED}! {m}{RESET}")
            else:
                print(f"    {GREEN}All hashes verified{RESET}")

    print(f"\n{'='*60}")
    if all_ok:
        print(f"  {GREEN}ALL CHECKS PASSED{RESET}")
    else:
        print(f"  {RED}INTEGRITY ISSUES DETECTED{RESET}")
    print(f"{'='*60}\n")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

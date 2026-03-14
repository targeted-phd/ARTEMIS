#!/usr/bin/env python3
"""
Pulse-Level ML Pipeline (v3) — correlate burst/pulse features with symptoms.

Uses pulse_features.json (per-IQ-file features) joined to symptom data
via sentinel cycle timestamps. Finds which pulse-level characteristics
predict specific symptoms.

Usage:
  python pulse_ml.py              # full pipeline
  python pulse_ml.py --reextract  # re-run pulse_features.py first
"""

import json
import glob
import os
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

RESULTS_DIR = Path("results")
PULSE_FILE = RESULTS_DIR / "pulse_features.json"
MASTER_FILE = RESULTS_DIR / "ml_master_dataset.json"
OUTPUT_DIR = RESULTS_DIR / "ml_v3"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_data():
    """Load pulse features and master dataset, join by timestamp."""
    with open(PULSE_FILE) as f:
        pulse_data = json.load(f)
    with open(MASTER_FILE) as f:
        master = json.load(f)

    LOCAL_TZ = datetime.now().astimezone().tzinfo

    # Index master timeline by timestamp for matching
    timeline = master["timeline"]
    tl_times = []
    for r in timeline:
        try:
            tl_times.append(datetime.strptime(r["cst"], "%Y-%m-%d %H:%M:%S"))
        except:
            tl_times.append(None)

    # Parse IQ file timestamps from filename
    # Format: sentinel_826MHz_014542.iq → 01:45:42
    # Or: sentinel_826MHz_HHMMSS.iq
    # Use file modification time as fallback
    joined = []
    for pf in pulse_data:
        if not pf.get("has_signal"):
            continue

        filepath = pf.get("file", "")
        # Get file mod time
        try:
            mtime = datetime.fromtimestamp(
                os.path.getmtime(filepath)).astimezone(LOCAL_TZ).replace(tzinfo=None)
        except:
            continue

        # Find nearest timeline row
        best_idx = None
        best_dist = float("inf")
        for i, t in enumerate(tl_times):
            if t is None:
                continue
            d = abs((t - mtime).total_seconds())
            if d < best_dist:
                best_dist = d
                best_idx = i

        if best_idx is None or best_dist > 300:  # within 5 min
            continue

        row = timeline[best_idx]
        # Merge pulse features with timeline row
        merged = {**pf, **{f"tl_{k}": v for k, v in row.items()
                          if k not in ("symptoms", "cst")}}
        merged["cst"] = row.get("cst", "")
        merged["symptoms"] = row.get("symptoms", [])
        joined.append(merged)

    print(f"Joined {len(joined)} IQ files to timeline rows")
    return joined, master


def build_feature_matrix(joined, symptom_types):
    """Build X (pulse features) and y (per-symptom) matrices."""

    # Pulse-level feature columns
    feat_cols = [
        "n_pulses", "pulse_width_mean_us", "pulse_width_std_us",
        "pulse_width_median_us", "pulse_snr_mean_db", "pulse_snr_max_db",
        "pulse_bw_mean_hz", "pulse_bw_std_hz", "pulse_bw_max_hz",
        "pulse_energy_mean", "pulse_energy_total", "total_pulse_duration_us",
        "duty_cycle", "ipi_mean_us", "ipi_std_us", "ipi_median_us",
        "prf_hz", "n_bursts", "burst_rep_rate_hz", "mean_ibi_us",
        "burst_n_pulses_mean", "burst_duration_mean_us", "burst_prf_mean_hz",
        "modulation_index", "inst_freq_mean_hz", "inst_freq_std_hz",
        "noise_mean", "noise_std", "freq_mhz",
    ]

    # Add timeline features
    tl_feat_cols = [
        "tl_ei_total", "tl_ei_zone_a", "tl_ei_zone_b",
        "tl_max_kurt", "tl_max_kurt_zone_a", "tl_max_kurt_zone_b",
        "tl_n_active_targets", "tl_total_pulses",
    ]

    all_cols = feat_cols + tl_feat_cols

    X = np.zeros((len(joined), len(all_cols)))
    for i, row in enumerate(joined):
        for j, col in enumerate(all_cols):
            v = row.get(col)
            if v is None or v != v:  # None or NaN
                X[i, j] = 0
            else:
                try:
                    X[i, j] = float(v)
                except (ValueError, TypeError):
                    X[i, j] = 0

    # Replace NaN/inf
    X = np.nan_to_num(X, nan=0, posinf=0, neginf=0)

    # Build per-symptom y vectors using interpolated values
    y_dict = {}
    for st in symptom_types:
        y = np.zeros(len(joined))
        for i, row in enumerate(joined):
            v = row.get(f"tl_{st}_interp", 0)
            if v is not None:
                y[i] = float(v)
        y_dict[st] = y

    return X, y_dict, all_cols


def run_analysis(X, y_dict, feature_names, joined):
    """Run per-symptom correlation and classification."""
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import roc_auc_score
    from scipy import stats as sp_stats

    results = {}

    for symptom, y_cont in y_dict.items():
        # Binary: any symptom > 0.1
        y_bin = (y_cont > 0.1).astype(int)
        n_pos = np.sum(y_bin)
        n_neg = len(y_bin) - n_pos

        if n_pos < 5 or n_neg < 5:
            print(f"\n  {symptom}: skipping (n+={n_pos}, n-={n_neg})")
            continue

        print(f"\n{'='*60}")
        print(f"  {symptom.upper()} (n+={n_pos}, n-={n_neg}, total={len(y_bin)})")
        print(f"{'='*60}")

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Feature correlation with symptom severity
        print(f"\n  Top pulse features correlated with {symptom} severity:")
        correlations = []
        for j, col in enumerate(feature_names):
            mask = ~np.isnan(X[:, j]) & (X[:, j] != 0)
            if np.sum(mask) < 10:
                continue
            rho, p = sp_stats.spearmanr(X[mask, j], y_cont[mask])
            if not np.isnan(rho):
                correlations.append((col, rho, p))

        correlations.sort(key=lambda x: abs(x[1]), reverse=True)
        for col, rho, p in correlations[:10]:
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            print(f"    {col:35s} rho={rho:+.3f}  p={p:.2e} {sig}")

        # Random Forest classification
        try:
            skf = StratifiedKFold(n_splits=min(5, n_pos, n_neg), shuffle=True, random_state=42)
            rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
            aucs = cross_val_score(rf, X_scaled, y_bin, cv=skf, scoring="roc_auc")
            mean_auc = np.mean(aucs)
            print(f"\n  RF AUC (5-fold): {mean_auc:.3f} ± {np.std(aucs):.3f}")
        except Exception as e:
            mean_auc = 0
            print(f"\n  RF failed: {e}")

        # Feature importance from RF
        try:
            rf_full = RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42)
            rf_full.fit(X_scaled, y_bin)
            importances = rf_full.feature_importances_
            top_idx = np.argsort(importances)[::-1][:10]
            print(f"\n  Top RF feature importances:")
            for idx in top_idx:
                if importances[idx] > 0.01:
                    print(f"    {feature_names[idx]:35s} importance={importances[idx]:.3f}")
        except:
            pass

        # Severity regression
        try:
            mask = y_cont > 0
            if np.sum(mask) >= 10:
                gbr = GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42)
                gbr.fit(X_scaled[mask], y_cont[mask])
                r2 = gbr.score(X_scaled[mask], y_cont[mask])
                print(f"\n  Severity regression R² (on positive samples): {r2:.3f}")
        except:
            pass

        results[symptom] = {
            "n_pos": int(n_pos),
            "n_neg": int(n_neg),
            "auc": round(mean_auc, 3),
            "top_correlations": [(c, round(r, 3), round(p, 6))
                                for c, r, p in correlations[:15]],
        }

    return results


def compare_zones(joined, feature_names):
    """Compare pulse characteristics between Zone A and Zone B."""
    zone_a = [j for j in joined if j.get("freq_mhz", 0) and 618 < j["freq_mhz"] < 640]
    zone_b = [j for j in joined if j.get("freq_mhz", 0) and 820 < j["freq_mhz"] < 840]

    print(f"\n{'='*60}")
    print(f"  ZONE COMPARISON (A={len(zone_a)}, B={len(zone_b)})")
    print(f"{'='*60}")

    compare_cols = [
        "n_pulses", "pulse_width_mean_us", "prf_hz", "duty_cycle",
        "pulse_bw_mean_hz", "modulation_index", "n_bursts",
        "burst_duration_mean_us", "pulse_energy_total",
    ]

    for col in compare_cols:
        va = [r.get(col, 0) for r in zone_a if r.get(col, 0)]
        vb = [r.get(col, 0) for r in zone_b if r.get(col, 0)]
        if va and vb:
            from scipy import stats as sp_stats
            stat, p = sp_stats.mannwhitneyu(va, vb, alternative="two-sided")
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            print(f"  {col:30s}  A={np.mean(va):>10.1f}  B={np.mean(vb):>10.1f}  p={p:.2e} {sig}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reextract", action="store_true")
    args = parser.parse_args()

    if args.reextract:
        print("Re-extracting pulse features...")
        os.system(".venv/bin/python3 pulse_features.py --workers 6")

    print("Loading data...")
    joined, master = load_data()
    symptom_types = master.get("stats", {}).get("symptom_types",
        ["speech", "headache", "tinnitus", "paresthesia", "pressure", "sleep", "nausea"])

    X, y_dict, feature_names = build_feature_matrix(joined, symptom_types)
    print(f"Feature matrix: {X.shape[0]} samples × {X.shape[1]} features")

    results = run_analysis(X, y_dict, feature_names, joined)
    compare_zones(joined, feature_names)

    # Save results
    with open(OUTPUT_DIR / "pulse_ml_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {OUTPUT_DIR}/pulse_ml_results.json")


if __name__ == "__main__":
    main()

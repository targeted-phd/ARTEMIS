#!/usr/bin/env python3
"""
RF-Symptom ML Analysis v2 — Per-symptom specificity, dose-response,
temporal prediction, zone differential analysis.

Fixes from v1:
  - Uses severity scores (0-3) not just binary
  - Per-symptom models, not just any_symptom
  - Zone A vs Zone B differential signatures
  - Temporal lag and cumulative exposure features
  - Dose-response curves
  - Honest about confounders (notification bias)

Usage:
  python rf_ml_v2.py analyze     # Full analysis
  python rf_ml_v2.py report      # Generate evidence report
"""

import json
import os
import sys
import hashlib
import warnings
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy import stats as sp_stats
from scipy.signal import correlate as sig_correlate

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

ML_DIR = Path("results/ml_v2")
PLOTS_DIR = ML_DIR / "plots"
MASTER = Path("results/ml_master_dataset.json")

SYMPTOM_COLS = ["headache", "paresthesia", "pressure", "sleep", "speech", "tinnitus", "nausea"]
SYMPTOM_INTERP = [f"{s}_interp" for s in SYMPTOM_COLS]
RF_FEATURES = ["ei_total", "ei_zone_a", "ei_zone_b", "max_kurt", "max_kurt_zone_a",
               "max_kurt_zone_b", "max_kurt_ul", "n_active_targets", "total_pulses",
               "mean_pulse_width_us", "total_pulse_duration_us"]
TEMPORAL_FEATURES = ["hour", "minute", "is_night"]

plt.style.use("dark_background")
plt.rcParams.update({"font.family": "monospace", "axes.grid": True,
                     "grid.alpha": 0.15, "grid.linewidth": 0.5})


def load_data():
    ds = json.load(open(MASTER))
    tl = ds["timeline"]
    data = [r for r in tl if r.get("type") != "GAP_NO_DATA"]
    print(f"  Loaded {len(data)} data rows ({len(tl)} total with gaps)")
    print(f"  Responded rows: {sum(1 for r in data if r.get('did_respond'))}")
    print(f"  Symptom rows: {sum(1 for r in data if (r.get('any_symptom') or 0) > 0)}")
    print(f"  Interpolated: {sum(1 for r in data if (r.get('any_symptom_interp') or 0) > 0)}")
    return ds, data


def build_feature_matrix(data):
    """Build X matrix with RF + temporal + lagged + cumulative features."""
    base_cols = RF_FEATURES + TEMPORAL_FEATURES
    # Lag features: previous cycle's RF values
    lag_cols = [f"lag1_{c}" for c in RF_FEATURES]
    lag2_cols = [f"lag2_{c}" for c in RF_FEATURES]
    # Rolling cumulative exposure (last 5 and 10 cycles)
    roll5_cols = [f"roll5_{c}" for c in ["ei_total", "max_kurt", "total_pulses", "total_pulse_duration_us"]]
    roll10_cols = [f"roll10_{c}" for c in ["ei_total", "max_kurt", "total_pulses", "total_pulse_duration_us"]]
    # Delta features (change from previous cycle)
    delta_cols = [f"delta_{c}" for c in ["ei_total", "max_kurt", "n_active_targets"]]
    # Zone differential
    zone_cols = ["zone_ratio_kurt", "zone_ratio_ei", "zone_b_dominant"]

    all_cols = base_cols + lag_cols + lag2_cols + roll5_cols + roll10_cols + delta_cols + zone_cols
    X = np.full((len(data), len(all_cols)), np.nan, dtype=np.float64)

    for i, row in enumerate(data):
        # Base RF + temporal
        for j, col in enumerate(base_cols):
            val = row.get(col)
            if val is not None and isinstance(val, (int, float)):
                X[i, j] = float(val)

        offset = len(base_cols)

        # Lag-1 features
        if i > 0:
            prev = data[i - 1]
            for j, col in enumerate(RF_FEATURES):
                val = prev.get(col)
                if val is not None and isinstance(val, (int, float)):
                    X[i, offset + j] = float(val)
        offset += len(RF_FEATURES)

        # Lag-2 features
        if i > 1:
            prev2 = data[i - 2]
            for j, col in enumerate(RF_FEATURES):
                val = prev2.get(col)
                if val is not None and isinstance(val, (int, float)):
                    X[i, offset + j] = float(val)
        offset += len(RF_FEATURES)

        # Rolling 5-cycle mean
        roll_src = ["ei_total", "max_kurt", "total_pulses", "total_pulse_duration_us"]
        for j, col in enumerate(roll_src):
            start = max(0, i - 5)
            vals = [data[k].get(col, 0) or 0 for k in range(start, i)]
            X[i, offset + j] = np.mean(vals) if vals else 0
        offset += len(roll_src)

        # Rolling 10-cycle mean
        for j, col in enumerate(roll_src):
            start = max(0, i - 10)
            vals = [data[k].get(col, 0) or 0 for k in range(start, i)]
            X[i, offset + j] = np.mean(vals) if vals else 0
        offset += len(roll_src)

        # Delta features
        delta_src = ["ei_total", "max_kurt", "n_active_targets"]
        if i > 0:
            for j, col in enumerate(delta_src):
                curr = row.get(col, 0) or 0
                prev_val = data[i - 1].get(col, 0) or 0
                X[i, offset + j] = curr - prev_val
        offset += len(delta_src)

        # Zone differential
        ka = row.get("max_kurt_zone_a") or 0
        kb = row.get("max_kurt_zone_b") or 0
        ea = row.get("ei_zone_a") or 0
        eb = row.get("ei_zone_b") or 0
        X[i, offset + 0] = ka / (kb + 1e-6)  # zone A/B kurtosis ratio
        X[i, offset + 1] = ea / (eb + 1e-6)  # zone A/B EI ratio
        X[i, offset + 2] = 1.0 if kb > ka else 0.0  # zone B dominant flag

    return X, all_cols


def per_symptom_analysis(data, X, feature_names):
    """Run per-symptom statistical tests and classifiers.

    Uses interpolated severity (_interp columns) for continuous targets.
    Only trains on rows where did_respond=True OR _interp > 0 (back-filled).
    Rows with did_respond=False and _interp=0 are UNKNOWN, not negative.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import StratifiedKFold, KFold
    from sklearn.metrics import roc_auc_score, mean_absolute_error, r2_score
    import joblib

    results = {}

    for sym in SYMPTOM_COLS:
        interp_col = f"{sym}_interp"

        # Build labeled mask: rows where we KNOW the symptom state
        # = did_respond=True (explicit) OR interp > 0 (back-filled from nearby response)
        labeled_mask = []
        for r in data:
            responded = r.get("did_respond", False)
            has_interp = (r.get(interp_col, 0) or 0) > 0.05
            labeled_mask.append(responded or has_interp)
        labeled_mask = np.array(labeled_mask)

        # Get continuous severity from interpolation
        y_interp = np.array([r.get(interp_col, 0) or 0 for r in data], dtype=float)
        y_binary = (y_interp > 0.05).astype(int)

        # Only use labeled rows
        n_labeled = int(labeled_mask.sum())
        n_pos = int((y_binary[labeled_mask] > 0).sum())
        n_neg = n_labeled - n_pos

        if n_pos < 3:
            print(f"  {sym}: {n_pos} events in {n_labeled} labeled rows — skipping")
            continue

        print(f"\n  === {sym.upper()} ({n_pos} positive / {n_neg} negative / "
              f"{n_labeled} labeled of {len(data)} total) ===")

        # Work only with labeled rows
        X_labeled = X[labeled_mask].copy()
        y_labeled = y_binary[labeled_mask]
        y_sev_labeled = y_interp[labeled_mask]

        # Impute NaN
        for col in range(X_labeled.shape[1]):
            mask = np.isnan(X_labeled[:, col])
            if mask.any():
                med = np.nanmedian(X_labeled[:, col])
                X_labeled[mask, col] = med if not np.isnan(med) else 0

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_labeled)

        # ── Mann-Whitney U per feature (on labeled rows only) ──
        pos_idx = np.where(y_labeled == 1)[0]
        neg_active = np.where(y_labeled == 0)[0]

        mw_results = []
        for j, fname in enumerate(feature_names):
            pv = X_labeled[pos_idx, j]
            nv = X_labeled[neg_active, j]
            pv = pv[~np.isnan(pv)]
            nv = nv[~np.isnan(nv)]
            if len(pv) < 2 or len(nv) < 2 or (np.std(pv) == 0 and np.std(nv) == 0):
                continue
            try:
                u, p = sp_stats.mannwhitneyu(pv, nv, alternative="two-sided")
                d = (np.mean(pv) - np.mean(nv)) / (np.sqrt((np.var(pv) + np.var(nv)) / 2) + 1e-12)
                mw_results.append({
                    "feature": fname, "p": float(p),
                    "p_bonf": float(min(p * len(feature_names), 1.0)),
                    "d": float(d), "sym_mean": float(np.mean(pv)),
                    "null_mean": float(np.mean(nv)),
                })
            except Exception:
                continue

        mw_results.sort(key=lambda x: x["p"])
        sig = [m for m in mw_results if m["p_bonf"] < 0.05]
        print(f"    Significant features (Bonferroni α=0.05): {len(sig)}/{len(mw_results)}")
        for s in mw_results[:5]:
            stars = "***" if s["p_bonf"] < 0.001 else "**" if s["p_bonf"] < 0.01 else "*" if s["p_bonf"] < 0.05 else ""
            direction = "↑" if s["d"] > 0 else "↓"
            print(f"      {s['feature']:35s} p={s['p_bonf']:.2e} d={s['d']:+.2f} "
                  f"{direction} sym={s['sym_mean']:.1f} null={s['null_mean']:.1f} {stars}")

        # ── 5-fold CV classifier (binary: symptom present/absent) ──
        if n_pos >= 5:
            skf = StratifiedKFold(n_splits=min(5, n_pos), shuffle=True, random_state=42)

            # Random Forest classifier
            y_pred = np.zeros(n_labeled, dtype=float)
            importances = np.zeros(len(feature_names))

            for train_idx, test_idx in skf.split(X_scaled, y_labeled):
                rf = RandomForestClassifier(n_estimators=200, max_depth=8,
                                           class_weight="balanced", random_state=42, n_jobs=-1)
                rf.fit(X_scaled[train_idx], y_labeled[train_idx])
                y_pred[test_idx] = rf.predict_proba(X_scaled[test_idx])[:, 1]
                importances += rf.feature_importances_

            importances /= skf.get_n_splits()
            auc = roc_auc_score(y_labeled, y_pred)
            print(f"    Random Forest AUC (5-fold CV): {auc:.3f}")

            # Top features by importance
            top_idx = np.argsort(importances)[::-1][:10]
            print(f"    Top RF features:")
            for idx in top_idx:
                if importances[idx] > 0.01:
                    print(f"      {feature_names[idx]:35s} importance={importances[idx]:.3f}")

            # Permutation test (500 iterations)
            n_perms = 500
            perm_aucs = np.zeros(n_perms)
            for pi in range(n_perms):
                yp = np.random.permutation(y_labeled)
                ypp = np.zeros(n_labeled)
                for tr, te in skf.split(X_scaled, yp):
                    rf_p = RandomForestClassifier(n_estimators=50, max_depth=5,
                                                 class_weight="balanced", random_state=pi)
                    try:
                        rf_p.fit(X_scaled[tr], yp[tr])
                        ypp[te] = rf_p.predict_proba(X_scaled[te])[:, 1]
                    except Exception:
                        ypp[te] = 0.5
                try:
                    perm_aucs[pi] = roc_auc_score(yp, ypp)
                except Exception:
                    perm_aucs[pi] = 0.5

            perm_p = (np.sum(perm_aucs >= auc) + 1) / (n_perms + 1)
            print(f"    Permutation p-value: {perm_p:.4f} (AUC {auc:.3f} vs null {np.mean(perm_aucs):.3f})")

            # ── Severity regression (continuous _interp target) ──
            sev_pos = y_sev_labeled[y_sev_labeled > 0.05]
            if len(sev_pos) >= 5 and len(set(np.round(sev_pos, 1))) > 1:
                kf = KFold(n_splits=min(5, len(sev_pos)), shuffle=True, random_state=42)
                X_sev = X_scaled[y_sev_labeled > 0.05]
                y_sev_target = y_sev_labeled[y_sev_labeled > 0.05]
                y_sev_pred = np.zeros(len(y_sev_target))

                for tr, te in kf.split(X_sev):
                    gbr = GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
                    gbr.fit(X_sev[tr], y_sev_target[tr])
                    y_sev_pred[te] = gbr.predict(X_sev[te])

                mae = mean_absolute_error(y_sev_target, y_sev_pred)
                r2 = r2_score(y_sev_target, y_sev_pred)
                print(f"    Severity regression (GBR): MAE={mae:.2f}, R²={r2:.3f}")
            else:
                mae, r2 = None, None

            # Save model
            rf_final = RandomForestClassifier(n_estimators=200, max_depth=8,
                                             class_weight="balanced", random_state=42, n_jobs=-1)
            rf_final.fit(X_scaled, y_labeled)
            joblib.dump(rf_final, MODELS_DIR / f"rf_{sym}.joblib")
            joblib.dump(scaler, MODELS_DIR / f"scaler_{sym}.joblib")
        else:
            auc, perm_p, importances = 0, 1, np.zeros(len(feature_names))
            top_idx = []
            mae, r2 = None, None

        results[sym] = {
            "n_events": n_pos,
            "n_labeled": n_labeled,
            "n_negative": n_neg,
            "mann_whitney": mw_results[:20],
            "n_significant": len(sig),
            "auc": float(auc),
            "perm_p": float(perm_p),
            "severity_regression_mae": mae,
            "severity_regression_r2": r2,
            "top_features": [{"name": feature_names[i], "importance": float(importances[i])}
                            for i in np.argsort(importances)[::-1][:10]],
            "severity_dist": dict(Counter(round(float(v), 1) for v in y_sev_labeled if v > 0.05)),
        }

    return results


def dose_response(data, X, feature_names):
    """Dose-response: how does symptom severity scale with RF parameters?"""
    results = {}

    for sym in SYMPTOM_COLS:
        severities = [r.get(sym, 0) for r in data]
        if max(severities) < 1:
            continue

        # Group by severity level
        levels = sorted(set(s for s in severities if s > 0))
        if len(levels) < 2:
            continue

        print(f"\n  Dose-response: {sym.upper()}")
        dr = {}
        for rf in RF_FEATURES:
            vals_by_sev = {}
            for sev in [0] + levels:
                idx = [i for i, r in enumerate(data) if r.get(sym, 0) == sev
                       and (sev > 0 or r.get("type") == "ACTIVE")]
                vals = [data[i].get(rf, 0) or 0 for i in idx]
                if vals:
                    vals_by_sev[sev] = np.mean(vals)

            if len(vals_by_sev) > 1:
                # Spearman correlation between severity and RF value
                sev_vals = []
                rf_vals = []
                for i, r in enumerate(data):
                    s = r.get(sym, 0)
                    v = r.get(rf)
                    if v is not None and isinstance(v, (int, float)):
                        sev_vals.append(s)
                        rf_vals.append(v)
                if len(set(sev_vals)) > 1:
                    rho, p = sp_stats.spearmanr(sev_vals, rf_vals)
                    dr[rf] = {
                        "means_by_severity": {str(k): float(v) for k, v in vals_by_sev.items()},
                        "spearman_rho": float(rho),
                        "spearman_p": float(p),
                    }
                    if p < 0.05:
                        print(f"    {rf:35s} rho={rho:+.3f} p={p:.2e} "
                              f"sev0={vals_by_sev.get(0,0):.1f} -> sev{max(levels)}={vals_by_sev.get(max(levels),0):.1f}")

        results[sym] = dr

    return results


def temporal_analysis(data):
    """Temporal patterns: when do symptoms cluster, lag analysis."""
    results = {}

    # Hour-of-day profile per symptom
    print("\n  Temporal profiles:")
    for sym in SYMPTOM_COLS:
        pos_hours = [r["hour"] for r in data if r.get(sym, 0) > 0]
        if not pos_hours:
            continue
        all_hours = [r["hour"] for r in data if r.get("type") == "ACTIVE"]
        # Normalize: symptom rate per hour
        hour_rate = {}
        for h in range(24):
            n_total = sum(1 for hr in all_hours if hr == h)
            n_sym = sum(1 for hr in pos_hours if hr == h)
            if n_total > 0:
                hour_rate[h] = n_sym / n_total
        if hour_rate:
            peak_hour = max(hour_rate, key=hour_rate.get)
            print(f"    {sym:15s} peak hour={peak_hour}:00 (rate={hour_rate[peak_hour]:.2f}), "
                  f"n={len(pos_hours)}")
            results[sym] = {"hour_rates": hour_rate, "peak_hour": peak_hour}

    # Lag analysis: does RF precede symptoms?
    print("\n  Lag analysis (RF activity before symptom onset):")
    for sym in SYMPTOM_COLS:
        y = np.array([1 if r.get(sym, 0) > 0 else 0 for r in data])
        if y.sum() < 3:
            continue

        rf_ts = np.array([r.get("ei_total", 0) or 0 for r in data])
        max_lag = 20
        xcorr = []
        for lag in range(-max_lag, max_lag + 1):
            if lag >= 0:
                a, b = rf_ts[:len(rf_ts) - lag] if lag > 0 else rf_ts, y[lag:]
            else:
                a, b = rf_ts[-lag:], y[:len(y) + lag]
            if len(a) > 10 and len(b) > 10:
                r_val = np.corrcoef(a[:min(len(a), len(b))], b[:min(len(a), len(b))])[0, 1]
                xcorr.append(float(r_val) if not np.isnan(r_val) else 0)
            else:
                xcorr.append(0)

        peak_lag = list(range(-max_lag, max_lag + 1))[np.argmax(np.abs(xcorr))]
        peak_r = xcorr[np.argmax(np.abs(xcorr))]

        # Does RF precede symptom? (negative lag = RF comes first)
        precede_r = max(abs(xcorr[i]) for i, lag in enumerate(range(-max_lag, max_lag + 1))
                       if lag < 0) if max_lag > 0 else 0
        follow_r = max(abs(xcorr[i]) for i, lag in enumerate(range(-max_lag, max_lag + 1))
                      if lag > 0) if max_lag > 0 else 0

        print(f"    {sym:15s} peak_lag={peak_lag:+d} cycles (r={peak_r:.3f})  "
              f"RF-precedes={precede_r:.3f}  RF-follows={follow_r:.3f}")

        if sym not in results:
            results[sym] = {}
        results[sym]["lag"] = {
            "peak_lag": peak_lag, "peak_r": float(peak_r),
            "rf_precedes_max_r": float(precede_r),
            "rf_follows_max_r": float(follow_r),
            "xcorr": xcorr,
        }

    return results


def zone_differential(data):
    """Which zone drives which symptoms?"""
    print("\n  Zone differential analysis:")
    results = {}

    for sym in SYMPTOM_COLS:
        pos = [r for r in data if r.get(sym, 0) > 0]
        if not pos:
            continue

        neg_active = [r for r in data if r.get(sym, 0) == 0 and r.get("type") == "ACTIVE"]

        # Zone A dominant vs Zone B dominant during symptoms
        a_dom = sum(1 for r in pos if (r.get("max_kurt_zone_a") or 0) > (r.get("max_kurt_zone_b") or 0))
        b_dom = sum(1 for r in pos if (r.get("max_kurt_zone_b") or 0) > (r.get("max_kurt_zone_a") or 0))
        neither = len(pos) - a_dom - b_dom

        # Same for null
        a_dom_null = sum(1 for r in neg_active if (r.get("max_kurt_zone_a") or 0) > (r.get("max_kurt_zone_b") or 0))
        b_dom_null = sum(1 for r in neg_active if (r.get("max_kurt_zone_b") or 0) > (r.get("max_kurt_zone_a") or 0))

        a_pct = a_dom / len(pos) * 100 if pos else 0
        b_pct = b_dom / len(pos) * 100 if pos else 0
        a_pct_null = a_dom_null / len(neg_active) * 100 if neg_active else 0
        b_pct_null = b_dom_null / len(neg_active) * 100 if neg_active else 0

        # EI ratio
        ei_a_sym = np.mean([(r.get("ei_zone_a") or 0) for r in pos])
        ei_b_sym = np.mean([(r.get("ei_zone_b") or 0) for r in pos])
        ei_a_null = np.mean([(r.get("ei_zone_a") or 0) for r in neg_active]) if neg_active else 0
        ei_b_null = np.mean([(r.get("ei_zone_b") or 0) for r in neg_active]) if neg_active else 0

        print(f"    {sym:15s} ZoneA={a_pct:.0f}% ZoneB={b_pct:.0f}% "
              f"(null: A={a_pct_null:.0f}% B={b_pct_null:.0f}%)  "
              f"EI_A={ei_a_sym:.0f} EI_B={ei_b_sym:.0f}")

        results[sym] = {
            "zone_a_dominant_pct": float(a_pct),
            "zone_b_dominant_pct": float(b_pct),
            "zone_a_dominant_null_pct": float(a_pct_null),
            "zone_b_dominant_null_pct": float(b_pct_null),
            "ei_zone_a_mean": float(ei_a_sym),
            "ei_zone_b_mean": float(ei_b_sym),
        }

    return results


def generate_plots(data, X, feature_names, sym_results, dose_results, temporal_results, zone_results):
    """Generate all analysis plots."""

    # 1. Per-symptom feature importance comparison
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    for ax, sym in zip(axes.flat, SYMPTOM_COLS):
        sr = sym_results.get(sym, {})
        top = sr.get("top_features", [])
        if not top:
            ax.set_title(f"{sym} — no data", fontsize=10)
            continue
        names = [t["name"][:25] for t in top[:8]]
        vals = [t["importance"] for t in top[:8]]
        ax.barh(range(len(names)), vals, color="#4dabf7", alpha=0.8)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=7)
        ax.set_title(f"{sym.upper()} (AUC={sr.get('auc', 0):.2f}, p={sr.get('perm_p', 1):.3f})",
                     fontsize=10, fontweight="bold")
        ax.invert_yaxis()
    fig.suptitle("Per-Symptom Feature Importance (Random Forest)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "per_symptom_importance.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 2. Dose-response curves
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    for ax, sym in zip(axes.flat, SYMPTOM_COLS):
        dr = dose_results.get(sym, {})
        if not dr:
            ax.set_title(f"{sym} — no data", fontsize=10)
            continue
        # Plot ei_total dose-response
        ei_dr = dr.get("ei_total", {})
        means = ei_dr.get("means_by_severity", {})
        if means:
            sevs = sorted(int(k) for k in means.keys())
            vals = [means[str(s)] for s in sevs]
            ax.bar(sevs, vals, color=["#888888" if s == 0 else "#ff6b6b" for s in sevs], alpha=0.8)
            ax.set_xlabel("Severity")
            ax.set_ylabel("Mean EI Total")
            rho = ei_dr.get("spearman_rho", 0)
            p = ei_dr.get("spearman_p", 1)
            ax.set_title(f"{sym.upper()} — EI dose-response\nρ={rho:.2f}, p={p:.3f}",
                        fontsize=10, fontweight="bold")
    fig.suptitle("Dose-Response: Exposure Index vs Symptom Severity", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "dose_response.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 3. Zone differential
    fig, ax = plt.subplots(figsize=(10, 6))
    syms_with_data = [s for s in SYMPTOM_COLS if s in zone_results]
    if syms_with_data:
        x = np.arange(len(syms_with_data))
        a_vals = [zone_results[s]["zone_a_dominant_pct"] for s in syms_with_data]
        b_vals = [zone_results[s]["zone_b_dominant_pct"] for s in syms_with_data]
        ax.bar(x - 0.2, a_vals, 0.35, label="Zone A dominant (622-636 MHz)", color="#ff6b6b", alpha=0.8)
        ax.bar(x + 0.2, b_vals, 0.35, label="Zone B dominant (826-834 MHz)", color="#4dabf7", alpha=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels([s.upper() for s in syms_with_data], fontsize=10)
        ax.set_ylabel("% of symptom cycles")
        ax.set_title("Zone Dominance by Symptom Type", fontsize=14, fontweight="bold")
        ax.legend()
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "zone_differential.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 4. Temporal profiles
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    for ax, sym in zip(axes.flat, SYMPTOM_COLS):
        tr = temporal_results.get(sym, {})
        hr = tr.get("hour_rates", {})
        if not hr:
            ax.set_title(f"{sym} — no data", fontsize=10)
            continue
        hours = sorted(hr.keys())
        rates = [hr[h] for h in hours]
        ax.bar(hours, rates, color="#ffd43b", alpha=0.8)
        ax.set_xlabel("Hour (CST)")
        ax.set_ylabel("Symptom rate")
        ax.set_title(f"{sym.upper()} — hourly rate", fontsize=10, fontweight="bold")
        ax.set_xlim(-0.5, 23.5)
    fig.suptitle("Symptom Occurrence Rate by Hour of Day", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "temporal_profiles.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 5. Lag analysis
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    for ax, sym in zip(axes.flat, SYMPTOM_COLS):
        tr = temporal_results.get(sym, {})
        lag_data = tr.get("lag", {})
        xcorr = lag_data.get("xcorr", [])
        if not xcorr:
            ax.set_title(f"{sym} — no data", fontsize=10)
            continue
        lags = list(range(-20, 21))
        ax.bar(lags, xcorr, color="#4dabf7", alpha=0.7, width=0.8)
        peak = lag_data.get("peak_lag", 0)
        ax.axvline(peak, color="#ff4444", linewidth=1.5, linestyle="--",
                  label=f"peak={peak:+d} (r={lag_data.get('peak_r', 0):.3f})")
        ax.axvline(0, color="#888888", linewidth=0.5)
        ax.set_xlabel("Lag (cycles, negative = RF first)")
        ax.set_ylabel("Correlation")
        ax.set_title(f"{sym.upper()}", fontsize=10, fontweight="bold")
        ax.legend(fontsize=8)
    fig.suptitle("RF → Symptom Lag Cross-Correlation\n(negative lag = RF precedes symptom)",
                fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "lag_analysis.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    # 6. Co-occurrence heatmap
    n_sym = len(SYMPTOM_COLS)
    cooccur = np.zeros((n_sym, n_sym))
    for r in data:
        active = [i for i, s in enumerate(SYMPTOM_COLS) if r.get(s, 0) > 0]
        for a in active:
            for b in active:
                cooccur[a, b] += 1

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cooccur, cmap="YlOrRd")
    ax.set_xticks(range(n_sym))
    ax.set_yticks(range(n_sym))
    ax.set_xticklabels([s.upper() for s in SYMPTOM_COLS], rotation=45, ha="right")
    ax.set_yticklabels([s.upper() for s in SYMPTOM_COLS])
    for i in range(n_sym):
        for j in range(n_sym):
            ax.text(j, i, f"{int(cooccur[i, j])}", ha="center", va="center",
                   color="white" if cooccur[i, j] > cooccur.max() / 2 else "black", fontsize=10)
    ax.set_title("Symptom Co-occurrence Matrix", fontsize=14, fontweight="bold")
    plt.colorbar(im, ax=ax, label="Co-occurring cycles")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "cooccurrence.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

    print(f"\n  Generated 6 plot files in {PLOTS_DIR}/")


MODELS_DIR = ML_DIR / "models"


def cmd_analyze(args=None):
    print(f"\n{'=' * 60}")
    print("  RF-SYMPTOM ML ANALYSIS v2")
    print(f"{'=' * 60}\n")

    ML_DIR.mkdir(parents=True, exist_ok=True)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    ds, data = load_data()
    X, feature_names = build_feature_matrix(data)
    print(f"  Feature matrix: {X.shape[0]} × {X.shape[1]}")
    print(f"  Features: {len(RF_FEATURES)} RF + {len(TEMPORAL_FEATURES)} temporal + "
          f"{len(RF_FEATURES)*2} lag + 8 rolling + 3 delta + 3 zone = {len(feature_names)}")

    # Save features
    np.savez_compressed(ML_DIR / "features.npz", X=X)
    json.dump({"feature_names": feature_names, "n_rows": len(data)},
              open(ML_DIR / "features_meta.json", "w"), indent=2)

    # Per-symptom analysis
    print(f"\n{'─' * 60}")
    print("  PER-SYMPTOM CLASSIFICATION")
    print(f"{'─' * 60}")
    sym_results = per_symptom_analysis(data, X, feature_names)

    # Dose-response
    print(f"\n{'─' * 60}")
    print("  DOSE-RESPONSE ANALYSIS")
    print(f"{'─' * 60}")
    dose_results = dose_response(data, X, feature_names)

    # Temporal
    print(f"\n{'─' * 60}")
    print("  TEMPORAL ANALYSIS")
    print(f"{'─' * 60}")
    temporal_results = temporal_analysis(data)

    # Zone differential
    print(f"\n{'─' * 60}")
    print("  ZONE DIFFERENTIAL")
    print(f"{'─' * 60}")
    zone_results = zone_differential(data)

    # Plots
    print(f"\n{'─' * 60}")
    print("  GENERATING PLOTS")
    print(f"{'─' * 60}")
    generate_plots(data, X, feature_names, sym_results, dose_results, temporal_results, zone_results)

    # Save all results
    all_results = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "n_data_rows": len(data),
        "n_features": len(feature_names),
        "per_symptom": sym_results,
        "dose_response": dose_results,
        "temporal": {k: {kk: vv for kk, vv in v.items() if kk != "xcorr"}
                    if isinstance(v, dict) else v
                    for k, v in temporal_results.items()},
        "zone_differential": zone_results,
    }
    json.dump(all_results, open(ML_DIR / "analysis_results.json", "w"), indent=2, default=str)

    # Confounder analysis
    print(f"\n{'─' * 60}")
    print("  CONFOUNDER CHECK")
    print(f"{'─' * 60}")

    # Check: when did symptom reporting start vs zone activity
    sym_rows = [r for r in data if r.get("any_symptom", 0) > 0]
    nonsym_rows = [r for r in data if r.get("any_symptom", 0) == 0 and r.get("type") == "ACTIVE"]
    if sym_rows:
        first_sym = sym_rows[0]["cst"]
        last_sym = sym_rows[-1]["cst"]
        print(f"  Symptom reporting window: {first_sym} → {last_sym}")
        print(f"  Total monitoring window:  {data[0]['cst']} → {data[-1]['cst']}")

        # Zone B activity during vs outside symptom reporting window
        sym_window = [r for r in data if r["cst"] >= first_sym]
        pre_window = [r for r in data if r["cst"] < first_sym]

        zb_during = np.mean([(r.get("max_kurt_zone_b") or 0) for r in sym_window])
        zb_before = np.mean([(r.get("max_kurt_zone_b") or 0) for r in pre_window]) if pre_window else 0
        za_during = np.mean([(r.get("max_kurt_zone_a") or 0) for r in sym_window])
        za_before = np.mean([(r.get("max_kurt_zone_a") or 0) for r in pre_window]) if pre_window else 0

        print(f"\n  Zone activity BEFORE symptom reporting started:")
        print(f"    Zone A mean kurt: {za_before:.1f}  (n={len(pre_window)} cycles)")
        print(f"    Zone B mean kurt: {zb_before:.1f}")
        print(f"  Zone activity DURING symptom reporting window:")
        print(f"    Zone A mean kurt: {za_during:.1f}  (n={len(sym_window)} cycles)")
        print(f"    Zone B mean kurt: {zb_during:.1f}")

        if zb_before > zb_during * 2:
            print(f"\n  ⚠ WARNING: Zone B was {zb_before/max(zb_during,0.1):.1f}x more active BEFORE "
                  f"symptom reporting started.")
            print(f"    Zone B's role in symptoms may be UNDERESTIMATED by the model.")
            print(f"    The model may over-attribute symptoms to Zone A simply because")
            print(f"    Zone A was what was active during the reporting window.")
            all_results["confounder_warning"] = (
                f"Zone B was {zb_before/max(zb_during,0.1):.1f}x more active before symptom "
                f"reporting began. Zone B's contribution to symptoms is likely underestimated. "
                f"Overnight data (Zone B dominant, no symptom reports) biases the model toward "
                f"Zone A as the predictor. Need continued monitoring with both zones active "
                f"to resolve this confound."
            )

        # has_zone_a coverage
        za_avail = sum(1 for r in data if r.get("has_zone_a"))
        print(f"\n  Zone A data available: {za_avail}/{len(data)} cycles ({100*za_avail/len(data):.0f}%)")
        print(f"    Model trained on {100-100*za_avail/len(data):.0f}% Zone-B-only data")

    # Summary
    print(f"\n{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    for sym in SYMPTOM_COLS:
        sr = sym_results.get(sym, {})
        if sr:
            print(f"  {sym:15s}  n={sr['n_events']:3d}  AUC={sr['auc']:.3f}  "
                  f"p={sr['perm_p']:.4f}  sig_features={sr['n_significant']}")
    print(f"\n  Results: {ML_DIR}/")
    print(f"  Plots:   {PLOTS_DIR}/")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RF-Symptom ML v2")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("analyze")
    sub.add_parser("report")
    args = parser.parse_args()
    if not args.command:
        args.command = "analyze"
    if args.command == "analyze":
        cmd_analyze(args)


if __name__ == "__main__":
    main()

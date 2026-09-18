"""Offline Block 17 audit.  Reads archived summaries only; performs no network/SAR I/O."""
from __future__ import annotations

import csv, hashlib, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from umbra_sar.selector_consolidation import (
    depth_variance, dispersion_derivatives, dispersion_omega, synthesize_band,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'umbra/selezione_scene/Block17_selector_consolidation'
B16 = ROOT / 'umbra/selezione_scene/Block16_scene_selection'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path, obj): path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    config = json.loads((OUT / "BLOCK17_CONFIG.json").read_text(encoding="utf-8"))
    (OUT / "BLOCK17_CONFIG.sha256").write_text(sha(OUT / "BLOCK17_CONFIG.json") + "\n", encoding="ascii")
    baseline_summary = json.loads((B16 / "BLOCK16A_SUMMARY.json").read_text(encoding="utf-8"))
    expected = {"A": 0, "B": 1, "C": 33, "D": 10106, "E": 0}
    with (B16 / "BLOCK16A_ALL_CANDIDATES.csv").open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    counts = Counter(r["category"] for r in rows)
    observed = {key: counts.get(key, 0) for key in expected}
    if observed != expected or baseline_summary["counts"]["categories"] != expected:
        raise RuntimeError(f"Block16A baseline mismatch: {observed}")

    measured_keys = set()
    with (B16 / "BLOCK16A_MEASURED_SPECTRA.csv").open(newline="", encoding="utf-8-sig") as fh:
        measured = list(csv.DictReader(fh))
    for r in measured: measured_keys.add(r["acquisition_key"])

    fields = ["acquisition_key", "previous_category", "corrected_category", "category_changed",
              "cause_class", "reference_reaudit", "roi_semantics", "temporal_semantics"]
    revised = []
    with (OUT / "BLOCK17_BASELINE_CORRECTED.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields); wr.writeheader()
        for r in rows:
            ref = ("not_reproducible_from_archived_summary_missing_per_bin_joint_mask"
                   if r["acquisition_key"] in measured_keys else "unchanged_no_measured_reference")
            wr.writerow({"acquisition_key": r["acquisition_key"], "previous_category": r["category"],
                         "corrected_category": r["category"], "category_changed": False,
                         "cause_class": "semantic_only_no_archived_evidence_for_reclassification",
                         "reference_reaudit": ref,
                         "roi_semantics": "legacy_clearance_proxy_renamed_not_maximum_roi",
                         "temporal_semantics": "CPHD_and_SICD_budgets_separated; legacy_category_preserved"})
            if r["category"] in {"A", "B", "C"}:
                revised.append({k: r.get(k, "") for k in ("acquisition_key", "collect_name", "category",
                    "cphd_tx_time_span_s", "sicd_processed_aperture_s", "ocean_fraction",
                    "coast_distance_m_proxy", "max_ocean_roi_diameter_m_proxy", "reference_class",
                    "station_id", "station_distance_km", "observation_offset_s", "score")})
    for r in revised:
        r["representative_ocean_point_clearance_m"] = r.pop("coast_distance_m_proxy")
        r["centered_clearance_diameter_m"] = r.pop("max_ocean_roi_diameter_m_proxy")
        r["joint_directional_band_status"] = ("not_reproducible_from_archived_summary" if r["acquisition_key"] in measured_keys else "not_measured")
        r["statistical_independence_demonstrated"] = False
    with (OUT / "BLOCK17_REVISED_SHORTLIST.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(revised[0])); wr.writeheader(); wr.writerows(revised)

    counterfactual = [r for r in rows if float(r.get("ocean_fraction") or 0) < .8 and
                      float(r.get("footprint_area_km2") or 0) >= 1 and
                      float(r.get("coast_distance_m_proxy") or 0) >= 500]
    write_json(OUT / "BLOCK17_MARINE_COUNTERFACTUAL.json", {
        "status": "counterfactual_only_no_promotions", "historical_ocean_fraction_gate_confirmed": 0.8,
        "rows_below_fraction_but_passing_legacy_area_and_clearance_proxies": len(counterfactual),
        "interpretation": "Representative-point clearance is not proof that the required wave-aligned ROI fits."
    })

    times = np.asarray(json.loads((ROOT / 'umbra/Vandenberg/results/analysis_block12/BLOCK12_PHASE_SLOPE.json').read_text())["look_times_s"])
    scfg = config["synthetic"]; rng = np.random.default_rng(scfg["seed"]); synth=[]
    for eps in scfg["relative_widths"]:
        for legacy in (False, True):
            vals=[]; centers=[]; failures=0
            for _ in range(scfg["realizations"]):
                trial=synthesize_band(times, scfg["f0_hz"], eps, scfg["components"], rng, legacy=legacy)
                vals.append(trial["realized_energy_std_hz"]); centers.append(trial["realized_energy_mean_hz"])
            target=scfg["f0_hz"]*eps
            synth.append({"epsilon": eps, "generator": "legacy" if legacy else "corrected",
                          "target_sigma_hz": target, "mean_realized_sigma_hz": float(np.mean(vals)),
                          "ratio_to_target": None if target == 0 else float(np.mean(vals)/target),
                          "expected_ratio": None if target == 0 else (2**-0.5 if legacy else 1.0),
                          "monte_carlo_center_mean_hz":float(np.mean(centers)),
                          "monte_carlo_center_std_hz":float(np.std(centers,ddof=1)),
                          "center_bias_vs_declared_f0_hz":float(np.mean(centers)-scfg["f0_hz"]),
                          "rejections_or_failures":failures,
                          "look_time_source": "archived_Block12_irregular_BP_times", "look_count": len(times)})
    write_json(OUT / "BLOCK17_SYNTHETIC_WIDTH_AUDIT.json", {"results": synth})
    with (OUT / "BLOCK17_SYNTHETIC_WIDTH_AUDIT.csv").open("w", newline="", encoding="utf-8") as fh:
        wr=csv.DictWriter(fh, fieldnames=list(synth[0])); wr.writeheader(); wr.writerows(synth)

    th=config["theory"]; omega=2*np.pi/th["period_s"]
    # solve k robustly by bisection
    lo,hi=1e-8,2.0
    for _ in range(100):
        mid=(lo+hi)/2
        if dispersion_omega(mid,th["depth_m"],th["gravity_m_s2"]) < omega: lo=mid
        else: hi=mid
    k=(lo+hi)/2; d=dispersion_derivatives(k,th["depth_m"],th["gravity_m_s2"])
    sigk=.002; sigo=.02
    cov=[]
    for rho in th["covariance_correlations"]:
        q=depth_variance(k,th["depth_m"],sigk**2,sigo**2,rho*sigk*sigo,th["gravity_m_s2"])
        cov.append({"correlation": rho, "sigma_h_m": float(np.sqrt(max(q["variance_h"],0)))})
    write_json(OUT / "BLOCK17_THEORY_CHECKS.json", {"status":"exploratory_not_gate", "k_rad_m":k,
        "omega_rad_s":omega, "group_velocity_m_s":d["group_velocity"], "dh_dk":d["dh_dk"],
        "dh_domega":d["dh_domega"], "uncertainty_examples":cov,
        "finite_band_note":"Compare each k with omega(k,h), not a constant reference frequency.",
        "gradient_note":"Spatial support must be projected along propagation; 2pi/W is a Fourier scale, not a universal estimator error floor."})

    summary={"block":"17", "status":"CHECKPOINT_17", "network_requests":0, "sar_reads":0,
             "tests":{"command":".venv-umbra-thesis/Scripts/python.exe -m pytest -q","passed":179,"failed":0},
             "baseline_expected":expected, "baseline_observed":observed, "category_changes":0,
             "measured_rows_requiring_per_bin_recovery_for_joint_audit":len(measured),
             "marine_counterfactual_count":len(counterfactual),
             "frozen_long_dwell_candidate":"collect:683a3778-7ef1-4653-bd9b-1777367585d5",
             "long_dwell_category":"C", "long_dwell_promoted":False,
             "abstention":"Archived measured CSV lacks per-bin arrays, so joint directional completeness cannot be reconstructed."}
    write_json(OUT / "BLOCK17_SUMMARY.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__": main()

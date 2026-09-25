#!/usr/bin/env python
"""Block40 step 8 - machine-readable summary answering the eight required questions."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("duck_frf/Block40_stratified_validation"))
    a = ap.parse_args(argv)
    out = (ROOT / a.out) if not a.out.is_absolute() else a.out
    audit = json.loads((out / "BLOCK40_SOURCE_AUDIT.json").read_text())
    prov = json.loads((out / "BLOCK40_WINDOW_PROVENANCE_SUMMARY.json").read_text())
    strat = json.loads((out / "BLOCK40_STRATIFIED.json").read_text())
    ladder = json.loads((out / "BLOCK40_LADDER_SUMMARY.json").read_text())
    budget = json.loads((out / "BLOCK40_UNCERTAINTY_BUDGET.json").read_text())

    # Block39 aggregate GRD median quoted in the caveats: taken from Block41 (all footprint cells) when
    # available, otherwise the published Block39 value obtained with the legacy random 60-depth subsample.
    b41 = ROOT / "duck_frf/Block41_depth_sampling/BLOCK41_DEPTH_SAMPLING.json"
    if b41.exists():
        m = json.loads(b41.read_text())["summary"]["b39/grd"]["median"]
        b39_aggregate = "%+.1f with all footprint depths; %+.1f published with the legacy random subsample" % (
            m["all_pct"], m["legacy_pct"])
    else:
        b39_aggregate = "-0.8, published with the legacy random 60-depth subsample"

    def pct(x):
        return None if x is None else round(100 * x, 2)

    prim = {k: {"windows": v["windows"], "median_pct": pct(v["contour"].get("median")),
                "ci95_pct": [pct(x) for x in v["contour"].get("median_ci95_block_bootstrap", [])] or None,
                "nmad_pct": pct(v["contour"].get("nmad")), "blocks": v["contour"].get("n_blocks"),
                "sources": v["dominant_sources"]}
            for k, v in strat["primary_by_band"].items()}
    summ = {
        "block": "Block40", "scope": "spatial k/lambda audit only - omega is not measured, temporal phase is not "
                                     "validated, bathymetric inversion is not validated",
        "protocol": "BLOCK40_PROTOCOL.md (frozen before the analysis)",
        "q1_accuracy_on_direct_admissible_bathymetry": {
            "primary_by_band_and_product": prim,
            "note": "band A has no admissible window: the contemporaneous FRF survey footprint never covers 90 % of a "
                    "512 m window (max 73 %)"},
        "q2_compensation_between_sources": {
            "strata": {k: {"windows": v["windows"], "median_pct": pct(v["contour"]["median"]),
                           "ci95_pct": [pct(x) for x in v["contour"].get("median_ci95_block_bootstrap", [])] or None}
                       for k, v in strat["all_strata"].items()},
            "reading": "the strata do not share one sign: shallow windows (0-12 m, 2019 lidar bathymetry) are positive, "
                       "legacy-dominated and primary H12859 windows are near zero or negative, so the Block39 aggregate "
                       "mixes terms of opposite sign"},
        "q3_by_depth_band": prim,
        "q4_validatable_coverage": {
            "cell_fraction_by_class": audit["cell_fraction_by_class"],
            "cell_fraction_admissible_by_band": audit["cell_fraction_admissible_by_band"],
            "windows_by_run": {k: {"total": v["windows"], "by_class": v["by_class"],
                                   "primary_by_band": v["primary_by_band"],
                                   "primary_at_75_and_100_pct": v["primary_at_sensitivity"]}
                               for k, v in prov.items()}},
        "q5_variance_reduction": {v: {"median_pct": pct(x["median"]),
                                      "ci95_pct": [pct(y) for y in x.get("median_ci95_block_bootstrap", [])] or None,
                                      "short_tail_pct": pct(x.get("short_wavelength_tail_fraction")),
                                      "enl": x.get("enl_annulus_median"),
                                      "lobe_halfpower_width_rad_m": x.get("lobe_halfpower_width_median_rad_m"),
                                      "lambda_shift_vs_single_look_pct": pct(x.get("lambda_shift_vs_single_look_median"))}
                                  for v, x in ladder["variants"].items()},
        "q6_variance_vs_resolution": {
            "reading": "the multitaper gives the largest improvement with the smallest resolution loss "
                       "(width x1.9 vs x2.5 for 2x2 incoherent looks) and the smallest lobe displacement, so the gain "
                       "follows variance reduction; the incoherent ladder is not monotone and none of the SLC variants "
                       "reaches the GRD"},
        "q7_term_weights": {
            "water_level_pct": {k: pct(v["delta_vs_baseline"]) for k, v in budget["terms"].items() if k.startswith("water_level")},
            "reference_spectrum_pct": {k: pct(v["delta_vs_baseline"]) for k, v in budget["terms"].items() if k.startswith("reference_")},
            "current_pct": pct(budget["terms"]["current_diagnostic"]["delta_vs_monochromatic_no_current"]),
            "bathymetry_vertical_pct": {k: round(v["lambda_sensitivity_pct_at_median_depth"], 2)
                                        for k, v in budget["terms"]["bathymetry_vertical"]["by_class"].items()},
            "estimator_pct": {k: pct(v["median_centroid_minus_contour"]) for k, v in strat["estimator_comparison"].items()},
            "variance_reduction_pct": {k: pct(v["median"]) for k, v in budget["terms"]["variance_reduction"].items()},
            "hierarchical_monte_carlo_pct": budget["hierarchical_monte_carlo"]},
        "q8_robust_conditional_unidentifiable": {
            "robust": ["GRD contour peak on direct H12859 bathymetry at 20-30 m",
                       "insensitivity to water level over the declared interval (<= 1 %)",
                       "the SLC single-look short-wavelength tail and its reduction by multitapering"],
            "conditional": ["band B 12-20 m (22-31 windows, one 2019 lidar contributor, wide CI)",
                            "any comparison with Block39 aggregates, which mix source classes",
                            "the radial centroid, which carries a +6.6/+6.8 % offset relative to the contour peak"],
            "not_identifiable": ["band A 0-12 m with the frozen 90 % rule and 512 m windows",
                                 "the independence of nhatt/VIMS, whose bias was calibrated on the validation area",
                                 "morphological change between each survey and 2021-10-28",
                                 "any statement about omega, temporal phase or full bathymetric inversion"]},
        "pairing": strat["pairing"],
        "must_not_conclude": ["temporal phase validated", "omega measured", "bathymetric inversion validated",
                              "source differences certainly caused by bar migration",
                              "overlapping windows independent", "corrected nhatt/VIMS independent truth",
                              ("the Block39 aggregate median (GRD %s %%) as absolute accuracy" % b39_aggregate)]}
    (out / "BLOCK40_SUMMARY.json").write_text(json.dumps(summ, indent=2, default=float))
    print(json.dumps(summ["q1_accuracy_on_direct_admissible_bathymetry"], indent=1, default=float))


if __name__ == "__main__":
    main()

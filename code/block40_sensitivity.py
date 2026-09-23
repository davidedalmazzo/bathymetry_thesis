#!/usr/bin/env python
"""Block40 step 5 - reference sensitivity (water level, period, current) and budget.

All scenarios were frozen in BLOCK40_PROTOCOL.md before any result was produced.
For every primary-admissible window the predicted wavelength is recomputed under each
scenario and compared with the SAR contour peak, so each term is quantified, not
mentioned.  The terms are kept separate; a combined figure is produced only as a
hierarchical Monte Carlo over the declared scenarios, with common-mode terms (water
level, reference spectrum, current) drawn once per realisation and per-source
bathymetric offsets drawn per class, so dependencies are preserved instead of being
summed in quadrature.

Outputs: BLOCK40_REFERENCE_SENSITIVITY.csv, BLOCK40_UNCERTAINTY_BUDGET.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "code"))
from forward_lambda_check import k_from_omega, predicted_radial, peak_and_centroid, block_bootstrap

G = 9.80665


def lambda_pred_spectrum(freq, energy, depth):
    """E(k) centroid of the dominant lobe at a single depth, computed analytically.

    The forward check histograms E(k) on the SAR k grid; here the same quantity is
    evaluated without binning, because a 0.1-0.4 m water-level change moves the
    prediction by less than one histogram bin and would otherwise be quantised to
    zero.  The dominant lobe is the half-power band of E(f) around its discrete
    maximum, mapped to k by the dispersion relation at `depth`; the returned value is
    the energy-weighted centroid of that band.  Agreement with the histogram estimator
    is reported per window as rel_err_forward_check.
    """
    f = np.asarray(freq, float); e = np.asarray(energy, float)
    ok = np.isfinite(e) & (f > 0)
    f, e = f[ok], e[ok]
    i = int(np.argmax(e)); half = e >= e[i] / 2
    lo = i
    while lo > 0 and half[lo - 1]:
        lo -= 1
    hi = i
    while hi < len(e) - 1 and half[hi + 1]:
        hi += 1
    fb, eb = f[lo:hi + 1], e[lo:hi + 1]
    df = np.gradient(f)[lo:hi + 1]
    k = k_from_omega(2 * np.pi * fb, np.full(fb.shape, float(depth)))
    w = eb * df
    return float(2 * math.pi / (np.sum(k * w) / np.sum(w)))


def lambda_pred_histogram(freq, energy, depth, kmax=0.4, bins=1200):
    """The Block39 forward-check estimator (histogrammed E(k)), kept for comparison."""
    kf = np.linspace(0, kmax, bins)
    kfc = 0.5 * (kf[1:] + kf[:-1])
    S = predicted_radial(freq, energy, [depth], kf, False)
    _, kc, _ = peak_and_centroid(kfc, S)
    return 2 * math.pi / kc if np.isfinite(kc) and kc > 0 else np.nan


def lambda_monochromatic(T, depth, U=0.0):
    """lambda from omega = sqrt(gk tanh kh) + k U (intrinsic + Doppler by a current U along k)."""
    om = 2 * math.pi / T
    k = k_from_omega(np.array([om]), np.array([depth]))[0]
    if U:
        for _ in range(60):
            f = math.sqrt(G * k * math.tanh(k * depth)) + k * U - om
            dk = 1e-6 * k
            fp = ((math.sqrt(G * (k + dk) * math.tanh((k + dk) * depth)) + (k + dk) * U - om) - f) / dk
            k = max(k - f / fp, 1e-6)
    return 2 * math.pi / k


def half_power_band(freq, energy):
    e = np.asarray(energy, float); f = np.asarray(freq, float)
    i = int(np.nanargmax(e)); half = e >= e[i] / 2
    lo = i
    while lo > 0 and half[lo - 1]:
        lo -= 1
    hi = i
    while hi < len(e) - 1 and half[hi + 1]:
        hi += 1
    return 1 / f[hi], 1 / f[lo], 1 / f[i]          # T_min, T_max, T_peak(discrete)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("duck_frf/Block40_stratified_validation"))
    ap.add_argument("--ground-truth", type=Path, default=Path("outputs/ground_truth_s1a_20211028_ext20"))
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--montecarlo", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    out = (ROOT / a.out) if not a.out.is_absolute() else a.out
    cfg = json.loads((out / "BLOCK40_CONFIG.json").read_text())
    gt = (ROOT / a.ground_truth) if not a.ground_truth.is_absolute() else a.ground_truth
    spectra = json.loads((gt / "wave_spectra.json").read_text())
    wr = spectra["FRF:waverider-17m"]
    f17 = np.asarray(wr["frequency_hz"], float); e17 = np.asarray(wr["energy_m2_hz"], float)
    Tlo, Thi, Tpk = half_power_band(f17, e17)
    published_Tp = 11.396011                      # WR17 waveTp (parabolic fit) at the acquisition
    cur = cfg["scenarios"]["current_diagnostic_m_s"]
    bearing = math.radians(cfg["estimation"]["sector_axial_bearing_deg"])
    U_proj = cur["east"] * math.sin(bearing) + cur["north"] * math.cos(bearing)

    rows = list(csv.DictReader(open(out / "BLOCK40_WINDOW_RESULTS.csv")))
    prim = [r for r in rows if r["window_class"] == "primary_admissible" and r["identifiable"] == "True"
            and r["lambda_contour_m"] not in ("", "nan")]
    scen_rows = []
    for r in prim:
        h = float(r["depth_mean_m"]); lam = float(r["lambda_contour_m"])
        base = lambda_pred_spectrum(f17, e17, h)
        rec = {"run": r["run"], "product": r["product"], "transect": r["transect"], "distance_m": r["distance_m"],
               "band_name": r["band_name"], "depth_navd88_m": h, "lambda_sar_contour_m": lam,
               "lambda_pred_base_m": base, "rel_err_base": lam / base - 1,
               "lambda_pred_histogram_m": lambda_pred_histogram(f17, e17, h),
               "rel_err_forward_check": float(r["rel_err_contour"]) if r["rel_err_contour"] not in ("", "nan") else np.nan,
               "block": r["block"]}
        for eta in cfg["scenarios"]["eta_m"]:
            p = lambda_pred_spectrum(f17, e17, h + eta)
            rec[f"lambda_pred_eta{eta:+.3f}_m"] = p
            rec[f"rel_err_eta{eta:+.3f}"] = lam / p - 1
        rec["lambda_pred_wr17_discrete_max_m"] = lambda_monochromatic(Tpk, h)
        rec["lambda_pred_wr17_published_Tp_m"] = lambda_monochromatic(published_Tp, h)
        rec["lambda_pred_wr17_lobe_Tmin_m"] = lambda_monochromatic(Tlo, h)
        rec["lambda_pred_wr17_lobe_Tmax_m"] = lambda_monochromatic(Thi, h)
        for key in ("wr17_discrete_max", "wr17_published_Tp", "wr17_lobe_Tmin", "wr17_lobe_Tmax"):
            rec[f"rel_err_{key}"] = lam / rec[f"lambda_pred_{key}_m"] - 1
        for name, sp in spectra.items():
            if name == "FRF:waverider-17m":
                continue
            p = lambda_pred_spectrum(np.asarray(sp["frequency_hz"], float), np.asarray(sp["energy_m2_hz"], float), h)
            tag = name.split(":")[-1]
            rec[f"lambda_pred_{tag}_m"] = p; rec[f"rel_err_{tag}"] = lam / p - 1
        rec["lambda_pred_current_diag_m"] = lambda_monochromatic(Tpk, h, U_proj)
        rec["rel_err_current_diag"] = lam / rec["lambda_pred_current_diag_m"] - 1
        scen_rows.append(rec)

    with open(out / "BLOCK40_REFERENCE_SENSITIVITY.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(scen_rows[0])); w.writeheader(); w.writerows(scen_rows)

    def med(field, sel=None):
        s = sel if sel is not None else scen_rows
        v = [x[field] for x in s if np.isfinite(x.get(field, np.nan))]
        b = [x["block"] for x in s if np.isfinite(x.get(field, np.nan))]
        return block_bootstrap(v, b, 2000, np.random.default_rng(a.seed))

    terms = {}
    base = med("rel_err_base")
    terms["baseline_wr17_Ek_centroid"] = base
    for eta in cfg["scenarios"]["eta_m"]:
        terms[f"water_level_eta{eta:+.3f}"] = {"median": med(f"rel_err_eta{eta:+.3f}")["median"],
                                               "delta_vs_baseline": med(f"rel_err_eta{eta:+.3f}")["median"] - base["median"]}
    for key in ("wr17_discrete_max", "wr17_published_Tp", "wr17_lobe_Tmin", "wr17_lobe_Tmax",
                "awac-11m", "8m-array", "waverider-26m"):
        m = med(f"rel_err_{key}")
        terms[f"reference_{key}"] = {"median": m["median"], "delta_vs_baseline": m["median"] - base["median"], "n": m.get("n")}
    terms["current_diagnostic"] = {"U_along_k_m_s": U_proj,
                                   "median": med("rel_err_current_diag")["median"],
                                   "delta_vs_monochromatic_no_current":
                                       med("rel_err_current_diag")["median"] - med("rel_err_wr17_discrete_max")["median"],
                                   "caveat": "AWAC profile-averaged current at 11 m, 38 min from the acquisition; "
                                             "not the surface current advecting the Bragg waves"}
    # bathymetric term: per-class empirical uncertainty -> depth perturbation -> lambda
    inv = list(csv.DictReader(open(out / "BLOCK40_SOURCE_INVENTORY.csv")))
    unc_by_class = {}
    for r in inv:
        try:
            u = float(r["empirical_nmad_vs_frf_m"]) if r["empirical_nmad_vs_frf_m"] else float(r["declared_vert_uncert_fixed_m"])
        except Exception:
            continue
        unc_by_class.setdefault(r["class_name"], []).append(u)
    unc_by_class = {k: float(np.median(v)) for k, v in unc_by_class.items()}
    h_ref = float(np.median([x["depth_navd88_m"] for x in scen_rows]))
    lam_ref = lambda_pred_spectrum(f17, e17, h_ref)
    bath = {}
    for cls, u in unc_by_class.items():
        lp = lambda_pred_spectrum(f17, e17, h_ref + u)
        bath[cls] = {"uncertainty_m": u, "lambda_sensitivity_pct_at_median_depth": 100 * (lp / lam_ref - 1)}
    terms["bathymetry_vertical"] = {"reference_depth_m": h_ref, "by_class": bath,
                                    "note": "vertical uncertainty only; survey age and morphological change are a separate, "
                                            "unquantified term"}
    terms["estimator_choice"] = json.loads((out / "BLOCK40_STRATIFIED.json").read_text())["estimator_comparison"]
    terms["variance_reduction"] = {v: {"median": s["median"], "short_tail": s.get("short_wavelength_tail_fraction")}
                                   for v, s in json.loads((out / "BLOCK40_LADDER_SUMMARY.json").read_text())["variants"].items()}
    terms["spatial_block_bootstrap"] = {"meaning": "variability between spatial blocks only, not a total uncertainty",
                                        "baseline_ci95": base.get("median_ci95_block_bootstrap"),
                                        "n_blocks": base.get("n_blocks"), "windows": base.get("n"),
                                        "window_dependence": "windows overlap by 50-100 m steps; they are not independent"}

    # hierarchical Monte Carlo over declared scenarios (common-mode terms drawn once per realisation)
    rng = np.random.default_rng(a.seed)
    lo, hi = cfg["scenarios"]["eta_prudential_interval_m"]
    freq_options = ["base", "wr17_discrete_max", "wr17_published_Tp", "wr17_lobe_Tmin", "wr17_lobe_Tmax",
                    "awac-11m", "8m-array", "waverider-26m"]
    per_window = {opt: np.array([x.get("rel_err_base" if opt == "base" else f"rel_err_{opt}", np.nan) for x in scen_rows])
                  for opt in freq_options}
    eta_grid = np.array(cfg["scenarios"]["eta_m"])
    eta_curves = np.array([[x[f"rel_err_eta{e:+.3f}"] for e in eta_grid] for x in scen_rows])
    depth_arr = np.array([x["depth_navd88_m"] for x in scen_rows])
    lam_arr = np.array([x["lambda_sar_contour_m"] for x in scen_rows])
    u_prim = float(np.median([bath.get(c, {}).get("uncertainty_m", 0.5) for c in ("bluetopo_direct_h12859_2016",
                                                                                  "bluetopo_direct_2019_2020_certified")]))
    meds = []
    order = np.argsort(eta_grid)
    for _ in range(a.montecarlo):
        eta = rng.uniform(lo, hi)
        rel = np.array([np.interp(eta, eta_grid[order], row[order]) for row in eta_curves])
        opt = freq_options[int(rng.integers(len(freq_options)))]
        rel = rel + (per_window[opt] - per_window["base"])                 # common-mode reference shift
        dz = rng.normal(0.0, u_prim)                                       # per-realisation bathymetric offset
        lam_shift = np.array([lambda_pred_spectrum(f17, e17, h + dz) / lambda_pred_spectrum(f17, e17, h) - 1
                              for h in (float(np.median(depth_arr)),)])[0]
        rel = (1 + rel) / (1 + lam_shift) - 1
        meds.append(float(np.nanmedian(rel)))
    meds = np.array(meds)
    budget = {"protocol": "BLOCK40_PROTOCOL.md", "windows": len(scen_rows),
              "terms": terms,
              "hierarchical_monte_carlo": {
                  "draws": a.montecarlo, "seed": a.seed,
                  "distributions": {"eta_m": f"uniform({lo}, {hi})",
                                    "reference_spectrum": "uniform over the declared frequency options",
                                    "bathymetry_offset_m": f"normal(0, {u_prim}) common to the realisation (per-class value)"},
                  "median_of_median_pct": float(100 * np.median(meds)),
                  "p05_p95_pct": [float(100 * np.percentile(meds, 5)), float(100 * np.percentile(meds, 95))],
                  "note": "scenario spread of the *median* bias; it does not include the spatial block-bootstrap term, "
                          "which is reported separately, and terms are not summed in quadrature"},
              "not_included": ["morphological change since each survey", "azimuth cut-off / velocity bunching / MTF",
                               "temporal (omega) terms - out of Block40 scope"]}
    (out / "BLOCK40_UNCERTAINTY_BUDGET.json").write_text(json.dumps(budget, indent=2, default=float))
    print(json.dumps({"baseline": base, "eta": {k: v for k, v in terms.items() if k.startswith("water_level")},
                      "reference": {k: v for k, v in terms.items() if k.startswith("reference_")},
                      "current": terms["current_diagnostic"],
                      "mc": budget["hierarchical_monte_carlo"]}, indent=1, default=float))


if __name__ == "__main__":
    main()

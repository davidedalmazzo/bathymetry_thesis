#!/usr/bin/env python
"""Block40 step 3 - paired SLC/GRD comparison, stratified by source and depth band.

Joins the Block40 window provenance with the forward predictions (WR17, contour peak
primary, radial centroid secondary), pairs SLC and GRD windows by geographic centre and
writes

    BLOCK40_MATCHED_RESULTS.csv     one row per matched pair
    BLOCK40_STRATIFIED.json         statistics by band, class and product

Primary rows use the Block40 forward passes (frozen sector 66.34 deg, external
admissible set).  The non-primary strata, needed only to answer whether the aggregate
Block39 number hides a compensation between sources, are taken from the Block39
forward passes: the contour peak is sector-independent, so it is comparable; the radial
centroid there used a different sector and is flagged as such.
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
from forward_lambda_check import block_bootstrap

RUNS = {"slc_near": "slc/near_k4", "slc_far": "slc/far_k4", "grd_near": "grd/near_k4", "grd_far": "grd/far_k4"}


def read_forward(path):
    if not Path(path).exists():
        return {}
    out = {}
    for r in csv.DictReader(open(path)):
        try:
            out[(int(r["transect"]), float(r["distance_m"]))] = r
        except Exception:
            pass
    return out


def fnum(r, k):
    try:
        v = float(r[k])
        return v if np.isfinite(v) else np.nan
    except Exception:
        return np.nan


def pair_windows(slc_rows, grd_rows, tol_m):
    """Pair SLC and GRD windows by geographic centre.

    A pair requires a centre offset <= tol_m, the same depth band and the same window
    class; each GRD window is used at most once and the nearest admissible candidate
    wins.  Footprints are physically equivalent, never pixel-identical, so the residual
    offset is returned and reported."""
    if not slc_rows or not grd_rows:
        return []
    G = np.array([[r["E"], r["N"]] for r in grd_rows], float)
    used = set(); out = []
    for r in slc_rows:
        d = np.hypot(G[:, 0] - r["E"], G[:, 1] - r["N"])
        for j in np.argsort(d)[:5]:
            j = int(j)
            if d[j] > tol_m or j in used:
                continue
            q = grd_rows[j]
            if q["band"] != r["band"] or q["window_class"] != r["window_class"]:
                continue
            used.add(j); out.append((r, q, float(d[j])))
            break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--block39", type=Path, default=Path("duck_frf/Block39_s1_paper_confirm"))
    ap.add_argument("--out", type=Path, default=Path("duck_frf/Block40_stratified_validation"))
    ap.add_argument("--near-tolerance-m", type=float, default=25.0)
    ap.add_argument("--far-tolerance-m", type=float, default=50.0)
    ap.add_argument("--block-transects", type=int, default=9)
    ap.add_argument("--block-distance-m", type=float, default=1024.0)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    out = (ROOT / a.out) if not a.out.is_absolute() else a.out
    b39 = (ROOT / a.block39) if not a.block39.is_absolute() else a.block39
    rng = np.random.default_rng(a.seed)

    prov = list(csv.DictReader(open(out / "BLOCK40_WINDOW_PROVENANCE.csv")))
    rows = []
    for lab, sub in RUNS.items():
        fw40 = read_forward(out / "forward" / lab / "forward_windows.csv")
        fw39 = read_forward(b39 / sub / "fwd_waverider-17m_fixed" / "forward_windows.csv")
        for p in (x for x in prov if x["run"] == lab):
            key = (int(p["transect"]), float(p["distance_m"]))
            primary = p["window_class"] == "primary_admissible"
            r = fw40.get(key) if primary else None
            src = "block40_sector66"
            if r is None or r.get("certified") != "True":
                r = fw39.get(key); src = "block39_sector72"
            if r is None or r.get("certified") != "True":
                continue
            lam_pred = 2 * math.pi / fnum(r, "pred_Ek_centroid_k") if fnum(r, "pred_Ek_centroid_k") > 0 else np.nan
            lam_cont = float(p["sar_wavelength_m"]) if p["sar_wavelength_m"] not in ("", "nan") else np.nan
            kc = fnum(r, "sar_centroid_k")
            lam_cen = 2 * math.pi / kc if kc > 0 else np.nan
            rows.append({"run": lab, "product": p["product"], "geometry": p["geometry"],
                         "transect": key[0], "distance_m": key[1], "E": float(p["E"]), "N": float(p["N"]),
                         "band": int(p["band"]), "band_name": p["band_name"], "window_class": p["window_class"],
                         "dominant_class_name": p["dominant_class_name"],
                         "admissible_fraction": float(p["admissible_fraction"]),
                         "depth_mean_m": float(p["depth_mean_m"]), "forward_source": src,
                         "lambda_contour_m": lam_cont, "lambda_centroid_m": lam_cen, "lambda_pred_m": lam_pred,
                         "identifiable": p["sar_identifiable"] == "True",
                         "rel_err_contour": lam_cont / lam_pred - 1 if np.isfinite(lam_cont) and np.isfinite(lam_pred) else np.nan,
                         "rel_err_centroid": lam_cen / lam_pred - 1 if np.isfinite(lam_cen) and np.isfinite(lam_pred) else np.nan,
                         "block": f"{key[0] // a.block_transects}_{int(key[1] // a.block_distance_m)}"})

    # ---- geographic pairing SLC <-> GRD
    pairs = []
    for geom, tol in (("near", a.near_tolerance_m), ("far", a.far_tolerance_m)):
        s = [r for r in rows if r["product"] == "slc" and r["geometry"] == geom]
        g = [r for r in rows if r["product"] == "grd" and r["geometry"] == geom]
        for r, q, off in pair_windows(s, g, tol):
            pairs.append({"geometry": geom, "centre_offset_m": float(off),
                          "transect_slc": r["transect"], "distance_m": r["distance_m"],
                          "E": r["E"], "N": r["N"], "band": r["band"], "band_name": r["band_name"],
                          "window_class": r["window_class"], "dominant_class_name": r["dominant_class_name"],
                          "depth_mean_m": 0.5 * (r["depth_mean_m"] + q["depth_mean_m"]),
                          "lambda_pred_m": 0.5 * (r["lambda_pred_m"] + q["lambda_pred_m"]),
                          "slc_lambda_contour_m": r["lambda_contour_m"], "grd_lambda_contour_m": q["lambda_contour_m"],
                          "slc_lambda_centroid_m": r["lambda_centroid_m"], "grd_lambda_centroid_m": q["lambda_centroid_m"],
                          "slc_rel_err_contour": r["rel_err_contour"], "grd_rel_err_contour": q["rel_err_contour"],
                          "slc_rel_err_centroid": r["rel_err_centroid"], "grd_rel_err_centroid": q["rel_err_centroid"],
                          "slc_identifiable": r["identifiable"], "grd_identifiable": q["identifiable"],
                          "forward_source": r["forward_source"], "block": r["block"]})
    with open(out / "BLOCK40_MATCHED_RESULTS.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pairs[0])); w.writeheader(); w.writerows(pairs)
    with open(out / "BLOCK40_WINDOW_RESULTS.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    def stats(sel, field):
        v = [r[field] for r in sel if np.isfinite(r.get(field, np.nan))]
        b = [r["block"] for r in sel if np.isfinite(r.get(field, np.nan))]
        s = block_bootstrap(v, b, a.bootstrap, np.random.default_rng(a.seed))
        if s.get("n"):
            s["nmad"] = float(1.4826 * np.median(np.abs(np.array(v) - np.median(v))))
            s["short_peak_fraction_below_minus_25pct"] = float(np.mean(np.array(v) < -0.25))
        return s

    res = {"pairing": {"tolerance_near_m": a.near_tolerance_m, "tolerance_far_m": a.far_tolerance_m,
                       "pairs": len(pairs),
                       "centre_offset_m": {"median": float(np.median([p["centre_offset_m"] for p in pairs])),
                                           "p90": float(np.percentile([p["centre_offset_m"] for p in pairs], 90)),
                                           "max": float(np.max([p["centre_offset_m"] for p in pairs]))},
                       "note": "footprints are physically equivalent, not pixel-identical"},
           "blocks": {"transects": a.block_transects, "distance_m": a.block_distance_m,
                      "resamples": a.bootstrap, "seed": a.seed,
                      "meaning": "spatial variability between blocks only"},
           "primary_by_band": {}, "all_strata": {}, "paired": {}, "estimator_comparison": {}}

    for band, name in ((1, "A_0_12m"), (2, "B_12_20m"), (3, "C_20_30m")):
        for prod in ("slc", "grd"):
            sel = [r for r in rows if r["band"] == band and r["product"] == prod
                   and r["window_class"] == "primary_admissible" and r["identifiable"]]
            res["primary_by_band"][f"{name}/{prod}"] = {"windows": len(sel),
                                                        "dominant_sources": sorted({r["dominant_class_name"] for r in sel}),
                                                        "contour": stats(sel, "rel_err_contour"),
                                                        "centroid": stats(sel, "rel_err_centroid")}
    for prod in ("slc", "grd"):
        for klass in sorted({r["window_class"] for r in rows}):
            for band, name in ((1, "A_0_12m"), (2, "B_12_20m"), (3, "C_20_30m")):
                sel = [r for r in rows if r["product"] == prod and r["window_class"] == klass
                       and r["band"] == band and r["identifiable"]]
                if len(sel) < 10:
                    continue
                res["all_strata"][f"{prod}/{name}/{klass}"] = {
                    "windows": len(sel), "dominant_sources": sorted({r["dominant_class_name"] for r in sel}),
                    "forward_sources": sorted({r["forward_source"] for r in sel}),
                    "contour": stats(sel, "rel_err_contour")}
    for tag, sel in (("primary_admissible", [p for p in pairs if p["window_class"] == "primary_admissible"]),
                     ("all_pairs", pairs)):
        if not sel:
            continue
        for prod in ("slc", "grd"):
            for est in ("contour", "centroid"):
                v = [{"x": p[f"{prod}_rel_err_{est}"], "block": p["block"]} for p in sel
                     if np.isfinite(p.get(f"{prod}_rel_err_{est}", np.nan))]
                s = block_bootstrap([q["x"] for q in v], [q["block"] for q in v], a.bootstrap, np.random.default_rng(a.seed))
                res["paired"][f"{tag}/{prod}/{est}"] = s
        d = [p["grd_rel_err_contour"] - p["slc_rel_err_contour"] for p in sel
             if np.isfinite(p["grd_rel_err_contour"]) and np.isfinite(p["slc_rel_err_contour"])]
        res["paired"][f"{tag}/grd_minus_slc_contour"] = {"n": len(d), "median": float(np.median(d)) if d else None,
                                                         "p10_p90": np.percentile(d, [10, 90]).tolist() if d else None}
    for prod in ("slc", "grd"):
        sel = [r for r in rows if r["product"] == prod and r["identifiable"]
               and np.isfinite(r["rel_err_contour"]) and np.isfinite(r["rel_err_centroid"])]
        d = [r["rel_err_centroid"] - r["rel_err_contour"] for r in sel]
        res["estimator_comparison"][prod] = {"n": len(d), "median_centroid_minus_contour": float(np.median(d)) if d else None,
                                             "p10_p90": np.percentile(d, [10, 90]).tolist() if d else None,
                                             "note": "systematic estimator difference, reported not suppressed"}
    (out / "BLOCK40_STRATIFIED.json").write_text(json.dumps(res, indent=2, default=float))
    print(json.dumps({"pairing": res["pairing"], "primary_by_band": {k: {"windows": v["windows"],
          "contour_median": v["contour"].get("median"), "ci": v["contour"].get("median_ci95_block_bootstrap")}
          for k, v in res["primary_by_band"].items()}}, indent=1, default=float))


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Block40 step 2 - window provenance and classification.

For every SAR window of the frozen Block39 runs the exact native footprint is
rasterised on the Block40 source mask and the area fraction of each source class is
measured.  The window is then classified with the frozen 90 % rule.

    BLOCK40_WINDOW_PROVENANCE.csv   one row per window and product

Classes: primary_admissible, mixed_source, direct_but_uncertain, interpolated,
legacy_calibrated, temporally_inadmissible, provenance_unknown.
The depth band decides which source class is admissible (band A 0-12 m: FRF 2021;
band B 12-20 m: direct 2019-2020 with NMAD <= 0.5 m; band C 20-30 m: H12859 2016).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CLASS = {0: "none", 1: "frf_survey_2021", 2: "bluetopo_direct_2019_2020_certified",
         3: "bluetopo_direct_2019_2020_uncertain", 4: "bluetopo_direct_h12859_2016",
         5: "bluetopo_direct_other_date", 6: "bluetopo_interpolated_or_pre2010",
         7: "legacy_bias_corrected", 8: "cudem"}
ADMISSIBLE_BY_BAND = {1: 1, 2: 2, 3: 4}          # depth band -> admissible source class
BAND_NAME = {1: "A_0_12m", 2: "B_12_20m", 3: "C_20_30m", 0: "outside_bands"}


def window_class(frac, band, thr):
    """Frozen decision rule. `frac` maps class code -> footprint fraction."""
    dom = max(frac, key=lambda c: frac[c]) if frac else 0
    adm = ADMISSIBLE_BY_BAND.get(band)
    if adm is not None and frac.get(adm, 0.0) >= thr:
        return "primary_admissible", dom
    if frac.get(dom, 0.0) < thr:
        return "mixed_source", dom
    if dom == 3:
        return "direct_but_uncertain", dom
    if dom in (6, 8):
        return "interpolated", dom
    if dom == 7:
        return "legacy_calibrated", dom
    if dom in (1, 2, 4, 5):
        return "temporally_inadmissible", dom     # direct, but not the class this band admits
    return "provenance_unknown", dom


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", default=[
        "slc_near:duck_frf/Block39_s1_paper_confirm/slc/near_k4",
        "slc_far:duck_frf/Block39_s1_paper_confirm/slc/far_k4",
        "grd_near:duck_frf/Block39_s1_paper_confirm/grd/near_k4",
        "grd_far:duck_frf/Block39_s1_paper_confirm/grd/far_k4"])
    ap.add_argument("--out", type=Path, default=Path("duck_frf/Block40_stratified_validation"))
    ap.add_argument("--threshold", type=float, default=0.90)
    ap.add_argument("--sensitivity-thresholds", nargs="*", type=float, default=[0.75, 1.0])
    a = ap.parse_args(argv)
    out = (ROOT / a.out) if not a.out.is_absolute() else a.out

    import rasterio
    from rasterio.features import geometry_mask
    ds = rasterio.open(out / "BLOCK40_SOURCE_MASK.tif")
    cls = ds.read(1); contrib = ds.read(2); year = ds.read(3); unc = ds.read(4); emp = ds.read(5)
    band_r = ds.read(6); adm_r = ds.read(7)
    import rasterio.transform
    depth_ds = rasterio.open(ROOT / "outputs/ground_truth_s1a_20211028_ext20/bathymetry_merged_utm.tif")
    depth = depth_ds.read(3)

    rows = []
    for spec in a.runs:
        label, d = spec.split(":", 1)
        run = (ROOT / d) if not Path(d).is_absolute() else Path(d)
        for r in csv.DictReader(open(run / "windows.csv")):
            if r["status"] != "ok":
                continue
            xs = [float(r[f"fp_E{i}"]) for i in range(4)]; ys = [float(r[f"fp_N{i}"]) for i in range(4)]
            poly = {"type": "Polygon", "coordinates": [list(zip(xs + xs[:1], ys + ys[:1]))]}
            r0, c0 = ds.index(min(xs), max(ys)); r1, c1 = ds.index(max(xs), min(ys))
            r0, c0 = max(r0 - 1, 0), max(c0 - 1, 0)
            r1, c1 = min(r1 + 2, cls.shape[0]), min(c1 + 2, cls.shape[1])
            if r1 <= r0 or c1 <= c0:
                continue
            wt = ds.transform * rasterio.Affine.translation(c0, r0)
            inside = ~geometry_mask([poly], out_shape=(r1 - r0, c1 - c0), transform=wt, all_touched=True)
            if not inside.any():
                continue
            sub = lambda arr: arr[r0:r1, c0:c1][inside]
            cc = sub(cls); dd = sub(depth)
            n = cc.size
            frac = {int(k): float((cc == k).sum()) / n for k in np.unique(cc)}
            dmean = float(np.nanmean(dd)) if np.isfinite(dd).any() else float("nan")
            band = int(np.rint(np.nanmedian(sub(band_r)))) if np.isfinite(sub(band_r)).any() else 0
            klass, dom = window_class(frac, band, a.threshold)
            row = {"run": label, "product": label.split("_")[0], "geometry": label.split("_")[1],
                   "transect": int(r["transect"]), "distance_m": float(r["distance_m"]),
                   "E": float(r["E"]), "N": float(r["N"]), "window_m": abs(xs[1] - xs[0]) if len(xs) > 1 else np.nan,
                   "depth_mean_m": dmean,
                   "depth_p10_m": float(np.nanpercentile(dd, 10)) if np.isfinite(dd).any() else np.nan,
                   "depth_p90_m": float(np.nanpercentile(dd, 90)) if np.isfinite(dd).any() else np.nan,
                   "band": band, "band_name": BAND_NAME.get(band, "outside_bands"),
                   "window_class": klass, "dominant_class": dom, "dominant_class_name": CLASS.get(dom, "?"),
                   "admissible_fraction": float(frac.get(ADMISSIBLE_BY_BAND.get(band, -1), 0.0)),
                   "cells": int(n),
                   "contributor_mode": int(np.rint(np.nanmedian(sub(contrib)))) if np.isfinite(sub(contrib)).any() else -1,
                   "year_min": float(np.nanmin(sub(year))) if np.isfinite(sub(year)).any() else np.nan,
                   "declared_unc_max_m": float(np.nanmax(sub(unc))) if np.isfinite(sub(unc)).any() else np.nan,
                   "empirical_unc_max_m": float(np.nanmax(sub(emp))) if np.isfinite(sub(emp)).any() else np.nan,
                   "admissible_cell_fraction": float(np.nanmean(sub(adm_r) == 1)),
                   "sar_wavelength_m": float(r["wavelength_m"]) if r.get("wavelength_m") else np.nan,
                   "sar_identifiable": r.get("identifiable") == "True",
                   "peak_at_kmin_edge": r.get("peak_at_kmin_edge") == "True"}
            for c in CLASS:
                row[f"frac_{CLASS[c]}"] = frac.get(c, 0.0)
            for t in a.sensitivity_thresholds:
                row[f"class_at_{t:g}"] = window_class(frac, band, t)[0]
            rows.append(row)
        print(f"{label}: {sum(1 for x in rows if x['run'] == label)} windows", flush=True)

    with open(out / "BLOCK40_WINDOW_PROVENANCE.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    summ = {}
    for label in {r["run"] for r in rows}:
        sel = [r for r in rows if r["run"] == label]
        summ[label] = {"windows": len(sel),
                       "by_class": {k: sum(1 for r in sel if r["window_class"] == k)
                                    for k in sorted({r["window_class"] for r in sel})},
                       "primary_by_band": {BAND_NAME[b]: sum(1 for r in sel if r["window_class"] == "primary_admissible" and r["band"] == b)
                                           for b in (1, 2, 3)},
                       "primary_at_sensitivity": {f"{t:g}": sum(1 for r in sel if r[f"class_at_{t:g}"] == "primary_admissible")
                                                  for t in a.sensitivity_thresholds}}
    (out / "BLOCK40_WINDOW_PROVENANCE_SUMMARY.json").write_text(json.dumps(summ, indent=2))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()

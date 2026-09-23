#!/usr/bin/env python
"""Block40 step 1 - ground-truth provenance audit.

Resolves every ground-truth cell of the Duck bbox to an actual survey (BlueTopo
contributor id, source_survey_id, institution, survey dates, coverage and
bathy_coverage flags, declared uncertainty, native resolution), measures the
empirical agreement with the FRF survey DEM where the two overlap, and writes

  BLOCK40_SOURCE_INVENTORY.csv   one row per resolvable source
  BLOCK40_SOURCE_MASK.tif        per-cell class / contributor / year / uncertainty /
                                 direct flag / band admissibility
  BLOCK40_SOURCE_AUDIT.json      machine-readable summary

Four quantities stay distinct and are never converted into one another: declared
per-cell vertical uncertainty, empirical NMAD against a higher-ranked survey, survey
age, and morphological change (not estimated here).

Class codes in band 1 of the mask:
  0 none                      1 FRF survey DEM 2021 (direct, 8 days before)
  2 BlueTopo direct 2019-2020 with NMAD vs FRF <= 0.5 m
  3 BlueTopo direct 2019-2020 uncertifiable or NMAD > 0.5 m
  4 BlueTopo direct H12859 (2016 MBES)
  5 BlueTopo direct, other date
  6 BlueTopo interpolated / generalised / pre-2010
  7 legacy grid with a removed bias (nhatt, VIMS)   8 CUDEM only
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

CLASS_NAMES = {0: "none", 1: "frf_survey_2021", 2: "bluetopo_direct_2019_2020_certified",
               3: "bluetopo_direct_2019_2020_uncertain", 4: "bluetopo_direct_h12859_2016",
               5: "bluetopo_direct_other_date", 6: "bluetopo_interpolated_or_pre2010",
               7: "legacy_bias_corrected", 8: "cudem"}
ACQUISITION = datetime(2021, 10, 28, 23, 6, 36, tzinfo=timezone.utc)


def nmad(d):
    d = np.asarray(d, float); d = d[np.isfinite(d)]
    return float(1.4826 * np.median(np.abs(d - np.median(d)))) if d.size else float("nan")


def is_direct(meta):
    sid = (meta.get("source_survey_id") or "")
    if "interpolated" in sid.lower() or "generalization" in sid.lower():
        return False
    return str(meta.get("coverage")) == "1" and str(meta.get("bathy_coverage")) == "1"


def survey_age_days(meta):
    try:
        d = datetime.fromisoformat((meta.get("survey_date_end") or meta["survey_date_start"])).replace(tzinfo=timezone.utc)
    except Exception:
        return float("nan")
    return (ACQUISITION - d).total_seconds() / 86400.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ground-truth", type=Path, default=Path("outputs/ground_truth_s1a_20211028_ext20"))
    ap.add_argument("--frf-survey-npz", type=Path, default=Path("outputs/ground_truth_s1a_20211028/frf_survey_dem.npz"))
    ap.add_argument("--out", type=Path, default=Path("duck_frf/Block40_stratified_validation"))
    ap.add_argument("--max-nmad-m", type=float, default=0.5)
    ap.add_argument("--recent-window", nargs=2, default=["2019-01-01", "2020-12-31"])
    a = ap.parse_args(argv)
    gt = (ROOT / a.ground_truth) if not a.ground_truth.is_absolute() else a.ground_truth
    out = (ROOT / a.out) if not a.out.is_absolute() else a.out
    out.mkdir(parents=True, exist_ok=True)

    import rasterio
    import pyproj
    from rasterio.warp import reproject, Resampling
    from scipy.interpolate import griddata

    merged = rasterio.open(gt / "bathymetry_merged_utm.tif")
    bed = merged.read(1); merged_src = merged.read(2); emp_merged = merged.read(8)
    shape = bed.shape; T = merged.transform; epsg = merged.crs.to_epsg()
    nanarr = lambda: np.full(shape, np.nan, "float32")

    def warp(path, band, method):
        arr = nanarr()
        with rasterio.open(path) as ds:
            data = ds.read(band, masked=True).astype("float32").filled(np.nan)
            reproject(data, arr, src_transform=ds.transform, src_crs=ds.crs, dst_transform=T,
                      dst_crs=merged.crs, resampling=method, src_nodata=np.nan, dst_nodata=np.nan)
        return arr

    prov = json.loads((gt / "bluetopo_bbox.tif.provenance.json").read_text())
    contributors = {int(k): v for k, v in prov["contributors"].items()}
    bt_z = warp(gt / "bluetopo_bbox.tif", 1, Resampling.average)
    bt_u = warp(gt / "bluetopo_bbox.tif", 2, Resampling.average)
    bt_c = warp(gt / "bluetopo_bbox.tif", 3, Resampling.nearest)

    # FRF survey DEM on the merged grid, strictly inside its own footprint
    frf = nanarr(); frf_meta = {}
    npz = (ROOT / a.frf_survey_npz) if not a.frf_survey_npz.is_absolute() else a.frf_survey_npz
    if npz.exists():
        s = np.load(npz)
        la, lo, el = s["latitude"].ravel(), s["longitude"].ravel(), s["elevation_navd88"].ravel()
        ok = np.isfinite(el) & np.isfinite(la)
        tr = pyproj.Transformer.from_crs(4326, epsg, always_xy=True)
        E, N = tr.transform(lo[ok], la[ok])
        gx = T.c + (np.arange(shape[1]) + .5) * T.a; gy = T.f + (np.arange(shape[0]) + .5) * T.e
        GX, GY = np.meshgrid(gx, gy)
        frf = griddata(np.column_stack((E, N)), el[ok], (GX, GY), method="linear").astype("float32")
        frf_meta = {"product": "FRF_geomorphology_DEMs_surveyDEM_20211021.nc", "survey_time_utc": "2021-10-21T00:00:00+00:00",
                    "age_days": round((ACQUISITION - datetime(2021, 10, 21, tzinfo=timezone.utc)).total_seconds() / 86400, 2),
                    "footprint": "xFRF 50-950 m, yFRF -100..1100 m (never extrapolated)",
                    "declared_uncertainty_m": 0.15, "datum": "NAVD88", "native_grid_m": 20.0}

    lo_d, hi_d = [datetime.fromisoformat(x).replace(tzinfo=timezone.utc) for x in a.recent_window]
    rows = []
    cls = np.zeros(shape, "float32"); adm_class = {}
    for cid, meta in contributors.items():
        m = np.isfinite(bt_c) & (np.rint(bt_c) == cid)
        n = int(m.sum())
        if not n:
            continue
        direct = is_direct(meta)
        try:
            start = datetime.fromisoformat(meta["survey_date_start"]).replace(tzinfo=timezone.utc)
        except Exception:
            start = None
        ov = m & np.isfinite(frf) & np.isfinite(bt_z)
        d = (bt_z - frf)[ov]
        nm = nmad(d) if ov.sum() >= 200 else float("nan")
        depth = -bed[m]
        sid = meta.get("source_survey_id") or ""
        recent = bool(start and lo_d <= start <= hi_d)
        h12859 = "h12859" in sid.lower()
        if not direct:
            c = 6
        elif recent:
            c = 2 if (np.isfinite(nm) and nm <= a.max_nmad_m) else 3
        elif h12859:
            c = 4
        elif start and start.year < 2010:
            c = 6
        else:
            c = 5
        cls[m] = c
        adm_class[cid] = c
        rows.append({"source_key": f"bluetopo_{cid}", "product": "NOAA BlueTopo", "contributor_id": cid,
                     "source_survey_id": sid, "source_institution": meta.get("source_institution"),
                     "survey_date_start": meta.get("survey_date_start"), "survey_date_end": meta.get("survey_date_end"),
                     "age_days_at_acquisition": round(survey_age_days(meta), 1),
                     "coverage": meta.get("coverage"), "bathy_coverage": meta.get("bathy_coverage"),
                     "direct": direct, "native_resolution_m": 4.0, "horizontal_datum": "NAD83 / UTM 18N",
                     "vertical_datum": "NAVD88",
                     "declared_vert_uncert_fixed_m": meta.get("vertical_uncert_fixed"),
                     "declared_vert_uncert_var": meta.get("vertical_uncert_var"),
                     "cells_merged_grid": n, "cells_overlap_frf": int(ov.sum()),
                     "median_minus_frf_m": float(np.median(d)) if ov.sum() >= 200 else "",
                     "empirical_nmad_vs_frf_m": nm if np.isfinite(nm) else "",
                     "depth_p05_m": float(np.nanpercentile(depth, 5)) if np.isfinite(depth).any() else "",
                     "depth_p95_m": float(np.nanpercentile(depth, 95)) if np.isfinite(depth).any() else "",
                     "datum_correction_applied_m": 0.0, "bias_removed_m": "",
                     "bias_provenance": "", "class": c, "class_name": CLASS_NAMES[c]})

    # FRF, legacy and CUDEM cells from the merged source band (1 FRF, 4 legacy, 2 CUDEM)
    mfrf = merged_src == 1; cls[mfrf] = 1
    mleg = merged_src == 4; cls[mleg] = np.where(cls[mleg] == 0, 7, 7)
    mcud = merged_src == 2; cls[mcud] = np.where(cls[mcud] == 0, 8, cls[mcud])
    if mfrf.any():
        depth = -bed[mfrf]
        rows.append({"source_key": "frf_survey_dem_2021", "product": "FRF geomorphology survey DEM",
                     "contributor_id": "", "source_survey_id": frf_meta.get("product", ""),
                     "source_institution": "USACE FRF", "survey_date_start": "2021-10-21", "survey_date_end": "2021-10-21",
                     "age_days_at_acquisition": frf_meta.get("age_days", ""), "coverage": 1, "bathy_coverage": 1,
                     "direct": True, "native_resolution_m": 20.0, "horizontal_datum": "FRF local / WGS84",
                     "vertical_datum": "NAVD88", "declared_vert_uncert_fixed_m": 0.15, "declared_vert_uncert_var": "",
                     "cells_merged_grid": int(mfrf.sum()), "cells_overlap_frf": int(mfrf.sum()),
                     "median_minus_frf_m": 0.0, "empirical_nmad_vs_frf_m": "",
                     "depth_p05_m": float(np.nanpercentile(depth, 5)), "depth_p95_m": float(np.nanpercentile(depth, 95)),
                     "datum_correction_applied_m": 0.0, "bias_removed_m": "", "bias_provenance": "",
                     "class": 1, "class_name": CLASS_NAMES[1]})
    merge_report = json.loads((gt / "MERGE_REPORT.json").read_text())
    for spec in merge_report.get("legacy", []):
        rows.append({"source_key": "legacy_" + spec["label"].split()[0].lower(), "product": spec["label"],
                     "contributor_id": "", "source_survey_id": spec["label"], "source_institution": "USGS / VIMS",
                     "survey_date_start": str(int(spec["year"])), "survey_date_end": str(int(spec["year"])),
                     "age_days_at_acquisition": round((ACQUISITION - datetime(int(spec["year"]), 1, 1, tzinfo=timezone.utc)).total_seconds() / 86400, 1),
                     "coverage": 1, "bathy_coverage": 1, "direct": True, "native_resolution_m": 40.0,
                     "horizontal_datum": "see source", "vertical_datum": "NAVD88 after datum shift",
                     "declared_vert_uncert_fixed_m": "", "declared_vert_uncert_var": "",
                     "cells_merged_grid": int(mleg.sum()), "cells_overlap_frf": spec.get("overlap_cells", ""),
                     "median_minus_frf_m": "", "empirical_nmad_vs_frf_m": spec.get("residual_nmad_m", ""),
                     "depth_p05_m": "", "depth_p95_m": "",
                     "datum_correction_applied_m": spec.get("datum_offset_to_navd88_m", ""),
                     "bias_removed_m": spec.get("correction_applied_m", ""),
                     "bias_provenance": "constant bias estimated against modern cells in the same area used for validation "
                                        "-> not independent ground truth",
                     "class": 7, "class_name": CLASS_NAMES[7]})

    # per-cell band admissibility: depth band decides which class is admissible
    depth_c = -bed
    band = np.zeros(shape, "float32")
    band[(depth_c > 0) & (depth_c <= 12)] = 1
    band[(depth_c > 12) & (depth_c <= 20)] = 2
    band[(depth_c > 20) & (depth_c <= 30)] = 3
    adm = np.zeros(shape, "float32")
    adm[(band == 1) & (cls == 1)] = 1
    adm[(band == 2) & (cls == 2)] = 1
    adm[(band == 3) & (cls == 4)] = 1

    year = nanarr(); unc = nanarr()
    for cid, meta in contributors.items():
        m = np.isfinite(bt_c) & (np.rint(bt_c) == cid)
        try:
            year[m] = float(meta["survey_date_start"][:4])
        except Exception:
            pass
        try:
            unc[m] = float(meta.get("vertical_uncert_fixed"))
        except Exception:
            pass
    year[mfrf] = 2021.0; unc[mfrf] = 0.15

    with rasterio.open(out / "BLOCK40_SOURCE_MASK.tif", "w", driver="GTiff", height=shape[0], width=shape[1],
                       count=7, dtype="float32", crs=merged.crs, transform=T, nodata=np.nan, compress="deflate") as ds:
        for i, arr in enumerate((cls, bt_c, year, unc, emp_merged, band, adm), 1):
            ds.write(arr.astype("float32"), i)
        ds.descriptions = ("source class (see BLOCK40_SOURCE_AUDIT.json)", "BlueTopo contributor id",
                           "survey start year", "declared vertical uncertainty m",
                           "empirical vertical uncertainty m (Block39 merge)", "depth band 1:0-12 2:12-20 3:20-30",
                           "admissible for its own depth band (1/0)")
    merged.close()

    rows.sort(key=lambda r: -(r["cells_merged_grid"] or 0))
    keys = list(rows[0])
    with open(out / "BLOCK40_SOURCE_INVENTORY.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)

    tot = float(np.isfinite(bed).sum())
    audit = {"acquisition_utc": ACQUISITION.isoformat(), "class_names": CLASS_NAMES,
             "criteria": {"direct": "coverage=1 and bathy_coverage=1 and survey id without 'interpolated'/'Generalization'",
                          "recent_window": a.recent_window, "max_empirical_nmad_m": a.max_nmad_m},
             "frf_survey": frf_meta,
             "cells_total_with_bed": int(tot),
             "cell_fraction_by_class": {CLASS_NAMES[c]: float((cls == c).sum() / tot) for c in CLASS_NAMES},
             "cell_fraction_admissible_by_band": {
                 "0-12 m": float((adm[band == 1] == 1).mean()) if (band == 1).any() else 0.0,
                 "12-20 m": float((adm[band == 2] == 1).mean()) if (band == 2).any() else 0.0,
                 "20-30 m": float((adm[band == 3] == 1).mean()) if (band == 3).any() else 0.0},
             "band_cells": {f"band{int(b)}": int((band == b).sum()) for b in (1, 2, 3)},
             "notes": ["declared uncertainty, empirical NMAD, survey age and morphological change are distinct quantities",
                       "a vertical NMAD is never reinterpreted as a morphological-change estimate",
                       "legacy grids carry a bias calibrated on the same area used for validation and are not independent truth"]}
    (out / "BLOCK40_SOURCE_AUDIT.json").write_text(json.dumps(audit, indent=2, default=float))
    print(json.dumps({k: audit[k] for k in ("cell_fraction_by_class", "cell_fraction_admissible_by_band", "band_cells")},
                     indent=1, default=float))


if __name__ == "__main__":
    main()

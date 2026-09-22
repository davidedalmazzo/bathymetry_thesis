#!/usr/bin/env python
"""One command for the Duck/FRF ground truth of a SAR acquisition.

  python code/frf_ground_truth.py --timestamp-utc 2021-10-28T23:06:39Z \
         --bbox -75.79 36.15 -75.70 36.22 --out outputs/ground_truth_20211028 \
         --tranche gt_20211028 --new-tranche

Linked pieces (no scene-specific configuration files):
  1. FRF observations via the existing FRF client (waves incl. spectra, currents,
     wind, water level) -> <out>/frf_observations/  (frf_client_cli / run_block32)
  2. FRF gridded survey DEM nearest in time            -> frf_client/dem.py
  3. NOAA BlueTopo (per-cell uncertainty + source survey) and NOAA NCEI CUDEM
     for the bbox (offshore)                              -> coastal_dem.py
  4. merged bathymetry on a local UTM grid ranked by measured accuracy: FRF survey
     > BlueTopo modern > legacy grids (bias-corrected against modern data,
     --legacy-grid) > BlueTopo interpolated > CUDEM; empirical-uncertainty band
  5. GROUND_TRUTH.json summarising level, currents, wind, per-instrument spectra.

All network use goes through named, budgeted tranches (FRF) or bbox-limited
HTTP range reads (CUDEM).  Vertical datum NAVD88 throughout.
"""
from __future__ import annotations
import argparse, csv, json, math, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repository_paths import ROOT                                   # noqa: E402
import coastal_dem                                                   # noqa: E402
from frf_client import dem as frf_dem                                # noqa: E402
from frf_client.transport import Transport                           # noqa: E402


def utc_epoch(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def observations(args, out):
    import run_block32_frf_client as frf
    argv = ["--mode", "fetch", "--acquisition-id", args.acquisition_id, "--timestamp-utc", args.timestamp_utc,
            "--output", str(out), "--config", args.frf_config, "--cache", args.cache,
            "--tranche", args.tranche, "--budget-config", args.budget_config]
    if args.new_tranche and not (ROOT / "_cache/frf_tranches" / args.tranche).exists():
        argv.append("--new-tranche")
    frf.main(argv)
    return out / args.acquisition_id


def summarise_observations(dossier, epoch):
    rows = list(csv.DictReader(open(dossier / "OBSERVATIONS.csv")))
    def nearest(family, variable):
        c = [r for r in rows if r["family"] == family and r["variable"] == variable and r["value"] not in ("", "nan")]
        if not c:
            return None
        r = min(c, key=lambda r: abs(float(r["offset_seconds"])))
        return {"instrument": r["instrument_id"], "value": float(r["value"]), "units": r["units"],
                "time_utc": r["sensor_time_utc"], "offset_s": float(r["offset_seconds"]),
                "qc_flag": r["qc_flag"], "status": r["status"], "representative_eligible": r["representative_eligible"]}
    out = {"water_level_navd88": nearest("water_level", "waterLevel"),
           "water_level_predicted": nearest("water_level", "predictedWaterLevel"),
           "water_level_residual": nearest("water_level", "residualWaterLevel"),
           "current_east": nearest("currents", "aveE"), "current_north": nearest("currents", "aveN"),
           "wind_speed": nearest("wind", "windSpeed"), "wind_direction_from": nearest("wind", "windDirection")}
    spectra = []; spectra_arrays = {}
    summ = json.loads((dossier / "SPECTRAL_SUMMARIES.json").read_text())
    tensors = json.loads((dossier / "TENSORS.json").read_text())
    for s in summ:
        try:
            key, _, var, idx = s["tensor_pointer"].split("/")[:4]
            item = tensors[key]; f = np.asarray(item["variables"]["waveFrequency"]["raw_values"], float)
            e = np.asarray(item["variables"][var]["raw_values"], float)[int(idx)]
            ok = np.isfinite(e) & np.asarray(item["variables"][var]["valid_mask"], bool)[int(idx)]
            k = int(np.nanargmax(np.where(ok, e, np.nan))); half = ok & (e >= e[k] / 2)
            pb = s.get("published_peak_band", {})
            spectra_arrays[s["instrument_id"]] = {"frequency_hz": f.tolist(), "energy_m2_hz": np.where(ok, e, np.nan).tolist(),
                                                  "offset_s": s.get("offset_seconds"), "tensor_pointer": s["tensor_pointer"]}
            spectra.append({"instrument": s["instrument_id"], "offset_s": s.get("offset_seconds"), "Hm0_m": s.get("Hm0_m"),
                            "published_Tp_s": pb.get("waveTp"), "discrete_peak_hz": float(f[k]), "discrete_peak_period_s": float(1 / f[k]),
                            "half_power_hz": [float(f[half].min()), float(f[half].max())],
                            "mean_direction_from_peak_deg": pb.get("waveMeanDirectionPeakFrequency"),
                            "directional_spread_deg": pb.get("directionalPeakSpread"), "status": s.get("status")})
        except Exception as exc:                        # keep other instruments
            spectra.append({"instrument": s.get("instrument_id"), "error": type(exc).__name__})
    out["wave_spectra"] = spectra
    (dossier.parent.parent / "wave_spectra.json").write_text(json.dumps(spectra_arrays, default=float))
    return out


def _nmad(d):
    d = np.asarray(d, float); d = d[np.isfinite(d)]
    return float(1.4826 * np.median(np.abs(d - np.median(d)))) if d.size else float("nan")


def water_level(wl, policy, max_offset_s=1800.0):
    """Event water level actually used for band 3, with the reason it was accepted or not.
    The FRF eopNoaaTide feed is NOAA *preliminary* data: it carries no QC flag
    (status 'qc_unknown', representative_eligible False), so under the default
    policy it is reported but not applied."""
    if not wl:
        return None, {"used": False, "reason": "no water level observation", "policy": policy}
    st = {"policy": policy, "instrument": wl["instrument"], "value_m": wl["value"], "offset_s": wl["offset_s"],
          "qc_status": wl["status"], "qc_flag": wl["qc_flag"], "representative_eligible": wl["representative_eligible"]}
    if abs(wl["offset_s"]) > max_offset_s:
        return None, {**st, "used": False, "reason": f"nearest measurement is {wl['offset_s']:.0f} s from the acquisition"}
    ok_qc = str(wl["status"]).lower() == "retrieved" and str(wl["representative_eligible"]).lower() == "true"
    if policy == "qc_only" and not ok_qc:
        return None, {**st, "used": False,
                      "reason": "not QC'd / not representative_eligible; depth band = -bed (NAVD88), "
                                "add this water level and the wave setup to the error budget "
                                f"(offset would be {wl['value']:+.3f} m)"}
    return wl["value"], {**st, "used": True, "reason": "QC passed" if ok_qc else "policy=preliminary"}


def merged_bathymetry(bbox, survey, res, out_tif, eta, bluetopo_tif=None, bluetopo_prov=None, cudem_tif=None,
                      frf_uncertainty=0.15, frf_year=None, legacy=(), modern_min_year=2010,
                      legacy_min_depth=9.0, min_overlap_cells=200):
    """Merge bathymetry sources on a local UTM grid, ranked by *measured* accuracy.

    Priority: 1 FRF survey DEM > 3 BlueTopo modern (non-interpolated, source year >=
    modern_min_year) > 4 legacy grids (bias-corrected) > 5 BlueTopo interpolated/old
    > 2 CUDEM.
    Legacy grids (e.g. USGS OFR 2011-1015 'nhatt') are shifted to NAVD88 with their
    declared datum offset, then a constant bias is estimated against modern cells
    (FRF + BlueTopo modern) in the overlap deeper than legacy_min_depth (shallower
    cells are dominated by bar migration).  Empirical uncertainty (band 8):
    FRF nominal; BlueTopo modern = NMAD vs FRF survey where they overlap (else the
    declared value); legacy = NMAD of the bias-corrected overlap residual; others =
    declared (BlueTopo) or NaN (CUDEM).
    Bands: 1 bed NAVD88, 2 source class, 3 event depth, 4 declared uncertainty,
    5 BlueTopo contributor id, 6 source year, 7 interpolated flag, 8 empirical uncertainty.
    """
    import rasterio, pyproj
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    from scipy.interpolate import griddata
    lon0, lat0, lon1, lat1 = bbox
    zone = int(((lon0 + lon1) / 2 + 180) // 6) + 1; epsg = (32600 if lat0 >= 0 else 32700) + zone
    tr = pyproj.Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = tr.transform([lon0, lon1, lon0, lon1], [lat0, lat0, lat1, lat1])
    e0, n1 = math.floor(min(xs) / res) * res, math.ceil(max(ys) / res) * res
    ne = int(math.ceil((max(xs) - e0) / res)); nn = int(math.ceil((n1 - min(ys)) / res))
    T = from_origin(e0, n1, res, res); shape = (nn, ne)
    nan = lambda: np.full(shape, np.nan, "float32")
    z = nan(); src = np.zeros(shape, "float32"); unc = nan(); emp = nan(); con = nan(); year = nan(); interp = nan()
    report = {"sources": {}, "legacy": []}

    def warp(path, band, method):
        a = nan()
        with rasterio.open(path) as ds:
            data = ds.read(band, masked=True).astype("float32").filled(np.nan)
            reproject(data, a, src_transform=ds.transform, src_crs=ds.crs, dst_transform=T, dst_crs=f"EPSG:{epsg}",
                      resampling=method, src_nodata=np.nan, dst_nodata=np.nan)
        return a

    def put(mask, value, cls, u_decl, u_emp, yr, itp, cid=np.nan):
        z[mask] = value[mask]; src[mask] = cls
        unc[mask] = u_decl[mask] if np.ndim(u_decl) else u_decl
        emp[mask] = u_emp[mask] if np.ndim(u_emp) else u_emp
        year[mask] = yr[mask] if np.ndim(yr) else yr
        interp[mask] = itp[mask] if np.ndim(itp) else itp
        con[mask] = cid[mask] if np.ndim(cid) else cid

    # --- FRF survey on the grid (needed as reference for empirical accuracy)
    frf = nan()
    if survey is not None:
        la, lo, el = survey["latitude"].ravel(), survey["longitude"].ravel(), survey["elevation_navd88"].ravel()
        ok = np.isfinite(el) & np.isfinite(la)
        E, N = tr.transform(lo[ok], la[ok])
        gx = e0 + (np.arange(ne) + .5) * res; gy = n1 - (np.arange(nn) + .5) * res
        GX, GY = np.meshgrid(gx, gy)
        frf = griddata(np.column_stack((E, N)), el[ok], (GX, GY), method="linear").astype("float32")
    # --- BlueTopo split into modern / interpolated-or-old
    bt_mod = np.zeros(shape, bool); bt_old = np.zeros(shape, bool)
    if bluetopo_tif:
        bz = warp(bluetopo_tif, 1, Resampling.average); bu = warp(bluetopo_tif, 2, Resampling.max)
        bc = warp(bluetopo_tif, 3, Resampling.mode)
        byr = nan(); bitp = nan()
        for key, meta in (bluetopo_prov or {}).get("contributors", {}).items():
            m = bc == float(key)
            try:
                byr[m] = float((meta.get("survey_date_start") or "nan")[:4])
            except ValueError:
                pass
            sid = (meta.get("source_survey_id") or "").lower()
            bitp[m] = 1.0 if ("interpolated" in sid or "generaliz" in sid) else 0.0
        have = np.isfinite(bz)
        bt_mod = have & (bitp == 0) & (byr >= modern_min_year)
        bt_old = have & ~bt_mod
        # empirical accuracy of each modern contributor against the FRF survey
        bemp = bu.copy(); bemp_src = {}
        for cid in np.unique(bc[bt_mod & np.isfinite(bc)]):
            m = bt_mod & (bc == cid); ov = m & np.isfinite(frf)
            if ov.sum() >= min_overlap_cells:
                d = bz[ov] - frf[ov]; v = _nmad(d)
                bemp[m] = v; bemp_src[float(cid)] = "frf"
                report["sources"][f"bluetopo_{int(cid)}_vs_frf"] = {"cells": int(ov.sum()), "median_m": float(np.median(d)), "nmad_m": v}
    # --- write in reverse priority order
    if cudem_tif:
        c = warp(cudem_tif, 1, Resampling.average); m = np.isfinite(c)
        put(m, c, 2, np.nan, np.nan, np.nan, np.nan)
    if bluetopo_tif:
        put(bt_old, bz, 5, bu, bu, byr, bitp, bc)
    modern = nan()
    if bluetopo_tif:
        modern[bt_mod] = bz[bt_mod]
    modern[np.isfinite(frf)] = frf[np.isfinite(frf)]
    legacy_corr = nan()
    for spec in legacy:
        g = warp(spec["path"], 1, Resampling.average) + float(spec.get("datum_offset_to_navd88_m", 0.0))
        g[g > 0] = np.nan                                  # keep underwater cells only
        ov = np.isfinite(g) & np.isfinite(modern) & (modern < -legacy_min_depth)
        rec = {k: spec[k] for k in spec if k != "path"}; rec["overlap_cells"] = int(ov.sum())
        if ov.sum() >= min_overlap_cells:
            d = g[ov] - modern[ov]; bias = float(np.median(d)); resid = _nmad(d - bias)
            dep = -modern[ov]; bins = []
            for lo_, hi_ in ((9, 12), (12, 15), (15, 18), (18, 22), (22, 30)):
                k = (dep >= lo_) & (dep < hi_)
                if k.sum() >= 50:
                    bins.append({"depth_m": [lo_, hi_], "cells": int(k.sum()), "median_m": float(np.median(d[k])), "nmad_m": _nmad(d[k])})
            rec.update(bias_vs_modern_m=bias, residual_nmad_m=resid, by_depth=bins, correction_applied_m=-bias)
            g = g - bias
            legacy_corr = np.where(np.isfinite(legacy_corr), legacy_corr, g)
            fill = np.isfinite(g) & ~np.isfinite(modern)
            put(fill, g, 4, np.nan, resid, float(spec.get("year", np.nan)), 0.0)
        else:
            rec["status"] = "not used: insufficient overlap with modern data to estimate bias"
        report["legacy"].append(rec)
    if bluetopo_tif:
        # modern contributors without FRF overlap: NMAD against the bias-corrected legacy
        # grid is an upper bound of their own scatter (combined error of both sources)
        for cid in np.unique(bc[bt_mod & np.isfinite(bc)]):
            if float(cid) in bemp_src:
                continue
            m = bt_mod & (bc == cid); ov = m & np.isfinite(legacy_corr) & (bz < -legacy_min_depth)
            if ov.sum() >= min_overlap_cells:
                d = bz[ov] - legacy_corr[ov]; v = _nmad(d); bemp[m] = v
                report["sources"][f"bluetopo_{int(cid)}_vs_legacy_corrected"] = {
                    "cells": int(ov.sum()), "median_m": float(np.median(d)), "nmad_m": v,
                    "note": "upper bound (combined scatter of both sources)"}
        put(bt_mod, bz, 3, bu, bemp, byr, bitp, bc)
    if survey is not None:
        m = np.isfinite(frf); put(m, frf, 1, frf_uncertainty, frf_uncertainty, frf_year or np.nan, 0.0)
    # band 3 is the still-water depth: the event water level when it is accepted,
    # otherwise the NAVD88 datum itself (depth = -bed), which must then be declared
    depth = (eta - z) if eta is not None else -z
    with rasterio.open(out_tif, "w", driver="GTiff", height=nn, width=ne, count=8, dtype="float32",
                       crs=f"EPSG:{epsg}", transform=T, nodata=np.nan, compress="deflate") as ds:
        for i, a in enumerate((z, src, depth, unc, con, year, interp, emp), 1):
            ds.write(a.astype("float32"), i)
        ds.descriptions = ("bed elevation NAVD88 m",
                           "source 1 FRF survey / 3 BlueTopo modern / 4 legacy corrected / 5 BlueTopo interpolated-old / 2 CUDEM / 0 none",
                           "still-water depth m (event water level - bed, or -bed when no QC'd water level)", "declared vertical uncertainty m",
                           "BlueTopo contributor id", "source survey start year", "interpolated source flag",
                           "empirical vertical uncertainty m (NMAD vs higher-ranked data)")
    frac = {f"fraction_class_{c}": float((src == c).mean()) for c in (1, 2, 3, 4, 5)}
    return {"utm_epsg": epsg, "resolution_m": res, "cells": [nn, ne], **frac,
            "frf_nominal_uncertainty_m": frf_uncertainty, "modern_min_year": modern_min_year,
            "legacy_min_depth_m": legacy_min_depth, **report}


def figure(out_tif, png):
    import rasterio, matplotlib
    matplotlib.use("Agg"); import matplotlib.pyplot as plt
    with rasterio.open(out_tif) as ds:
        z = ds.read(1); s = ds.read(2); b = ds.bounds
    fig, ax = plt.subplots(1, 2, figsize=(12, 6))
    im = ax[0].imshow(z, extent=[b.left, b.right, b.bottom, b.top], cmap="terrain", vmin=-20, vmax=10)
    ax[0].contour(np.linspace(b.left, b.right, z.shape[1]), np.linspace(b.top, b.bottom, z.shape[0]), z, levels=[-15, -10, -8, -6, -4, -2, 0], colors="k", linewidths=.4)
    fig.colorbar(im, ax=ax[0], label="bed elevation NAVD88 (m)")
    with rasterio.open(out_tif) as ds:
        u = ds.read(4)
        u = ds.read(8) if ds.count >= 8 else u
    im2 = ax[1].imshow(u, extent=[b.left, b.right, b.bottom, b.top], cmap="magma_r", vmin=0, vmax=1.5)
    fig.colorbar(im2, ax=ax[1], label="empirical vertical uncertainty (m)"); ax[1].set_title("empirical uncertainty (NMAD vs higher-ranked data)")
    for a in ax:
        a.set_xlabel("UTM E (m)"); a.set_ylabel("UTM N (m)"); a.set_aspect("equal")
    fig.tight_layout(); fig.savefig(png, dpi=140); plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--timestamp-utc", required=True)
    ap.add_argument("--bbox", nargs=4, type=float, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--acquisition-id", default="acquisition")
    ap.add_argument("--tranche", required=True, help="named FRF network tranche (budgeted, persistent)")
    ap.add_argument("--new-tranche", action="store_true")
    ap.add_argument("--budget-config", default="examples/frf/budget_ground_truth.json")
    ap.add_argument("--frf-config", default="examples/frf/client.json")
    ap.add_argument("--cache", default="_cache/frf_client")
    ap.add_argument("--dem-max-days", type=float, default=45.0)
    ap.add_argument("--grid-res", type=float, default=10.0)
    ap.add_argument("--skip-observations", action="store_true")
    ap.add_argument("--water-level-policy", choices=("qc_only", "preliminary"), default="qc_only",
                    help="qc_only (default): use the measured water level only if it passed QC and is flagged "
                         "representative_eligible; otherwise band 3 is depth = -bed (still-water datum NAVD88). "
                         "preliminary: accept the nearest measurement within 30 min whatever its QC status")
    ap.add_argument("--legacy-grid", action="append", default=[], metavar="PATH|URL.zip,OFFSET,LABEL,YEAR",
                    help="older gridded survey; OFFSET = its datum minus NAVD88 correction to add (m), e.g. MSL->NAVD88 at the "
                         "nearest tide station; a zip URL is downloaded to _cache/legacy and the first raster inside is used")
    a = ap.parse_args(argv)
    out = (ROOT / a.out) if not a.out.is_absolute() else a.out; out.mkdir(parents=True, exist_ok=True)
    epoch = utc_epoch(a.timestamp_utc)
    gt = {"timestamp_utc": a.timestamp_utc, "bbox": a.bbox, "vertical_datum": "NAVD88", "created_utc": datetime.now(timezone.utc).isoformat()}
    if not a.skip_observations:
        dossier = observations(a, out / "frf_observations")
        gt["frf_dossier"] = str(dossier.relative_to(ROOT)) if dossier.is_relative_to(ROOT) else str(dossier)
        gt["observations"] = summarise_observations(dossier, epoch)
    budget = json.loads((ROOT / a.budget_config).read_text())
    tdir = ROOT / "_cache/frf_tranches" / (a.tranche + "_dem")
    tr = Transport(ROOT / a.cache, max_requests=budget["max_requests"], max_bytes=budget["max_bytes"],
                   max_response=budget["max_response"], tranche_directory=tdir, tranche_name=a.tranche + "_dem",
                   new_tranche=not (tdir / "NETWORK_STATE.json").exists())
    prod = frf_dem.nearest_survey_dem(tr, epoch, a.dem_max_days)
    survey = None
    if prod:
        survey = frf_dem.fetch_survey_dem(tr, prod)
        np.savez_compressed(out / "frf_survey_dem.npz", **{k: v for k, v in survey.items() if isinstance(v, np.ndarray)})
        gt["frf_survey_dem"] = {"product": prod["name"], "offset_days": prod["offset_days"], "survey_time_utc": survey["survey_time_utc"],
                                "source": survey["source"], "xFRF_range": [float(survey["xFRF"].min()), float(survey["xFRF"].max())],
                                "yFRF_range": [float(survey["yFRF"].min()), float(survey["yFRF"].max())]}
    else:
        gt["frf_survey_dem"] = {"status": f"none within {a.dem_max_days} days"}
    cud = coastal_dem.read_cudem(a.bbox, out / "cudem_bbox_navd88.tif", ROOT / "_cache/cudem")
    gt["cudem"] = cud or {"status": "no CUDEM tile for bbox"}
    blu = coastal_dem.read_bluetopo(a.bbox, out / "bluetopo_bbox.tif", ROOT / "_cache/bluetopo")
    gt["bluetopo"] = blu or {"status": "no BlueTopo tile for bbox"}
    wl = gt.get("observations", {}).get("water_level_navd88")
    eta, eta_status = water_level(wl, a.water_level_policy)
    gt["event_water_level"] = eta_status
    legacy = [coastal_dem.legacy_spec(x, ROOT / "_cache/legacy") for x in a.legacy_grid]
    gt["merged_bathymetry"] = merged_bathymetry(a.bbox, survey, a.grid_res, out / "bathymetry_merged_utm.tif", eta, legacy=legacy,
                                                bluetopo_tif=out / "bluetopo_bbox.tif" if blu else None, bluetopo_prov=blu,
                                                cudem_tif=out / "cudem_bbox_navd88.tif" if cud else None,
                                                frf_year=float(survey["survey_time_utc"][:4]) if survey else None)
    gt["merged_bathymetry"]["event_water_level_used_m"] = eta
    gt["merged_bathymetry"]["event_water_level_status"] = eta_status
    gt["notes"] = ["FRF eopNoaaTide water level is NOAA preliminary (not NOAA-QC'd); wave setup nearshore not included",
                   "CUDEM mixes survey years; FRF survey DEM interpolates between survey lines",
                   "AWAC currents are at 11 m depth; not the surface current seen by the SAR"]
    (out / "GROUND_TRUTH.json").write_text(json.dumps(gt, indent=2, default=float))
    figure(out / "bathymetry_merged_utm.tif", out / "bathymetry_merged.png")
    print(json.dumps({k: gt[k] for k in ("frf_survey_dem", "merged_bathymetry")}, indent=1, default=float))


if __name__ == "__main__":
    main()

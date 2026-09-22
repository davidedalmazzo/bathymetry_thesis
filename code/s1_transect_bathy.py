#!/usr/bin/env python
"""Scene-generic Sentinel-1 IW SLC swell-wavelength transects (and optional depth).

Inspired by Mudiyanselage et al. (2024, Remote Sens. 16, 1): square windows
every --step metres along cross-shore transects (heavy overlap), 2-D spectrum,
20 contour levels, blob above the top level, centroid of the largest blob
closest to the origin, moving mean along each transect, Eq. 5 depth.

Everything is derived from the scene and the bbox:
  1. multilooked sigma0 map on a local UTM grid (all subswaths/bursts in bbox);
  2. instantaneous land/sea mask from the SAR (Otsu + morphology), or --coast;
  3. coastline = sea-mask boundary, smoothed; transects = its seaward normals;
  4. windows on native SLC pixels, single burst, fully at sea, no bright targets;
  5. spectrum evaluated exactly from native samples (no image resampling).

Depth is computed only when a period is supplied (--period, e.g. from a buoy);
the period is never derived from charts or from the result (circularity).

Example:
  python s1_transect_bathy.py S1A_..._B6FA.SAFE --bbox -75.78 36.16 -75.70 36.22 \
         --out results_duck --period 11.76
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter1d

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s1_paper_peak as pp                                   # noqa: E402
from s1_iw_annotation import parse_annotation                # noqa: E402
from s1_iw_geometry import GrdGeometry, SwathGeometry, parse_grd_annotation, window_inside_single_burst  # noqa: E402
from s1_spatial_trial import invert_dispersion, parse_calibration_lut  # noqa: E402

G = 9.80665


# ------------------------------------------------------------------ scene I/O
class Swath:
    def __init__(self, safe: Path, ann_path: Path):
        stem = ann_path.stem
        self.grd = "-grd-" in stem
        if self.grd:
            self.ann = parse_grd_annotation(ann_path); self.geo = GrdGeometry(self.ann)
        else:
            self.ann = parse_annotation(ann_path.read_bytes(), expected_polarisation=None); self.geo = SwathGeometry(self.ann)
        self.name = self.ann["swath"]
        self.tiff = safe / "measurement" / f"{stem}.tiff"
        self.cal = parse_calibration_lut(safe / "annotation" / "calibration" / f"calibration-{stem}.xml")
        if not self.tiff.exists():
            raise FileNotFoundError(self.tiff)
        self.block = None

    def sigma0(self, dn, lines, samples):
        lut = self.cal["interpolator"](np.column_stack((np.ravel(lines), np.ravel(samples)))).reshape(np.shape(dn))
        return np.abs(dn.astype(np.complex128)) ** 2 / lut ** 2

    def read(self, s0, l0, s1, l1):
        import rasterio
        from rasterio.windows import Window
        s0 = max(0, s0); l0 = max(0, l0); s1 = min(self.ann["number_of_samples"], s1); l1 = min(self.ann["number_of_lines"], l1)
        with rasterio.open(self.tiff) as ds:
            dn = ds.read(1, window=Window(s0, l0, s1 - s0, l1 - l0))
        if not self.grd and not np.iscomplexobj(dn):
            raise ValueError("expected complex SLC")
        return dn, s0, l0

    def valid_mask(self, s0, l0, shape, dn=None):
        if self.grd:                                     # GRD borders are zero-filled
            return np.ones(shape, bool) if dn is None else dn > 0
        m = np.zeros(shape, bool)
        for i in range(shape[0]):
            line = l0 + i; b = line // self.ann["lines_per_burst"]
            if b >= len(self.ann["bursts"]):
                continue
            burst = self.ann["bursts"][b]; loc = line - b * self.ann["lines_per_burst"]
            f = burst["first_valid_sample"][loc]; g = burst["last_valid_sample"][loc]
            if f >= 0:
                a = max(f - s0, 0); z = min(g - s0 + 1, shape[1])
                if z > a:
                    m[i, a:z] = True
        return m


def open_swaths(safe: Path, pol: str):
    anns = sorted((safe / "annotation").glob(f"s1?-iw?-slc-{pol.lower()}-*.xml")) or \
        sorted((safe / "annotation").glob(f"s1?-iw-grd-{pol.lower()}-*.xml"))
    if not anns:
        raise SystemExit(f"no IW SLC/GRD {pol} annotations in {safe}")
    return [Swath(safe, a) for a in anns]


def utm_transformers(lon, lat):
    import pyproj
    zone = int((lon + 180) // 6) + 1
    epsg = (32600 if lat >= 0 else 32700) + zone
    fwd = pyproj.Transformer.from_crs(4326, epsg, always_xy=True)
    inv = pyproj.Transformer.from_crs(epsg, 4326, always_xy=True)
    return epsg, (lambda lo, la: fwd.transform(lo, la)), (lambda e, n: inv.transform(e, n))


def pixel_bounds(sw: Swath, bbox, margin_m=1500.0):
    """Line/sample bounds (per burst) of the bbox, expanded by a margin."""
    lon0, lat0, lon1, lat1 = bbox
    dlon = margin_m / (111320 * math.cos(math.radians((lat0 + lat1) / 2))); dlat = margin_m / 110574
    lo = np.linspace(lon0 - dlon, lon1 + dlon, 9); la = np.linspace(lat0 - dlat, lat1 + dlat, 9)
    LO, LA = np.meshgrid(lo, la)
    t, s = sw.geo.geo_to_time_sample(LO.ravel(), LA.ravel())
    ok = np.isfinite(t) & np.isfinite(s)
    if not np.any(ok):
        return None
    s0 = int(max(0, np.floor(s[ok].min()))); s1 = int(min(sw.ann["number_of_samples"], np.ceil(s[ok].max()) + 1))
    tmin, tmax = t[ok].min(), t[ok].max(); lines = []
    for b, tb in enumerate(sw.geo.burst_t):
        a = (tmin - tb) / sw.geo.ati; z = (tmax - tb) / sw.geo.ati
        a = max(a, 0); z = min(z, sw.geo.lpb - 1)
        if z > a:
            lines.append((b, int(b * sw.geo.lpb + np.floor(a)), int(b * sw.geo.lpb + np.ceil(z) + 1)))
    return (s0, s1, lines) if lines and s1 > s0 else None


# ------------------------------------------------------------------ land/sea
def build_sigma0_map(swaths, bbox, to_utm, to_geo, res):
    """Multilooked sigma0 on a UTM grid, sampled (not binned) from each burst:
    every grid cell is mapped back to (azimuth time, sample) and the multilooked
    image is interpolated there; burst-overlap duplicates are averaged."""
    from scipy.interpolate import RegularGridInterpolator
    lon0, lat0, lon1, lat1 = bbox
    xs, ys = to_utm(np.array([lon0, lon1, lon0, lon1]), np.array([lat0, lat0, lat1, lat1]))
    e0, e1 = np.floor(min(xs) / res) * res, np.ceil(max(xs) / res) * res
    n0, n1 = np.floor(min(ys) / res) * res, np.ceil(max(ys) / res) * res
    ne = int((e1 - e0) / res); nn = int((n1 - n0) / res)
    EE, NN = np.meshgrid(e0 + (np.arange(ne) + .5) * res, n0 + (np.arange(nn) + .5) * res)
    LO, LA = to_geo(EE.ravel(), NN.ravel()); LO = np.asarray(LO); LA = np.asarray(LA)
    acc = np.zeros(EE.size); cnt = np.zeros(EE.size); reads = []
    for sw in swaths:
        pb = pixel_bounds(sw, bbox)
        if pb is None:
            continue
        s0, s1, lines = pb
        l0 = min(a for _, a, _ in lines); l1 = max(z for _, _, z in lines)
        dn, s0, l0 = sw.read(s0, l0, s1, l1)
        Lb, Sb = np.mgrid[l0:l0 + dn.shape[0], s0:s0 + dn.shape[1]]
        sw.block = (s0, l0, sw.sigma0(dn, Lb, Sb))
        reads.append({"swath": sw.name, "s0_l0_s1_l1": [s0, l0, s0 + dn.shape[1], l0 + dn.shape[0]]})
        valid = sw.valid_mask(s0, l0, dn.shape, dn)
        sw.valid_block = valid
        gs, gl, _, _ = sw.geo.ground_spacing(s0 + dn.shape[1] / 2, l0 + dn.shape[0] / 2, to_utm)
        ms = max(1, int(round(res / gs))); ml = max(1, int(round(res / gl)))
        hs = dn.shape[1] // ms * ms; hl = dn.shape[0] // ml * ml
        sig = sw.block[2][:hl, :hs]; v = valid[:hl, :hs]
        blk = lambda a: a.reshape(hl // ml, ml, hs // ms, ms)
        with np.errstate(invalid="ignore"):
            mlk = blk(np.where(v, sig, 0)).sum(axis=(1, 3)) / blk(v).sum(axis=(1, 3))
        mlk[blk(v).sum(axis=(1, 3)) < ml * ms] = np.nan
        cl = l0 + (np.arange(hl // ml) + .5) * ml - .5; cs = s0 + (np.arange(hs // ms) + .5) * ms - .5
        interp = RegularGridInterpolator((cl, cs), mlk, bounds_error=False, fill_value=np.nan)
        t, smp = sw.geo.geo_to_time_sample(LO, LA)
        for b, tb in enumerate(sw.geo.burst_t):
            rel = (t - tb) / sw.geo.ati
            use = np.isfinite(rel) & (rel >= 0) & (rel < sw.geo.lpb)
            if not np.any(use):
                continue
            val = interp(np.column_stack((b * sw.geo.lpb + rel[use], smp[use])))
            ok = np.isfinite(val); idx = np.flatnonzero(use)[ok]
            acc[idx] += val[ok]; cnt[idx] += 1
    with np.errstate(invalid="ignore"):
        m = (acc / cnt).reshape(nn, ne)
    return {"sigma0": m, "count": cnt.reshape(nn, ne), "e0": e0, "n0": n0, "res": res, "reads": reads}


def otsu(values, bins=256):
    h, edges = np.histogram(values, bins=bins); c = (edges[:-1] + edges[1:]) / 2
    w = np.cumsum(h); mu = np.cumsum(h * c); wt = w[-1]; mt = mu[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        sb = (mt * w - mu * wt) ** 2 / (w * (wt - w))
    return float(c[np.nanargmax(sb)])


def sea_mask_from_sar(smap, sea_side="auto", min_hole_cells=20):
    """Instantaneous water/land split (Otsu on median-filtered dB), then the open
    sea is the water-class component touching the bbox side facing the sea.
    With --sea-side auto the side is the one where either class forms the longest
    uninterrupted edge run and the class is chosen by the larger edge-connected
    component (reported; check overview.png or pass --sea-side)."""
    s = smap["sigma0"]; have = np.isfinite(s)
    db = np.where(have, 10 * np.log10(np.maximum(s, 1e-8)), np.nan)
    fill = np.where(have, db, np.nanmedian(db))
    db = np.where(have, ndimage.median_filter(fill, 3), np.nan)
    thr = otsu(db[have]); info = {"otsu_threshold_db": thr}
    sides = {"S": (0, slice(None)), "N": (-1, slice(None)), "W": (slice(None), 0), "E": (slice(None), -1)}
    comps = []
    for cls, m in (("dark", have & (db < thr)), ("bright", have & (db >= thr))):
        m = ndimage.binary_opening(ndimage.binary_closing(m, iterations=2, border_value=1), iterations=2, border_value=1) & have
        lab, n = ndimage.label(m)
        for i in range(1, n + 1):
            c = lab == i
            edge = {k: int(c[v].sum()) for k, v in sides.items()}
            comps.append({"class": cls, "mask": c, "cells": int(c.sum()), "edge_cells": edge})
    if sea_side == "auto":
        big = max(comps, key=lambda c: c["cells"])
        sea = big; rule = "auto: largest single connected class component (verify overview.png, or pass --sea-side)"
    else:
        sea = max(comps, key=lambda c: (c["edge_cells"][sea_side], c["cells"]))
        rule = f"class component with the longest contact with bbox side {sea_side}"
    holes = ndimage.binary_fill_holes(sea["mask"]) & ~sea["mask"]
    lab, n = ndimage.label(holes)
    sizes = ndimage.sum(holes, lab, range(1, n + 1)) if n else []
    small = np.isin(lab, [i + 1 for i, z in enumerate(sizes) if z < min_hole_cells])
    top = sorted(comps, key=lambda c: -c["cells"])[:4]
    info.update(sea_class=sea["class"], rule=rule, sea_cells=sea["cells"], small_holes_filled=int(small.sum()),
                largest_components=[{k: v for k, v in c.items() if k != "mask"} for c in top])
    return sea["mask"] | small, info


def sea_mask_from_vector(path, smap, to_utm):
    """Vector land polygons (e.g. TanDEM-X coastline GPKG) or water polygons -> sea mask."""
    import shapely
    from shapely.geometry import shape, Point
    from shapely.ops import unary_union, transform
    text = Path(path).read_text() if str(path).lower().endswith((".json", ".geojson")) else None
    if text is None:
        import pyogrio  # optional dependency for GPKG/SHP
        gdf = pyogrio.read_dataframe(path)
        geoms = list(gdf.to_crs(4326).geometry)
    else:
        d = json.loads(text); feats = d["features"] if "features" in d else [d]
        geoms = [shape(f["geometry"]) for f in feats]
    land = transform(lambda x, y, z=None: to_utm(x, y), unary_union(geoms))
    nn, ne = smap["sigma0"].shape
    E = smap["e0"] + (np.arange(ne) + 0.5) * smap["res"]; N = smap["n0"] + (np.arange(nn) + 0.5) * smap["res"]
    EE, NN = np.meshgrid(E, N)
    inside = shapely.contains_xy(land, EE, NN)
    return ~inside & np.isfinite(smap["sigma0"]), {"rule": f"outside land polygons of {Path(path).name}"}


def coastline(sea, smap, smooth_m):
    import contourpy
    gen = contourpy.contour_generator(z=sea.astype(float))
    lines = gen.lines(0.5)
    # keep only the land-sea interface: drop vertices on/near the bbox border and split there
    nn, ne = sea.shape; segs = []
    for ln in lines:
        inner = (ln[:, 0] > 2) & (ln[:, 0] < ne - 3) & (ln[:, 1] > 2) & (ln[:, 1] < nn - 3)
        lab, n = ndimage.label(inner)
        segs += [ln[lab == i] for i in range(1, n + 1)]
    if not segs:
        raise SystemExit("no coastline found in bbox")
    best = max(segs, key=len)
    res = smap["res"]
    xy = np.column_stack((smap["e0"] + (best[:, 0] + 0.5) * res, smap["n0"] + (best[:, 1] + 0.5) * res))
    seg = np.hypot(*np.diff(xy, axis=0).T); d = np.concatenate(([0], np.cumsum(seg)))
    step = 25.0; u = np.arange(0, d[-1], step)
    xr = np.interp(u, d, xy[:, 0]); yr = np.interp(u, d, xy[:, 1])
    sig = max(smooth_m / step / 2, 1)
    return np.column_stack((gaussian_filter1d(xr, sig, mode="nearest"), gaussian_filter1d(yr, sig, mode="nearest"))), xy


def sea_at(sea, smap, E, N):
    i = np.floor((np.asarray(N) - smap["n0"]) / smap["res"]).astype(int)
    j = np.floor((np.asarray(E) - smap["e0"]) / smap["res"]).astype(int)
    ok = (i >= 0) & (i < sea.shape[0]) & (j >= 0) & (j < sea.shape[1])
    out = np.zeros(np.shape(i), bool); out[ok] = sea[i[ok], j[ok]]
    return out


def transects(coast, sea, smap, spacing, smooth_m, test_d):
    step = 25.0; out = []
    edge = int(math.ceil(smooth_m / step))
    idx = np.arange(edge, len(coast) - edge, max(1, int(round(spacing / step))))
    for k, i in enumerate(idx):
        t = coast[min(i + 1, len(coast) - 1)] - coast[max(i - 1, 0)]; t = t / np.linalg.norm(t)
        n = np.array([t[1], -t[0]])
        p = coast[i]
        if sea_at(sea, smap, *(p + test_d * n)) and not sea_at(sea, smap, *(p - test_d * n)):
            pass
        elif sea_at(sea, smap, *(p - test_d * n)) and not sea_at(sea, smap, *(p + test_d * n)):
            n = -n
        else:
            continue
        out.append({"id": len(out), "origin_E": float(p[0]), "origin_N": float(p[1]),
                    "normal_E": float(n[0]), "normal_N": float(n[1]),
                    "seaward_bearing_deg": math.degrees(math.atan2(n[0], n[1])) % 360})
    return out


# ------------------------------------------------------------------ spectra
def affine_fit(S, L, E, N):
    A = np.column_stack((np.ones(S.size), S.ravel(), L.ravel()))
    ce = np.linalg.lstsq(A, E.ravel(), rcond=None)[0]; cn = np.linalg.lstsq(A, N.ravel(), rcond=None)[0]
    res = np.hypot(A @ ce - E.ravel(), A @ cn - N.ravel())
    return np.array([[ce[1], ce[2]], [cn[1], cn[2]]]), float(res.max())


def dtft_affine(z, J, k):
    """|sum z exp(-i k.(J [s,l]))| for positions affine in (sample,line); exact for affine maps."""
    KE, KN = np.meshgrid(k, k)
    qs = KE * J[0, 0] + KN * J[1, 0]; ql = KE * J[0, 1] + KN * J[1, 1]
    ns = z.shape[1]; nl = z.shape[0]
    s = np.arange(ns) - (ns - 1) / 2; l = np.arange(nl) - (nl - 1) / 2
    Es = np.exp(-1j * np.outer(qs.ravel(), s)); El = np.exp(-1j * np.outer(ql.ravel(), l))
    F = np.sum(El * (Es @ z.T), axis=1)
    return np.abs(F).reshape(KE.shape)


def window_spectrum(sig, S, L, Es, Ns, args, lim, sw, to_utm, sub):
    """Es/Ns: UTM positions on the subsampled grid S[sub], L[sub].  If the map is
    affine to within --affine-tolerance the fast separable DTFT is exact; else the
    full per-pixel positions are computed and an exact NUDFT is used."""
    J, resid = affine_fit(S[sub] - S.mean(), L[sub] - L.mean(), Es - Es.mean(), Ns - Ns.mean())
    k, dk = pp.k_grid(args.window, args.padding, args.kmax)
    if resid <= args.affine_tolerance:
        # detrend in ground coordinates predicted by the affine map
        Ea = J[0, 0] * (S - S.mean()) + J[0, 1] * (L - L.mean()); Na = J[1, 0] * (S - S.mean()) + J[1, 1] * (L - L.mean())
        z = pp.plane_detrend(sig, Ea, Na) * pp.hann2(sig.shape)
        mag = dtft_affine(z, J, k); method = "affine_dtft"
    else:
        lo, la = sw.geo.forward(S, L); E, N = (np.asarray(v) for v in to_utm(lo, la))
        z = pp.plane_detrend(sig, E, N) * pp.hann2(sig.shape)
        mag = pp.nudft_magnitude(z, E - E.mean(), N - N.mean(), k, k); method = "exact_nudft"
    mask = pp.search_mask(k, k, 2 * 2 * np.pi / args.window, lim)
    return k, mag, mask, {"affine_residual_max_m": resid, "spectrum_method": method}


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("safe", type=Path)
    ap.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"))
    ap.add_argument("--out", type=Path, default=Path("s1_transects_out"))
    ap.add_argument("--pol", default="VV")
    ap.add_argument("--coast", type=Path, help="optional vector land polygons (GeoJSON/GPKG/SHP) instead of SAR mask")
    ap.add_argument("--sea-side", default="auto", choices=["auto", "N", "S", "E", "W"])
    ap.add_argument("--mask-res", type=float, default=50.0, help="land/sea map resolution (m)")
    ap.add_argument("--smooth", type=float, default=1000.0, help="coastline smoothing scale (m)")
    ap.add_argument("--transect-spacing", type=float, default=250.0)
    ap.add_argument("--step", type=float, default=50.0, help="window step along transect (paper: 50 m)")
    ap.add_argument("--offshore", nargs=2, type=float, default=[250.0, 3000.0], help="window-centre distance range from coastline (m)")
    ap.add_argument("--window", type=float, default=512.0, help="square window side (m); paper 1280 m for 150-300 m swell")
    ap.add_argument("--padding", type=int, default=1)
    ap.add_argument("--kmax", type=float, default=0.30)
    ap.add_argument("--levels", type=int, default=20)
    ap.add_argument("--scale", default="log10", choices=["log10", "linear"])
    ap.add_argument("--blob", default="contour", choices=["contour", "fastpeakfind"])
    ap.add_argument("--lobe-min", type=float, default=3.0)
    ap.add_argument("--moving-mean", type=int, default=5)
    ap.add_argument("--max-bright-fraction", type=float, default=0.002, help="fraction of pixels > 50x window median allowed")
    ap.add_argument("--affine-tolerance", type=float, default=1.0, help="max affine geolocation residual (m) for the fast DTFT; 1 m gives <= 2*pi/34 rad phase error at the shortest searched wavelength")
    ap.add_argument("--period", type=float, nargs="*", default=[], help="wave period(s) T (s) for Eq.5 depth; from in-situ data only")
    ap.add_argument("--current", type=float, nargs="*", default=[-0.5, 0.5], help="current along k (m/s) sensitivity")
    ap.add_argument("--alongshore-average", type=int, default=0,
                    help="average normalised spectra of N neighbouring transects on each side at the same distance "
                         "before peak picking (0 = paper, single window). Assumes alongshore-uniform wave field over "
                         "(2N+1) x transect spacing; single-look periodograms are chi2(2) and need averaging")
    ap.add_argument("--band", type=float, default=500.0, help="distance-band width (m) for the ensemble-averaged diagnostic spectrum")
    ap.add_argument("--save-spectra", action="store_true", help="write window_spectra.npz (spectra used for peak picking)")
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--geometry-only", action="store_true", help="stop after mask/coastline/transects (quick check)")
    ap.add_argument("--chunk", nargs=2, type=int, metavar=("I", "N"),
                    help="compute only the I-th of N contiguous transect groups and save a partial result "
                         "(for time-limited shells); finish with --finalize N")
    ap.add_argument("--finalize", type=int, metavar="N", help="merge N partial results and run peak picking/outputs")
    args = ap.parse_args(argv)
    t_start = time.time(); args.out.mkdir(parents=True, exist_ok=True)

    swaths = open_swaths(args.safe, args.pol)
    lonc = (args.bbox[0] + args.bbox[2]) / 2; latc = (args.bbox[1] + args.bbox[3]) / 2
    epsg, to_utm, to_geo = utm_transformers(lonc, latc)
    smap = build_sigma0_map(swaths, args.bbox, to_utm, to_geo, args.mask_res)
    if not smap["reads"]:
        raise SystemExit("bbox not covered by any subswath")
    if args.coast:
        sea, sea_info = sea_mask_from_vector(args.coast, smap, to_utm)
    else:
        sea, sea_info = sea_mask_from_sar(smap, args.sea_side)
    coast, coast_raw = coastline(sea, smap, args.smooth)
    trs = transects(coast, sea, smap, args.transect_spacing, args.smooth, test_d=max(300.0, args.offshore[0]))
    print(f"{len(trs)} transects; sea mask: {sea_info.get('rule')}", flush=True)
    if args.geometry_only:
        write_outputs(args, [], trs, coast, coast_raw, sea, smap, sea_info, epsg, to_geo, {}, time.time() - t_start)
        make_figures(args, [], trs, coast, sea, smap, [])
        return

    rows = []; examples = []; bands = {}; spectra = {}
    import pickle
    parts = args.out / "parts"
    if args.finalize:
        files = [parts / f"part_{i}_of_{args.finalize}.pkl" for i in range(args.finalize)]
        missing = [f.name for f in files if not f.exists()]
        if missing:
            raise SystemExit(f"missing partial results: {missing}")
        for f in files:
            pr, ps = pickle.loads(f.read_bytes()); rows += pr; spectra.update(ps)
        rows.sort(key=lambda r: (r["transect"], r["distance_m"]))
    todo = [] if args.finalize else (list(np.array_split(np.array(trs, dtype=object), args.chunk[1])[args.chunk[0]]) if args.chunk else trs)
    for tr in todo:
        o = np.array([tr["origin_E"], tr["origin_N"]]); n = np.array([tr["normal_E"], tr["normal_N"]])
        for d in np.arange(args.offshore[0], args.offshore[1] + 1e-6, args.step):
            c = o + d * n; lon, lat = to_geo(*c)
            row = {"transect": tr["id"], "distance_m": float(d), "E": float(c[0]), "N": float(c[1]), "lon": lon, "lat": lat}
            h = args.window / 2 * 1.45     # circumscribed radius of the square window
            ring = [c + h * np.array([math.cos(a), math.sin(a)]) for a in np.linspace(0, 2 * np.pi, 16, endpoint=False)]
            if not sea_at(sea, smap, *c) or not all(sea_at(sea, smap, *q) for q in ring):
                rows.append({**row, "status": "touches_land_or_unmapped"}); continue
            placed = None
            for sw in swaths:
                if sw.block is None:
                    continue
                for cand in sw.geo.candidates(lon, lat):
                    gs, gl, _, _ = sw.geo.ground_spacing(cand["sample"], cand["line"], to_utm)
                    ns = int(round(args.window / gs)); nl = int(round(args.window / gl))
                    s0 = int(round(cand["sample"] - ns / 2)); l0 = int(round(cand["line"] - nl / 2))
                    if window_inside_single_burst(sw.ann, cand["burst"], s0, l0, s0 + ns, l0 + nl):
                        placed = (sw, cand, s0, l0, ns, nl, gs, gl); break
                if placed:
                    break
            if not placed:
                rows.append({**row, "status": "no_single_burst_support"}); continue
            sw, cand, s0, l0, ns, nl, gs, gl = placed
            bs0, bl0, sblock = sw.block
            if s0 < bs0 or l0 < bl0 or s0 + ns > bs0 + sblock.shape[1] or l0 + nl > bl0 + sblock.shape[0]:
                rows.append({**row, "status": "outside_read_block"}); continue
            L, S = np.mgrid[l0:l0 + nl, s0:s0 + ns].astype(float)
            sub = (slice(None, None, 3), slice(None, None, 3))
            lo, la = sw.geo.forward(S[sub], L[sub]); E, N = to_utm(lo, la); E = np.asarray(E); N = np.asarray(N)
            row.update(swath=sw.name, burst=cand["burst"], sample=cand["sample"], line=cand["line"],
                       n_samples=ns, n_lines=nl, ground_spacing_sample_m=gs, ground_spacing_line_m=gl)
            for i, (a_, b_) in enumerate(((0, 0), (0, -1), (-1, -1), (-1, 0))):   # footprint corners (UTM)
                row[f"fp_E{i}"] = float(E[a_, b_]); row[f"fp_N{i}"] = float(N[a_, b_])
            if not np.all(sea_at(sea, smap, E, N)):
                rows.append({**row, "status": "touches_land_or_unmapped"}); continue
            sig = sblock[l0 - bl0:l0 - bl0 + nl, s0 - bs0:s0 - bs0 + ns]
            if not sw.valid_block[l0 - bl0:l0 - bl0 + nl, s0 - bs0:s0 - bs0 + ns].all():
                rows.append({**row, "status": "no_single_burst_support"}); continue
            bright = float(np.mean(sig > 50 * np.median(sig)))
            row["bright_fraction"] = bright
            if bright > args.max_bright_fraction:
                rows.append({**row, "status": "bright_targets"}); continue
            ls_, lg_ = sw.geo.ground_spacing(cand["sample"], cand["line"], to_utm)[2:]
            ua = np.asarray(lg_) / np.linalg.norm(lg_); ur = np.asarray(ls_) / np.linalg.norm(ls_)
            lim = [(ua[0], ua[1], 0.8 * np.pi / gl), (ur[0], ur[1], 0.8 * np.pi / gs)]
            k, mag, mask, sinfo = window_spectrum(sig, S, L, E, N, args, lim, sw, to_utm, sub)
            row.update(sinfo, status="ok", incidence_deg=float(sw.geo.incidence(cand["sample"], cand["line"])))
            rows.append(row)
            spectra[(tr["id"], float(d))] = (k, (mag / np.median(mag[mask])) ** 2, mask)
    if args.chunk:
        parts.mkdir(exist_ok=True)
        (parts / f"part_{args.chunk[0]}_of_{args.chunk[1]}.pkl").write_bytes(pickle.dumps((rows, spectra)))
        print(f"saved part {args.chunk[0]}/{args.chunk[1]}: {len(rows)} windows", flush=True)
        return
    saved = []
    # peak identification; optional alongshore ensemble of neighbouring transects at equal distance
    for row in rows:
        key = (row["transect"], row["distance_m"])
        if key not in spectra:
            continue
        k, P, mask = spectra[key]
        nb = [spectra[(t, key[1])] for t in range(key[0] - args.alongshore_average, key[0] + args.alongshore_average + 1)
              if (t, key[1]) in spectra and spectra[(t, key[1])][0].size == k.size]
        Pm = np.mean([x[1] for x in nb], axis=0); mag = np.sqrt(Pm)
        if args.save_spectra:
            saved.append((row["transect"], row["distance_m"], Pm.astype("float32"), mask, k))
        res = pp.paper_peak(mag, k, k, mask, n_levels=args.levels, scale=args.scale, blob_method=args.blob)
        am = pp.argmax_peak(mag, k, k, mask)
        row.update(n_spectra_averaged=len(nb), peak_status=res["status"], n_blobs=len(res["blobs_canonical"]),
                   argmax_wavelength_m=am["wavelength_m"],
                   argmax_axial_bearing_deg=math.degrees(math.atan2(am["kx"], am["ky"])) % 180)
        if "wavelength_m" in res:
            lobe = pp.lobe_to_annulus(mag, k, k, mask, res["kx"], res["ky"], 2 * np.pi / args.window)
            row.update(wavelength_m=res["wavelength_m"], k_rad_m=res["k_rad_m"],
                       axial_bearing_deg=math.degrees(math.atan2(res["kx"], res["ky"])) % 180,
                       blob_area_px=res["selected"]["area_px"], lobe_to_annulus=lobe,
                       identifiable=bool(res["status"] == "identified" and lobe >= args.lobe_min))
        else:
            row["identifiable"] = False
        b = int(key[1] // args.band) * args.band
        acc = bands.setdefault(b, {"k": k, "sum": np.zeros_like(P), "n": 0, "mask": mask})
        if acc["k"].size == k.size:
            acc["sum"] += P; acc["n"] += 1
        if len(examples) < 64:
            examples.append((row, k, mag, mask, res))
    # moving mean per transect
    for tr in trs:
        r = [x for x in rows if x["transect"] == tr["id"]]
        mm = pp.moving_mean([x.get("wavelength_m", np.nan) for x in r], [x.get("identifiable", False) for x in r],
                            args.moving_mean, max(2, args.moving_mean // 2 + 1))
        for x, v in zip(r, mm):
            x["wavelength_smoothed_m"] = float(v)
    # optional depth
    lam_max = np.nanmax([x.get("wavelength_smoothed_m", np.nan) for x in rows]) if rows else np.nan
    summary = {"tmin_eq6_s": pp.minimum_period(lam_max) if np.isfinite(lam_max) else None, "lambda_max_smoothed_m": lam_max}
    for T in args.period:
        for x in rows:
            lam = x.get("wavelength_smoothed_m", np.nan)
            if not np.isfinite(lam):
                continue
            x[f"depth_T{T:g}_m"] = pp.depth_from_wavelength_period(lam, T)
            for U in args.current:
                x[f"depth_T{T:g}_U{U:+g}_m"] = invert_dispersion(2 * np.pi / lam, 2 * np.pi / T, U)["depth_m"]
        summary[f"T{T:g}_not_below_tmin"] = bool(summary["tmin_eq6_s"] is None or T >= summary["tmin_eq6_s"])
    if args.save_spectra and saved:
        np.savez_compressed(args.out / "window_spectra.npz", transect=np.array([x[0] for x in saved]),
                            distance_m=np.array([x[1] for x in saved]), power=np.stack([x[2] for x in saved]),
                            mask=saved[0][3], k=saved[0][4], k_axes="k_E (columns), k_N (rows), rad/m; power normalised by window median")
    ens = []
    for b, acc in sorted(bands.items()):
        P = acc["sum"] / acc["n"]; k = acc["k"]; m = acc["mask"]
        res = pp.paper_peak(np.sqrt(P), k, k, m, n_levels=args.levels, scale=args.scale, blob_method=args.blob)
        am = pp.argmax_peak(np.sqrt(P), k, k, m)
        ens.append({"band_m": [b, b + args.band], "n_windows": acc["n"], "status": res["status"],
                    "wavelength_m": res.get("wavelength_m"), "axial_bearing_deg": (math.degrees(math.atan2(res["kx"], res["ky"])) % 180) if "kx" in res else None,
                    "argmax_wavelength_m": am["wavelength_m"], "argmax_axial_bearing_deg": math.degrees(math.atan2(am["kx"], am["ky"])) % 180,
                    "peak_to_median": float(P[m].max() / np.median(P[m]))})
        acc["res"] = res; acc["P"] = P
    summary["ensemble_by_distance_band"] = ens
    write_outputs(args, rows, trs, coast, coast_raw, sea, smap, sea_info, epsg, to_geo, summary, time.time() - t_start)
    if not args.no_figures and bands:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, axs = plt.subplots(1, len(bands), figsize=(4.2 * len(bands), 4.2), squeeze=False)
        for ax, (b, acc) in zip(axs[0], sorted(bands.items())):
            k = acc["k"]; P = np.where(acc["mask"], 10 * np.log10(acc["P"]), np.nan)
            ax.pcolormesh(k, k, P, shading="nearest", cmap="magma"); r = acc["res"]
            if "kx" in r:
                ax.plot([r["kx"], -r["kx"]], [r["ky"], -r["ky"]], "c+", ms=12, mew=2)
            ax.set(title=f"{b:.0f}-{b + args.band:.0f} m, n={acc['n']}\n{r['status']} λ={r.get('wavelength_m', float('nan')):.0f} m", xlabel="k_E", ylabel="k_N"); ax.set_aspect("equal")
        fig.tight_layout(); fig.savefig(args.out / "ensemble_spectra_by_distance.png", dpi=130); plt.close(fig)
    if not args.no_figures:
        make_figures(args, rows, trs, coast, sea, smap, examples)
    print(json.dumps({k: v for k, v in summary.items()}, default=float), flush=True)


def write_outputs(args, rows, trs, coast, coast_raw, sea, smap, sea_info, epsg, to_geo, summary, seconds):
    fields = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(args.out / "windows.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in r.items()})

    def line_feature(xy, props):
        lo, la = to_geo(xy[:, 0], xy[:, 1])
        return {"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": np.column_stack((lo, la)).tolist()}}
    feats = [line_feature(coast, {"kind": "coastline_smoothed"}), line_feature(coast_raw, {"kind": "coastline_raw"})]
    for t in trs:
        o = np.array([t["origin_E"], t["origin_N"]]); n = np.array([t["normal_E"], t["normal_N"]])
        feats.append(line_feature(np.vstack((o + args.offshore[0] * n, o + args.offshore[1] * n)), {"kind": "transect", **t}))
    for r in rows:
        if r.get("status") == "ok":
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                          "properties": {k: v for k, v in r.items() if isinstance(v, (int, float, str, bool)) and not (isinstance(v, float) and not np.isfinite(v))}})
    (args.out / "transects.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    try:
        import rasterio
        from rasterio.transform import from_origin
        tfm = from_origin(smap["e0"], smap["n0"] + smap["sigma0"].shape[0] * smap["res"], smap["res"], smap["res"])
        with rasterio.open(args.out / "sigma0_seamask_utm.tif", "w", driver="GTiff", height=sea.shape[0], width=sea.shape[1],
                           count=2, dtype="float32", crs=f"EPSG:{epsg}", transform=tfm, nodata=np.nan) as ds:
            ds.write(np.flipud(10 * np.log10(np.maximum(smap["sigma0"], 1e-8))).astype("float32"), 1)
            ds.write(np.flipud(sea.astype("float32")), 2)
    except Exception as exc:                                   # figure/GIS convenience only
        print("GeoTIFF not written:", exc)
    status = {}
    for r in rows:
        status[r["status"]] = status.get(r["status"], 0) + 1
    meta = {"args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}, "utm_epsg": epsg,
            "sea_mask": sea_info, "reads": smap["reads"], "n_transects": len(trs), "window_status": status,
            "identifiable_windows": sum(bool(r.get("identifiable")) for r in rows), "summary": summary,
            "runtime_s": seconds,
            "notes": ["overlapping windows are not independent samples",
                      "wavelength is SAR-only; depth requires an externally measured period",
                      "geolocation uses burst azimuth time (s1_iw_geometry)"]}
    (args.out / "run.json").write_text(json.dumps(meta, indent=2, default=lambda o: float(o) if isinstance(o, np.floating) else str(o)))


def make_figures(args, rows, trs, coast, sea, smap, examples):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    res = smap["res"]; ext = [smap["e0"], smap["e0"] + sea.shape[1] * res, smap["n0"], smap["n0"] + sea.shape[0] * res]
    db = 10 * np.log10(np.maximum(smap["sigma0"], 1e-8))
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(db, origin="lower", extent=ext, cmap="gray", vmin=np.nanpercentile(db, 2), vmax=np.nanpercentile(db, 98))
    ax.contour(np.linspace(ext[0], ext[1], sea.shape[1]), np.linspace(ext[2], ext[3], sea.shape[0]), sea.astype(float), [0.5], colors="cyan", linewidths=.6)
    ax.plot(coast[:, 0], coast[:, 1], "y-", lw=1.2, label="smoothed coastline")
    ok = [r for r in rows if r.get("identifiable")]
    if ok:
        sc = ax.scatter([r["E"] for r in ok], [r["N"] for r in ok], c=[r.get("wavelength_smoothed_m", np.nan) for r in ok], s=9, cmap="viridis")
        fig.colorbar(sc, ax=ax, label="smoothed wavelength (m)", shrink=.7)
    bad = [r for r in rows if not r.get("identifiable")]
    ax.scatter([r["E"] for r in bad], [r["N"] for r in bad], c="r", s=2, label="not identifiable / excluded")
    ax.set(xlabel="UTM E (m)", ylabel="UTM N (m)", title="sigma0 (dB), SAR sea mask, transect windows"); ax.set_aspect("equal"); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(args.out / "overview.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 5))
    for t in trs:
        r = [x for x in rows if x["transect"] == t["id"]]
        ax.plot([x["distance_m"] for x in r], [x.get("wavelength_smoothed_m", np.nan) for x in r], lw=1)
    ax.set(xlabel="distance from coastline (m)", ylabel="smoothed wavelength (m)", title="Wavelength along transects (one line per transect)")
    ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(args.out / "wavelength_profiles.png", dpi=150); plt.close(fig)
    pick = [e for e in examples if e[4].get("status") in ("identified", "ambiguous_multiple_blobs")][:3] or examples[:3]
    if pick:
        fig, axs = plt.subplots(1, len(pick), figsize=(5 * len(pick), 4.6))
        for ax, (row, k, mag, mask, resd) in zip(np.atleast_1d(axs), pick):
            s = np.log10(np.maximum(mag, 1e-30)); base = np.nanmin(s[mask])
            ax.pcolormesh(k, k, np.where(mask, s, np.nan), shading="nearest", cmap="viridis")
            ax.contour(k, k, np.where(mask, s, base), levels=resd["levels"], colors="k", linewidths=.3)
            ax.contour(k, k, np.where(mask, s, base), levels=[resd["threshold"]], colors="r", linewidths=1)
            if "kx" in resd:
                ax.plot([resd["kx"], -resd["kx"]], [resd["ky"], -resd["ky"]], "r+", ms=12, mew=2)
            ax.set(title=f"transect {row['transect']} d={row['distance_m']:.0f} m\n{resd['status']} λ={resd.get('wavelength_m', float('nan')):.1f} m",
                   xlabel="k_E (rad/m)", ylabel="k_N (rad/m)"); ax.set_aspect("equal")
        fig.tight_layout(); fig.savefig(args.out / "example_spectra.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Check the SAR-derived waterline against the z = const contour of the ground-truth DEM.

The transects of `s1_transect_bathy.py` start from the instantaneous SAR waterline
(Otsu land/sea split), so an error there shifts every window's distance-from-shore
by the same amount.  This compares it with the bed-elevation contour of the merged
ground truth (band 1, NAVD88) at one or more levels: the still-water datum (0 m) and
the event water level, if the tide is known, are the two natural choices -- on a
gently sloping beach a 0.2 m level difference already moves the waterline by metres.

    python code/coastline_check.py --run duck_frf/.../ext_near \
        --ground-truth outputs/ground_truth_s1a_20211028_ext20 --level 0 --level 0.235

Reported per level: signed cross-shore distance from each SAR waterline vertex to the
nearest DEM contour point (positive = SAR waterline seaward of the DEM contour),
median, NMAD, p10/p90, and the along-shore profile of the median.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def contour_points(Z, E, N, level):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    cs = ax.contour(E, N, Z, levels=[level])
    segs = [np.asarray(p) for c in getattr(cs, "allsegs", [[]]) for p in c]
    plt.close(fig)
    segs = [s for s in segs if len(s) > 2]
    return np.vstack(segs) if segs else np.empty((0, 2))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True, help="s1_transect_bathy output dir (transects.geojson)")
    ap.add_argument("--ground-truth", type=Path, required=True)
    ap.add_argument("--level", type=float, action="append", default=[], help="bed elevation contour level (m NAVD88); repeatable")
    ap.add_argument("--kind", default="coastline_raw", choices=("coastline_raw", "coastline_smoothed"))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    levels = a.level or [0.0]
    out = a.out or a.run / "coastline_check"
    out.mkdir(parents=True, exist_ok=True)

    import rasterio
    import pyproj
    ds = rasterio.open(a.ground_truth / "bathymetry_merged_utm.tif")
    Z = ds.read(1)
    nn, ne = Z.shape
    E = ds.transform.c + (np.arange(ne) + 0.5) * ds.transform.a
    N = ds.transform.f + (np.arange(nn) + 0.5) * ds.transform.e

    gj = json.loads((a.run / "transects.geojson").read_text())
    feat = next(f for f in gj["features"] if f["properties"].get("kind") == a.kind)
    lon, lat = np.array(feat["geometry"]["coordinates"]).T
    to_utm = pyproj.Transformer.from_crs(4326, ds.crs.to_epsg(), always_xy=True).transform
    X, Y = (np.asarray(v) for v in to_utm(lon, lat))

    rep = {"run": str(a.run), "ground_truth": str(a.ground_truth), "kind": a.kind,
           "dem_crs": ds.crs.to_string(), "n_sar_vertices": int(X.size), "levels": {}}
    sea_sign = None
    for lv in levels:
        C = contour_points(np.where(np.isfinite(Z), Z, np.nan), E, N, lv)
        if C.size == 0:
            rep["levels"][f"{lv:g}"] = {"status": "no contour at this level in the DEM"}
            continue
        # nearest contour point per SAR vertex (KD-tree if available, else chunked brute force)
        try:
            from scipy.spatial import cKDTree
            dist, j = cKDTree(C).query(np.c_[X, Y])
        except Exception:
            dist = np.empty(X.size); j = np.empty(X.size, int)
            for i0 in range(0, X.size, 2000):
                s = slice(i0, i0 + 2000)
                d2 = (X[s, None] - C[None, :, 0]) ** 2 + (Y[s, None] - C[None, :, 1]) ** 2
                j[s] = d2.argmin(1); dist[s] = np.sqrt(d2.min(1))
        if sea_sign is None:                       # seaward direction from the mean SAR->DEM offset sign per axis
            sea_sign = np.sign(np.median(X - C[j, 0]) or 1.0)
        signed = np.sign(X - C[j, 0]) * dist       # cross-shore axis is ~E-W at Duck
        med = float(np.median(signed))
        rep["levels"][f"{lv:g}"] = {
            "n_contour_points": int(len(C)),
            "signed_distance_m": {"median": med, "nmad": float(1.4826 * np.median(np.abs(signed - med))),
                                  "p10_p90": np.percentile(signed, [10, 90]).tolist(),
                                  "max_abs": float(np.max(np.abs(signed)))},
            "convention": "positive = SAR waterline east (seaward at Duck) of the DEM contour",
            "alongshore_profile": [{"N_m": float(np.median(Y[s])), "n": int(s.stop - s.start),
                                    "median_signed_m": float(np.median(signed[s]))}
                                   for s in (slice(i, min(i + 50, X.size)) for i in range(0, X.size, 50))],
        }
    (out / "coastline_check.json").write_text(json.dumps(rep, indent=2, default=float))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 8))
        ax.plot(X, Y, "k-", lw=1, label="SAR waterline")
        for lv in levels:
            C = contour_points(np.where(np.isfinite(Z), Z, np.nan), E, N, lv)
            if C.size:
                ax.plot(C[:, 0], C[:, 1], ".", ms=1, label=f"DEM z = {lv:g} m")
        ax.set(xlabel="E (m)", ylabel="N (m)"); ax.set_aspect("equal"); ax.legend(fontsize=8); ax.grid(alpha=.3)
        fig.tight_layout(); fig.savefig(out / "coastline_check.png", dpi=150); plt.close(fig)
    except Exception as exc:
        print("figure skipped:", exc)
    print(json.dumps({lv: {k: v for k, v in d.items() if k != "alongshore_profile"}
                      for lv, d in rep["levels"].items()}, indent=1, default=float))


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Duck-only comparison of s1_transect_bathy.py output with FRF data.

Reads windows.csv of the generic script, converts window centres to FRF x/y
(affine fit on the Block35 survey lon/lat <-> xFRF/yFRF pairs), attaches the
survey bed elevation (NAVD88) within --radius of each centre, and inverts the
SAR wavelength with FRF-measured periods (Block37 FRF_ASSOCIATION: WR17/AWAC
discrete peak and half-power band).  Bed elevation is not water depth: the event
water level eta is unknown here, so the implied eta = h_SAR + z_bed is reported.
"""
from __future__ import annotations

import argparse, csv, json, math, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
import s1_paper_peak as pp                                         # noqa: E402

B35 = ROOT / "duck_frf" / "Block35_s1_spatial_selection"
B37 = ROOT / "duck_frf" / "Block37_s1_iw_spatial_trial"
SURVEYS = ["20211004", "20211016", "20211024", "20211027"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("windows_csv", type=Path)
    ap.add_argument("--radius", type=float, default=100.0)
    ap.add_argument("--min-points", type=int, default=20)
    ap.add_argument("--survey", default="20211024", help="survey date used for elevations (27 Oct only covers yFRF<412)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    out = a.out or a.windows_csv.parent / "duck_frf_compare"
    out.mkdir(parents=True, exist_ok=True)
    pts = {s: json.loads((B35 / "surveys" / f"FRF_geomorphology_elevationTransects_survey_{s}.nc.json").read_text())["points"] for s in SURVEYS}
    allp = [q for s in SURVEYS for q in pts[s]]
    coef, fit = pp.fit_frf_geo_affine(np.array([q["xFRF"] for q in allp]), np.array([q["yFRF"] for q in allp]),
                                      np.array([q["lon"] for q in allp]), np.array([q["lat"] for q in allp]))
    sv = pts[a.survey]; sx = np.array([q["xFRF"] for q in sv]); sy = np.array([q["yFRF"] for q in sv]); sz = np.array([q["elevation"] for q in sv])
    frf = json.loads((B37 / "FRF_ASSOCIATION.json").read_text())["frf_references"]
    rows = [r for r in csv.DictReader(open(a.windows_csv)) if r["status"] == "ok" and r.get("identifiable") == "True"]
    res = []
    for r in rows:
        x, y = pp.geo_to_frf(coef, float(r["lon"]), float(r["lat"]))
        x = float(x); y = float(y)
        lam = float(r["wavelength_smoothed_m"]) if r.get("wavelength_smoothed_m") not in ("", None) else float("nan")
        o = {"transect": int(r["transect"]), "distance_m": float(r["distance_m"]), "xFRF": x, "yFRF": y,
             "wavelength_m": float(r["wavelength_m"]), "wavelength_smoothed_m": lam, "axial_bearing_deg": float(r["axial_bearing_deg"])}
        d = np.hypot(sx - x, sy - y) <= a.radius
        near_pier = abs(y - 515) < 150 and x < 700
        o["near_pier"] = near_pier
        if d.sum() >= a.min_points:
            p5, p50, p95 = np.percentile(sz[d], [5, 50, 95])
            o.update(survey_points=int(d.sum()), z_p5=p5, z_p50=p50, z_p95=p95)
        for ref in frf:
            tag = "wr17" if "17" in ref["instrument_id"] else "awac"
            T = ref["discrete_peak_period_s"]; f0, f1 = ref["half_power_frequency_hz"]
            o[f"h_{tag}"] = pp.depth_from_wavelength_period(lam, T) if np.isfinite(lam) else float("nan")
            o[f"h_{tag}_lo"] = pp.depth_from_wavelength_period(lam, 1 / f1) if np.isfinite(lam) else float("nan")
            o[f"h_{tag}_hi"] = pp.depth_from_wavelength_period(lam, 1 / f0) if np.isfinite(lam) else float("nan")
            if "z_p50" in o:
                o[f"implied_eta_{tag}"] = o[f"h_{tag}"] + o["z_p50"]
        res.append(o)
    with open(out / "comparison.csv", "w", newline="") as f:
        keys = sorted({k for o in res for k in o}, key=lambda k: list(res[0]).index(k) if k in res[0] else 99)
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(res)
    cmp = [o for o in res if "z_p50" in o and not o["near_pier"]]
    summ = {"frf_affine_fit": fit, "survey": a.survey, "n_windows_with_survey": len(cmp), "note":
            "overlapping windows are not independent; eta (event water level, NAVD88) unknown; bed elevation != depth",
            "frf_axial_propagation_deg": [ (r["propagation_toward_deg"] % 180) for r in frf]}
    for tag in ("wr17", "awac"):
        e = np.array([o[f"implied_eta_{tag}"] for o in cmp]); e = e[np.isfinite(e)]
        if e.size:
            h = np.array([o[f"h_{tag}"] for o in cmp]); z = np.array([-o["z_p50"] for o in cmp]); ok = np.isfinite(h)
            summ[tag] = {"implied_eta_median_m": float(np.median(e)), "implied_eta_p10_p90_m": np.percentile(e, [10, 90]).tolist(),
                         "rmse_h_vs_minus_z_m": float(np.sqrt(np.mean((h[ok] - z[ok]) ** 2))),
                         "shape_rmse_after_median_offset_m": float(np.sqrt(np.mean((h[ok] - z[ok] - np.median(h[ok] - z[ok])) ** 2))),
                         "r_h_vs_depth": float(np.corrcoef(h[ok], z[ok])[0, 1]) if ok.sum() > 2 else None,
                         "depth_range_m": [float(z.min()), float(z.max())]}
    (out / "summary.json").write_text(json.dumps(summ, indent=2, default=float))
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 6))
        for tag, c in (("wr17", "tab:blue"), ("awac", "tab:orange")):
            ax.scatter([-o["z_p50"] for o in cmp], [o[f"h_{tag}"] for o in cmp], s=10, c=c, label=f"SAR h, T {tag}")
        lim = [0, max(15, max([-o["z_p50"] for o in cmp] + [0]) + 2)]
        ax.plot(lim, lim, "k-", lw=.8, label="1:1 (eta=0)")
        ax.set(xlabel="−bed elevation NAVD88 (m), survey median in radius", ylabel="SAR conditional depth (m)", xlim=lim, ylim=lim,
               title="Duck: SAR depth vs survey (event water level not applied)")
        ax.legend(); ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(out / "scatter.png", dpi=150); plt.close(fig)
    except Exception as exc:
        print("figure skipped:", exc)
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Combine forward_lambda_check runs made with different reference gauges.

Each certified SAR window is compared with the prediction propagated from the
gauge whose depth is closest to the window's mean event depth (the frequency
spectrum changes across the shelf: refraction, shoaling, local wind sea, so a
nearshore gauge is not representative offshore and vice versa).  Gauge depths are
given on the command line (nominal/measured, m).  Output: combined CSV, summary
by depth bin, figure lambda_SAR vs lambda_pred and relative error vs depth.

  python code/forward_lambda_combine.py --out DIR \
     --run near:duck_frf/.../ext_near --run far:duck_frf/.../ext_far \
     --gauge 8m-array=8 --gauge awac-11m=11.9 --gauge waverider-17m=18 --gauge waverider-26m=26
"""
from __future__ import annotations
import argparse, csv, json, math
from pathlib import Path
import numpy as np


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="append", required=True, help="LABEL:DIR of an s1_transect_bathy run with forward_<gauge>/ subfolders")
    ap.add_argument("--gauge", action="append", required=True, help="NAME=DEPTH_M (NAME as in forward_<NAME>)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--prefer", default=None, help="run label preferred where runs overlap in depth (e.g. far for >19 m)")
    ap.add_argument("--prefer-min-depth", type=float, default=np.inf)
    a = ap.parse_args(argv); a.out.mkdir(parents=True, exist_ok=True)
    gauges = {g.split("=")[0]: float(g.split("=")[1]) for g in a.gauge}
    rows = []
    for spec in a.run:
        label, d = spec.split(":", 1); d = Path(d)
        per = {}
        for name in gauges:
            f = d / f"forward_{name}" / "forward_windows.csv"
            if not f.exists():
                continue
            for r in csv.DictReader(open(f)):
                if r["certified"] != "True":
                    continue
                per.setdefault((r["transect"], r["distance_m"]), {})[name] = r
        for key, by in per.items():
            any_r = next(iter(by.values())); h = float(any_r["depth_mean_m"])
            name = min((n for n in by), key=lambda n: abs(gauges[n] - h)); r = by[name]
            lam_sar = 2 * math.pi / float(r["sar_centroid_k"]) if r["sar_centroid_k"] not in ("", "nan") else np.nan
            lam_pap = float(r["sar_paper_wavelength_m"]) if r["sar_paper_wavelength_m"] not in ("", "nan") else np.nan
            lam_pred = 2 * math.pi / float(r["pred_Ek_centroid_k"])
            rows.append({"run": label, "transect": key[0], "distance_m": float(key[1]), "E": float(r["E"]), "N": float(r["N"]),
                         "depth_mean_m": h, "reference_gauge": name, "gauge_depth_m": gauges[name],
                         "lambda_sar_radial_m": lam_sar, "lambda_sar_paper_m": lam_pap,
                         "sar_paper_identifiable": r["sar_identifiable"] == "True", "lambda_pred_m": lam_pred,
                         "rel_err_radial": lam_sar / lam_pred - 1, "rel_err_paper": lam_pap / lam_pred - 1,
                         "uncertainty_max_m": float(r["uncertainty_max_m"]), "legacy_fraction": float(r.get("legacy_fraction") or 0)})
    if a.prefer:
        rows = [r for r in rows if not (r["depth_mean_m"] >= a.prefer_min_depth and r["run"] != a.prefer)
                and not (r["depth_mean_m"] < a.prefer_min_depth and r["run"] == a.prefer)]
    with open(a.out / "combined_windows.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    d = np.array([r["depth_mean_m"] for r in rows]); er = np.array([r["rel_err_radial"] for r in rows])
    ep = np.array([r["rel_err_paper"] if r["sar_paper_identifiable"] else np.nan for r in rows])
    summ = {"gauges_m": gauges, "n_windows": len(rows), "depth_range_m": [float(d.min()), float(d.max())],
            "radial_centroid": {"median": float(np.nanmedian(er)), "p10_p90": np.nanpercentile(er, [10, 90]).tolist(),
                                "robust_scatter_nmad": float(1.4826 * np.nanmedian(np.abs(er - np.nanmedian(er))))},
            "paper_peak": {"n": int(np.isfinite(ep).sum()), "median": float(np.nanmedian(ep)), "p10_p90": np.nanpercentile(ep, [10, 90]).tolist(),
                           "robust_scatter_nmad": float(1.4826 * np.nanmedian(np.abs(ep - np.nanmedian(ep))))},
            "note": "overlapping windows (50-100 m steps, alongshore averaging) are strongly correlated; bins are not independent samples",
            "by_depth_bin": []}
    for lo in np.arange(np.floor(d.min()), np.ceil(d.max()), 1.0):
        m = (d >= lo) & (d < lo + 1)
        if m.sum() < 10:
            continue
        sel = [r for r, k in zip(rows, m) if k]
        summ["by_depth_bin"].append({"depth_m": [float(lo), float(lo + 1)], "n": int(m.sum()),
            "gauges": sorted({r["reference_gauge"] for r in sel}),
            "lambda_pred_median_m": float(np.median([r["lambda_pred_m"] for r in sel])),
            "lambda_sar_radial_median_m": float(np.nanmedian([r["lambda_sar_radial_m"] for r in sel])),
            "lambda_sar_paper_median_m": float(np.nanmedian([r["lambda_sar_paper_m"] for r in sel if r["sar_paper_identifiable"]] or [np.nan])),
            "rel_err_radial_median": float(np.nanmedian(er[m])), "rel_err_radial_p10_p90": np.nanpercentile(er[m], [10, 90]).tolist()})
    (a.out / "combined_summary.json").write_text(json.dumps(summ, indent=2, default=float))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.5))
    b = summ["by_depth_bin"]; hc = [x["depth_m"][0] + .5 for x in b]
    ax[0].scatter(d, [r["lambda_sar_radial_m"] for r in rows], s=3, c="0.75", label="SAR windows (radial centroid)")
    ax[0].plot(hc, [x["lambda_sar_radial_median_m"] for x in b], "k-o", ms=3, label="SAR median per 1 m bin")
    ax[0].plot(hc, [x["lambda_sar_paper_median_m"] for x in b], "b--", lw=1, label="SAR paper contour peak, median")
    ax[0].plot(hc, [x["lambda_pred_median_m"] for x in b], "r-s", ms=3, label="predicted from nearest-depth gauge E(f)")
    ax[0].set(xlabel="mean event depth in window (m)", ylabel="wavelength (m)", ylim=(50, 260)); ax[0].grid(alpha=.3); ax[0].legend(fontsize=8)
    ax[1].axhline(0, c="k", lw=.8)
    ax[1].fill_between(hc, [100 * x["rel_err_radial_p10_p90"][0] for x in b], [100 * x["rel_err_radial_p10_p90"][1] for x in b], color="0.85", label="p10–p90")
    ax[1].plot(hc, [100 * x["rel_err_radial_median"] for x in b], "k-o", ms=3, label="median")
    ax[1].set(xlabel="mean event depth in window (m)", ylabel="λ_SAR / λ_pred − 1 (%)", ylim=(-50, 50)); ax[1].grid(alpha=.3); ax[1].legend(fontsize=8)
    for g_, h_ in gauges.items():
        ax[1].axvline(h_, c="tab:orange", lw=.6, ls=":"); ax[1].text(h_, 45, g_, fontsize=6, rotation=90, va="top")
    fig.suptitle("Duck 2021-10-28 S1A IW3: forward check on certified bathymetry (empirical unc ≤ 0.5 m)")
    fig.tight_layout(); fig.savefig(a.out / "forward_combined.png", dpi=150); plt.close(fig)
    print(json.dumps({k: v for k, v in summ.items() if k != "by_depth_bin"}, indent=1, default=float))
    for x in b:
        print(x["depth_m"], x["n"], x["gauges"], round(x["lambda_pred_median_m"]), round(x["lambda_sar_radial_median_m"]),
              f"{100 * x['rel_err_radial_median']:+.1f}%")


if __name__ == "__main__":
    main()

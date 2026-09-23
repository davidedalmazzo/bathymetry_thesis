#!/usr/bin/env python
"""Block40 step 6 - the eight required figures."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "code"))

CLS_SHORT = {0: "none", 1: "FRF 2021", 2: "BT direct 19-20 ok", 3: "BT direct 19-20 unc.",
             4: "H12859 2016", 5: "BT direct other", 6: "interp/pre-2010", 7: "legacy corrected", 8: "CUDEM"}


def f1_source_map(out, fig_dir):
    import rasterio
    ds = rasterio.open(out / "BLOCK40_SOURCE_MASK.tif")
    cls = ds.read(1); year = ds.read(3); adm = ds.read(7)
    ext = [ds.bounds.left, ds.bounds.right, ds.bounds.bottom, ds.bounds.top]
    fig, ax = plt.subplots(1, 3, figsize=(15, 6))
    cmap = plt.get_cmap("tab10", 9)
    im = ax[0].imshow(cls, extent=ext, origin="upper", cmap=cmap, vmin=-0.5, vmax=8.5, interpolation="nearest")
    cb = fig.colorbar(im, ax=ax[0], ticks=range(9)); cb.ax.set_yticklabels([CLS_SHORT[i] for i in range(9)], fontsize=7)
    ax[0].set_title("source class")
    im = ax[1].imshow(np.where(np.isfinite(year), year, np.nan), extent=ext, origin="upper", cmap="viridis")
    fig.colorbar(im, ax=ax[1], label="survey start year"); ax[1].set_title("survey year")
    ax[2].imshow(adm, extent=ext, origin="upper", cmap="Greys_r", vmin=0, vmax=1, interpolation="nearest")
    ax[2].set_title("primary admissible for its own depth band")
    for x in ax:
        x.set_xlabel("E (m)"); x.set_ylabel("N (m)")
    fig.suptitle("Block40 fig.1 - ground-truth provenance and primary mask (Duck, 2021-10-28)")
    fig.tight_layout(); fig.savefig(fig_dir / "fig1_source_provenance_map.png", dpi=140); plt.close(fig)


def f2_coverage(prov, fig_dir):
    bands = ["A_0_12m", "B_12_20m", "C_20_30m"]
    fig, ax = plt.subplots(1, 2, figsize=(14, 5.5))
    runs = ["slc_near", "slc_far", "grd_near", "grd_far"]
    w = 0.2
    classes = ["primary_admissible", "mixed_source", "direct_but_uncertain", "temporally_inadmissible",
               "legacy_calibrated", "interpolated"]
    for i, k in enumerate(classes):
        ax[0].bar(np.arange(len(runs)) + (i - 2.5) * w / 2, [sum(1 for r in prov if r["run"] == u and r["window_class"] == k)
                                                             for u in runs], width=w / 2, label=k)
    ax[0].set_xticks(range(len(runs))); ax[0].set_xticklabels(runs); ax[0].set_yscale("log")
    ax[0].set_ylabel("windows"); ax[0].legend(fontsize=7); ax[0].set_title("window classes per run (log scale)")
    for i, u in enumerate(runs):
        vals = [sum(1 for r in prov if r["run"] == u and r["window_class"] == "primary_admissible" and r["band_name"] == b)
                for b in bands]
        ax[1].bar(np.arange(3) + (i - 1.5) * 0.2, vals, width=0.2, label=u)
        for j, v in enumerate(vals):
            ax[1].text(j + (i - 1.5) * 0.2, v + 3, str(v), ha="center", fontsize=7)
    ax[1].set_xticks(range(3)); ax[1].set_xticklabels(bands); ax[1].set_ylabel("primary-admissible windows")
    ax[1].legend(fontsize=7); ax[1].set_title("primary coverage by depth band (90 % rule)")
    fig.suptitle("Block40 fig.2 - admissible window coverage")
    fig.tight_layout(); fig.savefig(fig_dir / "fig2_admissible_coverage.png", dpi=140); plt.close(fig)


def f3_error_by_depth_and_source(rows, fig_dir):
    fig, ax = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
    for i, prod in enumerate(("slc", "grd")):
        for klass, col in (("primary_admissible", "tab:green"), ("legacy_calibrated", "tab:orange"),
                           ("temporally_inadmissible", "tab:red"), ("mixed_source", "0.6")):
            sel = [r for r in rows if r["product"] == prod and r["window_class"] == klass
                   and np.isfinite(r["rel_err_contour"])]
            if len(sel) < 10:
                continue
            d = np.array([r["depth_mean_m"] for r in sel]); e = np.array([r["rel_err_contour"] for r in sel])
            hb, xb = [], []
            for lo in np.arange(6, 30, 2):
                m = (d >= lo) & (d < lo + 2)
                if m.sum() >= 10:
                    hb.append(100 * np.median(e[m])); xb.append(lo + 1)
            ax[i].plot(xb, hb, "-o", ms=4, color=col, label=f"{klass} (n={len(sel)})")
        ax[i].axhline(0, c="k", lw=.8); ax[i].grid(alpha=.3)
        ax[i].set(xlabel="mean still-water depth (m)", title=prod.upper())
        ax[i].legend(fontsize=7)
    ax[0].set_ylabel("median $\\lambda_{SAR}/\\lambda_{pred}-1$ (%)"); ax[0].set_ylim(-40, 30)
    fig.suptitle("Block40 fig.3 - wavelength error by depth and bathymetric source class")
    fig.tight_layout(); fig.savefig(fig_dir / "fig3_error_by_depth_and_source.png", dpi=140); plt.close(fig)


def f4_ladder(ladder_summary, fig_dir):
    v = ladder_summary["variants"]
    order = ["slc_single_look", "slc_incoherent_N2", "slc_incoherent_N4", "slc_multitaper_K4", "grd_esa"]
    med = [100 * v[k]["median"] for k in order]
    lo = [100 * (v[k]["median"] - v[k].get("median_ci95_block_bootstrap", [v[k]["median"]] * 2)[0]) for k in order]
    hi = [100 * (v[k].get("median_ci95_block_bootstrap", [v[k]["median"]] * 2)[1] - v[k]["median"]) for k in order]
    fig, ax = plt.subplots(1, 3, figsize=(15, 5))
    ax[0].errorbar(range(len(order)), med, yerr=[lo, hi], fmt="o-", capsize=4)
    ax[0].axhline(0, c="k", lw=.8); ax[0].set_xticks(range(len(order)))
    ax[0].set_xticklabels(order, rotation=20, ha="right", fontsize=8)
    ax[0].set_ylabel("median error (%)"); ax[0].grid(alpha=.3); ax[0].set_title("median with block-bootstrap CI")
    tail = [100 * v[k].get("short_wavelength_tail_fraction", np.nan) for k in order]
    ax[1].bar(range(len(order)), tail, color="tab:red", alpha=.7)
    ax[1].set_xticks(range(len(order))); ax[1].set_xticklabels(order, rotation=20, ha="right", fontsize=8)
    ax[1].set_ylabel("fraction with error < -25 % (%)"); ax[1].grid(alpha=.3); ax[1].set_title("short-wavelength tail")
    sl = [k for k in order if k != "grd_esa"]
    enl = [v[k]["enl_annulus_median"] for k in sl]; wid = [1000 * v[k]["lobe_halfpower_width_median_rad_m"] for k in sl]
    ax2 = ax[2].twinx()
    ax[2].plot(range(len(sl)), enl, "s-", color="tab:blue", label="ENL diagnostic")
    ax2.plot(range(len(sl)), wid, "^--", color="tab:brown", label="lobe half-power width")
    ax[2].set_xticks(range(len(sl))); ax[2].set_xticklabels(sl, rotation=20, ha="right", fontsize=8)
    ax[2].set_ylabel("ENL (annulus diagnostic)", color="tab:blue")
    ax2.set_ylabel("half-power width ($10^{-3}$ rad/m)", color="tab:brown")
    ax[2].set_title("variance reduction vs resolution loss"); ax[2].grid(alpha=.3)
    fig.suptitle("Block40 fig.4 - SLC spatial variance-reduction ladder (no temporal sub-apertures)")
    fig.tight_layout(); fig.savefig(fig_dir / "fig4_variance_ladder.png", dpi=140); plt.close(fig)


def f5_tails(ladder, rows, fig_dir):
    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    bins = np.linspace(-1, 0.8, 60)
    for v in ("slc_single_look", "slc_incoherent_N4", "slc_multitaper_K4"):
        e = [r["rel_err"] for r in ladder if r["variant"] == v and np.isfinite(r.get("rel_err", np.nan))]
        ax[0].hist(e, bins=bins, histtype="step", lw=1.5, label=f"{v} (n={len(e)})", density=True)
    e = [r["paired_grd_rel_err"] for r in ladder if r["variant"] == "slc_single_look"
         and np.isfinite(r.get("paired_grd_rel_err", np.nan))]
    ax[0].hist(e, bins=bins, histtype="step", lw=1.5, color="k", label=f"grd_esa (n={len(e)})", density=True)
    ax[0].axvline(-0.25, c="r", ls=":", lw=1); ax[0].set(xlabel="$\\lambda_{SAR}/\\lambda_{pred}-1$", ylabel="density")
    ax[0].legend(fontsize=7); ax[0].grid(alpha=.3); ax[0].set_title("error distribution, primary-admissible windows")
    for prod, col in (("slc", "tab:blue"), ("grd", "tab:green")):
        sel = [r for r in rows if r["product"] == prod and np.isfinite(r["rel_err_contour"])]
        lam = np.array([r["lambda_contour_m"] for r in sel]); e = np.array([r["rel_err_contour"] for r in sel])
        ax[1].scatter(lam, 100 * e, s=4, alpha=.3, color=col, label=f"{prod} (n={len(sel)})")
    ax[1].axhline(-25, c="r", ls=":", lw=1); ax[1].axhline(0, c="k", lw=.8)
    ax[1].set(xlabel="$\\lambda_{SAR}$ (m)", ylabel="error (%)", ylim=(-100, 60))
    ax[1].legend(fontsize=7); ax[1].grid(alpha=.3); ax[1].set_title("short peaks drive the negative tail")
    fig.suptitle("Block40 fig.5 - tails and spurious short-wavelength peaks")
    fig.tight_layout(); fig.savefig(fig_dir / "fig5_tails_short_peaks.png", dpi=140); plt.close(fig)


def f6_example_spectra(out, fig_dir, safe, ladder):
    """One window where the single-look peak is spurious and the multitaper recovers the
    physical lobe, and one where both agree."""
    import s1_paper_peak as pp
    import s1_transect_bathy as tb
    import block40_variance_ladder as bl
    single = {(r["run"], r["transect"], r["distance_m"]): r for r in ladder if r["variant"] == "slc_single_look"}
    multi = {(r["run"], r["transect"], r["distance_m"]): r for r in ladder if r["variant"] == "slc_multitaper_K4"}
    cand = []
    for k, s in single.items():
        m = multi.get(k)
        if not m or not np.isfinite(s.get("rel_err", np.nan)) or not np.isfinite(m.get("rel_err", np.nan)):
            continue
        cand.append((s["rel_err"], m["rel_err"], k))
    # spurious: the single-look peak is far too short while the multitaper recovers the lobe
    far = [c for c in cand if c[2][0] == "slc_far"]
    rec = [c for c in far if c[0] < -0.4 and abs(c[1]) < 0.10] or [c for c in far if c[0] < -0.4]
    bad = min(rec, key=lambda c: c[0] - c[1]) if rec else min(cand, key=lambda c: c[0] - c[1])
    stable = [c for c in far if abs(c[0]) < 0.05 and abs(c[1]) < 0.05] or far or cand
    good = min(stable, key=lambda c: abs(c[0]) + abs(c[1]))
    runs = {"slc_near": ("duck_frf/Block39_s1_paper_confirm/slc/near_k4", 512.0),
            "slc_far": ("duck_frf/Block39_s1_paper_confirm/slc/far_k4", 1024.0)}
    swaths = {s.name: s for s in tb.open_swaths(ROOT / safe, "VV")}
    epsg, to_utm, to_geo = tb.utm_transformers(-75.675, 36.205)
    fig, axs = plt.subplots(2, 2, figsize=(11, 10))
    for row, (tag, sel) in enumerate((("spurious single-look", bad), ("stable window", good))):
        _, _, key = sel
        rundir, win = runs[key[0]]
        rec = next(r for r in csv.DictReader(open(ROOT / rundir / "windows.csv"))
                   if int(r["transect"]) == key[1] and float(r["distance_m"]) == key[2])
        sw = swaths[rec["swath"]]
        ns = int(rec["n_samples"]); nl = int(rec["n_lines"])
        s0 = int(round(float(rec["sample"]) - ns / 2)); l0 = int(round(float(rec["line"]) - nl / 2))
        dn, rs0, rl0 = sw.read(s0, l0, s0 + ns, l0 + nl)
        L, S = np.mgrid[l0:l0 + nl, s0:s0 + ns].astype(float)
        sig = sw.sigma0(dn, L, S)
        sub = (slice(None, None, 3), slice(None, None, 3))
        lo, la = sw.geo.forward(S[sub], L[sub]); E, N = (np.asarray(v) for v in to_utm(lo, la))
        J, _ = tb.affine_fit(S[sub] - S.mean(), L[sub] - L.mean(), E - E.mean(), N - N.mean())
        kmax = float(next(r for r in ladder if (r["run"], r["transect"], r["distance_m"]) == key).get("kmax_rad_m") or 0.30)
        k, _ = pp.k_grid(win, 1, kmax)
        KE, KN = np.meshgrid(k, k)
        mask = np.hypot(KE, KN) > 2 * np.pi / win
        for col, v in enumerate(("slc_single_look", "slc_multitaper_K4")):
            P, _ = bl.variant_spectra(sig, S, L, J, k, v)
            d = bl.diagnostics(P, k, mask, 4 * np.pi / win)
            ax = axs[row, col]
            ax.pcolormesh(k, k, np.where(mask, 10 * np.log10(P / np.nanmedian(P[mask])), np.nan),
                          shading="nearest", cmap="magma")
            if "k_rad_m" in d:
                th = math.radians(d["axial_bearing_deg"])
                kx = d["k_rad_m"] * math.sin(th); ky = d["k_rad_m"] * math.cos(th)
                ax.plot([kx, -kx], [ky, -ky], "c+", ms=12, mew=2)
            ax.add_patch(plt.Circle((0, 0), 4 * np.pi / win, fill=False, color="w", ls=":", lw=1))
            ax.set_aspect("equal"); ax.set(xlabel="$k_E$ (rad/m)", ylabel="$k_N$ (rad/m)")
            ax.set_title(f"{tag}\n{v}: $\\lambda$={d.get('wavelength_m', float('nan')):.0f} m, "
                         f"ENL={d.get('enl_annulus', float('nan')):.2f}", fontsize=9)
    fig.suptitle("Block40 fig.6 - example spectra (transect/distance frozen from the ladder)")
    fig.tight_layout(); fig.savefig(fig_dir / "fig6_example_spectra.png", dpi=140); plt.close(fig)


def f7_sensitivity(budget, fig_dir):
    t = budget["terms"]
    labels, vals = [], []
    for k, v in t.items():
        if k.startswith("water_level_"):
            labels.append("eta " + k.split("eta")[1]); vals.append(100 * v["delta_vs_baseline"])
    for k, v in t.items():
        if k.startswith("reference_"):
            labels.append(k.replace("reference_", "ref ")); vals.append(100 * v["delta_vs_baseline"])
    labels.append("current (AWAC diag.)"); vals.append(100 * t["current_diagnostic"]["delta_vs_monochromatic_no_current"])
    for cls, d in t["bathymetry_vertical"]["by_class"].items():
        if cls in ("frf_survey_2021", "bluetopo_direct_2019_2020_certified", "bluetopo_direct_h12859_2016",
                   "legacy_bias_corrected"):
            labels.append(f"bathy {cls} ({d['uncertainty_m']:.2f} m)")
            vals.append(-d["lambda_sensitivity_pct_at_median_depth"])
    labels.append("estimator: centroid - contour"); vals.append(100 * t["estimator_choice"]["grd"]["median_centroid_minus_contour"])
    order = np.argsort(np.abs(vals))
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(range(len(order)), [vals[i] for i in order],
            color=["tab:red" if vals[i] < 0 else "tab:blue" for i in order])
    ax.set_yticks(range(len(order))); ax.set_yticklabels([labels[i] for i in order], fontsize=8)
    ax.axvline(0, c="k", lw=.8); ax.set_xlabel("shift of the median error vs the frozen baseline (%)")
    mc = budget["hierarchical_monte_carlo"]
    ax.set_title("Block40 fig.7 - sensitivity of the reference and of the bathymetry\n"
                 f"hierarchical MC over declared scenarios: median {mc['median_of_median_pct']:.1f} %, "
                 f"p05/p95 {mc['p05_p95_pct'][0]:.1f}/{mc['p05_p95_pct'][1]:.1f} %", fontsize=10)
    ax.grid(alpha=.3, axis="x")
    fig.tight_layout(); fig.savefig(fig_dir / "fig7_reference_sensitivity.png", dpi=140); plt.close(fig)


def f8_estimators(rows, pairs, fig_dir):
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.5))
    for prod, col in (("slc", "tab:blue"), ("grd", "tab:green")):
        sel = [r for r in rows if r["product"] == prod and np.isfinite(r["rel_err_contour"])
               and np.isfinite(r["rel_err_centroid"])]
        ax[0].scatter([100 * r["rel_err_contour"] for r in sel], [100 * r["rel_err_centroid"] for r in sel],
                      s=4, alpha=.25, color=col, label=f"{prod} (n={len(sel)})")
    lim = [-80, 80]
    ax[0].plot(lim, lim, "k-", lw=.8); ax[0].set(xlim=lim, ylim=lim, xlabel="contour peak error (%)",
                                                 ylabel="radial centroid error (%)")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=.3); ax[0].set_title("primary vs secondary estimator")
    d = [100 * (p["grd_rel_err_contour"] - p["slc_rel_err_contour"]) for p in pairs
         if np.isfinite(p["grd_rel_err_contour"]) and np.isfinite(p["slc_rel_err_contour"])]
    ax[1].hist(d, bins=60, color="0.5")
    ax[1].axvline(0, c="k", lw=.8); ax[1].axvline(np.median(d), c="r", lw=1.2,
                                                  label=f"median {np.median(d):+.1f} %")
    ax[1].set(xlabel="GRD - SLC contour error on paired windows (%)", ylabel="pairs")
    ax[1].legend(fontsize=8); ax[1].grid(alpha=.3); ax[1].set_title(f"paired difference (n={len(d)})")
    fig.suptitle("Block40 fig.8 - estimator comparison and paired GRD-SLC difference")
    fig.tight_layout(); fig.savefig(fig_dir / "fig8_estimator_comparison.png", dpi=140); plt.close(fig)


def fnum(r, k):
    try:
        v = float(r[k])
        return v
    except Exception:
        return float("nan")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("duck_frf/Block40_stratified_validation"))
    ap.add_argument("--safe", default="duck_frf/Block37_s1_iw_spatial_trial/extracted_safe/"
                                     "S1A_IW_SLC__1SDV_20211028T230636_20211028T230703_040326_04C765_B6FA.SAFE")
    ap.add_argument("--only", nargs="*", type=int)
    a = ap.parse_args(argv)
    out = (ROOT / a.out) if not a.out.is_absolute() else a.out
    fig_dir = out / "figures"; fig_dir.mkdir(parents=True, exist_ok=True)
    prov = list(csv.DictReader(open(out / "BLOCK40_WINDOW_PROVENANCE.csv")))
    rows = [{**r, "depth_mean_m": fnum(r, "depth_mean_m"), "rel_err_contour": fnum(r, "rel_err_contour"),
             "rel_err_centroid": fnum(r, "rel_err_centroid"), "lambda_contour_m": fnum(r, "lambda_contour_m")}
            for r in csv.DictReader(open(out / "BLOCK40_WINDOW_RESULTS.csv"))]
    pairs = [{**p, "grd_rel_err_contour": fnum(p, "grd_rel_err_contour"),
              "slc_rel_err_contour": fnum(p, "slc_rel_err_contour")}
             for p in csv.DictReader(open(out / "BLOCK40_MATCHED_RESULTS.csv"))]
    ladder = [{**r, "rel_err": fnum(r, "rel_err"), "paired_grd_rel_err": fnum(r, "paired_grd_rel_err"),
               "transect": int(r["transect"]), "distance_m": float(r["distance_m"])}
              for r in csv.DictReader(open(out / "BLOCK40_SLC_VARIANCE_LADDER.csv"))]
    lad_sum = json.loads((out / "BLOCK40_LADDER_SUMMARY.json").read_text())
    budget = json.loads((out / "BLOCK40_UNCERTAINTY_BUDGET.json").read_text())
    todo = a.only or [1, 2, 3, 4, 5, 6, 7, 8]
    if 1 in todo:
        f1_source_map(out, fig_dir)
    if 2 in todo:
        f2_coverage(prov, fig_dir)
    if 3 in todo:
        f3_error_by_depth_and_source(rows, fig_dir)
    if 4 in todo:
        f4_ladder(lad_sum, fig_dir)
    if 5 in todo:
        f5_tails(ladder, rows, fig_dir)
    if 6 in todo:
        f6_example_spectra(out, fig_dir, a.safe, ladder)
    if 7 in todo:
        f7_sensitivity(budget, fig_dir)
    if 8 in todo:
        f8_estimators(rows, pairs, fig_dir)
    print("figures:", sorted(p.name for p in fig_dir.glob("*.png")))


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Forward check of SAR wavenumbers against measured bathymetry (no inversion).

For every SAR window of an s1_transect_bathy run (windows.csv + window_spectra.npz)
whose whole footprint lies on certified bathymetry (ground truth of
frf_ground_truth.py: EMPIRICAL vertical uncertainty (band 8, NMAD against
higher-ranked data) <= --max-uncertainty, not interpolated, optional source year
>= --min-year, event depth <= --max-depth), the measured frequency
spectrum E(f) of a reference wave gauge is mapped to a wavenumber spectrum at the
depths inside the footprint with linear dispersion (U = 0),
    E(k) = E(f) df/dk = E(f) c_g / (2 pi),     omega^2 = g k tanh(k h),
optionally weighted by k^2 (tilt + hydrodynamic modulation, range-travelling
waves), and compared with the SAR radial spectrum taken in a +-sector around
the SAR's own peak direction.  Peak and half-power centroid wavenumbers are
compared; other gauges' discrete peak periods give a period sensitivity.

The SAR selection never uses bathymetry or buoy data.
"""
from __future__ import annotations
import argparse, csv, json, math
from pathlib import Path
import numpy as np

G = 9.80665


def k_from_omega(omega, h, iters=40):
    omega = np.asarray(omega, float); h = np.asarray(h, float)
    k = omega ** 2 / G / np.sqrt(np.tanh(omega ** 2 * h / G))     # Eckart-type start
    for _ in range(iters):
        t = np.tanh(k * h); f = G * k * t - omega ** 2
        df = G * t + G * k * h * (1 - t ** 2)
        k = k - f / df
    return k


def group_velocity(k, h):
    kh = k * h; om = np.sqrt(G * k * np.tanh(kh))
    return 0.5 * om / k * (1 + 2 * kh / np.sinh(2 * kh))


def predicted_radial(freq, energy, depths, kbins, weight_k2):
    """E(k) histogram-averaged over the footprint depth samples (vectorised over depths)."""
    ok = np.isfinite(energy) & (freq > 0)
    f = freq[ok]; e = energy[ok]; df = np.gradient(f)
    om = 2 * np.pi * f
    h = np.asarray(depths, float)[:, None]
    K = k_from_omega(np.broadcast_to(om, (h.shape[0], om.size)), np.broadcast_to(h, (h.shape[0], om.size)))
    var = np.broadcast_to(e * df, K.shape)
    if weight_k2:
        var = var * K ** 2
    S = np.histogram(K.ravel(), bins=kbins, weights=var.ravel())[0]
    return S / h.shape[0] / np.diff(kbins)


def peak_and_centroid(kc, S):
    if not np.any(S > 0):
        return np.nan, np.nan, [np.nan, np.nan]
    i = int(np.argmax(S)); kp = kc[i]
    if 0 < i < len(S) - 1 and np.all(S[i - 1:i + 2] > 0):
        a, b, c = np.log(S[i - 1:i + 2]); den = a - 2 * b + c
        if den < 0:
            kp = kc[i] + 0.5 * (a - c) / den * (kc[1] - kc[0])
    half = S >= S[i] / 2
    # contiguous half-power band around the peak
    lo = i
    while lo > 0 and half[lo - 1]:
        lo -= 1
    hi = i
    while hi < len(S) - 1 and half[hi + 1]:
        hi += 1
    w = S[lo:hi + 1]
    return float(kp), float(np.sum(kc[lo:hi + 1] * w) / np.sum(w)), [float(kc[lo]), float(kc[hi])]


def sar_radial(P, mask, k, sector_deg):
    KE, KN = np.meshgrid(k, k); kr = np.hypot(KE, KN); th = np.degrees(np.arctan2(KE, KN)) % 180
    Pm = np.where(mask, P, np.nan)
    iy, ix = np.unravel_index(np.nanargmax(np.where(KE >= 0, Pm, np.nan)), P.shape)
    th0 = th[iy, ix]
    dth = np.abs((th - th0 + 90) % 180 - 90)
    sect = mask & (dth <= sector_deg)
    floor = np.nanmedian(np.where(mask & ~sect, P, np.nan))      # speckle/background level
    dk = k[1] - k[0]; kbins = np.arange(0, kr[mask].max() + dk, dk)
    num = np.histogram(kr[sect], bins=kbins, weights=(P[sect] - floor))[0]
    cnt = np.histogram(kr[sect], bins=kbins)[0]
    with np.errstate(invalid="ignore"):
        S = np.where(cnt > 0, num / cnt, 0.0)
    return kbins, np.clip(S, 0, None), float(th0), float(floor)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True, help="s1_transect_bathy output dir (with --save-spectra)")
    ap.add_argument("--ground-truth", type=Path, required=True, help="frf_ground_truth output dir")
    ap.add_argument("--reference", default="FRF:8m-array", help="gauge whose E(f) is propagated")
    ap.add_argument("--max-depth", type=float, default=30.0)
    ap.add_argument("--max-uncertainty", type=float, default=0.5, help="max empirical vertical uncertainty (m) in footprint")
    ap.add_argument("--min-year", type=float, default=0, help="optional minimum source year (accuracy, not age, is the default criterion)")
    ap.add_argument("--sector", type=float, default=30.0, help="half-width (deg) of the SAR directional sector")
    ap.add_argument("--depth-samples", type=int, default=60)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--chunk", nargs=2, type=int, metavar=("I", "N"), help="process the I-th of N window slices, save partial rows")
    ap.add_argument("--finalize", type=int, metavar="N", help="merge N partial row files and write summary/figure")
    a = ap.parse_args(argv)
    out = a.out or a.run / "forward_check"; out.mkdir(parents=True, exist_ok=True)
    import rasterio
    from rasterio.features import geometry_mask
    gt = a.ground_truth
    ds = rasterio.open(gt / "bathymetry_merged_utm.tif")
    depth, unc, year, interp, src = (ds.read(i) for i in (3, 8 if ds.count >= 8 else 4, 6, 7, 2))
    spectra = json.loads((gt / "wave_spectra.json").read_text())
    ref = spectra[a.reference]; freq = np.asarray(ref["frequency_hz"], float); energy = np.asarray(ref["energy_m2_hz"], float)
    periods = {inst: 1 / np.asarray(v["frequency_hz"])[int(np.nanargmax(np.asarray(v["energy_m2_hz"], float)))] for inst, v in spectra.items()}
    sp = np.load(a.run / "window_spectra.npz"); k = sp["k"]; mask = sp["mask"]
    power = sp["power"]                       # decompress once (npz members are re-read on every access)
    idx = {(int(t), float(d)): i for i, (t, d) in enumerate(zip(sp["transect"], sp["distance_m"]))}
    rows_in = [r for r in csv.DictReader(open(a.run / "windows.csv")) if r["status"] == "ok"]
    rng = np.random.default_rng(0); rows = []
    for r in rows_in:
        key = (int(r["transect"]), float(r["distance_m"]))
        if key not in idx:
            continue
        poly = {"type": "Polygon", "coordinates": [[(float(r[f"fp_E{i}"]), float(r[f"fp_N{i}"])) for i in (0, 1, 2, 3, 0)]]}
        # rasterise only the footprint's bounding window (full-raster masks are slow)
        xs_ = [c[0] for c in poly["coordinates"][0]]; ys_ = [c[1] for c in poly["coordinates"][0]]
        r0, c0 = ds.index(min(xs_), max(ys_)); r1, c1 = ds.index(max(xs_), min(ys_))
        r0, c0 = max(r0 - 1, 0), max(c0 - 1, 0); r1, c1 = min(r1 + 2, depth.shape[0]), min(c1 + 2, depth.shape[1])
        inside = np.zeros(depth.shape, bool)
        if r1 > r0 and c1 > c0:
            wt = ds.transform * rasterio.Affine.translation(c0, r0)
            inside[r0:r1, c0:c1] = ~geometry_mask([poly], out_shape=(r1 - r0, c1 - c0), transform=wt, all_touched=True)
        if not inside.any():
            continue
        d = depth[inside]; u = unc[inside]
        cert = (np.all(np.isfinite(d)) and np.all(np.isfinite(u)) and np.nanmax(u) <= a.max_uncertainty
                and np.all(interp[inside] == 0) and (a.min_year <= 0 or (np.all(np.isfinite(year[inside])) and np.nanmin(year[inside]) >= a.min_year))
                and np.nanmax(d) <= a.max_depth and np.nanmin(d) > 0)
        o = {"transect": key[0], "distance_m": key[1], "E": float(r["E"]), "N": float(r["N"]), "certified": bool(cert),
             "depth_mean_m": float(np.nanmean(d)), "depth_p10_m": float(np.nanpercentile(d, 10)), "depth_p90_m": float(np.nanpercentile(d, 90)),
             "uncertainty_max_m": float(np.nanmax(u)) if np.any(np.isfinite(u)) else np.nan,
             "frf_survey_fraction": float(np.mean(src[inside] == 1)), "legacy_fraction": float(np.mean(src[inside] == 4)),
             "source_year_min": float(np.nanmin(year[inside])) if np.any(np.isfinite(year[inside])) else np.nan, "sar_paper_wavelength_m": float(r["wavelength_m"]) if r.get("wavelength_m") else np.nan,
             "sar_identifiable": r.get("identifiable") == "True"}
        if cert:
            P = power[idx[key]].astype(float)
            kbins, S_sar, th0, floor = sar_radial(P, mask, k, a.sector)
            kc = 0.5 * (kbins[1:] + kbins[:-1])
            kp, kcen, band = peak_and_centroid(kc, S_sar)
            hs = rng.choice(d[np.isfinite(d)], size=min(a.depth_samples, np.isfinite(d).sum()), replace=False)
            o.update(sar_axial_deg=th0, sar_peak_k=kp, sar_centroid_k=kcen, sar_band_k=band)
            for tag, w in (("Ek", False), ("k2Ek", True)):
                # prediction on a fine k grid: the SAR bin width (2 pi / window) would quantise it by ~10 %
                kf = np.linspace(0, kbins[-1], 8 * (len(kbins) - 1) + 1); kfc = 0.5 * (kf[1:] + kf[:-1])
                S_p = predicted_radial(freq, energy, hs, kf, w)
                pk, pc, pb = peak_and_centroid(kfc, S_p)
                o.update({f"pred_{tag}_peak_k": pk, f"pred_{tag}_centroid_k": pc, f"pred_{tag}_band_k": pb})
            for inst, T in periods.items():
                o[f"lambda_Tpeak_{inst.split(':')[-1]}_m"] = float(np.mean(2 * np.pi / k_from_omega(2 * np.pi / T, hs)))
        rows.append(o)
    keys = []
    for o in rows:
        keys += [k_ for k_ in o if k_ not in keys]
    with open(out / "forward_windows.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    cert = [o for o in rows if o["certified"]]
    summ = {"reference_gauge": a.reference, "reference_peak_period_s": periods.get(a.reference), "periods_by_gauge_s": periods,
            "criteria": {"max_depth_m": a.max_depth, "max_uncertainty_m": a.max_uncertainty, "min_year": a.min_year,
                         "not_interpolated": True}, "windows_total": len(rows), "windows_certified": len(cert),
            "note": "overlapping windows (50 m step, 512 m windows, alongshore averaging) are strongly correlated; effective sample is far smaller"}
    if cert:
        for tag in ("Ek", "k2Ek"):
            for kind in ("peak", "centroid"):
                s_ = np.array([o[f"sar_{kind}_k"] for o in cert]); p_ = np.array([o[f"pred_{tag}_{kind}_k"] for o in cert])
                ok = np.isfinite(s_) & np.isfinite(p_) & (p_ > 0)
                rel = p_[ok] / s_[ok] - 1          # = lambda_SAR / lambda_pred - 1
                summ[f"{tag}_{kind}"] = {"n": int(ok.sum()), "median_lambdaSAR_over_lambdaPred_minus_1": float(np.median(rel)),
                                         "p10_p90": np.percentile(rel, [10, 90]).tolist(), "rms": float(np.sqrt(np.mean(rel ** 2)))}
        lp = np.array([o["sar_paper_wavelength_m"] for o in cert]); lpr = np.array([2 * np.pi / o["pred_Ek_centroid_k"] for o in cert])
        ok = np.isfinite(lp) & np.isfinite(lpr) & np.array([o["sar_identifiable"] for o in cert])
        rel = lp[ok] / lpr[ok] - 1
        summ["paper_peak_vs_Ek_centroid"] = {"n": int(ok.sum()), "median_lambdaSAR_over_lambdaPred_minus_1": float(np.median(rel)),
                                             "p10_p90": np.percentile(rel, [10, 90]).tolist(), "rms": float(np.sqrt(np.mean(rel ** 2)))}
        summ["k2_weighting_note"] = ("k^2 weighting of the full gauge spectrum is dominated by the high-frequency tail "
                                     "(no azimuth cut-off / system MTF / noise model); reported for completeness, not interpretable")
        d = np.array([o["depth_mean_m"] for o in cert])
        summ["depth_range_certified_m"] = [float(d.min()), float(d.max())]
        bins = []
        for lo in np.arange(np.floor(d.min()), np.ceil(d.max()), 1.0):
            m = [o for o in cert if lo <= o["depth_mean_m"] < lo + 1]
            if m:
                bins.append({"depth_bin_m": [float(lo), float(lo + 1)], "n": len(m),
                             "lambda_sar_centroid_median_m": float(np.median([2 * np.pi / o["sar_centroid_k"] for o in m])),
                             "lambda_pred_k2Ek_centroid_median_m": float(np.median([2 * np.pi / o["pred_k2Ek_centroid_k"] for o in m])),
                             "lambda_pred_Ek_centroid_median_m": float(np.median([2 * np.pi / o["pred_Ek_centroid_k"] for o in m])),
                             "lambda_sar_paper_median_m": float(np.nanmedian([o["sar_paper_wavelength_m"] for o in m]))})
        summ["by_depth_bin"] = bins
    (out / "forward_summary.json").write_text(json.dumps(summ, indent=2, default=float))
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 6))
        if cert:
            d = np.array([o["depth_mean_m"] for o in cert])
            ax.scatter(d, [2 * np.pi / o["sar_centroid_k"] for o in cert], s=10, c="k", label="SAR radial centroid (sector)")
            ax.scatter(d, [o["sar_paper_wavelength_m"] for o in cert], s=8, c="0.6", marker="x", label="SAR paper contour peak")
            ax.scatter(d, [2 * np.pi / o["pred_Ek_centroid_k"] for o in cert], s=10, c="tab:orange", label=f"pred. {a.reference} spectrum, E(k)")
            hh = np.linspace(max(1, d.min() - 1), d.max() + 1, 50)
            for inst, T in periods.items():
                ax.plot(hh, 2 * np.pi / k_from_omega(2 * np.pi / T, hh), lw=1, label=f"λ(h) at {inst.split(':')[-1]} peak T={T:.1f} s")
        ax.set(xlabel="mean event depth in window footprint (m)", ylabel="wavelength (m)",
               title="Forward check on certified bathymetry (no inversion)"); ax.grid(alpha=.3); ax.legend(fontsize=7)
        fig.tight_layout(); fig.savefig(out / "forward_lambda_vs_depth.png", dpi=150); plt.close(fig)
    except Exception as exc:
        print("figure skipped:", exc)
    print(json.dumps({k_: v for k_, v in summ.items() if k_ != "by_depth_bin"}, indent=1, default=float))


if __name__ == "__main__":
    main()

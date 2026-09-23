#!/usr/bin/env python
"""Block40 step 4 - controlled SLC variance reduction (spatial audit only).

Recomputes the spectrum of the *same* native SLC windows with four estimators that
differ only in the averaging domain, and compares them with the ESA GRD result of the
paired window:

  slc_single_look     one Hann-tapered periodogram (reference)
  slc_incoherent_N2   2 disjoint azimuth sub-blocks, periodograms averaged
  slc_incoherent_N4   2x2 disjoint sub-blocks, periodograms averaged
  slc_multitaper_K4   2-D DPSS multitaper (NW=2.5, K=2 per axis -> 4 tapers)
  grd_esa             paired ESA-focused GRDH window (external reference)

No temporal sub-aperture is created and no physical time is attached to any look:
this is a spatial variance audit.  Averaged pixels, tapers and sub-blocks are not
independent acquisitions and are never treated as Monte-Carlo replicas.

Identical across variants: footprint, plane detrending in affine ground coordinates,
k grid, kmin, sector, peak algorithm (contour), identifiability rule.  Per window and
variant the script records the wavelength, the lobe-to-annulus prominence, an ENL
diagnostic measured on a signal-free annulus, the half-power radial width of the main
lobe (effective spectral resolution), and the lobe displacement with respect to the
single-look estimate.
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
import s1_paper_peak as pp
import s1_transect_bathy as tb
from forward_lambda_check import block_bootstrap


def dpss_tapers(n, nw, k):
    """Discrete prolate spheroidal sequences; scipy >= 1.1 provides them directly."""
    from scipy.signal.windows import dpss
    return np.atleast_2d(dpss(n, nw, k))


def periodogram_affine(z, J, k):
    """|DTFT|^2 of one tapered block on the fixed k grid, normalised by the taper energy."""
    mag = tb.dtft_affine(z, J, k)
    return (mag ** 2) / max(float(np.sum(np.abs(z) ** 2)), 1e-30)


def variant_spectra(sig, S, L, J, k, variant):
    """Return the averaged periodogram and the number of averaged looks."""
    Sm, Lm = S.mean(), L.mean()
    Ea = J[0, 0] * (S - Sm) + J[0, 1] * (L - Lm)
    Na = J[1, 0] * (S - Sm) + J[1, 1] * (L - Lm)
    det = pp.plane_detrend(sig, Ea, Na)
    nl, ns = det.shape
    if variant == "slc_single_look":
        return periodogram_affine(det * pp.hann2(det.shape), J, k), 1
    if variant in ("slc_incoherent_N2", "slc_incoherent_N4"):
        nb = (2, 1) if variant == "slc_incoherent_N2" else (2, 2)
        hl, hs = nl // nb[0], ns // nb[1]
        acc = None; n = 0
        for i in range(nb[0]):
            for j in range(nb[1]):
                b = det[i * hl:(i + 1) * hl, j * hs:(j + 1) * hs]
                P = periodogram_affine(b * pp.hann2(b.shape), J, k)
                acc = P if acc is None else acc + P
                n += 1
        return acc / n, n
    if variant == "slc_multitaper_K4":
        tl = dpss_tapers(nl, 2.5, 2); ts = dpss_tapers(ns, 2.5, 2)
        acc = None; n = 0
        for wl in tl:
            for ws in ts:
                P = periodogram_affine(det * np.outer(wl, ws), J, k)
                acc = P if acc is None else acc + P
                n += 1
        return acc / n, n
    raise ValueError(variant)


def diagnostics(P, k, mask, kmin):
    """Peak, prominence, ENL on a signal-free annulus, half-power radial width."""
    KE, KN = np.meshgrid(k, k); kr = np.hypot(KE, KN)
    m = mask & (kr >= kmin)
    mag = np.sqrt(P)
    res = pp.paper_peak(mag, k, k, m, n_levels=20, scale="log10", blob_method="contour")
    out = {"peak_status": res["status"], "n_blobs": len(res.get("blobs_canonical", []))}
    dk = k[1] - k[0]
    if "wavelength_m" in res:
        kp = res["k_rad_m"]
        out.update(wavelength_m=res["wavelength_m"], k_rad_m=kp,
                   axial_bearing_deg=math.degrees(math.atan2(res["kx"], res["ky"])) % 180,
                   lobe_to_annulus=pp.lobe_to_annulus(mag, k, k, m, res["kx"], res["ky"], 2 * np.pi / (2 * np.pi / dk)),
                   peak_at_kmin_edge=bool(kp < kmin + 0.5 * dk))
        # half-power radial width of the main lobe along the peak direction
        th = math.atan2(res["kx"], res["ky"])
        rr = np.arange(max(kmin, kp - 20 * dk), kp + 20 * dk, dk / 4)
        pts = np.interp(rr, k, np.arange(k.size))                      # index along each axis
        ke = rr * math.sin(th); kn = rr * math.cos(th)
        from scipy.ndimage import map_coordinates
        ie = np.interp(ke, k, np.arange(k.size)); iN = np.interp(kn, k, np.arange(k.size))
        prof = map_coordinates(P, [iN, ie], order=1, mode="nearest")
        pk = prof.max(); half = prof >= pk / 2
        i0 = int(np.argmax(prof))
        lo = i0
        while lo > 0 and half[lo - 1]:
            lo -= 1
        hi = i0
        while hi < len(prof) - 1 and half[hi + 1]:
            hi += 1
        out["lobe_halfpower_width_rad_m"] = float(rr[hi] - rr[lo])
        # ENL diagnostic: variance of the estimate in a signal-free annulus (far from the peak)
        ann = m & (np.abs(kr - kp) > 6 * dk) & (kr > kmin + 3 * dk)
        v = P[ann]
        v = v[np.isfinite(v) & (v > 0)]
        out["enl_annulus"] = float(np.mean(v) ** 2 / np.var(v)) if v.size > 50 else float("nan")
        out["annulus_cells"] = int(v.size)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--safe", type=Path, default=Path("duck_frf/Block37_s1_iw_spatial_trial/extracted_safe/"
                    "S1A_IW_SLC__1SDV_20211028T230636_20211028T230703_040326_04C765_B6FA.SAFE"))
    ap.add_argument("--runs", nargs="+", default=["slc_near:duck_frf/Block39_s1_paper_confirm/slc/near_k4:512",
                                                 "slc_far:duck_frf/Block39_s1_paper_confirm/slc/far_k4:1024"])
    ap.add_argument("--out", type=Path, default=Path("duck_frf/Block40_stratified_validation"))
    ap.add_argument("--window-class", default="primary_admissible")
    ap.add_argument("--kmin-factor", type=float, default=4.0)
    ap.add_argument("--kmax", type=float, default=None,
                    help="default: the kmax frozen in each run's run.json (0.30 near, 0.15 far), so the ladder "
                         "shares the k grid of the Block39 run it audits; identical across variants either way")
    ap.add_argument("--pol", default="VV")
    ap.add_argument("--chunk", nargs=2, type=int, metavar=("I", "N"))
    ap.add_argument("--finalize", type=int, metavar="N")
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    out = (ROOT / a.out) if not a.out.is_absolute() else a.out
    parts = out / "ladder_parts"
    variants = ["slc_single_look", "slc_incoherent_N2", "slc_incoherent_N4", "slc_multitaper_K4"]

    prov = {(r["run"], int(r["transect"]), float(r["distance_m"])): r
            for r in csv.DictReader(open(out / "BLOCK40_WINDOW_PROVENANCE.csv"))}
    rows = []
    import pickle
    if a.finalize:
        for i in range(a.finalize):
            f = parts / f"part_{i}_of_{a.finalize}.pkl"
            if not f.exists():
                raise SystemExit(f"missing {f.name}")
            rows += pickle.loads(f.read_bytes())
    else:
        safe = (ROOT / a.safe) if not a.safe.is_absolute() else a.safe
        swaths = {s.name: s for s in tb.open_swaths(safe, a.pol)}
        todo = []
        kmax_by_run = {}
        for spec in a.runs:
            label, d, win = spec.split(":")
            run = ROOT / d
            kmax_by_run[label] = a.kmax if a.kmax else float(json.loads((run / "run.json").read_text())["args"]["kmax"])
            for r in csv.DictReader(open(run / "windows.csv")):
                key = (label, int(r["transect"]), float(r["distance_m"]))
                p = prov.get(key)
                if r["status"] != "ok" or p is None or p["window_class"] != a.window_class:
                    continue
                todo.append((label, float(win), r, p))
        if a.chunk:
            todo = list(np.array_split(np.array(todo, dtype=object), a.chunk[1])[a.chunk[0]])
        # one read per swath covering all requested windows
        need = {}
        for label, win, r, p in todo:
            ns = int(r["n_samples"]); nl = int(r["n_lines"])
            s0 = int(round(float(r["sample"]) - ns / 2)); l0 = int(round(float(r["line"]) - nl / 2))
            b = need.setdefault(r["swath"], [10 ** 9, 10 ** 9, -1, -1])
            b[0] = min(b[0], s0 - ns); b[1] = min(b[1], l0 - nl); b[2] = max(b[2], s0 + 2 * ns); b[3] = max(b[3], l0 + 2 * nl)
        blocks = {}
        for name, (s0, l0, s1, l1) in need.items():
            sw = swaths[name]
            dn, rs0, rl0 = sw.read(max(0, s0), max(0, l0), s1, l1)
            blocks[name] = (rs0, rl0, dn)
            print(f"read {name}: {dn.shape} at {rs0},{rl0}", flush=True)
        epsg, to_utm, to_geo = tb.utm_transformers(-75.675, 36.205)
        for label, win, r, p in todo:
            sw = swaths[r["swath"]]; rs0, rl0, dn = blocks[r["swath"]]
            ns = int(r["n_samples"]); nl = int(r["n_lines"])
            s0 = int(round(float(r["sample"]) - ns / 2)); l0 = int(round(float(r["line"]) - nl / 2))
            sl = (slice(l0 - rl0, l0 - rl0 + nl), slice(s0 - rs0, s0 - rs0 + ns))
            if sl[0].start < 0 or sl[1].start < 0 or sl[0].stop > dn.shape[0] or sl[1].stop > dn.shape[1]:
                continue
            L, S = np.mgrid[l0:l0 + nl, s0:s0 + ns].astype(float)
            sig = sw.sigma0(dn[sl], L, S)
            sub = (slice(None, None, 3), slice(None, None, 3))
            lo, la = sw.geo.forward(S[sub], L[sub]); E, N = (np.asarray(v) for v in to_utm(lo, la))
            J, resid = tb.affine_fit(S[sub] - S.mean(), L[sub] - L.mean(), E - E.mean(), N - N.mean())
            kmax = kmax_by_run[label]
            k, dk = pp.k_grid(win, 1, kmax)
            gs = float(r["ground_spacing_sample_m"]); gl = float(r["ground_spacing_line_m"])
            ls_, lg_ = sw.geo.ground_spacing(float(r["sample"]), float(r["line"]), to_utm)[2:]
            ua = np.asarray(lg_) / np.linalg.norm(lg_); ur = np.asarray(ls_) / np.linalg.norm(ls_)
            lim = [(ua[0], ua[1], 0.8 * np.pi / gl), (ur[0], ur[1], 0.8 * np.pi / gs)]
            mask0 = pp.search_mask(k, k, 2 * np.pi / win, lim)
            kmin = a.kmin_factor * np.pi / win
            base = {"run": label, "transect": int(r["transect"]), "distance_m": float(r["distance_m"]),
                    "window_m": win, "E": float(r["E"]), "N": float(r["N"]),
                    "band_name": p["band_name"], "dominant_class_name": p["dominant_class_name"],
                    "depth_mean_m": float(p["depth_mean_m"]), "affine_residual_max_m": resid,
                    "n_samples": ns, "n_lines": nl, "ground_spacing_sample_m": gs, "ground_spacing_line_m": gl,
                    "kmax_rad_m": kmax}
            ref = None
            for v in variants:
                P, looks = variant_spectra(sig, S, L, J, k, v)
                diag = diagnostics(P, k, mask0, kmin)
                row = {**base, "variant": v, "looks_averaged": looks,
                       "averaging_domain": {"slc_single_look": "none",
                                            "slc_incoherent_N2": "2 disjoint azimuth sub-blocks, intensity spectra",
                                            "slc_incoherent_N4": "2x2 disjoint sub-blocks, intensity spectra",
                                            "slc_multitaper_K4": "4 DPSS tapers (NW=2.5), same full window"}[v],
                       "effective_window_lines": {"slc_single_look": nl, "slc_incoherent_N2": nl // 2,
                                                  "slc_incoherent_N4": nl // 2, "slc_multitaper_K4": nl}[v],
                       "effective_window_samples": {"slc_single_look": ns, "slc_incoherent_N2": ns,
                                                    "slc_incoherent_N4": ns // 2, "slc_multitaper_K4": ns}[v],
                       **diag}
                if v == "slc_single_look":
                    ref = row
                if ref and "wavelength_m" in row and "wavelength_m" in ref:
                    row["lambda_shift_vs_single_look"] = row["wavelength_m"] / ref["wavelength_m"] - 1
                    row["bearing_shift_deg_vs_single_look"] = ((row["axial_bearing_deg"] - ref["axial_bearing_deg"] + 90) % 180) - 90
                rows.append(row)
        if a.chunk:
            parts.mkdir(parents=True, exist_ok=True)
            (parts / f"part_{a.chunk[0]}_of_{a.chunk[1]}.pkl").write_bytes(pickle.dumps(rows))
            print(f"saved ladder part {a.chunk[0]}/{a.chunk[1]}: {len(rows)} rows", flush=True)
            return

    # ---- attach the prediction and the paired GRD result
    pred = {}
    for lab in ("slc_near", "slc_far", "grd_near", "grd_far"):
        f = out / "forward" / lab / "forward_windows.csv"
        if f.exists():
            for r in csv.DictReader(open(f)):
                if r["certified"] == "True" and r.get("pred_Ek_centroid_k"):
                    try:
                        pred[(lab, int(r["transect"]), float(r["distance_m"]))] = 2 * np.pi / float(r["pred_Ek_centroid_k"])
                    except Exception:
                        pass
    grd = {}
    for r in csv.DictReader(open(out / "BLOCK40_WINDOW_RESULTS.csv")):
        if r["product"] == "grd":
            grd[(r["geometry"], float(r["E"]), float(r["N"]))] = r
    grd_xy = np.array([[e, n] for (_, e, n) in grd]) if grd else np.zeros((0, 2))
    grd_keys = list(grd)
    for row in rows:
        key = (row["run"], row["transect"], row["distance_m"])
        lam_pred = pred.get(key, float("nan"))
        row["lambda_pred_m"] = lam_pred
        row["rel_err"] = row["wavelength_m"] / lam_pred - 1 if row.get("wavelength_m") and np.isfinite(lam_pred) else float("nan")
        row["block"] = f"{row['transect'] // 9}_{int(row['distance_m'] // 1024)}"
        if grd_keys:
            geom = row["run"].split("_")[1]
            d = np.hypot(grd_xy[:, 0] - row["E"], grd_xy[:, 1] - row["N"])
            same = np.array([grd_keys[i][0] == geom for i in range(len(grd_keys))])
            d = np.where(same, d, np.inf)
            j = int(np.argmin(d))
            tol = 25.0 if geom == "near" else 50.0
            if d[j] <= tol:
                g = grd[grd_keys[j]]
                row["paired_grd_centre_offset_m"] = float(d[j])
                row["paired_grd_lambda_m"] = float(g["lambda_contour_m"]) if g["lambda_contour_m"] not in ("", "nan") else float("nan")
                row["paired_grd_rel_err"] = float(g["rel_err_contour"]) if g["rel_err_contour"] not in ("", "nan") else float("nan")

    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(out / "BLOCK40_SLC_VARIANCE_LADDER.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)

    summ = {"variants": {}, "note": ["spatial variance reduction only; no temporal sub-aperture, no time assigned to looks",
                                     "tapers, sub-blocks and averaged pixels are not independent acquisitions",
                                     "the single-look reference here has no alongshore averaging, unlike the Block39 runs"]}
    rng = np.random.default_rng(a.seed)
    for v in variants + ["grd_esa"]:
        if v == "grd_esa":
            sel = [r for r in rows if r["variant"] == "slc_single_look" and np.isfinite(r.get("paired_grd_rel_err", np.nan))]
            e = [r["paired_grd_rel_err"] for r in sel]; blk = [r["block"] for r in sel]
            extra = {"paired_windows": len(sel)}
        else:
            sel = [r for r in rows if r["variant"] == v]
            e = [r["rel_err"] for r in sel if np.isfinite(r.get("rel_err", np.nan))]
            blk = [r["block"] for r in sel if np.isfinite(r.get("rel_err", np.nan))]
            ident = [r for r in sel if r.get("wavelength_m")]
            extra = {"windows": len(sel), "with_peak": len(ident),
                     "looks_averaged": int(np.median([r["looks_averaged"] for r in sel])) if sel else 0,
                     "enl_annulus_median": float(np.nanmedian([r.get("enl_annulus", np.nan) for r in sel])),
                     "lobe_halfpower_width_median_rad_m": float(np.nanmedian([r.get("lobe_halfpower_width_rad_m", np.nan) for r in sel])),
                     "lobe_to_annulus_median": float(np.nanmedian([r.get("lobe_to_annulus", np.nan) for r in sel])),
                     "lambda_shift_vs_single_look_median": float(np.nanmedian([r.get("lambda_shift_vs_single_look", np.nan) for r in sel])),
                     "bearing_shift_deg_median": float(np.nanmedian([r.get("bearing_shift_deg_vs_single_look", np.nan) for r in sel])),
                     "peak_at_kmin_edge_fraction": float(np.mean([bool(r.get("peak_at_kmin_edge")) for r in sel])) if sel else 0.0}
        s = block_bootstrap(e, blk, a.bootstrap, np.random.default_rng(a.seed))
        if e:
            arr = np.asarray(e)
            s["short_wavelength_tail_fraction"] = float(np.mean(arr < -0.25))
            s["p05"] = float(np.percentile(arr, 5))
        summ["variants"][v] = {**extra, **s}
    (out / "BLOCK40_LADDER_SUMMARY.json").write_text(json.dumps(summ, indent=2, default=float))
    print(json.dumps(summ, indent=1, default=float)[:3000])


if __name__ == "__main__":
    main()

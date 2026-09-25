"""Block41 - Monte Carlo audit of the footprint-depth subsampling in the forward check.

forward_lambda_check.py predicts E(k) per window from 60 footprint depths drawn at random with one
generator shared by all windows of a process. Block39/40 ran chunked (6 processes, each restarting
at seed 0), so the predicted lambda of a window depended on the chunking (found in repro_block39).

Phase A re-runs the forward check on the committed Block39 SAR runs, chunked 6 as in Block39, for
the configurations that feed the published numbers:
  b39_sar      WR17, SAR-driven sector              -> Block39 headline (combine, WR17, far >= 19 m)
  b39_fixed72  WR17, fixed sector 72 deg            -> fallback rows of block40_matched (NOT re-run:
               committed files in every realization; the primary strata do not use them)
  b40_fixed66  WR17, fixed 66.34 deg, admissible set -> Block40 primary strata
storing, per certified window, 20 random subsamples seeded per window (chunk-independent) and the
deterministic 'all' (every footprint cell) and 'quantile' (60 mid-quantiles) predictions.
The legacy column must reproduce the committed files exactly (check L).

Phase B recomputes, for each realization (legacy, mc00..mc19, all, quantile), the Block39 combine
headline and the Block40 stratified statistics, and summarises their spread.

Declared before running: the Monte Carlo spread (sd and min-max over the 20 realizations) of every
headline/stratum median and CI bound is reported as the subsampling error of the published numbers;
'all' is the deterministic reference for Block41 onward, 'quantile' is reported as a check of it.
k_from_omega now stops at convergence instead of 40 fixed Newton steps (speed; the root agrees to
an ulp; the b39_sar/slc_near run was computed before this change). Only pred_Ek_centroid_k changes between realizations; SAR estimates, certification and the
bootstrap seed are identical in all of them.
"""
import argparse, csv, json, math, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
B39 = Path("duck_frf/Block39_s1_paper_confirm")
B40 = Path("duck_frf/Block40_stratified_validation")
RUNS = {"slc_near": "slc/near_k4", "slc_far": "slc/far_k4", "grd_near": "grd/near_k4", "grd_far": "grd/far_k4"}
COMMITTED = {"b39_sar": lambda lab, sub: B39 / sub / "fwd_waverider-17m_sar",
             "b39_fixed72": lambda lab, sub: B39 / sub / "fwd_waverider-17m_fixed",
             "b40_fixed66": lambda lab, sub: B40 / "forward" / lab}
N_MC = 20; CHUNKS = 6
# b39_fixed72 feeds block40_matched only for windows without a certified Block40 row, which the primary
# strata do not use: it is taken from the committed files, identical in every realization
MC_CFGS = ("b39_sar", "b40_fixed66")


def cfg_args(cfg, lab):
    a = ["--reference", "FRF:waverider-17m"]
    if cfg == "b39_fixed72":
        a += ["--sector-source", "fixed", "--sector-bearing", "72"]
    if cfg == "b40_fixed66":
        a += ["--sector-source", "fixed", "--sector-bearing", "66.34",
              "--admissible-csv", str(B40 / "BLOCK40_WINDOW_PROVENANCE.csv"), "--admissible-run", lab]
    return a


def run(cmd, quiet=False):
    print(">", " ".join(map(str, cmd)), flush=True)
    subprocess.run([sys.executable, *map(str, cmd)], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL if quiet else None)


def read_csv(p):
    return list(csv.DictReader(open(ROOT / p, newline="")))


def write_csv(p, rows):
    p = ROOT / p; p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def phase_a(out, gt, skip):
    timing = {}
    for cfg in MC_CFGS:
        for lab, sub in RUNS.items():
            dst = out / "forward" / cfg / lab
            if skip and (ROOT / dst / "forward_windows.csv").exists():
                continue
            base = ["code/forward_lambda_check.py", "--run", B39 / sub, "--ground-truth", gt, "--out", dst,
                    "--depth-sampling", "random", "--seed", "0", "--mc-realizations", N_MC, *cfg_args(cfg, lab)]
            t0 = time.time()
            for i in range(CHUNKS):
                run(base + ["--chunk", i, CHUNKS], quiet=True)
            run(base + ["--finalize", CHUNKS], quiet=True)
            timing[f"{cfg}/{lab}"] = time.time() - t0
    return timing


def legacy_check(out):
    res = {}
    for cfg in MC_CFGS:
        where = COMMITTED[cfg]
        for lab, sub in RUNS.items():
            old = {(r["transect"], float(r["distance_m"])): r for r in read_csv(where(lab, sub) / "forward_windows.csv")}
            new = {(r["transect"], float(r["distance_m"])): r for r in read_csv(out / "forward" / cfg / lab / "forward_windows.csv")}
            cert = [k for k, r in old.items() if r["certified"] == "True"]
            same_cert = {k for k, r in new.items() if r["certified"] == "True"} == set(cert)
            rel = [abs(float(new[k]["pred_Ek_centroid_k"]) / float(old[k]["pred_Ek_centroid_k"]) - 1)
                   for k in cert if k in new and old[k]["pred_Ek_centroid_k"] not in ("", "nan")]
            res[f"{cfg}/{lab}"] = {"certified_equal": same_cert, "n_certified": len(cert),
                                   "max_rel_dpred": max(rel, default=math.nan),
                                   "n_rel_dpred_gt_1e-9": sum(x > 1e-9 for x in rel)}
    return res


def realization_inputs(out, work, real):
    """Forward csvs with pred_Ek_centroid_k taken from the chosen realization, laid out as expected by
    forward_lambda_combine (fwd_{gauge}_sar) and block40_matched (--block39 / --out)."""
    col = None if real == "legacy" else f"pred_Ek_centroid_k_{real}"
    for cfg in COMMITTED:
        for lab, sub in RUNS.items():
            src = COMMITTED[cfg](lab, sub) if cfg not in MC_CFGS else out / "forward" / cfg / lab
            rows = read_csv(src / "forward_windows.csv")
            for r in rows:
                if col is not None and cfg in MC_CFGS and r["certified"] == "True":
                    r["pred_Ek_centroid_k"] = r[col]
            dst = {"b39_sar": work / "b39" / sub / "fwd_waverider-17m_sar",
                   "b39_fixed72": work / "b39" / sub / "fwd_waverider-17m_fixed",
                   "b40_fixed66": work / "b40" / "forward" / lab}[cfg]
            write_csv(dst / "forward_windows.csv", rows)
    shutil.copyfile(ROOT / B40 / "BLOCK40_WINDOW_PROVENANCE.csv", ROOT / work / "b40" / "BLOCK40_WINDOW_PROVENANCE.csv")


def metrics(work):
    m = {}
    for s in ("grd", "slc"):
        cs = work / "combine" / s
        run(["code/forward_lambda_combine.py", "--run", f"near:{work / 'b39' / s / 'near_k4'}",
             "--run", f"far:{work / 'b39' / s / 'far_k4'}", "--gauge", "waverider-17m=18",
             "--primary-gauge", "waverider-17m", "--forward-template", "fwd_{gauge}_sar",
             "--prefer", "far", "--prefer-min-depth", "19", "--out", cs], quiet=True)
        pp = json.load(open(ROOT / cs / "combined_summary.json"))["paper_peak_block_bootstrap"]
        m[f"b39/{s}"] = {"n": pp["n"], "median": pp["median"], "ci": pp["median_ci95_block_bootstrap"]}
    run(["code/block40_matched.py", "--block39", work / "b39", "--out", work / "b40"], quiet=True)
    st = json.load(open(ROOT / work / "b40" / "BLOCK40_STRATIFIED.json"))["primary_by_band"]
    for k, v in st.items():
        for est in ("contour", "centroid"):
            e = v[est]
            if e.get("n"):
                m[f"b40/{k}/{est}"] = {"n": e["n"], "median": e["median"], "ci": e.get("median_ci95_block_bootstrap")}
    return m


def per_window_spread(out):
    res = {}
    for lab in RUNS:
        rows = [r for r in read_csv(out / "forward" / "b39_sar" / lab / "forward_windows.csv") if r["certified"] == "True"]
        sd, rng_, dq = [], [], []
        def fk(r, c):
            try:
                v = float(r[c]); return v if v > 0 else math.nan
            except (KeyError, ValueError):
                return math.nan
        for r in rows:
            lam = np.array([2 * math.pi / fk(r, f"pred_Ek_centroid_k_mc{i:02d}") for i in range(N_MC)])
            la = 2 * math.pi / fk(r, "pred_Ek_centroid_k_all"); lq = 2 * math.pi / fk(r, "pred_Ek_centroid_k_quantile")
            if not (np.all(np.isfinite(lam)) and np.isfinite(la) and np.isfinite(lq)):
                continue
            sd.append(lam.std(ddof=1) / la); rng_.append((lam.max() - lam.min()) / la); dq.append(lq / la - 1)
        sd, rng_, dq = map(np.array, (sd, rng_, dq))
        res[lab] = {"n": len(rows), "n_finite": int(sd.size), "median_rel_sd": float(np.median(sd)), "p90_rel_sd": float(np.percentile(sd, 90)),
                    "frac_range_gt_5pct": float(np.mean(rng_ > 0.05)),
                    "quantile_vs_all_median": float(np.median(dq)), "quantile_vs_all_max_abs": float(np.max(np.abs(dq)))}
    return res


def summarise(per_real):
    keys = sorted(set().union(*[m.keys() for m in per_real.values()]))
    mc = [r for r in per_real if r.startswith("mc")]
    out = {}
    for k in keys:
        def val(r, what):
            x = per_real[r].get(k)
            if x is None: return math.nan
            return x["median"] if what == "median" else (x["ci"][0] if what == "lo" else x["ci"][1]) if x.get("ci") else math.nan
        ent = {"n": per_real["legacy"].get(k, {}).get("n")}
        for what in ("median", "lo", "hi"):
            v = np.array([val(r, what) for r in mc]) * 100
            ent[what] = {"legacy_pct": 100 * val("legacy", what), "all_pct": 100 * val("all", what),
                         "quantile_pct": 100 * val("quantile", what),
                         "mc_mean_pct": float(np.nanmean(v)), "mc_sd_pp": float(np.nanstd(v, ddof=1)),
                         "mc_min_pct": float(np.nanmin(v)), "mc_max_pct": float(np.nanmax(v))}
        out[k] = ent
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ground-truth", type=Path, default=Path("outputs/ground_truth_s1a_20211028_ext20"))
    ap.add_argument("--out", type=Path, default=Path("duck_frf/Block41_depth_sampling"))
    ap.add_argument("--work", type=Path, default=Path("_tmp/block41_work"))
    ap.add_argument("--phase", choices=("A", "B", "all"), default="all")
    ap.add_argument("--skip-existing", action="store_true")
    a = ap.parse_args(argv)
    rep_path = ROOT / a.out / "BLOCK41_DEPTH_SAMPLING.json"
    rep = json.loads(rep_path.read_text()) if rep_path.exists() else {}
    import numpy, scipy, rasterio
    rep["environment"] = {"python": sys.version, "numpy": numpy.__version__, "scipy": scipy.__version__, "rasterio": rasterio.__version__}
    rep["protocol"] = __doc__.strip()
    if a.phase in ("A", "all"):
        rep["timing_s"] = phase_a(a.out, a.ground_truth, a.skip_existing)
        rep["L_legacy_reproduction"] = legacy_check(a.out)
        rep["per_window_spread_b39_sar"] = per_window_spread(a.out)
        rep_path.parent.mkdir(parents=True, exist_ok=True); rep_path.write_text(json.dumps(rep, indent=2, default=float))
    if a.phase in ("B", "all"):
        per_real = {}
        for real in ["legacy", *[f"mc{i:02d}" for i in range(N_MC)], "all", "quantile"]:
            w = a.work / real
            realization_inputs(a.out, w, real)
            per_real[real] = metrics(w)
            print(real, json.dumps({k: round(100 * v["median"], 2) for k, v in per_real[real].items()}), flush=True)
        rep["per_realization"] = per_real
        rep["summary"] = summarise(per_real)
        rep_path.write_text(json.dumps(rep, indent=2, default=float))
        rows = [{"quantity": k, "stat": what, "n": v["n"], **v[what]} for k, v in rep["summary"].items() for what in ("median", "lo", "hi")]
        write_csv(a.out / "BLOCK41_SUMMARY.csv", rows)
    print(json.dumps({k: rep[k] for k in ("L_legacy_reproduction", "per_window_spread_b39_sar") if k in rep}, indent=1, default=float))
    print("report:", rep_path)


if __name__ == "__main__":
    main()

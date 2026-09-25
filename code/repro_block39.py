"""Reproduce the Block39 primary result in the current environment and compare it with the
committed outputs.

Block39 was produced in the Linux device shell (python 3.10, numpy 2.2, scipy 1.15,
rasterio 1.4, chunked runs); the authoritative environment is .venv-umbra-thesis on Windows
(python 3.13, versions pinned in requirements-thesis.txt). This script re-runs, from the SAFE
products, the four runs that feed the primary result (GRD/SLC x near/far, kmin_factor 4), the
WR17 forward check with the SAR-driven sector, and the combine with WR17 predeclared,
`--prefer far --prefer-min-depth 19`, then compares window by window.

The forward check is forced to --depth-sampling random (the Block39 method; the default became
'all' in Block41). Command lines are rebuilt from the stored run.json args (the history was not recorded); the
rebuilt run.json args must equal the originals except out/parts_from/chunk/finalize, which
is checked first. Outputs go to _tmp/repro_block39 (git-ignored); nothing committed is touched.

Acceptance, declared before running:
  A. argv reconstruction: identical args (excluding out/parts_from/chunk/finalize);
  B. window sets: identical ok/identifiable/certified sets and depth_mean_m equal to 1e-6 m
     (a depth mismatch means a different ground-truth input, not a numerical difference);
  C. wavelengths: >= 99 % of identifiable windows with |dlambda/lambda| <= 1e-6;
  D. headline: paper-peak median and both CI bounds within 0.1 percentage points.
"""
import argparse, csv, json, math, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B39 = Path("duck_frf/Block39_s1_paper_confirm")
SKIP = {"out", "parts_from", "chunk", "finalize"}


def argv_from_args(args):
    argv = [str(args["safe"])]
    for k, v in args.items():
        if k == "safe" or k in SKIP or v is None or v is False:
            continue
        opt = "--" + k.replace("_", "-")
        if v is True:
            argv.append(opt)
        elif isinstance(v, list):
            if v:                                   # empty nargs="*" lists equal the defaults
                argv += [opt, *map(str, v)]
        else:
            argv += [opt, str(v)]
    return argv


def run(cmd):
    print(">", " ".join(map(str, cmd)), flush=True)
    subprocess.run([sys.executable, *map(str, cmd)], cwd=ROOT, check=True)


def rows(path, key=("transect", "distance_m")):
    return {(r[key[0]], float(r[key[1]])): r for r in csv.DictReader(open(ROOT / path))}


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return math.nan


def compare_runs(orig, new):
    a, b = rows(orig / "windows.csv"), rows(new / "windows.csv")
    ok = lambda d: {k for k, r in d.items() if r["status"] == "ok"}
    ide = lambda d: {k for k, r in d.items() if r.get("identifiable") == "True"}
    common = ide(a) & ide(b)
    rel = [abs(fnum(b[k]["wavelength_m"]) / fnum(a[k]["wavelength_m"]) - 1) for k in common]
    rel = [x for x in rel if math.isfinite(x)]
    return {"windows_ok_equal": ok(a) == ok(b), "n_ok": [len(ok(a)), len(ok(b))],
            "identifiable_equal": ide(a) == ide(b), "n_identifiable": [len(ide(a)), len(ide(b))],
            "n_compared": len(rel), "max_rel_dlambda": max(rel, default=math.nan),
            "frac_rel_dlambda_le_1e-6": sum(x <= 1e-6 for x in rel) / len(rel) if rel else math.nan}


def compare_forward(orig, new):
    a, b = rows(orig / "forward_windows.csv"), rows(new / "forward_windows.csv")
    cert = lambda d: {k for k, r in d.items() if r["certified"] == "True"}
    common = cert(a) & cert(b)
    dd = [abs(fnum(a[k]["depth_mean_m"]) - fnum(b[k]["depth_mean_m"])) for k in common]
    return {"certified_equal": cert(a) == cert(b), "n_certified": [len(cert(a)), len(cert(b))],
            "max_abs_ddepth_m": max(dd, default=math.nan)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ground-truth", type=Path, default=Path("outputs/ground_truth_s1a_20211028_ext20"))
    ap.add_argument("--out", type=Path, default=Path("_tmp/repro_block39"))
    ap.add_argument("--sensors", nargs="+", default=["grd", "slc"])
    ap.add_argument("--skip-sar", action="store_true", help="reuse the SAR runs already in --out")
    a = ap.parse_args(argv)
    report = {"environment": {"python": sys.version}, "acceptance": __doc__.split("Acceptance")[1].strip(), "sensors": {}}
    try:
        import numpy, scipy, rasterio, pyproj
        report["environment"].update(numpy=numpy.__version__, scipy=scipy.__version__,
                                     rasterio=rasterio.__version__, pyproj=pyproj.__version__)
    except ImportError as e:
        report["environment"]["import_error"] = str(e)
    for s in a.sensors:
        rep = report["sensors"][s] = {"runs": {}}
        for part in ("near", "far"):
            orig = B39 / s / f"{part}_k4"; new = a.out / s / part
            args = json.load(open(ROOT / orig / "run.json"))["args"]
            if not a.skip_sar:
                run(["code/s1_transect_bathy.py", *argv_from_args(args), "--out", new])
            new_args = json.load(open(ROOT / new / "run.json"))["args"]
            diff = sorted(k for k in set(args) | set(new_args) if k not in SKIP and args.get(k) != new_args.get(k))
            fwd_new = new / "fwd_waverider-17m_sar"
            run(["code/forward_lambda_check.py", "--run", new, "--ground-truth", a.ground_truth,
                 "--reference", "FRF:waverider-17m", "--depth-sampling", "random", "--out", fwd_new])
            rep["runs"][part] = {"A_args_mismatch": diff, **compare_runs(orig, new),
                                 "forward": compare_forward(orig / "fwd_waverider-17m_sar", fwd_new)}
        comb = a.out / s / "combined_wr17"
        run(["code/forward_lambda_combine.py", "--run", f"near:{a.out / s / 'near'}", "--run", f"far:{a.out / s / 'far'}",
             "--gauge", "waverider-17m=18", "--primary-gauge", "waverider-17m", "--forward-template", "fwd_{gauge}_sar",
             "--prefer", "far", "--prefer-min-depth", "19", "--out", comb])
        po = json.load(open(ROOT / B39 / s / "combined_wr17/combined_summary.json"))["paper_peak_block_bootstrap"]
        pn = json.load(open(ROOT / comb / "combined_summary.json"))["paper_peak_block_bootstrap"]
        d = [100 * (pn["median"] - po["median"])] + [100 * (x - y) for x, y in zip(pn["median_ci95_block_bootstrap"], po["median_ci95_block_bootstrap"])]
        rep["headline"] = {"original_pct": [100 * po["median"], *[100 * x for x in po["median_ci95_block_bootstrap"]]],
                           "repro_pct": [100 * pn["median"], *[100 * x for x in pn["median_ci95_block_bootstrap"]]],
                           "n": [po["n"], pn["n"]], "delta_pp": d}
        R = rep["runs"].values()
        rep["verdict"] = {
            "A_args": all(not r["A_args_mismatch"] for r in R),
            "B_window_sets": all(r["windows_ok_equal"] and r["identifiable_equal"] and r["forward"]["certified_equal"]
                                 and r["forward"]["max_abs_ddepth_m"] <= 1e-6 for r in R),
            "C_wavelengths": all(r["frac_rel_dlambda_le_1e-6"] >= 0.99 for r in R),
            "D_headline": all(abs(x) <= 0.1 for x in d)}
    (ROOT / a.out).mkdir(parents=True, exist_ok=True)
    out = ROOT / a.out / "REPRO_BLOCK39.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    for s, rep in report["sensors"].items():
        print(s, "headline %:", rep["headline"], "\n  verdict:", rep["verdict"])
    print("report:", out)


if __name__ == "__main__":
    main()

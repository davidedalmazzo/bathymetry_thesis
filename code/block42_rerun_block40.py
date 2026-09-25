"""Block42 - Block40 re-run with deterministic footprint depths (forward check --depth-sampling all).

Block41 showed that the Block39/40 forward predictions depended on a random 60-depth subsample
drawn by one generator per process, i.e. on how the runs were chunked. The published Block40
numbers are one realization of that Monte Carlo. Since Block41 the default of
forward_lambda_check.py is 'all' (every footprint cell, deterministic).

This script rebuilds the Block40 outputs in a NEW directory (Block40 stays as published):
  - inputs that do not depend on the depth sampling are copied from Block40: configuration,
    source mask/inventory/audit, window provenance and the SLC variance-ladder partial spectra
    (ladder_parts: SAR-only, the prediction is attached only at --finalize);
  - forward passes re-run with --depth-sampling all, for the Block40 configuration (sector 66.34,
    admissible set) AND for the Block39 fixed-72 fallback used by block40_matched, so that no
    row of the new block carries a random subsample;
  - block40_matched, block40_variance_ladder --finalize, block40_sensitivity, block40_figures,
    block40_summary, block40_manifest run unchanged with --out pointing here;
  - BLOCK42_COMPARISON.json lists every numeric leaf of the Block40 JSON outputs that changed,
    plus the Block39 headline with 'all' taken from Block41.

Protocol, sectors, seeds, blocks, admissibility and estimators are exactly those of Block40.
Hard-coded prose in block40_summary.py (e.g. '+6.6/+6.8 %', '-0.8 %') is NOT recomputed; the
comparison file gives the current values.
"""
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B39 = Path("duck_frf/Block39_s1_paper_confirm")
B40 = Path("duck_frf/Block40_stratified_validation")
B41 = Path("duck_frf/Block41_depth_sampling")
RUNS = {"slc_near": "slc/near_k4", "slc_far": "slc/far_k4", "grd_near": "grd/near_k4", "grd_far": "grd/far_k4"}
STATIC = ["BLOCK40_CONFIG.json", "BLOCK40_PROTOCOL.md", "BLOCK40_SOURCE_MASK.tif", "BLOCK40_SOURCE_INVENTORY.csv",
          "BLOCK40_SOURCE_AUDIT.json", "BLOCK40_WINDOW_PROVENANCE.csv", "BLOCK40_WINDOW_PROVENANCE_SUMMARY.json"]
COMPARE = ["BLOCK40_STRATIFIED.json", "BLOCK40_LADDER_SUMMARY.json", "BLOCK40_UNCERTAINTY_BUDGET.json",
           "BLOCK40_SUMMARY.json"]
LADDER_PARTS = 24


def run(cmd):
    print(">", " ".join(map(str, cmd)), flush=True)
    t0 = time.time()
    subprocess.run([sys.executable, *map(str, cmd)], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    return time.time() - t0


def leaves(x, prefix=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from leaves(v, f"{prefix}/{k}" if prefix else str(k))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from leaves(v, f"{prefix}[{i}]")
    elif isinstance(x, (int, float)) and not isinstance(x, bool):
        yield prefix, float(x)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("duck_frf/Block42_block40_depth_all"))
    ap.add_argument("--ground-truth", type=Path, default=Path("outputs/ground_truth_s1a_20211028_ext20"))
    ap.add_argument("--skip-existing", action="store_true", help="do not re-run forward passes already present")
    a = ap.parse_args(argv)
    out = ROOT / a.out; out.mkdir(parents=True, exist_ok=True)
    timing = {}

    for f in STATIC:
        shutil.copyfile(ROOT / B40 / f, out / f)
    (out / "ladder_parts").mkdir(exist_ok=True)
    for i in range(LADDER_PARTS):
        f = f"part_{i}_of_{LADDER_PARTS}.pkl"
        shutil.copyfile(ROOT / B40 / "ladder_parts" / f, out / "ladder_parts" / f)

    prov = a.out / "BLOCK40_WINDOW_PROVENANCE.csv"
    for lab, sub in RUNS.items():
        common = ["code/forward_lambda_check.py", "--run", B39 / sub, "--ground-truth", a.ground_truth,
                  "--reference", "FRF:waverider-17m", "--depth-sampling", "all", "--sector-source", "fixed"]
        jobs = {f"b40_fixed66/{lab}": (a.out / "forward" / lab,
                                       ["--sector-bearing", "66.34", "--admissible-csv", prov, "--admissible-run", lab]),
                f"b39_fixed72/{lab}": (a.out / "b39_fixed72" / sub / "fwd_waverider-17m_fixed", ["--sector-bearing", "72"])}
        for name, (dst, extra) in jobs.items():
            if a.skip_existing and (ROOT / dst / "forward_windows.csv").exists():
                continue
            timing[name] = run([*common, *extra, "--out", dst])

    timing["matched"] = run(["code/block40_matched.py", "--out", a.out, "--block39", a.out / "b39_fixed72"])
    timing["ladder"] = run(["code/block40_variance_ladder.py", "--out", a.out, "--finalize", LADDER_PARTS])
    timing["sensitivity"] = run(["code/block40_sensitivity.py", "--out", a.out, "--ground-truth", a.ground_truth])
    timing["figures"] = run(["code/block40_figures.py", "--out", a.out])
    timing["summary"] = run(["code/block40_summary.py", "--out", a.out])
    timing["manifest"] = run(["code/block40_manifest.py", "--out", a.out])

    comp = {"note": "Block40 (published, random 60-depth subsample) vs Block42 (all footprint cells); "
                    "only leaves whose value changed are listed", "timing_s": timing, "files": {}}
    for f in COMPARE:
        old = dict(leaves(json.loads((ROOT / B40 / f).read_text())))
        new = dict(leaves(json.loads((out / f).read_text())))
        comp["files"][f] = {k: {"block40": old.get(k), "block42": new.get(k),
                                "delta": (new[k] - old[k]) if k in old and k in new else None}
                            for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)}
    b41 = ROOT / B41 / "BLOCK41_DEPTH_SAMPLING.json"
    if b41.exists():
        s = json.loads(b41.read_text())["summary"]
        comp["block39_headline_all_pct"] = {k: {w: {"published": s[k][w]["legacy_pct"], "all": s[k][w]["all_pct"]}
                                                for w in ("median", "lo", "hi")} for k in ("b39/grd", "b39/slc")}
    (out / "BLOCK42_COMPARISON.json").write_text(json.dumps(comp, indent=2, default=float))
    st = json.loads((out / "BLOCK40_STRATIFIED.json").read_text())["primary_by_band"]
    for k, v in st.items():
        c = v["contour"]
        if c.get("n"):
            print(f"{k:16s} n={c['n']:4d}  contour {100 * c['median']:+6.2f} %  CI "
                  f"{100 * c['median_ci95_block_bootstrap'][0]:+6.2f} .. {100 * c['median_ci95_block_bootstrap'][1]:+6.2f}")
    print("comparison:", out / "BLOCK42_COMPARISON.json")


if __name__ == "__main__":
    main()

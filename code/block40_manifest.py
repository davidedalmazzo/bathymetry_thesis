#!/usr/bin/env python
"""Block40 step 7 - summary and reproducibility manifest (inputs, versions, seeds, SHA-256)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha256(path, limit_mb=4096):
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk); n += len(chunk)
            if n > limit_mb * (1 << 20):
                return h.hexdigest() + f" (first {limit_mb} MB)"
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("duck_frf/Block40_stratified_validation"))
    a = ap.parse_args(argv)
    out = (ROOT / a.out) if not a.out.is_absolute() else a.out
    cfg = json.loads((out / "BLOCK40_CONFIG.json").read_text())

    inputs = [cfg["inputs"]["ground_truth"] + "/bathymetry_merged_utm.tif",
              cfg["inputs"]["ground_truth"] + "/bluetopo_bbox.tif",
              cfg["inputs"]["ground_truth"] + "/bluetopo_bbox.tif.provenance.json",
              cfg["inputs"]["ground_truth"] + "/wave_spectra.json",
              cfg["inputs"]["ground_truth"] + "/MERGE_REPORT.json",
              cfg["inputs"]["frf_survey_npz"]]
    for r in cfg["inputs"]["block39_runs"]:
        inputs += [r + "/windows.csv", r + "/run.json"]
    code_files = ["code/block40_source_audit.py", "code/block40_windows.py", "code/block40_matched.py",
                  "code/block40_variance_ladder.py", "code/block40_sensitivity.py", "code/block40_figures.py",
                  "code/block40_manifest.py", "code/forward_lambda_check.py", "code/s1_transect_bathy.py",
                  "code/s1_paper_peak.py", "code/s1_iw_geometry.py", "code/frf_ground_truth.py",
                  "tests/test_block40.py"]
    outputs = sorted([p for p in out.glob("BLOCK40_*")] + [p for p in (out / "figures").glob("*.png")] +
                     [p for p in (out / "forward").rglob("forward_summary.json")])

    def entries(paths):
        rows = []
        for p in paths:
            f = (ROOT / p) if not Path(p).is_absolute() else Path(p)
            if not f.exists() or f.is_dir():
                continue
            rows.append({"path": str(f.relative_to(ROOT)), "bytes": f.stat().st_size, "sha256": sha256(f)})
        return rows

    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True).stdout
    except Exception:
        commit, dirty = "", ""
    import scipy, rasterio, matplotlib
    manifest = {
        "block": "Block40", "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_at_run": commit, "git_dirty_entries": len([x for x in dirty.splitlines() if x.strip()]),
        "protocol": "BLOCK40_PROTOCOL.md", "config": "BLOCK40_CONFIG.json",
        "seeds": {"block_bootstrap": cfg["statistics"]["seed"], "monte_carlo": 0,
                  "bootstrap_resamples": cfg["statistics"]["bootstrap_resamples"]},
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "numpy": np.__version__, "scipy": scipy.__version__, "rasterio": rasterio.__version__,
                        "matplotlib": matplotlib.__version__,
                        "note": "the authoritative suite is .venv-umbra-thesis on Windows; this run used the Linux "
                                "device shell, which cannot execute the Windows interpreter"},
        "inputs": entries(inputs), "code": entries(code_files), "outputs": entries(outputs)}
    (out / "BLOCK40_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"manifest: {len(manifest['inputs'])} inputs, {len(manifest['code'])} code files, {len(manifest['outputs'])} outputs")


if __name__ == "__main__":
    main()

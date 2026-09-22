"""Re-run the bathymetry merge of an existing ground-truth directory, offline.

Uses only what is already on disk (BlueTopo/CUDEM tiles + provenance, the cached
FRF survey DEM npz, the cached legacy grids), so it spends no FRF network budget.
Use it when the merge logic changes -- e.g. the water-level policy of
`frf_ground_truth.water_level` -- and the ground truth must be regenerated.

    python code/rebuild_merged_bathymetry.py --dir outputs/ground_truth_s1a_20211028_ext20 \
        --bbox -75.79 36.15 -75.56 36.26 --survey-npz outputs/ground_truth_s1a_20211028/frf_survey_dem.npz \
        --frf-year 2021 --water-level-policy qc_only \
        --legacy-grid "_cache/legacy/nhatt,-0.128,USGS OFR2011-1015 nhatt (MSL->NAVD88 via NOAA 8651370),2001" \
        --legacy-grid "_cache/legacy/vims_2002,-0.623,USGS/VIMS LARC 2002 (MLW->NAVD88 via NOAA 8651370),2002"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "code"))
import coastal_dem
import frf_ground_truth as gt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True, help="existing ground-truth output directory")
    ap.add_argument("--bbox", nargs=4, type=float, required=True)
    ap.add_argument("--grid-res", type=float, default=10.0)
    ap.add_argument("--survey-npz", type=Path, help="cached FRF survey DEM (frf_survey_dem.npz)")
    ap.add_argument("--frf-year", type=float)
    ap.add_argument("--legacy-grid", action="append", default=[])
    ap.add_argument("--water-level-policy", choices=("qc_only", "preliminary"), default="qc_only")
    ap.add_argument("--water-level-json", type=Path,
                    help="GROUND_TRUTH.json holding observations.water_level_navd88 (default: --dir/GROUND_TRUTH.json)")
    a = ap.parse_args(argv)
    d = (ROOT / a.dir) if not a.dir.is_absolute() else a.dir
    wl_src = a.water_level_json or (d / "GROUND_TRUTH.json")
    wl = None
    if Path(wl_src).exists():
        wl = json.loads(Path(wl_src).read_text()).get("observations", {}).get("water_level_navd88")
    eta, eta_status = gt.water_level(wl, a.water_level_policy)
    survey = None
    if a.survey_npz:
        p = (ROOT / a.survey_npz) if not a.survey_npz.is_absolute() else a.survey_npz
        survey = {k: v for k, v in np.load(p).items()}
    bt = d / "bluetopo_bbox.tif"; cu = d / "cudem_bbox_navd88.tif"
    prov = json.loads((d / "bluetopo_bbox.tif.provenance.json").read_text()) if bt.exists() else None
    legacy = [coastal_dem.legacy_spec(x, ROOT / "_cache/legacy") for x in a.legacy_grid]
    rep = gt.merged_bathymetry(a.bbox, survey, a.grid_res, d / "bathymetry_merged_utm.tif", eta, legacy=legacy,
                               bluetopo_tif=bt if bt.exists() else None, bluetopo_prov=prov,
                               cudem_tif=cu if cu.exists() else None, frf_year=a.frf_year)
    rep["event_water_level_used_m"] = eta
    rep["event_water_level_status"] = eta_status
    rep["rebuilt_from"] = {"dir": str(d), "survey_npz": str(a.survey_npz) if a.survey_npz else None,
                           "legacy_grid": a.legacy_grid}
    (d / "MERGE_REPORT.json").write_text(json.dumps(rep, indent=2, default=float))
    gt.figure(d / "bathymetry_merged_utm.tif", d / "bathymetry_merged.png")
    print(json.dumps({k: rep[k] for k in rep if k != "sources"}, indent=1, default=float))


if __name__ == "__main__":
    main()

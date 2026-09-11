import csv
import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Vandenberg" / "results" / "analysis_block7"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_block7_geolocation_support_and_formed_arrays():
    support = load("BLOCK7_ROI_SUPPORT_PLAN.json")
    assert math.isclose(support["geolocation_surface"]["projection_HAE_m"], -36.376, abs_tol=1e-12)
    assert support["candidate_rois"][-1]["L_parallel_m"] == 1440
    assert all(r["sicd_inside_image"] and r["maximum_elevation_NAVD88_m"] < -2 for r in support["candidate_rois"])
    manifest = load_from_path(ROOT / "Vandenberg" / "results" / "block7_enlarged_nominal_sea_surface" / "BLOCK7_ENLARGED_NOMINAL_MANIFEST.json")
    assert manifest["source_sicd_shape_rows_cols"] == [13310, 107800]
    assert "all 107800" in manifest["anti_bias_rule"]
    for path in manifest["files"]:
        array = np.load(path, mmap_mode="r")
        assert list(array.shape) == manifest["output_shape"]
        assert array.dtype == np.float32
        assert np.isfinite(array).all()


def load_from_path(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_block7_science_gate_and_frozen_guardrails():
    spatial = load("BLOCK7_SPATIAL_CONVERGENCE.json")
    assert spatial["summary_nearshore_anchored_by_size"][-1]["L_parallel_m"] == 1440
    assert 120 < spatial["summary_nearshore_anchored_by_size"][-1]["lambda_median_m"] < 140
    assert spatial["homogeneity"]["alongshore_lambda_cv"] > 0.10
    bathy = load("BLOCK7_BATHYMETRY_STATS.json")
    assert bathy["dataset"]["vertical_reference"].startswith("NAVD88")
    assert 10 <= bathy["original_roi_statistics"]["depth_median_m"] <= 12
    residual = load("BLOCK7_FROZEN_RESIDUAL_DIAGNOSTIC.json")
    assert math.isclose(residual["frozen_period_s"], 17.902230457045317, abs_tol=1e-12)
    assert math.isclose(residual["frozen_slope_rad_per_s"], -0.3509722055168202, abs_tol=1e-14)
    gate = load("BLOCK7_INTERNAL_DISPERSION_GATE.json")
    assert gate["gate_passed"] is False
    assert gate["omega_k_test"]["performed"] is False
    assert gate["dwell_sweep_performed"] is False
    assert gate["definitive_bathymetric_inversion_performed"] is False
    with (OUT / "BLOCK7_SPATIAL_CONVERGENCE.csv").open(newline="", encoding="utf-8") as stream:
        assert sum(1 for _ in csv.DictReader(stream)) == 117

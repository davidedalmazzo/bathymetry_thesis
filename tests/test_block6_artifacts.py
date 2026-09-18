from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'umbra/Vandenberg' / "results" / "analysis_block6"


def load_summary() -> dict:
    return json.loads((OUTPUT / "BLOCK6_PHASE_SLOPE_SUMMARY.json").read_text(encoding="utf-8"))


def test_frozen_value_is_reproduced_without_retuning() -> None:
    result = load_summary()
    assert result["frozen_inputs"]["T_SAR_s"] == 17.902230457045317
    assert result["frozen_inputs"]["slope_rad_per_s"] == -0.3509722055168202
    assert result["frozen_inputs"]["NDBC_comparison_changed"] is False
    assert result["frozen_peak_reproduction"]["absolute_difference_from_frozen_rad_per_s"] == 0.0
    assert result["guardrails"]["T_SAR_retuned"] is False


def test_csv_contains_required_fields_and_only_coherent_rows() -> None:
    with (OUTPUT / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        rows = list(csv.DictReader(stream))
    required = {
        "kx_range_cycles_per_m",
        "ky_azimuth_cycles_per_m",
        "k_magnitude_cycles_per_m",
        "wavelength_m",
        "angle_from_local_range_axis_deg",
        "angle_from_local_azimuth_axis_deg",
        "slope_rad_per_s",
        "slope_selected_standard_error_rad_per_s",
        "fit_r_squared",
        "minimum_adjacent_coherence",
        "minimum_independent_anchor_coherence",
    }
    assert len(rows) == 68
    assert required.issubset(rows[0])
    assert min(float(row["minimum_adjacent_coherence"]) for row in rows) >= 0.70
    assert min(float(row["minimum_independent_anchor_coherence"]) for row in rows) >= 0.25
    assert min(float(row["wavelength_m"]) for row in rows) >= 40.0
    assert max(float(row["wavelength_m"]) for row in rows) <= 500.0


def test_npz_masks_and_conjugate_antisymmetry() -> None:
    with np.load(OUTPUT / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.npz") as data:
        assert int(np.sum(data["map_mask"])) == 68
        assert int(np.sum(data["high_quality_mask"])) == 48
        assert int(np.sum(data["primary_lobe_mask"])) == 22
        slope = data["slope_rad_per_s"]
        mask = data["map_mask"] & data["map_mask"][::-1, ::-1]
        assert np.max(np.abs(slope + slope[::-1, ::-1])[mask]) < 2e-15


def test_orientation_result_does_not_treat_bias_as_constant() -> None:
    result = load_summary()["orientation_analysis"]
    bounds = result["primary_lobe_ranges"]["bias_vs_h13_33_dispersion_rad_per_s"]
    assert bounds[1] - bounds[0] > 0.30
    model = result["standardized_multivariable_models"][
        "bias13_from_k_magnitude_and_abs_k_azimuth"
    ]
    k_effect = abs(model["coefficient_per_predictor_1sd"]["k_magnitude_cycles_per_m"])
    az_effect = abs(model["coefficient_per_predictor_1sd"]["abs_k_azimuth_cycles_per_m"])
    assert az_effect < 0.01 * k_effect


def test_theory_scaling_and_duration_guardrails() -> None:
    result = load_summary()
    geometry = result["theory"]["umbra_geometry_order_of_magnitude"]
    diagnostic = result["theory"]["can_0_120_rad_per_s_be_reached"]
    assert math.isclose(geometry["R_over_V_s"], 79.71058144543186, abs_tol=1e-12)
    assert 0.35 < geometry["ATBD_core_dimensionless_shift_parameter_context_only"] < 0.40
    assert 0.40 < geometry["finite_depth_velocity_bunching_parameter_context_only"] < 0.50
    assert math.isclose(
        diagnostic["required_extra_rate_at_frozen_peak_rad_per_s"],
        2.0 * math.pi / 13.33 - 0.3509722055168202,
        abs_tol=1e-14,
    )
    assert diagnostic["uniform_advection_speed_along_k_required_m_per_s"] > 2.4
    assert result["duration_guardrail"]["SICD_processed_aperture_duration_s"] == 18.068061721230308
    assert result["duration_guardrail"]["CPHD_available_dwell_s"] == 22.540812513364376
    assert result["guardrails"]["dwell_sweep_performed"] is False
    assert result["guardrails"]["bathymetric_inversion_performed"] is False


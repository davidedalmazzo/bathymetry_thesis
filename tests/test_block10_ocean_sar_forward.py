from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from umbra_sar.ocean_sar_forward import (
    LinearWaveSurface,
    RadarGeometry,
    physical_components,
)
from umbra_sar.synthetic_validation import finite_depth_omega


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'umbra/validazione/Block10_validation' / "results"


def load_summary() -> dict:
    return json.loads(
        (RESULTS / "BLOCK10_FORWARD_MODEL_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )


def test_truth_is_finite_depth_and_not_calibrated_to_vandenberg() -> None:
    for angle_case in ("range_0deg", "vandenberg_like_22deg"):
        components = physical_components(angle_case)
        assert len(components) == 6
        assert min(item.wavelength_m for item in components) >= 79.0
        assert max(item.wavelength_m for item in components) <= 193.0
        for item in components:
            assert np.isclose(item.steepness_ka, 0.012)
            assert np.isclose(item.amplitude_m * item.k_rad_per_m, 0.012)
            assert np.isclose(
                item.omega_rad_per_s,
                finite_depth_omega(item.k_rad_per_m, 10.0),
                atol=1e-14,
            )
            assert not np.isclose(item.period_s, 17.902230457, atol=0.05)
    angled = physical_components("vandenberg_like_22deg")
    assert all(20.0 <= item.angle_from_range_deg <= 25.0 for item in angled)


def test_real_geometry_sign_and_range_over_velocity_are_explicit() -> None:
    radar = RadarGeometry()
    assert np.isclose(radar.incidence_angle_deg, 21.842925232944808)
    assert np.isclose(radar.range_over_velocity_s, 79.71058144543186)
    assert radar.azimuth_mapping_sign == 1
    assert radar.los_radial_velocity_positive == "toward_sensor"
    assert np.isclose(
        (radar.range_bearing_toward_sensor_deg + 180.0) % 360.0,
        radar.grid_row_positive_bearing_deg,
        atol=1e-6,
    )


def test_linear_orbital_velocity_and_los_derivative_are_self_consistent() -> None:
    surface = LinearWaveSurface(
        physical_components("vandenberg_like_22deg"), RadarGeometry()
    )
    time = 7.125
    step = 0.05
    fields = surface.fields(time)
    # Periodic centered difference in physical azimuth verifies the analytic
    # partial u_LOS / partial y used in the mapping Jacobian.
    numerical = (
        np.roll(fields["u_los_m_per_s"], -1, axis=1)
        - np.roll(fields["u_los_m_per_s"], 1, axis=1)
    ) / (2.0 * 8.0)
    # At 8 m sampling the centered finite difference has the expected O((k dy)^2)
    # truncation error; this tolerance is still below 0.3% of the derivative RMS.
    assert np.sqrt(
        np.mean((numerical - fields["du_los_dy_per_s"]) ** 2)
    ) < 5e-5
    # Surface elevation time derivative equals vertical velocity in the
    # linear kinematic boundary condition.
    before = surface.fields(time - step)["eta_m"]
    after = surface.fields(time + step)["eta_m"]
    eta_t = (after - before) / (2.0 * step)
    assert np.sqrt(np.mean((eta_t - fields["w_vertical_m_per_s"]) ** 2)) < 2e-4


def test_zero_bunching_reduces_combined_model_to_rar() -> None:
    surface = LinearWaveSurface(
        physical_components("vandenberg_like_22deg"), RadarGeometry()
    )
    images, diagnostics = surface.instantaneous_models(
        8.0, beta_scale=0.0, model_names=("M1", "M4")
    )
    assert np.allclose(images["M1"], images["M4"], atol=2e-6)
    assert diagnostics["maximum_abs_azimuth_displacement_m"] == 0.0
    assert diagnostics["minimum_mapping_jacobian"] == 1.0
    assert diagnostics["fold_fraction_jacobian_le_zero"] == 0.0


def test_range_travelling_case_is_invariant_to_azimuth_bunching() -> None:
    surface = LinearWaveSurface(physical_components("range_0deg"), RadarGeometry())
    images, _ = surface.instantaneous_models(
        8.0, beta_scale=1.0, model_names=("M0", "M2", "M3")
    )
    assert np.max(np.abs(images["M0"] - images["M2"])) < 2e-5
    assert np.max(np.abs(images["M0"] - images["M3"])) < 2e-5


def test_m0_to_m4_preserve_dispersion_and_strength_sweep_does_not_collapse() -> None:
    summary = load_summary()
    assert summary["first_mechanism_destroying_dispersion"] is None
    assert summary["simple_model_explains_Vandenberg_flattening"] is False
    for angle_case in summary["nominal_models"].values():
        for model in angle_case.values():
            assert model["valid_component_count"] == 6
            assert model["quasi_constant"] is False
            assert model["constantness_ratio_std_hat_over_std_truth"] > 0.95
    for row in summary["bunching_strength_sweep"]:
        assert row["valid_component_count"] == 6
        assert row["quasi_constant"] is False
        assert row["constantness_ratio"] > 0.95


def test_short_look_prediction_was_frozen_and_gate_failed() -> None:
    prediction = json.loads(
        (RESULTS / "BLOCK10_FROZEN_SHORT_LOOK_PREDICTION.json").read_text(
            encoding="utf-8"
        )
    )
    assert prediction["frozen_before_any_new_Vandenberg_short_look_processing"]
    assert prediction["criterion"]["declared_before_synthetic_results"]
    assert prediction["prediction_triggered"] is False
    assert (
        prediction["synthetic_result"]["increase_m_per_s"]
        < prediction["synthetic_result"]["required_increase_m_per_s"]
    )
    summary = load_summary()
    assert summary["conditional_real_short_look_test"]["performed"] is False


def test_block10_manifest_preserves_blocks_4_to_9() -> None:
    manifest = json.loads(
        (RESULTS / "BLOCK10_MANIFEST.json").read_text(encoding="utf-8")
    )
    assert manifest["guards_unchanged"] is True
    assert manifest["guard_hashes_before"] == manifest["guard_hashes_after"]
    assert manifest["new_Vandenberg_processing_performed"] is False
    summary = load_summary()
    assert not any(summary["guardrails"].values())

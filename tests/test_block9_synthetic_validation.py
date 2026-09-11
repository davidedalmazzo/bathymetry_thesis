from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from umbra_sar.synthetic_validation import (
    deduplicate_conjugate_offsets,
    finite_depth_omega,
    fit_linear_law,
    frozen_truth_components,
    run_full_subaperture_surrogate,
    run_oracle_case,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "Block9_validation" / "results"


def synthetic_times() -> np.ndarray:
    with np.load(
        ROOT
        / "Vandenberg"
        / "results"
        / "analysis_block4"
        / "nearshore_sliding_spectrum_crops.npz"
    ) as archive:
        return np.asarray(archive["time_s"], dtype=np.float64)


@lru_cache(maxsize=1)
def oracle_dispersion() -> dict:
    components = frozen_truth_components()
    return run_oracle_case(
        components,
        synthetic_times(),
        [item.omega_rad_per_s for item in components],
        case_name="pytest_dispersion",
    )


@lru_cache(maxsize=1)
def negative_controls() -> dict[str, dict]:
    components = frozen_truth_components()
    k = np.asarray([item.k_rad_per_m for item in components])
    laws = {
        "static": np.zeros(k.size),
        "constant": np.full(k.size, 0.53),
        "linear": 0.20 + 5.0 * k,
    }
    return {
        name: run_oracle_case(
            components,
            synthetic_times(),
            omega,
            case_name=f"pytest_{name}",
        )
        for name, omega in laws.items()
    }


@lru_cache(maxsize=1)
def full_surrogate() -> dict:
    return run_full_subaperture_surrogate(frozen_truth_components())


def test_frozen_truth_is_grid_resolved_finite_depth_dispersion() -> None:
    components = frozen_truth_components()
    assert len(components) == 6
    modes = [item.range_fft_mode for item in components]
    assert len(set(modes)) == len(modes)
    # No quadratic sideband difference lands on another injected mode.
    differences = {
        abs(first - second)
        for index, first in enumerate(modes)
        for second in modes[index + 1 :]
    }
    assert not differences.intersection(modes)
    assert min(item.wavelength_m for item in components) >= 80.0
    assert max(item.wavelength_m for item in components) <= 200.0
    for item in components:
        assert np.isclose(
            item.omega_rad_per_s,
            finite_depth_omega(item.k_rad_per_m, 10.0),
            atol=1e-14,
        )
        assert not np.isclose(item.period_s, 17.902230457, atol=0.05)
        assert not np.isclose(item.period_s, 13.33, atol=0.05)


def test_oracle_recovers_nonlinear_dispersion_without_constant_collapse() -> None:
    result = oracle_dispersion()
    truth = np.asarray(
        [item["omega_truth_rad_per_s"] for item in result["stage_tracking"]]
    )
    recovered = np.asarray(
        [item["omega_final_rad_per_s"] for item in result["stage_tracking"]]
    )
    assert result["all_bins_valid"]
    assert result["max_abs_error_rad_per_s"] <= 0.005
    assert np.ptp(recovered) > 0.25
    constant_rmse = np.sqrt(np.mean((truth - np.mean(truth)) ** 2))
    assert result["rmse_rad_per_s"] < constant_rmse / 50.0


def test_negative_controls_remain_distinguishable() -> None:
    components = frozen_truth_components()
    k = np.asarray([item.k_rad_per_m for item in components])
    results = negative_controls()
    static = np.asarray(
        [item["omega_final_rad_per_s"] for item in results["static"]["stage_tracking"]]
    )
    constant = np.asarray(
        [item["omega_final_rad_per_s"] for item in results["constant"]["stage_tracking"]]
    )
    linear = np.asarray(
        [item["omega_final_rad_per_s"] for item in results["linear"]["stage_tracking"]]
    )
    assert np.max(np.abs(static)) <= 1e-10
    assert np.max(np.abs(constant - 0.53)) <= 1e-4
    fit = fit_linear_law(k, linear)
    assert abs(fit["intercept_rad_per_s"] - 0.20) <= 0.002
    assert abs(fit["slope_m_per_s"] - 5.0) <= 0.05
    assert np.ptp(static) < 1e-10
    assert np.ptp(constant) < 1e-4
    assert np.ptp(linear) > 0.20


def test_conjugate_deduplication_keeps_one_canonical_half_plane() -> None:
    offsets = [(43, 0), (-43, 0), (0, 9), (0, -9), (5, 7), (-5, -7)]
    unique = deduplicate_conjugate_offsets(offsets)
    assert unique == [(0, 9), (5, 7), (43, 0)]
    summary = json.loads(
        (RESULTS / "BLOCK9_SYNTHETIC_VALIDATION_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    conjugate = summary["synthetic_conjugate_test"]
    assert conjugate["rows_before_deduplication"] == 12
    assert conjugate["independent_half_plane_rows"] == 6
    assert conjugate["maximum_abs_signed_slope_sum_rad_per_s"] <= 1e-9


def test_full_complex_subaperture_chain_preserves_dispersion() -> None:
    result = full_surrogate()
    assert result["sicd_sign_surrogate"] == -1
    assert result["image_to_Doppler_transform"] == "fft"
    assert result["Doppler_to_image_transform"] == "ifft"
    assert np.isclose(
        result["Doppler_slice_time_mapping"]["overlap_fraction"], 0.8
    )
    assert result["roundtrip_relative_max_error"] <= 1e-12
    assert result["all_bins_valid"]
    assert result["max_abs_error_rad_per_s"] <= 0.005
    for row in result["stage_tracking"]:
        assert abs(
            row["omega_after_sublook_formation_rad_per_s"]
            - row["omega_truth_rad_per_s"]
        ) <= 1e-12


def test_constant_slope_collapse_regressions_all_pass() -> None:
    summary = json.loads(
        (RESULTS / "BLOCK9_SYNTHETIC_VALIDATION_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert all(summary["constant_slope_collapse_audit"].values())
    assert all(summary["acceptance"]["assertions"].values())
    assert summary["acceptance"]["decision"] == "AUTHORIZED TO RETURN TO REAL DATA"


def test_block9_preserved_frozen_guards() -> None:
    manifest = json.loads(
        (RESULTS / "BLOCK9_MANIFEST.json").read_text(encoding="utf-8")
    )
    assert manifest["guards_unchanged"] is True
    assert manifest["guard_hashes_before"] == manifest["guard_hashes_after"]
    summary = json.loads(
        (RESULTS / "BLOCK9_SYNTHETIC_VALIDATION_SUMMARY.json").read_text(
            encoding="utf-8"
        )
    )
    assert not any(summary["guardrails"].values())

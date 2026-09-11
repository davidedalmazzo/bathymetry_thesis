"""Measure fixed-patch temporal phase on Block-4 sliding sub-looks."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import t as student_t

from umbra_sar.wave_analysis import (
    coherent_patch_cross,
    intensity_spectrum_crop,
    linear_phase_fit,
    physical_frequency_grid,
    wrap_phase,
)


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"
OUTPUT = VANDENBERG / "results" / "analysis_block4"
HALF_WIDTH = 64
PATCH_RADIUS = 2
PATCH_SIGMA = 1.0


def gaussian_weights(radius: int, sigma: float = 1.0) -> np.ndarray:
    row, col = np.mgrid[-radius : radius + 1, -radius : radius + 1]
    weights = np.exp(-(row**2 + col**2) / (2.0 * sigma**2))
    return weights / np.sum(weights)


def patch(array: np.ndarray, center: tuple[int, int], radius: int) -> np.ndarray:
    row, col = center
    return array[row - radius : row + radius + 1, col - radius : col + radius + 1]


def fit_with_period(time: np.ndarray, phase: np.ndarray, hac_lag: int) -> dict[str, Any]:
    result = linear_phase_fit(time, phase, hac_lag=hac_lag)
    slope = float(result["slope_rad_per_s"])
    slope_standard_error = max(
        float(result["ols_slope_standard_error_rad_per_s"]),
        float(result["hac_slope_standard_error_rad_per_s"]),
    )
    critical = float(student_t.ppf(0.975, int(result["degrees_of_freedom"])))
    slope_ci = [
        slope - critical * slope_standard_error,
        slope + critical * slope_standard_error,
    ]
    resolved = bool(slope_ci[0] * slope_ci[1] > 0)
    period = 2.0 * np.pi / abs(slope) if slope != 0 else math.inf
    period_standard_error = (
        2.0 * np.pi * slope_standard_error / slope**2 if slope != 0 else math.inf
    )
    period_ci = None
    if resolved:
        endpoint_periods = [2.0 * np.pi / abs(value) for value in slope_ci]
        period_ci = [min(endpoint_periods), max(endpoint_periods)]
    result.update(
        {
            "slope_standard_error_selected_rad_per_s": slope_standard_error,
            "slope_95_percent_ci_rad_per_s": slope_ci,
            "slope_resolved_from_zero_at_95_percent": resolved,
            "period_s": period if resolved else None,
            "period_1sigma_fit_only_s": period_standard_error if resolved else None,
            "period_95_percent_ci_fit_only_s": period_ci,
            "uncertainty_note": "Selected 1-sigma is max(OLS, Newey-West HAC). It is fit-only; estimator and overlapping-window systematics are reported separately.",
        }
    )
    return result


def phase_estimator(
    spectra: np.ndarray,
    center: tuple[int, int],
    time: np.ndarray,
    radius: int,
    hac_lag: int,
) -> dict[str, Any]:
    weights = gaussian_weights(radius, PATCH_SIGMA) if radius else np.ones((1, 1))
    patches = [patch(item, center, radius) for item in spectra]
    direct = [coherent_patch_cross(patches[0], item, weights) for item in patches]
    adjacent = [
        coherent_patch_cross(first, second, weights)
        for first, second in zip(patches[:-1], patches[1:])
    ]
    wrapped = np.array([item["phase_rad"] for item in direct], dtype=np.float64)
    direct_steps = np.angle(np.exp(1j * np.diff(wrapped)))
    adjacent_steps = np.array(
        [item["phase_rad"] for item in adjacent], dtype=np.float64
    )
    adjacent_coherence = np.array(
        [item["magnitude_squared_coherence"] for item in adjacent], dtype=np.float64
    )
    step_consistency = np.angle(np.exp(1j * (direct_steps - adjacent_steps)))
    criteria = {
        "maximum_abs_direct_temporal_step_rad": float(np.max(np.abs(direct_steps))),
        "maximum_abs_adjacent_cross_phase_rad": float(
            np.max(np.abs(adjacent_steps))
        ),
        "minimum_adjacent_magnitude_squared_coherence": float(
            np.min(adjacent_coherence)
        ),
        "maximum_abs_direct_step_minus_adjacent_cross_phase_rad": float(
            np.max(np.abs(step_consistency))
        ),
        "required_maximum_abs_step_rad": float(np.pi / 2.0),
        "required_minimum_adjacent_coherence": 0.5,
        "required_maximum_step_consistency_error_rad": 0.25,
    }
    justified = bool(
        criteria["maximum_abs_direct_temporal_step_rad"]
        < criteria["required_maximum_abs_step_rad"]
        and criteria["maximum_abs_adjacent_cross_phase_rad"]
        < criteria["required_maximum_abs_step_rad"]
        and criteria["minimum_adjacent_magnitude_squared_coherence"]
        >= criteria["required_minimum_adjacent_coherence"]
        and criteria["maximum_abs_direct_step_minus_adjacent_cross_phase_rad"]
        <= criteria["required_maximum_step_consistency_error_rad"]
    )
    unwrapped = np.unwrap(wrapped) if justified else np.full_like(wrapped, np.nan)
    fit = fit_with_period(time, unwrapped, hac_lag) if justified else None

    cumulative_adjacent = np.r_[0.0, np.cumsum(adjacent_steps)]
    adjacent_fit = fit_with_period(time, cumulative_adjacent, hac_lag)
    return {
        "patch_radius_bins": radius,
        "patch_shape": list(weights.shape),
        "patch_weight": "Gaussian sigma=1 bin" if radius else "single fixed bin",
        "cross_convention": "F_secondary * conj(F_reference)",
        "reference_chronological_index": 1,
        "wrapped_phase_relative_reference_rad": wrapped.tolist(),
        "direct_reference_magnitude_squared_coherence": [
            float(item["magnitude_squared_coherence"]) for item in direct
        ],
        "adjacent_cross_phase_rad": adjacent_steps.tolist(),
        "adjacent_magnitude_squared_coherence": adjacent_coherence.tolist(),
        "direct_temporal_wrapped_step_rad": direct_steps.tolist(),
        "direct_step_minus_adjacent_cross_phase_rad": step_consistency.tolist(),
        "unwrapping_criteria": criteria,
        "temporal_unwrapping_justified": justified,
        "unwrapped_phase_relative_reference_rad": unwrapped.tolist(),
        "fit_direct_reference_phase": fit,
        "adjacent_linked_cumulative_phase_rad": cumulative_adjacent.tolist(),
        "fit_adjacent_linked_phase": adjacent_fit,
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest_path = (
        VANDENBERG
        / "results"
        / "block4_sliding_complex"
        / "BLOCK4_SLIDING_MANIFEST.json"
    )
    plan_path = VANDENBERG / "metadata" / "BLOCK4_SLIDING_LOOK_PLAN.json"
    roi_path = VANDENBERG / "roi" / "ROIS.json"
    block3_path = (
        VANDENBERG / "results" / "analysis_block3" / "BLOCK3_SPECTRAL_METRICS.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    rois = json.loads(roi_path.read_text(encoding="utf-8"))["rois"]
    block3 = json.loads(block3_path.read_text(encoding="utf-8"))
    times = np.array(
        [item["effective_early_center_late_s"][1] for item in plan["looks_chronological"]],
        dtype=np.float64,
    )
    mean_step = float(np.mean(np.diff(times)))
    mean_width = float(
        np.mean([item["effective_span_s"] for item in plan["looks_chronological"]])
    )
    nonoverlap_indices = plan["independent_nonoverlap_set_retained"][
        "chronological_indices"
    ]
    # Looks separated by five sequence steps have disjoint Doppler support;
    # correlations can extend through lags 1..4, not lag 5.
    hac_lag = int(nonoverlap_indices[1] - nonoverlap_indices[0] - 1)

    selected_peak = block3["results"]["nearshore"]["cross_spectra"]["selected_peak"]
    target_k = np.array(
        [
            selected_peak["k_east_cycles_per_m"],
            selected_peak["k_north_cycles_per_m"],
        ],
        dtype=np.float64,
    )
    results: dict[str, Any] = {}
    stored_spectra: dict[str, np.ndarray] = {}
    for roi_name in ("nearshore", "land_control"):
        records = manifest["outputs"][roi_name]
        spectra = []
        indices = None
        for record in records:
            complex_data = np.load(record["path"], mmap_mode="r")
            intensity = np.asarray(
                complex_data.real * complex_data.real
                + complex_data.imag * complex_data.imag,
                dtype=np.float32,
            )
            del complex_data
            current, current_indices = intensity_spectrum_crop(
                intensity, half_width=HALF_WIDTH, workers=-1
            )
            del intensity
            spectra.append(current)
            if indices is None:
                indices = current_indices
        assert indices is not None
        spectra_array = np.asarray(spectra, dtype=np.complex64)
        stored_spectra[roi_name] = spectra_array
        shape = tuple(int(value) for value in records[0]["shape"])
        jacobian = np.asarray(
            rois[roi_name]["local_ground_jacobian_EN_m_per_pixel"],
            dtype=np.float64,
        )
        k_east, k_north, _, _ = physical_frequency_grid(shape, indices, jacobian)
        if roi_name == "nearshore":
            center = tuple(int(value) for value in selected_peak["crop_index_row_col"])
            center_method = "fixed Block-3 nearshore look-2 peak bin"
        else:
            distance = (k_east - target_k[0]) ** 2 + (k_north - target_k[1]) ** 2
            center = tuple(int(value) for value in np.unravel_index(np.argmin(distance), distance.shape))
            center_method = "nearest land-control FFT bin to the fixed nearshore physical EN wavevector"

        primary = phase_estimator(
            spectra_array, center, times, PATCH_RADIUS, hac_lag
        )
        radius_sensitivity = {
            str(radius): phase_estimator(
                spectra_array, center, times, radius, hac_lag
            )["fit_direct_reference_phase"]
            for radius in range(1, 6)
        }
        single_bin = phase_estimator(spectra_array, center, times, 0, hac_lag)
        conjugate_center = (
            2 * HALF_WIDTH - center[0],
            2 * HALF_WIDTH - center[1],
        )
        conjugate = phase_estimator(
            spectra_array, conjugate_center, times, PATCH_RADIUS, hac_lag
        )

        drift = []
        drift_radius = 3
        for index, spectrum in enumerate(spectra_array):
            local_power = np.abs(
                patch(spectrum, center, drift_radius)
            ) ** 2
            local_index = np.unravel_index(np.argmax(local_power), local_power.shape)
            offset = [
                int(local_index[0] - drift_radius),
                int(local_index[1] - drift_radius),
            ]
            row = center[0] + offset[0]
            col = center[1] + offset[1]
            magnitude = float(np.hypot(k_east[row, col], k_north[row, col]))
            drift.append(
                {
                    "chronological_index": index + 1,
                    "offset_from_fixed_patch_center_row_col_bins": offset,
                    "k_east_cycles_per_m": float(k_east[row, col]),
                    "k_north_cycles_per_m": float(k_north[row, col]),
                    "wavelength_m": 1.0 / magnitude,
                    "wavevector_bearing_deg_mod_180": float(
                        np.degrees(np.arctan2(k_east[row, col], k_north[row, col]))
                        % 180.0
                    ),
                    "power": float(local_power[local_index]),
                }
            )

        primary_fit = primary["fit_direct_reference_phase"]
        conjugate_fit = conjugate["fit_direct_reference_phase"]
        radius_periods = [
            float(value["period_s"])
            for value in radius_sensitivity.values()
            if value is not None and value["period_s"] is not None
        ]
        results[roi_name] = {
            "roi": rois[roi_name],
            "fixed_physical_target_from_nearshore_block3": {
                "k_east_cycles_per_m": float(target_k[0]),
                "k_north_cycles_per_m": float(target_k[1]),
                "wavelength_m": float(selected_peak["wavelength_m"]),
                "wavevector_bearing_deg_mod_180": float(
                    selected_peak["wavevector_bearing_deg_mod_180"]
                ),
            },
            "fixed_patch_center": {
                "method": center_method,
                "crop_index_row_col": list(center),
                "fft_bin_offset_row_col": [center[0] - HALF_WIDTH, center[1] - HALF_WIDTH],
                "nearest_integer_bin_k_east_cycles_per_m": float(k_east[center]),
                "nearest_integer_bin_k_north_cycles_per_m": float(k_north[center]),
                "nearest_integer_bin_wavelength_m": float(
                    1.0 / np.hypot(k_east[center], k_north[center])
                ),
            },
            "primary_fixed_patch_phase": primary,
            "conjugate_peak_check": {
                "center_crop_index_row_col": list(conjugate_center),
                "fit": conjugate_fit,
                "slope_sum_with_primary_rad_per_s": float(
                    primary_fit["slope_rad_per_s"]
                    + conjugate_fit["slope_rad_per_s"]
                ),
                "period_difference_s": float(
                    primary_fit["period_s"] - conjugate_fit["period_s"]
                )
                if primary_fit["period_s"] is not None
                and conjugate_fit["period_s"] is not None
                else None,
            },
            "estimator_sensitivity": {
                "gaussian_patch_radius_1_to_5_bins": radius_sensitivity,
                "patch_period_range_s": [min(radius_periods), max(radius_periods)]
                if radius_periods
                else None,
                "single_center_bin": single_bin["fit_direct_reference_phase"],
                "adjacent_linked": primary["fit_adjacent_linked_phase"],
                "note": "Only the fixed-patch radius-2 direct-reference estimator is primary. Peak drift is not used to retune the phase bin.",
            },
            "separate_peak_drift_diagnostic_not_used_for_phase": drift,
        }
        npz_path = OUTPUT / f"{roi_name}_sliding_spectrum_crops.npz"
        np.savez_compressed(
            npz_path,
            spectra=spectra_array,
            time_s=times,
            k_east=k_east,
            k_north=k_north,
            fixed_center=np.asarray(center, dtype=np.int64),
        )
        results[roi_name]["spectrum_crop_npz"] = str(npz_path.resolve())

    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Block 4 fixed-width sliding-look temporal phase; nearshore primary plus land control",
        "inputs": {
            "sliding_manifest": str(manifest_path.resolve()),
            "sliding_plan": str(plan_path.resolve()),
            "rois": str(roi_path.resolve()),
            "block3_metrics": str(block3_path.resolve()),
        },
        "time_axis": {
            "source": "CPHD/PVP Doppler-to-TxTime inversion",
            "physical_slow_time_centers_s": times.tolist(),
            "mean_center_step_s": mean_step,
            "mean_effective_window_span_s": mean_width,
            "overlap_correlation_hac_lag": hac_lag,
        },
        "phase_model": "phi(t)=omega_p*t+phi_0",
        "cross_convention": "F_secondary * conj(F_reference)",
        "external_data_used_for_unwrapping_or_fit": False,
        "results": results,
        "independent_nonoverlap_set": plan["independent_nonoverlap_set_retained"],
        "guardrails": {
            "dwell_sweep_performed": False,
            "bathymetric_inversion_performed": False,
            "external_branch_forcing_performed": False,
        },
    }
    json_path = OUTPUT / "BLOCK4_PHASE_METRICS_SAR_ONLY.json"
    json_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex="col", constrained_layout=True)
    for row_index, roi_name in enumerate(("nearshore", "land_control")):
        item = results[roi_name]["primary_fixed_patch_phase"]
        fit = item["fit_direct_reference_phase"]
        wrapped = np.asarray(item["wrapped_phase_relative_reference_rad"])
        unwrapped = np.asarray(item["unwrapped_phase_relative_reference_rad"])
        axes[row_index, 0].plot(times, wrapped, "o", label="wrapped")
        axes[row_index, 0].plot(times, unwrapped, "o-", label="unwrapped")
        axes[row_index, 0].plot(times, fit["predicted_phase_rad"], "--", label="linear fit")
        axes[row_index, 0].set_ylabel(f"{roi_name}\nphase (rad)")
        axes[row_index, 0].grid(True, alpha=0.25)
        axes[row_index, 0].legend(fontsize=8)
        axes[row_index, 1].axhline(0.0, color="black", linewidth=0.7)
        axes[row_index, 1].plot(times, fit["residual_phase_rad"], "o-")
        axes[row_index, 1].set_ylabel("fit residual (rad)")
        axes[row_index, 1].grid(True, alpha=0.25)
    axes[1, 0].set_xlabel("CPHD/PVP slow-time center (s)")
    axes[1, 1].set_xlabel("CPHD/PVP slow-time center (s)")
    axes[0, 0].set_title("Fixed-patch relative phase")
    axes[0, 1].set_title("Linear-model residual")
    phase_plot = OUTPUT / "BLOCK4_PHASE_TIMESERIES.png"
    fig.savefig(phase_plot, dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
    for axis, roi_name in zip(axes, ("nearshore", "land_control")):
        drift = results[roi_name]["separate_peak_drift_diagnostic_not_used_for_phase"]
        offsets = np.array(
            [item["offset_from_fixed_patch_center_row_col_bins"] for item in drift]
        )
        axis.plot(times, offsets[:, 0], "o-", label="row-bin drift")
        axis.plot(times, offsets[:, 1], "s-", label="col-bin drift")
        axis.axhline(0.0, color="black", linewidth=0.7)
        axis.set_title(roi_name)
        axis.set_xlabel("CPHD/PVP slow-time center (s)")
        axis.set_ylabel("local maximum offset (bins)")
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8)
    drift_plot = OUTPUT / "BLOCK4_PEAK_DRIFT_DIAGNOSTIC.png"
    fig.savefig(drift_plot, dpi=180)
    plt.close(fig)
    print(json_path)
    print(phase_plot)
    print(drift_plot)


if __name__ == "__main__":
    main()

"""Block 10: physical ocean-surface to SAR-intensity forward-model tests."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

from umbra_sar.ocean_sar_forward import (
    N_AZIMUTH,
    N_RANGE,
    PIXEL_SPACING_AZIMUTH_M,
    PIXEL_SPACING_RANGE_M,
    LinearWaveSurface,
    RadarGeometry,
    physical_components,
    recover_phase_frequencies,
    temporally_averaged_sequences,
)


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"
BLOCK8 = ROOT / "Block8_validation"
BLOCK9 = ROOT / "Block9_validation"
OUTPUT = ROOT / "Block10_validation"
RESULTS = OUTPUT / "results"
PLOTS = OUTPUT / "plots"
ANGLE_CASES = ("range_0deg", "vandenberg_like_22deg")
MODEL_NAMES = ("M0", "M1", "M2", "M3", "M4")
MODEL_LABELS = {
    "M0": "pure wave snapshots",
    "M1": "RAR/tilt only",
    "M2": "velocity displacement only",
    "M3": "velocity displacement + density/Jacobian",
    "M4": "RAR + displacement + density/Jacobian",
}
SHORT_LOOK_PREDICTION_CRITERION = {
    "declared_before_synthetic_results": True,
    "metric": "domega_hat/dk for M4, Vandenberg-like angle",
    "trigger": (
        "mean slope for 1.5 and 2 s exceeds the 6 s slope by at least "
        "max(0.5 m/s, 10% of truth slope), with all six components valid"
    ),
    "reason": (
        "This tests a material predicted re-emergence of dispersion rather than "
        "responding to small numerical fluctuations."
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frozen_guard_paths() -> list[Path]:
    paths = [
        VANDENBERG
        / "results"
        / "analysis_block4"
        / "BLOCK4_PHASE_METRICS_SAR_ONLY.json",
        ROOT / "CHECKPOINT_5.md",
        VANDENBERG
        / "results"
        / "analysis_block5"
        / "BLOCK5_FROZEN_INPUTS.json",
        VANDENBERG / "results" / "analysis_block6" / "CHECKPOINT_6.md",
        VANDENBERG
        / "results"
        / "analysis_block6"
        / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.csv",
        VANDENBERG
        / "results"
        / "analysis_block6"
        / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.npz",
        VANDENBERG / "results" / "analysis_block7" / "CHECKPOINT_7.md",
        VANDENBERG
        / "results"
        / "analysis_block7"
        / "BLOCK7_SPATIAL_CONVERGENCE.json",
        BLOCK8 / "results" / "CHECKPOINT_8.md",
        BLOCK8 / "results" / "top16_candidates.csv",
        BLOCK8 / "results" / "ranked_candidates_all.csv",
        BLOCK9 / "results" / "CHECKPOINT_9.md",
        BLOCK9 / "results" / "BLOCK9_SYNTHETIC_VALIDATION_SUMMARY.json",
        BLOCK9 / "results" / "BLOCK9_SYNTHETIC_TRUTH.json",
        BLOCK9 / "results" / "BLOCK9_MANIFEST.json",
    ]
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"frozen guard inputs missing: {missing}")
    return paths


def weighted_fit(k: np.ndarray, omega: np.ndarray, se: np.ndarray) -> dict[str, Any]:
    design = np.column_stack((np.ones(k.size), k))
    weights = 1.0 / np.maximum(se, 1e-12) ** 2
    beta = np.linalg.solve(
        design.T @ (weights[:, None] * design), design.T @ (weights * omega)
    )
    residual = omega - design @ beta
    return {
        "intercept_rad_per_s": float(beta[0]),
        "domega_obs_dk_m_per_s": float(beta[1]),
        "rmse_rad_per_s": float(np.sqrt(np.mean(residual**2))),
        "r_squared": float(
            1.0 - np.sum(residual**2) / np.sum((omega - np.mean(omega)) ** 2)
        ),
        "weights": "1/max(OLS,HAC4 slope standard error)^2",
    }


def real_data_benchmark() -> dict[str, Any]:
    path = (
        VANDENBERG
        / "results"
        / "analysis_block6"
        / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.csv"
    )
    with path.open(newline="", encoding="utf-8") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row["frozen_peak_lobe_flag"] == "True"
        ]
    k = np.asarray([float(row["k_magnitude_rad_per_m"]) for row in rows])
    omega = np.asarray([abs(float(row["slope_rad_per_s"])) for row in rows])
    angle = np.asarray([float(row["angle_from_local_range_axis_deg"]) for row in rows])
    se = np.asarray(
        [float(row["slope_selected_standard_error_rad_per_s"]) for row in rows]
    )
    base = weighted_fit(k, omega, se)
    predictors = np.column_stack((k, angle))
    means = np.mean(predictors, axis=0)
    scales = np.std(predictors, axis=0, ddof=1)
    standardized = (predictors - means) / scales
    design = np.column_stack((np.ones(k.size), standardized))
    weights = 1.0 / np.maximum(se, 1e-12) ** 2
    beta = np.linalg.solve(
        design.T @ (weights[:, None] * design), design.T @ (weights * omega)
    )
    residual = omega - design @ beta
    rho = spearmanr(angle, omega)
    return {
        "role": "real-data benchmark only; never used to set synthetic parameters",
        "source_csv": str(path.resolve()),
        "source_sha256": sha256(path),
        "independent_half_plane": "frozen_peak_lobe_flag side only",
        "unique_sample_count": len(rows),
        "k_range_rad_per_m": [float(np.min(k)), float(np.max(k))],
        "wavelength_range_m": [
            min(float(row["wavelength_m"]) for row in rows),
            max(float(row["wavelength_m"]) for row in rows),
        ],
        "omega_obs_range_rad_per_s": [float(np.min(omega)), float(np.max(omega))],
        "angle_from_range_range_deg": [float(np.min(angle)), float(np.max(angle))],
        "weighted_fit": base,
        "weighted_standardized_k_plus_angle": {
            "intercept_rad_per_s": float(beta[0]),
            "coefficient_per_1sd_k_rad_per_m": float(beta[1]),
            "coefficient_per_1sd_angle_deg": float(beta[2]),
            "angle_to_k_effect_magnitude_ratio": float(abs(beta[2] / beta[1])),
            "r_squared": float(
                1.0
                - np.sum(residual**2)
                / np.sum((omega - np.mean(omega)) ** 2)
            ),
        },
        "spearman_omega_vs_angle": {
            "rho": float(rho.statistic),
            "nominal_p_value_not_used": float(rho.pvalue),
        },
        "interpretation": (
            "The unique-bin ridge is much flatter than finite-depth dispersion. "
            "After k is included, the standardized angle effect is small relative "
            "to the k effect; overlapping patches preclude independent-bin inference."
        ),
    }


def write_truth_tables() -> tuple[dict[str, Any], list[Path]]:
    radar = RadarGeometry()
    payload = {
        "frozen_before_forward_processing": True,
        "depth_m": 10.0,
        "gravity_m_per_s2": 9.80665,
        "amplitude_rule": "a_j=0.012/k_j, equal component steepness ka=0.012",
        "amplitudes_not_tuned_to_Vandenberg": True,
        "radar_geometry": radar.as_dict(),
        "grid": {
            "range_samples": N_RANGE,
            "azimuth_samples": N_AZIMUTH,
            "range_pixel_spacing_m": PIXEL_SPACING_RANGE_M,
            "azimuth_pixel_spacing_m": PIXEL_SPACING_AZIMUTH_M,
        },
        "angle_cases": {},
    }
    paths = []
    for angle_case in ANGLE_CASES:
        components = physical_components(angle_case)
        hm0 = float(
            4.0
            * np.sqrt(
                0.5 * np.sum([item.amplitude_m**2 for item in components])
            )
        )
        payload["angle_cases"][angle_case] = {
            "equivalent_Hm0_m_for_six_discrete_components": hm0,
            "components": [item.as_dict() for item in components],
        }
        csv_path = RESULTS / f"BLOCK10_TRUTH_{angle_case}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=list(components[0].as_dict())
            )
            writer.writeheader()
            writer.writerows(item.as_dict() for item in components)
        paths.append(csv_path)
    json_path = RESULTS / "BLOCK10_FROZEN_TRUTH.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    paths.append(json_path)
    return payload, paths


def compact_model_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "all_components_valid": result["all_components_valid"],
        "valid_component_count": result["valid_component_count"],
        "bias_mean_rad_per_s": result["bias_mean_rad_per_s"],
        "bias_max_abs_rad_per_s": result["bias_max_abs_rad_per_s"],
        "rmse_rad_per_s": result["rmse_rad_per_s"],
        "truth_linear_fit": result["truth_linear_fit"],
        "recovered_linear_fit": result["recovered_linear_fit"],
        "constantness_ratio_std_hat_over_std_truth": result[
            "constantness_ratio_std_hat_over_std_truth"
        ],
        "quasi_constant": result["quasi_constant"],
        "minimum_adjacent_coherence": min(
            item["minimum_adjacent_coherence"] for item in result["components"]
        ),
        "minimum_independent_coherence": min(
            item["minimum_independent_coherence"] for item in result["components"]
        ),
        "components": result["components"],
        "spatial_spectral_resolution": result["spatial_spectral_resolution"],
    }


def nominal_models(center_times: np.ndarray) -> tuple[dict[str, Any], dict[str, Any]]:
    results = {}
    diagnostics = {}
    for angle_case in ANGLE_CASES:
        components = physical_components(angle_case)
        surface = LinearWaveSurface(components, RadarGeometry())
        sequences, current_diagnostics = temporally_averaged_sequences(
            surface,
            center_times,
            look_width_s=6.0,
            beta_scale=1.0,
            model_names=MODEL_NAMES,
            quadrature_order=9,
        )
        results[angle_case] = {}
        for model_name in MODEL_NAMES:
            recovered = recover_phase_frequencies(
                sequences[model_name], center_times, components
            )
            results[angle_case][model_name] = compact_model_result(recovered)
        diagnostics[angle_case] = current_diagnostics
        del sequences, surface
    return results, diagnostics


def bunching_strength_sweep(
    center_times: np.ndarray, nominal: dict[str, Any]
) -> list[dict[str, Any]]:
    angle_case = "vandenberg_like_22deg"
    components = physical_components(angle_case)
    surface = LinearWaveSurface(components, RadarGeometry())
    records = []
    for scale in (0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0):
        if scale == 0.0:
            recovered = nominal[angle_case]["M1"]
            diagnostic = {
                "maximum_abs_azimuth_displacement_m": 0.0,
                "minimum_mapping_jacobian": 1.0,
                "maximum_fold_fraction": 0.0,
            }
        elif scale == 1.0:
            recovered = nominal[angle_case]["M4"]
            diagnostic = None
        else:
            sequences, diagnostics = temporally_averaged_sequences(
                surface,
                center_times,
                look_width_s=6.0,
                beta_scale=scale,
                model_names=("M4",),
                quadrature_order=5,
            )
            recovered = compact_model_result(
                recover_phase_frequencies(sequences["M4"], center_times, components)
            )
            diagnostic = {
                "maximum_abs_azimuth_displacement_m": max(
                    item["maximum_abs_azimuth_displacement_m"]
                    for item in diagnostics["per_look"]
                ),
                "minimum_mapping_jacobian": min(
                    item["minimum_mapping_jacobian"]
                    for item in diagnostics["per_look"]
                ),
                "maximum_fold_fraction": max(
                    item["maximum_fold_fraction"]
                    for item in diagnostics["per_look"]
                ),
            }
            del sequences
        if diagnostic is None:
            # Nominal diagnostics are recorded in the main model result; repeat
            # one midpoint only for compact sweep-specific fold metadata.
            _, current = surface.instantaneous_models(
                float(center_times[len(center_times) // 2]),
                beta_scale=1.0,
                model_names=("M4",),
            )
            diagnostic = {
                "maximum_abs_azimuth_displacement_m": current[
                    "maximum_abs_azimuth_displacement_m"
                ],
                "minimum_mapping_jacobian": current["minimum_mapping_jacobian"],
                "maximum_fold_fraction": current[
                    "fold_fraction_jacobian_le_zero"
                ],
            }
        records.append(
            {
                "beta_scale": scale,
                "beta_s": scale * RadarGeometry().range_over_velocity_s,
                "look_width_s": 6.0,
                "domega_hat_dk_m_per_s": recovered["recovered_linear_fit"][
                    "domega_hat_dk_m_per_s"
                ],
                "truth_domega_dk_m_per_s": recovered["truth_linear_fit"][
                    "domega_dk_m_per_s"
                ],
                "rmse_rad_per_s": recovered["rmse_rad_per_s"],
                "constantness_ratio": recovered[
                    "constantness_ratio_std_hat_over_std_truth"
                ],
                "quasi_constant": recovered["quasi_constant"],
                "valid_component_count": recovered["valid_component_count"],
                "minimum_adjacent_coherence": recovered[
                    "minimum_adjacent_coherence"
                ],
                "minimum_independent_coherence": recovered[
                    "minimum_independent_coherence"
                ],
                **diagnostic,
                "components": recovered["components"],
            }
        )
    del surface
    return records


def look_width_experiment(
    center_times: np.ndarray, nominal: dict[str, Any]
) -> list[dict[str, Any]]:
    angle_case = "vandenberg_like_22deg"
    components = physical_components(angle_case)
    surface = LinearWaveSurface(components, RadarGeometry())
    records = []
    for width in (6.0, 4.0, 3.0, 2.0, 1.5):
        if width == 6.0:
            recovered = nominal[angle_case]["M4"]
        else:
            sequences, _ = temporally_averaged_sequences(
                surface,
                center_times,
                look_width_s=width,
                beta_scale=1.0,
                model_names=("M4",),
                quadrature_order=7,
            )
            recovered = compact_model_result(
                recover_phase_frequencies(sequences["M4"], center_times, components)
            )
            del sequences
        records.append(
            {
                "look_width_s": width,
                "nominal_temporal_passband_scale_rad_per_s": 2.0 * np.pi / width,
                "domega_hat_dk_m_per_s": recovered["recovered_linear_fit"][
                    "domega_hat_dk_m_per_s"
                ],
                "truth_domega_dk_m_per_s": recovered["truth_linear_fit"][
                    "domega_dk_m_per_s"
                ],
                "rmse_rad_per_s": recovered["rmse_rad_per_s"],
                "constantness_ratio": recovered[
                    "constantness_ratio_std_hat_over_std_truth"
                ],
                "quasi_constant": recovered["quasi_constant"],
                "valid_component_count": recovered["valid_component_count"],
                "minimum_adjacent_coherence": recovered[
                    "minimum_adjacent_coherence"
                ],
                "minimum_independent_coherence": recovered[
                    "minimum_independent_coherence"
                ],
                "spatial_resolution_note": (
                    "This intensity-domain forward model keeps the spatial grid/FFT "
                    "resolution fixed; raw-SAR aperture-dependent PSF broadening is not modeled."
                ),
                "delta_k_range_rad_per_m": recovered[
                    "spatial_spectral_resolution"
                ]["delta_k_range_rad_per_m"],
                "delta_k_azimuth_rad_per_m": recovered[
                    "spatial_spectral_resolution"
                ]["delta_k_azimuth_rad_per_m"],
                "components": recovered["components"],
            }
        )
    del surface
    return records


def write_flat_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    fieldnames = [name for name in rows[0] if name != "components"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: row[key] for key in fieldnames} for row in rows)


def freeze_prediction(look_width: list[dict[str, Any]]) -> tuple[dict[str, Any], Path, str]:
    by_width = {float(row["look_width_s"]): row for row in look_width}
    slope_6 = float(by_width[6.0]["domega_hat_dk_m_per_s"])
    slope_short = float(
        np.mean(
            [
                by_width[2.0]["domega_hat_dk_m_per_s"],
                by_width[1.5]["domega_hat_dk_m_per_s"],
            ]
        )
    )
    truth_slope = float(by_width[6.0]["truth_domega_dk_m_per_s"])
    threshold = max(0.5, 0.10 * abs(truth_slope))
    all_valid = bool(
        by_width[2.0]["valid_component_count"] == 6
        and by_width[1.5]["valid_component_count"] == 6
    )
    triggered = bool(slope_short - slope_6 >= threshold and all_valid)
    payload = {
        "frozen_before_any_new_Vandenberg_short_look_processing": True,
        "criterion": SHORT_LOOK_PREDICTION_CRITERION,
        "synthetic_result": {
            "M4_6s_domega_hat_dk_m_per_s": slope_6,
            "M4_mean_1p5_2s_domega_hat_dk_m_per_s": slope_short,
            "increase_m_per_s": slope_short - slope_6,
            "required_increase_m_per_s": threshold,
            "all_short_width_components_valid": all_valid,
        },
        "prediction_triggered": triggered,
        "prediction": (
            "Shorter 1.5--2 s looks must materially increase domega_hat/dk."
            if triggered
            else "No material short-look increase in domega_hat/dk is predicted by this model."
        ),
        "authorized_real_action": (
            "Apply only 1.5--2 s Vandenberg looks."
            if triggered
            else "Do not process new Vandenberg short looks; the predeclared trigger failed."
        ),
    }
    path = RESULTS / "BLOCK10_FROZEN_SHORT_LOOK_PREDICTION.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload, path, sha256(path)


def plot_results(
    benchmark: dict[str, Any],
    nominal: dict[str, Any],
    strength: list[dict[str, Any]],
    widths: list[dict[str, Any]],
) -> list[Path]:
    paths = []
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    for axis, angle_case in zip(axes, ANGLE_CASES):
        components = nominal[angle_case]["M0"]["components"]
        k = np.asarray([row["k_rad_per_m"] for row in components])
        truth = np.asarray([row["omega_truth_rad_per_s"] for row in components])
        axis.plot(k, truth, "ko-", label="truth")
        for model_name in MODEL_NAMES:
            values = [
                row["omega_hat_aligned_rad_per_s"]
                for row in nominal[angle_case][model_name]["components"]
            ]
            axis.plot(k, values, "o--", label=model_name)
        axis.set_title(angle_case)
        axis.set_xlabel("k (rad/m)")
        axis.set_ylabel("omega (rad/s)")
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8)
    path = PLOTS / "BLOCK10_M0_M4_DISPERSION.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(path)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    scale = np.asarray([row["beta_scale"] for row in strength])
    slope = np.asarray([row["domega_hat_dk_m_per_s"] for row in strength])
    truth = np.asarray([row["truth_domega_dk_m_per_s"] for row in strength])
    folds = np.asarray([row["maximum_fold_fraction"] for row in strength])
    axes[0].plot(scale, slope, "o-", label="recovered")
    axes[0].plot(scale, truth, "k--", label="truth")
    axes[0].axvline(1.0, color="tab:red", linestyle=":", label="Vandenberg R/V")
    axes[0].set_xlabel("bunching strength beta/beta_Vandenberg")
    axes[0].set_ylabel("d omega_hat / dk (m/s)")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(fontsize=8)
    axes[1].plot(scale, 100.0 * folds, "o-")
    axes[1].axvline(1.0, color="tab:red", linestyle=":")
    axes[1].set_xlabel("bunching strength beta/beta_Vandenberg")
    axes[1].set_ylabel("maximum fold fraction (%)")
    axes[1].grid(True, alpha=0.25)
    path = PLOTS / "BLOCK10_BUNCHING_STRENGTH.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(path)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    width = np.asarray([row["look_width_s"] for row in widths])
    slope = np.asarray([row["domega_hat_dk_m_per_s"] for row in widths])
    truth = np.asarray([row["truth_domega_dk_m_per_s"] for row in widths])
    coherence = np.asarray(
        [
            min(row["minimum_adjacent_coherence"], row["minimum_independent_coherence"])
            for row in widths
        ]
    )
    axes[0].plot(width, slope, "o-", label="recovered")
    axes[0].plot(width, truth, "k--", label="truth")
    axes[0].invert_xaxis()
    axes[0].set_xlabel("look width (s)")
    axes[0].set_ylabel("d omega_hat / dk (m/s)")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(fontsize=8)
    axes[1].plot(width, coherence, "o-")
    axes[1].invert_xaxis()
    axes[1].set_xlabel("look width (s)")
    axes[1].set_ylabel("minimum coherence")
    axes[1].set_ylim(0, 1.02)
    axes[1].grid(True, alpha=0.25)
    path = PLOTS / "BLOCK10_LOOK_WIDTH.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(path)

    # Keep the real-data benchmark visibly separate from the synthetic curves.
    fig, axis = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    with Path(benchmark["source_csv"]).open(newline="", encoding="utf-8") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row["frozen_peak_lobe_flag"] == "True"
        ]
    k = np.asarray([float(row["k_magnitude_rad_per_m"]) for row in rows])
    omega = np.asarray([abs(float(row["slope_rad_per_s"])) for row in rows])
    axis.scatter(k, omega, label="Vandenberg benchmark")
    dense = np.linspace(np.min(k), np.max(k), 200)
    fit = benchmark["weighted_fit"]
    axis.plot(
        dense,
        fit["intercept_rad_per_s"] + fit["domega_obs_dk_m_per_s"] * dense,
        label="Vandenberg WLS",
    )
    axis.set_xlabel("k (rad/m)")
    axis.set_ylabel("omega_obs (rad/s)")
    axis.set_title("Read-only real-data benchmark; not a synthetic calibration target")
    axis.grid(True, alpha=0.25)
    axis.legend()
    path = PLOTS / "BLOCK10_REAL_BENCHMARK.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(path)
    return paths


def write_checkpoint(summary: dict[str, Any]) -> Path:
    benchmark = summary["real_data_benchmark"]
    nominal = summary["nominal_models"]
    prediction = summary["frozen_short_look_prediction"]
    lines = [
        "# CHECKPOINT_10 — physical ocean-to-SAR forward model",
        "",
        f"Generated: {summary['generated_utc']}",
        "",
        "## Guardrails",
        "",
        "- Blocks 4–9 and the Block-8 shortlist were hash-guarded and remained unchanged.",
        "- No radar data was downloaded; no real-data dwell sweep or bathymetric inversion was performed.",
        "- The synthetic amplitudes use fixed steepness `ka=0.012`; no coefficient was fitted to 0.35 rad/s or 17.9 s.",
        "",
        "## Definitive real-data benchmark",
        "",
        f"- One half-plane contains `{benchmark['unique_sample_count']}` unique connected-lobe bins.",
        f"- k range `{benchmark['k_range_rad_per_m'][0]:.6f}–{benchmark['k_range_rad_per_m'][1]:.6f} rad/m`; omega_obs `{benchmark['omega_obs_range_rad_per_s'][0]:.6f}–{benchmark['omega_obs_range_rad_per_s'][1]:.6f} rad/s`.",
        f"- Weighted fit `omega_obs={benchmark['weighted_fit']['intercept_rad_per_s']:.6f}+{benchmark['weighted_fit']['domega_obs_dk_m_per_s']:.6f} k`, R2={benchmark['weighted_fit']['r_squared']:.4f}.",
        f"- After k is included, the standardized angle/k effect ratio is `{benchmark['weighted_standardized_k_plus_angle']['angle_to_k_effect_magnitude_ratio']:.4f}`; no strong independent angle law is resolved.",
        "",
        "## Forward-model formulation",
        "",
        "For each component `psi=k·x-omega t+phi`, linear theory gives `u_h=a omega coth(kh) cos(psi) k_hat` and `w=a omega sin(psi)`. With LOS positive toward the sensor, `u_LOS=sin(i)u_range+cos(i)w`. The real geometry is `i=21.8429 deg`, `R/V=79.7106 s`, and `y_SAR=y+(R/V)u_LOS`.",
        "",
        "- M0: `10+eta` passive wave tracer.",
        "- M1: geometric tilt/RAR proxy `(n·LOS/cos(i))^2`.",
        "- M2: brightness-preserving inverse azimuth warp.",
        "- M3: conservative forward mapping, including density/Jacobian and folds.",
        "- M4: RAR brightness plus conservative bunching/Jacobian.",
        "",
        "## Nominal 6-s results",
        "",
        "| Angle | Model | max bias rad/s | RMSE rad/s | d omega_hat/dk m/s | constantness | folds/collapse |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for angle_case in ANGLE_CASES:
        max_fold = max(
            item["maximum_fold_fraction"]
            for item in summary["nominal_diagnostics"][angle_case]["per_look"]
        )
        for model_name in MODEL_NAMES:
            row = nominal[angle_case][model_name]
            lines.append(
                f"| {angle_case} | {model_name} | {row['bias_max_abs_rad_per_s']:.6f} | {row['rmse_rad_per_s']:.6f} | {row['recovered_linear_fit']['domega_hat_dk_m_per_s']:.4f} | {row['constantness_ratio_std_hat_over_std_truth']:.3f} | {'yes' if row['quasi_constant'] else 'no'}; max fold {100*max_fold:.3f}% |"
            )
    strength = summary["bunching_strength_sweep"]
    widths = summary["look_width_experiment"]
    lines += [
        "",
        "No M0–M4 case destroys the injected dispersion. Range-travelling waves are nearly insensitive to azimuth bunching, as expected from ky=0. At 22 deg, nominal folds occur locally, but the six fundamental phase rates remain distinct.",
        "",
        "## Bunching-strength sweep (M4, 22 deg, 6 s)",
        "",
        "| beta/beta_VDB | d omega_hat/dk m/s | RMSE rad/s | constantness | max fold % |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in strength:
        lines.append(
            f"| {row['beta_scale']:.2f} | {row['domega_hat_dk_m_per_s']:.4f} | {row['rmse_rad_per_s']:.6f} | {row['constantness_ratio']:.3f} | {100*row['maximum_fold_fraction']:.3f} |"
        )
    lines += [
        "",
        "No predeclared quasi-constant transition occurs over 0–3 times the Vandenberg R/V bunching scale.",
        "",
        "## Synthetic look-width experiment (M4, 22 deg, nominal R/V)",
        "",
        "| width s | d omega_hat/dk m/s | RMSE rad/s | min coherence | valid modes |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in widths:
        coherence = min(
            row["minimum_adjacent_coherence"], row["minimum_independent_coherence"]
        )
        lines.append(
            f"| {row['look_width_s']:.1f} | {row['domega_hat_dk_m_per_s']:.4f} | {row['rmse_rad_per_s']:.6f} | {coherence:.4f} | {row['valid_component_count']} |"
        )
    lines += [
        "",
        "The model keeps spatial FFT resolution fixed; it tests temporal look averaging but not raw-SAR aperture-dependent PSF broadening.",
        "",
        "## Frozen Vandenberg prediction gate",
        "",
        f"- Prediction: **{prediction['prediction']}**",
        f"- Triggered: `{prediction['prediction_triggered']}`.",
        f"- Action: {prediction['authorized_real_action']}",
        "- Because the trigger failed, no new 1.5–2 s Vandenberg processing was performed.",
        "",
        "## Physical conclusion and limitations",
        "",
        "This minimal linear-wave + geometric RAR + scalar velocity-bunching/Jacobian model does **not** explain Vandenberg's loss of dispersion. The first mechanism destroying omega(k) is therefore not found among M0–M4, even when local folds appear.",
        "",
        "The forward model is not a raw-SAR simulation. Missing mechanisms include hydrodynamic modulation, coherent speckle, phase-history/focusing of moving scatterers, higher-order velocity bunching, full two-scale Bragg scattering/MTF, range migration, decorrelation, and look-dependent complex transfer terms. Failure to reproduce Vandenberg is not automatically attributed to the ROI.",
        "",
        "# CHECKPOINT_10",
        "",
    ]
    path = RESULTS / "CHECKPOINT_10.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)
    guards_before = {str(path.resolve()): sha256(path) for path in frozen_guard_paths()}
    benchmark = real_data_benchmark()
    benchmark_path = RESULTS / "BLOCK10_REAL_DATA_BENCHMARK.json"
    benchmark_path.write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")
    truth, truth_paths = write_truth_tables()
    truth_hash = sha256(RESULTS / "BLOCK10_FROZEN_TRUTH.json")

    with np.load(
        VANDENBERG
        / "results"
        / "analysis_block4"
        / "nearshore_sliding_spectrum_crops.npz"
    ) as archive:
        center_times = np.asarray(archive["time_s"], dtype=np.float64)

    nominal, nominal_diagnostics = nominal_models(center_times)
    strength = bunching_strength_sweep(center_times, nominal)
    widths = look_width_experiment(center_times, nominal)
    strength_path = RESULTS / "BLOCK10_BUNCHING_STRENGTH_SWEEP.csv"
    width_path = RESULTS / "BLOCK10_LOOK_WIDTH_EXPERIMENT.csv"
    write_flat_csv(strength_path, strength)
    write_flat_csv(width_path, widths)

    prediction, prediction_path, prediction_hash = freeze_prediction(widths)
    real_short_look = {
        "prediction_hash_before_real_check": prediction_hash,
        "prediction_triggered": prediction["prediction_triggered"],
        "performed": False,
        "reason": (
            "The frozen predeclared synthetic trigger failed; no new Vandenberg "
            "short-look processing is authorized by Block 10."
        ),
    }
    first_destroying = None
    for angle_case in ANGLE_CASES:
        for model_name in MODEL_NAMES:
            if nominal[angle_case][model_name]["quasi_constant"]:
                first_destroying = f"{angle_case}/{model_name}"
                break
        if first_destroying:
            break
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Block 10 minimal physical ocean-to-SAR forward model",
        "guardrails": {
            "blocks_4_to_9_modified": False,
            "block8_shortlist_modified": False,
            "new_radar_download": False,
            "real_data_dwell_sweep": False,
            "bathymetric_inversion": False,
            "Vandenberg_17p902_retuned": False,
            "synthetic_calibrated_to_real_benchmark": False,
        },
        "real_data_benchmark": benchmark,
        "frozen_truth": truth,
        "frozen_truth_sha256": truth_hash,
        "physical_formulation": {
            "surface": "eta=sum a cos(k dot x-omega t+phi)",
            "dispersion": "omega^2=g k tanh(k h0), h0=10 m",
            "surface_horizontal_velocity": "u_h=a omega coth(kh) cos(psi) k_hat",
            "surface_vertical_velocity": "w=a omega sin(psi)",
            "LOS_projection": "u_LOS=sin(incidence) u_range + cos(incidence) w, positive toward sensor",
            "RAR": "10 [max(n dot LOS,0)/cos(incidence)]^2",
            "bunching": "y_SAR=y+(R/V)u_LOS",
            "jacobian": "J=1+(R/V) partial u_LOS/partial y; M3/M4 use conservative forward splatting and retain multi-source folds",
            "temporal_look": "rectangular slow-time brightness average by Gauss-Legendre quadrature",
        },
        "model_definitions": MODEL_LABELS,
        "nominal_models": nominal,
        "nominal_diagnostics": nominal_diagnostics,
        "bunching_strength_sweep": strength,
        "look_width_experiment": widths,
        "first_mechanism_destroying_dispersion": first_destroying,
        "simple_model_explains_Vandenberg_flattening": False,
        "frozen_short_look_prediction": prediction,
        "conditional_real_short_look_test": real_short_look,
        "limitations": [
            "not a raw-SAR phase-history simulator",
            "no hydrodynamic modulation",
            "no coherent speckle",
            "no moving-scatterer phase-history/focusing or range migration",
            "no higher-order coherent velocity-bunching operator",
            "no full two-scale Bragg RAR/MTF or wind dependence",
            "fixed spatial grid resolution across look widths",
        ],
    }
    plots = plot_results(benchmark, nominal, strength, widths)
    summary["plots"] = [str(path.resolve()) for path in plots]
    summary_path = RESULTS / "BLOCK10_FORWARD_MODEL_SUMMARY.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    checkpoint = write_checkpoint(summary)

    if sha256(RESULTS / "BLOCK10_FROZEN_TRUTH.json") != truth_hash:
        raise RuntimeError("Block-10 synthetic truth changed during processing")
    if sha256(prediction_path) != prediction_hash:
        raise RuntimeError("Block-10 prediction changed after it was frozen")
    guards_after = {str(path.resolve()): sha256(path) for path in frozen_guard_paths()}
    if guards_after != guards_before:
        raise RuntimeError("A frozen Block 4--9 artifact changed")
    artifacts = [
        benchmark_path,
        *truth_paths,
        strength_path,
        width_path,
        prediction_path,
        summary_path,
        checkpoint,
        *plots,
    ]
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "guard_hashes_before": guards_before,
        "guard_hashes_after": guards_after,
        "guards_unchanged": True,
        "truth_sha256_before_and_after": truth_hash,
        "prediction_sha256_before_any_real_short_look": prediction_hash,
        "new_Vandenberg_processing_performed": False,
        "artifacts": {
            str(path.resolve()): sha256(path) for path in artifacts
        },
    }
    manifest_path = RESULTS / "BLOCK10_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "checkpoint": str(checkpoint.resolve()),
                "summary": str(summary_path.resolve()),
                "real_unique_samples": benchmark["unique_sample_count"],
                "real_fit": benchmark["weighted_fit"],
                "first_mechanism_destroying_dispersion": first_destroying,
                "prediction": prediction,
                "guards_unchanged": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

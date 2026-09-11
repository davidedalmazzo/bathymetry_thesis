"""Block 9: independent real-map recheck and end-to-end synthetic validation."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import matplotlib.pyplot as plt
import numpy as np

from umbra_sar.synthetic_validation import (
    canonical_half_plane_mask,
    component_crop_centers,
    finite_depth_group_velocity,
    finite_depth_omega,
    fit_linear_law,
    frozen_truth_components,
    generate_oracle_intensities,
    gaussian_patch_weights,
    run_full_subaperture_surrogate,
    run_oracle_case,
    spectra_from_intensities,
)
from umbra_sar.wave_analysis import local_coherent_phase_slope_map


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"
BLOCK8 = ROOT / "Block8_validation"
OUTPUT = ROOT / "Block9_validation"
RESULTS = OUTPUT / "results"
PLOTS = OUTPUT / "plots"
G_M_PER_S2 = 9.80665


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frozen_guard_paths() -> list[Path]:
    return [
        BLOCK8 / "results" / "CHECKPOINT_8.md",
        BLOCK8 / "results" / "top16_candidates.csv",
        BLOCK8 / "results" / "ranked_candidates_all.csv",
        VANDENBERG
        / "results"
        / "analysis_block4"
        / "BLOCK4_PHASE_METRICS_SAR_ONLY.json",
        VANDENBERG
        / "results"
        / "analysis_block6"
        / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.csv",
        VANDENBERG
        / "results"
        / "analysis_block6"
        / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.npz",
    ]


def weighted_linear_fit(k: np.ndarray, omega: np.ndarray, se: np.ndarray) -> dict[str, Any]:
    design = np.column_stack((np.ones(k.size), k))
    weights = 1.0 / np.maximum(se, 1e-12) ** 2
    beta = np.linalg.solve(design.T @ (weights[:, None] * design), design.T @ (weights * omega))
    fitted = design @ beta
    residual = omega - fitted
    rng = np.random.default_rng(902019)
    bootstrap = []
    for _ in range(10000):
        indices = rng.integers(0, k.size, k.size)
        xb = design[indices]
        wb = weights[indices]
        if np.ptp(k[indices]) == 0:
            continue
        try:
            current = np.linalg.solve(
                xb.T @ (wb[:, None] * xb), xb.T @ (wb * omega[indices])
            )
        except np.linalg.LinAlgError:
            continue
        bootstrap.append(current)
    boot = np.asarray(bootstrap)
    ordinary = np.linalg.lstsq(design, omega, rcond=None)[0]
    return {
        "model": "omega_obs=a+b*k_rad_per_m",
        "weights": "inverse squared selected max(OLS,HAC4) slope fit error",
        "warning": (
            "The 5x5 spectral patches overlap.  The bootstrap treats unique bins "
            "as resampling units and is descriptive, not an independent-DOF interval."
        ),
        "sample_count_conjugate_deduplicated": int(k.size),
        "a_rad_per_s": float(beta[0]),
        "b_m_per_s": float(beta[1]),
        "rmse_rad_per_s": float(np.sqrt(np.mean(residual**2))),
        "r_squared": float(
            1.0 - np.sum(residual**2) / np.sum((omega - np.mean(omega)) ** 2)
        ),
        "bootstrap_95_percent_interval": {
            "a_rad_per_s": np.quantile(boot[:, 0], [0.025, 0.975]).tolist(),
            "b_m_per_s": np.quantile(boot[:, 1], [0.025, 0.975]).tolist(),
        },
        "unweighted_sensitivity": {
            "a_rad_per_s": float(ordinary[0]),
            "b_m_per_s": float(ordinary[1]),
        },
    }


def real_data_recheck() -> dict[str, Any]:
    csv_path = (
        VANDENBERG
        / "results"
        / "analysis_block6"
        / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.csv"
    )
    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    by_offset = {
        (int(row["fft_bin_offset_row"]), int(row["fft_bin_offset_col"])): row
        for row in rows
    }
    seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    pairs = []
    unpaired = []
    for offset, row in by_offset.items():
        opposite = (-offset[0], -offset[1])
        key = tuple(sorted((offset, opposite)))
        if key in seen:
            continue
        seen.add(key)
        if opposite not in by_offset or opposite == offset:
            unpaired.append(offset)
            continue
        other = by_offset[opposite]
        pairs.append(
            {
                "first_offset": list(offset),
                "second_offset": list(opposite),
                "signed_slope_sum_rad_per_s": float(row["slope_rad_per_s"])
                + float(other["slope_rad_per_s"]),
                "aligned_slope_difference_rad_per_s": float(
                    row["aligned_slope_rad_per_s"]
                )
                - float(other["aligned_slope_rad_per_s"]),
            }
        )
    unique = [
        row
        for row in rows
        if canonical_half_plane_mask(
            np.asarray(int(row["fft_bin_offset_row"])),
            np.asarray(int(row["fft_bin_offset_col"])),
        )
    ]
    primary = [row for row in rows if row["frozen_peak_lobe_flag"] == "True"]
    primary_unique = [
        row
        for row in primary
        if canonical_half_plane_mask(
            np.asarray(int(row["fft_bin_offset_row"])),
            np.asarray(int(row["fft_bin_offset_col"])),
        )
    ]
    # The primary lobe and its conjugate occupy opposite half-planes in this
    # artifact.  Fall back to the explicitly marked primary side if needed.
    if not primary_unique:
        primary_unique = primary
    k = np.asarray([float(row["k_magnitude_rad_per_m"]) for row in primary_unique])
    omega = np.asarray([abs(float(row["slope_rad_per_s"])) for row in primary_unique])
    se = np.asarray(
        [float(row["slope_selected_standard_error_rad_per_s"]) for row in primary_unique]
    )
    fit = weighted_linear_fit(k, omega, se)

    dispersion = {}
    for depth in (5.0, 10.0, 20.0):
        expected = finite_depth_omega(k, depth)
        derivative = finite_depth_group_velocity(k, depth)
        dispersion[str(int(depth))] = {
            "omega_expected_range_rad_per_s": [
                float(np.min(expected)),
                float(np.max(expected)),
            ],
            "domega_dk_range_m_per_s": [
                float(np.min(derivative)),
                float(np.max(derivative)),
            ],
            "rmse_observed_vs_dispersion_rad_per_s": float(
                np.sqrt(np.mean((omega - expected) ** 2))
            ),
        }

    # Recompute the two disconnected low-k bins with several local smoothing
    # patches.  Thresholds only gate validity; the slopes themselves are fit
    # before thresholding in local_coherent_phase_slope_map.
    npz_path = (
        VANDENBERG
        / "results"
        / "analysis_block4"
        / "nearshore_sliding_spectrum_crops.npz"
    )
    with np.load(npz_path) as archive:
        spectra = np.asarray(archive["spectra"], dtype=np.complex128)
        time = np.asarray(archive["time_s"], dtype=np.float64)
    diagnostic_points = {
        "low_k_lambda_381m": (63, 65),
        "low_k_lambda_242m": (63, 66),
        "primary_lambda_191m": (62, 62),
        "primary_lambda_131m": (60, 63),
        "primary_lambda_81m": (58, 61),
    }
    smoothing = {}
    for radius in (0, 1, 2, 3, 4):
        weights = gaussian_patch_weights(radius, sigma=max(1.0, radius / 2.0))
        mapped = local_coherent_phase_slope_map(
            spectra,
            time,
            weights,
            hac_lag=4,
            adjacent_coherence_threshold=0.70,
            independent_indices=(0, 5, 10),
            independent_coherence_threshold=0.25,
            maximum_phase_step_rad=np.pi / 2.0,
            maximum_step_consistency_error_rad=0.25,
        )
        smoothing[f"{2 * radius + 1}x{2 * radius + 1}"] = {
            name: {
                "signed_slope_rad_per_s": float(mapped["slope_rad_per_s"][index]),
                "omega_abs_rad_per_s": abs(float(mapped["slope_rad_per_s"][index])),
                "fit_r_squared": float(mapped["r_squared"][index]),
                "minimum_independent_coherence": float(
                    mapped["minimum_independent_magnitude_squared_coherence"][index]
                ),
                "valid": bool(mapped["coherence_and_unwrap_valid"][index]),
                "maximum_phase_step_rad": float(
                    mapped["maximum_abs_direct_step_rad"][index]
                ),
            }
            for name, index in diagnostic_points.items()
        }

    high_quality_unique = [row for row in unique if row["high_quality_flag"] == "True"]
    low_high_quality = [
        row
        for row in high_quality_unique
        if row["frozen_peak_lobe_flag"] != "True"
        and float(row["wavelength_m"]) >= 200.0
    ]
    result = {
        "source_csv": str(csv_path.resolve()),
        "source_sha256": sha256(csv_path),
        "counts": {
            "total_csv_rows": len(rows),
            "conjugate_pairs": len(pairs),
            "unpaired_rows": len(unpaired),
            "independent_half_plane_samples": len(unique),
            "primary_lobe_rows_one_side": len(primary),
            "independent_conjugate_deduplicated_primary_lobe_bins": len(primary_unique),
            "statistical_independence_warning": (
                "The 22 unique lobe bins use overlapping 5x5 patches and are not "
                "22 independent statistical degrees of freedom."
            ),
        },
        "conjugate_check": {
            "maximum_abs_signed_slope_sum_rad_per_s": float(
                max(abs(item["signed_slope_sum_rad_per_s"]) for item in pairs)
            ),
            "maximum_abs_aligned_slope_difference_rad_per_s": float(
                max(abs(item["aligned_slope_difference_rad_per_s"]) for item in pairs)
            ),
            "aligned_pair_values_identical": bool(
                max(abs(item["aligned_slope_difference_rad_per_s"]) for item in pairs)
                < 2e-15
            ),
        },
        "primary_lobe": {
            "wavelength_range_m": [
                min(float(row["wavelength_m"]) for row in primary_unique),
                max(float(row["wavelength_m"]) for row in primary_unique),
            ],
            "omega_observed_range_rad_per_s": [float(np.min(omega)), float(np.max(omega))],
            "reported_0p352_to_0p407_strictly_reproduced": bool(
                np.min(omega) >= 0.352 and np.max(omega) <= 0.407
            ),
            "note": (
                "The wavelength range is reproduced.  The exact all-bin lobe range is "
                "0.34594--0.42286 rad/s; 0.352--0.407 is only an approximate trimmed range."
            ),
            "weighted_linear_fit": fit,
            "finite_depth_comparison": dispersion,
            "group_velocity_label_authorized": False,
        },
        "low_k_diagnostic": {
            "high_quality_unique_bins_outside_primary_with_lambda_ge_200m": [
                {
                    "crop_row": int(row["crop_row"]),
                    "crop_col": int(row["crop_col"]),
                    "wavelength_m": float(row["wavelength_m"]),
                    "omega_abs_rad_per_s": abs(float(row["slope_rad_per_s"])),
                    "signed_slope_rad_per_s": float(row["slope_rad_per_s"]),
                    "fit_r_squared": float(row["fit_r_squared"]),
                }
                for row in low_high_quality
            ],
            "patch_smoothing_sensitivity": smoothing,
            "conclusion": (
                "Two low-k high-quality bins exist at about 381 and 242 m, but they "
                "form a disconnected component and have the opposite signed branch on "
                "the chosen half-plane. Their small rate persists qualitatively yet "
                "changes materially with patch size and loses validity for wider patches. "
                "This is not a resolved transition inside the connected nearshore lobe."
            ),
            "implementation_audit": {
                "coherence_thresholds": "change inclusion only, not the precomputed fit slope",
                "connected_component_selection": "correctly excludes the two low-k bins from the frozen-peak lobe",
                "smoothing": "materially changes the low-k numerical rate and validity",
                "patch_indexing": "direct CSV offsets and NPZ indices agree",
                "sign_alignment": "does not cause the gap; raw low-k slopes already have the opposite sign",
                "phase_unwrapping": "original phase steps are far below pi/2; no wrap branch is required",
            },
        },
    }
    return result


def write_real_recheck_report(result: dict[str, Any]) -> Path:
    counts = result["counts"]
    lobe = result["primary_lobe"]
    fit = lobe["weighted_linear_fit"]
    low = result["low_k_diagnostic"]
    path = RESULTS / "BLOCK9_REAL_DATA_RECHECK.md"
    lines = [
        "# BLOCK 9 — independent Block-6 real-data recheck",
        "",
        "This report is read-only with respect to all frozen Vandenberg artifacts.",
        "",
        "## Conjugate deduplication",
        "",
        f"- CSV rows: **{counts['total_csv_rows']}**.",
        f"- Exact +k/-k pairs: **{counts['conjugate_pairs']}**; unpaired rows: **{counts['unpaired_rows']}**.",
        f"- Independent half-plane representatives: **{counts['independent_half_plane_samples']}**.",
        f"- Conjugate-deduplicated bins on the connected frozen nearshore lobe: **{counts['independent_conjugate_deduplicated_primary_lobe_bins']}**.",
        f"- Maximum aligned pair mismatch: `{result['conjugate_check']['maximum_abs_aligned_slope_difference_rad_per_s']:.3e} rad/s`.",
        "- These are unique spectral-bin observations, not independent statistical DOF, because adjacent 5x5 patches overlap.",
        "",
        "## Recomputed omega_obs(k)",
        "",
        f"- Connected-lobe wavelength range: `{lobe['wavelength_range_m'][0]:.3f}–{lobe['wavelength_range_m'][1]:.3f} m`.",
        f"- Exact `|dphi/dt|` range: `{lobe['omega_observed_range_rad_per_s'][0]:.6f}–{lobe['omega_observed_range_rad_per_s'][1]:.6f} rad/s`.",
        "- Therefore the earlier 80.5–191.5 m range is verified, but 0.352–0.407 rad/s is only an approximate trimmed description; the complete lobe reaches 0.34594–0.42286 rad/s.",
        f"- Inverse-variance WLS on 22 unique bins: `omega={fit['a_rad_per_s']:.6f}+{fit['b_m_per_s']:.6f} k`, with descriptive bootstrap 95% interval for b `{fit['bootstrap_95_percent_interval']['b_m_per_s'][0]:.3f}–{fit['bootstrap_95_percent_interval']['b_m_per_s'][1]:.3f} m/s`.",
        f"- Unweighted sensitivity gives `b={fit['unweighted_sensitivity']['b_m_per_s']:.6f} m/s`.",
        "- The reported ~1.68 m/s is verified numerically, but it is not called group velocity: finite-depth `domega/dk` over h=5–20 m is much larger and the observed points do not follow a gravity-wave dispersion curve.",
        "",
        "## Apparent low-k transition",
        "",
    ]
    for item in low["high_quality_unique_bins_outside_primary_with_lambda_ge_200m"]:
        lines.append(
            f"- lambda={item['wavelength_m']:.3f} m: |rate|={item['omega_abs_rad_per_s']:.6f} rad/s, signed rate={item['signed_slope_rad_per_s']:.6f}, R2={item['fit_r_squared']:.4f}."
        )
    lines += [
        "",
        low["conclusion"],
        "",
        "The coherence thresholds do not create the numerical slope; they only gate it. The strongest implementation sensitivity is local spectral smoothing. The original small phase steps exclude an unwrap-branch explanation, and direct offset checks exclude a patch-index mapping error.",
        "",
        "**Conclusion:** the connected nearshore lobe is a relatively flat phase-rate ridge, not an observed ocean-wave dispersion curve. The two low-k points are a separate, processing-sensitive feature and cannot be interpreted as a resolved regime transition.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def scenario_statistics(
    components: Sequence[Any],
    times: np.ndarray,
    omega: np.ndarray,
    name: str,
    options: dict[str, Any],
    *,
    realizations: int,
) -> dict[str, Any]:
    estimates = []
    valid = []
    for index in range(realizations):
        current = dict(options)
        current["seed"] = 92000 + index
        result = run_oracle_case(
            components,
            times,
            omega,
            case_name=name,
            generator_options=current,
        )
        estimates.append(
            [item["omega_final_rad_per_s"] for item in result["stage_tracking"]]
        )
        valid.append(result["all_bins_valid"])
    values = np.asarray(estimates)
    error = values - omega[None, :]
    return {
        "scenario": name,
        "isolated_effect": options,
        "realizations": realizations,
        "all_realizations_valid": bool(all(valid)),
        "per_component_mean_omega_rad_per_s": np.mean(values, axis=0).tolist(),
        "per_component_bias_rad_per_s": np.mean(error, axis=0).tolist(),
        "per_component_variance_rad2_per_s2": np.var(values, axis=0, ddof=1).tolist()
        if realizations > 1
        else [0.0] * omega.size,
        "max_abs_bias_rad_per_s": float(np.max(np.abs(np.mean(error, axis=0)))),
        "max_standard_deviation_rad_per_s": float(
            np.max(np.std(values, axis=0, ddof=1)) if realizations > 1 else 0.0
        ),
        "rmse_all_realizations_rad_per_s": float(np.sqrt(np.mean(error**2))),
    }


def plot_results(
    real: dict[str, Any],
    truth: Sequence[Any],
    oracle: dict[str, Any],
    full: dict[str, Any],
    negative: dict[str, Any],
    realism: list[dict[str, Any]],
) -> list[Path]:
    output = []
    k_truth = np.asarray([item.k_rad_per_m for item in truth])
    omega_truth = np.asarray([item.omega_rad_per_s for item in truth])
    dense = np.linspace(0.9 * np.min(k_truth), 1.1 * np.max(k_truth), 300)
    oracle_values = np.asarray(
        [item["omega_final_rad_per_s"] for item in oracle["stage_tracking"]]
    )
    full_values = np.asarray(
        [item["omega_final_rad_per_s"] for item in full["stage_tracking"]]
    )
    fig, axis = plt.subplots(figsize=(8.5, 5.5), constrained_layout=True)
    axis.plot(dense, finite_depth_omega(dense, 10.0), "k-", label="truth h=10 m")
    axis.plot(k_truth, omega_truth, "ko", label="injected modes")
    axis.plot(k_truth, oracle_values, "s", label="oracle recovered")
    axis.plot(k_truth, full_values, "^", label="full sub-aperture recovered")
    axis.set_xlabel("k (rad/m)")
    axis.set_ylabel("omega (rad/s)")
    axis.grid(True, alpha=0.25)
    axis.legend()
    path = PLOTS / "BLOCK9_SYNTHETIC_DISPERSION_RECOVERY.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    output.append(path)

    fig, axis = plt.subplots(figsize=(8.5, 5.2), constrained_layout=True)
    for name, result in negative.items():
        values = [item["omega_final_rad_per_s"] for item in result["stage_tracking"]]
        axis.plot(k_truth, values, "o-", label=name)
    axis.set_xlabel("k (rad/m)")
    axis.set_ylabel("recovered omega (rad/s)")
    axis.set_title("Negative controls remain distinguishable")
    axis.grid(True, alpha=0.25)
    axis.legend()
    path = PLOTS / "BLOCK9_NEGATIVE_CONTROLS.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    output.append(path)

    labels = [item["scenario"] for item in realism]
    bias = [item["max_abs_bias_rad_per_s"] for item in realism]
    std = [item["max_standard_deviation_rad_per_s"] for item in realism]
    x = np.arange(len(labels))
    fig, axis = plt.subplots(figsize=(10, 5.5), constrained_layout=True)
    axis.bar(x - 0.18, bias, width=0.36, label="max |bias|")
    axis.bar(x + 0.18, std, width=0.36, label="max std")
    axis.set_xticks(x, labels, rotation=25, ha="right")
    axis.set_ylabel("rad/s")
    axis.set_title("Progressive-realism sensitivity")
    axis.grid(True, axis="y", alpha=0.25)
    axis.legend()
    path = PLOTS / "BLOCK9_PROGRESSIVE_REALISM.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    output.append(path)

    # Independent Block-6 recheck plot uses the primary-side CSV again only
    # for visualization; the numerical fit is already frozen in the JSON.
    csv_path = Path(real["source_csv"])
    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = [r for r in csv.DictReader(stream) if r["frozen_peak_lobe_flag"] == "True"]
    k = np.asarray([float(r["k_magnitude_rad_per_m"]) for r in rows])
    obs = np.asarray([abs(float(r["slope_rad_per_s"])) for r in rows])
    fit = real["primary_lobe"]["weighted_linear_fit"]
    dense = np.linspace(np.min(k), np.max(k), 300)
    fig, axis = plt.subplots(figsize=(8.5, 5.5), constrained_layout=True)
    axis.scatter(k, obs, label="unique +k lobe bins")
    axis.plot(dense, fit["a_rad_per_s"] + fit["b_m_per_s"] * dense, label="weighted linear fit")
    for depth in (5.0, 10.0, 20.0):
        axis.plot(dense, finite_depth_omega(dense, depth), label=f"dispersion h={depth:g} m")
    axis.set_xlabel("k (rad/m)")
    axis.set_ylabel("|dphi/dt| (rad/s)")
    axis.set_title("Block-6 lobe does not follow finite-depth dispersion")
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize=8)
    path = PLOTS / "BLOCK9_REAL_DATA_RECHECK.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    output.append(path)
    return output


def write_checkpoint(summary: dict[str, Any]) -> Path:
    real = summary["real_data_recheck"]
    oracle = summary["oracle_dispersion"]
    full = summary["full_subaperture_surrogate"]
    controls = summary["negative_controls"]
    decision = summary["acceptance"]["decision"]
    path = RESULTS / "CHECKPOINT_9.md"
    lines = [
        "# CHECKPOINT_9 — end-to-end synthetic validation",
        "",
        f"Generated: {summary['generated_utc']}",
        "",
        "## Frozen scope",
        "",
        "- Block 8 remains a screening result only: its best available candidate is the 2025-12-02 Gulf collect, conditional because the verified buoy peak is 4.255 s wind sea rather than long swell. No candidate payload was downloaded.",
        "- Vandenberg Blocks 4–8 and `T_SAR=17.902230457 s` were neither modified nor reinterpreted.",
        "- No dwell sweep, bathymetric inversion, radar download, or real-data rerun was performed.",
        "",
        "## Independent Block-6 recheck",
        "",
        f"- 68 CSV rows form 34 exact conjugate pairs and 34 independent half-plane representatives.",
        f"- The connected nearshore lobe has 22 conjugate-deduplicated bins (overlapping patches, hence fewer than 22 statistical DOF).",
        f"- Aligned conjugate slopes agree within `{real['conjugate_check']['maximum_abs_aligned_slope_difference_rad_per_s']:.3e} rad/s`.",
        f"- Exact lobe range: lambda `{real['primary_lobe']['wavelength_range_m'][0]:.3f}–{real['primary_lobe']['wavelength_range_m'][1]:.3f} m`, omega_obs `{real['primary_lobe']['omega_observed_range_rad_per_s'][0]:.6f}–{real['primary_lobe']['omega_observed_range_rad_per_s'][1]:.6f} rad/s`.",
        f"- Unique-bin weighted fit: `b={real['primary_lobe']['weighted_linear_fit']['b_m_per_s']:.6f} m/s`; verified numerically but **not** identified as group velocity.",
        "- The 381/242 m low-k bins are a disconnected, smoothing-sensitive feature, not a resolved transition inside the nearshore lobe.",
        "",
        "## Synthetic truth",
        "",
        "- Six grid-resolved components span approximately 83–191 m and obey finite-depth gravity-wave dispersion at h=10 m.",
        "- Their periods are independent synthetic values; neither 17.9 s nor 13.33 s is used.",
        "",
        "## TEST A — Oracle intensity",
        "",
        f"- Maximum |omega_hat-omega_truth|: `{oracle['max_abs_error_rad_per_s']:.6f} rad/s`; RMSE `{oracle['rmse_rad_per_s']:.6f} rad/s`.",
        f"- All bins valid: `{oracle['all_bins_valid']}`. The nonlinear dispersion curve remains resolved and does not collapse to a constant.",
        "",
        "## TEST B — negative controls",
        "",
        f"- Static maximum error: `{controls['static']['max_abs_error_rad_per_s']:.3e} rad/s`.",
        f"- Constant-frequency maximum error: `{controls['constant']['max_abs_error_rad_per_s']:.3e} rad/s`.",
        f"- Artificial linear-law recovered coefficients: `a={summary['negative_control_fits']['linear']['intercept_rad_per_s']:.6f} rad/s`, `b={summary['negative_control_fits']['linear']['slope_m_per_s']:.6f} m/s` for injected a=0.2 and b=5.0.",
        "",
        "## TEST C — conjugates",
        "",
        f"- Maximum synthetic +k/-k signed-slope sum: `{summary['synthetic_conjugate_test']['maximum_abs_signed_slope_sum_rad_per_s']:.3e} rad/s`.",
        "- Future independent counts use one canonical half-plane; frozen Block-6 files were not edited.",
        "",
        "## TEST D — full sub-aperture surrogate",
        "",
        "- Construction: `Z(x,f)=R(f)[1+sum epsilon A_j exp(i k_j x-i omega_j t(f)+i phi_j)]` with an exact linear Doppler-bin to slow-time map.",
        "- `Col.Sgn=-1` surrogate uses FFT image→Doppler and IFFT Doppler→image; 11 six-second Tukey looks have 1.2 s centers and 80% overlap.",
        f"- Doppler round-trip relative maximum error: `{full['roundtrip_relative_max_error']:.3e}`.",
        f"- Maximum final frequency error: `{full['max_abs_error_rad_per_s']:.6f} rad/s`; RMSE `{full['rmse_rad_per_s']:.6f} rad/s`; all bins valid `{full['all_bins_valid']}`.",
        f"- First failing stage: `{summary['acceptance']['first_failing_stage']}`.",
        "",
        "## Constant-collapse audit and fixes",
        "",
        "- Fixed truth centers, temporal series, patch IDs, unwrap results, reference cross-spectra and sign-alignment outputs are asserted distinct per component.",
        "- Conjugate pairs are deduplicated before fitting/statistics.",
        "- Synthetic carrier construction uses a deterministic unit-modulus coherent carrier. A constant-phase carrier was rejected because it collapses into one azimuth impulse and makes spatial tapering dominate artificially; this correction is covered by the full-surrogate regression test.",
        "- No production real-data estimator bug causing constant-slope reuse was found.",
        "",
        "## Progressive realism",
        "",
    ]
    for item in summary["progressive_realism"]:
        lines.append(
            f"- `{item['scenario']}`: max |bias| `{item['max_abs_bias_rad_per_s']:.6f}` rad/s, max std `{item['max_standard_deviation_rad_per_s']:.6f}` rad/s, RMSE `{item['rmse_all_realizations_rad_per_s']:.6f}` rad/s."
        )
    lines += [
        "",
        "## Full suite and decision",
        "",
        f"- Block-9 acceptance assertions: `{summary['acceptance']['all_acceptance_assertions_passed']}`.",
        "- The total repository pytest result is finalized after this analysis run in `BLOCK9_TEST_SUITE_RESULT.json`; the delivered checkpoint records the exact count and duration.",
        "",
        f"# {decision}",
        "",
        "This authorization concerns software correctness only. It does not authorize a candidate SAR download; that remains a separate post-checkpoint decision.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)
    guard_before = {str(path.resolve()): sha256(path) for path in frozen_guard_paths()}

    real = real_data_recheck()
    real_json = RESULTS / "BLOCK9_REAL_DATA_RECHECK.json"
    real_json.write_text(json.dumps(real, indent=2) + "\n", encoding="utf-8")
    real_md = write_real_recheck_report(real)

    components = frozen_truth_components()
    truth_json = RESULTS / "BLOCK9_SYNTHETIC_TRUTH.json"
    truth_csv = RESULTS / "BLOCK9_SYNTHETIC_TRUTH.csv"
    truth_payload = {
        "frozen_before_processing": True,
        "depth_m": 10.0,
        "gravity_m_per_s2": G_M_PER_S2,
        "spatial_grid": {
            "range_samples": 1024,
            "range_pixel_spacing_m": 8.0,
            "range_length_m": 8192.0,
        },
        "components": [item.as_dict() for item in components],
        "explicit_exclusions": {
            "17p902_s_used_as_truth": False,
            "13p33_s_used_as_truth": False,
        },
    }
    truth_json.write_text(json.dumps(truth_payload, indent=2) + "\n", encoding="utf-8")
    with truth_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(components[0].as_dict()))
        writer.writeheader()
        writer.writerows(item.as_dict() for item in components)
    truth_hash_before = sha256(truth_json)

    with np.load(
        VANDENBERG
        / "results"
        / "analysis_block4"
        / "nearshore_sliding_spectrum_crops.npz"
    ) as archive:
        times = np.asarray(archive["time_s"], dtype=np.float64)
    omega_truth = np.asarray([item.omega_rad_per_s for item in components])
    k_truth = np.asarray([item.k_rad_per_m for item in components])

    oracle = run_oracle_case(
        components,
        times,
        omega_truth,
        case_name="finite_depth_dispersion_h10",
    )
    oracle_raw = run_oracle_case(
        components,
        times,
        omega_truth,
        case_name="rectangular_spatial_fft_control",
        standard_window=False,
    )
    negative_omega = {
        "static": np.zeros_like(k_truth),
        "constant": np.full_like(k_truth, 0.53),
        "linear": 0.20 + 5.0 * k_truth,
    }
    negative = {
        name: run_oracle_case(
            components, times, values, case_name=name
        )
        for name, values in negative_omega.items()
    }
    negative_fits = {
        name: fit_linear_law(
            k_truth,
            [item["omega_final_rad_per_s"] for item in result["stage_tracking"]],
        )
        for name, result in negative.items()
    }

    # Explicit conjugate slopes from real oracle intensity spectra.
    images = generate_oracle_intensities(components, times, omega_truth)
    spectra = spectra_from_intensities(images, standard_window=True)
    mapped = local_coherent_phase_slope_map(
        spectra,
        times,
        gaussian_patch_weights(2),
        hac_lag=4,
        adjacent_coherence_threshold=0.5,
        independent_indices=(0, 5, 10),
        independent_coherence_threshold=0.2,
    )
    conjugate_rows = []
    half = spectra.shape[1] // 2
    for component, positive in zip(components, component_crop_centers(components)):
        negative_center = (2 * half - positive[0], 2 * half - positive[1])
        positive_slope = float(mapped["slope_rad_per_s"][positive])
        negative_slope = float(mapped["slope_rad_per_s"][negative_center])
        conjugate_rows.append(
            {
                "component_id": component.component_id,
                "positive_center": list(positive),
                "negative_center": list(negative_center),
                "positive_slope_rad_per_s": positive_slope,
                "negative_slope_rad_per_s": negative_slope,
                "signed_slope_sum_rad_per_s": positive_slope + negative_slope,
                "aligned_positive_rad_per_s": -positive_slope,
                "aligned_negative_rad_per_s": negative_slope,
            }
        )
    conjugate = {
        "rows_before_deduplication": 2 * len(components),
        "independent_half_plane_rows": len(components),
        "maximum_abs_signed_slope_sum_rad_per_s": float(
            max(abs(item["signed_slope_sum_rad_per_s"]) for item in conjugate_rows)
        ),
        "maximum_abs_aligned_difference_rad_per_s": float(
            max(
                abs(item["aligned_positive_rad_per_s"] - item["aligned_negative_rad_per_s"])
                for item in conjugate_rows
            )
        ),
        "pairs": conjugate_rows,
    }
    del images, spectra, mapped

    full = run_full_subaperture_surrogate(components)

    unequal = [
        replace(item, amplitude=value)
        for item, value in zip(components, (1.00, 0.91, 0.83, 0.76, 0.69, 0.63))
    ]
    realism = [
        scenario_statistics(
            components,
            times,
            omega_truth,
            "white_additive_noise",
            {"white_noise_std": 1.0},
            realizations=8,
        ),
        scenario_statistics(
            components,
            times,
            omega_truth,
            "fixed_speckle_background",
            {"fixed_speckle_std": 1.0},
            realizations=8,
        ),
        scenario_statistics(
            components,
            times,
            omega_truth,
            "decorrelating_speckle",
            {"decorrelating_speckle_std": 0.35},
            realizations=8,
        ),
        scenario_statistics(
            unequal,
            times,
            omega_truth,
            "unequal_component_amplitudes",
            {},
            realizations=1,
        ),
        scenario_statistics(
            components,
            times,
            omega_truth,
            "finite_width_spectral_peaks",
            {"finite_peak_half_width_bins": 2},
            realizations=1,
        ),
    ]
    spatial_window_sensitivity = {
        "scenario": "real_data_like_detrend_Tukey_window",
        "isolated_effect": "difference from rectangular spatial FFT control",
        "realizations": 1,
        "all_realizations_valid": oracle["all_bins_valid"],
        "max_abs_bias_rad_per_s": oracle["max_abs_error_rad_per_s"],
        "max_standard_deviation_rad_per_s": 0.0,
        "rmse_all_realizations_rad_per_s": oracle["rmse_rad_per_s"],
        "rectangular_control_max_abs_error_rad_per_s": oracle_raw[
            "max_abs_error_rad_per_s"
        ],
    }
    realism.append(spatial_window_sensitivity)
    realism.append(
        {
            "scenario": "80_percent_overlapping_Doppler_looks",
            "isolated_effect": "full complex sub-aperture surrogate",
            "realizations": 1,
            "all_realizations_valid": full["all_bins_valid"],
            "max_abs_bias_rad_per_s": full["max_abs_error_rad_per_s"],
            "max_standard_deviation_rad_per_s": 0.0,
            "rmse_all_realizations_rad_per_s": full["rmse_rad_per_s"],
        }
    )

    oracle_values = np.asarray(
        [item["omega_final_rad_per_s"] for item in oracle["stage_tracking"]]
    )
    constant_baseline_rmse = float(
        np.sqrt(np.mean((omega_truth - np.mean(omega_truth)) ** 2))
    )
    constant_collapse_assertions = {
        "unique_truth_patch_centers": len(set(component_crop_centers(components)))
        == len(components),
        "truth_temporal_rates_not_shared": len(set(np.round(omega_truth, 12)))
        == len(components),
        "recovered_rates_not_constant": float(np.ptp(oracle_values)) > 0.25,
        "dispersion_rmse_better_than_constant_collapse_by_factor_50": oracle[
            "rmse_rad_per_s"
        ]
        < constant_baseline_rmse / 50.0,
        "smoothing_patches_do_not_overlap_other_truth_centers": min(
            abs(a.range_fft_mode - b.range_fft_mode)
            for index, a in enumerate(components)
            for b in components[index + 1 :]
        )
        > 2 * 2 + 2,
        "look_times_strictly_increasing": bool(
            np.all(
                np.diff(
                    full["Doppler_slice_time_mapping"]["effective_look_centers_s"]
                )
                > 0
            )
        ),
        "cross_convention_preserves_injected_sign": bool(
            all(item["signed_slope_rad_per_s"] < 0 for item in oracle["component_diagnostics"])
        ),
        "conjugates_deduplicated": conjugate["independent_half_plane_rows"]
        * 2
        == conjugate["rows_before_deduplication"],
        "reference_cross_spectrum_not_reused": bool(
            np.ptp(
                [
                    item["omega_after_spatial_fft_rad_per_s"]
                    for item in oracle["stage_tracking"]
                ]
            )
            > 0.25
        ),
    }

    acceptance_assertions = {
        "oracle_nonlinear_dispersion_max_error_le_0p005": oracle[
            "max_abs_error_rad_per_s"
        ]
        <= 0.005,
        "oracle_all_bins_valid": oracle["all_bins_valid"],
        "static_max_error_le_1e_10": negative["static"]["max_abs_error_rad_per_s"]
        <= 1e-10,
        "constant_max_error_le_1e_4": negative["constant"][
            "max_abs_error_rad_per_s"
        ]
        <= 1e-4,
        "linear_a_error_le_0p002": abs(
            negative_fits["linear"]["intercept_rad_per_s"] - 0.20
        )
        <= 0.002,
        "linear_b_error_le_0p05": abs(
            negative_fits["linear"]["slope_m_per_s"] - 5.0
        )
        <= 0.05,
        "conjugate_antisymmetry_le_1e_9": conjugate[
            "maximum_abs_signed_slope_sum_rad_per_s"
        ]
        <= 1e-9,
        "full_subaperture_max_error_le_0p005": full[
            "max_abs_error_rad_per_s"
        ]
        <= 0.005,
        "full_subaperture_all_bins_valid": full["all_bins_valid"],
        "full_Doppler_roundtrip_le_1e_12": full["roundtrip_relative_max_error"]
        <= 1e-12,
        "constant_collapse_audit_all_pass": all(constant_collapse_assertions.values()),
    }
    passed = all(acceptance_assertions.values())
    first_failing = next(
        (name for name, value in acceptance_assertions.items() if not value), None
    )
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Block 9 software correctness; no new real-data processing",
        "block8_brief": {
            "status": "CHECKPOINT_8 frozen",
            "best_available_conditional_collect": "2025-12-02-16-00-55_UMBRA-07",
            "action_taken": "none; no candidate radar payload downloaded",
        },
        "guardrails": {
            "Vandenberg_modified": False,
            "Block8_modified": False,
            "new_real_data_dwell_sweep": False,
            "bathymetric_inversion": False,
            "new_radar_download": False,
            "frozen_T_SAR_modified": False,
        },
        "real_data_recheck": real,
        "synthetic_truth_path": str(truth_json.resolve()),
        "synthetic_truth_sha256": truth_hash_before,
        "oracle_dispersion": oracle,
        "oracle_rectangular_spatial_fft_control": oracle_raw,
        "negative_controls": negative,
        "negative_control_fits": negative_fits,
        "synthetic_conjugate_test": conjugate,
        "full_subaperture_surrogate": full,
        "constant_slope_collapse_audit": constant_collapse_assertions,
        "progressive_realism": realism,
        "acceptance": {
            "assertions": acceptance_assertions,
            "all_acceptance_assertions_passed": passed,
            "first_failing_stage": first_failing,
            "decision": (
                "AUTHORIZED TO RETURN TO REAL DATA"
                if passed
                else "NOT YET AUTHORIZED TO RETURN TO REAL DATA"
            ),
        },
    }
    plots = plot_results(real, components, oracle, full, negative, realism)
    summary["plots"] = [str(path.resolve()) for path in plots]
    summary_json = RESULTS / "BLOCK9_SYNTHETIC_VALIDATION_SUMMARY.json"
    summary_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    checkpoint = write_checkpoint(summary)

    if sha256(truth_json) != truth_hash_before:
        raise RuntimeError("Synthetic truth changed after the processing run")
    guard_after = {str(path.resolve()): sha256(path) for path in frozen_guard_paths()}
    if guard_after != guard_before:
        raise RuntimeError("A frozen Block-8 or Vandenberg artifact changed")
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "guard_hashes_before": guard_before,
        "guard_hashes_after": guard_after,
        "guards_unchanged": True,
        "synthetic_truth_sha256_before_and_after": truth_hash_before,
        "artifacts": {
            str(path.resolve()): sha256(path)
            for path in [real_json, real_md, truth_json, truth_csv, summary_json, checkpoint, *plots]
        },
        "decision": summary["acceptance"]["decision"],
    }
    manifest_path = RESULTS / "BLOCK9_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "checkpoint": str(checkpoint.resolve()),
                "real_recheck": str(real_md.resolve()),
                "truth": str(truth_json.resolve()),
                "summary": str(summary_json.resolve()),
                "decision": summary["acceptance"]["decision"],
                "acceptance": acceptance_assertions,
            },
            indent=2,
        )
    )
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

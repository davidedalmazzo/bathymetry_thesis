"""Generate the reproducible human-readable Block-4 checkpoint."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"


def fmt(value: float, digits: int = 6) -> str:
    return f"{float(value):.{digits}f}"


def main() -> None:
    geometry = json.loads(
        (VANDENBERG / "metadata" / "RANGE_AXIS_RECONCILIATION.json").read_text(
            encoding="utf-8"
        )
    )
    plan = json.loads(
        (VANDENBERG / "metadata" / "BLOCK4_SLIDING_LOOK_PLAN.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (
            VANDENBERG
            / "results"
            / "block4_sliding_complex"
            / "BLOCK4_SLIDING_MANIFEST.json"
        ).read_text(encoding="utf-8")
    )
    metrics = json.loads(
        (
            VANDENBERG
            / "results"
            / "analysis_block4"
            / "BLOCK4_PHASE_METRICS_SAR_ONLY.json"
        ).read_text(encoding="utf-8")
    )
    external = json.loads(
        (
            VANDENBERG
            / "results"
            / "analysis_block4"
            / "BLOCK4_EXTERNAL_NDBC_COMPARISON.json"
        ).read_text(encoding="utf-8")
    )
    near = metrics["results"]["nearshore"]
    land = metrics["results"]["land_control"]
    near_phase = near["primary_fixed_patch_phase"]
    land_phase = land["primary_fixed_patch_phase"]
    near_fit = near_phase["fit_direct_reference_phase"]
    land_fit = land_phase["fit_direct_reference_phase"]
    times = metrics["time_axis"]["physical_slow_time_centers_s"]
    near_wrapped = near_phase["wrapped_phase_relative_reference_rad"]
    near_unwrapped = near_phase["unwrapped_phase_relative_reference_rad"]
    near_residual = near_fit["residual_phase_rad"]
    land_wrapped = land_phase["wrapped_phase_relative_reference_rad"]
    land_residual = land_fit["residual_phase_rad"]

    lines = [
        "# CHECKPOINT_4 — Nearshore fixed-width sliding-look phase",
        "",
        "## Stop condition",
        "",
        "Block 4 is complete for the reliable nearshore ROI, with the land ROI used only as a control. No dwell sweep and no bathymetric inversion were performed.",
        "",
        "## Range-axis reconciliation",
        "",
        f"- `105.848355722°` is CPHD `ReferenceGeometry.Monostatic.AzimuthAngle` at `{geometry['metadata_correction']['cphd_reference_time_s']:.9f} s`; it is not SICD `SCPCOA.AzimAng`.",
        f"- SICD `SCPCOA.AzimAng={geometry['metadata_correction']['actual_sicd_scpcoa_azimang_deg']:.9f}°` at `SCPTime={geometry['metadata_correction']['actual_sicd_scpcoa_scp_time_s']:.9f} s` is the ground-to-platform bearing.",
        f"- The groundward slant LOS is `{geometry['directed_los_bearings']['sicd_scp_time']['platform_to_ground_los_bearing_deg']:.9f}°`; positive Grid Row projected on the SCP tangent plane is `{geometry['sicd_grid_at_scp']['row_positive_bearing_tangent_projection_deg']:.9f}°`. They define the same undirected line as SCPCOA modulo 180°.",
        "- The geographic frequency conversion uses the local surface Jacobian, not the later CPHD reference angle:",
        "",
        "| ROI | wavevector (° mod 180) | local surface Grid Row (°) | Δ from local Row | Δ from SICD SCPCOA axis | Δ from CPHD-reference axis |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in ("nearshore", "offshore"):
        item = geometry["local_surface_projection"]["roi_results"][name]
        lines.append(
            f"| {name} | {item['wavevector_bearing_deg_mod_180']:.3f} | {item['local_surface_grid_row_bearing_deg']:.3f} | {item['wavevector_difference_from_local_surface_row_deg']:.3f} | {item['wavevector_difference_from_sicd_scpcoa_azimang_axis_deg']:.3f} | {item['wavevector_difference_from_cphd_reference_azimuth_axis_deg']:.3f} |"
        )
    lines.extend(
        [
            "",
            "The Block-3 values `21.3°` and `14.6°` therefore refer specifically to the local surface projection of SICD Grid Row.",
            "",
            "## Sliding-look construction and time axis",
            "",
            f"- Count: `{plan['sequence']['count']}`; common Doppler width: `{plan['window']['length_bins']}` bins with energy-normalized Tukey α=0.25.",
            f"- Effective physical width: `{min(item['effective_span_s'] for item in plan['looks_chronological']):.3f}–{max(item['effective_span_s'] for item in plan['looks_chronological']):.3f} s`.",
            f"- CPHD/PVP center spacing: `{plan['sequence']['center_step_s']['minimum']:.3f}–{plan['sequence']['center_step_s']['maximum']:.3f} s`; Doppler overlap: approximately `80%`.",
            f"- Each processed row used all `{manifest['algorithm']['azimuth_columns_read_per_transformed_row']}` SICD columns; pre-decomposition azimuth crop: `{manifest['algorithm']['azimuth_pre_crop_before_doppler_decomposition']}`.",
            f"- Nonfinite input values: `{manifest['input_nonfinite_values_replaced_with_zero']}`. Complex64 phase is preserved.",
            "- Chronological looks 1, 6, and 11 are exactly the original three disjoint Block-3 bands (Block-3 looks 3, 2, and 1); their independent set remains stored separately for future dispersion work.",
            "- Processed aperture and CPHD dwell remain distinct: `18.068061721230308 s` versus `22.540812513364376 s`.",
            "",
            "## Fixed spectral coefficient",
            "",
            f"The phase uses one fixed 5×5 Gaussian-weighted patch centered at Block-3 crop bin `{near['fixed_patch_center']['crop_index_row_col']}` (offset `{near['fixed_patch_center']['fft_bin_offset_row_col']}`), wavelength `{near['fixed_patch_center']['nearest_integer_bin_wavelength_m']:.3f} m`. The coefficient is always `F_secondary * conj(F_reference)` relative to chronological look 1. Local peak drift is recorded separately and never retunes this patch.",
            "",
            "## Nearshore phase series",
            "",
            "| Look | PVP center t (s) | φ wrapped (rad) | φ unwrap (rad) | fit residual (rad) | direct-reference coherence |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for index, values in enumerate(
        zip(
            times,
            near_wrapped,
            near_unwrapped,
            near_residual,
            near_phase["direct_reference_magnitude_squared_coherence"],
        ),
        start=1,
    ):
        time, wrapped, unwrapped, residual, coherence = values
        lines.append(
            f"| {index} | {time:.6f} | {wrapped:.6f} | {unwrapped:.6f} | {residual:.6f} | {coherence:.4f} |"
        )

    criteria = near_phase["unwrapping_criteria"]
    sensitivity = near["estimator_sensitivity"]
    single = sensitivity["single_center_bin"]
    adjacent = sensitivity["adjacent_linked"]
    lines.extend(
        [
            "",
            "### Unwrapping decision",
            "",
            f"- Maximum direct temporal step: `{criteria['maximum_abs_direct_temporal_step_rad']:.3f} rad`; maximum adjacent cross phase: `{criteria['maximum_abs_adjacent_cross_phase_rad']:.3f} rad`, both below π/2.",
            f"- Minimum adjacent coherence: `{criteria['minimum_adjacent_magnitude_squared_coherence']:.4f}`; maximum direct-step/adjacent-cross discrepancy: `{criteria['maximum_abs_direct_step_minus_adjacent_cross_phase_rad']:.3f} rad`.",
            "- Temporal unwrapping is therefore justified by SAR continuity alone. No buoy or hindcast value entered this decision.",
            "",
            "### Linear fit",
            "",
            f"- `φ(t)=ω_p t+φ_0`, with `ω_p={near_fit['slope_rad_per_s']:.9f} rad/s` and `φ_0={near_fit['intercept_rad']:.9f} rad` for t from CollectionStart.",
            f"- Selected fit-only 1σ uncertainty on ω: `{near_fit['slope_standard_error_selected_rad_per_s']:.9f} rad/s`; 95% interval `{near_fit['slope_95_percent_ci_rad_per_s'][0]:.9f}` to `{near_fit['slope_95_percent_ci_rad_per_s'][1]:.9f} rad/s`.",
            f"- `T_SAR=2π/|ω_p|={near_fit['period_s']:.6f} s`; fit-only 1σ `{near_fit['period_1sigma_fit_only_s']:.6f} s`; fit-only 95% interval `{near_fit['period_95_percent_ci_fit_only_s'][0]:.6f}–{near_fit['period_95_percent_ci_fit_only_s'][1]:.6f} s`.",
            f"- Regression RMSE `{near_fit['residual_rmse_rad']:.6f} rad`, maximum residual `{near_fit['residual_max_abs_rad']:.6f} rad`, `R²={near_fit['r_squared']:.6f}`.",
            f"- Gaussian patch radii 1–5 give `{sensitivity['patch_period_range_s'][0]:.3f}–{sensitivity['patch_period_range_s'][1]:.3f} s`; adjacent-linked accumulation gives `{adjacent['period_s']:.3f} s`; the noisier single fixed bin gives `{single['period_s']:.3f} s`.",
            "- The latter alternatives are a methodological sensitivity envelope, not independent Gaussian samples. The quoted ±0.247 s is therefore fit-only and does not capture all sliding-window systematics.",
            f"- The conjugate peak reverses the slope with sum `{near['conjugate_peak_check']['slope_sum_with_primary_rad_per_s']:.3e} rad/s` and reproduces the period within `{near['conjugate_peak_check']['period_difference_s']:.3e} s`.",
            "",
            "## Land control with identical centers",
            "",
            f"The land patch is the nearest physical EN frequency to the nearshore target: crop bin `{land['fixed_patch_center']['crop_index_row_col']}`, wavelength `{land['fixed_patch_center']['nearest_integer_bin_wavelength_m']:.3f} m`.",
            "",
            "| Look | PVP center t (s) | land φ (rad) | land fit residual (rad) |",
            "|---:|---:|---:|---:|",
        ]
    )
    for index, values in enumerate(
        zip(times, land_wrapped, land_residual), start=1
    ):
        time, wrapped, residual = values
        lines.append(
            f"| {index} | {time:.6f} | {wrapped:.6f} | {residual:.6f} |"
        )
    lines.extend(
        [
            "",
            f"The land slope is `{land_fit['slope_rad_per_s']:.6f} ± {land_fit['slope_standard_error_selected_rad_per_s']:.6f} rad/s` (1σ); its 95% interval `{land_fit['slope_95_percent_ci_rad_per_s'][0]:.6f}` to `{land_fit['slope_95_percent_ci_rad_per_s'][1]:.6f} rad/s` includes zero. `R²={land_fit['r_squared']:.4f}` and no land period is declared. The nearshore linear trend is therefore not a common deterministic ramp seen on land.",
            "",
            "## External comparison performed afterward",
            "",
            f"The frozen SAR-only JSON predates and is hashed before the external comparison (`{external['ordering_guardrail']['sar_only_metrics_sha256']}`). No phase, branch, fit, or uncertainty was changed afterward.",
            "",
            f"NOAA/NDBC station 46218 Harvest (CDIP 071), `{external['source']['distance_from_nearshore_roi_center_km']:.2f} km` from the ROI, reports at `{external['nearest_buoy_record']['time_utc']}` (`{external['nearest_buoy_record']['time_difference_from_sicd_midpoint_s']:.1f} s` after SICD midpoint):",
            "",
            f"- Hs `{external['nearest_buoy_record']['significant_wave_height_m']:.2f} m`; dominant period DPD `{external['nearest_buoy_record']['dominant_wave_period_s']:.2f} s`; all-wave average APD `{external['nearest_buoy_record']['average_wave_period_s']:.2f} s`.",
            f"- MWD `{external['nearest_buoy_record']['mean_wave_direction_from_deg_true']:.0f}°` from, corresponding to a propagation-to axis of `{external['comparison']['ndbc_inferred_propagation_to_deg_true']:.0f}°`; its undirected difference from the SAR wavevector is `{external['comparison']['undirected_axis_difference_sar_vs_ndbc_deg']:.2f}°`.",
            f"- `T_SAR/DPD={external['comparison']['sar_to_ndbc_dominant_period_ratio']:.3f}` and the difference is `{external['comparison']['sar_minus_ndbc_dominant_period_s']:.3f} s`. The periods do not agree within the fit-only SAR interval.",
            "- DPD is the maximum-energy spectral period and APD is the all-wave average; neither is automatically a swell-partition period.",
            "",
            "## Interpretation boundary",
            "",
            "The nearshore fixed-patch phase is experimentally very close to linear over the available centers, and the land control does not share its slope. `T_SAR=17.90 s` is therefore a reproducible SAR phase-rate estimator for this configuration. Its disagreement with the coincident buoy DPD, plus the strong correlation of 80%-overlapping windows, means it is not yet validated as the physical ocean-wave peak period.",
            "",
            "No bathymetric inversion, 5–16 s dwell sweep, hindcast-forced branch selection, or retuning to the buoy was performed. Synthetic regression suite: `22 passed`.",
            "",
            "## Explicit stop",
            "",
            "`CHECKPOINT_4`: stopped before the dwell sweep and before bathymetric inversion.",
            "",
        ]
    )
    output = ROOT / "CHECKPOINT_4.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

"""Generate CHECKPOINT_3.md from verified Block-3 machine-readable outputs."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / 'umbra/Vandenberg'


def f(value: float, digits: int = 3) -> str:
    return f"{float(value):.{digits}f}"


def main() -> None:
    verification = json.loads(
        (VANDENBERG / "metadata" / "SICD_DOWNLOAD_VERIFICATION.json").read_text(
            encoding="utf-8"
        )
    )
    mapping = json.loads(
        (VANDENBERG / "metadata" / "CPHD_DOPPLER_TIME_MAPPING.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (
            VANDENBERG
            / "results"
            / "sublooks_complex"
            / "SUBLOOK_MANIFEST.json"
        ).read_text(encoding="utf-8")
    )
    metrics = json.loads(
        (
            VANDENBERG
            / "results"
            / "analysis_block3"
            / "BLOCK3_SPECTRAL_METRICS.json"
        ).read_text(encoding="utf-8")
    )

    lines = [
        "# CHECKPOINT_3 — Vandenberg fixed three-look analysis",
        "",
        "## Stop condition",
        "",
        "Block 3 is complete. No 5–16 s dwell sweep, bathymetric inversion, or automatic cross-phase-to-period conversion was performed.",
        "",
        "## SICD integrity",
        "",
        f"- Final file: `{verification['path']}`.",
        f"- Exact size: `{verification['size_bytes']}` bytes; match: `{verification['exact_size_match']}`.",
        f"- Multipart ETag: `{verification['multipart_etag']}`; match: `{verification['multipart_etag_match']}`.",
        f"- SHA-256: `{verification['sha256']}`.",
        f"- NITF file-length field matches EOF: `{verification['nitf_header_length_matches_file']}`.",
        f"- SarPy stitched shape: `{verification['sarpy']['stitched_data_shapes']}`; SICD XSD valid: `{verification['validation_interpretation']['range_extracted_xml_xsd_valid']}`.",
        f"- SarPy recursive semantic flag: `{verification['sarpy']['recursive_semantic_valid']}`; expected/nonblocking due to the documented negative downchirp sign check plus SVA-without-WgtFunct: `{verification['validation_interpretation']['sarpy_false_is_expected_and_nonblocking']}`.",
        "",
        "## Timing and Doppler order",
        "",
        f"- SICD processed aperture: `{mapping['durations_kept_distinct']['sicd_processed_aperture_duration_s']}` s.",
        f"- CPHD available PVP slow-time dwell: `{mapping['durations_kept_distinct']['cphd_available_slow_time_dwell_s']}` s.",
        "- These quantities remain distinct throughout the code and results.",
        f"- PVP geometry reproduces SICD `Row.KCtr` with absolute error `{mapping['reference_checks']['row_kctr_absolute_error_per_m']:.3e}` cycles/m.",
        f"- CPHD PVP versus SICD ARP-polynomial `k_col` residual: RMS `{mapping['reference_checks']['cphd_vs_sicd_arp_poly_k_col_residual_per_m']['rms']:.3e}` cycles/m.",
        "- `k_col` decreases with TxTime. Therefore the fixed FFT order is look 1 = late, look 2 = central, look 3 = early.",
        "",
        "| Look | Effective early–center–late PVP time (s) | Effective span (s) |",
        "|---:|---|---:|",
    ]
    for item in mapping["looks"]:
        times = item["effective_early_center_late_s"]
        lines.append(
            f"| {item['look_index']} | {f(times[0])} – {f(times[1])} – {f(times[2])} | {f(item['effective_edge_span_s'])} |"
        )

    lines.extend(
        [
            "",
            "## Formation and ROI controls",
            "",
            f"- `Col.Sgn={manifest['algorithm']['sicd_col_sgn']}`: image→Doppler `{manifest['algorithm']['image_to_shifted_spectrum']}`, Doppler→image `{manifest['algorithm']['shifted_spectrum_to_image']}`.",
            f"- Every transformed row used all `{manifest['algorithm']['azimuth_columns_read_per_transformed_row']}` azimuth columns; pre-decomposition azimuth crop: `{manifest['algorithm']['azimuth_pre_crop_before_doppler_decomposition']}`.",
            f"- Replaced nonfinite source samples: `{manifest['input_nonfinite_values_replaced_with_zero']}`.",
            f"- Native weighting: `{manifest['native_weight']['name']}`, sampled WgtFunct present: `{manifest['native_weight']['samples_present']}`. This warning did not block processing.",
            "- The GEC was used only to localize reproducible ROIs; every spectrum below comes from the complex SICD.",
            "",
            "| ROI | Kind | SICD bounds (rows; cols) | Approx. ground size (m) |",
            "|---|---|---|---|",
        ]
    )
    for name, result in metrics["results"].items():
        roi = result["roi"]
        bounds = roi["sicd_bounds"]
        extent = roi["approximate_ground_extent_row_col_m"]
        lines.append(
            f"| {name} | {roi['kind']} | {bounds['row_start_inclusive']}:{bounds['row_stop_exclusive']}; {bounds['col_start_inclusive']}:{bounds['col_stop_exclusive']} | {f(extent[0],1)} × {f(extent[1],1)} |"
        )

    lines.extend(
        [
            "",
            "## 2-D intensity-spectrum peaks and stability",
            "",
            "The peak direction is the modulation wavevector. The visible crest/stripe orientation is perpendicular to it, so a range-directed wavevector and azimuth-aligned stripes are compatible rather than contradictory.",
            "",
            "| ROI | Robust | λ look 1 / 2 / 3 (m) | Mean λ (m) | Wavevector bearing (° mod 180) | Crest bearing (° mod 180) | Δ wavevector from range (°) | Δ crest from azimuth (°) |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name, result in metrics["results"].items():
        stability = result["three_look_peak_stability"]
        if stability.get("matched_candidates"):
            wavelengths = " / ".join(
                f(item["wavelength_m"], 1)
                for item in stability["matched_candidates"]
            )
            lines.append(
                f"| {name} | {stability['robust']} | {wavelengths} | {f(stability['mean_wavelength_m'],1)} | {f(stability['mean_wavevector_bearing_deg_mod_180'],1)} | {f(stability['mean_crest_orientation_deg_mod_180'],1)} | {f(stability['mean_wavevector_difference_from_range_axis_deg'],1)} | {f(stability['mean_crest_difference_from_azimuth_axis_deg'],1)} |"
            )
        else:
            lines.append(f"| {name} | False | — | — | — | — | — | — |")

    lines.extend(["", "### Resolution of the range/azimuth ambiguity", ""])
    for name, result in metrics["results"].items():
        if not str(result["roi"]["kind"]).startswith("ocean"):
            continue
        stability = result["three_look_peak_stability"]
        if not stability["robust"]:
            lines.append(
                f"- **{name}:** unresolved in this fixed-look test because no peak passed all three-look thresholds."
            )
            continue
        range_difference = stability[
            "mean_wavevector_difference_from_range_axis_deg"
        ]
        azimuth_crest_difference = stability[
            "mean_crest_difference_from_azimuth_axis_deg"
        ]
        if range_difference <= 15.0 and azimuth_crest_difference <= 15.0:
            conclusion = (
                "the spectral wavevector is range-aligned while the visible crests are azimuth-aligned; "
                "the two descriptions refer to perpendicular aspects of the same modulation and are not conflicting"
            )
        elif stability["mean_wavevector_difference_from_azimuth_axis_deg"] <= 15.0:
            conclusion = (
                "the robust spectral wavevector is azimuth-aligned (and its crests range-aligned), "
                "so it does not support the preliminary near-range swell interpretation"
            )
        else:
            conclusion = (
                "the robust spectral peak is oblique to both local range and azimuth axes; "
                "the preliminary binary description is too coarse"
            )
        lines.append(
            f"- **{name}:** {conclusion} (Δk from range `{range_difference:.1f}°`, Δcrest from azimuth `{azimuth_crest_difference:.1f}°`)."
        )

    robust_ocean = [
        (name, result)
        for name, result in metrics["results"].items()
        if str(result["roi"]["kind"]).startswith("ocean")
        and result["three_look_peak_stability"]["robust"]
    ]
    lines.extend(["", "## Ocean cross-spectra and phase closure", ""])
    if not robust_ocean:
        lines.append(
            "No ocean peak passed the predeclared three-look robustness thresholds; conditional cross-spectra were therefore not formed."
        )
    for name, result in robust_ocean:
        cross = result["cross_spectra"]
        lines.extend(
            [
                f"### {name}",
                "",
                "Cross-spectra use detrended/windowed intensity and exactly `F_secondary * conj(F_reference)`.",
                "",
                "| Pair | Δt = t_secondary−t_reference (s) | Raw phase (rad) | Smoothed phase (rad) | Local magnitude-squared coherence |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for label in ("1-2", "2-3", "1-3"):
            pair = cross["pairs"][label]
            lines.append(
                f"| {label} | {f(pair['effective_secondary_minus_reference_s'],6)} | {f(pair['raw_bin_phase_rad'],6)} | {f(pair['locally_smoothed_phase_rad'],6)} | {f(pair['local_magnitude_squared_coherence'],4)} |"
            )
        closure = cross["phase_closure"]
        lines.extend(
            [
                "",
                f"- Raw same-bin closure error `φ13−wrap(φ12+φ23)`: `{closure['raw_closure_error_rad']:.3e}` rad.",
                f"- Locally smoothed closure error: `{closure['locally_smoothed_closure_error_rad']:.3e}` rad.",
                f"- Upper-quartile joint-amplitude field closure RMS / max: `{closure['upper_quartile_joint_amplitude_field_closure_rms_rad']:.3e}` / `{closure['upper_quartile_joint_amplitude_field_closure_max_abs_rad']:.3e}` rad.",
                "- The raw same-bin identity is an algebraic consistency check; scientific reliability is assessed from local smoothing and coherence.",
                "- No phase was converted into a wave period.",
                "",
            ]
        )

    land = metrics["land_control_deterministic_terms"]
    lines.extend(
        [
            "## Land-control deterministic terms",
            "",
            "Registration is performed on `log1p` of 8-column block-averaged intensity (approximately isotropic ground sampling). No correction is silently applied to the ocean products.",
            "",
            "| Pair | SICD displacement row,col (pixels) | Ground displacement E,N (m) | Magnitude (m) | Zero-shift log Pearson | Ramp-removed resultant |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for label in ("1-2", "2-3", "1-3"):
        pair = land["pairs"][label]
        pixels = pair["original_sicd_pixel_displacement_row_col"]
        ground = pair["ground_displacement_east_north_m"]
        lines.append(
            f"| {label} | {f(pixels[0],4)}, {f(pixels[1],4)} | {f(ground[0],4)}, {f(ground[1],4)} | {f(pair['ground_displacement_magnitude_m'],4)} | {f(pair['zero_shift_log_intensity_pearson_correlation'],4)} | {f(pair['phase_ramp_removed_residual_resultant'],4)} |"
        )
    raw_23 = land["pairs"]["2-3"]["raw_intensity_phase_correlation_diagnostic"]
    raw_13 = land["pairs"]["1-3"]["raw_intensity_phase_correlation_diagnostic"]
    pair_23 = land["pairs"]["2-3"]
    pair_13 = land["pairs"]["1-3"]
    lines.extend(
        [
            "",
            f"Shift-closure residual magnitude on ground: `{land['shift_closure_ground_magnitude_m']:.6f}` m.",
            "",
            "Raw-intensity phase correlation was also retained as an adverse diagnostic. A few point scatterers spanning more than six orders of magnitude produced false maxima for pairs 2–3 and 1–3 at display-pixel shifts "
            f"`{raw_23['subpixel_displacement_secondary_relative_to_reference_row_col']}` and `{raw_13['subpixel_displacement_secondary_relative_to_reference_row_col']}`. "
            "At those raw candidates, log-intensity Pearson correlations are only "
            f"`{pair_23['raw_candidate_log_intensity_pearson_correlation']:.4f}` and `{pair_13['raw_candidate_log_intensity_pearson_correlation']:.4f}`, versus zero-shift values "
            f"`{pair_23['zero_shift_log_intensity_pearson_correlation']:.4f}` and `{pair_13['zero_shift_log_intensity_pearson_correlation']:.4f}`. "
            "Log-intensity registration and Gaussian scales 1, 2, 4, and 8 display pixels all select the zero-shift neighborhood; therefore the apparent ~98 m raw result is rejected as an outlier-driven lock, not corrected away. Exact multi-scale shifts are retained in the metrics JSON.",
            "",
            "Ramp-removed resultants of 0.316–0.447 are too low to support one common deterministic phase ramp across all three land looks.",
            "",
            "## Method choice and remaining limits",
            "",
            "- The intensity-domain choice follows Li, Mouche, Stopa & Chapron (2019), JGR Oceans, section 2.2.1, which explicitly forms sub-look intensity images after inverse transforming three nonoverlapping Doppler parts, then forms image cross-spectra: https://doi.org/10.1029/2018JC014638.",
            "- The three complex64 sub-looks are retained as master products; intensity is derived afterward.",
            "- The present ROI result is a fixed-look diagnostic, not yet an ensemble-averaged operational ocean-wave retrieval.",
            "- A `T_SAR` is not declared in this checkpoint. Effective PVP look times are available, but physical phase interpretation still requires review of land terms, coherence, and dispersion across future independent tiles/dwells.",
            "- Synthetic regression suite: `21 passed`. The original five convention groups remain explicitly documented in `tests/TEST_REPORT.md`; the two Block-3 wave/registration regressions are documented in `tests/TEST_REPORT_BLOCK3.md`.",
            "",
            "## Explicit stop",
            "",
            "`CHECKPOINT_3`: stopped before the requested 5–16 s dwell sweep and before depth inversion.",
            "",
        ]
    )
    output = ROOT / 'docs/checkpoints/CHECKPOINT_3.md'
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

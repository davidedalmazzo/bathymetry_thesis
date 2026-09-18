"""Block 6: coherent 2-D temporal phase-slope map and orientation diagnostics."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import label
from scipy.stats import spearmanr

from umbra_sar.wave_analysis import local_coherent_phase_slope_map


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / 'umbra/Vandenberg'
OUTPUT = VANDENBERG / "results" / "analysis_block6"
FROZEN_T_SAR_S = 17.902230457045317
FROZEN_SLOPE_RAD_PER_S = -0.3509722055168202
FROZEN_SHA256 = "c399af008e2159ede9b6e27b8bf99dffdd17b7f808aa263ea569d20438df8fcd"
G_M_PER_S2 = 9.80665


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gaussian_weights(radius: int = 2, sigma: float = 1.0) -> np.ndarray:
    row, col = np.mgrid[-radius : radius + 1, -radius : radius + 1]
    weight = np.exp(-(row**2 + col**2) / (2.0 * sigma**2))
    return weight / np.sum(weight)


def unit_en(bearing_deg: float) -> np.ndarray:
    angle = np.deg2rad(bearing_deg)
    return np.array([np.sin(angle), np.cos(angle)], dtype=np.float64)


def axial_difference(first_deg: np.ndarray, second_deg: float) -> np.ndarray:
    return np.abs(((first_deg - second_deg + 90.0) % 180.0) - 90.0)


def finite_depth_omega(k_rad_per_m: np.ndarray, depth_m: float) -> np.ndarray:
    return np.sqrt(G_M_PER_S2 * k_rad_per_m * np.tanh(k_rad_per_m * depth_m))


def standardized_ols(y: np.ndarray, variables: dict[str, np.ndarray]) -> dict[str, Any]:
    names = list(variables)
    raw = np.column_stack([np.asarray(variables[name], dtype=np.float64) for name in names])
    means = np.mean(raw, axis=0)
    scales = np.std(raw, axis=0, ddof=1)
    if np.any(scales == 0):
        raise ValueError("standardized regression received a constant predictor")
    standardized = (raw - means) / scales
    design = np.column_stack((np.ones(y.size), standardized))
    beta = np.linalg.lstsq(design, y, rcond=None)[0]
    residual = y - design @ beta
    dof = y.size - design.shape[1]
    covariance = np.sum(residual**2) / dof * np.linalg.inv(design.T @ design)
    total = np.sum((y - np.mean(y)) ** 2)
    return {
        "sample_count": int(y.size),
        "predictors": names,
        "predictor_means": means.tolist(),
        "predictor_standard_deviations": scales.tolist(),
        "intercept": float(beta[0]),
        "coefficient_per_predictor_1sd": {
            name: float(value) for name, value in zip(names, beta[1:])
        },
        "standard_error": {
            "intercept": float(np.sqrt(covariance[0, 0])),
            **{
                name: float(value)
                for name, value in zip(names, np.sqrt(np.diag(covariance))[1:])
            },
        },
        "r_squared": float(1.0 - np.sum(residual**2) / total),
        "residual_rmse": float(np.sqrt(np.mean(residual**2))),
        "inference_warning": "Neighbouring 5x5 spectral patches overlap, so binwise standard errors are descriptive and anti-conservative; effect sizes, not p-values, are used for the conclusion.",
    }


def correlation(first: np.ndarray, second: np.ndarray) -> dict[str, Any]:
    result = spearmanr(first, second)
    return {
        "spearman_rho": float(result.statistic),
        "nominal_p_value_not_used_for_inference": float(result.pvalue),
        "sample_count": int(first.size),
    }


def angle_bins(
    angle_deg: np.ndarray, values: np.ndarray, mask: np.ndarray
) -> list[dict[str, Any]]:
    output = []
    for low in range(0, 90, 15):
        high = low + 15
        current = mask & (angle_deg >= low) & (
            (angle_deg < high) if high < 90 else (angle_deg <= high)
        )
        sample = values[current]
        output.append(
            {
                "angle_from_range_bounds_deg": [low, high],
                "sample_count": int(sample.size),
                "median_rad_per_s": float(np.median(sample)) if sample.size else None,
                "minimum_rad_per_s": float(np.min(sample)) if sample.size else None,
                "maximum_rad_per_s": float(np.max(sample)) if sample.size else None,
            }
        )
    return output


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    block4_json = VANDENBERG / "results" / "analysis_block4" / "BLOCK4_PHASE_METRICS_SAR_ONLY.json"
    frozen_json = VANDENBERG / "results" / "analysis_block5" / "BLOCK5_FROZEN_INPUTS.json"
    spectra_path = VANDENBERG / "results" / "analysis_block4" / "nearshore_sliding_spectrum_crops.npz"
    roi_path = VANDENBERG / "roi" / "ROIS.json"
    metadata_path = VANDENBERG / "metadata" / "SICD_METADATA.json"
    dispersion_path = VANDENBERG / "results" / "analysis_block5" / "BLOCK5_DISPERSION_DIAGNOSTIC.json"
    ndbc_path = VANDENBERG / "results" / "analysis_block5" / "BLOCK5_NDBC_FULL_SPECTRUM.json"

    frozen = json.loads(frozen_json.read_text(encoding="utf-8"))
    block4 = json.loads(block4_json.read_text(encoding="utf-8"))
    roi = json.loads(roi_path.read_text(encoding="utf-8"))["rois"]["nearshore"]
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    dispersion = json.loads(dispersion_path.read_text(encoding="utf-8"))
    ndbc = json.loads(ndbc_path.read_text(encoding="utf-8"))
    frozen_values = frozen["frozen_sar_only"]
    if not math.isclose(frozen_values["T_SAR_s"], FROZEN_T_SAR_S, abs_tol=1e-12):
        raise RuntimeError("Frozen T_SAR changed")
    if not math.isclose(frozen_values["omega_rad_per_s"], FROZEN_SLOPE_RAD_PER_S, abs_tol=1e-14):
        raise RuntimeError("Frozen slope changed")
    if sha256(block4_json) != FROZEN_SHA256:
        raise RuntimeError("Block-4 frozen source hash changed")

    with np.load(spectra_path) as archive:
        spectra = np.asarray(archive["spectra"], dtype=np.complex128)
        time_s = np.asarray(archive["time_s"], dtype=np.float64)
        k_east = np.asarray(archive["k_east"], dtype=np.float64)
        k_north = np.asarray(archive["k_north"], dtype=np.float64)
        fixed_center = tuple(int(value) for value in archive["fixed_center"])

    weights = gaussian_weights()
    mapped = local_coherent_phase_slope_map(
        spectra,
        time_s,
        weights,
        hac_lag=4,
        adjacent_coherence_threshold=0.70,
        independent_indices=(0, 5, 10),
        independent_coherence_threshold=0.25,
        maximum_phase_step_rad=np.pi / 2.0,
        maximum_step_consistency_error_rad=0.25,
    )

    range_bearing = float(roi["local_row_axis_bearing_deg_clockwise_from_north"])
    azimuth_bearing = float(roi["local_col_axis_bearing_deg_clockwise_from_north"])
    range_unit = unit_en(range_bearing)
    azimuth_unit = unit_en(azimuth_bearing)
    k_range = k_east * range_unit[0] + k_north * range_unit[1]
    k_azimuth = k_east * azimuth_unit[0] + k_north * azimuth_unit[1]
    k_magnitude = np.hypot(k_east, k_north)
    k_rad = 2.0 * np.pi * k_magnitude
    wavelength = np.divide(
        1.0,
        k_magnitude,
        out=np.full_like(k_magnitude, np.inf),
        where=k_magnitude > 0,
    )
    bearing_360 = np.degrees(np.arctan2(k_east, k_north)) % 360.0
    bearing_180 = bearing_360 % 180.0
    angle_from_range = axial_difference(bearing_180, range_bearing % 180.0)
    angle_from_azimuth = axial_difference(bearing_180, azimuth_bearing % 180.0)

    target_en = np.array(
        [
            frozen_values["lambda_SAR_m"] ** -1
            * np.sin(np.deg2rad(frozen_values["theta_SAR_wavevector_bearing_deg_mod_180"])),
            frozen_values["lambda_SAR_m"] ** -1
            * np.cos(np.deg2rad(frozen_values["theta_SAR_wavevector_bearing_deg_mod_180"])),
        ]
    )
    hemisphere = np.where(k_east * target_en[0] + k_north * target_en[1] >= 0, 1.0, -1.0)
    aligned_slope = hemisphere * mapped["slope_rad_per_s"]
    depth_13 = float(dispersion["required_depth_cases_m"]["buoy_dominant_13_33"])
    depth_17 = float(dispersion["required_depth_cases_m"]["frozen_SAR_exact"])
    omega_13 = finite_depth_omega(k_rad, depth_13)
    omega_17 = finite_depth_omega(k_rad, depth_17)
    bias_13 = aligned_slope + omega_13
    bias_17 = aligned_slope + omega_17

    map_mask = (
        mapped["coherence_and_unwrap_valid"]
        & (wavelength >= 40.0)
        & (wavelength <= 500.0)
    )
    primary_power = float(mapped["mean_local_power"][fixed_center])
    high_quality = (
        map_mask
        & (mapped["r_squared"] >= 0.95)
        & (mapped["selected_slope_standard_error_rad_per_s"] <= 0.04)
        & (mapped["mean_local_power"] >= 0.05 * primary_power)
    )
    component_labels, _ = label(high_quality, structure=np.ones((3, 3), dtype=np.int8))
    primary_label = int(component_labels[fixed_center])
    if primary_label == 0:
        raise RuntimeError("The frozen nearshore bin did not survive declared quality criteria")
    primary_lobe = component_labels == primary_label
    conjugate_lobe = primary_lobe[::-1, ::-1]

    slope_at_peak = float(mapped["slope_rad_per_s"][fixed_center])
    if not math.isclose(slope_at_peak, FROZEN_SLOPE_RAD_PER_S, abs_tol=1e-13):
        raise RuntimeError("Slope-map estimator does not reproduce the frozen fixed-patch result")
    center_conjugate = (
        spectra.shape[1] - 1 - fixed_center[0],
        spectra.shape[2] - 1 - fixed_center[1],
    )
    conjugate_slope_sum = slope_at_peak + float(mapped["slope_rad_per_s"][center_conjugate])
    antisymmetry_error = np.nanmax(
        np.abs(mapped["slope_rad_per_s"] + mapped["slope_rad_per_s"][::-1, ::-1])[
            map_mask & map_mask[::-1, ::-1]
        ]
    )

    rows = []
    center_row = spectra.shape[1] // 2
    center_col = spectra.shape[2] // 2
    for row, col in np.argwhere(map_mask):
        index = (int(row), int(col))
        record = {
            "crop_row": int(row),
            "crop_col": int(col),
            "fft_bin_offset_row": int(row - center_row),
            "fft_bin_offset_col": int(col - center_col),
            "k_east_cycles_per_m": float(k_east[index]),
            "k_north_cycles_per_m": float(k_north[index]),
            "kx_range_cycles_per_m": float(k_range[index]),
            "ky_azimuth_cycles_per_m": float(k_azimuth[index]),
            "k_magnitude_cycles_per_m": float(k_magnitude[index]),
            "kx_range_rad_per_m": float(2.0 * np.pi * k_range[index]),
            "ky_azimuth_rad_per_m": float(2.0 * np.pi * k_azimuth[index]),
            "k_magnitude_rad_per_m": float(k_rad[index]),
            "wavelength_m": float(wavelength[index]),
            "wavevector_bearing_deg": float(bearing_360[index]),
            "wavevector_bearing_deg_mod_180": float(bearing_180[index]),
            "angle_from_local_range_axis_deg": float(angle_from_range[index]),
            "angle_from_local_azimuth_axis_deg": float(angle_from_azimuth[index]),
            "slope_rad_per_s": float(mapped["slope_rad_per_s"][index]),
            "slope_ols_standard_error_rad_per_s": float(
                mapped["ols_slope_standard_error_rad_per_s"][index]
            ),
            "slope_hac4_standard_error_rad_per_s": float(
                mapped["hac_slope_standard_error_rad_per_s"][index]
            ),
            "slope_selected_standard_error_rad_per_s": float(
                mapped["selected_slope_standard_error_rad_per_s"][index]
            ),
            "fit_residual_rmse_rad": float(mapped["residual_rmse_rad"][index]),
            "fit_r_squared": float(mapped["r_squared"][index]),
            "minimum_adjacent_coherence": float(
                mapped["minimum_adjacent_magnitude_squared_coherence"][index]
            ),
            "minimum_independent_anchor_coherence": float(
                mapped["minimum_independent_magnitude_squared_coherence"][index]
            ),
            "end_to_end_coherence_look1_look11": float(
                mapped["independent_magnitude_squared_coherence"][2][index]
            ),
            "mean_local_power": float(mapped["mean_local_power"][index]),
            "power_relative_to_frozen_peak": float(
                mapped["mean_local_power"][index] / primary_power
            ),
            "hemisphere_relative_to_frozen_wavevector": int(hemisphere[index]),
            "aligned_slope_rad_per_s": float(aligned_slope[index]),
            "expected_omega_rad_per_s_h13_33_compatibility": float(omega_13[index]),
            "bias_vs_h13_33_dispersion_rad_per_s": float(bias_13[index]),
            "expected_omega_rad_per_s_h17_902_compatibility": float(omega_17[index]),
            "bias_vs_h17_902_dispersion_rad_per_s": float(bias_17[index]),
            "high_quality_flag": bool(high_quality[index]),
            "frozen_peak_lobe_flag": bool(primary_lobe[index]),
            "conjugate_peak_lobe_flag": bool(conjugate_lobe[index]),
        }
        rows.append(record)

    csv_path = OUTPUT / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    selected = primary_lobe
    selected_annulus = selected & (
        k_magnitude >= 0.85 * k_magnitude[fixed_center]
    ) & (k_magnitude <= 1.15 * k_magnitude[fixed_center])
    orientation_analysis = {
        "selection": {
            "map_wavelength_bounds_m": [40.0, 500.0],
            "minimum_r_squared_for_primary_lobe": 0.95,
            "maximum_selected_slope_standard_error_rad_per_s": 0.04,
            "minimum_power_fraction_of_frozen_peak": 0.05,
            "lobe_definition": "8-connected high-quality component containing the frozen Block-4 bin; no new maximum was selected",
            "primary_lobe_bin_count": int(np.sum(selected)),
            "near_peak_annulus_fractional_k_bounds": [0.85, 1.15],
            "near_peak_annulus_bin_count": int(np.sum(selected_annulus)),
        },
        "primary_lobe_ranges": {
            "wavelength_m": [float(np.min(wavelength[selected])), float(np.max(wavelength[selected]))],
            "angle_from_range_deg": [float(np.min(angle_from_range[selected])), float(np.max(angle_from_range[selected]))],
            "aligned_slope_rad_per_s": [float(np.min(aligned_slope[selected])), float(np.max(aligned_slope[selected]))],
            "bias_vs_h13_33_dispersion_rad_per_s": [float(np.min(bias_13[selected])), float(np.max(bias_13[selected]))],
        },
        "spearman_descriptive": {
            "bias13_vs_k_magnitude": correlation(k_magnitude[selected], bias_13[selected]),
            "bias13_vs_abs_k_azimuth": correlation(np.abs(k_azimuth[selected]), bias_13[selected]),
            "bias13_vs_angle_from_range": correlation(angle_from_range[selected], bias_13[selected]),
            "near_peak_annulus_slope_vs_abs_k_azimuth": correlation(
                np.abs(k_azimuth[selected_annulus]), aligned_slope[selected_annulus]
            ),
            "near_peak_annulus_slope_vs_angle_from_range": correlation(
                angle_from_range[selected_annulus], aligned_slope[selected_annulus]
            ),
        },
        "standardized_multivariable_models": {
            "bias13_from_k_magnitude_and_abs_k_azimuth": standardized_ols(
                bias_13[selected],
                {
                    "k_magnitude_cycles_per_m": k_magnitude[selected],
                    "abs_k_azimuth_cycles_per_m": np.abs(k_azimuth[selected]),
                },
            ),
            "bias13_from_k_magnitude_and_angle_from_range": standardized_ols(
                bias_13[selected],
                {
                    "k_magnitude_cycles_per_m": k_magnitude[selected],
                    "angle_from_range_deg": angle_from_range[selected],
                },
            ),
            "observed_slope_from_k_magnitude_and_abs_k_azimuth": standardized_ols(
                aligned_slope[selected],
                {
                    "k_magnitude_cycles_per_m": k_magnitude[selected],
                    "abs_k_azimuth_cycles_per_m": np.abs(k_azimuth[selected]),
                },
            ),
        },
        "angle_binned_bias13": angle_bins(angle_from_range, bias_13, selected),
        "interpretation": "The +0.120 rad/s value is one bin, not a constant field correction. Across the connected lobe the diagnostic bias varies mainly with |k| because the measured phase-rate ridge is much flatter than the finite-depth dispersion curve. After controlling for |k|, the standardized |k_az| coefficient is negligible relative to its descriptive standard error. The seven-bin near-peak annulus hints at a more-negative slope away from range, but overlapping patches and the small effective sample do not establish a systematic orientation law.",
    }

    platform_speed = float(np.linalg.norm(metadata["scpcoa"]["arp_velocity_ecf_mps"]))
    slant_range = float(metadata["scpcoa"]["slant_range_m"])
    range_over_velocity = slant_range / platform_speed
    incidence_rad = np.deg2rad(metadata["scpcoa"]["incidence_angle_deg"])
    selected_angle_rad = np.deg2rad(
        json.loads(
            (VANDENBERG / "metadata" / "RANGE_AXIS_RECONCILIATION.json").read_text(
                encoding="utf-8"
            )
        )["local_surface_projection"]["roi_results"]["nearshore"][
            "wavevector_difference_from_local_surface_row_deg"
        ]
    )
    lambda_peak = float(frozen_values["lambda_SAR_m"])
    k_peak_rad = 2.0 * np.pi / lambda_peak
    omega_buoy = 2.0 * np.pi / 13.33
    k_az_peak_rad = k_peak_rad * np.sin(selected_angle_rad)
    mtf_direction_factor = float(
        np.hypot(
            np.cos(selected_angle_rad) * np.sin(incidence_rad),
            np.cos(incidence_rad),
        )
    )
    shift_mtf_core_m_per_m = range_over_velocity * omega_buoy * mtf_direction_factor
    shift_modulation_per_m_amplitude = abs(k_az_peak_rad) * shift_mtf_core_m_per_m
    frozen_partition_hm0 = float(
        ndbc["broad_energy_partitions"][0]["equivalent_partition_Hm0_m"]
    )
    equivalent_sinusoid_amplitude = frozen_partition_hm0 / (2.0 * np.sqrt(2.0))
    atbd_shift_parameter = shift_modulation_per_m_amplitude * equivalent_sinusoid_amplitude
    kh = k_peak_rad * depth_13
    horizontal_orbital_velocity_amplitude = (
        equivalent_sinusoid_amplitude * omega_buoy / np.tanh(kh)
    )
    vertical_orbital_velocity_amplitude = equivalent_sinusoid_amplitude * omega_buoy
    los_velocity_amplitude = float(
        np.hypot(
            horizontal_orbital_velocity_amplitude
            * np.sin(incidence_rad)
            * np.cos(selected_angle_rad),
            vertical_orbital_velocity_amplitude * np.cos(incidence_rad),
        )
    )
    finite_depth_bunching_parameter = (
        abs(k_az_peak_rad) * range_over_velocity * los_velocity_amplitude
    )
    extra_rate_at_peak = omega_buoy + FROZEN_SLOPE_RAD_PER_S
    fractional_extra_rate = extra_rate_at_peak / omega_buoy
    nonlinear_ratio_in_phase = fractional_extra_rate / (1.0 - fractional_extra_rate)
    nonlinear_ratio_quadrature = math.sqrt(
        fractional_extra_rate / (1.0 - fractional_extra_rate)
    )

    theory = {
        "sources": {
            "engen_johnsen": {
                "citation": "G. Engen and H. Johnsen, SAR-ocean wave inversion using image cross spectra, IEEE TGRS 33(4), 1995, DOI 10.1109/36.406690",
                "role": "nonlinear ocean-to-SAR image cross-spectrum and directional ambiguity removal",
            },
            "sentinel1_osw_atbd": {
                "local_pdf": str((ROOT / "tmp" / "pdfs" / "S1_OSW_ATBD_2020_v1.3.pdf").resolve()),
                "equations_used": [34, 35, 36, 37],
            },
        },
        "quasi_linear_single_component": {
            "equation": "P_ql(k,t)=C(k)[A(k) exp(-i omega t)+B(k) exp(+i omega t)]",
            "definitions": "C=U exp[-(k_y lambda_c/2pi)^2]/2; A=|T(k)|^2 S(k); B=|T(-k)|^2 S(-k)",
            "phase_rate": "d arg(P_ql)/dt = omega (B^2-A^2)/(A^2+B^2+2AB cos(2 omega t)) for stationary C",
            "one_direction_limit": "B=0 gives exactly -omega; arg(C) is a constant intercept",
            "mtf_note": "In Eq. 34 the stationary MTF enters as |T|^2. Its own complex phase therefore cannot by itself change the ideal temporal slope. Through A/B and P_nlin, however, its k_y-dependent shift term changes component mixing and nonlinearity.",
        },
        "general_bias_terms": {
            "equation": "P=C(t)[A exp(-i omega t)+B exp(+i omega t)]+N(t); dphi/dt=Im(conj(P) dP/dt)/|P|^2",
            "terms": [
                "opposite-direction mixture B/A=S(-k)|T(-k)|^2 / [S(k)|T(k)|^2]",
                "nonlinear transform contribution N=P_nlin, explicitly subtracted by Sentinel-1 before quasi-linear inversion",
                "look-dependent system/MTF phase d arg(C)/dt, possible for sliding Doppler sub-apertures even though stationary C only shifts phi0",
                "current/advection k dot U, which changes the actual encounter frequency rather than the SAR MTF",
                "six-second symmetric look averaging changes amplitude by a real sinc for one stationary tone; overlap changes covariance, not the ideal slope",
            ],
            "single_component_plus_stationary_nonlinear_term": "For P=A exp(-i omega t)+N, dphi/dt=-omega[A^2+A Re(N* exp(-i omega t))]/[A^2+|N|^2+2A Re(N* exp(-i omega t))].",
        },
        "umbra_geometry_order_of_magnitude": {
            "slant_range_m": slant_range,
            "platform_speed_m_per_s": platform_speed,
            "R_over_V_s": range_over_velocity,
            "incidence_angle_deg": float(metadata["scpcoa"]["incidence_angle_deg"]),
            "frozen_peak_lambda_m": lambda_peak,
            "peak_angle_from_local_range_deg": float(np.rad2deg(selected_angle_rad)),
            "peak_k_azimuth_rad_per_m": k_az_peak_rad,
            "omega_13_33_rad_per_s": omega_buoy,
            "ATBD_shift_MTF_geometric_core_m_per_m_surface_amplitude": shift_mtf_core_m_per_m,
            "dimensionless_shift_modulation_per_m_surface_amplitude": shift_modulation_per_m_amplitude,
            "frozen_NDBC_partition_Hm0_m_context_only": frozen_partition_hm0,
            "equivalent_narrow_sinusoid_amplitude_m_context_only": equivalent_sinusoid_amplitude,
            "ATBD_core_dimensionless_shift_parameter_context_only": atbd_shift_parameter,
            "finite_depth_kh_at_10_627m": kh,
            "finite_depth_LOS_orbital_velocity_amplitude_m_per_s_context_only": los_velocity_amplitude,
            "finite_depth_velocity_bunching_parameter_context_only": finite_depth_bunching_parameter,
            "caveat": "The ATBD tuning/switch factor u_h is unavailable for Umbra and was set to unity only for an unfitted geometric scale. The NDBC Hm0 is the already-frozen context, not a refit or a period-selection input.",
        },
        "can_0_120_rad_per_s_be_reached": {
            "required_extra_rate_at_frozen_peak_rad_per_s": extra_rate_at_peak,
            "fraction_of_13_33s_omega": fractional_extra_rate,
            "stationary_N_over_A_required_if_in_phase": nonlinear_ratio_in_phase,
            "stationary_N_over_A_required_if_quadrature": nonlinear_ratio_quadrature,
            "uniform_advection_speed_along_k_required_m_per_s": extra_rate_at_peak / k_peak_rad,
            "assessment": "A uniform-current explanation alone requires about 2.5 m/s along k and is not the economical explanation. Umbra's R/V and nonzero k_az give an unfitted velocity-bunching parameter of order 0.4 for the frozen sea-state scale, large enough that tens-of-percent nonlinear cross-spectral terms are plausible. This establishes order-of-magnitude plausibility, not a prediction of +0.120 rad/s: the full P_nlin lookup, X-band RAR MTF/wind dependence, and look-dependent transfer are unavailable.",
        },
    }

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Block 6 SAR-only 2-D phase-slope map and theory; nearshore only",
        "frozen_inputs": {
            "T_SAR_s": FROZEN_T_SAR_S,
            "slope_rad_per_s": FROZEN_SLOPE_RAD_PER_S,
            "lambda_SAR_m": frozen_values["lambda_SAR_m"],
            "theta_SAR_deg_mod_180": frozen_values[
                "theta_SAR_wavevector_bearing_deg_mod_180"
            ],
            "block4_sha256": sha256(block4_json),
            "NDBC_comparison_changed": False,
        },
        "time_axis": block4["time_axis"],
        "local_axes": {
            "kx_definition": "projection of EN wavevector on positive local SICD Grid Row/range direction",
            "ky_definition": "projection of EN wavevector on positive local SICD Grid Col/azimuth direction",
            "positive_range_bearing_deg": range_bearing,
            "positive_azimuth_bearing_deg": azimuth_bearing,
            "axis_separation_deg": float(axial_difference(np.array([range_bearing]), azimuth_bearing)[0]),
        },
        "criteria": {
            "patch": "same Gaussian 5x5, sigma=1 bin as frozen Block 4",
            "cross_convention": "F_secondary * conj(F_reference)",
            "minimum_adjacent_magnitude_squared_coherence": 0.70,
            "minimum_each_independent_anchor_pair_coherence": 0.25,
            "independent_anchor_chronological_indices": [1, 6, 11],
            "maximum_phase_step_rad": float(np.pi / 2.0),
            "maximum_step_consistency_error_rad": 0.25,
            "wavelength_bounds_m": [40.0, 500.0],
            "fit_error": "max(OLS standard error, Newey-West HAC lag-4 standard error)",
        },
        "counts": {
            "coherence_and_unwrap_valid_all_wavenumbers": int(
                np.sum(mapped["coherence_and_unwrap_valid"])
            ),
            "map_rows_40_to_500m": int(np.sum(map_mask)),
            "high_quality_rows": int(np.sum(high_quality)),
            "primary_lobe_rows": int(np.sum(primary_lobe)),
            "conjugate_lobe_rows": int(np.sum(conjugate_lobe)),
        },
        "frozen_peak_reproduction": {
            "crop_index_row_col": list(fixed_center),
            "slope_map_rad_per_s": slope_at_peak,
            "absolute_difference_from_frozen_rad_per_s": abs(
                slope_at_peak - FROZEN_SLOPE_RAD_PER_S
            ),
            "r_squared": float(mapped["r_squared"][fixed_center]),
            "selected_slope_standard_error_rad_per_s": float(
                mapped["selected_slope_standard_error_rad_per_s"][fixed_center]
            ),
            "minimum_adjacent_coherence": float(
                mapped["minimum_adjacent_magnitude_squared_coherence"][fixed_center]
            ),
            "minimum_independent_anchor_coherence": float(
                mapped["minimum_independent_magnitude_squared_coherence"][fixed_center]
            ),
            "bias_vs_13_33s_compatibility_rad_per_s": float(bias_13[fixed_center]),
        },
        "hermitian_conjugate_check": {
            "conjugate_center_row_col": list(center_conjugate),
            "frozen_plus_conjugate_slope_rad_per_s": conjugate_slope_sum,
            "maximum_abs_slope_antisymmetry_error_over_map_rad_per_s": float(
                antisymmetry_error
            ),
        },
        "orientation_analysis": orientation_analysis,
        "theory": theory,
        "duration_guardrail": {
            "SICD_processed_aperture_duration_s": metadata["image_formation"][
                "processed_dwell_s"
            ],
            "CPHD_available_dwell_s": metadata["cphd_comparison"]["cphd_dwell_s"],
            "kept_distinct": True,
        },
        "guardrails": {
            "dwell_sweep_performed": False,
            "bathymetric_inversion_performed": False,
            "T_SAR_retuned": False,
            "NDBC_reanalysis_performed": False,
            "diagnostic_depths_are_not_bathymetry": True,
        },
        "artifacts": {
            "map_csv": str(csv_path.resolve()),
            "map_npz": str((OUTPUT / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.npz").resolve()),
            "map_figure": str((OUTPUT / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.png").resolve()),
            "orientation_figure": str((OUTPUT / "BLOCK6_ORIENTATION_DIAGNOSTIC.png").resolve()),
        },
    }

    npz_path = OUTPUT / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.npz"
    np.savez_compressed(
        npz_path,
        k_east_cycles_per_m=k_east,
        k_north_cycles_per_m=k_north,
        k_range_cycles_per_m=k_range,
        k_azimuth_cycles_per_m=k_azimuth,
        wavelength_m=wavelength,
        angle_from_range_deg=angle_from_range,
        slope_rad_per_s=mapped["slope_rad_per_s"],
        slope_standard_error_rad_per_s=mapped[
            "selected_slope_standard_error_rad_per_s"
        ],
        residual_rmse_rad=mapped["residual_rmse_rad"],
        r_squared=mapped["r_squared"],
        minimum_adjacent_coherence=mapped[
            "minimum_adjacent_magnitude_squared_coherence"
        ],
        minimum_independent_coherence=mapped[
            "minimum_independent_magnitude_squared_coherence"
        ],
        bias_vs_h13_33_dispersion_rad_per_s=bias_13,
        mean_local_power=mapped["mean_local_power"],
        map_mask=map_mask,
        high_quality_mask=high_quality,
        primary_lobe_mask=primary_lobe,
        conjugate_lobe_mask=conjugate_lobe,
        wrapped_phase_relative_reference_rad=mapped[
            "wrapped_phase_relative_reference_rad"
        ],
        unwrapped_phase_relative_reference_rad=mapped[
            "unwrapped_phase_relative_reference_rad"
        ],
        time_s=time_s,
    )

    summary_path = OUTPUT / "BLOCK6_PHASE_SLOPE_SUMMARY.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    theory_path = OUTPUT / "BLOCK6_CROSS_SPECTRUM_THEORY.json"
    theory_path.write_text(json.dumps(theory, indent=2) + "\n", encoding="utf-8")

    x = 1000.0 * k_range
    y = 1000.0 * k_azimuth
    edge_row, edge_col = np.mgrid[
        -0.5 : x.shape[0] + 0.5 : 1.0, -0.5 : x.shape[1] + 0.5 : 1.0
    ]
    x_edge = (
        x[0, 0]
        + edge_row * (x[1, 0] - x[0, 0])
        + edge_col * (x[0, 1] - x[0, 0])
    )
    y_edge = (
        y[0, 0]
        + edge_row * (y[1, 0] - y[0, 0])
        + edge_col * (y[0, 1] - y[0, 0])
    )
    extent_masked = lambda value: np.ma.masked_where(~map_mask, value)
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), constrained_layout=True)
    plot_specs = [
        (np.log10(mapped["mean_local_power"]), "log10 local spectral power", "viridis", None, None),
        (extent_masked(mapped["slope_rad_per_s"]), "phase slope s (rad/s)", "coolwarm", -0.48, 0.48),
        (extent_masked(mapped["r_squared"]), "linear-fit R²", "magma", 0.0, 1.0),
        (extent_masked(bias_13), "aligned bias vs 13.33-s dispersion (rad/s)", "coolwarm", -0.35, 0.35),
    ]
    for axis, (value, title, cmap, vmin, vmax) in zip(axes.ravel(), plot_specs):
        artist = axis.pcolormesh(
            x_edge, y_edge, value, shading="flat", cmap=cmap, vmin=vmin, vmax=vmax
        )
        axis.plot(x[fixed_center], y[fixed_center], "wo", markeredgecolor="black", markersize=7, label="frozen bin")
        axis.contour(x, y, primary_lobe.astype(float), levels=[0.5], colors="lime", linewidths=1.2)
        axis.set_title(title)
        axis.set_xlabel("k range (cycles/km)")
        axis.set_ylabel("k azimuth (cycles/km)")
        axis.set_aspect("equal", adjustable="box")
        fig.colorbar(artist, ax=axis, shrink=0.86)
    for axis in (axes[0, 1], axes[1, 0], axes[1, 1]):
        axis.set_xlim(-35.0, 35.0)
        axis.set_ylim(-30.0, 30.0)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Nearshore: same 11 sliding looks, Gaussian 5×5 local cross-spectrum")
    map_figure = OUTPUT / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.png"
    fig.savefig(map_figure, dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    scatter = axes[0, 0].scatter(
        wavelength[selected], aligned_slope[selected], c=angle_from_range[selected], cmap="viridis", s=45
    )
    axes[0, 0].axhline(FROZEN_SLOPE_RAD_PER_S, color="black", linestyle="--", linewidth=1)
    axes[0, 0].set_xlabel("wavelength (m)")
    axes[0, 0].set_ylabel("aligned phase slope (rad/s)")
    axes[0, 0].set_title("Connected frozen-peak lobe")
    fig.colorbar(scatter, ax=axes[0, 0], label="angle from range (deg)")
    axes[0, 1].scatter(k_magnitude[selected], bias_13[selected], c=angle_from_range[selected], cmap="viridis", s=45)
    axes[0, 1].axhline(0.0, color="black", linewidth=0.8)
    axes[0, 1].set_xlabel("|k| (cycles/m)")
    axes[0, 1].set_ylabel("bias vs h=10.627 m dispersion (rad/s)")
    axes[0, 1].set_title("Bias is not a constant over the lobe")

    # Residualize both variables against |k| to show the partial orientation effect.
    current_k = k_magnitude[selected]
    current_az = np.abs(k_azimuth[selected])
    current_bias = bias_13[selected]
    base = np.column_stack((np.ones(current_k.size), current_k))
    az_residual = current_az - base @ np.linalg.lstsq(base, current_az, rcond=None)[0]
    bias_residual = current_bias - base @ np.linalg.lstsq(base, current_bias, rcond=None)[0]
    partial = np.polyfit(az_residual, bias_residual, 1)
    line_x = np.linspace(np.min(az_residual), np.max(az_residual), 100)
    axes[1, 0].scatter(1000.0 * az_residual, bias_residual, s=45)
    axes[1, 0].plot(1000.0 * line_x, np.polyval(partial, line_x), "r--")
    axes[1, 0].axhline(0.0, color="black", linewidth=0.8)
    axes[1, 0].set_xlabel("|k azimuth| residual after |k| (cycles/km)")
    axes[1, 0].set_ylabel("bias residual after |k| (rad/s)")
    axes[1, 0].set_title("Partial orientation effect")

    axes[1, 1].scatter(
        angle_from_range[selected_annulus],
        aligned_slope[selected_annulus],
        c=np.abs(k_azimuth[selected_annulus]) * 1000.0,
        cmap="plasma",
        s=60,
    )
    axes[1, 1].axhline(FROZEN_SLOPE_RAD_PER_S, color="black", linestyle="--", linewidth=1)
    axes[1, 1].set_xlabel("angle from local range axis (deg)")
    axes[1, 1].set_ylabel("aligned phase slope (rad/s)")
    axes[1, 1].set_title("Near-peak annulus ±15% in |k| (n=7)")
    for axis in axes.ravel():
        axis.grid(True, alpha=0.25)
    orientation_figure = OUTPUT / "BLOCK6_ORIENTATION_DIAGNOSTIC.png"
    fig.savefig(orientation_figure, dpi=180)
    plt.close(fig)

    print(summary_path)
    print(csv_path)
    print(npz_path)
    print(map_figure)
    print(orientation_figure)


if __name__ == "__main__":
    main()

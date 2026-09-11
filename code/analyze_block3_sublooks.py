"""Run Block-3 intensity, wave-spectrum, cross-spectrum, and land controls."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter

from umbra_sar.wave_analysis import (
    axial_difference_deg,
    find_peak_candidates,
    intensity_spectrum_crop,
    match_stable_peak,
    phase_correlation_shift,
    physical_frequency_grid,
    wrap_phase,
)


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"


def block_average_columns(intensity: np.ndarray, factor: int = 8) -> np.ndarray:
    rows, cols = intensity.shape
    if cols % factor:
        raise ValueError("column count must be divisible by display averaging factor")
    return np.mean(
        intensity.reshape(rows, cols // factor, factor), axis=2, dtype=np.float32
    )


def intensity_from_complex(data: np.ndarray) -> np.ndarray:
    source = np.asarray(data)
    return np.asarray(source.real * source.real + source.imag * source.imag, dtype=np.float32)


def overlap_pearson_at_integer_shift(
    reference: np.ndarray, secondary: np.ndarray, shift_row_col: np.ndarray
) -> float:
    """Pearson correlation after applying a non-wrapping integer displacement."""

    row_shift, col_shift = np.rint(shift_row_col).astype(int)
    if row_shift >= 0:
        first = reference[: -row_shift or None, :]
        second = secondary[row_shift:, :]
    else:
        first = reference[-row_shift:, :]
        second = secondary[:row_shift, :]
    if col_shift >= 0:
        first = first[:, : -col_shift or None]
        second = second[:, col_shift:]
    else:
        first = first[:, -col_shift:]
        second = second[:, :col_shift]
    first = first - np.mean(first)
    second = second - np.mean(second)
    return float(
        np.sum(first * second)
        / np.sqrt(np.sum(first**2) * np.sum(second**2))
    )


def enrich_candidate(
    candidate: dict[str, Any], row_axis_bearing: float, col_axis_bearing: float
) -> dict[str, Any]:
    result = dict(candidate)
    result["wavevector_difference_from_range_axis_deg"] = axial_difference_deg(
        candidate["wavevector_bearing_deg_mod_180"], row_axis_bearing % 180.0
    )
    result["wavevector_difference_from_azimuth_axis_deg"] = axial_difference_deg(
        candidate["wavevector_bearing_deg_mod_180"], col_axis_bearing % 180.0
    )
    result["crest_difference_from_range_axis_deg"] = axial_difference_deg(
        candidate["crest_orientation_deg_mod_180"], row_axis_bearing % 180.0
    )
    result["crest_difference_from_azimuth_axis_deg"] = axial_difference_deg(
        candidate["crest_orientation_deg_mod_180"], col_axis_bearing % 180.0
    )
    return result


def plot_intensities(
    roi_name: str,
    full_display: np.ndarray,
    displays: list[np.ndarray],
    row_extent_m: float,
    col_extent_m: float,
    row_bearing: float,
    col_bearing: float,
    output: Path,
) -> None:
    all_displays = [full_display, *displays]
    db_values = [10.0 * np.log10(np.maximum(item, np.finfo(np.float32).tiny)) for item in all_displays]
    combined = np.concatenate([item.ravel()[::8] for item in db_values])
    vmin, vmax = np.percentile(combined, [1.0, 99.7])
    fig, axes = plt.subplots(1, 4, figsize=(19, 5.1), constrained_layout=True)
    labels = ["full aperture", "look 1", "look 2", "look 3"]
    for index, (axis, values, label) in enumerate(zip(axes, db_values, labels)):
        image = axis.imshow(
            values,
            cmap="gray",
            origin="upper",
            extent=(0, col_extent_m / 1000.0, row_extent_m / 1000.0, 0),
            vmin=vmin,
            vmax=vmax,
            interpolation="nearest",
        )
        axis.set_title(label)
        axis.set_xlabel(f"SICD Col / azimuth axis (km; bearing {col_bearing%180:.1f}°)")
        if index == 0:
            axis.set_ylabel(f"SICD Row / range axis (km; bearing {row_bearing%180:.1f}°)")
        axis.set_aspect("equal")
    fig.colorbar(image, ax=axes, label="Intensity (dB, common display scale)", shrink=0.86)
    fig.suptitle(
        f"{roi_name}: full aperture and nominal ~6 s complex sub-looks (8-column intensity block average)"
    )
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_normalized_differences(
    roi_name: str,
    displays: list[np.ndarray],
    row_extent_m: float,
    col_extent_m: float,
    output: Path,
) -> None:
    pairs = [("1−2", 0, 1), ("2−3", 1, 2), ("1−3", 0, 2)]
    differences = [
        2.0
        * (displays[first] - displays[second])
        / np.maximum(displays[first] + displays[second], np.finfo(np.float32).tiny)
        for _, first, second in pairs
    ]
    limit = float(
        np.percentile(np.abs(np.concatenate([item.ravel()[::8] for item in differences])), 99)
    )
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5), constrained_layout=True)
    for axis, difference, (label, _, _) in zip(axes, differences, pairs):
        image = axis.imshow(
            difference,
            cmap="RdBu_r",
            origin="upper",
            extent=(0, col_extent_m / 1000, row_extent_m / 1000, 0),
            vmin=-limit,
            vmax=limit,
            interpolation="nearest",
        )
        axis.set_title(label)
        axis.set_xlabel("SICD Col / azimuth ground distance (km)")
        axis.set_aspect("equal")
    axes[0].set_ylabel("SICD Row / range ground distance (km)")
    fig.colorbar(image, ax=axes, label="2(Ia−Ib)/(Ia+Ib)", shrink=0.85)
    fig.suptitle(f"{roi_name}: normalized sub-look intensity differences")
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_power_spectra(
    roi_name: str,
    powers: list[np.ndarray],
    k_east: np.ndarray,
    k_north: np.ndarray,
    matched: list[dict[str, Any]],
    output: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), constrained_layout=True)
    radial = np.hypot(k_east, k_north)
    wave_band = (radial >= 1.0 / 500.0) & (radial <= 1.0 / 40.0)
    for index, (axis, power) in enumerate(zip(axes, powers), start=1):
        reference_power = float(np.max(power[wave_band]))
        values = 10.0 * np.log10(
            np.maximum(power / reference_power, np.finfo(float).tiny)
        )
        image = axis.pcolormesh(
            k_east * 1000.0,
            k_north * 1000.0,
            values,
            cmap="magma",
            shading="auto",
            vmin=-35,
            vmax=0,
        )
        if matched:
            peak = matched[index - 1]
            axis.scatter(
                peak["k_east_cycles_per_m"] * 1000.0,
                peak["k_north_cycles_per_m"] * 1000.0,
                marker="x",
                color="cyan",
                s=70,
                linewidth=2,
            )
        axis.set_title(f"look {index}")
        axis.set_xlabel("East spatial frequency (cycles/km)")
        if index == 1:
            axis.set_ylabel("North spatial frequency (cycles/km)")
        axis.set_aspect("equal")
        axis.set_xlim(-26, 26)
        axis.set_ylim(-26, 26)
        axis.grid(True, alpha=0.2)
    fig.colorbar(image, ax=axes, label="2-D power (dB relative to panel maximum)", shrink=0.86)
    fig.suptitle(f"{roi_name}: intensity power spectra; cyan = matched stability peak")
    fig.savefig(output, dpi=180)
    plt.close(fig)


def local_cross_metrics(
    first: np.ndarray,
    second: np.ndarray,
    index: tuple[int, int],
) -> dict[str, float]:
    cross = second * np.conjugate(first)
    row, col = index
    radius = 2
    row_slice = slice(max(0, row - radius), min(cross.shape[0], row + radius + 1))
    col_slice = slice(max(0, col - radius), min(cross.shape[1], col + radius + 1))
    block = cross[row_slice, col_slice]
    first_block = first[row_slice, col_slice]
    second_block = second[row_slice, col_slice]
    yy, xx = np.mgrid[
        row_slice.start - row : row_slice.stop - row,
        col_slice.start - col : col_slice.stop - col,
    ]
    weights = np.exp(-0.5 * (xx * xx + yy * yy))
    smoothed_cross = np.sum(weights * block)
    denominator = math.sqrt(
        float(np.sum(weights * np.abs(first_block) ** 2))
        * float(np.sum(weights * np.abs(second_block) ** 2))
    )
    return {
        "raw_bin_phase_rad": float(np.angle(cross[row, col])),
        "locally_smoothed_phase_rad": float(np.angle(smoothed_cross)),
        "local_magnitude_squared_coherence": float(
            min(1.0, abs(smoothed_cross) ** 2 / (denominator * denominator))
        ),
    }


def compute_cross_spectra(
    roi_name: str,
    spectra: list[np.ndarray],
    stability: dict[str, Any],
    k_east: np.ndarray,
    k_north: np.ndarray,
    time_mapping: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    selected = stability["matched_candidates"][1]
    selected_index = tuple(int(value) for value in selected["crop_index_row_col"])
    centers = {
        int(item["look_index"]): float(item["effective_early_center_late_s"][1])
        for item in time_mapping["looks"]
    }
    pair_definitions = [("1-2", 0, 1), ("2-3", 1, 2), ("1-3", 0, 2)]
    pair_metrics: dict[str, Any] = {}
    cross_arrays: dict[str, np.ndarray] = {}
    for label, reference, secondary in pair_definitions:
        first = np.asarray(spectra[reference], dtype=np.complex128)
        second = np.asarray(spectra[secondary], dtype=np.complex128)
        cross = second * np.conjugate(first)
        cross_arrays[f"cross_{label.replace('-', '_')}"] = cross.astype(np.complex64)
        pair_metrics[label] = {
            "reference_look": reference + 1,
            "secondary_look": secondary + 1,
            "formula": "F_secondary * conj(F_reference)",
            "effective_reference_center_s": centers[reference + 1],
            "effective_secondary_center_s": centers[secondary + 1],
            "effective_secondary_minus_reference_s": centers[secondary + 1]
            - centers[reference + 1],
            **local_cross_metrics(first, second, selected_index),
        }

    phi12 = pair_metrics["1-2"]["raw_bin_phase_rad"]
    phi23 = pair_metrics["2-3"]["raw_bin_phase_rad"]
    phi13 = pair_metrics["1-3"]["raw_bin_phase_rad"]
    smooth12 = pair_metrics["1-2"]["locally_smoothed_phase_rad"]
    smooth23 = pair_metrics["2-3"]["locally_smoothed_phase_rad"]
    smooth13 = pair_metrics["1-3"]["locally_smoothed_phase_rad"]

    cross12 = np.asarray(cross_arrays["cross_1_2"], dtype=np.complex128)
    cross23 = np.asarray(cross_arrays["cross_2_3"], dtype=np.complex128)
    cross13 = np.asarray(cross_arrays["cross_1_3"], dtype=np.complex128)
    closure_field = np.angle(cross13 * np.conjugate(cross12 * cross23))
    joint_amplitude = np.abs(cross12) * np.abs(cross23) * np.abs(cross13)
    field_mask = joint_amplitude >= np.percentile(joint_amplitude, 75.0)
    closure = {
        "identity": "phi13 ~= wrap(phi12 + phi23)",
        "selected_same_k_bin": list(selected_index),
        "raw_phi12_rad": phi12,
        "raw_phi23_rad": phi23,
        "raw_phi13_rad": phi13,
        "raw_wrapped_phi12_plus_phi23_rad": wrap_phase(phi12 + phi23),
        "raw_closure_error_rad": wrap_phase(phi13 - phi12 - phi23),
        "locally_smoothed_closure_error_rad": wrap_phase(
            smooth13 - smooth12 - smooth23
        ),
        "upper_quartile_joint_amplitude_field_closure_rms_rad": float(
            np.sqrt(np.mean(closure_field[field_mask] ** 2))
        ),
        "upper_quartile_joint_amplitude_field_closure_max_abs_rad": float(
            np.max(np.abs(closure_field[field_mask]))
        ),
    }

    npz_path = output_dir / f"{roi_name}_cross_spectra.npz"
    np.savez_compressed(
        npz_path,
        k_east_cycles_per_m=k_east,
        k_north_cycles_per_m=k_north,
        **cross_arrays,
    )

    fig, axes = plt.subplots(2, 3, figsize=(15.5, 9), constrained_layout=True)
    radial = np.hypot(k_east, k_north)
    wave_band = (radial >= 1.0 / 500.0) & (radial <= 1.0 / 40.0)
    for column, (label, _, _) in enumerate(pair_definitions):
        cross = cross_arrays[f"cross_{label.replace('-', '_')}"]
        reference_magnitude = float(np.max(np.abs(cross)[wave_band]))
        magnitude_db = 20.0 * np.log10(
            np.maximum(np.abs(cross) / reference_magnitude, np.finfo(float).tiny)
        )
        mag_image = axes[0, column].pcolormesh(
            k_east * 1000,
            k_north * 1000,
            magnitude_db,
            shading="auto",
            cmap="magma",
            vmin=-35,
            vmax=0,
        )
        phase_values = np.ma.masked_where(
            (magnitude_db < -20.0) | (~wave_band), np.angle(cross)
        )
        phase_image = axes[1, column].pcolormesh(
            k_east * 1000,
            k_north * 1000,
            phase_values,
            shading="auto",
            cmap="twilight",
            vmin=-np.pi,
            vmax=np.pi,
        )
        for axis in axes[:, column]:
            axis.scatter(
                selected["k_east_cycles_per_m"] * 1000,
                selected["k_north_cycles_per_m"] * 1000,
                marker="x",
                color="cyan",
                s=55,
            )
            axis.set_xlim(-26, 26)
            axis.set_ylim(-26, 26)
            axis.set_aspect("equal")
            axis.set_xlabel("East cycles/km")
        axes[0, column].set_title(f"{label} magnitude")
        axes[1, column].set_title(f"{label} phase")
    axes[0, 0].set_ylabel("North cycles/km")
    axes[1, 0].set_ylabel("North cycles/km")
    fig.colorbar(mag_image, ax=axes[0, :], label="Magnitude (dB relative)", shrink=0.8)
    fig.colorbar(phase_image, ax=axes[1, :], label="Phase (rad)", shrink=0.8)
    fig.suptitle(
        f"{roi_name}: intensity cross-spectra, F_secondary × conj(F_reference)"
    )
    figure_path = output_dir / f"{roi_name}_cross_spectra.png"
    fig.savefig(figure_path, dpi=180)
    plt.close(fig)
    return {
        "computed": True,
        "input_domain": "detrended and spatially windowed sub-look intensity",
        "period_conversion_performed": False,
        "selected_peak": selected,
        "pairs": pair_metrics,
        "phase_closure": closure,
        "npz": str(npz_path.resolve()),
        "figure": str(figure_path.resolve()),
    }


def land_shift_controls(
    displays: list[np.ndarray],
    ground_jacobian: np.ndarray,
    time_mapping: dict[str, Any],
) -> dict[str, Any]:
    centers = {
        int(item["look_index"]): float(item["effective_early_center_late_s"][1])
        for item in time_mapping["looks"]
    }
    pairs = [("1-2", 0, 1), ("2-3", 1, 2), ("1-3", 0, 2)]
    output: dict[str, Any] = {}
    original_pixel_shifts: dict[str, np.ndarray] = {}
    for label, reference, secondary in pairs:
        # Point-like land scatterers span more than six orders of magnitude in
        # intensity.  Raw phase correlation can therefore lock onto a sidelobe
        # associated with one or two changing bright targets.  Registration on
        # log intensity retains the stable structural content.  Keep the raw
        # result in the audit trail so this choice is explicit and testable.
        reference_log = np.log1p(displays[reference])
        secondary_log = np.log1p(displays[secondary])
        metrics = phase_correlation_shift(reference_log, secondary_log)
        raw_metrics = phase_correlation_shift(
            displays[reference], displays[secondary]
        )
        reference_centered = reference_log - np.mean(reference_log)
        secondary_centered = secondary_log - np.mean(secondary_log)
        zero_shift_pearson = float(
            np.sum(reference_centered * secondary_centered)
            / np.sqrt(
                np.sum(reference_centered**2) * np.sum(secondary_centered**2)
            )
        )
        raw_candidate_shift = np.asarray(
            raw_metrics[
                "subpixel_displacement_secondary_relative_to_reference_row_col"
            ],
            dtype=np.float64,
        )
        raw_candidate_log_pearson = overlap_pearson_at_integer_shift(
            reference_log, secondary_log, raw_candidate_shift
        )
        multiscale_log_results = {
            str(sigma): phase_correlation_shift(
                gaussian_filter(reference_log, sigma=sigma),
                gaussian_filter(secondary_log, sigma=sigma),
            )["subpixel_displacement_secondary_relative_to_reference_row_col"]
            for sigma in (1.0, 2.0, 4.0, 8.0)
        }
        downsample_shift = np.asarray(
            metrics["subpixel_displacement_secondary_relative_to_reference_row_col"],
            dtype=np.float64,
        )
        original_shift = np.array([downsample_shift[0], 8.0 * downsample_shift[1]])
        ground_en = ground_jacobian @ original_shift
        original_pixel_shifts[label] = original_shift
        output[label] = {
            **metrics,
            "registration_preprocessing": "log1p(intensity)",
            "zero_shift_log_intensity_pearson_correlation": zero_shift_pearson,
            "raw_candidate_log_intensity_pearson_correlation": raw_candidate_log_pearson,
            "multiscale_log_intensity_phase_correlation_shifts_display_pixels": multiscale_log_results,
            "raw_intensity_phase_correlation_diagnostic": raw_metrics,
            "display_column_block_average_factor": 8,
            "original_sicd_pixel_displacement_row_col": original_shift.tolist(),
            "ground_displacement_east_north_m": ground_en.tolist(),
            "ground_displacement_magnitude_m": float(np.linalg.norm(ground_en)),
            "ground_displacement_bearing_deg": float(
                math.degrees(math.atan2(ground_en[0], ground_en[1])) % 360.0
            ),
            "effective_secondary_minus_reference_s": centers[secondary + 1]
            - centers[reference + 1],
        }
    closure_pixels = original_pixel_shifts["1-3"] - (
        original_pixel_shifts["1-2"] + original_pixel_shifts["2-3"]
    )
    closure_ground = ground_jacobian @ closure_pixels
    return {
        "domain": "log1p of 8-column block-averaged land intensity; approximately isotropic ground pixels",
        "cross_convention": "F_secondary * conj(F_reference)",
        "pairs": output,
        "shift_closure_13_minus_12_plus_23_original_pixels": closure_pixels.tolist(),
        "shift_closure_ground_east_north_m": closure_ground.tolist(),
        "shift_closure_ground_magnitude_m": float(np.linalg.norm(closure_ground)),
        "complex_sublook_note": "The three complex sub-looks occupy disjoint Doppler bands, so land registration and deterministic phase-ramp checks are performed on their intensity images. Log compression prevents a few extreme point scatterers from dominating phase correlation; raw-intensity results are retained as diagnostics.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=VANDENBERG / "results" / "sublooks_complex" / "SUBLOOK_MANIFEST.json",
    )
    parser.add_argument(
        "--rois", type=Path, default=VANDENBERG / "roi" / "ROIS.json"
    )
    parser.add_argument(
        "--time-mapping",
        type=Path,
        default=VANDENBERG / "metadata" / "CPHD_DOPPLER_TIME_MAPPING.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=VANDENBERG / "results" / "analysis_block3",
    )
    parser.add_argument("--workers", type=int, default=-1)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    roi_document = json.loads(args.rois.read_text(encoding="utf-8"))
    time_mapping = json.loads(args.time_mapping.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    land_displays: list[np.ndarray] | None = None
    land_jacobian: np.ndarray | None = None

    for roi_name, roi in roi_document["rois"].items():
        print(f"analyzing {roi_name}", flush=True)
        jacobian = np.asarray(
            roi["local_ground_jacobian_EN_m_per_pixel"], dtype=np.float64
        )
        bounds = roi["sicd_bounds"]
        shape = (int(bounds["rows"]), int(bounds["cols"]))
        row_extent, col_extent = roi["approximate_ground_extent_row_col_m"]
        row_bearing = float(roi["local_row_axis_bearing_deg_clockwise_from_north"])
        col_bearing = float(roi["local_col_axis_bearing_deg_clockwise_from_north"])
        spectra: list[np.ndarray] = []
        powers: list[np.ndarray] = []
        displays: list[np.ndarray] = []
        candidates_by_look: list[list[dict[str, Any]]] = []
        intensity_statistics: list[dict[str, Any]] = []
        k_east = k_north = None
        index_vectors = None
        full_complex = np.load(
            manifest["full_aperture_outputs"][roi_name]["path"], mmap_mode="r"
        )
        full_intensity = intensity_from_complex(full_complex)
        full_display = block_average_columns(full_intensity, factor=8)
        full_intensity_statistics = {
            "mean": float(np.mean(full_intensity, dtype=np.float64)),
            "standard_deviation": float(np.std(full_intensity, dtype=np.float64)),
            "percentiles_1_50_99_99_9": np.percentile(
                full_intensity, [1, 50, 99, 99.9]
            ).tolist(),
        }
        del full_intensity, full_complex
        for record in manifest["outputs"][roi_name]:
            complex_data = np.load(record["path"], mmap_mode="r")
            intensity = intensity_from_complex(complex_data)
            displays.append(block_average_columns(intensity, factor=8))
            percentiles = np.percentile(intensity, [1, 50, 99, 99.9])
            intensity_statistics.append(
                {
                    "look_index": int(record["look_index"]),
                    "mean": float(np.mean(intensity, dtype=np.float64)),
                    "standard_deviation": float(np.std(intensity, dtype=np.float64)),
                    "percentiles_1_50_99_99_9": percentiles.tolist(),
                }
            )
            spectrum, indices = intensity_spectrum_crop(
                intensity, half_width=64, workers=args.workers
            )
            if index_vectors is None:
                index_vectors = indices
                k_east, k_north, _, _ = physical_frequency_grid(
                    shape, indices, jacobian
                )
            spectra.append(spectrum)
            power = np.abs(spectrum.astype(np.complex128)) ** 2
            powers.append(power)
            candidates = find_peak_candidates(power, k_east, k_north)
            candidates_by_look.append(
                [enrich_candidate(item, row_bearing, col_bearing) for item in candidates]
            )
            del intensity, complex_data

        stability = match_stable_peak(candidates_by_look)
        if stability["matched_candidates"]:
            stability["matched_candidates"] = [
                enrich_candidate(item, row_bearing, col_bearing)
                for item in stability["matched_candidates"]
            ]
            mean_wavevector = stability["mean_wavevector_bearing_deg_mod_180"]
            mean_crest = stability["mean_crest_orientation_deg_mod_180"]
            stability["mean_wavevector_difference_from_range_axis_deg"] = axial_difference_deg(
                mean_wavevector, row_bearing % 180.0
            )
            stability["mean_wavevector_difference_from_azimuth_axis_deg"] = axial_difference_deg(
                mean_wavevector, col_bearing % 180.0
            )
            stability["mean_crest_difference_from_range_axis_deg"] = axial_difference_deg(
                mean_crest, row_bearing % 180.0
            )
            stability["mean_crest_difference_from_azimuth_axis_deg"] = axial_difference_deg(
                mean_crest, col_bearing % 180.0
            )
            stability["orientation_semantics"] = (
                "The 2-D FFT peak gives the modulation wavevector; visible crest/stripe "
                "orientation is perpendicular (+90 degrees, modulo 180)."
            )

        intensity_figure = args.output_dir / f"{roi_name}_three_look_intensity.png"
        difference_figure = args.output_dir / f"{roi_name}_sublook_differences.png"
        spectrum_figure = args.output_dir / f"{roi_name}_three_look_power_spectrum.png"
        plot_intensities(
            roi_name,
            full_display,
            displays,
            row_extent,
            col_extent,
            row_bearing,
            col_bearing,
            intensity_figure,
        )
        plot_normalized_differences(
            roi_name,
            displays,
            row_extent,
            col_extent,
            difference_figure,
        )
        plot_power_spectra(
            roi_name,
            powers,
            k_east,
            k_north,
            stability.get("matched_candidates", []),
            spectrum_figure,
        )
        spectrum_npz = args.output_dir / f"{roi_name}_spectrum_crops.npz"
        np.savez_compressed(
            spectrum_npz,
            k_east_cycles_per_m=k_east,
            k_north_cycles_per_m=k_north,
            look1_spectrum=spectra[0],
            look2_spectrum=spectra[1],
            look3_spectrum=spectra[2],
            look1_power=powers[0],
            look2_power=powers[1],
            look3_power=powers[2],
        )

        is_ocean = str(roi["kind"]).startswith("ocean")
        if is_ocean and stability["robust"]:
            cross = compute_cross_spectra(
                roi_name,
                spectra,
                stability,
                k_east,
                k_north,
                time_mapping,
                args.output_dir,
            )
        else:
            cross = {
                "computed": False,
                "reason": (
                    "ROI is not ocean."
                    if not is_ocean
                    else "No three-look peak passed the predeclared robustness thresholds."
                ),
            }
        results[roi_name] = {
            "roi": roi,
            "full_aperture_intensity_statistics": full_intensity_statistics,
            "intensity_statistics": intensity_statistics,
            "peak_search": {
                "wavelength_band_m": [40.0, 500.0],
                "spatial_preprocessing": "global plane removal + energy-normalized 2-D Tukey(alpha=0.1)",
                "conjugate_pair_treatment": "centro-symmetric power average; one half-plane retained",
                "candidates_by_look": candidates_by_look,
            },
            "three_look_peak_stability": stability,
            "cross_spectra": cross,
            "artifacts": {
                "intensity_figure": str(intensity_figure.resolve()),
                "normalized_difference_figure": str(difference_figure.resolve()),
                "power_spectrum_figure": str(spectrum_figure.resolve()),
                "spectrum_crop_npz": str(spectrum_npz.resolve()),
                "complex_master_arrays": [item["path"] for item in manifest["outputs"][roi_name]],
            },
        }
        if roi_name == "land_control":
            land_displays = displays
            land_jacobian = jacobian

    if land_displays is None or land_jacobian is None:
        raise ValueError("land-control ROI was not processed")
    land_controls = land_shift_controls(land_displays, land_jacobian, time_mapping)

    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Block 3 fixed three-look analysis only",
        "guardrails": {
            "dwell_sweep_5_to_16_s_performed": False,
            "bathymetric_inversion_performed": False,
            "cross_phase_to_period_conversion_performed": False,
            "gec_used_for_wave_spectrum": False,
            "small_azimuth_crop_before_doppler_decomposition": False,
        },
        "durations_kept_distinct": time_mapping["durations_kept_distinct"],
        "time_mapping": {
            "source": str(args.time_mapping.resolve()),
            "look_effective_centers_s": {
                str(item["look_index"]): item["effective_early_center_late_s"][1]
                for item in time_mapping["looks"]
            },
            "ordering": "look 1 late, look 2 central, look 3 early",
        },
        "cross_spectrum_convention": "F_secondary * conj(F_reference)",
        "cross_spectrum_domain_choice": {
            "chosen_domain": "intensity images derived from the preserved complex sub-looks",
            "primary_source": "Li, Mouche, Stopa & Chapron (2019), JGR Oceans, doi:10.1029/2018JC014638, section 2.2.1",
            "source_url": "https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2018JC014638",
            "source_method_summary": "The SLC azimuth spectrum is divided into three non-overlapping parts, inverse transformed into sub-look intensity images, and 2-D image cross-spectra are then formed.",
        },
        "results": results,
        "land_control_deterministic_terms": land_controls,
    }
    metrics_path = args.output_dir / "BLOCK3_SPECTRAL_METRICS.json"
    metrics_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(metrics_path)


if __name__ == "__main__":
    main()

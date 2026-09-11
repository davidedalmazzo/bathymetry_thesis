"""Moderate SAR-only sensitivity analysis around the frozen Block-4 estimator."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from analyze_block4_phase_timeseries import phase_estimator
from umbra_sar.wave_analysis import intensity_spectrum_crop, physical_frequency_grid


ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "Vandenberg"
OUT = V / "results/analysis_block5"
FROZEN_PATH = OUT / "BLOCK5_FROZEN_INPUTS.json"
WIDTH_NPZ = OUT / "BLOCK5_WIDTH_SENSITIVITY_SPECTRA.npz"
WIDTH_FORMATION = OUT / "BLOCK5_WIDTH_FORMATION.json"
BASELINE_NPZ = V / "results/analysis_block4/nearshore_sliding_spectrum_crops.npz"
BLOCK4_MANIFEST = V / "results/block4_sliding_complex/BLOCK4_SLIDING_MANIFEST.json"
BLOCK3_METRICS = V / "results/analysis_block3/BLOCK3_SPECTRAL_METRICS.json"
ROI_PATH = V / "roi/ROIS.json"
PATCH_CENTER = (60, 63)


def compact(estimator: dict[str, Any]) -> dict[str, Any]:
    fit = estimator["fit_direct_reference_phase"]
    return {
        "temporal_unwrapping_justified": estimator[
            "temporal_unwrapping_justified"
        ],
        "unwrapping_criteria": estimator["unwrapping_criteria"],
        "minimum_adjacent_coherence": min(
            estimator["adjacent_magnitude_squared_coherence"]
        ),
        "fit": fit,
    }


def fit_values(records: dict[str, dict[str, Any]]) -> np.ndarray:
    return np.asarray(
        [
            record["fit"]["slope_rad_per_s"]
            for record in records.values()
            if record.get("fit") is not None
        ],
        dtype=np.float64,
    )


def overlapping_hac_lag(bands: list[dict[str, int]]) -> int:
    maximum = 0
    for lag in range(1, len(bands)):
        any_overlap = False
        for first, second in zip(bands[:-lag], bands[lag:]):
            overlap = min(
                int(first["stop_exclusive"]), int(second["stop_exclusive"])
            ) - max(
                int(first["start_inclusive"]), int(second["start_inclusive"])
            )
            any_overlap |= overlap > 0
        if any_overlap:
            maximum = lag
    return maximum


def main() -> None:
    frozen = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    frozen_slope = float(frozen["frozen_sar_only"]["omega_rad_per_s"])
    width_archive = np.load(WIDTH_NPZ)
    width_formation = json.loads(WIDTH_FORMATION.read_text(encoding="utf-8"))
    baseline_archive = np.load(BASELINE_NPZ)
    baseline_spectra = baseline_archive["spectra"]
    baseline_times = baseline_archive["time_s"]
    baseline_center = tuple(int(value) for value in baseline_archive["fixed_center"])
    if baseline_center != PATCH_CENTER:
        raise ValueError(f"Unexpected baseline patch center: {baseline_center}")

    width_results: dict[str, dict[str, Any]] = {}
    for width_index, width in enumerate(width_archive["widths_s"]):
        formation = next(
            item
            for item in width_formation["formation_records"]
            if float(item["width_s"]) == float(width)
        )
        hac_lag = overlapping_hac_lag(formation["bands"])
        estimator = phase_estimator(
            width_archive["spectra"][width_index],
            PATCH_CENTER,
            width_archive["physical_center_times_s"],
            2,
            hac_lag,
        )
        width_results[f"{float(width):.1f}_s"] = {
            "requested_width_s": float(width),
            "realized_width_s": formation["realized_nominal_width_s"],
            "sample_count": int(width_archive["spectra"].shape[1]),
            "common_chronological_indices": width_archive[
                "chronological_indices"
            ].tolist(),
            "hac_lag_from_band_overlap": hac_lag,
            **compact(estimator),
        }

    patch_results: dict[str, dict[str, Any]] = {}
    for radius in range(1, 6):
        patch_results[f"radius_{radius}"] = {
            "center_row_col": list(PATCH_CENTER),
            "radius_bins": radius,
            **compact(
                phase_estimator(
                    baseline_spectra,
                    PATCH_CENTER,
                    baseline_times,
                    radius,
                    4,
                )
            ),
        }
    for name, delta in (
        ("center_row_minus_1", (-1, 0)),
        ("center_row_plus_1", (1, 0)),
        ("center_col_minus_1", (0, -1)),
        ("center_col_plus_1", (0, 1)),
    ):
        center = (PATCH_CENTER[0] + delta[0], PATCH_CENTER[1] + delta[1])
        patch_results[name] = {
            "center_row_col": list(center),
            "radius_bins": 2,
            **compact(
                phase_estimator(
                    baseline_spectra, center, baseline_times, 2, 4
                )
            ),
        }

    overlap_results: dict[str, dict[str, Any]] = {}
    overlap_variants = {
        "step_1_nominal_80pct": (np.arange(11), 4),
        "step_2_start_1_nominal_60pct": (np.arange(0, 11, 2), 2),
        "step_2_start_2_nominal_60pct": (np.arange(1, 11, 2), 2),
        "step_3_start_1_nominal_40pct": (np.arange(0, 11, 3), 1),
        "step_3_start_2_nominal_40pct": (np.arange(1, 11, 3), 1),
        "step_3_start_3_nominal_40pct": (np.arange(2, 11, 3), 1),
    }
    for name, (indices, hac_lag) in overlap_variants.items():
        estimator = phase_estimator(
            baseline_spectra[indices],
            PATCH_CENTER,
            baseline_times[indices],
            2,
            hac_lag,
        )
        overlap_results[name] = {
            "zero_based_indices": indices.tolist(),
            "chronological_indices": (indices + 1).tolist(),
            "sample_count": int(indices.size),
            "hac_lag": hac_lag,
            **compact(estimator),
        }

    manifest = json.loads(BLOCK4_MANIFEST.read_text(encoding="utf-8"))
    rois = json.loads(ROI_PATH.read_text(encoding="utf-8"))["rois"]
    block3 = json.loads(BLOCK3_METRICS.read_text(encoding="utf-8"))
    selected = block3["results"]["nearshore"]["cross_spectra"]["selected_peak"]
    target_k = np.asarray(
        [selected["k_east_cycles_per_m"], selected["k_north_cycles_per_m"]],
        dtype=np.float64,
    )
    jacobian = np.asarray(
        rois["nearshore"]["local_ground_jacobian_EN_m_per_pixel"],
        dtype=np.float64,
    )
    roi_variants = {
        "range_pixel_low_80pct": (slice(0, 960), slice(0, 9600)),
        "range_pixel_high_80pct": (slice(240, 1200), slice(0, 9600)),
        "azimuth_pixel_low_80pct": (slice(0, 1200), slice(0, 7680)),
        "azimuth_pixel_high_80pct": (slice(0, 1200), slice(1920, 9600)),
        "central_80pct_each_axis": (slice(120, 1080), slice(960, 8640)),
    }
    variant_spectra: dict[str, list[np.ndarray]] = {
        name: [] for name in roi_variants
    }
    variant_indices: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    records = manifest["outputs"]["nearshore"]
    for sequence_index, record in enumerate(records, start=1):
        complex_data = np.load(record["path"], mmap_mode="r")
        intensity = np.asarray(
            complex_data.real * complex_data.real
            + complex_data.imag * complex_data.imag,
            dtype=np.float32,
        )
        del complex_data
        for name, slices in roi_variants.items():
            spectrum, indices = intensity_spectrum_crop(
                intensity[slices], half_width=64, workers=-1
            )
            variant_spectra[name].append(spectrum)
            variant_indices[name] = indices
        del intensity
        print(f"ROI variants: processed look {sequence_index}/11", flush=True)

    roi_results: dict[str, dict[str, Any]] = {
        "baseline_full_1200x9600": {
            "slices_row_col": [[0, 1200], [0, 9600]],
            "shape": [1200, 9600],
            "fixed_center_row_col": list(PATCH_CENTER),
            "target_k_east_north_cycles_per_m": target_k.tolist(),
            **compact(
                phase_estimator(
                    baseline_spectra,
                    PATCH_CENTER,
                    baseline_times,
                    2,
                    4,
                )
            ),
        }
    }
    for name, slices in roi_variants.items():
        spectra = np.asarray(variant_spectra[name], dtype=np.complex64)
        shape = (
            slices[0].stop - slices[0].start,
            slices[1].stop - slices[1].start,
        )
        k_east, k_north, _, _ = physical_frequency_grid(
            shape, variant_indices[name], jacobian
        )
        distance = (k_east - target_k[0]) ** 2 + (k_north - target_k[1]) ** 2
        center = tuple(
            int(value) for value in np.unravel_index(np.argmin(distance), distance.shape)
        )
        estimator = phase_estimator(spectra, center, baseline_times, 2, 4)
        roi_results[name] = {
            "slices_row_col": [
                [slices[0].start, slices[0].stop],
                [slices[1].start, slices[1].stop],
            ],
            "shape": list(shape),
            "fixed_center_row_col": list(center),
            "target_k_east_north_cycles_per_m": target_k.tolist(),
            "nearest_bin_k_east_north_cycles_per_m": [
                float(k_east[center]),
                float(k_north[center]),
            ],
            **compact(estimator),
        }

    families = {
        "look_width": width_results,
        "overlap_subsampling": overlap_results,
        "roi": roi_results,
        "spectral_patch": patch_results,
    }
    summary = {}
    all_slopes = []
    for family, family_records in families.items():
        slopes = fit_values(family_records)
        periods = 2.0 * np.pi / np.abs(slopes)
        relative = (slopes - frozen_slope) / abs(frozen_slope)
        summary[family] = {
            "valid_fit_count": int(slopes.size),
            "all_negative": bool(np.all(slopes < 0)),
            "slope_range_rad_per_s": [float(np.min(slopes)), float(np.max(slopes))],
            "period_range_s": [float(np.min(periods)), float(np.max(periods))],
            "maximum_absolute_relative_slope_change": float(np.max(np.abs(relative))),
        }
        all_slopes.extend(slopes.tolist())
    all_slopes_array = np.asarray(all_slopes)
    robustness = {
        "all_valid_variants_preserve_negative_sign": bool(
            np.all(all_slopes_array < 0)
        ),
        "median_slope_rad_per_s": float(np.median(all_slopes_array)),
        "median_period_s": float(2.0 * np.pi / abs(np.median(all_slopes_array))),
        "all_variant_slope_range_rad_per_s": [
            float(np.min(all_slopes_array)),
            float(np.max(all_slopes_array)),
        ],
        "all_variant_period_range_s": [
            float(np.min(2.0 * np.pi / np.abs(all_slopes_array))),
            float(np.max(2.0 * np.pi / np.abs(all_slopes_array))),
        ],
        "interpretation": "Sign and order of magnitude are robust if all families remain negative; the family ranges quantify processing sensitivity rather than replacing the frozen primary estimate.",
    }

    fig, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    for ax, (family, family_records) in zip(axes.flat, families.items()):
        labels = []
        slopes = []
        for name, record in family_records.items():
            if record.get("fit") is None:
                continue
            labels.append(name)
            slopes.append(record["fit"]["slope_rad_per_s"])
        positions = np.arange(len(slopes))
        ax.bar(positions, slopes, color="tab:blue", alpha=0.8)
        ax.axhline(frozen_slope, color="tab:red", linestyle="--", label="frozen -0.350972")
        ax.set_xticks(positions, labels, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("Slope [rad/s]")
        ax.set_title(family.replace("_", " ").title())
        ax.grid(axis="y", alpha=0.25)
        ax.legend(fontsize=8)
    plot_path = OUT / "BLOCK5_SAR_SENSITIVITY.png"
    fig.savefig(plot_path, dpi=180)
    plt.close(fig)

    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Moderate SAR-only sensitivity of nearshore phase slope",
        "frozen_primary": frozen["frozen_sar_only"],
        "external_data_used_in_sensitivity": False,
        "families": families,
        "family_summaries": summary,
        "robustness_summary": robustness,
        "artifacts": {
            "plot": str(plot_path),
            "width_spectra": str(WIDTH_NPZ),
        },
        "guardrails": {
            "full_5_to_16_s_dwell_sweep_performed": False,
            "only_local_widths_5_5_6_0_6_5_s": True,
            "bathymetric_inversion_performed": False,
            "peak_reselected_per_variant": False,
            "fixed_physical_peak_or_declared_one_bin_offsets": True,
        },
    }
    json_path = OUT / "BLOCK5_SAR_SENSITIVITY.json"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {plot_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

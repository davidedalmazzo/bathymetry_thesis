"""Form only the nearshore spectra needed for a 5.5/6.0/6.5-s width check.

This is deliberately not the requested future 5-16 s dwell sweep. The common
interior centers 2-10 are used because 6.5 s does not fit inside the processed
SICD support at the two edge centers.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numpy.lib.format import open_memmap
from sarpy.io.complex.converter import open_complex
from sarpy.io.complex.sicd_elements.SICD import SICDType

from umbra_sar.subaperture import (
    SicdSubapertureContext,
    SubapertureBand,
    image_to_shifted_spectrum,
    make_window,
    sublook_from_spectrum,
)
from umbra_sar.wave_analysis import intensity_spectrum_crop


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"
OUTPUT_DIR = VANDENBERG / "results" / "analysis_block5"
WORK_DIR = OUTPUT_DIR / "_width_work"
OUTPUT_NPZ = OUTPUT_DIR / "BLOCK5_WIDTH_SENSITIVITY_SPECTRA.npz"
OUTPUT_JSON = OUTPUT_DIR / "BLOCK5_WIDTH_FORMATION.json"
WIDTHS_S = (5.5, 6.0, 6.5)
COMMON_INDICES = tuple(range(2, 11))


def main() -> None:
    if OUTPUT_NPZ.exists() or OUTPUT_JSON.exists():
        raise FileExistsError("Block-5 width artifacts already exist; refusing overwrite")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if any(WORK_DIR.iterdir()):
        raise FileExistsError(f"Temporary work directory is not empty: {WORK_DIR}")

    sicd_path = VANDENBERG / "2025-02-16-18-55-44_UMBRA-10_SICD.nitf"
    plan_path = VANDENBERG / "metadata" / "BLOCK4_SLIDING_LOOK_PLAN.json"
    fixed_plan_path = VANDENBERG / "metadata" / "SUBAPERTURE_PLAN_6S.json"
    roi_path = VANDENBERG / "roi" / "ROIS.json"
    block4_manifest_path = (
        VANDENBERG
        / "results"
        / "block4_sliding_complex"
        / "BLOCK4_SLIDING_MANIFEST.json"
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    fixed_plan = json.loads(fixed_plan_path.read_text(encoding="utf-8"))
    roi = json.loads(roi_path.read_text(encoding="utf-8"))["rois"]["nearshore"]
    block4_manifest = json.loads(block4_manifest_path.read_text(encoding="utf-8"))
    sicd_xml = SICDType.from_xml_file(plan["inputs"]["sicd_xml"])
    context = SicdSubapertureContext.from_sicd(
        sicd_xml,
        cphd_slow_time_dwell_s=float(
            plan["durations_kept_distinct"]["cphd_available_slow_time_dwell_s"]
        ),
    )
    if context.axis.azimuth_axis != 1 or context.axis.azimuth_sgn != -1:
        raise ValueError("Unexpected SICD azimuth convention")

    support_start = int(fixed_plan["support"]["start"])
    support_stop = int(fixed_plan["support"]["stop"])
    support_size = int(fixed_plan["support"]["size"])
    processed_duration = float(
        plan["durations_kept_distinct"]["sicd_processed_aperture_duration_s"]
    )
    look_plan = {
        int(item["chronological_index"]): item for item in plan["looks_chronological"]
    }
    times = np.asarray(
        [look_plan[index]["effective_early_center_late_s"][1] for index in COMMON_INDICES],
        dtype=np.float64,
    )

    bounds = roi["sicd_bounds"]
    row_start = int(bounds["row_start_inclusive"])
    row_stop = int(bounds["row_stop_exclusive"])
    col_start = int(bounds["col_start_inclusive"])
    col_stop = int(bounds["col_stop_exclusive"])
    roi_shape = (row_stop - row_start, col_stop - col_start)
    expected_shape = (
        int(sicd_xml.ImageData.NumRows),
        int(sicd_xml.ImageData.NumCols),
    )
    all_spectra: list[np.ndarray] = []
    formation_records = []
    started = time.perf_counter()

    # Width 6.0 s already exists and is read without alteration.
    records6 = {
        int(item["chronological_index"]): item
        for item in block4_manifest["outputs"]["nearshore"]
    }
    spectra6 = []
    indices6 = None
    for index in COMMON_INDICES:
        complex_data = np.load(records6[index]["path"], mmap_mode="r")
        intensity = np.asarray(
            complex_data.real * complex_data.real
            + complex_data.imag * complex_data.imag,
            dtype=np.float32,
        )
        spectrum, indices = intensity_spectrum_crop(
            intensity, half_width=64, workers=-1
        )
        del intensity, complex_data
        spectra6.append(spectrum)
        indices6 = indices
    all_spectra.append(np.asarray(spectra6, dtype=np.complex64))
    formation_records.append(
        {
            "width_s": 6.0,
            "source": "reused Block-4 complex looks",
            "common_chronological_indices": list(COMMON_INDICES),
            "spectrum_shape": list(all_spectra[-1].shape),
        }
    )
    print("6.0 s: derived spectra from existing Block-4 looks", flush=True)

    reader = open_complex(str(sicd_path))
    try:
        reader_shapes = tuple(
            tuple(int(value) for value in shape)
            for shape in reader.get_data_size_as_tuple()
        )
        if reader_shapes != (expected_shape,):
            raise ValueError(f"Unexpected SICD shape: {reader_shapes}")

        for width_s in (5.5, 6.5):
            width_bins = int(round(support_size * width_s / processed_duration))
            if width_bins % 2:
                width_bins += 1
            bands = []
            for index in COMMON_INDICES:
                original = look_plan[index]["band"]
                center = 0.5 * (
                    int(original["start_inclusive"])
                    + int(original["stop_exclusive"])
                )
                start = int(round(center - 0.5 * width_bins))
                stop = start + width_bins
                if start < support_start or stop > support_stop:
                    raise ValueError(
                        f"Width {width_s} s does not fit at common index {index}"
                    )
                bands.append(
                    SubapertureBand(
                        start=start,
                        stop=stop,
                        support_start=support_start,
                        support_stop=support_stop,
                        requested_nominal_duration_s=width_s,
                        requested_bandwidth_fraction=width_s / processed_duration,
                        realized_bandwidth_fraction=width_bins / support_size,
                        realized_nominal_duration_s=width_bins
                        / support_size
                        * processed_duration,
                        center_fraction_in_support=(
                            0.5 * (start + stop) - support_start
                        )
                        / support_size,
                        nominal_center_time_from_collect_start_s=float("nan"),
                        timing_model="fixed Block-4 CPHD/PVP center",
                    )
                )
            window, window_metadata = make_window(
                width_bins,
                "tukey",
                tukey_alpha=0.25,
                normalization="energy",
            )
            window = window.astype(np.float32)
            temp_paths = [
                WORK_DIR / f"width_{width_s:.1f}_t{index:02d}_intensity32.npy"
                for index in COMMON_INDICES
            ]
            maps = [
                open_memmap(path, mode="w+", dtype=np.float32, shape=roi_shape)
                for path in temp_paths
            ]
            width_started = time.perf_counter()
            nonfinite_count = 0
            print(
                f"{width_s:.1f} s: forming {len(bands)} nearshore looks from all {expected_shape[1]} azimuth columns",
                flush=True,
            )
            for block_start in range(row_start, row_stop, 64):
                block_stop = min(block_start + 64, row_stop)
                source = np.asarray(
                    reader[
                        (
                            slice(block_start, block_stop),
                            slice(0, expected_shape[1]),
                            0,
                        )
                    ],
                    dtype=np.complex64,
                )
                nonfinite = ~np.isfinite(source)
                nonfinite_count += int(np.count_nonzero(nonfinite))
                if np.any(nonfinite):
                    source[nonfinite] = 0
                shifted = image_to_shifted_spectrum(
                    source,
                    axis=context.axis.azimuth_axis,
                    sgn=context.axis.azimuth_sgn,
                    workers=-1,
                )
                local_rows = slice(block_start - row_start, block_stop - row_start)
                for output_map, band in zip(maps, bands):
                    sublook = sublook_from_spectrum(
                        shifted,
                        band,
                        axis=context.axis.azimuth_axis,
                        sgn=context.axis.azimuth_sgn,
                        window=window,
                        workers=-1,
                    )[:, col_start:col_stop]
                    output_map[local_rows, :] = np.asarray(
                        sublook.real * sublook.real + sublook.imag * sublook.imag,
                        dtype=np.float32,
                    )
                    del sublook
                del shifted, source
                print(
                    f"  rows {block_start}:{block_stop} ({block_stop-row_start}/{roi_shape[0]})",
                    flush=True,
                )
            for output_map in maps:
                output_map.flush()
            del output_map, maps

            spectra = []
            indices_current = None
            for path in temp_paths:
                intensity = np.load(path, mmap_mode="r")
                spectrum, indices = intensity_spectrum_crop(
                    intensity, half_width=64, workers=-1
                )
                spectra.append(spectrum)
                indices_current = indices
                del intensity
            all_spectra.append(np.asarray(spectra, dtype=np.complex64))

            work_resolved = WORK_DIR.resolve()
            deleted_bytes = 0
            for path in temp_paths:
                resolved = path.resolve()
                if resolved.parent != work_resolved:
                    raise RuntimeError(f"Refusing to delete temp outside work dir: {resolved}")
                deleted_bytes += resolved.stat().st_size
                resolved.unlink()
            formation_records.append(
                {
                    "width_s": width_s,
                    "requested_width_s": width_s,
                    "width_bins": width_bins,
                    "realized_nominal_width_s": bands[0].realized_nominal_duration_s,
                    "bands": [
                        {"start_inclusive": band.start, "stop_exclusive": band.stop}
                        for band in bands
                    ],
                    "window": asdict(window_metadata),
                    "source": "new nearshore-only formation from full SICD azimuth extent",
                    "azimuth_pre_crop_before_doppler_decomposition": False,
                    "nonfinite_source_values_replaced": nonfinite_count,
                    "elapsed_s": time.perf_counter() - width_started,
                    "temporary_intensity_bytes_deleted_after_spectra": deleted_bytes,
                    "spectrum_shape": list(all_spectra[-1].shape),
                }
            )
            if indices6 is None or indices_current is None:
                raise RuntimeError("Missing FFT crop indices")
            if not (
                np.array_equal(indices6[0], indices_current[0])
                and np.array_equal(indices6[1], indices_current[1])
            ):
                raise RuntimeError("Spectrum crops do not share FFT indices")
            print(f"{width_s:.1f} s: spectra complete; temporary intensities removed", flush=True)
    finally:
        reader.close()

    # Reorder widths from the formation order [6.0, 5.5, 6.5] to [5.5, 6.0, 6.5].
    spectra_by_width = {record["width_s"]: array for record, array in zip(formation_records, all_spectra)}
    ordered = np.asarray([spectra_by_width[width] for width in WIDTHS_S], dtype=np.complex64)
    assert indices6 is not None
    np.savez_compressed(
        OUTPUT_NPZ,
        spectra=ordered,
        widths_s=np.asarray(WIDTHS_S, dtype=np.float64),
        chronological_indices=np.asarray(COMMON_INDICES, dtype=np.int64),
        physical_center_times_s=times,
        fft_crop_row_indices=indices6[0],
        fft_crop_col_indices=indices6[1],
    )
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Moderate local look-width sensitivity, not a dwell sweep",
        "source_sicd": str(sicd_path.resolve()),
        "source_sicd_size_bytes": sicd_path.stat().st_size,
        "widths_s": list(WIDTHS_S),
        "common_chronological_indices": list(COMMON_INDICES),
        "physical_center_times_s": times.tolist(),
        "edge_centers_excluded": [1, 11],
        "edge_exclusion_reason": "6.5-s support exceeds the processed SICD support at centers 1 and 11",
        "formation_records": sorted(formation_records, key=lambda item: item["width_s"]),
        "output_npz": str(OUTPUT_NPZ),
        "elapsed_s": time.perf_counter() - started,
        "guardrails": {
            "full_dwell_sweep_performed": False,
            "bathymetric_inversion_performed": False,
            "complex_sublook_files_persisted": False,
            "only_derived_spectrum_crops_persisted": True,
        },
    }
    OUTPUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_NPZ}")
    print(f"Wrote {OUTPUT_JSON}")
    print(f"elapsed_s={summary['elapsed_s']:.3f}")


if __name__ == "__main__":
    main()

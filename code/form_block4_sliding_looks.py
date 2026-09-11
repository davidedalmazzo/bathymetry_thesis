"""Form Block-4 overlapping complex looks for nearshore and land control.

Every requested SICD range row is transformed across all 107800 azimuth
columns. ROI columns are cropped only after inverse transformation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
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


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sicd",
        type=Path,
        default=VANDENBERG / "2025-02-16-18-55-44_UMBRA-10_SICD.nitf",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=VANDENBERG / "metadata" / "BLOCK4_SLIDING_LOOK_PLAN.json",
    )
    parser.add_argument(
        "--rois", type=Path, default=VANDENBERG / "roi" / "ROIS.json"
    )
    parser.add_argument(
        "--block3-dir",
        type=Path,
        default=VANDENBERG / "results" / "sublooks_complex",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=VANDENBERG / "results" / "block4_sliding_complex",
    )
    parser.add_argument("--row-chunk", type=int, default=64)
    parser.add_argument("--workers", type=int, default=-1)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    rois = json.loads(args.rois.read_text(encoding="utf-8"))["rois"]
    sicd_xml = SICDType.from_xml_file(plan["inputs"]["sicd_xml"])
    context = SicdSubapertureContext.from_sicd(
        sicd_xml,
        cphd_slow_time_dwell_s=float(
            plan["durations_kept_distinct"]["cphd_available_slow_time_dwell_s"]
        ),
    )
    if context.axis.azimuth_sgn != -1 or context.axis.azimuth_axis != 1:
        raise ValueError("Block 4 requires the already validated Col.Sgn=-1 axis-1 convention")
    fixed_plan = json.loads(
        (VANDENBERG / "metadata" / "SUBAPERTURE_PLAN_6S.json").read_text(
            encoding="utf-8"
        )
    )
    fixed_support_start = int(fixed_plan["support"]["start"])
    fixed_support_stop = int(fixed_plan["support"]["stop"])
    fixed_support_size = int(fixed_plan["support"]["size"])
    processed_duration = context.durations.processed_aperture_duration_s

    look_objects: dict[int, SubapertureBand] = {}
    window = None
    for item in plan["looks_chronological"]:
        band_info = item["band"]
        start = int(band_info["start_inclusive"])
        stop = int(band_info["stop_exclusive"])
        center_fraction = (
            0.5 * (start + stop) - fixed_support_start
        ) / fixed_support_size
        band = SubapertureBand(
            start=start,
            stop=stop,
            support_start=fixed_support_start,
            support_stop=fixed_support_stop,
            requested_nominal_duration_s=6.0,
            requested_bandwidth_fraction=6.0 / processed_duration,
            realized_bandwidth_fraction=(stop - start) / fixed_support_size,
            realized_nominal_duration_s=(stop - start)
            / fixed_support_size
            * processed_duration,
            center_fraction_in_support=center_fraction,
            nominal_center_time_from_collect_start_s=float("nan"),
            timing_model="CPHD/PVP physical centers stored in Block-4 plan",
        )
        look_objects[int(item["chronological_index"])] = band
        if window is None:
            window, _ = make_window(
                band.size, "tukey", tukey_alpha=0.25, normalization="energy"
            )
        elif band.size != window.size:
            raise ValueError("sliding looks do not share a common width")
    assert window is not None
    window = window.astype(np.float32)

    expected_shape = (
        int(sicd_xml.ImageData.NumRows),
        int(sicd_xml.ImageData.NumCols),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reader = open_complex(str(args.sicd))
    outputs: dict[str, list[dict[str, object]]] = {}
    total_nonfinite = 0
    started = time.perf_counter()
    try:
        reader_shapes = tuple(
            tuple(int(value) for value in shape)
            for shape in reader.get_data_size_as_tuple()
        )
        if reader_shapes != (expected_shape,):
            raise ValueError(f"unexpected SICD reader shape: {reader_shapes}")
        for roi_name in ("nearshore", "land_control"):
            bounds = rois[roi_name]["sicd_bounds"]
            row_start = int(bounds["row_start_inclusive"])
            row_stop = int(bounds["row_stop_exclusive"])
            col_start = int(bounds["col_start_inclusive"])
            col_stop = int(bounds["col_stop_exclusive"])
            roi_shape = (row_stop - row_start, col_stop - col_start)

            generated_items = [
                item
                for item in plan["looks_chronological"]
                if item["reuses_block3_nonoverlap_look"] is None
            ]
            final_paths = [
                args.output_dir
                / f"{roi_name}_sliding_t{int(item['chronological_index']):02d}_complex64.npy"
                for item in generated_items
            ]
            existing = [path.exists() for path in final_paths]
            if any(existing) and not all(existing):
                raise FileExistsError(
                    f"incomplete existing output set for {roi_name}; refusing overwrite"
                )
            if not all(existing):
                part_paths = [
                    path.with_suffix(path.suffix + ".part") for path in final_paths
                ]
                if any(path.exists() for path in part_paths):
                    raise FileExistsError(
                        f"stale partial output exists for {roi_name}; inspect it before rerun"
                    )
                maps = [
                    open_memmap(path, mode="w+", dtype=np.complex64, shape=roi_shape)
                    for path in part_paths
                ]
                print(
                    f"{roi_name}: forming {len(maps)} new sliding looks; every row uses all {expected_shape[1]} columns",
                    flush=True,
                )
                roi_nonfinite = 0
                for block_start in range(row_start, row_stop, args.row_chunk):
                    block_stop = min(block_start + args.row_chunk, row_stop)
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
                    nonfinite = int(np.count_nonzero(~np.isfinite(source)))
                    if nonfinite:
                        source[~np.isfinite(source)] = 0
                        roi_nonfinite += nonfinite
                    shifted = image_to_shifted_spectrum(
                        source,
                        axis=context.axis.azimuth_axis,
                        sgn=context.axis.azimuth_sgn,
                        workers=args.workers,
                    )
                    local_rows = slice(
                        block_start - row_start, block_stop - row_start
                    )
                    for output_map, item in zip(maps, generated_items):
                        sublook = sublook_from_spectrum(
                            shifted,
                            look_objects[int(item["chronological_index"])],
                            axis=context.axis.azimuth_axis,
                            sgn=context.axis.azimuth_sgn,
                            window=window,
                            workers=args.workers,
                        )
                        output_map[local_rows, :] = sublook[:, col_start:col_stop]
                        del sublook
                    del shifted, source
                    print(
                        f"  {roi_name} rows {block_start}:{block_stop} ({block_stop-row_start}/{row_stop-row_start})",
                        flush=True,
                    )
                total_nonfinite += roi_nonfinite
                for output_map in maps:
                    output_map.flush()
                del output_map, maps
                for part_path, final_path in zip(part_paths, final_paths):
                    os.replace(part_path, final_path)
            else:
                print(f"{roi_name}: reusing {len(final_paths)} completed sliding arrays")

            records_out: list[dict[str, object]] = []
            for item in plan["looks_chronological"]:
                index = int(item["chronological_index"])
                reused = item["reuses_block3_nonoverlap_look"]
                if reused is None:
                    path = args.output_dir / f"{roi_name}_sliding_t{index:02d}_complex64.npy"
                    source_type = "generated_block4_sliding"
                else:
                    path = args.block3_dir / f"{roi_name}_look{int(reused)}_complex64.npy"
                    source_type = "reused_block3_nonoverlap"
                array = np.load(path, mmap_mode="r")
                if array.shape != roi_shape or array.dtype != np.complex64:
                    raise ValueError(f"unexpected array metadata for {path}")
                if not np.all(np.isfinite(array)):
                    raise ValueError(f"nonfinite values in {path}")
                records_out.append(
                    {
                        "chronological_index": index,
                        "path": str(path.resolve()),
                        "source_type": source_type,
                        "reused_block3_look": reused,
                        "shape": list(array.shape),
                        "dtype": str(array.dtype),
                        "size_bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                        "mean_intensity": float(
                            np.mean(np.abs(array) ** 2, dtype=np.float64)
                        ),
                        "band": item["band"],
                        "effective_early_center_late_s": item[
                            "effective_early_center_late_s"
                        ],
                    }
                )
                del array
            outputs[roi_name] = records_out
    finally:
        reader.close()

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_sicd": str(args.sicd.resolve()),
        "source_sicd_size_bytes": args.sicd.stat().st_size,
        "source_plan": str(args.plan.resolve()),
        "source_rois": str(args.rois.resolve()),
        "algorithm": {
            "rois": ["nearshore", "land_control"],
            "range_block_rows": args.row_chunk,
            "azimuth_columns_read_per_transformed_row": expected_shape[1],
            "azimuth_pre_crop_before_doppler_decomposition": False,
            "image_to_shifted_spectrum": "fft",
            "shifted_spectrum_to_image": "ifft",
            "sicd_col_sgn": -1,
            "complex_phase_preserved": True,
            "new_look_count_per_roi": 8,
            "reused_exact_nonoverlap_look_count_per_roi": 3,
        },
        "native_weight": {
            "name": "SVA",
            "samples_present": False,
            "warning": "SVA is declared without WgtFunct; unchanged from Blocks 2/3 and nonblocking",
        },
        "input_nonfinite_values_replaced_with_zero": total_nonfinite,
        "elapsed_seconds": time.perf_counter() - started,
        "outputs": outputs,
        "independent_nonoverlap_set": {
            "preserved_separately": True,
            "directory": str(args.block3_dir.resolve()),
            "chronological_sliding_indices": [1, 6, 11],
        },
        "guardrails": {
            "dwell_sweep_performed": False,
            "bathymetric_inversion_performed": False,
        },
    }
    manifest_path = args.output_dir / "BLOCK4_SLIDING_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    print(f"elapsed_seconds={manifest['elapsed_seconds']:.3f}")


if __name__ == "__main__":
    main()

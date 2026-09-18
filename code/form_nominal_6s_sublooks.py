"""Form the three planned complex SICD sub-looks for reproducible ROIs.

The implementation reads each requested range-row block across *all* SICD
azimuth columns, performs the metadata-directed Doppler FFT and band filtering,
then crops ROI columns only after the inverse transform. This is the key Block-3
anti-bias constraint.
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
VANDENBERG = ROOT / 'umbra/Vandenberg'


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
        default=VANDENBERG / "metadata" / "SUBAPERTURE_PLAN_6S.json",
    )
    parser.add_argument(
        "--rois", type=Path, default=VANDENBERG / "roi" / "ROIS.json"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=VANDENBERG / "results" / "sublooks_complex",
    )
    parser.add_argument("--row-chunk", type=int, default=64)
    parser.add_argument("--workers", type=int, default=-1)
    args = parser.parse_args()

    if args.row_chunk < 1:
        raise ValueError("row chunk must be positive")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    roi_document = json.loads(args.rois.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sicd_xml = SICDType.from_xml_file(str(plan["sicd_xml"]))
    context = SicdSubapertureContext.from_sicd(
        sicd_xml,
        cphd_slow_time_dwell_s=float(
            plan["looks"][0]["durations"]["cphd_slow_time_dwell_s"]
        ),
    )
    bands = [SubapertureBand(**item["band"]) for item in plan["looks"]]
    windows = []
    for item, band in zip(plan["looks"], bands):
        window_info = item["window"]
        window, metrics = make_window(
            band.size,
            str(window_info["kind"]),
            tukey_alpha=float(window_info["tukey_alpha"]),
            normalization=str(window_info["normalization"]),
        )
        if not np.isclose(metrics.applied_scale, window_info["applied_scale"], rtol=0, atol=1e-14):
            raise ValueError("regenerated Doppler window differs from planned window")
        windows.append(window.astype(np.float32))

    expected_shape = (
        int(sicd_xml.ImageData.NumRows),
        int(sicd_xml.ImageData.NumCols),
    )
    reader = open_complex(str(args.sicd))
    started = time.perf_counter()
    outputs: dict[str, list[dict[str, object]]] = {}
    full_aperture_outputs: dict[str, dict[str, object]] = {}
    total_nonfinite = 0
    try:
        reader_shapes = tuple(tuple(int(v) for v in shape) for shape in reader.get_data_size_as_tuple())
        if len(reader_shapes) != 1 or reader_shapes[0] != expected_shape:
            raise ValueError(
                f"reader data shape {reader_shapes} does not match SICD {expected_shape}"
            )
        reader_sicd = reader.get_sicds_as_tuple()[0]
        if int(reader_sicd.Grid.Col.Sgn) != -1:
            raise ValueError("Block-3 plan requires the already validated Col.Sgn=-1")

        for roi_name, roi in roi_document["rois"].items():
            bounds = roi["sicd_bounds"]
            row_start = int(bounds["row_start_inclusive"])
            row_stop = int(bounds["row_stop_exclusive"])
            col_start = int(bounds["col_start_inclusive"])
            col_stop = int(bounds["col_stop_exclusive"])
            roi_shape = (row_stop - row_start, col_stop - col_start)
            roi_records: list[dict[str, object]] = []
            full_final_path = args.output_dir / f"{roi_name}_full_aperture_complex64.npy"
            full_part_path = full_final_path.with_suffix(full_final_path.suffix + ".part")
            existing_look_paths = [
                args.output_dir / f"{roi_name}_look{look_index}_complex64.npy"
                for look_index in range(1, 4)
            ]
            completed_paths = [full_final_path, *existing_look_paths]
            if all(path.exists() for path in completed_paths):
                print(f"ROI {roi_name}: reusing four completed complex64 arrays", flush=True)
                full_array = np.load(full_final_path, mmap_mode="r")
                if full_array.shape != roi_shape or full_array.dtype != np.complex64:
                    raise ValueError(f"invalid existing full-aperture array: {full_final_path}")
                full_aperture_outputs[roi_name] = {
                    "path": str(full_final_path.resolve()),
                    "shape": list(full_array.shape),
                    "dtype": str(full_array.dtype),
                    "size_bytes": full_final_path.stat().st_size,
                    "sha256": sha256_file(full_final_path),
                    "all_finite": bool(np.all(np.isfinite(full_array))),
                    "mean_intensity": float(
                        np.mean(np.abs(full_array) ** 2, dtype=np.float64)
                    ),
                }
                del full_array
                for look_index, final_path in enumerate(existing_look_paths, start=1):
                    array = np.load(final_path, mmap_mode="r")
                    if array.shape != roi_shape or array.dtype != np.complex64:
                        raise ValueError(f"invalid existing sub-look array: {final_path}")
                    finite = bool(np.all(np.isfinite(array)))
                    if not finite:
                        raise ValueError(f"non-finite values in {final_path}")
                    roi_records.append(
                        {
                            "look_index": look_index,
                            "path": str(final_path.resolve()),
                            "shape": list(array.shape),
                            "dtype": str(array.dtype),
                            "size_bytes": final_path.stat().st_size,
                            "sha256": sha256_file(final_path),
                            "all_finite": finite,
                            "mean_intensity": float(
                                np.mean(np.abs(array) ** 2, dtype=np.float64)
                            ),
                            "band": plan["looks"][look_index - 1]["band"],
                            "window": plan["looks"][look_index - 1]["window"],
                        }
                    )
                    del array
                outputs[roi_name] = roi_records
                continue
            if any(path.exists() for path in completed_paths):
                raise FileExistsError(
                    f"Inconsistent completed-output set for {roi_name}; refusing overwrite"
                )
            if full_part_path.exists():
                full_part_path.unlink()
            if full_final_path.exists():
                raise FileExistsError(
                    f"Refusing to overwrite completed output without explicit cleanup: {full_final_path}"
                )
            full_memmap = open_memmap(
                full_part_path, mode="w+", dtype=np.complex64, shape=roi_shape
            )
            memmaps: list[np.memmap] = []
            part_paths: list[Path] = []
            final_paths: list[Path] = []
            for look_index in range(1, 4):
                final_path = args.output_dir / f"{roi_name}_look{look_index}_complex64.npy"
                part_path = final_path.with_suffix(final_path.suffix + ".part")
                if part_path.exists():
                    part_path.unlink()
                if final_path.exists():
                    raise FileExistsError(
                        f"Refusing to overwrite completed output without explicit cleanup: {final_path}"
                    )
                memmaps.append(
                    open_memmap(part_path, mode="w+", dtype=np.complex64, shape=roi_shape)
                )
                part_paths.append(part_path)
                final_paths.append(final_path)

            print(
                f"ROI {roi_name}: rows {row_start}:{row_stop}; reading every chunk across "
                f"all {expected_shape[1]} azimuth columns",
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
                local_rows = slice(block_start - row_start, block_stop - row_start)
                full_memmap[local_rows, :] = source[:, col_start:col_stop]
                for memmap, band, window in zip(memmaps, bands, windows):
                    sublook_full_azimuth = sublook_from_spectrum(
                        shifted,
                        band,
                        axis=context.axis.azimuth_axis,
                        sgn=context.axis.azimuth_sgn,
                        window=window,
                        workers=args.workers,
                    )
                    memmap[local_rows, :] = sublook_full_azimuth[:, col_start:col_stop]
                    del sublook_full_azimuth
                del shifted, source
                print(
                    f"  completed rows {block_start}:{block_stop} "
                    f"({block_stop-row_start}/{row_stop-row_start})",
                    flush=True,
                )

            total_nonfinite += roi_nonfinite
            full_memmap.flush()
            del full_memmap
            for memmap in memmaps:
                memmap.flush()
            del memmap
            del memmaps
            os.replace(full_part_path, full_final_path)
            full_array = np.load(full_final_path, mmap_mode="r")
            full_finite = bool(np.all(np.isfinite(full_array)))
            if not full_finite:
                raise ValueError(f"non-finite values remain in {full_final_path}")
            full_aperture_outputs[roi_name] = {
                "path": str(full_final_path.resolve()),
                "shape": list(full_array.shape),
                "dtype": str(full_array.dtype),
                "size_bytes": full_final_path.stat().st_size,
                "sha256": sha256_file(full_final_path),
                "all_finite": full_finite,
                "mean_intensity": float(
                    np.mean(np.abs(full_array) ** 2, dtype=np.float64)
                ),
            }
            del full_array
            for look_index, (part_path, final_path) in enumerate(
                zip(part_paths, final_paths), start=1
            ):
                os.replace(part_path, final_path)
                array = np.load(final_path, mmap_mode="r")
                finite = bool(np.all(np.isfinite(array)))
                mean_intensity = float(np.mean(np.abs(array) ** 2, dtype=np.float64))
                if not finite:
                    raise ValueError(f"non-finite values remain in {final_path}")
                roi_records.append(
                    {
                        "look_index": look_index,
                        "path": str(final_path.resolve()),
                        "shape": list(array.shape),
                        "dtype": str(array.dtype),
                        "size_bytes": final_path.stat().st_size,
                        "sha256": sha256_file(final_path),
                        "all_finite": finite,
                        "mean_intensity": mean_intensity,
                        "band": plan["looks"][look_index - 1]["band"],
                        "window": plan["looks"][look_index - 1]["window"],
                    }
                )
                del array
            outputs[roi_name] = roi_records
    finally:
        reader.close()

    elapsed = time.perf_counter() - started
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_sicd": str(args.sicd.resolve()),
        "source_sicd_size_bytes": args.sicd.stat().st_size,
        "source_plan": str(args.plan.resolve()),
        "source_rois": str(args.rois.resolve()),
        "source_image_shape_rows_cols": list(expected_shape),
        "algorithm": {
            "range_block_rows": args.row_chunk,
            "azimuth_columns_read_per_transformed_row": expected_shape[1],
            "azimuth_pre_crop_before_doppler_decomposition": False,
            "image_to_shifted_spectrum": context.axis.forward_transform_name,
            "shifted_spectrum_to_image": context.axis.inverse_transform_name,
            "sicd_col_sgn": context.axis.azimuth_sgn,
            "workers": args.workers,
            "complex_phase_preserved": True,
        },
        "durations_kept_distinct": {
            "sicd_processed_aperture_duration_s": context.durations.processed_aperture_duration_s,
            "cphd_available_slow_time_dwell_s": context.durations.cphd_slow_time_dwell_s,
        },
        "native_weight": plan["looks"][0]["native_weight"],
        "input_nonfinite_values_replaced_with_zero": total_nonfinite,
        "elapsed_seconds": elapsed,
        "full_aperture_outputs": full_aperture_outputs,
        "outputs": outputs,
    }
    manifest_path = args.output_dir / "SUBLOOK_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    print(f"elapsed_seconds={elapsed:.3f}")


if __name__ == "__main__":
    main()

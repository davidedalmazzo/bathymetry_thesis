"""Form Block-7 enlarged nominal sublooks without a pre-Doppler spatial crop.

Every selected range-row block is FFT-filtered across all 107800 SICD columns.
Only after inverse transformation is the enlarged bounding box cropped.  The
complex result is converted to intensity and 2 x 20 pixel block-averaged
(~0.90 x 1.13 m on ground), far below the 95--150 m wave scale.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numpy.lib.format import open_memmap
from sarpy.io.complex.converter import open_complex
from sarpy.io.complex.sicd_elements.SICD import SICDType

from umbra_sar.subaperture import SicdSubapertureContext, SubapertureBand, image_to_shifted_spectrum, make_window, sublook_from_spectrum


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / 'umbra/Vandenberg'
OUTPUT = VANDENBERG / "results" / "block7_enlarged_nominal_sea_surface"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    support = json.loads((VANDENBERG / "results" / "analysis_block7" / "BLOCK7_ROI_SUPPORT_PLAN.json").read_text())
    plan = json.loads((VANDENBERG / "metadata" / "SUBAPERTURE_PLAN_6S.json").read_text())
    row0, row1, col0, col1 = map(int, support["maximal_sicd_bounding_rows_cols"])
    row_factor, col_factor = 2, 20
    # Trim only trailing padding so that block averaging has exact support.
    row1 = row0 + ((row1-row0)//row_factor)*row_factor
    col1 = col0 + ((col1-col0)//col_factor)*col_factor
    out_shape = ((row1-row0)//row_factor, (col1-col0)//col_factor)
    final_paths = [OUTPUT / f"look{i}_intensity_bavg.npy" for i in range(1,4)]
    if all(path.exists() for path in final_paths):
        manifest = {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "source_sicd": str((VANDENBERG / "2025-02-16-18-55-44_UMBRA-10_SICD.nitf").resolve()),
            "source_sicd_shape_rows_cols": [13310,107800],
            "post_doppler_crop_sicd_bounds": [row0,row1,col0,col1],
            "output_shape": list(out_shape), "row_block_factor": row_factor, "col_block_factor": col_factor,
            "coarse_pixel_center_formula": {"sicd_row": f"{row0}+(i+0.5)*{row_factor}", "sicd_col": f"{col0}+(j+0.5)*{col_factor}"},
            "anti_bias_rule": "FFT and sub-band filtering applied across all 107800 azimuth columns before crop.",
            "complex_handling": "Complex preserved through sub-aperture filtering; intensity formed only after inverse FFT and spatial crop.",
            "files": [str(path.resolve()) for path in final_paths], "bands": [item["band"] for item in plan["looks"]],
        }
        (OUTPUT / "BLOCK7_ENLARGED_NOMINAL_MANIFEST.json").write_text(json.dumps(manifest,indent=2), encoding="utf-8")
        print("Reusing completed Block-7 enlarged nominal intensities")
        return

    sicd = SICDType.from_xml_file(plan["sicd_xml"])
    context = SicdSubapertureContext.from_sicd(sicd, cphd_slow_time_dwell_s=float(plan["looks"][0]["durations"]["cphd_slow_time_dwell_s"]))
    bands = [SubapertureBand(**item["band"]) for item in plan["looks"]]
    windows = []
    for item, band in zip(plan["looks"], bands):
        w, _ = make_window(band.size, item["window"]["kind"], tukey_alpha=float(item["window"]["tukey_alpha"]), normalization=item["window"]["normalization"])
        windows.append(w.astype(np.float32))

    part_paths = [path.with_suffix(".npy.part") for path in final_paths]
    for path in part_paths:
        if path.exists():
            path.unlink()
    outputs = [open_memmap(path, mode="w+", dtype=np.float32, shape=out_shape) for path in part_paths]
    reader = open_complex(str(VANDENBERG / "2025-02-16-18-55-44_UMBRA-10_SICD.nitf"))
    try:
        if int(reader.get_sicds_as_tuple()[0].Grid.Col.Sgn) != -1:
            raise RuntimeError("Validated Col.Sgn=-1 convention changed")
        chunk = 16  # divisible by row_factor; limits the 107800-column working set
        for start in range(row0, row1, chunk):
            stop = min(start+chunk, row1)
            source = np.asarray(reader[(slice(start,stop), slice(0,107800), 0)], dtype=np.complex64)
            source[~np.isfinite(source)] = 0
            shifted = image_to_shifted_spectrum(source, axis=context.axis.azimuth_axis, sgn=context.axis.azimuth_sgn, workers=-1)
            oi0 = (start-row0)//row_factor
            oi1 = (stop-row0)//row_factor
            for output, band, window in zip(outputs,bands,windows):
                complex_full = sublook_from_spectrum(shifted, band, axis=context.axis.azimuth_axis, sgn=context.axis.azimuth_sgn, window=window, workers=-1)
                cropped = complex_full[:, col0:col1]
                intensity = np.asarray(cropped.real*cropped.real + cropped.imag*cropped.imag, dtype=np.float32)
                reduced = intensity.reshape((stop-start)//row_factor,row_factor,out_shape[1],col_factor).mean(axis=(1,3), dtype=np.float32)
                output[oi0:oi1] = reduced
                del complex_full, cropped, intensity, reduced
            del shifted, source
            print(f"rows {start}:{stop} ({stop-row0}/{row1-row0})", flush=True)
    finally:
        reader.close()
    for output in outputs:
        output.flush()
    del output
    del outputs
    for part, final in zip(part_paths, final_paths):
        os.replace(part, final)
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_sicd": str((VANDENBERG / "2025-02-16-18-55-44_UMBRA-10_SICD.nitf").resolve()),
        "source_sicd_shape_rows_cols": [13310,107800],
        "post_doppler_crop_sicd_bounds": [row0,row1,col0,col1],
        "output_shape": list(out_shape), "row_block_factor": row_factor, "col_block_factor": col_factor,
        "coarse_pixel_center_formula": {"sicd_row": f"{row0}+(i+0.5)*{row_factor}", "sicd_col": f"{col0}+(j+0.5)*{col_factor}"},
        "anti_bias_rule": "FFT and sub-band filtering applied across all 107800 azimuth columns before crop.",
        "complex_handling": "Complex preserved through sub-aperture filtering; intensity formed only after inverse FFT and spatial crop.",
        "files": [str(path.resolve()) for path in final_paths], "bands": [item["band"] for item in plan["looks"]],
    }
    (OUTPUT / "BLOCK7_ENLARGED_NOMINAL_MANIFEST.json").write_text(json.dumps(manifest,indent=2), encoding="utf-8")
    print(json.dumps({"completed": True, "output_shape": out_shape}, indent=2))


if __name__ == "__main__":
    main()

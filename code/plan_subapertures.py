#!/usr/bin/env python3
"""Create a JSON sub-aperture plan from SICD XML without reading image data."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sarpy.io.complex.sicd_elements.SICD import SICDType

from umbra_sar.subaperture import (
    ProcessedSupport,
    SicdSubapertureContext,
    make_window,
    plan_centered_band,
    plan_tiled_bands,
    sublook_metadata,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sicd-xml", type=Path, required=True)
    parser.add_argument("--cphd-json", type=Path, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--mode", choices=("centered", "tiled"), default="tiled")
    parser.add_argument("--overlap", type=float, default=0.0)
    parser.add_argument("--window", choices=("rect", "tukey"), default="tukey")
    parser.add_argument("--tukey-alpha", type=float, default=0.25)
    parser.add_argument(
        "--normalization", choices=("none", "energy", "coherent"), default="energy"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sicd = SICDType.from_xml_string(args.sicd_xml.read_bytes())
    cphd = json.loads(args.cphd_json.read_text(encoding="utf-8"))
    cphd_dwell = float(cphd["dwell"]["dwell_time_s"])
    context = SicdSubapertureContext.from_sicd(
        sicd, cphd_slow_time_dwell_s=cphd_dwell
    )
    fft_size = int(sicd.ImageData.NumCols)
    support = ProcessedSupport.from_axis_metadata(fft_size, context.axis)
    if args.mode == "centered":
        bands = [plan_centered_band(context, support, args.duration)]
    else:
        bands = plan_tiled_bands(
            context,
            support,
            args.duration,
            overlap_fraction=args.overlap,
        )

    records = []
    for index, band in enumerate(bands, start=1):
        _, window_metrics = make_window(
            band.size,
            args.window,
            tukey_alpha=args.tukey_alpha,
            normalization=args.normalization,
        )
        metadata = sublook_metadata(context, support, band, window_metrics)
        metadata["look_index"] = index
        records.append(metadata)

    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "metadata_only": True,
        "sicd_pixels_read": False,
        "sicd_xml": str(args.sicd_xml.resolve()),
        "cphd_json": str(args.cphd_json.resolve()),
        "mode": args.mode,
        "overlap_fraction": args.overlap,
        "requested_nominal_duration_s": args.duration,
        "support": {**asdict(support), "size": support.size},
        "looks": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"wrote {args.output}")
    print("SICD pixels read: False")


if __name__ == "__main__":
    main()

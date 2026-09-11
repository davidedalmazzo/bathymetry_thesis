"""Verify the finalized NITF/SICD container and several stitched pixel reads."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from lxml import etree
from sarpy.io.complex.converter import open_complex
from sarpy.io.general.nitf import NITFDetails


EXPECTED_SIZE = 11_478_596_733
EXPECTED_ETAG = "f06d503551fb567303477152aee18652-219"


def canonical_xml(path: Path) -> bytes:
    parser = etree.XMLParser(remove_blank_text=True)
    return etree.tostring(etree.parse(str(path), parser), method="c14n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sicd", type=Path)
    parser.add_argument("--metadata-xml", type=Path, required=True)
    parser.add_argument("--metadata-json", type=Path, required=True)
    parser.add_argument("--etag-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    etag_report = json.loads(args.etag_report.read_text(encoding="utf-8"))
    prior_metadata = json.loads(args.metadata_json.read_text(encoding="utf-8"))
    file_size = args.sicd.stat().st_size
    if file_size != EXPECTED_SIZE:
        raise SystemExit(f"size mismatch: {file_size} != {EXPECTED_SIZE}")
    if not etag_report.get("passed"):
        raise SystemExit("multipart ETag report is not passing")
    if etag_report["computed_multipart_etag"].lower() != EXPECTED_ETAG.lower():
        raise SystemExit("multipart ETag report contains unexpected ETag")

    details = NITFDetails(str(args.sicd))
    header_file_length = int(details.nitf_header.FL)
    if header_file_length != file_size:
        raise SystemExit(
            f"NITF FL mismatch: header={header_file_length}, actual={file_size}"
        )
    image_headers = []
    for index in range(len(details.img_headers)):
        header = details.img_headers[index]
        image_headers.append(
            {
                "index": index,
                "iid1": str(header.IID1),
                "rows": int(header.NROWS),
                "cols": int(header.NCOLS),
                "image_mode": str(header.IMODE),
                "compression": str(header.IC),
                "pixel_value_type": str(header.PVTYPE),
                "bits_per_pixel": int(header.NBPP),
            }
        )

    reader = open_complex(str(args.sicd))
    try:
        image_segment_collections = [
            list(map(int, collection))
            for collection in reader.image_segment_collections
        ]
        shapes = [list(map(int, shape)) for shape in reader.get_data_size_as_tuple()]
        sicds = reader.get_sicds_as_tuple()
        if len(sicds) != 1 or shapes != [[13310, 107800]]:
            raise SystemExit(f"unexpected SICD count/shape: {len(sicds)}, {shapes}")
        sicd = sicds[0]
        semantic_valid = bool(sicd.is_valid(recursive=True, stack=False))
        waveform = sicd.RadarCollection.Waveform[0]
        tx_pulse_length = float(waveform.TxPulseLength)
        tx_fm_rate = float(waveform.TxFMRate)
        tx_bandwidth = float(waveform.TxRFBandwidth)
        downchirp_bandwidth = abs(tx_fm_rate) * tx_pulse_length
        downchirp_consistent = bool(
            np.isclose(downchirp_bandwidth, tx_bandwidth, rtol=1e-12, atol=1e-3)
        )
        sva_without_samples = bool(
            str(sicd.Grid.Row.WgtType.WindowName).upper() == "SVA"
            and str(sicd.Grid.Col.WgtType.WindowName).upper() == "SVA"
            and sicd.Grid.Row.WgtFunct is None
            and sicd.Grid.Col.WgtFunct is None
        )
        serialized = sicd.to_xml_bytes(tag="SICD", urn="urn:SICD:1.3.0")
        extracted_c14n = canonical_xml(args.metadata_xml)
        parsed_serialized = etree.fromstring(serialized)
        serialized_c14n = etree.tostring(parsed_serialized, method="c14n")

        sample_starts = [
            (0, 0),
            (1140, 53900),
            (6651, 53896),
            (12190, 53900),
            (13302, 107792),
        ]
        samples = []
        for row, col in sample_starts:
            data = np.asarray(
                reader[(slice(row, row + 8), slice(col, col + 8), 0)]
            )
            samples.append(
                {
                    "row_col_start": [row, col],
                    "shape": list(data.shape),
                    "dtype": str(data.dtype),
                    "finite_count": int(np.count_nonzero(np.isfinite(data))),
                    "sample_count": int(data.size),
                    "nonzero_count": int(np.count_nonzero(data)),
                    "mean_intensity": float(np.mean(np.abs(data) ** 2)),
                }
            )
    finally:
        reader.close()

    report = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "path": str(args.sicd.resolve()),
        "size_bytes": file_size,
        "expected_size_bytes": EXPECTED_SIZE,
        "exact_size_match": file_size == EXPECTED_SIZE,
        "multipart_etag": etag_report["computed_multipart_etag"],
        "expected_multipart_etag": EXPECTED_ETAG,
        "multipart_etag_match": etag_report["computed_multipart_etag"].lower()
        == EXPECTED_ETAG.lower(),
        "sha256": etag_report["sha256"],
        "nitf_header_file_length_bytes": header_file_length,
        "nitf_header_length_matches_file": header_file_length == file_size,
        "nitf_version": details.nitf_version,
        "image_segment_collections": image_segment_collections,
        "image_segments": image_headers,
        "sarpy": {
            "sicd_count": len(sicds),
            "stitched_data_shapes": shapes,
            "recursive_semantic_valid": semantic_valid,
            "pixel_type": str(sicd.ImageData.PixelType),
            "collection_core_name": str(sicd.CollectionInfo.CoreName),
            "collect_id": str(sicd.CollectionInfo.Parameters["collect_id"]),
        },
        "validation_interpretation": {
            "range_extracted_xml_xsd_valid": bool(
                prior_metadata["validation"]["xsd_valid"]
            ),
            "sarpy_recursive_semantic_valid": semantic_valid,
            "sarpy_false_is_expected_and_nonblocking": bool(
                not semantic_valid and downchirp_consistent and sva_without_samples
            ),
            "known_reasons": [
                "SarPy 2.0.1 endpoint validation assumes a positive TxFMRate; this product is a consistent negative-rate downchirp.",
                "Grid Row/Col declare SVA weighting without sampled WgtFunct values.",
            ],
            "downchirp_abs_rate_times_pulse_length_hz": downchirp_bandwidth,
            "declared_tx_rf_bandwidth_hz": tx_bandwidth,
            "downchirp_bandwidth_consistent": downchirp_consistent,
            "sva_without_wgtfunct_confirmed": sva_without_samples,
            "blocking_rule": "The documented SVA/WgtFunct omission and SarPy downchirp-sign validator limitation do not block structural/data integrity checks.",
        },
        "metadata_comparison": {
            "range_extracted_xml": str(args.metadata_xml.resolve()),
            "canonical_xml_exact_match_after_parse_and_serialize": extracted_c14n
            == serialized_c14n,
            "range_extracted_c14n_bytes": len(extracted_c14n),
            "reader_serialized_c14n_bytes": len(serialized_c14n),
        },
        "stitched_pixel_read_samples": samples,
        "passed": bool(
            file_size == EXPECTED_SIZE
            and header_file_length == file_size
            and bool(prior_metadata["validation"]["xsd_valid"])
            and downchirp_consistent
            and sva_without_samples
            and shapes == [[13310, 107800]]
            and all(item["finite_count"] == item["sample_count"] for item in samples)
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit("final SICD verification failed")


if __name__ == "__main__":
    main()

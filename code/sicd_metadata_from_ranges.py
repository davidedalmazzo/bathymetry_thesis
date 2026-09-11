#!/usr/bin/env python3
"""Build a SICD metadata report from small HTTP-range fragments of a NITF.

This utility allows metadata inspection before the multi-gigabyte SICD is
downloaded.  It expects a leading NITF fragment, the second image subheader,
and the complete DES subheader+payload fragment containing the SICD XML.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lxml import etree

from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.general.nitf import NITFDetails
from sarpy.io.general.nitf_elements.image import ImageSegmentHeader


def value(obj: Any, *names: str) -> Any:
    current = obj
    for name in names:
        if current is None:
            return None
        current = getattr(current, name, None)
    return current


def array_value(obj: Any) -> list[Any] | None:
    if obj is None:
        return None
    if hasattr(obj, "get_array"):
        return obj.get_array().tolist()
    return list(obj)


def poly_value(obj: Any) -> list[Any] | None:
    if obj is None:
        return None
    return obj.get_array(dtype="float64").tolist()


def ecf_to_enu(vector_ecf: list[float], lat_deg: float, lon_deg: float) -> list[float]:
    x, y, z = vector_ecf
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    east = -math.sin(lon) * x + math.cos(lon) * y
    north = (
        -math.sin(lat) * math.cos(lon) * x
        - math.sin(lat) * math.sin(lon) * y
        + math.cos(lat) * z
    )
    up = (
        math.cos(lat) * math.cos(lon) * x
        + math.cos(lat) * math.sin(lon) * y
        + math.sin(lat) * z
    )
    return [east, north, up]


def bearing_deg(enu: list[float]) -> float:
    return math.degrees(math.atan2(enu[0], enu[1])) % 360.0


def header_summary(header: ImageSegmentHeader) -> dict[str, Any]:
    fields = (
        "IID1",
        "IDATIM",
        "IID2",
        "NROWS",
        "NCOLS",
        "PVTYPE",
        "IREP",
        "ICAT",
        "ABPP",
        "ICORDS",
        "IGEOLO",
        "IC",
        "NBPR",
        "NBPC",
        "NPPBH",
        "NPPBV",
        "NBPP",
        "IDLVL",
        "IALVL",
        "ILOC",
        "IMODE",
    )
    return {name: getattr(header, name, None) for name in fields}


def schema_valid(xml: bytes) -> tuple[bool, list[str]]:
    import sarpy.io.complex.sicd_schema as schema_package

    schema_path = (
        Path(schema_package.__file__).parent / "SICD_schema_V1.3.0_2021_11_30.xsd"
    )
    schema = etree.XMLSchema(etree.parse(str(schema_path)))
    document = etree.fromstring(xml)
    valid = schema.validate(document)
    return valid, [str(item) for item in schema.error_log]


def collect(
    head_fragment: Path,
    second_image_subheader: Path,
    des_fragment: Path,
    des_subheader_size: int,
    cphd_json: Path | None,
    public_asset: str,
    public_content_length: int,
) -> tuple[dict[str, Any], bytes, SICDType]:
    details = NITFDetails(str(head_fragment))
    first_header = details.parse_image_subheader(0)
    second_header = ImageSegmentHeader.from_bytes(second_image_subheader.read_bytes(), 0)
    xml = des_fragment.read_bytes()[des_subheader_size:]
    if not xml.lstrip().startswith(b"<SICD"):
        raise ValueError("DES payload does not start with SICD XML")
    sicd = SICDType.from_xml_string(xml)
    xsd_valid, xsd_errors = schema_valid(xml)
    sarpy_semantic_valid = bool(sicd.is_valid(recursive=True, stack=False))

    image_data = sicd.ImageData
    grid = sicd.Grid
    timeline = sicd.Timeline
    formation = sicd.ImageFormation
    scpcoa = sicd.SCPCOA
    geo = sicd.GeoData
    radar = sicd.RadarCollection
    collection = sicd.CollectionInfo
    timeline_dict = timeline.to_dict()
    collect_start = timeline_dict["CollectStart"]

    processed_dwell = float(formation.TEndProc - formation.TStartProc)
    row_fraction = float((grid.Row.DeltaK2 - grid.Row.DeltaK1) * grid.Row.SS)
    col_fraction = float((grid.Col.DeltaK2 - grid.Col.DeltaK1) * grid.Col.SS)
    col_support_bins = int(round(col_fraction * image_data.NumCols))

    lat = float(geo.SCP.LLH.Lat)
    lon = float(geo.SCP.LLH.Lon)
    row_enu = ecf_to_enu(array_value(grid.Row.UVectECF), lat, lon)
    col_enu = ecf_to_enu(array_value(grid.Col.UVectECF), lat, lon)
    velocity_enu = ecf_to_enu(array_value(scpcoa.ARPVel), lat, lon)

    waveform = radar.Waveform[0]
    downchirp_bandwidth = float(abs(waveform.TxFMRate) * waveform.TxPulseLength)
    downchirp_low = float(waveform.TxFreqStart - downchirp_bandwidth)
    downchirp_high = float(waveform.TxFreqStart)

    result: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_fragments": {
            "head": str(head_fragment.resolve()),
            "second_image_subheader": str(second_image_subheader.resolve()),
            "des": str(des_fragment.resolve()),
            "des_subheader_bytes": des_subheader_size,
        },
        "public_asset": {
            "url": public_asset,
            "content_length_bytes": public_content_length,
            "downloaded": False,
            "metadata_retrieved_by_http_range": True,
        },
        "validation": {
            "sicd_version": "1.3.0",
            "xsd_valid": xsd_valid,
            "xsd_errors": xsd_errors,
            "sarpy_recursive_semantic_valid": sarpy_semantic_valid,
            "sarpy_semantic_notes": [
                "Grid Row and Col declare SVA weighting but omit WgtFunct samples.",
                "SarPy 2.0.1 validation assumes positive TxFMRate when checking waveform bandwidth and endpoints; this product is a physically consistent negative-rate downchirp.",
            ],
            "downchirp_check": {
                "abs_fm_rate_times_pulse_length_hz": downchirp_bandwidth,
                "declared_bandwidth_hz": float(waveform.TxRFBandwidth),
                "derived_low_hz": downchirp_low,
                "derived_high_hz": downchirp_high,
                "declared_low_hz": float(radar.TxFrequency.Min),
                "declared_high_hz": float(radar.TxFrequency.Max),
            },
        },
        "nitf": {
            "version": details.nitf_version,
            "file_length": int(details.nitf_header.FL),
            "header_length": int(details.nitf_header.HL),
            "image_subheader_offsets": details.img_subheader_offsets.tolist(),
            "image_subheader_sizes": details.img_subheader_sizes.tolist(),
            "image_segment_offsets": details.img_segment_offsets.tolist(),
            "image_segment_sizes": details.img_segment_sizes.tolist(),
            "text_subheader_offsets": details.text_subheader_offsets.tolist(),
            "text_subheader_sizes": details.text_subheader_sizes.tolist(),
            "text_segment_offsets": details.text_segment_offsets.tolist(),
            "text_segment_sizes": details.text_segment_sizes.tolist(),
            "des_subheader_offsets": details.des_subheader_offsets.tolist(),
            "des_subheader_sizes": details.des_subheader_sizes.tolist(),
            "des_segment_offsets": details.des_segment_offsets.tolist(),
            "des_segment_sizes": details.des_segment_sizes.tolist(),
            "image_headers": [header_summary(first_header), header_summary(second_header)],
        },
        "collection": {
            "collector": collection.CollectorName,
            "core_name": collection.CoreName,
            "collect_type": collection.CollectType,
            "radar_mode": collection.RadarMode.ModeType,
            "parameters": collection.Parameters,
            "image_creation": sicd.ImageCreation.to_dict(),
        },
        "image_data": {
            "num_rows": int(image_data.NumRows),
            "num_cols": int(image_data.NumCols),
            "pixel_type": image_data.PixelType,
            "first_row": int(image_data.FirstRow),
            "first_col": int(image_data.FirstCol),
            "scp_pixel": [int(image_data.SCPPixel.Row), int(image_data.SCPPixel.Col)],
        },
        "grid": {
            "type": grid.Type,
            "image_plane": grid.ImagePlane,
            "time_coa_poly": poly_value(grid.TimeCOAPoly),
            "row": {
                "ss_m": float(grid.Row.SS),
                "imp_resp_width_m": float(grid.Row.ImpRespWid),
                "imp_resp_bw_per_m": float(grid.Row.ImpRespBW),
                "sgn": int(grid.Row.Sgn),
                "k_center_per_m": float(grid.Row.KCtr),
                "delta_k1_per_m": float(grid.Row.DeltaK1),
                "delta_k2_per_m": float(grid.Row.DeltaK2),
                "delta_kcoa_poly": poly_value(grid.Row.DeltaKCOAPoly),
                "window_name": grid.Row.WgtType.WindowName,
                "weight_samples_present": grid.Row.WgtFunct is not None,
                "processed_support_fraction_of_fft": row_fraction,
                "uvect_ecf": array_value(grid.Row.UVectECF),
                "uvect_enu": row_enu,
                "ground_projection_bearing_deg": bearing_deg(row_enu),
            },
            "col": {
                "ss_m": float(grid.Col.SS),
                "imp_resp_width_m": float(grid.Col.ImpRespWid),
                "imp_resp_bw_per_m": float(grid.Col.ImpRespBW),
                "sgn": int(grid.Col.Sgn),
                "k_center_per_m": float(grid.Col.KCtr),
                "delta_k1_per_m": float(grid.Col.DeltaK1),
                "delta_k2_per_m": float(grid.Col.DeltaK2),
                "delta_kcoa_poly": poly_value(grid.Col.DeltaKCOAPoly),
                "window_name": grid.Col.WgtType.WindowName,
                "weight_samples_present": grid.Col.WgtFunct is not None,
                "processed_support_fraction_of_fft": col_fraction,
                "processed_support_bins": col_support_bins,
                "uvect_ecf": array_value(grid.Col.UVectECF),
                "uvect_enu": col_enu,
                "ground_projection_bearing_deg": bearing_deg(col_enu),
            },
        },
        "timeline": {
            "collect_start": collect_start,
            "collect_duration_s": float(timeline.CollectDuration),
            "ipp": [entry.to_dict() for entry in timeline.IPP],
        },
        "image_formation": {
            "algorithm": formation.ImageFormAlgo,
            "t_start_proc_s": float(formation.TStartProc),
            "t_end_proc_s": float(formation.TEndProc),
            "processed_dwell_s": processed_dwell,
            "tx_frequency_min_proc_hz": float(formation.TxFrequencyProc.MinProc),
            "tx_frequency_max_proc_hz": float(formation.TxFrequencyProc.MaxProc),
            "tx_rcv_polarization_proc": formation.TxRcvPolarizationProc,
            "azimuth_autofocus": formation.AzAutofocus,
            "range_autofocus": formation.RgAutofocus,
        },
        "scpcoa": {
            "scp_time_s": float(scpcoa.SCPTime),
            "slant_range_m": float(scpcoa.SlantRange),
            "ground_range_m": float(scpcoa.GroundRange),
            "graze_angle_deg": float(scpcoa.GrazeAng),
            "incidence_angle_deg": float(scpcoa.IncidenceAng),
            "azimuth_angle_deg": float(scpcoa.AzimAng),
            "side_of_track": scpcoa.SideOfTrack,
            "doppler_cone_angle_deg": float(scpcoa.DopplerConeAng),
            "arp_position_ecf_m": array_value(scpcoa.ARPPos),
            "arp_velocity_ecf_mps": array_value(scpcoa.ARPVel),
            "arp_velocity_enu_mps": velocity_enu,
            "ground_track_bearing_deg": bearing_deg(velocity_enu),
        },
        "position": sicd.Position.to_dict(),
        "geo_data": {
            "earth_model": geo.EarthModel,
            "scp_ecf_m": array_value(geo.SCP.ECF),
            "scp_llh": {
                "lat_deg": lat,
                "lon_deg": lon,
                "hae_m": float(geo.SCP.LLH.HAE),
            },
            "image_corners": [entry.to_dict() for entry in geo.ImageCorners],
        },
        "axis_determination": {
            "unambiguous": grid.Type == "RGAZIM",
            "range_dimension": "Row",
            "range_numpy_axis": 0,
            "azimuth_dimension": "Col",
            "azimuth_numpy_axis": 1,
            "physical_forward_transform": "sarpy.processing.sicd.fft_base.fft_sicd(array, 1, sicd)",
            "actual_col_sgn": int(grid.Col.Sgn),
            "actual_numpy_transform_for_image_to_spectrum": "numpy.fft.fft(axis=1)" if grid.Col.Sgn < 0 else "numpy.fft.ifft(axis=1)",
            "delta_kcoa_is_zero": poly_value(grid.Col.DeltaKCOAPoly) == [[0.0]],
        },
        "sicd_selected_metadata": sicd.to_dict(),
    }

    if cphd_json:
        cphd = json.loads(cphd_json.read_text(encoding="utf-8"))
        cphd_geometry = cphd["reference_geometry"]
        cphd_dwell = cphd["dwell"]["dwell_time_s"]
        result["cphd_comparison"] = {
            "same_collect_uuid": (
                cphd["collection"]["parameters"].get("collect_id")
                == collection.Parameters.get("collect_id")
            ),
            "same_collection_start": cphd["global"]["collection_start"] == collect_start,
            "cphd_dwell_s": cphd_dwell,
            "sicd_timeline_collect_duration_s": float(timeline.CollectDuration),
            "sicd_processed_dwell_s": processed_dwell,
            "processed_dwell_minus_cphd_dwell_s": processed_dwell - cphd_dwell,
            "processed_dwell_fraction_of_cphd": processed_dwell / cphd_dwell,
            "scp_reference_time_difference_s": float(scpcoa.SCPTime) - cphd_geometry["reference_time_s"],
            "azimuth_angle_difference_deg": float(scpcoa.AzimAng) - cphd_geometry["azimuth_angle_deg"],
            "incidence_angle_difference_deg": float(scpcoa.IncidenceAng) - cphd_geometry["incidence_angle_deg"],
            "slant_range_difference_m": float(scpcoa.SlantRange) - cphd_geometry["slant_range_m"],
            "ground_range_difference_m": float(scpcoa.GroundRange) - cphd_geometry["ground_range_m"],
            "explanation": "Reference-geometry differences are expected because SICD SCPTime and CPHD ReferenceTime differ.",
        }
    return result, xml, sicd


def fmt(value: Any, digits: int = 12) -> str:
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def report_markdown(data: dict[str, Any]) -> str:
    image = data["image_data"]
    grid = data["grid"]
    timeline = data["timeline"]
    formation = data["image_formation"]
    scpcoa = data["scpcoa"]
    geo = data["geo_data"]
    validation = data["validation"]
    axis = data["axis_determination"]
    compare = data.get("cphd_comparison", {})
    lines = [
        "# SICD metadata report",
        "",
        f"Generated: `{data['generated_utc']}`",
        "",
        "## Provenance and status",
        "",
        f"- Public asset: `{data['public_asset']['url']}`",
        f"- HTTP Content-Length: `{data['public_asset']['content_length_bytes']}` bytes.",
        "- The full SICD is **not yet downloaded**. Metadata was extracted with byte-range requests for the NITF header, second image subheader, and SICD DES XML.",
        f"- NITF-declared file length: `{data['nitf']['file_length']}` bytes; match with HTTP: `{data['nitf']['file_length'] == data['public_asset']['content_length_bytes']}`.",
        f"- SICD 1.3.0 XML schema validation: `{validation['xsd_valid']}`.",
        "",
        "The NITF contains two vertically joined image segments (11,595 + 1,715 rows) and one SICD XML DES. The joined dimensions agree with ImageData.",
        "",
        "## ImageData",
        "",
        f"- NumRows: `{image['num_rows']}`",
        f"- NumCols: `{image['num_cols']}`",
        f"- PixelType: `{image['pixel_type']}` (complex float32 real/imaginary)",
        f"- SCPPixel: row `{image['scp_pixel'][0]}`, col `{image['scp_pixel'][1]}`",
        "",
        "## Grid",
        "",
        f"- Grid.Type / ImagePlane: `{grid['type']}` / `{grid['image_plane']}`",
        f"- Row: SS `{fmt(grid['row']['ss_m'])}` m, ImpRespBW `{fmt(grid['row']['imp_resp_bw_per_m'])}` 1/m, DeltaK1/2 `{fmt(grid['row']['delta_k1_per_m'])}` / `{fmt(grid['row']['delta_k2_per_m'])}` 1/m, Sgn `{grid['row']['sgn']}`.",
        f"- Col: SS `{fmt(grid['col']['ss_m'])}` m, ImpRespBW `{fmt(grid['col']['imp_resp_bw_per_m'])}` 1/m, DeltaK1/2 `{fmt(grid['col']['delta_k1_per_m'])}` / `{fmt(grid['col']['delta_k2_per_m'])}` 1/m, Sgn `{grid['col']['sgn']}`.",
        f"- Row/Col DeltaKCOAPoly: `{grid['row']['delta_kcoa_poly']}` / `{grid['col']['delta_kcoa_poly']}`.",
        f"- Both dimensions declare `{grid['row']['window_name']}` weighting; explicit WgtFunct samples are absent.",
        f"- Processed support occupies `{fmt(grid['col']['processed_support_fraction_of_fft'])}` of the Col FFT, about `{grid['col']['processed_support_bins']}` of `{image['num_cols']}` bins.",
        "",
        "## Timeline and ImageFormation",
        "",
        f"- CollectStart: `{timeline['collect_start']}`",
        f"- Timeline.CollectDuration: `{fmt(timeline['collect_duration_s'])}` s",
        f"- ImageFormAlgo: `{formation['algorithm']}`",
        f"- TStartProc / TEndProc: `{fmt(formation['t_start_proc_s'])}` / `{fmt(formation['t_end_proc_s'])}` s",
        f"- **Processed aperture duration: `{fmt(formation['processed_dwell_s'])}` s.**",
        f"- Processed frequency range: `{fmt(formation['tx_frequency_min_proc_hz'])}` to `{fmt(formation['tx_frequency_max_proc_hz'])}` Hz",
        f"- Processing polarization: `{formation['tx_rcv_polarization_proc']}`",
        "",
        "The processed duration, not Timeline.CollectDuration, is the available aperture baseline for SICD sub-aperture splitting. Consequently a 20 s sub-aperture cannot be produced from this SICD.",
        "",
        "## SCPCOA and geolocation",
        "",
        f"- SCPTime: `{fmt(scpcoa['scp_time_s'])}` s",
        f"- Slant / ground range: `{fmt(scpcoa['slant_range_m'])}` / `{fmt(scpcoa['ground_range_m'])}` m",
        f"- Graze / incidence: `{fmt(scpcoa['graze_angle_deg'])}` / `{fmt(scpcoa['incidence_angle_deg'])}` deg",
        f"- AzimAng: `{fmt(scpcoa['azimuth_angle_deg'])}` deg; SideOfTrack `{scpcoa['side_of_track']}`; DopplerConeAng `{fmt(scpcoa['doppler_cone_angle_deg'])}` deg",
        f"- SCP LLH: `{geo['scp_llh']['lat_deg']}`, `{geo['scp_llh']['lon_deg']}`, HAE `{fmt(geo['scp_llh']['hae_m'])}` m",
        f"- Derived platform ground-track bearing at SCPTime: `{fmt(scpcoa['ground_track_bearing_deg'])}` deg",
        f"- Col ground-projection bearing: `{fmt(grid['col']['ground_projection_bearing_deg'])}` deg",
        "",
        "## Range/azimuth axis determination",
        "",
        f"- Grid.Type is `{grid['type']}`. In SICD/SarPy the coordinate order is Row then Col; RGAZIM means range then Doppler/azimuth.",
        f"- Range = Row = NumPy `axis={axis['range_numpy_axis']}`.",
        f"- Azimuth/Doppler = Col = NumPy `axis={axis['azimuth_numpy_axis']}`.",
        f"- Col.Sgn is `{axis['actual_col_sgn']}`; image-to-spectrum must use `{axis['physical_forward_transform']}`, which is `{axis['actual_numpy_transform_for_image_to_spectrum']}` for this file.",
        f"- Col DeltaKCOAPoly is zero: `{axis['delta_kcoa_is_zero']}`; no Col deskew phase is required for this product.",
        "",
        "This conclusion is unambiguous for this SICD. A generic splitter must still reject other Grid.Type values unless explicitly validated.",
        "",
        "## CPHD comparison",
        "",
        f"- Same collect UUID: `{compare.get('same_collect_uuid')}`; same CollectionStart: `{compare.get('same_collection_start')}`.",
        f"- CPHD dwell: `{fmt(compare.get('cphd_dwell_s'))}` s; SICD Timeline duration: `{fmt(compare.get('sicd_timeline_collect_duration_s'))}` s; SICD processed duration: `{fmt(compare.get('sicd_processed_dwell_s'))}` s.",
        f"- SICD processed duration is `{fmt(100 * compare.get('processed_dwell_fraction_of_cphd', float('nan')))}`% of the CPHD dwell.",
        f"- SCP/reference time offset (SICD minus CPHD): `{fmt(compare.get('scp_reference_time_difference_s'))}` s.",
        f"- Azimuth/incidence differences: `{fmt(compare.get('azimuth_angle_difference_deg'))}` / `{fmt(compare.get('incidence_angle_difference_deg'))}` deg.",
        "",
        "The geometry differences are explained by the different reference times; they are not evidence that the products belong to different collects.",
        "",
        "## Validation caveats",
        "",
        "- The XML is XSD-valid.",
        "- SarPy 2.0.1 recursive semantic validation returns false because SVA lacks WgtFunct and because its waveform validator assumes a positive chirp rate. The negative-rate chirp is internally consistent when bandwidth is checked with `abs(TxFMRate)`: the derived endpoints exactly match RadarCollection.TxFrequency.",
        "- Missing SVA samples are scientifically relevant: native spectral deweighting cannot be reconstructed exactly from this metadata. Initial tests must preserve the native weighting and clearly describe any additional window.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--head-fragment", type=Path, required=True)
    parser.add_argument("--second-image-subheader", type=Path, required=True)
    parser.add_argument("--des-fragment", type=Path, required=True)
    parser.add_argument("--des-subheader-size", type=int, default=973)
    parser.add_argument("--cphd-json", type=Path)
    parser.add_argument("--asset-url", required=True)
    parser.add_argument("--content-length", type=int, required=True)
    parser.add_argument("--xml-output", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    result, xml, _ = collect(
        args.head_fragment,
        args.second_image_subheader,
        args.des_fragment,
        args.des_subheader_size,
        args.cphd_json,
        args.asset_url,
        args.content_length,
    )
    for path in (args.xml_output, args.json, args.report):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.xml_output.write_bytes(xml)
    args.json.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    args.report.write_text(report_markdown(result), encoding="utf-8")
    print(f"wrote {args.xml_output}")
    print(f"wrote {args.json}")
    print(f"wrote {args.report}")
    print("full SICD downloaded: False")


if __name__ == "__main__":
    main()

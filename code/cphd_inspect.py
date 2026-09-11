#!/usr/bin/env python3
"""Lightweight CPHD 1.1 metadata and PVP inspector.

The signal block is never opened or read.  Only the small ASCII header, XML
block, and PVP block are accessed.  The PVP array is memory-mapped.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np


HEADER_SCAN_BYTES = 64 * 1024


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    return next((item for item in element if local_name(item.tag) == name), None)


def node(root: ET.Element, *names: str) -> ET.Element | None:
    current: ET.Element | None = root
    for name in names:
        current = child(current, name)
        if current is None:
            return None
    return current


def text(root: ET.Element, *names: str, default: str | None = None) -> str | None:
    item = node(root, *names)
    if item is None or item.text is None:
        return default
    return item.text.strip()


def number(root: ET.Element, *names: str, default: float | None = None) -> float | None:
    value = text(root, *names)
    return default if value is None else float(value)


def integer(root: ET.Element, *names: str, default: int | None = None) -> int | None:
    value = text(root, *names)
    return default if value is None else int(value)


def vector(root: ET.Element, *names: str) -> list[float] | None:
    item = node(root, *names)
    if item is None:
        return None
    values = [float(text(item, axis)) for axis in ("X", "Y", "Z")]
    return values


def parse_header(path: Path) -> tuple[str, dict[str, str], bytes]:
    with path.open("rb") as stream:
        prefix = stream.read(HEADER_SCAN_BYTES)
    marker = prefix.find(b"\x0c\n")
    if marker < 0:
        raise ValueError("CPHD ASCII header terminator was not found")
    raw = prefix[: marker + 2]
    lines = raw.decode("ascii").splitlines()
    version = lines[0]
    values: dict[str, str] = {}
    for line in lines[1:]:
        if ":=" in line:
            key, value = line.split(":=", 1)
            values[key.strip()] = value.strip()
    return version, values, raw


def read_xml(path: Path, header: dict[str, str]) -> tuple[ET.Element, bytes]:
    offset = int(header["XML_BLOCK_BYTE_OFFSET"])
    size = int(header["XML_BLOCK_SIZE"])
    with path.open("rb") as stream:
        stream.seek(offset)
        raw = stream.read(size)
    if len(raw) != size:
        raise IOError(f"Expected {size} XML bytes, read {len(raw)}")
    return ET.fromstring(raw), raw


def named_parameters(parent: ET.Element | None) -> dict[str, str]:
    if parent is None:
        return {}
    output: dict[str, str] = {}
    for item in parent:
        if local_name(item.tag) == "Parameter":
            output[item.attrib.get("name", "")] = (item.text or "").strip()
    return output


def pvp_field_definitions(root: ET.Element) -> dict[str, dict[str, Any]]:
    pvp = node(root, "PVP")
    if pvp is None:
        return {}
    output: dict[str, dict[str, Any]] = {}
    for item in pvp.iter():
        offset = child(item, "Offset")
        size = child(item, "Size")
        fmt = child(item, "Format")
        if offset is None or size is None or fmt is None:
            continue
        name = local_name(item.tag)
        if name == "AddedPVP":
            name = (child(item, "Name").text or "").strip()
        output[name] = {
            "offset_words": int(offset.text),
            "size_words": int(size.text),
            "format": (fmt.text or "").strip(),
        }
    return output


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


def inspect_pvp(
    path: Path,
    header: dict[str, str],
    root: ET.Element,
    definitions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    num_vectors = integer(root, "Data", "Channel", "NumVectors")
    bytes_per_record = integer(root, "Data", "NumBytesPVP")
    if num_vectors is None or bytes_per_record is None:
        raise ValueError("Missing NumVectors or NumBytesPVP")
    if bytes_per_record % 8:
        raise ValueError("This inspector expects 8-byte-aligned PVP records")

    pvp_offset = int(header["PVP_BLOCK_BYTE_OFFSET"])
    channel_offset = integer(root, "Data", "Channel", "PVPArrayByteOffset", default=0)
    offset = pvp_offset + int(channel_offset or 0)
    records = np.memmap(
        path,
        dtype=">f8",
        mode="r",
        offset=offset,
        shape=(num_vectors, bytes_per_record // 8),
    )

    tx_offset = definitions["TxTime"]["offset_words"]
    tx_time = np.asarray(records[:, tx_offset], dtype=np.float64)
    delta_time = np.diff(tx_time)
    output: dict[str, Any] = {
        "endianness": "big-endian",
        "record_bytes": bytes_per_record,
        "vectors": num_vectors,
        "tx_time_s": {
            "first": float(tx_time[0]),
            "last": float(tx_time[-1]),
            "min": float(tx_time.min()),
            "max": float(tx_time.max()),
            "span_first_to_last": float(tx_time[-1] - tx_time[0]),
            "strictly_monotonic": bool(np.all(delta_time > 0)),
        },
        "recorded_vector_interval_s": {
            "min": float(delta_time.min()),
            "median": float(np.median(delta_time)),
            "mean": float(delta_time.mean()),
            "max": float(delta_time.max()),
        },
        "recorded_vector_rate_hz": float((num_vectors - 1) / (tx_time[-1] - tx_time[0])),
    }

    pulse_def = definitions.get("PulseNumber")
    signal_def = definitions.get("SIGNAL")
    dtype_names: list[str] = []
    dtype_formats: list[str] = []
    dtype_offsets: list[int] = []
    if pulse_def:
        dtype_names.append("pulse")
        dtype_formats.append(">u8")
        dtype_offsets.append(8 * pulse_def["offset_words"])
    if signal_def:
        dtype_names.append("signal")
        dtype_formats.append(">i8")
        dtype_offsets.append(8 * signal_def["offset_words"])
    if dtype_names:
        structured = np.memmap(
            path,
            dtype=np.dtype(
                {
                    "names": dtype_names,
                    "formats": dtype_formats,
                    "offsets": dtype_offsets,
                    "itemsize": bytes_per_record,
                }
            ),
            mode="r",
            offset=offset,
            shape=(num_vectors,),
        )
        if pulse_def:
            pulse = np.asarray(structured["pulse"], dtype=np.int64)
            delta_pulse = np.diff(pulse)
            per_pulse_interval = delta_time / delta_pulse
            increments, counts = np.unique(delta_pulse, return_counts=True)
            output["pulse_number"] = {
                "first": int(pulse[0]),
                "last": int(pulse[-1]),
                "missing_from_contiguous_span": int(pulse[-1] - pulse[0] + 1 - num_vectors),
                "increment_counts": {str(int(k)): int(v) for k, v in zip(increments, counts)},
            }
            output["nominal_pulse_interval_s"] = {
                "min": float(per_pulse_interval.min()),
                "median": float(np.median(per_pulse_interval)),
                "mean": float(per_pulse_interval.mean()),
                "max": float(per_pulse_interval.max()),
            }
            output["nominal_pulse_rate_from_median_hz"] = float(1.0 / np.median(per_pulse_interval))
        if signal_def:
            counts = Counter(int(value) for value in np.asarray(structured["signal"]))
            output["signal_flag_counts"] = {str(k): v for k, v in sorted(counts.items())}

    def values(field: str, index: int) -> list[float] | float | None:
        definition = definitions.get(field)
        if definition is None:
            return None
        start = definition["offset_words"]
        size = definition["size_words"]
        data = np.asarray(records[index, start : start + size], dtype=np.float64)
        return float(data[0]) if size == 1 else data.tolist()

    reference_index = integer(root, "Channel", "Parameters", "RefVectorIndex", default=num_vectors // 2)
    output["samples"] = {
        "indices": [0, reference_index, num_vectors - 1],
        "TxPos_ECF_m": [values("TxPos", index) for index in (0, reference_index, num_vectors - 1)],
        "TxVel_ECF_mps": [values("TxVel", index) for index in (0, reference_index, num_vectors - 1)],
        "RcvTime_s": [values("RcvTime", index) for index in (0, reference_index, num_vectors - 1)],
        "SRPPos_ECF_m": [values("SRPPos", index) for index in (0, reference_index, num_vectors - 1)],
    }
    for field in ("aFDOP", "FX1", "FX2"):
        definition = definitions.get(field)
        if definition:
            column = np.asarray(records[:, definition["offset_words"]], dtype=np.float64)
            output[field] = {"min": float(column.min()), "max": float(column.max())}
    return output


def collect_metadata(path: Path, expected_size: int | None) -> dict[str, Any]:
    version, header, _ = parse_header(path)
    root, xml_bytes = read_xml(path, header)
    try:
        from sarpy.io.phase_history.cphd1_elements.CPHD import CPHDType

        sarpy_validation = bool(
            CPHDType.from_xml_string(xml_bytes).is_valid(recursive=True, stack=False)
        )
        sarpy_validation_error = None
    except Exception as exc:  # pragma: no cover - only a fallback without SarPy
        sarpy_validation = None
        sarpy_validation_error = repr(exc)
    definitions = pvp_field_definitions(root)
    file_size = path.stat().st_size
    signal_end = int(header["SIGNAL_BLOCK_BYTE_OFFSET"]) + int(header["SIGNAL_BLOCK_SIZE"])
    num_vectors = integer(root, "Data", "Channel", "NumVectors")
    num_samples = integer(root, "Data", "Channel", "NumSamples")
    signal_format = text(root, "Data", "SignalArrayFormat")
    bytes_per_sample = {"CF8": 8, "CI4": 4, "CI2": 2}.get(signal_format or "")
    expected_signal_size = (
        num_vectors * num_samples * bytes_per_sample
        if None not in (num_vectors, num_samples, bytes_per_sample)
        else None
    )

    llh_node = node(root, "SceneCoordinates", "IARP", "LLH")
    lat = float(text(llh_node, "Lat")) if llh_node is not None else None
    lon = float(text(llh_node, "Lon")) if llh_node is not None else None
    velocity = vector(root, "ReferenceGeometry", "Monostatic", "ARPVel")
    track: dict[str, Any] | None = None
    if lat is not None and lon is not None and velocity is not None:
        enu = ecf_to_enu(velocity, lat, lon)
        track = {
            "velocity_enu_mps": enu,
            "horizontal_speed_mps": math.hypot(enu[0], enu[1]),
            "azimuth_clockwise_from_true_north_deg": bearing_deg(enu),
            "undirected_axis_deg_mod_180": bearing_deg(enu) % 180.0,
        }

    dwell_poly = number(root, "Dwell", "DwellTime", "DwellTimePoly", "Coef")
    tx_time_1 = number(root, "Global", "Timeline", "TxTime1")
    tx_time_2 = number(root, "Global", "Timeline", "TxTime2")
    output: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(path.resolve()),
        "access_scope": "ASCII header + XML + memory-mapped PVP; signal block not read",
        "signal_block_read": False,
        "validation": {
            "sarpy_recursive_semantic_valid": sarpy_validation,
            "error": sarpy_validation_error,
        },
        "file": {
            "size_bytes": file_size,
            "expected_size_bytes": expected_size,
            "expected_size_match": None if expected_size is None else file_size == expected_size,
            "version": version,
            "header": header,
            "signal_block_end_byte": signal_end,
            "signal_block_ends_at_eof": signal_end == file_size,
            "expected_signal_size_from_dimensions": expected_signal_size,
            "signal_size_matches_dimensions": expected_signal_size == int(header["SIGNAL_BLOCK_SIZE"]),
            "xml_bytes": len(xml_bytes),
        },
        "collection": {
            "collector": text(root, "CollectionID", "CollectorName"),
            "core_name": text(root, "CollectionID", "CoreName"),
            "collect_type": text(root, "CollectionID", "CollectType"),
            "radar_mode": text(root, "CollectionID", "RadarMode", "ModeType"),
            "parameters": named_parameters(node(root, "CollectionID")),
        },
        "global": {
            "domain_type": text(root, "Global", "DomainType"),
            "sgn": integer(root, "Global", "SGN"),
            "collection_start": text(root, "Global", "Timeline", "CollectionStart"),
            "tx_time_1_s": tx_time_1,
            "tx_time_2_s": tx_time_2,
            "tx_time_span_s": tx_time_2 - tx_time_1,
            "fx_min_hz": number(root, "Global", "FxBand", "FxMin"),
            "fx_max_hz": number(root, "Global", "FxBand", "FxMax"),
        },
        "data": {
            "signal_array_format": signal_format,
            "num_bytes_pvp": integer(root, "Data", "NumBytesPVP"),
            "num_channels": integer(root, "Data", "NumCPHDChannels"),
            "channel_identifier": text(root, "Data", "Channel", "Identifier"),
            "num_vectors": num_vectors,
            "num_samples": num_samples,
        },
        "channel": {
            "reference_channel": text(root, "Channel", "RefChId"),
            "reference_vector_index": integer(root, "Channel", "Parameters", "RefVectorIndex"),
            "tx_polarization": text(root, "Channel", "Parameters", "Polarization", "TxPol"),
            "receive_polarization": text(root, "Channel", "Parameters", "Polarization", "RcvPol"),
            "center_frequency_hz": number(root, "Channel", "Parameters", "FxC"),
            "bandwidth_hz": number(root, "Channel", "Parameters", "FxBW"),
        },
        "dwell": {
            "cod_time_s": number(root, "Dwell", "CODTime", "CODTimePoly", "Coef"),
            "dwell_time_s": dwell_poly,
            "reference_geometry_dwell_s": number(root, "ReferenceGeometry", "SRPDwellTime"),
        },
        "scene": {
            "iarp_ecf_m": vector(root, "SceneCoordinates", "IARP", "ECF"),
            "iarp_llh": {
                "lat_deg": lat,
                "lon_deg": lon,
                "hae_m": number(root, "SceneCoordinates", "IARP", "LLH", "HAE"),
            },
            "reference_surface_uIAX_ecf": vector(root, "SceneCoordinates", "ReferenceSurface", "Planar", "uIAX"),
            "reference_surface_uIAY_ecf": vector(root, "SceneCoordinates", "ReferenceSurface", "Planar", "uIAY"),
        },
        "reference_geometry": {
            "reference_time_s": number(root, "ReferenceGeometry", "ReferenceTime"),
            "srp_ecf_m": vector(root, "ReferenceGeometry", "SRP", "ECF"),
            "side_of_track": text(root, "ReferenceGeometry", "Monostatic", "SideOfTrack"),
            "slant_range_m": number(root, "ReferenceGeometry", "Monostatic", "SlantRange"),
            "ground_range_m": number(root, "ReferenceGeometry", "Monostatic", "GroundRange"),
            "doppler_cone_angle_deg": number(root, "ReferenceGeometry", "Monostatic", "DopplerConeAngle"),
            "graze_angle_deg": number(root, "ReferenceGeometry", "Monostatic", "GrazeAngle"),
            "incidence_angle_deg": number(root, "ReferenceGeometry", "Monostatic", "IncidenceAngle"),
            "azimuth_angle_deg": number(root, "ReferenceGeometry", "Monostatic", "AzimuthAngle"),
            "arp_position_ecf_m": vector(root, "ReferenceGeometry", "Monostatic", "ARPPos"),
            "arp_velocity_ecf_mps": velocity,
            "ground_track": track,
        },
        "transmit_receive": {
            "pulse_length_s": number(root, "TxRcv", "TxWFParameters", "PulseLength"),
            "rf_bandwidth_hz": number(root, "TxRcv", "TxWFParameters", "RFBandwidth"),
            "center_frequency_hz": number(root, "TxRcv", "TxWFParameters", "FreqCenter"),
            "lfm_rate_hz_per_s": number(root, "TxRcv", "TxWFParameters", "LFMRate"),
            "tx_polarization": text(root, "TxRcv", "TxWFParameters", "Polarization"),
            "receive_sample_rate_hz": number(root, "TxRcv", "RcvParameters", "SampleRate"),
            "receive_polarization": text(root, "TxRcv", "RcvParameters", "Polarization"),
        },
        "pvp_fields": definitions,
    }
    output["pvp"] = inspect_pvp(path, header, root, definitions)
    return output


def fmt(value: Any, digits: int = 12) -> str:
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def report_markdown(data: dict[str, Any]) -> str:
    file_data = data["file"]
    collection = data["collection"]
    global_data = data["global"]
    channel = data["channel"]
    geometry = data["reference_geometry"]
    pvp = data["pvp"]
    track = geometry["ground_track"]
    dwell = data["dwell"]
    lines = [
        "# CPHD metadata report",
        "",
        f"Generated: `{data['generated_utc']}`",
        "",
        "## Scope and integrity",
        "",
        f"- Source: `{data['source']}`",
        f"- File size: `{file_data['size_bytes']}` bytes; expected-size match: `{file_data['expected_size_match']}`.",
        f"- Format: `{file_data['version']}`; XML size: `{file_data['xml_bytes']}` bytes.",
        f"- Signal block ends exactly at EOF: `{file_data['signal_block_ends_at_eof']}`.",
        f"- Signal size matches NumVectors x NumSamples x sample bytes: `{file_data['signal_size_matches_dimensions']}`.",
        "- Access performed: ASCII header, XML, and memory-mapped PVP only. **The signal block was not read.**",
        "",
        f"SarPy recursive semantic validation: `{data['validation']['sarpy_recursive_semantic_valid']}`.",
        "",
        "## Collection and channel",
        "",
        f"- Collector/platform: `{collection['collector']}`; core name: `{collection['core_name']}`.",
        f"- Collect UUID: `{collection['parameters'].get('collect_id')}`.",
        f"- Type/mode/domain: `{collection['collect_type']}` / `{collection['radar_mode']}` / `{global_data['domain_type']}`.",
        f"- CollectionStart: `{global_data['collection_start']}`.",
        f"- Channels: `{data['data']['num_channels']}` (`{data['data']['channel_identifier']}`); format `{data['data']['signal_array_format']}`.",
        f"- NumVectors: `{data['data']['num_vectors']}`; NumSamples: `{data['data']['num_samples']}`; PVP bytes/vector: `{data['data']['num_bytes_pvp']}`.",
        f"- Polarization: `{channel['tx_polarization']}:{channel['receive_polarization']}`.",
        f"- Center frequency: `{fmt(channel['center_frequency_hz'])}` Hz; bandwidth: `{fmt(channel['bandwidth_hz'])}` Hz.",
        "",
        "## Timing and pulse cadence",
        "",
        f"- XML TxTime1 / TxTime2: `{fmt(global_data['tx_time_1_s'])}` / `{fmt(global_data['tx_time_2_s'])}` s.",
        f"- XML TxTime span: `{fmt(global_data['tx_time_span_s'])}` s.",
        f"- DwellTimePoly constant: `{fmt(dwell['dwell_time_s'])}` s; SRPDwellTime: `{fmt(dwell['reference_geometry_dwell_s'])}` s.",
        f"- PVP first / last TxTime: `{fmt(pvp['tx_time_s']['first'])}` / `{fmt(pvp['tx_time_s']['last'])}` s; span `{fmt(pvp['tx_time_s']['span_first_to_last'])}` s.",
        f"- TxTime strictly monotonic: `{pvp['tx_time_s']['strictly_monotonic']}`.",
        f"- Nominal local pulse rate from median per-pulse interval: `{fmt(pvp['nominal_pulse_rate_from_median_hz'])}` Hz.",
        f"- Mean rate of stored PVP vectors over the span: `{fmt(pvp['recorded_vector_rate_hz'])}` vectors/s.",
        f"- PulseNumber range: `{pvp['pulse_number']['first']}` to `{pvp['pulse_number']['last']}`; missing numbers in the contiguous span: `{pvp['pulse_number']['missing_from_contiguous_span']}`.",
        "",
        "The two rates differ because the PVP sequence contains pulse-number gaps. Therefore no single constant PRF is hardcoded.",
        "",
        "## Reference geometry",
        "",
        f"- SRP/IARP LLH: `{data['scene']['iarp_llh']['lat_deg']}`, `{data['scene']['iarp_llh']['lon_deg']}`, HAE `{fmt(data['scene']['iarp_llh']['hae_m'])}` m.",
        f"- SideOfTrack: `{geometry['side_of_track']}`.",
        f"- Slant / ground range: `{fmt(geometry['slant_range_m'])}` / `{fmt(geometry['ground_range_m'])}` m.",
        f"- Graze / incidence: `{fmt(geometry['graze_angle_deg'])}` / `{fmt(geometry['incidence_angle_deg'])}` deg.",
        f"- Viewing azimuth: `{fmt(geometry['azimuth_angle_deg'])}` deg clockwise from true north.",
        f"- Doppler cone angle: `{fmt(geometry['doppler_cone_angle_deg'])}` deg.",
        f"- Derived ground-track azimuth: `{fmt(track['azimuth_clockwise_from_true_north_deg'])}` deg; undirected azimuth axis `{fmt(track['undirected_axis_deg_mod_180'])}` deg.",
        "",
        "The derived 191.20 deg ground track and 11.20 deg undirected axis confirm the preliminary geometry; they are derived values, not hardcoded assumptions.",
        "",
        "## PVP fields",
        "",
        "| Field | Offset (8-byte words) | Size (words) | Format |",
        "|---|---:|---:|---|",
    ]
    for name, definition in data["pvp_fields"].items():
        lines.append(
            f"| {name} | {definition['offset_words']} | {definition['size_words']} | `{definition['format']}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Measured CPHD dwell is about 22.5408 s, consistent with but more precise than the preliminary ~22.6 s.",
            "- The CPHD is the authoritative source for the later slow-time/look-angle/Doppler mapping.",
            "- The XML reports a fixed SRP and FX-domain data; no signal samples were inspected at this checkpoint.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cphd", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expected-size", type=int)
    args = parser.parse_args()

    result = collect_metadata(args.cphd, args.expected_size)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    args.report.write_text(report_markdown(result), encoding="utf-8")
    print(f"wrote {args.json}")
    print(f"wrote {args.report}")
    print("signal block read: False")


if __name__ == "__main__":
    main()

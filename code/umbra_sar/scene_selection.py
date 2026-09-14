"""Pure, deterministic primitives for the Block16A Umbra scene selector.

The module deliberately contains no selected-scene list and performs no network
I/O.  The runner owns catalog/reference retrieval; this module owns parsing,
auditing, geometry, observability, gating, ranking, and provenance semantics.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, transform, unary_union
from shapely.validation import make_valid


UUID_RE = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
VANDENBERG_UUID = "9d8283d8-550d-4435-899f-5483d2c1abcc"
VANDENBERG_NAMES = {
    "2025-02-16-18-55-44_UMBRA-10",
    "2025-02-16-18-55-33_UMBRA-10",
}


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_identifier(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan"}:
        return None
    return text.lower() if UUID_RE.fullmatch(text) else text


def parse_datetime(value: Any) -> datetime | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def asset_kind(name: str, asset: Mapping[str, Any]) -> str:
    label = " ".join((name, str(asset.get("title", "")), str(asset.get("description", "")))).lower()
    if "cphd" in label or name.lower().endswith(".cphd"):
        return "CPHD"
    if "sicd" in label and (name.lower().endswith((".nitf", ".ntf", ".xml"))):
        return "SICD_XML" if name.lower().endswith(".xml") else "SICD"
    if "sidd" in label:
        return "SIDD"
    if "gec" in label:
        return "GEC"
    if name.lower().endswith((".tif", ".tiff")):
        return "TIFF"
    if name.lower().endswith(".json"):
        return "STAC"
    return "OTHER"


def _object_lookup(objects: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(row.get("key", "")): row for row in objects}


def _public_asset_key(stac_key: str, name: str) -> str:
    return stac_key.rsplit("/", 1)[0] + "/" + name


def _geometry_hash(geometry: Any) -> str:
    return sha256_bytes(canonical_json_bytes(geometry)) if geometry else "missing"


def acquisition_key(collect_id: Any, *, platform: Any, start: Any, end: Any, geometry: Any) -> str:
    cid = normalized_identifier(collect_id)
    if cid:
        return "collect:" + cid
    fallback = {
        "platform": normalized_identifier(platform),
        "start": parse_datetime(start).isoformat() if parse_datetime(start) else None,
        "end": parse_datetime(end).isoformat() if parse_datetime(end) else None,
        "geometry_sha256": _geometry_hash(geometry),
    }
    return "fallback:" + sha256_bytes(canonical_json_bytes(fallback))[:24]


def normalize_stac_item(
    item: Mapping[str, Any],
    *,
    stac_key: str,
    objects: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    props = dict(item.get("properties") or {})
    start, end = parse_datetime(props.get("start_datetime")), parse_datetime(props.get("end_datetime"))
    duration = (end - start).total_seconds() if start and end else None
    by_key = _object_lookup(objects)
    listed_by_kind: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for listed in objects:
        listed_by_kind[asset_kind(Path(str(listed.get("key", ""))).name, {})].append(listed)
    assets: list[dict[str, Any]] = []
    for name, raw in sorted((item.get("assets") or {}).items()):
        raw = dict(raw or {})
        public_key = _public_asset_key(stac_key, name)
        kind = asset_kind(name, raw)
        listing = by_key.get(public_key, {})
        if not listing and kind in {"CPHD", "SICD", "SICD_XML", "SIDD", "GEC", "STAC"}:
            candidates = listed_by_kind.get(kind, [])
            if candidates:
                listing = max(candidates, key=lambda value: int(value.get("size_bytes") or 0))
                public_key = str(listing.get("key"))
        assets.append({
            "name": name,
            "kind": kind,
            "href": raw.get("href"),
            "public_key": public_key,
            "size_bytes": int(listing["size_bytes"]) if str(listing.get("size_bytes", "")).isdigit() else None,
            "etag": listing.get("etag"),
            "last_modified": listing.get("last_modified"),
        })
    kinds = defaultdict(list)
    for asset in assets:
        kinds[asset["kind"]].append(asset)
    geometry = item.get("geometry")
    collect_id = normalized_identifier(props.get("umbra:collect_id"))
    key = acquisition_key(collect_id, platform=props.get("platform"), start=props.get("start_datetime"), end=props.get("end_datetime"), geometry=geometry)
    processing_version = props.get("processing:version")
    software = props.get("processing:software")
    pkey = sha256_bytes(canonical_json_bytes({
        "acquisition_key": key,
        "stac_item_id": item.get("id"),
        "processing_version": processing_version,
        "processing_created": props.get("created"),
        "stac_key": stac_key,
    }))[:24]
    basename = Path(stac_key).name.removesuffix(".stac.v2.json")
    return {
        "acquisition_key": key,
        "processing_key": "processing:" + pkey,
        "collect_id": collect_id,
        "task_id": normalized_identifier(props.get("umbra:task_id")),
        "stac_item_id": normalized_identifier(item.get("id")),
        "collect_name": basename,
        "platform": props.get("platform"),
        "datetime_utc": props.get("datetime"),
        "start_datetime_utc": props.get("start_datetime"),
        "end_datetime_utc": props.get("end_datetime"),
        "catalog_duration_s": duration,
        "processing_version": processing_version,
        "processing_created_utc": props.get("created"),
        "processing_updated_utc": props.get("updated"),
        "processing_software_json": json.dumps(software, sort_keys=True) if software is not None else "",
        "instrument_mode": props.get("sar:instrument_mode"),
        "product_type": props.get("sar:product_type"),
        "platform_count": len(props.get("platforms") or []) or (1 if props.get("platform") else 0),
        "is_multistatic": "multistatic" in json.dumps(item).lower(),
        "incidence_deg": as_float(props.get("view:incidence_angle")),
        "view_azimuth_deg": as_float(props.get("view:azimuth")),
        "look_side": props.get("sar:observation_direction"),
        "polarizations_json": json.dumps(props.get("sar:polarizations") or []),
        "resolution_range_m": as_float(props.get("sar:resolution_range")),
        "resolution_azimuth_m": as_float(props.get("sar:resolution_azimuth")),
        "best_resolution_range_m": as_float(props.get("umbra:best_resolution_range_meters")),
        "best_resolution_azimuth_m": as_float(props.get("umbra:best_resolution_azimuth_meters")),
        "geometry_json": json.dumps(geometry, separators=(",", ":")) if geometry else "",
        "geometry_sha256": _geometry_hash(geometry),
        "stac_s3_key": stac_key,
        "asset_count": len(assets),
        "assets_json": json.dumps(assets, sort_keys=True, separators=(",", ":")),
        "has_cphd": bool(kinds["CPHD"]),
        "has_sicd": bool(kinds["SICD"]),
        "has_sicd_xml": bool(kinds["SICD_XML"]),
        "has_gec_or_preview": bool(kinds["GEC"] or kinds["TIFF"]),
        "cphd_count": len(kinds["CPHD"]),
        "sicd_count": len(kinds["SICD"]),
        "cphd_size_bytes": max((x["size_bytes"] or 0 for x in kinds["CPHD"]), default=0) or None,
        "sicd_size_bytes": max((x["size_bytes"] or 0 for x in kinds["SICD"]), default=0) or None,
    }


def anomaly_flags(record: Mapping[str, Any], snapshot_time: datetime, config: Mapping[str, Any]) -> list[str]:
    limits = config["plausibility"]
    flags: list[str] = []
    start, end = parse_datetime(record.get("start_datetime_utc")), parse_datetime(record.get("end_datetime_utc"))
    earliest = parse_datetime(limits["earliest_acquisition_utc"])
    tolerance = float(limits["future_tolerance_s"])
    if start and start < earliest:
        flags.append("date_before_plausible_interval")
    if start and (start - snapshot_time).total_seconds() > tolerance:
        flags.append("date_in_future")
    if start and end and end < start:
        flags.append("start_end_inverted")
    duration = as_float(record.get("catalog_duration_s"))
    if duration is not None and duration <= 0:
        flags.append("dwell_nonpositive")
    if duration is None:
        flags.append("dwell_missing")
    elif duration < float(limits["catalog_duration_min_s"]) or duration > float(limits["catalog_duration_max_s"]):
        flags.append("dwell_implausible")
    if not record.get("geometry_json"):
        flags.append("geometry_empty")
    else:
        try:
            geometry = repaired_geometry(json.loads(str(record["geometry_json"])))
            if geometry.is_empty:
                flags.append("geometry_empty")
            minx, miny, maxx, maxy = geometry.bounds
            if miny < -90 or maxy > 90 or minx < -180 or maxx > 180:
                flags.append("coordinates_invalid")
        except Exception:
            flags.append("geometry_invalid_unrepairable")
    incidence, azimuth = as_float(record.get("incidence_deg")), as_float(record.get("view_azimuth_deg"))
    if incidence is not None and not 0 <= incidence <= 90:
        flags.append("incidence_out_of_range")
    if azimuth is not None and not 0 <= azimuth <= 360:
        flags.append("azimuth_out_of_range")
    if int(record.get("cphd_count") or 0) > 1 or int(record.get("sicd_count") or 0) > 1:
        flags.append("multiple_products_or_channels")
    if record.get("has_cphd") and not record.get("has_sicd"):
        flags.append("cphd_without_sicd")
    if record.get("has_sicd") and not record.get("has_cphd"):
        flags.append("sicd_without_cphd")
    if str(record.get("instrument_mode", "")).upper() not in {str(x).upper() for x in limits["allowed_instrument_modes"]}:
        flags.append("mode_not_allowed")
    if record.get("is_multistatic"):
        flags.append("multistatic")
    if not record.get("collect_id"):
        flags.append("collect_id_missing")
    assets = json.loads(record.get("assets_json") or "[]")
    names = [x.get("name") for x in assets]
    if len(names) != len(set(names)):
        flags.append("duplicate_assets")
    for asset in assets:
        size = asset.get("size_bytes")
        if size is not None and int(size) <= 0:
            flags.append("asset_size_invalid")
            break
    return sorted(set(flags))


def _completeness(record: Mapping[str, Any]) -> int:
    fields = ("collect_id", "task_id", "stac_item_id", "start_datetime_utc", "end_datetime_utc", "geometry_json", "incidence_deg", "view_azimuth_deg", "processing_version")
    return sum(record.get(field) not in (None, "") for field in fields)


def processing_preference(record: Mapping[str, Any]) -> tuple[Any, ...]:
    created = parse_datetime(record.get("processing_updated_utc") or record.get("processing_created_utc"))
    created_value = created.timestamp() if created else float("-inf")
    fatal = len(json.loads(record.get("anomaly_flags_json") or "[]"))
    verifiable = int(bool(record.get("cphd_size_bytes"))) + int(bool(record.get("sicd_size_bytes")))
    return (
        int(bool(record.get("has_cphd") and record.get("has_sicd"))),
        _completeness(record),
        -fatal,
        created_value,
        verifiable,
        str(record.get("processing_key")),
    )


def deduplicate_processings(records: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in records:
        groups[str(source["acquisition_key"])].append(dict(source))
    acquisitions, variants = [], []
    for key in sorted(groups):
        ordered = sorted(groups[key], key=processing_preference, reverse=True)
        preferred_key = ordered[0]["processing_key"]
        for index, row in enumerate(ordered):
            row["preferred_processing"] = row["processing_key"] == preferred_key
            row["processing_variant_rank"] = index + 1
            row["processing_variant_count"] = len(ordered)
            variants.append(row)
        acquisitions.append(dict(ordered[0]))
    return acquisitions, variants


def repaired_geometry(geometry: Mapping[str, Any] | BaseGeometry) -> BaseGeometry:
    candidate = geometry if isinstance(geometry, BaseGeometry) else shape(geometry)
    candidate = make_valid(candidate) if not candidate.is_valid else candidate
    polygons: list[Polygon] = []
    if isinstance(candidate, Polygon):
        polygons = [candidate]
    elif isinstance(candidate, MultiPolygon):
        polygons = list(candidate.geoms)
    elif isinstance(candidate, GeometryCollection):
        polygons = [g for g in candidate.geoms if isinstance(g, Polygon)]
    if not polygons:
        raise ValueError("geometry contains no polygon")
    return polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)


def _iter_polygons(geometry: BaseGeometry) -> Iterable[Polygon]:
    if isinstance(geometry, Polygon):
        yield geometry
    elif isinstance(geometry, MultiPolygon):
        yield from geometry.geoms
    elif isinstance(geometry, GeometryCollection):
        for part in geometry.geoms:
            yield from _iter_polygons(part)


def _ring_area_m2(coords: Sequence[Sequence[float]]) -> float:
    if len(coords) < 3:
        return 0.0
    radius = 6371008.8
    total = 0.0
    for first, second in zip(coords, coords[1:] + coords[:1]):
        lon1, lat1 = math.radians(first[0]), math.radians(first[1])
        lon2, lat2 = math.radians(second[0]), math.radians(second[1])
        delta = (lon2 - lon1 + math.pi) % (2 * math.pi) - math.pi
        total += delta * (2 + math.sin(lat1) + math.sin(lat2))
    return total * radius * radius / 2


def geodesic_area_m2(geometry: BaseGeometry) -> float:
    total = 0.0
    for polygon in _iter_polygons(geometry):
        exterior = abs(_ring_area_m2(list(polygon.exterior.coords)))
        holes = sum(abs(_ring_area_m2(list(ring.coords))) for ring in polygon.interiors)
        total += max(0.0, exterior - holes)
    return total


def representative_lonlat(geometry: BaseGeometry) -> tuple[float, float]:
    point = geometry.representative_point()
    lon = ((point.x + 180) % 360) - 180
    return float(lon), float(point.y)


def _local_scale_m(point: Point) -> tuple[float, float]:
    return 111320.0 * max(math.cos(math.radians(point.y)), 0.01), 110574.0


def _distance_to_boundary_m(point: Point, geometry: BaseGeometry) -> float:
    a, b = nearest_points(point, geometry.boundary)
    sx, sy = _local_scale_m(point)
    return math.hypot((a.x - b.x) * sx, (a.y - b.y) * sy)


def marine_geometry_metrics(footprint: Mapping[str, Any] | BaseGeometry, land: BaseGeometry | None) -> dict[str, Any]:
    repaired = repaired_geometry(footprint)
    area = geodesic_area_m2(repaired)
    if land is None:
        return {
            "geometry_valid": True, "footprint_area_km2": area / 1e6,
            "ocean_fraction": None, "land_fraction": None,
            "representative_ocean_lon": None, "representative_ocean_lat": None,
            "coast_distance_m_proxy": None, "max_ocean_roi_diameter_m_proxy": None,
            "ocean_roi_available": None, "land_control_available": None,
            "geometry_role": "unevaluable_without_preliminary_land_mask",
        }
    land_piece = make_valid(repaired.intersection(land))
    ocean_piece = make_valid(repaired.difference(land))
    land_area = geodesic_area_m2(land_piece)
    ocean_area = geodesic_area_m2(ocean_piece)
    denominator = max(land_area + ocean_area, area, np.finfo(float).eps)
    ocean_fraction = min(1.0, max(0.0, ocean_area / denominator))
    if ocean_piece.is_empty:
        lon = lat = clearance = diameter = None
    else:
        point = ocean_piece.representative_point()
        lon, lat = representative_lonlat(ocean_piece)
        clearance = _distance_to_boundary_m(point, ocean_piece)
        diameter = 2 * clearance
    return {
        "geometry_valid": True,
        "footprint_area_km2": area / 1e6,
        "ocean_fraction": ocean_fraction,
        "land_fraction": 1.0 - ocean_fraction,
        "representative_ocean_lon": lon,
        "representative_ocean_lat": lat,
        "coast_distance_m_proxy": clearance,
        "max_ocean_roi_diameter_m_proxy": diameter,
        "ocean_roi_available": bool(ocean_area >= 1e6 and diameter is not None and diameter >= 500),
        "land_control_available": bool(land_area / denominator >= 0.01),
        "geometry_role": "natural_earth_preliminary_only",
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(((lon2 - lon1 + 180) % 360) - 180)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(min(1.0, math.sqrt(value)))


def direction_from_to(direction_from_deg: float) -> float:
    return (float(direction_from_deg) + 180.0) % 360.0


def axial_direction_difference_deg(direction_deg: float, axis_deg: float) -> float:
    return abs(((float(direction_deg) - float(axis_deg) + 90.0) % 180.0) - 90.0)


def full_direction_difference_deg(first_deg: float, second_deg: float) -> float:
    return ((float(first_deg) - float(second_deg) + 180.0) % 360.0) - 180.0


def temporal_metrics(
    *,
    catalog_duration_s: float | None,
    period_s: float | None,
    cphd_tx_time_span_s: float | None = None,
    sicd_processed_aperture_s: float | None = None,
    nominal_look_duration_s: float = 6.0,
    minimum_independent_looks: int = 3,
    sliding_step_s: float = 1.25,
    minimum_cycles: float = 1.25,
    preferred_cycles: float = 2.0,
) -> dict[str, Any]:
    sources = (("cphd_tx_time_span_s", cphd_tx_time_span_s), ("sicd_processed_aperture_s", sicd_processed_aperture_s), ("catalog_duration_s", catalog_duration_s))
    source, duration = next(((name, as_float(value)) for name, value in sources if as_float(value) is not None), (None, None))
    if duration is None or duration <= 0:
        return {"duration_source": source, "usable_duration_s": duration, "temporal_not_verified": True, "temporal_hard_gate": None, "temporal_preferred_gate": None}
    max_look = duration / minimum_independent_looks
    look = min(float(nominal_look_duration_s), max_look)
    independent = int(math.floor((duration + 1e-12) / look)) if look > 0 else 0
    center_span = max(0.0, duration - look)
    sliding = int(math.floor(center_span / sliding_step_s + 1e-12)) + 1
    cycles = None if period_s is None or as_float(period_s) is None or float(period_s) <= 0 else center_span / float(period_s)
    hard = None if cycles is None else independent >= minimum_independent_looks and cycles >= minimum_cycles
    preferred = None if cycles is None else independent >= minimum_independent_looks and cycles >= preferred_cycles
    return {
        "duration_source": source,
        "catalog_duration_s": as_float(catalog_duration_s),
        "cphd_tx_time_span_s": as_float(cphd_tx_time_span_s),
        "sicd_processed_aperture_s": as_float(sicd_processed_aperture_s),
        "usable_duration_s": duration,
        "maximum_compatible_look_duration_s": max_look,
        "selected_nominal_look_duration_s": look,
        "usable_center_span_s": center_span,
        "independent_look_count": independent,
        "sliding_center_count": sliding,
        "look_duration_to_period_ratio": None if period_s is None or float(period_s) <= 0 else look / float(period_s),
        "observable_cycles": cycles,
        "available_aperture_fraction": 1.0,
        "edge_loss_s": duration - center_span,
        "temporal_not_verified": source == "catalog_duration_s",
        "temporal_hard_gate": hard,
        "temporal_preferred_gate": preferred,
    }


def deepwater_wavelength_m(period_s: float, gravity_m_s2: float = 9.80665) -> float:
    return gravity_m_s2 * float(period_s) ** 2 / (2 * math.pi)


def clean_spectral_arrays(
    frequency_hz: Sequence[float], density: Sequence[float], *directional: Sequence[float], missing_codes: Sequence[float] = (99, 999, 9999)
) -> tuple[np.ndarray, ...]:
    arrays = [np.asarray(frequency_hz, float), np.asarray(density, float), *(np.asarray(x, float) for x in directional)]
    if len({array.shape for array in arrays}) != 1:
        raise ValueError("spectral arrays have inconsistent lengths")
    f, energy = arrays[:2]
    if not np.all(np.isfinite(f)) or np.any(f <= 0) or np.any(np.diff(f) <= 0):
        raise ValueError("frequencies must be finite, positive, and strictly increasing")
    valid = np.isfinite(energy) & (energy >= 0)
    for code in missing_codes:
        valid &= ~np.isclose(energy, code)
    output = [f[valid], energy[valid]]
    for array in arrays[2:]:
        cleaned = array[valid].astype(float, copy=True)
        invalid = ~np.isfinite(cleaned)
        for code in missing_codes:
            invalid |= np.isclose(cleaned, code)
        cleaned[invalid] = np.nan
        output.append(cleaned)
    if len(output[0]) < 2:
        raise ValueError("fewer than two valid spectral bins")
    return tuple(output)


def spectral_hm0_m(frequency_hz: Sequence[float], density_m2_hz: Sequence[float]) -> float:
    f, density = clean_spectral_arrays(frequency_hz, density_m2_hz)[:2]
    return 4.0 * math.sqrt(max(float(np.trapezoid(density, f)), 0.0))


def spectral_peak(frequency_hz: Sequence[float], density_m2_hz: Sequence[float]) -> dict[str, float]:
    f, density = clean_spectral_arrays(frequency_hz, density_m2_hz)[:2]
    index = int(np.argmax(density))
    return {"peak_frequency_hz": float(f[index]), "measured_peak_period_s": float(1 / f[index]), "peak_density_m2_hz": float(density[index])}


def period_fields(*, model_peak: Any = None, model_mean: Any = None, measured_peak: Any = None) -> dict[str, Any]:
    measured, peak, mean = as_float(measured_peak), as_float(model_peak), as_float(model_mean)
    if measured is not None:
        proxy, source, provisional = measured, "measured_peak_period", False
    elif peak is not None:
        proxy, source, provisional = peak, "model_peak_period", True
    elif mean is not None:
        proxy, source, provisional = mean, "model_mean_period_proxy", True
    else:
        proxy, source, provisional = None, "missing", True
    return {"measured_peak_period_s": measured, "model_peak_period_s": peak, "model_mean_period_s": mean, "period_proxy_for_screening_s": proxy, "period_proxy_source": source, "period_metrics_provisional": provisional}


def reference_classification(*, station_active: bool, spectrum_density: bool, alpha1: bool, alpha2: bool, r1: bool, r2: bool, within_distance: bool, within_time: bool, model_available: bool) -> str:
    complete = all((spectrum_density, alpha1, alpha2, r1, r2, within_distance, within_time))
    if complete:
        return "measured_complete"
    if spectrum_density and within_distance and within_time:
        return "measured_incomplete"
    if station_active and within_distance:
        return "nearby_buoy_without_spectrum"
    if model_available:
        return "model_only"
    return "no_reference"


def observation_offset_s(scene_time: Any, observation_time: Any) -> float | None:
    scene, observation = parse_datetime(scene_time), parse_datetime(observation_time)
    return None if scene is None or observation is None else (observation - scene).total_seconds()


def cphd_sicd_association(cphd: Mapping[str, Any], sicd: Mapping[str, Any]) -> bool:
    c_collect, s_collect = normalized_identifier(cphd.get("collect_id")), normalized_identifier(sicd.get("collect_id"))
    if c_collect and s_collect:
        return c_collect == s_collect
    c_start, s_start = parse_datetime(cphd.get("collect_start")), parse_datetime(sicd.get("collect_start"))
    c_platform, s_platform = normalized_identifier(cphd.get("platform")), normalized_identifier(sicd.get("platform"))
    return bool(c_start and s_start and c_platform and c_platform == s_platform and abs((c_start - s_start).total_seconds()) <= 1)


def is_vandenberg(record: Mapping[str, Any]) -> bool:
    return normalized_identifier(record.get("collect_id")) == VANDENBERG_UUID or str(record.get("collect_name")) in VANDENBERG_NAMES


def hard_gate_failures(record: Mapping[str, Any], config: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    anomalies = json.loads(record.get("anomaly_flags_json") or "[]")
    fatal = {"date_in_future", "start_end_inverted", "dwell_nonpositive", "dwell_implausible", "coordinates_invalid", "geometry_empty", "geometry_invalid_unrepairable", "multistatic"}
    if fatal.intersection(anomalies): failures.append("record_anomaly")
    if is_vandenberg(record): failures.append("vandenberg_regression_exclusion")
    if str(record.get("instrument_mode", "")).upper() != "SPOTLIGHT": failures.append("not_spotlight")
    if not as_bool(record.get("has_cphd")): failures.append("cphd_missing")
    if not as_bool(record.get("has_sicd")): failures.append("sicd_missing")
    if record.get("ocean_roi_available") is False: failures.append("ocean_roi_unavailable")
    duration = as_float(record.get("catalog_duration_s"))
    if duration is not None and duration < float(config["temporal"]["minimum_catalog_duration_s"]): failures.append("duration_short")
    temporal = record.get("temporal_hard_gate")
    if temporal is False: failures.append("insufficient_cycles_or_looks")
    delta = as_float(record.get("wave_range_axial_difference_deg"))
    if delta is not None and delta > float(config["direction"]["hard_max_axial_difference_deg"]): failures.append("unfavorable_wave_range_angle")
    incidence = as_float(record.get("incidence_deg"))
    low, high = config["plausibility"]["allowed_incidence_hard_deg"]
    if incidence is not None and not float(low) <= incidence <= float(high): failures.append("incidence_outside_hard_interval")
    if record.get("metadata_association_verified") is False: failures.append("cphd_sicd_mismatch")
    if record.get("preliminary_spatial_gate") is False: failures.append("preliminary_spatial_unfavorable")
    reference = record.get("reference_class")
    if reference == "measured_complete":
        if (as_float(record.get("measured_hm0_m")) or 0) < float(config["wave_model"]["minimum_swell_height_m"]): failures.append("weak_measured_sea_state")
        if (as_float(record.get("measured_peak_r1")) or 0) < float(config["wave_model"]["minimum_directional_concentration_r1"]): failures.append("weak_directional_concentration")
        if (as_float(record.get("measured_long_energy_fraction_f_le_0p1")) or 0) < float(config["wave_model"]["minimum_swell_energy_proxy_ratio"]): failures.append("measured_swell_not_dominant")
    if reference == "model_only":
        if (as_float(record.get("model_swell_height_m")) or 0) < float(config["wave_model"]["minimum_swell_height_m"]): failures.append("weak_model_swell")
        if (as_float(record.get("model_swell_energy_proxy_ratio")) or 0) < float(config["wave_model"]["minimum_swell_energy_proxy_ratio"]): failures.append("model_swell_not_dominant")
    return sorted(set(failures))


def classify_candidate(record: Mapping[str, Any], config: Mapping[str, Any]) -> tuple[str, list[str]]:
    failures = hard_gate_failures(record, config)
    if failures:
        control_failures = {"duration_short", "weak_measured_sea_state", "weak_directional_concentration", "measured_swell_not_dominant", "weak_model_swell", "model_swell_not_dominant"}
        if set(failures).issubset(control_failures) and (set(failures) != {"duration_short"} or 5 <= (as_float(record.get("catalog_duration_s")) or 0) <= 7):
            return "C", failures
        return "D", failures
    required_unknown = [record.get("ocean_roi_available"), record.get("temporal_hard_gate"), record.get("wave_range_axial_difference_deg"), record.get("metadata_association_verified"), record.get("preliminary_spatial_gate")]
    if any(value is None or value == "" for value in required_unknown):
        return "E", ["required_gate_not_evaluable"]
    reference = record.get("reference_class")
    if reference == "measured_complete":
        return "A", []
    if reference == "model_only":
        return "B", []
    if reference in {"measured_incomplete", "nearby_buoy_without_spectrum"}:
        return "C", ["reference_incomplete"]
    return "E", ["reference_missing"]


def _bounded(value: Any, low: float, high: float, *, reverse: bool = False) -> float:
    number = as_float(value)
    if number is None or high <= low:
        return 0.0
    score = min(1.0, max(0.0, (number - low) / (high - low)))
    return 1.0 - score if reverse else score


def transparent_score(record: Mapping[str, Any], category: str, config: Mapping[str, Any]) -> tuple[float, dict[str, float]]:
    weights = config["ranking"]["weights_measured" if category == "A" else "weights_model"]
    components = {
        "cycles": _bounded(record.get("observable_cycles"), config["temporal"]["minimum_observable_cycles"], config["temporal"]["preferred_observable_cycles"]),
        "direction": _bounded(record.get("wave_range_axial_difference_deg"), config["direction"]["preferred_max_axial_difference_deg"], config["direction"]["hard_max_axial_difference_deg"], reverse=True),
        "incidence": 1.0 if as_float(record.get("incidence_deg")) is not None and 15 <= float(record["incidence_deg"]) <= 35 else 0.5,
    }
    if category == "A":
        components.update({
            "swell_energy": _bounded(record.get("measured_hm0_m"), 0.5, 1.5),
            "directional_concentration": _bounded(record.get("measured_peak_r1"), 0.5, 0.7),
            "station_distance": _bounded(record.get("station_distance_km"), 30, 50, reverse=True),
        })
    else:
        components.update({
            "swell_height": _bounded(record.get("model_swell_height_m"), 0.5, 1.0),
            "swell_dominance": _bounded(record.get("model_swell_energy_proxy_ratio"), 0.5, 0.7),
        })
    score = 100 * sum(float(weights.get(name, 0)) * value for name, value in components.items())
    return score, components


def pareto_front(rows: Sequence[Mapping[str, Any]], *, maximize: Sequence[str], minimize: Sequence[str]) -> list[bool]:
    def value(row: Mapping[str, Any], key: str, missing: float) -> float:
        parsed = as_float(row.get(key))
        return missing if parsed is None else parsed
    result = []
    for i, row in enumerate(rows):
        dominated = False
        for j, other in enumerate(rows):
            if i == j: continue
            weak = all(value(other, k, -math.inf) >= value(row, k, -math.inf) for k in maximize)
            weak &= all(value(other, k, math.inf) <= value(row, k, math.inf) for k in minimize)
            strict = any(value(other, k, -math.inf) > value(row, k, -math.inf) for k in maximize)
            strict |= any(value(other, k, math.inf) < value(row, k, math.inf) for k in minimize)
            if weak and strict:
                dominated = True; break
        result.append(not dominated)
    return result


def rank_candidates(records: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    output = []
    for source in records:
        row = dict(source)
        category, reasons = classify_candidate(row, config)
        score, components = transparent_score(row, category, config) if category in {"A", "B"} else (0.0, {})
        row.update({"category": category, "gate_failures_json": json.dumps(reasons), "score": score, "score_components_json": json.dumps(components, sort_keys=True)})
        output.append(row)
    for category in "ABC":
        subset = [r for r in output if r["category"] == category]
        fronts = pareto_front(subset, maximize=("observable_cycles", "measured_hm0_m", "model_swell_height_m"), minimize=("wave_range_axial_difference_deg", "station_distance_km")) if subset else []
        for row, front in zip(subset, fronts): row["pareto_front"] = front
    for row in output:
        row.setdefault("pareto_front", False)
    output.sort(key=lambda row: ("ABCDE".index(row["category"]), not row.get("pareto_front", False), -float(row["score"]), str(row.get("acquisition_key"))))
    for index, row in enumerate(output, 1): row["overall_row_number"] = index
    return output


@dataclass
class ByteRangeBudget:
    maximum_bytes: int
    used_bytes: int = 0

    def reserve(self, requested_bytes: int) -> None:
        if requested_bytes < 0:
            raise ValueError("requested bytes must be nonnegative")
        if self.used_bytes + requested_bytes > self.maximum_bytes:
            raise RuntimeError("byte-range metadata budget exceeded")
        self.used_bytes += requested_bytes

    @property
    def remaining_bytes(self) -> int:
        return self.maximum_bytes - self.used_bytes


def crawl_status(*, listed_sidecars: int, parsed_sidecars: int, errors: Sequence[Any]) -> str:
    return "complete" if listed_sidecars == parsed_sidecars and not errors else "incomplete"


def snapshot_identity(manifest_core: Mapping[str, Any]) -> str:
    """Hash deterministic snapshot content, excluding storage path/timestamp."""
    return sha256_bytes(canonical_json_bytes(dict(manifest_core)))


def output_provenance(*, config_sha256: str, source_hashes: Mapping[str, str], endpoints: Sequence[str], cache_used: Sequence[str], errors: Sequence[Any]) -> dict[str, Any]:
    return {
        "config_sha256": config_sha256,
        "source_hashes": dict(sorted(source_hashes.items())),
        "endpoints": sorted(set(endpoints)),
        "cache_used": sorted(set(cache_used)),
        "errors": list(errors),
    }

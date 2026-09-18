"""Canonical metadata-only Block16A Umbra validation-scene selector.

This runner never requests a complete SAR product.  It creates an immutable
catalog snapshot, then performs preliminary coastline/model/reference screens
and bounded CPHD/SICD metadata preflights for a frozen number of finalists.
"""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import http.client
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import time
from typing import Any, Iterable, Mapping, Sequence
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
import numpy as np
from shapely import STRtree
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from umbra_sar.scene_selection import (
    ByteRangeBudget,
    anomaly_flags,
    as_bool,
    as_float,
    axial_direction_difference_deg,
    canonical_json_bytes,
    clean_spectral_arrays,
    crawl_status,
    deduplicate_processings,
    deepwater_wavelength_m,
    direction_from_to,
    full_direction_difference_deg,
    geodesic_area_m2,
    haversine_km,
    marine_geometry_metrics,
    normalize_stac_item,
    observation_offset_s,
    output_provenance,
    period_fields,
    rank_candidates,
    reference_classification,
    repaired_geometry,
    sha256_bytes,
    sha256_file,
    snapshot_identity,
    spectral_hm0_m,
    spectral_peak,
    temporal_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'umbra/selezione_scene/Block16_scene_selection'
CONFIG_PATH = BASE / "BLOCK16A_CONFIG.json"
CONFIG_HASH_PATH = BASE / "BLOCK16A_CONFIG.sha256"
SNAPSHOTS = BASE / "catalog_snapshots"
LEGACY_CACHE = ROOT / 'umbra/validazione/Block8_validation' / "catalog_raw" / "umbra_stac_v2_sidecars.jsonl.gz"
LAND_SHP = ROOT / 'umbra/validazione/Block8_validation' / "catalog_raw" / "ne_10m_land" / "ne_10m_land.shp"
USER_AGENT = "Umbra-thesis-Block16A-metadata-only/1.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")


def atomic_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None) -> None:
    if fields is None:
        fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["status"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(path, stream.getvalue().encode("utf-8"))


def atomic_gzip_lines(path: Path, lines: Iterable[str]) -> None:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as zipped:
        for line in lines:
            zipped.write(line.encode("utf-8"))
    atomic_bytes(path, buffer.getvalue())


def load_config() -> tuple[dict[str, Any], str]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    actual = sha256_file(CONFIG_PATH)
    expected = CONFIG_HASH_PATH.read_text(encoding="utf-8").split()[0]
    if actual != expected:
        raise RuntimeError(f"frozen configuration hash mismatch: {actual} != {expected}")
    return config, actual


def fetch_bytes(url: str, config: Mapping[str, Any], budget: ByteRangeBudget, *, byte_range: tuple[int, int] | None = None, method: str = "GET") -> tuple[bytes, Mapping[str, str]]:
    headers = {"User-Agent": USER_AGENT}
    if byte_range is not None:
        start, end = byte_range
        requested = end - start + 1
        if requested > int(config["byte_range_audit"]["max_per_request_bytes"]):
            raise RuntimeError("single byte-range exceeds configured limit")
        headers["Range"] = f"bytes={start}-{end}"
    last_error = None
    for attempt in range(int(config["catalog"]["retries"]) + 1):
        try:
            request = urllib.request.Request(url, headers=headers, method=method)
            with urllib.request.urlopen(request, timeout=float(config["catalog"]["timeout_s"])) as response:
                payload = b"" if method == "HEAD" else response.read()
                response_headers = dict(response.headers.items())
            budget.reserve(len(payload))
            return payload, response_headers
        except urllib.error.HTTPError as exc:
            last_error = exc
            if 400 <= exc.code < 500:
                break
            if attempt == int(config["catalog"]["retries"]):
                break
            time.sleep(float(config["catalog"]["retry_backoff_s"]) * (attempt + 1))
        except Exception as exc:
            last_error = exc
            if attempt == int(config["catalog"]["retries"]):
                break
            time.sleep(float(config["catalog"]["retry_backoff_s"]) * (attempt + 1))
    raise RuntimeError(f"request failed for {url}: {last_error!r}")


def list_s3(config: Mapping[str, Any], budget: ByteRangeBudget) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    endpoint = config["catalog"]["s3_endpoint"]
    prefix = config["catalog"]["s3_prefix"]
    token = None
    rows: list[dict[str, Any]] = []
    urls, errors = [], []
    parsed_endpoint = urllib.parse.urlsplit(endpoint)
    connection = http.client.HTTPSConnection(parsed_endpoint.netloc, timeout=float(config["catalog"]["timeout_s"]))
    while True:
        query = {"list-type": "2", "prefix": prefix, "max-keys": "1000", "encoding-type": "url"}
        if token:
            query["continuation-token"] = token
        url = endpoint + "?" + urllib.parse.urlencode(query)
        urls.append(url)
        payload = None; last_error = None
        for attempt in range(int(config["catalog"]["retries"]) + 1):
            try:
                path = (parsed_endpoint.path or "/") + "?" + urllib.parse.urlencode(query)
                connection.request("GET", path, headers={"User-Agent": USER_AGENT, "Connection": "keep-alive"})
                response = connection.getresponse(); candidate = response.read()
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {candidate[:200]!r}")
                budget.reserve(len(candidate)); payload = candidate; break
            except Exception as exc:
                last_error = exc
                try: connection.close()
                except Exception: pass
                connection = http.client.HTTPSConnection(parsed_endpoint.netloc, timeout=float(config["catalog"]["timeout_s"]))
                time.sleep(float(config["catalog"]["retry_backoff_s"]) * (attempt + 1))
        if payload is None:
            errors.append(repr(last_error)); break
        root = ET.fromstring(payload)
        namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        for node in root.findall("s3:Contents", namespace):
            key = urllib.parse.unquote(node.findtext("s3:Key", namespaces=namespace) or "")
            rows.append({
                "key": key,
                "size_bytes": int(node.findtext("s3:Size", namespaces=namespace) or 0),
                "last_modified": node.findtext("s3:LastModified", namespaces=namespace),
                "etag": (node.findtext("s3:ETag", namespaces=namespace) or "").strip('"'),
                "storage_class": node.findtext("s3:StorageClass", namespaces=namespace),
            })
        if root.findtext("s3:IsTruncated", namespaces=namespace) != "true":
            break
        token = root.findtext("s3:NextContinuationToken", namespaces=namespace)
        if not token:
            errors.append("truncated S3 listing without continuation token"); break
        if len(rows) % 10000 == 0:
            print(f"S3 listing: {len(rows)} objects", flush=True)
    connection.close()
    return rows, urls, errors


def normalize_listing_key(key: str) -> str:
    parts = key.split("/")
    uuid = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
    if len(parts) > 3 and parts[:2] == ["sar-data", "tasks"]:
        stop = next((i for i, part in enumerate(parts[2:], 2) if uuid.fullmatch(part)), 3)
        for index in range(2, stop):
            parts[index] = parts[index].replace("+", " ")
    return "/".join(parts)


def public_url(endpoint: str, key: str) -> str:
    return endpoint + urllib.parse.quote(key, safe="/")


def load_sidecar_cache() -> dict[str, tuple[dict[str, Any], int, str]]:
    result: dict[str, tuple[dict[str, Any], int, str]] = {}
    if LEGACY_CACHE.exists():
        with gzip.open(LEGACY_CACHE, "rt", encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                result[normalize_listing_key(record["key"])] = (record["item"], int(record.get("content_length", 0)), "Block8_read_only_cache")
    for snapshot in sorted(SNAPSHOTS.glob("*/sidecars.jsonl.gz"), reverse=True):
        try:
            with gzip.open(snapshot, "rt", encoding="utf-8") as stream:
                for line in stream:
                    record = json.loads(line)
                    result[record["key"]] = (record["item"], int(record.get("content_length", 0)), str(snapshot.relative_to(ROOT)))
            break
        except Exception:
            continue
    return result


def crawl_sidecars(keys: Sequence[str], config: Mapping[str, Any], budget: ByteRangeBudget) -> tuple[dict[str, tuple[dict[str, Any], int, str]], list[dict[str, str]], list[str]]:
    endpoint = config["catalog"]["s3_endpoint"]
    cache = load_sidecar_cache()
    missing = [key for key in keys if key not in cache]
    errors: list[dict[str, str]] = []
    urls: list[str] = []

    def fetch_one(key: str):
        url = public_url(endpoint, key)
        payload, _ = fetch_bytes(url, config, budget)
        return key, json.loads(payload), len(payload), url

    with ThreadPoolExecutor(max_workers=int(config["catalog"]["concurrency"])) as pool:
        futures = [pool.submit(fetch_one, key) for key in missing]
        for index, future in enumerate(as_completed(futures), 1):
            try:
                key, item, size, url = future.result()
                cache[key] = (item, size, "remote")
                urls.append(url)
            except Exception as exc:
                errors.append({"key": "unknown", "error": repr(exc)})
            if index % 250 == 0 or index == len(futures):
                print(f"STAC sidecars: {index}/{len(futures)} new; errors={len(errors)}", flush=True)
    selected = {key: cache[key] for key in keys if key in cache}
    return selected, errors, urls


def new_snapshot_path(now: datetime) -> Path:
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = SNAPSHOTS / stamp
    if path.exists():
        raise FileExistsError(f"snapshot already exists: {path}")
    path.mkdir(parents=True)
    return path


def build_snapshot(config: Mapping[str, Any], config_hash: str, budget: ByteRangeBudget) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    started = utc_now()
    snapshot = new_snapshot_path(started)
    objects, listing_urls, listing_errors = list_s3(config, budget)
    for row in objects:
        row["key"] = normalize_listing_key(row["key"])
    stac_keys = sorted({row["key"] for row in objects if row["key"].lower().endswith(".stac.v2.json")})
    sidecars, sidecar_errors, sidecar_urls = crawl_sidecars(stac_keys, config, budget)
    errors: list[Any] = [*listing_errors, *sidecar_errors]
    status = crawl_status(listed_sidecars=len(stac_keys), parsed_sidecars=len(sidecars), errors=errors)

    listing_buffer = io.StringIO(newline="")
    listing_writer = csv.DictWriter(listing_buffer, fieldnames=["key", "size_bytes", "last_modified", "etag", "storage_class"])
    listing_writer.writeheader(); listing_writer.writerows(sorted(objects, key=lambda row: row["key"]))
    atomic_gzip_lines(snapshot / "listing_s3.csv.gz", [listing_buffer.getvalue()])
    atomic_gzip_lines(snapshot / "sidecars.jsonl.gz", (
        json.dumps({"key": key, "content_length": sidecars[key][1], "cache_source": sidecars[key][2], "item": sidecars[key][0]}, separators=(",", ":")) + "\n"
        for key in sorted(sidecars)
    ))

    normalized: list[dict[str, Any]] = []
    objects_by_directory: dict[str, list[dict[str, Any]]] = {}
    for object_row in objects:
        objects_by_directory.setdefault(object_row["key"].rsplit("/", 1)[0], []).append(object_row)
    for key in sorted(sidecars):
        directory = key.rsplit("/", 1)[0]
        members = objects_by_directory.get(directory, [])
        row = normalize_stac_item(sidecars[key][0], stac_key=key, objects=members)
        row["anomaly_flags_json"] = json.dumps(anomaly_flags(row, started, config), separators=(",", ":"))
        normalized.append(row)
    acquisitions, variants = deduplicate_processings(normalized)
    atomic_csv(snapshot / "normalized_processings.csv", variants)
    atomic_csv(snapshot / "normalized_acquisitions.csv", acquisitions)
    atomic_json(snapshot / "errors.json", errors)
    core = {
        "schema_version": config["catalog"]["snapshot_schema"],
        "status": status,
        "config_sha256": config_hash,
        "object_count": len(objects),
        "listed_sidecar_count": len(stac_keys),
        "parsed_sidecar_count": len(sidecars),
        "processing_count": len(variants),
        "unique_acquisition_count": len(acquisitions),
        "error_count": len(errors),
        "listing_sha256": sha256_file(snapshot / "listing_s3.csv.gz"),
        "sidecars_sha256": sha256_file(snapshot / "sidecars.jsonl.gz"),
        "processing_table_sha256": sha256_file(snapshot / "normalized_processings.csv"),
        "acquisition_table_sha256": sha256_file(snapshot / "normalized_acquisitions.csv"),
    }
    manifest = {
        **core,
        "snapshot_identity_sha256": snapshot_identity(core),
        "started_utc": started.isoformat(),
        "completed_utc": utc_now().isoformat(),
        "endpoint": config["catalog"]["s3_endpoint"],
        "prefix": config["catalog"]["s3_prefix"],
        "metadata_bytes_downloaded": budget.used_bytes,
        "cache_sources": sorted({source for _, _, source in sidecars.values()}),
        "request_url_count": len(listing_urls) + len(sidecar_urls),
        "incomplete_fail_closed": status != "complete",
    }
    atomic_json(snapshot / "manifest.json", manifest)
    if status == "complete":
        atomic_csv(BASE / "BLOCK16A_CATALOG.csv", acquisitions)
        atomic_csv(BASE / "BLOCK16A_PROCESSING_VARIANTS.csv", variants)
    return snapshot, acquisitions, variants, manifest


def read_esri_polygon_shapefile(path: Path) -> list[Polygon]:
    """Read Polygon records from the fixed Natural Earth shapefile.

    This tiny reader avoids adding a GIS dependency to the frozen thesis
    environment. It supports the Polygon records used by Natural Earth only.
    """
    data = path.read_bytes()
    offset, rings = 100, []
    while offset + 8 <= len(data):
        _, words = struct.unpack(">2i", data[offset:offset + 8]); offset += 8
        content = data[offset:offset + 2 * words]; offset += 2 * words
        if len(content) < 44:
            continue
        kind = struct.unpack("<i", content[:4])[0]
        if kind == 0: continue
        if kind not in {5, 15, 25}:
            raise ValueError(f"unsupported shapefile shape type {kind}")
        parts_count, points_count = struct.unpack("<2i", content[36:44])
        starts = list(struct.unpack(f"<{parts_count}i", content[44:44 + 4 * parts_count])) + [points_count]
        point_offset = 44 + 4 * parts_count
        points = [struct.unpack("<2d", content[point_offset + 16 * i:point_offset + 16 * (i + 1)]) for i in range(points_count)]
        rings.extend(points[starts[i]:starts[i + 1]] for i in range(parts_count) if starts[i + 1] - starts[i] >= 4)
    outers, holes = [], []
    for ring in rings:
        polygon = Polygon(ring)
        (holes if polygon.exterior.is_ccw else outers).append(polygon)
    assignments: dict[int, list[Sequence[tuple[float, float]]]] = {index: [] for index in range(len(outers))}
    for hole in holes:
        representative = hole.representative_point()
        containers = [(outer.area, index) for index, outer in enumerate(outers) if outer.covers(representative)]
        if containers:
            assignments[min(containers)[1]].append(list(hole.exterior.coords))
        else:
            outers.append(hole); assignments[len(outers) - 1] = []
    return [Polygon(list(outer.exterior.coords), assignments[index]) for index, outer in enumerate(outers)]


def compute_marine_table(acquisitions: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    land_polygons = read_esri_polygon_shapefile(LAND_SHP)
    tree = STRtree(land_polygons)
    output = []
    for index, source in enumerate(acquisitions, 1):
        row = dict(source)
        duration = as_float(row.get("catalog_duration_s"))
        should_evaluate = duration is not None and 5 <= duration <= 120 and row.get("geometry_json")
        if should_evaluate:
            try:
                footprint = repaired_geometry(json.loads(row["geometry_json"]))
                hits = tree.query(footprint, predicate="intersects")
                local_land = unary_union([land_polygons[int(i)] for i in hits]) if len(hits) else Polygon()
                metrics = marine_geometry_metrics(footprint, local_land)
                threshold = config["marine"]
                metrics["ocean_roi_available"] = bool(
                    metrics["ocean_fraction"] >= float(threshold["minimum_ocean_fraction"])
                    and metrics["footprint_area_km2"] * metrics["ocean_fraction"] >= float(threshold["minimum_ocean_area_km2"])
                    and (metrics["max_ocean_roi_diameter_m_proxy"] or 0) >= float(threshold["minimum_internal_ocean_roi_diameter_m_proxy"])
                )
                row.update(metrics); row["geometry_error"] = ""
            except Exception as exc:
                row.update({"ocean_fraction": None, "land_fraction": None, "ocean_roi_available": None, "land_control_available": None, "geometry_error": repr(exc)})
        else:
            row.update({"ocean_fraction": None, "land_fraction": None, "ocean_roi_available": None, "land_control_available": None, "geometry_error": "not_evaluated_outside_temporal_band"})
        output.append(row)
        if index % 1000 == 0:
            print(f"marine geometry: {index}/{len(acquisitions)}", flush=True)
    return output


def wave_query_url(row: Mapping[str, Any], config: Mapping[str, Any]) -> str:
    when = datetime.fromisoformat(str(row["datetime_utc"]).replace("Z", "+00:00"))
    variables = [
        "wave_height", "wave_direction", "wave_period", "wave_peak_period",
        "wind_wave_height", "wind_wave_direction", "wind_wave_period", "wind_wave_peak_period",
        "swell_wave_height", "swell_wave_direction", "swell_wave_period", "swell_wave_peak_period",
        "secondary_swell_wave_height", "secondary_swell_wave_direction", "secondary_swell_wave_period",
    ]
    query = {
        "latitude": row["representative_ocean_lat"], "longitude": row["representative_ocean_lon"],
        "start_date": when.date().isoformat(), "end_date": when.date().isoformat(),
        "hourly": ",".join(variables), "timezone": "GMT", "cell_selection": "sea",
        "models": config["wave_model"]["model"],
    }
    return config["wave_model"]["endpoint"] + "?" + urllib.parse.urlencode(query, safe=",")


def nearest_hour_values(payload: Mapping[str, Any], acquisition: datetime) -> tuple[dict[str, Any], datetime | None, float | None]:
    hourly = payload.get("hourly") or {}
    times = [datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=timezone.utc) for value in hourly.get("time", [])]
    if not times:
        return {}, None, None
    valid = [i for i in range(len(times)) if any((hourly.get(name) or [None] * len(times))[i] is not None for name in ("wave_height", "swell_wave_height"))]
    if not valid:
        return {}, None, None
    index = min(valid, key=lambda i: abs((times[i] - acquisition).total_seconds()))
    return {name: (values[index] if index < len(values) else None) for name, values in hourly.items() if name != "time" and isinstance(values, list)}, times[index], (times[index] - acquisition).total_seconds()


def query_wave_models(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any], budget: ByteRangeBudget) -> tuple[list[dict[str, Any]], list[Any], list[str], list[str]]:
    cache_dir = BASE / "cache" / "wave_model"
    cache_dir.mkdir(parents=True, exist_ok=True)
    output, errors, urls, cache_used = [], [], [], []
    for index, source in enumerate(rows, 1):
        row = dict(source)
        url = wave_query_url(row, config)
        identity = hashlib.sha256(url.encode()).hexdigest()
        cache_path = cache_dir / f"{identity}.json"
        try:
            if cache_path.exists():
                raw = cache_path.read_bytes(); cache_used.append(str(cache_path.relative_to(ROOT)))
            else:
                raw, _ = fetch_bytes(url, config, budget); atomic_bytes(cache_path, raw); urls.append(url)
            payload = json.loads(raw)
            acquisition = datetime.fromisoformat(str(row["datetime_utc"]).replace("Z", "+00:00"))
            values, model_time, offset = nearest_hour_values(payload, acquisition)
            error = ""
        except Exception as exc:
            payload, values, model_time, offset = {}, {}, None, None
            error = repr(exc); errors.append({"acquisition_key": row["acquisition_key"], "error": error, "url": url})
        model_peak = as_float(values.get("swell_wave_peak_period"))
        model_mean = as_float(values.get("swell_wave_period"))
        swell_from = as_float(values.get("swell_wave_direction"))
        swell_to = direction_from_to(swell_from) if swell_from is not None else None
        axis = as_float(row.get("view_azimuth_deg"))
        total_h, swell_h = as_float(values.get("wave_height")), as_float(values.get("swell_wave_height"))
        height_ratio = None if total_h is None or total_h <= 0 or swell_h is None else swell_h / total_h
        energy_ratio = None if height_ratio is None else height_ratio ** 2
        row.update(period_fields(model_peak=model_peak, model_mean=model_mean))
        row.update({
            "wave_model": config["wave_model"]["model"],
            "wave_model_role": config["wave_model"]["role"],
            "wave_model_query_url": url,
            "wave_model_query_utc": utc_now().isoformat(),
            "wave_model_payload_sha256": sha256_bytes(raw) if not error else None,
            "wave_model_cache": str(cache_path.relative_to(ROOT)),
            "wave_model_error": error,
            "wave_model_time_utc": model_time.isoformat() if model_time else None,
            "wave_model_time_offset_s": offset,
            "wave_model_grid_lat": payload.get("latitude"), "wave_model_grid_lon": payload.get("longitude"),
            "model_total_hs_m": total_h, "model_swell_height_m": swell_h,
            "model_swell_height_ratio": height_ratio, "model_swell_energy_proxy_ratio": energy_ratio,
            "model_swell_direction_from_deg": swell_from, "model_swell_propagation_to_deg": swell_to,
            "model_wave_range_axial_difference_deg": None if swell_to is None or axis is None else axial_direction_difference_deg(swell_to, axis),
            "model_wave_range_full_difference_deg": None if swell_to is None or axis is None else full_direction_difference_deg(swell_to, axis),
        })
        output.append(row)
        if index % 20 == 0 or index == len(rows):
            print(f"wave model: {index}/{len(rows)} errors={len(errors)}", flush=True)
    return output, errors, urls, cache_used


def parse_station_metadata(payload: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(payload)
    records = []
    for station in root.findall("station"):
        if station.get("type") not in {"moored buoy", "buoy"}:
            continue
        histories = station.findall("history") or [station]
        for history in histories:
            try:
                lat = float(history.get("lat") or station.get("lat")); lon = float(history.get("lng") or station.get("lon"))
            except (TypeError, ValueError):
                continue
            records.append({
                "station_id": station.get("id"), "name": station.get("name"), "owner": station.get("owner"),
                "program": station.get("pgm"), "type": station.get("type"), "lat": lat, "lon": lon,
                "start": history.get("start"), "stop": history.get("stop"),
            })
    return records


def station_active(record: Mapping[str, Any], when: datetime) -> bool:
    start = datetime.min.replace(tzinfo=timezone.utc) if not record.get("start") else datetime.fromisoformat(str(record["start"])).replace(tzinfo=timezone.utc)
    stop = datetime.max.replace(tzinfo=timezone.utc) if not record.get("stop") else datetime.fromisoformat(str(record["stop"])).replace(tzinfo=timezone.utc)
    return start <= when < stop


def parse_ascii_vector(text: str, variable: str) -> np.ndarray:
    match = re.search(rf"(?m)^{re.escape(variable)}\[\d+\]\s*\n([^\n]+)", text)
    if not match:
        raise ValueError(f"vector {variable} absent")
    return np.asarray([float(value.strip()) for value in match.group(1).split(",")], dtype=float)


def parse_ascii_grid(text: str, variable: str) -> np.ndarray:
    match = re.search(rf"(?m)^{re.escape(variable)}\.{re.escape(variable)}[^\n]*\n(.*?)(?:\n\s*\n|\Z)", text, re.S)
    if not match:
        raise ValueError(f"grid {variable} absent")
    return np.asarray([float(line.rsplit(",", 1)[-1].strip()) for line in match.group(1).splitlines() if line.strip()], dtype=float)


def ndbc_spectrum_subset(station: str, acquisition: datetime, config: Mapping[str, Any], budget: ByteRangeBudget) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    root = config["references"]["ndbc_thredds_root"]
    dataset = f"{root}/swden/{station}/{station}w9999.nc"
    dods = dataset.replace("/catalog/", "/dodsC/") if "/catalog/" in dataset else dataset.replace("/thredds/", "/thredds/dodsC/")
    # Config root is already the THREDDS catalog namespace; normalize once.
    dods = re.sub(r"/thredds/(?:dodsC/)?catalog/data/", "/thredds/dodsC/data/", dods)
    time_url = dods + ".ascii?time"
    payload, _ = fetch_bytes(time_url, config, budget)
    epochs = parse_ascii_vector(payload.decode("utf-8", errors="replace"), "time")
    target = acquisition.timestamp(); index = int(np.argmin(np.abs(epochs - target)))
    variables = ("spectral_wave_density", "mean_wave_dir", "principal_wave_dir", "wave_spectrum_r1", "wave_spectrum_r2")
    clauses = ["frequency"] + [f"{name}[{index}:1:{index}][0:1:97][0:1:0][0:1:0]" for name in variables]
    subset_url = dods + ".ascii?" + ",".join(clauses)
    subset, _ = fetch_bytes(subset_url, config, budget)
    text = subset.decode("utf-8", errors="replace")
    frequency = parse_ascii_vector(text, "frequency")
    arrays = [parse_ascii_grid(text, name) for name in variables]
    f, density, alpha1, alpha2, r1, r2 = clean_spectral_arrays(frequency, *arrays, missing_codes=config["references"]["missing_codes"])
    peak = spectral_peak(f, density); peak_index = int(np.argmax(density))
    total_variance = float(np.trapezoid(density, f))
    long_mask = f <= 0.1
    long_variance = float(np.trapezoid(density[long_mask], f[long_mask])) if np.count_nonzero(long_mask) >= 2 else 0.0
    observation = datetime.fromtimestamp(float(epochs[index]), timezone.utc)
    peak_from = None if np.isnan(alpha1[peak_index]) else float(alpha1[peak_index])
    peak_to = None if peak_from is None else direction_from_to(peak_from)
    local_maxima = [i for i in range(1, len(density) - 1) if density[i] >= density[i - 1] and density[i] > density[i + 1]]
    systems = [i for i in local_maxima if density[i] >= 0.25 * density[peak_index]]
    return {
        "station_id": station,
        "observation_utc": observation.isoformat(),
        "observation_offset_s": (observation - acquisition).total_seconds(),
        "frequency_bin_count": len(f),
        "frequency_min_hz": float(f[0]), "frequency_max_hz": float(f[-1]),
        "measured_hm0_m": spectral_hm0_m(f, density),
        "measured_long_energy_fraction_f_le_0p1": None if total_variance <= 0 else long_variance / total_variance,
        **peak,
        "measured_peak_direction_from_deg": peak_from,
        "measured_peak_propagation_to_deg": peak_to,
        "measured_peak_alpha2_deg": None if np.isnan(alpha2[peak_index]) else float(alpha2[peak_index]),
        "measured_peak_r1": None if np.isnan(r1[peak_index]) else float(r1[peak_index]),
        "measured_peak_r2": None if np.isnan(r2[peak_index]) else float(r2[peak_index]),
        "competing_system_count": len(systems),
        "spectral_density_available": True, "alpha1_available": bool(np.isfinite(alpha1).any()),
        "alpha2_available": bool(np.isfinite(alpha2).any()), "r1_available": bool(np.isfinite(r1).any()), "r2_available": bool(np.isfinite(r2).any()),
        "source_url": subset_url, "payload_sha256": sha256_bytes(subset),
    }, [time_url, subset_url], []


def query_references(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any], budget: ByteRangeBudget) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Any], list[str]]:
    cache = BASE / "cache" / "ndbc_stationmetadata.xml"
    urls, errors = [], []
    if cache.exists():
        station_payload = cache.read_bytes(); cache_used = [str(cache.relative_to(ROOT))]
    else:
        station_payload, _ = fetch_bytes(config["references"]["ndbc_station_metadata"], config, budget)
        atomic_bytes(cache, station_payload); urls.append(config["references"]["ndbc_station_metadata"]); cache_used = []
    stations = parse_station_metadata(station_payload)
    availability, spectra = [], []
    spectrum_cache: dict[tuple[str, int], dict[str, Any] | None] = {}
    for index, source in enumerate(rows, 1):
        row = dict(source); acquisition = datetime.fromisoformat(str(row["datetime_utc"]).replace("Z", "+00:00"))
        lat, lon = float(row["representative_ocean_lat"]), float(row["representative_ocean_lon"])
        active = [(haversine_km(lat, lon, s["lat"], s["lon"]), s) for s in stations if station_active(s, acquisition)]
        active.sort(key=lambda pair: (pair[0], pair[1]["station_id"] or ""))
        nearest_distance, nearest = active[0] if active else (None, None)
        spectrum = None
        maximum_distance = float(config["references"]["maximum_station_distance_km"])
        within = nearest_distance is not None and nearest_distance <= maximum_distance
        spectrum_station = nearest
        spectrum_distance = nearest_distance
        attempted = []
        for candidate_distance, candidate_station in [pair for pair in active if pair[0] <= maximum_distance]:
            key = (str(candidate_station["station_id"]), acquisition.year)
            attempted.append(candidate_station["station_id"])
            try:
                # The w9999 dataset is station-wide; each scene still receives
                # its own exact-time subset while the time vector may be cached.
                spectrum, used_urls, _ = ndbc_spectrum_subset(str(candidate_station["station_id"]), acquisition, config, budget)
                urls.extend(used_urls); spectrum_cache[key] = spectrum
                spectrum_station, spectrum_distance = candidate_station, candidate_distance
                break
            except Exception as exc:
                errors.append({"acquisition_key": row["acquisition_key"], "station": candidate_station["station_id"], "error": repr(exc)})
        if spectrum:
            spectrum["acquisition_key"] = row["acquisition_key"]
            spectrum["station_distance_km"] = spectrum_distance
            spectrum["wave_range_axial_difference_deg"] = None if spectrum["measured_peak_propagation_to_deg"] is None else axial_direction_difference_deg(spectrum["measured_peak_propagation_to_deg"], float(row["view_azimuth_deg"]))
            spectrum["wave_range_full_difference_deg"] = None if spectrum["measured_peak_propagation_to_deg"] is None else full_direction_difference_deg(spectrum["measured_peak_propagation_to_deg"], float(row["view_azimuth_deg"]))
            spectra.append(spectrum)
        time_ok = spectrum is not None and abs(float(spectrum["observation_offset_s"])) <= float(config["references"]["maximum_observation_offset_s"])
        fields = spectrum or {}
        reference = reference_classification(
            station_active=nearest is not None, spectrum_density=bool(fields.get("spectral_density_available")),
            alpha1=bool(fields.get("alpha1_available")), alpha2=bool(fields.get("alpha2_available")),
            r1=bool(fields.get("r1_available")), r2=bool(fields.get("r2_available")),
            within_distance=within, within_time=time_ok, model_available=not bool(row.get("wave_model_error")),
        )
        availability.append({
            "acquisition_key": row["acquisition_key"], "station_active": nearest is not None,
            "station_id": spectrum_station.get("station_id") if spectrum_station else None, "station_distance_km": spectrum_distance,
            "nearest_active_station_id": nearest.get("station_id") if nearest else None, "nearest_active_station_distance_km": nearest_distance,
            "station_name": spectrum_station.get("name") if spectrum_station else None, "station_owner": spectrum_station.get("owner") if spectrum_station else None,
            "station_program": spectrum_station.get("program") if spectrum_station else None,
            "ndbc_directional_spectrum_available": spectrum is not None,
            "cdip_linked_station": bool(spectrum_station and "SCRIPPS" in str(spectrum_station.get("owner", "")).upper()),
            "cdip_source": config["references"]["cdip_thredds_root"] if spectrum_station and "SCRIPPS" in str(spectrum_station.get("owner", "")).upper() else None,
            "stations_checked_within_50_km_json": json.dumps(attempted),
            "observation_offset_s": fields.get("observation_offset_s"), "reference_class": reference,
            "reference_error": next((e["error"] for e in reversed(errors) if e.get("acquisition_key") == row["acquisition_key"]), ""),
        })
        if index % 10 == 0 or index == len(rows):
            print(f"references: {index}/{len(rows)} spectra={len(spectra)} errors={len(errors)}", flush=True)
    return availability, spectra, errors, urls + cache_used


def asset_of_kind(row: Mapping[str, Any], kind: str) -> dict[str, Any] | None:
    assets = json.loads(row.get("assets_json") or "[]")
    candidates = [asset for asset in assets if asset.get("kind") == kind]
    return max(candidates, key=lambda asset: int(asset.get("size_bytes") or 0), default=None)


def parse_kv_header(payload: bytes) -> dict[str, Any]:
    text = payload.decode("ascii", errors="ignore")
    result: dict[str, Any] = {"format": text.splitlines()[0] if text else ""}
    for line in text.splitlines()[1:]:
        if ":=" not in line:
            continue
        key, value = (part.strip() for part in line.split(":=", 1))
        result[key] = int(value) if value.isdigit() else value
    return result


def xml_nodes(root: ET.Element, path: Sequence[str]) -> list[ET.Element]:
    nodes = [root]
    for name in path:
        nodes = [child for node in nodes for child in list(node) if child.tag.rsplit("}", 1)[-1] == name]
    return nodes


def xml_text(root: ET.Element, path: Sequence[str]) -> str | None:
    nodes = xml_nodes(root, path)
    return nodes[0].text.strip() if nodes and nodes[0].text else None


def cphd_metadata_audit(url: str, expected_size: int | None, config: Mapping[str, Any], budget: ByteRangeBudget) -> tuple[dict[str, Any], bytes]:
    head, headers = fetch_bytes(url, config, budget, byte_range=(0, 4095))
    parsed = parse_kv_header(head)
    xml_offset, xml_size = int(parsed["XML_BLOCK_BYTE_OFFSET"]), int(parsed["XML_BLOCK_SIZE"])
    xml, _ = fetch_bytes(url, config, budget, byte_range=(xml_offset, xml_offset + xml_size - 1))
    root = ET.fromstring(xml)
    data_channels = xml_nodes(root, ("Data", "Channel"))
    channels = []
    for channel in data_channels:
        def local(name: str):
            node = next((x for x in list(channel) if x.tag.rsplit("}", 1)[-1] == name), None)
            return node.text.strip() if node is not None and node.text else None
        channels.append({name: local(name) for name in ("Identifier", "NumVectors", "NumSamples", "SignalArrayByteOffset", "PVPArrayByteOffset")})
    pvp_size = int(xml_text(root, ("Data", "NumBytesPVP")) or 0)
    tx_offset_words = int(xml_text(root, ("PVP", "TxTime", "Offset")) or 0)
    pvp_block_offset = int(parsed.get("PVP_BLOCK_BYTE_OFFSET", 0))
    samples = []
    if channels and pvp_size >= 8:
        count = int(channels[0].get("NumVectors") or 0)
        channel_offset = int(channels[0].get("PVPArrayByteOffset") or 0)
        indices = np.linspace(0, max(0, count - 1), min(int(config["byte_range_audit"]["pvp_sample_count"]), count), dtype=int)
        for index in np.unique(indices):
            offset = pvp_block_offset + channel_offset + int(index) * pvp_size + tx_offset_words * 8
            value, _ = fetch_bytes(url, config, budget, byte_range=(offset, offset + 7))
            samples.append({"vector_index": int(index), "tx_time_s": struct.unpack(">d", value)[0]})
    signal_size = int(parsed.get("SIGNAL_BLOCK_SIZE", 0))
    return {
        "http_content_length": int(headers.get("Content-Length", expected_size or 0)),
        "expected_size": expected_size,
        "file_format": parsed.get("format"),
        "collect_start": xml_text(root, ("Global", "Timeline", "CollectionStart")),
        "collector": xml_text(root, ("CollectionID", "CollectorName")),
        "core_name": xml_text(root, ("CollectionID", "CoreName")),
        "collect_type": xml_text(root, ("CollectionID", "CollectType")),
        "radar_mode": xml_text(root, ("CollectionID", "RadarMode", "ModeType")),
        "channel_count": len(channels), "channels": channels,
        "num_bytes_pvp": pvp_size, "tx_time_offset_words": tx_offset_words,
        "sampled_pvp_tx_times": samples,
        "sampled_tx_time_span_s": (max(x["tx_time_s"] for x in samples) - min(x["tx_time_s"] for x in samples)) if samples else None,
        "sampled_tx_time_monotonic": all(b["tx_time_s"] > a["tx_time_s"] for a, b in zip(samples, samples[1:])),
        "signal_block_size_bytes": signal_size,
        "signal_block_read": False,
        "xml_sha256": sha256_bytes(xml),
    }, xml


def _array(value: Any) -> list[float] | None:
    if value is None: return None
    return [float(x) for x in value.get_array()] if hasattr(value, "get_array") else [float(x) for x in value]


def _enu(vector: Sequence[float], lat_deg: float, lon_deg: float) -> list[float]:
    x, y, z = vector; lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    return [
        -math.sin(lon) * x + math.cos(lon) * y,
        -math.sin(lat) * math.cos(lon) * x - math.sin(lat) * math.sin(lon) * y + math.cos(lat) * z,
        math.cos(lat) * math.cos(lon) * x + math.cos(lat) * math.sin(lon) * y + math.sin(lat) * z,
    ]


def sicd_metadata_audit(xml_url: str, expected_size: int | None, config: Mapping[str, Any], budget: ByteRangeBudget) -> tuple[dict[str, Any], bytes]:
    if expected_size is not None and expected_size > int(config["byte_range_audit"]["max_per_request_bytes"]):
        raise RuntimeError("SICD XML exceeds per-request metadata limit")
    end = max(0, int(expected_size or config["byte_range_audit"]["max_per_request_bytes"]) - 1)
    xml, _ = fetch_bytes(xml_url, config, budget, byte_range=(0, end))
    from sarpy.io.complex.sicd_elements.SICD import SICDType
    sicd = SICDType.from_xml_string(xml)
    lat, lon = float(sicd.GeoData.SCP.LLH.Lat), float(sicd.GeoData.SCP.LLH.Lon)
    row_enu, col_enu = _enu(_array(sicd.Grid.Row.UVectECF), lat, lon), _enu(_array(sicd.Grid.Col.UVectECF), lat, lon)
    bearing = lambda v: math.degrees(math.atan2(v[0], v[1])) % 360
    duration = float(sicd.ImageFormation.TEndProc - sicd.ImageFormation.TStartProc)
    return {
        "collect_start": sicd.Timeline.to_dict().get("CollectStart"),
        "collector": sicd.CollectionInfo.CollectorName, "core_name": sicd.CollectionInfo.CoreName,
        "radar_mode": sicd.CollectionInfo.RadarMode.ModeType,
        "num_rows": int(sicd.ImageData.NumRows), "num_cols": int(sicd.ImageData.NumCols), "pixel_type": sicd.ImageData.PixelType,
        "t_start_proc_s": float(sicd.ImageFormation.TStartProc), "t_end_proc_s": float(sicd.ImageFormation.TEndProc),
        "sicd_processed_aperture_s": duration,
        "grid_type": sicd.Grid.Type, "grid_image_plane": sicd.Grid.ImagePlane,
        "grid_row_uvect_ecf": _array(sicd.Grid.Row.UVectECF), "grid_col_uvect_ecf": _array(sicd.Grid.Col.UVectECF),
        "grid_row_ground_bearing_deg": bearing(row_enu), "grid_col_ground_bearing_deg": bearing(col_enu),
        "grid_row_ss_m": float(sicd.Grid.Row.SS), "grid_col_ss_m": float(sicd.Grid.Col.SS),
        "grid_row_imp_resp_bw": float(sicd.Grid.Row.ImpRespBW), "grid_col_imp_resp_bw": float(sicd.Grid.Col.ImpRespBW),
        "grid_col_delta_k1": float(sicd.Grid.Col.DeltaK1), "grid_col_delta_k2": float(sicd.Grid.Col.DeltaK2),
        "look_side": sicd.SCPCOA.SideOfTrack, "incidence_deg": float(sicd.SCPCOA.IncidenceAng),
        "azimuth_deg": float(sicd.SCPCOA.AzimAng), "doppler_cone_deg": float(sicd.SCPCOA.DopplerConeAng),
        "polarization": sicd.ImageFormation.TxRcvPolarizationProc,
        "processing_software": sicd.ImageCreation.to_dict() if sicd.ImageCreation is not None else None,
        "xml_sha256": sha256_bytes(xml), "image_pixels_read": False,
    }, xml


def sicd_xml_from_nitf(url: str, config: Mapping[str, Any], budget: ByteRangeBudget) -> bytes:
    from sarpy.io.general.nitf_elements.nitf_head import NITFHeader
    head, _ = fetch_bytes(url, config, budget, byte_range=(0, int(config["byte_range_audit"]["max_per_request_bytes"]) - 1))
    header = NITFHeader.from_bytes(head, 0)
    offset = int(header.HL)
    for collection in (header.ImageSegments, header.GraphicsSegments, header.TextSegments):
        for subheader_size, item_size in zip(collection.subhead_sizes, collection.item_sizes):
            offset += int(subheader_size) + int(item_size)
    for subheader_size, item_size in zip(header.DataExtensions.subhead_sizes, header.DataExtensions.item_sizes):
        subheader_size, item_size = int(subheader_size), int(item_size)
        payload_offset = offset + subheader_size
        if item_size <= int(config["byte_range_audit"]["max_per_request_bytes"]):
            payload, _ = fetch_bytes(url, config, budget, byte_range=(payload_offset, payload_offset + item_size - 1))
            marker = payload.find(b"<SICD")
            if marker >= 0:
                return payload[marker:]
        offset += subheader_size + item_size
    raise ValueError("SICD XML DES not found within configured NITF byte ranges")


def sicd_metadata_from_bytes(xml: bytes) -> dict[str, Any]:
    cache_config = {"byte_range_audit": {"max_per_request_bytes": max(len(xml), 1)}}
    # Parse directly using the same semantic extraction as the URL path.
    from sarpy.io.complex.sicd_elements.SICD import SICDType
    sicd = SICDType.from_xml_string(xml)
    lat, lon = float(sicd.GeoData.SCP.LLH.Lat), float(sicd.GeoData.SCP.LLH.Lon)
    row_enu, col_enu = _enu(_array(sicd.Grid.Row.UVectECF), lat, lon), _enu(_array(sicd.Grid.Col.UVectECF), lat, lon)
    bearing = lambda v: math.degrees(math.atan2(v[0], v[1])) % 360
    return {
        "collect_start": sicd.Timeline.to_dict().get("CollectStart"), "collector": sicd.CollectionInfo.CollectorName,
        "core_name": sicd.CollectionInfo.CoreName, "radar_mode": sicd.CollectionInfo.RadarMode.ModeType,
        "num_rows": int(sicd.ImageData.NumRows), "num_cols": int(sicd.ImageData.NumCols), "pixel_type": sicd.ImageData.PixelType,
        "t_start_proc_s": float(sicd.ImageFormation.TStartProc), "t_end_proc_s": float(sicd.ImageFormation.TEndProc),
        "sicd_processed_aperture_s": float(sicd.ImageFormation.TEndProc - sicd.ImageFormation.TStartProc),
        "grid_type": sicd.Grid.Type, "grid_image_plane": sicd.Grid.ImagePlane,
        "grid_row_ground_bearing_deg": bearing(row_enu), "grid_col_ground_bearing_deg": bearing(col_enu),
        "grid_row_ss_m": float(sicd.Grid.Row.SS), "grid_col_ss_m": float(sicd.Grid.Col.SS),
        "grid_row_imp_resp_bw": float(sicd.Grid.Row.ImpRespBW), "grid_col_imp_resp_bw": float(sicd.Grid.Col.ImpRespBW),
        "grid_col_delta_k1": float(sicd.Grid.Col.DeltaK1), "grid_col_delta_k2": float(sicd.Grid.Col.DeltaK2),
        "look_side": sicd.SCPCOA.SideOfTrack, "incidence_deg": float(sicd.SCPCOA.IncidenceAng),
        "azimuth_deg": float(sicd.SCPCOA.AzimAng), "doppler_cone_deg": float(sicd.SCPCOA.DopplerConeAng),
        "polarization": sicd.ImageFormation.TxRcvPolarizationProc,
        "processing_software": sicd.ImageCreation.to_dict() if sicd.ImageCreation is not None else None,
        "xml_sha256": sha256_bytes(xml), "image_pixels_read": False,
    }


def audit_finalists(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any], budget: ByteRangeBudget) -> tuple[list[dict[str, Any]], list[Any], list[str]]:
    endpoint = config["catalog"]["s3_endpoint"]
    output, errors, urls = [], [], []
    for source in rows[:int(config["byte_range_audit"]["candidate_count"])]:
        row = dict(source); before = budget.used_bytes
        cphd, sicd_xml, sicd_nitf = asset_of_kind(row, "CPHD"), asset_of_kind(row, "SICD_XML"), asset_of_kind(row, "SICD")
        audit = {"acquisition_key": row["acquisition_key"], "collect_name": row.get("collect_name"), "metadata_budget_before_bytes": before}
        try:
            if cphd is None: raise ValueError("CPHD asset absent")
            cphd_url = public_url(endpoint, cphd["public_key"]); urls.append(cphd_url)
            cphd_result, _ = cphd_metadata_audit(cphd_url, cphd.get("size_bytes"), config, budget)
            audit["cphd_json"] = json.dumps(cphd_result, sort_keys=True)
            audit["cphd_tx_time_span_s"] = cphd_result["sampled_tx_time_span_s"]
            audit["cphd_signal_block_size_bytes"] = cphd_result["signal_block_size_bytes"]
            if sicd_xml is not None and sicd_xml.get("size_bytes"):
                sicd_url = public_url(endpoint, sicd_xml["public_key"]); urls.append(sicd_url)
                sicd_result, _ = sicd_metadata_audit(sicd_url, sicd_xml.get("size_bytes"), config, budget)
            elif sicd_nitf is not None:
                sicd_url = public_url(endpoint, sicd_nitf["public_key"]); urls.append(sicd_url)
                sicd_bytes = sicd_xml_from_nitf(sicd_url, config, budget)
                sicd_result = sicd_metadata_from_bytes(sicd_bytes)
            else:
                raise ValueError("SICD asset absent")
            audit["sicd_json"] = json.dumps(sicd_result, sort_keys=True)
            audit["sicd_processed_aperture_s"] = sicd_result["sicd_processed_aperture_s"]
            starts = observation_offset_s(cphd_result.get("collect_start"), sicd_result.get("collect_start"))
            names_match = str(cphd_result.get("collector", "")).lower() == str(sicd_result.get("collector", "")).lower()
            association = starts is not None and abs(starts) <= 1 and names_match
            audit["metadata_association_verified"] = association
            audit["cphd_sicd_start_difference_s"] = starts
            audit["local_range_axis_deg"] = sicd_result["grid_row_ground_bearing_deg"]
            audit["local_azimuth_axis_deg"] = sicd_result["grid_col_ground_bearing_deg"]
            audit["verified_incidence_deg"] = sicd_result["incidence_deg"]
            audit["stac_vs_local_range_axis_difference_deg"] = axial_direction_difference_deg(float(row["view_azimuth_deg"]), float(audit["local_range_axis_deg"]))
            audit["doppler_slow_time_mapping_status"] = "preliminary_monotonic_TxTime_samples_only" if cphd_result["sampled_tx_time_monotonic"] else "sampled_TxTime_nonmonotonic"
            audit["audit_status"] = "complete"
        except Exception as exc:
            audit["audit_status"] = "incomplete"; audit["metadata_association_verified"] = None
            audit["error"] = repr(exc); errors.append({"acquisition_key": row["acquisition_key"], "error": repr(exc)})
        audit["metadata_bytes_downloaded"] = budget.used_bytes - before
        output.append(audit)
    return output, errors, urls


def update_observability(row: dict[str, Any], config: Mapping[str, Any]) -> None:
    measured = as_float(row.get("measured_peak_period_s"))
    fields = period_fields(model_peak=row.get("model_peak_period_s"), model_mean=row.get("model_mean_period_s"), measured_peak=measured)
    row.update(fields)
    period = fields["period_proxy_for_screening_s"]
    metrics = temporal_metrics(
        catalog_duration_s=as_float(row.get("catalog_duration_s")),
        cphd_tx_time_span_s=as_float(row.get("cphd_tx_time_span_s")),
        sicd_processed_aperture_s=as_float(row.get("sicd_processed_aperture_s")),
        period_s=period,
        nominal_look_duration_s=float(config["temporal"]["nominal_look_duration_s"]),
        minimum_independent_looks=int(config["temporal"]["minimum_independent_looks"]),
        sliding_step_s=float(config["temporal"]["sliding_center_step_s"]),
        minimum_cycles=float(config["temporal"]["minimum_observable_cycles"]),
        preferred_cycles=float(config["temporal"]["preferred_observable_cycles"]),
    )
    row.update(metrics)
    if period:
        wavelength = deepwater_wavelength_m(period, float(config["spatial"]["gravity_m_s2"]))
        row["deepwater_wavelength_limit_m"] = wavelength
        diameter = as_float(row.get("max_ocean_roi_diameter_m_proxy"))
        count = None if diameter is None else diameter / wavelength
        row["wavelengths_in_roi_proxy"] = count
        row["preliminary_spatial_gate"] = None if count is None else count >= float(config["spatial"]["minimum_wavelengths_in_roi"])
    else:
        row["deepwater_wavelength_limit_m"] = None; row["wavelengths_in_roi_proxy"] = None; row["preliminary_spatial_gate"] = None
    row["spatial_resolvability_status"] = "preliminary_delta_eff_not_verified"


def merge_science_tables(marine: Sequence[Mapping[str, Any]], waves: Sequence[Mapping[str, Any]], references: Sequence[Mapping[str, Any]], spectra: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    wave_by = {row["acquisition_key"]: row for row in waves}
    ref_by = {row["acquisition_key"]: row for row in references}
    spectrum_by = {row["acquisition_key"]: row for row in spectra}
    output = []
    for source in marine:
        row = dict(source)
        if row["acquisition_key"] in wave_by: row.update(wave_by[row["acquisition_key"]])
        reference = ref_by.get(row["acquisition_key"], {})
        spectrum = spectrum_by.get(row["acquisition_key"], {})
        row.update(reference); row.update(spectrum)
        if not row.get("reference_class"):
            row["reference_class"] = "model_only" if row.get("wave_model") and not row.get("wave_model_error") else "no_reference"
        measured_direction = as_float(row.get("measured_peak_propagation_to_deg"))
        model_direction = as_float(row.get("model_swell_propagation_to_deg"))
        direction = measured_direction if measured_direction is not None else model_direction
        axis = as_float(row.get("view_azimuth_deg"))
        row["wave_propagation_to_deg"] = direction
        row["wave_direction_source"] = "measured_peak" if measured_direction is not None else "model_swell" if model_direction is not None else "missing"
        row["wave_range_axial_difference_deg"] = None if direction is None or axis is None else axial_direction_difference_deg(direction, axis)
        row["wave_range_full_difference_deg"] = None if direction is None or axis is None else full_direction_difference_deg(direction, axis)
        row["range_axis_status"] = "STAC_view_azimuth_preliminary"
        row["metadata_association_verified"] = None
        update_observability(row, config)
        output.append(row)
    return output


def preliminary_finalists(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    provisional = []
    for source in rows:
        row = dict(source)
        if not (row.get("has_cphd") and row.get("has_sicd") and row.get("ocean_roi_available")):
            continue
        if (as_float(row.get("catalog_duration_s")) or 0) < float(config["temporal"]["minimum_catalog_duration_s"]):
            continue
        if str(row.get("instrument_mode", "")).upper() != "SPOTLIGHT":
            continue
        if "dwell_implausible" in json.loads(row.get("anomaly_flags_json") or "[]"):
            continue
        row["metadata_association_verified"] = True
        provisional.append(row)
    return rank_candidates(provisional, config)


def apply_byte_audits(rows: Sequence[Mapping[str, Any]], audits: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_key = {row["acquisition_key"]: row for row in audits}
    output = []
    for source in rows:
        row = dict(source); audit = by_key.get(row["acquisition_key"])
        if audit:
            for field in ("metadata_association_verified", "cphd_tx_time_span_s", "sicd_processed_aperture_s", "local_range_axis_deg", "verified_incidence_deg", "stac_vs_local_range_axis_difference_deg", "doppler_slow_time_mapping_status"):
                row[field] = audit.get(field)
            if audit.get("local_range_axis_deg") is not None and row.get("wave_propagation_to_deg") is not None:
                row["wave_range_axial_difference_deg"] = axial_direction_difference_deg(float(row["wave_propagation_to_deg"]), float(audit["local_range_axis_deg"]))
                row["wave_range_full_difference_deg"] = full_direction_difference_deg(float(row["wave_propagation_to_deg"]), float(audit["local_range_axis_deg"]))
                row["range_axis_status"] = "SICD_Grid_Row_ground_projection_verified"
            update_observability(row, config)
        output.append(row)
    return output


def exclusion_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for reason in json.loads(row.get("gate_failures_json") or "[]"):
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def plot_outputs(rows: Sequence[Mapping[str, Any]], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    category_colors = {"A": "#0072B2", "B": "#E69F00", "C": "#009E73", "D": "#999999", "E": "#CC79A7"}
    evaluable = [row for row in rows if as_float(row.get("period_proxy_for_screening_s")) is not None]
    figures = []

    fig, ax = plt.subplots(figsize=(7, 5))
    for category in "ABCDE":
        subset = [r for r in evaluable if r["category"] == category]
        ax.scatter([float(r["period_proxy_for_screening_s"]) for r in subset], [float(r.get("cphd_tx_time_span_s") or r.get("sicd_processed_aperture_s") or r.get("catalog_duration_s")) for r in subset], s=18, alpha=.7, label=category, color=category_colors[category])
    ax.set(xlabel="Period used for screening (s)", ylabel="Best available duration (s)", title="Duration versus period (verified metadata when available)"); ax.legend(title="Category"); ax.grid(alpha=.2)
    path = output_dir / "dwell_verified_vs_period.png"; fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig); figures.append(path)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    cycles = [float(r["observable_cycles"]) for r in evaluable if as_float(r.get("observable_cycles")) is not None]
    ax.hist(cycles, bins=min(30, max(5, len(cycles) // 3)), color="#0072B2", alpha=.8)
    ax.axvline(1.25, color="#D55E00", label="hard 1.25"); ax.axvline(2.0, color="#009E73", linestyle="--", label="preferred 2.0")
    ax.set(xlabel="Observable centre-span cycles", ylabel="Acquisitions", title="Temporal observability"); ax.legend(); ax.grid(axis="y", alpha=.2)
    path = output_dir / "observable_cycles.png"; fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig); figures.append(path)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ref_names = sorted({str(r.get("reference_class", "no_reference")) for r in rows})
    for name in ref_names:
        subset = [
            r for r in rows
            if str(r.get("reference_class", "no_reference")) == name
            and as_float(r.get("catalog_duration_s")) is not None
            and "dwell_implausible" not in json.loads(r.get("anomaly_flags_json") or "[]")
        ]
        ax.scatter([float(r["catalog_duration_s"]) for r in subset], [ref_names.index(name)] * len(subset), s=16, alpha=.5, label=name)
    ax.set_yticks(range(len(ref_names)), ref_names); ax.set(xlabel="Plausible catalog duration (s)", ylabel="Reference availability", title="Duration and independent-reference availability"); ax.grid(axis="x", alpha=.2)
    path = output_dir / "duration_vs_reference.png"; fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig); figures.append(path)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    angles = [float(r["wave_range_axial_difference_deg"]) for r in rows if as_float(r.get("wave_range_axial_difference_deg")) is not None]
    ax.hist(angles, bins=np.arange(0, 92.5, 2.5), color="#0072B2", alpha=.8); ax.axvline(5, color="#009E73", label="preferred 5°"); ax.axvline(15, color="#D55E00", label="hard 15°")
    ax.set(xlabel="Wave propagation–range axial difference (deg)", ylabel="Acquisitions", title="Preliminary/verified directional geometry"); ax.legend(); ax.grid(axis="y", alpha=.2)
    path = output_dir / "wave_range_direction.png"; fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig); figures.append(path)

    category_counts = {category: sum(r["category"] == category for r in rows) for category in "ABCDE"}
    category_labels = list(category_counts)
    fig, ax = plt.subplots(figsize=(6, 4.5)); ax.bar(category_labels, [category_counts[x] for x in category_labels], color=[category_colors[x] for x in category_labels]);
    for index, value in enumerate(category_counts.values()): ax.text(index, value, str(value), ha="center", va="bottom")
    ax.set(xlabel="Eligibility category", ylabel="Unique acquisitions", title="Block16A categories"); ax.grid(axis="y", alpha=.2)
    path = output_dir / "category_counts.png"; fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig); figures.append(path)

    reasons = list(exclusion_counts(rows).items())[:12]
    fig, ax = plt.subplots(figsize=(8, 5)); labels, values = zip(*reversed(reasons)) if reasons else (["none"], [0]); ax.barh(labels, values, color="#999999")
    ax.set(xlabel="Unique acquisition rows (reasons may overlap)", title="Leading gate failures"); ax.grid(axis="x", alpha=.2)
    path = output_dir / "exclusion_reasons.png"; fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig); figures.append(path)
    return figures


def sensitivity_summary(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> dict[str, Any]:
    baseline = rank_candidates(rows, config)
    baseline_top = {category: next((r["acquisition_key"] for r in baseline if r["category"] == category), None) for category in "AB"}
    variants = []
    for factor in (0.9, 1.1):
        changed = json.loads(json.dumps(config))
        for group in ("weights_measured", "weights_model"):
            weights = changed["ranking"][group]
            weights["direction"] *= factor
            total = sum(weights.values())
            for key in weights: weights[key] /= total
        ranked = rank_candidates(rows, changed)
        top = {category: next((r["acquisition_key"] for r in ranked if r["category"] == category), None) for category in "AB"}
        variants.append({"direction_weight_factor": factor, "top": top, "unchanged": top == baseline_top})
    return {"baseline_top": baseline_top, "variants": variants, "all_top_unchanged": all(v["unchanged"] for v in variants)}


def frozen_hashes() -> dict[str, str]:
    paths = sorted((ROOT / 'umbra/validazione/Block8_validation').rglob("*"))
    result = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path) for path in paths if path.is_file()}
    classification = ROOT / 'umbra/Vandenberg' / "results" / "analysis_block15" / "BLOCK15K_VANDENBERG_CLASSIFICATION.json"
    result[str(classification.relative_to(ROOT)).replace("\\", "/")] = sha256_file(classification)
    return result


def write_report(summary: Mapping[str, Any], shortlist: Sequence[Mapping[str, Any]], audit_findings: Sequence[str]) -> None:
    counts = summary["counts"]
    primary = next((row for row in shortlist if row["category"] == "A"), None)
    alternatives = [row for row in shortlist if row["category"] in {"B", "C"}][:5]
    def candidate_line(row: Mapping[str, Any]) -> str:
        return (f"`{row.get('collect_name')}` ({row.get('acquisition_key')}): category {row.get('category')}, "
                f"catalog/CPHD/SICD durations {row.get('catalog_duration_s')}/{row.get('cphd_tx_time_span_s')}/{row.get('sicd_processed_aperture_s')} s, "
                f"period {row.get('period_proxy_for_screening_s')} s ({row.get('period_proxy_source')}), cycles {row.get('observable_cycles')}, "
                f"reference {row.get('reference_class')}, CPHD/SICD {row.get('cphd_size_bytes')}/{row.get('sicd_size_bytes')} bytes.")
    report = f"""# Block16A — metadata-only Umbra validation-scene selection

Generated: {summary['generated_utc']}  
Catalog snapshot: `{summary['snapshot']}` (`{summary['snapshot_status']}`)  
Frozen configuration SHA-256: `{summary['config_sha256']}`

## Outcome

{('A primary measured-validation scene passes every Block16A metadata gate: ' + candidate_line(primary)) if primary else 'No Category-A primary scene passes every frozen gate. Thresholds were not relaxed.'}

Conditional alternatives:
{os.linesep.join('- ' + candidate_line(row) for row in alternatives) if alternatives else '- None.'}

No SAR product was downloaded and no scene pixels or CPHD signal samples were read. The byte-range audit was restricted to header/XML and nine stratified TxTime PVP values per audited CPHD.

## Required counts

1. Unique physical acquisitions: **{counts['unique_acquisitions']}**.
2. Duplicate processing rows beyond one preferred processing: **{counts['duplicate_processing_rows']}**.
3. Acquisitions excluded for anomalous dates/durations: **{counts['anomalous_date_or_duration']}**.
4. Preferred records with both CPHD and SICD: **{counts['cphd_and_sicd']}**; byte-range-coherent finalists: **{counts['metadata_association_verified']}**.
5. Preliminary useful marine ROI: **{counts['ocean_roi_available']}**.
6. Complete measured directional reference: **{counts['measured_directional_reference']}**.
7. Minimum/preferred cycle threshold: **{counts['minimum_cycles']} / {counts['preferred_cycles']}**.
8. Joint temporal, preliminary-spatial and directional geometry gate: **{counts['joint_temporal_spatial_geometry']}**.
9. Category-A primary exists: **{'yes' if primary else 'no'}**.
10. Remaining preview/small-product gates: measured SAR `delta_eff`, interior coast clearance at SAR scale, lobe separability (>=2 `delta_eff`), usable intensity ROI, SNR/coherence, and full Doppler–slow-time mapping. These are not inferred from Natural Earth or pixel spacing.
11. Non-hard sensitivity: **{'top candidate stable' if summary['sensitivity']['all_top_unchanged'] else 'top candidate changes'}** under ±10% direction-weight perturbation.
12. Difference from Block8: acquisitions are deduplicated by `collect_id`, anomalous timing is fail-closed, cycles replace a long-period reward, references are queried from the first gate rather than a six-case list, measured/model quantities are separated, and finalist range geometry is independently audited.

## Eligibility categories

| Category | Count | Meaning |
|---|---:|---|
| A | {counts['categories']['A']} | positive validation with complete measured directional spectrum |
| B | {counts['categories']['B']} | promising, model-only |
| C | {counts['categories']['C']} | control/weak/incomplete reference |
| D | {counts['categories']['D']} | excluded by an explicit hard gate |
| E | {counts['categories']['E']} | not evaluable without missing metadata/reference |

## Legacy Block8 audit

{os.linesep.join(f'{index + 1}. {finding}' for index, finding in enumerate(audit_findings))}

## Method boundaries

`catalog_duration_s`, `cphd_tx_time_span_s`, and `sicd_processed_aperture_s` remain distinct. A model mean period is never relabelled as a peak period. Model results are `screening_not_independent_validation`. `view:azimuth` is preliminary; only audited SICD Grid Row ground projection is labelled local range. Natural Earth 1:10m is preliminary and cannot establish SAR-scale coast clearance. Deep-water wavelength is a descriptive limit, not truth, and `delta_eff` remains unverified until a small preview/product is inspected.

## Stop

Block16A stops here. No download is authorized automatically.
"""
    atomic_bytes(BASE / "BLOCK16A_REPORT.md", report.encode("utf-8"))


def load_latest_complete_snapshot() -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    for snapshot in sorted((path for path in SNAPSHOTS.iterdir() if path.is_dir()), reverse=True):
        manifest_path = snapshot / "manifest.json"
        if not manifest_path.exists(): continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "complete": continue
        def read_table(name: str) -> list[dict[str, Any]]:
            with (snapshot / name).open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            for row in rows:
                for field in ("has_cphd", "has_sicd", "has_sicd_xml", "has_gec_or_preview", "is_multistatic", "preferred_processing"):
                    if field in row: row[field] = as_bool(row[field])
                for field in ("cphd_count", "sicd_count", "asset_count", "processing_variant_rank", "processing_variant_count", "cphd_size_bytes", "sicd_size_bytes"):
                    if row.get(field) not in (None, ""): row[field] = int(float(row[field]))
            return rows
        return snapshot, read_table("normalized_acquisitions.csv"), read_table("normalized_processings.csv"), manifest
    raise RuntimeError("no complete Block16A catalog snapshot available")


def run(*, resume: bool = False) -> dict[str, Any]:
    config, config_hash = load_config()
    frozen_before = frozen_hashes()
    if resume:
        snapshot, acquisitions, variants, snapshot_manifest = load_latest_complete_snapshot()
        budget = ByteRangeBudget(int(config["catalog"]["max_metadata_bytes"]), int(snapshot_manifest.get("metadata_bytes_downloaded", 0)))
    else:
        budget = ByteRangeBudget(int(config["catalog"]["max_metadata_bytes"]))
        snapshot, acquisitions, variants, snapshot_manifest = build_snapshot(config, config_hash, budget)
    if snapshot_manifest["status"] != "complete":
        summary = {"generated_utc": utc_now().isoformat(), "status": "incomplete_catalog_fail_closed", "snapshot": str(snapshot.relative_to(ROOT)), "snapshot_status": "incomplete", "config_sha256": config_hash, "errors": snapshot_manifest["error_count"]}
        atomic_json(BASE / "BLOCK16A_SUMMARY.json", summary)
        raise RuntimeError("catalog crawl incomplete; fail-closed before scientific ranking")

    anomaly_rows = []
    for row in acquisitions:
        for flag in json.loads(row.get("anomaly_flags_json") or "[]"):
            anomaly_rows.append({"acquisition_key": row["acquisition_key"], "collect_name": row.get("collect_name"), "flag": flag, "catalog_duration_s": row.get("catalog_duration_s"), "start_datetime_utc": row.get("start_datetime_utc"), "end_datetime_utc": row.get("end_datetime_utc")})
    atomic_csv(BASE / "BLOCK16A_ANOMALIES.csv", anomaly_rows)

    marine = compute_marine_table(acquisitions, config)
    atomic_csv(BASE / "BLOCK16A_MARINE_GEOMETRY.csv", marine)
    first_gate = [row for row in marine if row.get("ocean_roi_available") and row.get("has_cphd") and row.get("has_sicd") and str(row.get("instrument_mode", "")).upper() == "SPOTLIGHT" and float(row.get("catalog_duration_s") or 0) >= float(config["temporal"]["minimum_catalog_duration_s"]) and not any(flag in {"date_in_future", "start_end_inverted", "dwell_nonpositive", "dwell_implausible"} for flag in json.loads(row.get("anomaly_flags_json") or "[]")) and not row.get("collect_id") == "9d8283d8-550d-4435-899f-5483d2c1abcc"]
    waves, wave_errors, wave_urls, wave_cache = query_wave_models(first_gate, config, budget)
    atomic_csv(BASE / "BLOCK16A_WAVE_MODEL_SCREEN.csv", waves)
    references, spectra, reference_errors, reference_urls = query_references(waves, config, budget)
    atomic_csv(BASE / "BLOCK16A_REFERENCE_AVAILABILITY.csv", references)
    atomic_csv(BASE / "BLOCK16A_MEASURED_SPECTRA.csv", spectra)

    combined = merge_science_tables(marine, waves, references, spectra, config)
    provisional = preliminary_finalists(combined, config)
    audits, audit_errors, audit_urls = audit_finalists(provisional, config, budget)
    atomic_csv(BASE / "BLOCK16A_BYTE_RANGE_AUDIT.csv", audits)
    combined = apply_byte_audits(combined, audits, config)
    ranked = rank_candidates(combined, config)
    temporal_fields = ["acquisition_key", "collect_name", "catalog_duration_s", "cphd_tx_time_span_s", "sicd_processed_aperture_s", "duration_source", "selected_nominal_look_duration_s", "usable_center_span_s", "independent_look_count", "sliding_center_count", "period_proxy_for_screening_s", "period_proxy_source", "observable_cycles", "temporal_hard_gate", "temporal_preferred_gate", "temporal_not_verified"]
    atomic_csv(BASE / "BLOCK16A_TEMPORAL_METRICS.csv", ranked, temporal_fields)
    atomic_csv(BASE / "BLOCK16A_ALL_CANDIDATES.csv", ranked)
    shortlist = [row for row in ranked if row["category"] in {"A", "B", "C"}][:20]
    atomic_csv(BASE / "BLOCK16A_SHORTLIST.csv", shortlist)

    figure_paths = plot_outputs(ranked, BASE / "figures")
    sensitivity = sensitivity_summary(combined, config)
    date_duration_flags = {"date_before_plausible_interval", "date_in_future", "start_end_inverted", "dwell_nonpositive", "dwell_implausible"}
    counts = {
        "catalog_objects": snapshot_manifest["object_count"], "sidecars": snapshot_manifest["parsed_sidecar_count"],
        "unique_acquisitions": len(acquisitions), "processing_rows": len(variants), "duplicate_processing_rows": len(variants) - len(acquisitions),
        "anomalous_date_or_duration": sum(bool(date_duration_flags.intersection(json.loads(r.get("anomaly_flags_json") or "[]"))) for r in acquisitions),
        "cphd_and_sicd": sum(bool(r.get("has_cphd") and r.get("has_sicd")) for r in acquisitions),
        "metadata_association_verified": sum(r.get("metadata_association_verified") is True for r in ranked),
        "ocean_roi_available": sum(r.get("ocean_roi_available") is True for r in ranked),
        "measured_directional_reference": sum(r.get("reference_class") == "measured_complete" for r in ranked),
        "minimum_cycles": sum(r.get("temporal_hard_gate") is True for r in ranked),
        "preferred_cycles": sum(r.get("temporal_preferred_gate") is True for r in ranked),
        "joint_temporal_spatial_geometry": sum(r.get("temporal_hard_gate") is True and r.get("preliminary_spatial_gate") is True and as_float(r.get("wave_range_axial_difference_deg")) is not None and float(r["wave_range_axial_difference_deg"]) <= float(config["direction"]["hard_max_axial_difference_deg"]) for r in ranked),
        "categories": {category: sum(r["category"] == category for r in ranked) for category in "ABCDE"},
    }
    audit_findings = [
        "Confirmed: both legacy crawlers target `Block8_validation/umbra_all.csv`; schemas differ (static-STAC asset metadata versus S3 size-joined fields).",
        "Confirmed: legacy finalization keys catalog/waves/references by `collect_name`, despite repeated processing variants.",
        "Confirmed: historical catalog has 12,539 rows, 10,137 unique `collect_id`, hence 2,402 duplicate processing rows.",
        "Confirmed and more severe: historical durations include 962.6/1848.6 s and values up to 769,206,143.2 s; 82 exceed 120 s.",
        "Confirmed: legacy `catalog_dwell_s` is exactly STAC end minus start and is not PVP-verified dwell.",
        "Confirmed: legacy scores include a monotone dwell/period reward and no observable-cycle metric.",
        "Confirmed: six long-dwell spectra were manually verified (plus two short-dwell rows in a separate output).",
        "Confirmed: legacy score assigns up to 15 points for a verified buoy, coupling manual verification and rank.",
        "Confirmed: `analyze_block8_ndbc_short_spectra.py` contains six hardcoded `CASES`.",
        "Confirmed: legacy score combines model mean-period proxies, measured peak periods, height ratios, long-band energy and verification status.",
        "Confirmed: marine fraction alone was used; no interior clean-ROI size was estimated.",
        "Confirmed: ocean fraction contributed a positive score and land-control availability was absent.",
        "Confirmed: STAC `view:azimuth` was treated as range axis without finalist local-grid verification.",
        "Confirmed: baseline suite had no Block8 selector pytest module; Block16A adds an offline dedicated suite.",
    ]
    all_errors = [*wave_errors, *reference_errors, *audit_errors]
    summary = {
        "generated_utc": utc_now().isoformat(), "status": "complete", "snapshot": str(snapshot.relative_to(ROOT)).replace("\\", "/"),
        "snapshot_status": snapshot_manifest["status"], "snapshot_identity_sha256": snapshot_manifest["snapshot_identity_sha256"], "config_sha256": config_hash,
        "counts": counts, "sensitivity": sensitivity, "metadata_bytes_downloaded": budget.used_bytes,
        "errors": all_errors, "primary_acquisition_key": next((r["acquisition_key"] for r in shortlist if r["category"] == "A"), None),
        "conditional_alternatives": [r["acquisition_key"] for r in shortlist if r["category"] in {"B", "C"}][:5],
        "frozen_artifact_count": len(frozen_before), "frozen_artifacts_unchanged": frozen_hashes() == frozen_before,
        "provenance": output_provenance(config_sha256=config_hash, source_hashes={"snapshot_manifest": sha256_file(snapshot / "manifest.json"), "natural_earth_shp": sha256_file(LAND_SHP)}, endpoints=[*wave_urls, *reference_urls, *audit_urls], cache_used=wave_cache, errors=all_errors),
    }
    if not summary["frozen_artifacts_unchanged"]:
        raise RuntimeError("a frozen Block8 or Block15K artifact changed")
    atomic_json(BASE / "BLOCK16A_SUMMARY.json", summary)
    write_report(summary, shortlist, audit_findings)
    return {"summary": summary, "frozen_hashes": frozen_before, "figures": figure_paths}


def delivery_manifest(result: Mapping[str, Any], test_result: Mapping[str, Any]) -> dict[str, Any]:
    config, config_hash = load_config()
    # Hash every Block16A deliverable, including the immutable catalog snapshots.
    # The manifest itself is excluded because its digest would be self-referential.
    output_paths = [
        path for path in BASE.rglob("*")
        if path.is_file() and path.name != "BLOCK16A_DELIVERY_MANIFEST.json"
    ]
    output_paths.extend(
        path for path in (
            ROOT / "code" / "umbra_sar" / "scene_selection.py",
            ROOT / "code" / "run_block16a_scene_selection.py",
            ROOT / "tests" / "test_scene_selection.py",
            ROOT / "WORKLOG.md",
        )
        if path.is_file()
    )
    git_commit = "unknown"
    try:
        import subprocess
        git_commit = subprocess.check_output(["git", "-c", "safe.directory=D:/Dati Tesi/Umbra", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        pass
    manifest = {
        "block": "16A", "status": "complete_metadata_only", "generated_utc": utc_now().isoformat(), "git_commit": git_commit,
        "environment": {"python_executable": sys.executable, "python_version": sys.version, "temp": os.environ.get("TEMP"), "tmp": os.environ.get("TMP")},
        "dependencies": {name: __import__(name).__version__ for name in ("numpy", "matplotlib", "shapely", "sarpy")},
        "config_sha256": config_hash, "config": config, "summary": result["summary"], "tests": dict(test_result),
        "frozen_artifact_hashes": result["frozen_hashes"],
        "output_hashes": {str(path.relative_to(ROOT)).replace("\\", "/"): {"bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in sorted(output_paths)},
        "full_sar_products_downloaded": 0, "signal_arrays_read": 0,
    }
    atomic_json(BASE / "BLOCK16A_DELIVERY_MANIFEST.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "resume"), nargs="?", default="run")
    args = parser.parse_args()
    result = run(resume=args.command == "resume")
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

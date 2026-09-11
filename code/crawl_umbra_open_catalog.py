"""Crawl the complete public Umbra static STAC catalog into umbra_all.csv.

Only JSON metadata are downloaded.  No SAR product asset is requested.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "Block8_validation"
RAW = BASE / "catalog_raw"
STAC_ROOT = "https://s3.us-west-2.amazonaws.com/umbra-open-data-catalog/stac/catalog.json"


def fetch(url: str) -> tuple[str, dict, int]:
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Umbra-Block8-metadata-screen/1.0"})
            with urllib.request.urlopen(request, timeout=40) as response:
                payload = response.read()
            return url, json.loads(payload), len(payload)
        except Exception:
            if attempt == 4:
                raise
            time.sleep(0.5 * 2**attempt)
    raise AssertionError


def links(document: dict, base_url: str, relation: str) -> list[str]:
    return [urljoin(base_url, item["href"]) for item in document.get("links", []) if item.get("rel") == relation]


def centroid(geometry: dict | None) -> tuple[float | None, float | None]:
    if not geometry:
        return None, None
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon" and coordinates:
        ring = coordinates[0][:-1] if len(coordinates[0]) > 1 else coordinates[0]
        return sum(float(p[0]) for p in ring) / len(ring), sum(float(p[1]) for p in ring) / len(ring)
    return None, None


def polygon_area_km2(geometry: dict | None) -> float | None:
    if not geometry or geometry.get("type") != "Polygon" or not geometry.get("coordinates"):
        return None
    ring = geometry["coordinates"][0]
    lat0 = math.radians(sum(float(p[1]) for p in ring) / len(ring))
    xy = [(6371.0088 * math.radians(float(p[0])) * math.cos(lat0), 6371.0088 * math.radians(float(p[1]))) for p in ring]
    return abs(sum(xy[i][0] * xy[(i + 1) % len(xy)][1] - xy[(i + 1) % len(xy)][0] * xy[i][1] for i in range(len(xy))) / 2)


def parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def item_row(url: str, item: dict) -> dict[str, object]:
    props = item.get("properties", {})
    start = parse_time(props.get("start_datetime")); end = parse_time(props.get("end_datetime"))
    lon, lat = centroid(item.get("geometry"))
    assets = item.get("assets", {})
    by_title: dict[str, list[str]] = {}
    for name, value in assets.items():
        by_title.setdefault(str(value.get("title", "")), []).append(name)
    cphd = sorted(by_title.get("CPHD", [])); sicd = sorted(by_title.get("SICD", []))
    return {
        "stac_item_id": item.get("id"), "collect_id": props.get("umbra:collect_id"), "task_id": props.get("umbra:task_id"),
        "collect_name": (cphd[0].rsplit("_MM.cphd", 1)[0].rsplit(".cphd", 1)[0] if cphd else (sicd[0].split("_SICD", 1)[0] if sicd else item.get("id"))),
        "datetime_utc": props.get("datetime"), "start_datetime_utc": props.get("start_datetime"), "end_datetime_utc": props.get("end_datetime"),
        "catalog_dwell_s": ((end-start).total_seconds() if start and end else None), "centroid_lon_deg": lon, "centroid_lat_deg": lat,
        "bbox_west": item.get("bbox", [None]*4)[0], "bbox_south": item.get("bbox", [None]*4)[1], "bbox_east": item.get("bbox", [None]*4)[2], "bbox_north": item.get("bbox", [None]*4)[3],
        "footprint_area_km2_approx": polygon_area_km2(item.get("geometry")), "platform": props.get("platform"), "incidence_deg": props.get("view:incidence_angle"),
        "range_view_azimuth_deg": props.get("view:azimuth"), "grazing_deg": props.get("umbra:grazing_angle_degrees"), "look_side": props.get("sar:observation_direction"),
        "orbit_state": props.get("sat:orbit_state"), "polarizations": ",".join(props.get("sar:polarizations", [])), "instrument_mode": props.get("sar:instrument_mode"),
        "resolution_range_m": props.get("sar:resolution_range"), "resolution_azimuth_m": props.get("sar:resolution_azimuth"),
        "best_resolution_range_m": props.get("umbra:best_resolution_range_meters"), "best_resolution_azimuth_m": props.get("umbra:best_resolution_azimuth_meters"),
        "has_cphd": bool(cphd), "has_sicd": bool(sicd), "cphd_asset_name": "|".join(cphd), "sicd_asset_name": "|".join(sicd),
        "asset_count": len(assets), "stac_item_url": url, "geometry_json": json.dumps(item.get("geometry"), separators=(",", ":")),
    }


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    root_url, root_doc, root_bytes = fetch(STAC_ROOT)
    frontier = links(root_doc, root_url, "child")
    catalogs = [(root_url, root_doc, root_bytes)]
    item_urls: set[str] = set()
    seen = {root_url}
    with ThreadPoolExecutor(max_workers=16) as pool:
        while frontier:
            current = [url for url in frontier if url not in seen]
            frontier = []
            futures = [pool.submit(fetch, url) for url in current]
            for future in as_completed(futures):
                url, doc, size = future.result(); seen.add(url); catalogs.append((url, doc, size))
                frontier.extend(links(doc, url, "child")); item_urls.update(links(doc, url, "item"))
            print(f"catalog documents={len(catalogs)} item links={len(item_urls)}", flush=True)

        items = []
        futures = [pool.submit(fetch, url) for url in sorted(item_urls)]
        for index, future in enumerate(as_completed(futures), 1):
            url, doc, size = future.result(); items.append((url, doc, size))
            if index % 250 == 0 or index == len(futures):
                print(f"items {index}/{len(futures)}", flush=True)

    rows = [item_row(url, item) for url, item, _ in items]
    rows.sort(key=lambda row: (str(row["datetime_utc"]), str(row["stac_item_id"])))
    csv_path = BASE / "umbra_all.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    jsonl_path = RAW / "umbra_stac_items.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as stream:
        for url, item, size in sorted(items):
            stream.write(json.dumps({"url": url, "content_length": size, "item": item}, separators=(",", ":")) + "\n")
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "stac_root": STAC_ROOT,
        "catalog_document_count": len(catalogs), "item_count": len(items), "row_count": len(rows),
        "items_with_cphd": sum(bool(row["has_cphd"]) for row in rows), "items_with_sicd": sum(bool(row["has_sicd"]) for row in rows),
        "metadata_bytes_downloaded": sum(size for _, _, size in catalogs) + sum(size for _, _, size in items),
        "umbra_all_csv": str(csv_path.resolve()), "umbra_all_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "note": "Complete public static STAC catalog visible from the root at crawl time; JSON metadata only, no SAR assets downloaded.",
    }
    (RAW / "CRAWL_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

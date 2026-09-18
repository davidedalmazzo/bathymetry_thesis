"""Geometry-only first gate for Block 8 validation-scene screening.

The script reads the complete S3-derived ``umbra_all.csv`` and evaluates only
CPHD collects in the long-dwell (>=15 s) or short-control (5--7 s) bands.  A
Natural Earth 1:10m land polygon index is used to estimate the geodesic land
fraction of each SAR footprint.  No SAR product payload is opened or fetched.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pyogrio
from pyproj import Geod
from shapely import STRtree, from_geojson, make_valid
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'umbra/validazione/Block8_validation'
RESULTS = BASE / "results"
LAND_SHP = BASE / "catalog_raw" / "ne_10m_land" / "ne_10m_land.shp"
CATALOG = BASE / "umbra_all.csv"
VANDENBERG_COLLECT = "2025-02-16-18-55-44_UMBRA-10"
GEOD = Geod(ellps="WGS84")


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes"}


def polygonal_geodesic_area_m2(geometry):
    if geometry.is_empty:
        return 0.0
    kind = geometry.geom_type
    if kind == "Polygon":
        return abs(GEOD.geometry_area_perimeter(geometry)[0])
    if kind in {"MultiPolygon", "GeometryCollection"}:
        return sum(polygonal_geodesic_area_m2(part) for part in geometry.geoms)
    return 0.0


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    with CATALOG.open(newline="", encoding="utf-8") as handle:
        source = list(csv.DictReader(handle))

    selected = []
    for row in source:
        dwell = as_float(row.get("catalog_dwell_s"))
        if not truthy(row.get("has_cphd")) or dwell is None:
            continue
        band = "long_dwell" if dwell >= 15.0 else "short_5_7s" if 5.0 <= dwell <= 7.0 else None
        if band is None:
            continue
        row = dict(row)
        row["screen_band"] = band
        selected.append(row)

    land_frame = pyogrio.read_dataframe(LAND_SHP, columns=[])
    land_geometries = [make_valid(g) for g in land_frame.geometry if g is not None and not g.is_empty]
    tree = STRtree(land_geometries)

    output = []
    for index, row in enumerate(selected, 1):
        try:
            footprint = make_valid(from_geojson(row["geometry_json"]))
            footprint_area = polygonal_geodesic_area_m2(footprint)
            hits = tree.query(footprint, predicate="intersects")
            clipped = [land_geometries[int(i)].intersection(footprint) for i in hits]
            land_piece = unary_union([g for g in clipped if not g.is_empty]) if clipped else None
            land_area = polygonal_geodesic_area_m2(land_piece) if land_piece is not None else 0.0
            land_fraction = min(1.0, max(0.0, land_area / footprint_area)) if footprint_area else None
            geometry_error = ""
        except Exception as exc:  # retained for transparent audit, not silently dropped
            footprint_area = None
            land_fraction = None
            geometry_error = repr(exc)

        ocean_fraction = None if land_fraction is None else 1.0 - land_fraction
        if ocean_fraction is None:
            marine_class = "unknown"
        elif ocean_fraction >= 0.98:
            marine_class = "open_or_fully_marine"
        elif ocean_fraction >= 0.80:
            marine_class = "predominantly_marine"
        else:
            marine_class = "land_or_mixed"

        azimuth = as_float(row.get("range_view_azimuth_deg"))
        compact = {
            "screen_band": row["screen_band"],
            "collect_name": row.get("collect_name"),
            "collect_id": row.get("collect_id"),
            "datetime_utc": row.get("datetime_utc"),
            "centroid_lon_deg": row.get("centroid_lon_deg"),
            "centroid_lat_deg": row.get("centroid_lat_deg"),
            "catalog_dwell_s": row.get("catalog_dwell_s"),
            "incidence_deg": row.get("incidence_deg"),
            "range_view_azimuth_deg": row.get("range_view_azimuth_deg"),
            "range_axis_deg_mod180": None if azimuth is None else azimuth % 180.0,
            "footprint_area_km2_geodesic": None if footprint_area is None else footprint_area / 1e6,
            "land_fraction_ne10m": land_fraction,
            "ocean_fraction_ne10m": ocean_fraction,
            "marine_class": marine_class,
            "geometry_error": geometry_error,
            "excluded_development_vandenberg": row.get("collect_name") == VANDENBERG_COLLECT,
            "cphd_size_bytes": row.get("cphd_size_bytes"),
            "sicd_size_bytes": row.get("sicd_size_bytes"),
            "cphd_asset_names": row.get("cphd_asset_names"),
            "sicd_asset_names": row.get("sicd_asset_names"),
            "stac_public_url": row.get("stac_public_url"),
            "geometry_json": row.get("geometry_json"),
        }
        output.append(compact)
        if index % 250 == 0 or index == len(selected):
            print(f"footprints {index}/{len(selected)}", flush=True)

    output.sort(key=lambda r: (r["screen_band"], str(r["datetime_utc"]), str(r["collect_name"])))
    destination = RESULTS / "marine_geometry_screen.csv"
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)

    counts = {}
    for band in ("long_dwell", "short_5_7s"):
        band_rows = [r for r in output if r["screen_band"] == band]
        counts[band] = {
            "all": len(band_rows),
            "ocean_fraction_ge_0_80": sum((as_float(r["ocean_fraction_ne10m"]) or 0) >= 0.80 for r in band_rows),
            "ocean_fraction_ge_0_98": sum((as_float(r["ocean_fraction_ne10m"]) or 0) >= 0.98 for r in band_rows),
        }
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "input_catalog": str(CATALOG.resolve()),
        "input_rows": len(source),
        "natural_earth_dataset": "Natural Earth 1:10m Physical Land polygons",
        "natural_earth_source": "https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/",
        "area_method": "WGS84 ellipsoidal geodesic area after polygon intersection",
        "marine_threshold_predominant": 0.80,
        "marine_threshold_open_or_full": 0.98,
        "vandenberg_policy": "Retained only as an auditable excluded row; never eligible or ranked.",
        "counts": counts,
        "output_csv": str(destination.resolve()),
        "output_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }
    (RESULTS / "MARINE_GEOMETRY_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

"""Match marine Block-8 candidate footprints to historically active NDBC buoys."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'umbra/validazione/Block8_validation'
RESULTS = BASE / "results"
INPUT = RESULTS / "wave_model_screen.csv"
STATIONS = BASE / "buoy_data" / "ndbc_stationmetadata.xml"


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def history_date(value, end=False):
    if not value:
        return datetime.max.replace(tzinfo=timezone.utc) if end else datetime.min.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc)


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def main():
    with INPUT.open(newline="", encoding="utf-8") as handle:
        scenes = list(csv.DictReader(handle))
    root = ET.parse(STATIONS).getroot()
    stations = []
    for node in root.findall("station"):
        if node.get("type") not in {"moored buoy", "buoy"}:
            continue
        for history in node.findall("history"):
            try:
                lat, lon = float(history.get("lat")), float(history.get("lng"))
            except (TypeError, ValueError):
                continue
            stations.append({
                "station_id": node.get("id"), "station_name": node.get("name"),
                "station_owner": node.get("owner"), "station_program": node.get("pgm"),
                "station_type": node.get("type"), "station_lat": lat, "station_lon": lon,
                "history_start": history.get("start"), "history_stop": history.get("stop"),
                "active_start": history_date(history.get("start")),
                "active_stop": history_date(history.get("stop"), end=True),
            })
    output = []
    for scene in scenes:
        when = dt(scene["datetime_utc"])
        lat, lon = float(scene["centroid_lat_deg"]), float(scene["centroid_lon_deg"])
        active = []
        for station in stations:
            if station["active_start"] <= when < station["active_stop"]:
                active.append((haversine_km(lat, lon, station["station_lat"], station["station_lon"]), station))
        active.sort(key=lambda pair: pair[0])
        if active:
            distance, nearest = active[0]
            record = {
                "screen_band": scene["screen_band"], "collect_name": scene["collect_name"],
                "datetime_utc": scene["datetime_utc"], "scene_lat": lat, "scene_lon": lon,
                "nearest_ndbc_station": nearest["station_id"], "nearest_ndbc_distance_km": distance,
                "nearest_station_name": nearest["station_name"], "nearest_station_owner": nearest["station_owner"],
                "nearest_station_program": nearest["station_program"], "nearest_station_type": nearest["station_type"],
                "station_lat": nearest["station_lat"], "station_lon": nearest["station_lon"],
                "deployment_start": nearest["history_start"], "deployment_stop": nearest["history_stop"],
                "within_20_km": distance <= 20, "within_30_km": distance <= 30, "within_50_km": distance <= 50,
                "ndbc_station_page": f"https://www.ndbc.noaa.gov/station_page.php?station={nearest['station_id']}",
                "ndbc_swden_thredds_catalog": f"https://dods.ndbc.noaa.gov/thredds/catalog/data/swden/{nearest['station_id']}/catalog.xml",
                "nearest_five_active_buoys_json": json.dumps([
                    {"station": s["station_id"], "distance_km": d, "owner": s["station_owner"], "lat": s["station_lat"], "lon": s["station_lon"]}
                    for d, s in active[:5]
                ], separators=(",", ":")),
            }
        else:
            record = {"screen_band": scene["screen_band"], "collect_name": scene["collect_name"], "datetime_utc": scene["datetime_utc"], "scene_lat": lat, "scene_lon": lon,
                      "nearest_ndbc_station": "", "nearest_ndbc_distance_km": "", "nearest_station_name": "", "nearest_station_owner": "", "nearest_station_program": "", "nearest_station_type": "", "station_lat": "", "station_lon": "", "deployment_start": "", "deployment_stop": "",
                      "within_20_km": False, "within_30_km": False, "within_50_km": False, "ndbc_station_page": "", "ndbc_swden_thredds_catalog": "", "nearest_five_active_buoys_json": "[]"}
        output.append(record)
    destination = RESULTS / "nearest_ndbc_stations.csv"
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0])); writer.writeheader(); writer.writerows(output)
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "candidate_count": len(scenes),
        "historical_buoy_deployment_records": len(stations),
        "within_20_km": sum(r["within_20_km"] for r in output), "within_30_km": sum(r["within_30_km"] for r in output),
        "within_50_km": sum(r["within_50_km"] for r in output), "station_metadata_source": "https://www.ndbc.noaa.gov/metadata/stationmetadata.xml",
        "output_csv": str(destination.resolve()), "output_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }
    (RESULTS / "NDBC_MATCH_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

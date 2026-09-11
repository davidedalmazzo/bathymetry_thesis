"""Attach a consistent historical wave-model screen to marine Block-8 scenes.

This is a screening layer, not independent validation.  MFWAM fields are
queried at each acquisition time.  Open-Meteo reports wave directions as
coming *from*; this script converts swell direction to propagation *toward*
before comparing it with the undirected SAR range axis modulo 180 degrees.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "Block8_validation"
RESULTS = BASE / "results"
CACHE = BASE / "buoy_data" / "open_meteo_mfwam_cache"
INPUT = RESULTS / "marine_geometry_screen.csv"
ENDPOINT = "https://marine-api.open-meteo.com/v1/marine"
MODEL = "meteofrance_wave"
VARIABLES = [
    "wave_height", "wave_direction", "wave_period", "wave_peak_period",
    "wind_wave_height", "wind_wave_direction", "wind_wave_period", "wind_wave_peak_period",
    "swell_wave_height", "swell_wave_direction", "swell_wave_period", "swell_wave_peak_period",
    "secondary_swell_wave_height", "secondary_swell_wave_direction", "secondary_swell_wave_period",
]


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def axial_delta_deg(direction, axis):
    return abs(((direction - axis + 90.0) % 180.0) - 90.0)


def safe_ratio(a, b):
    return None if a is None or b is None or b <= 0 else a / b


def fetch(row):
    when = parse_time(row["datetime_utc"])
    identity = f"{row['collect_name']}__{MODEL}"
    cache_path = CACHE / f"{identity}.json"
    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return row, payload, str(cache_path), None
    query = {
        "latitude": row["centroid_lat_deg"],
        "longitude": row["centroid_lon_deg"],
        "start_date": when.date().isoformat(),
        "end_date": when.date().isoformat(),
        "hourly": ",".join(VARIABLES),
        "timezone": "GMT",
        "cell_selection": "sea",
        "models": MODEL,
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(query, safe=",")
    error = None
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Umbra-Block8-wave-screen/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read())
            payload["_query_url"] = url
            payload["_requested_model"] = MODEL
            cache_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            return row, payload, str(cache_path), None
        except Exception as exc:
            error = repr(exc)
            time.sleep(1.5 * (attempt + 1))
    return row, None, str(cache_path), error


def extract_nearest(payload, acquisition):
    hourly = payload.get("hourly") or {}
    times = [parse_time(t + "Z") for t in hourly.get("time", [])]
    if not times:
        return {}, None, None
    # Choose the closest time that has at least total or swell wave height.
    usable = [i for i in range(len(times)) if any((hourly.get(v) or [None] * len(times))[i] is not None for v in ("wave_height", "swell_wave_height"))]
    if not usable:
        return {}, None, None
    index = min(usable, key=lambda i: abs((times[i] - acquisition).total_seconds()))
    values = {name: (hourly.get(name) or [None] * len(times))[index] for name in VARIABLES}
    return values, times[index], abs((times[index] - acquisition).total_seconds())


def preliminary_score(row):
    dwell = as_float(row.get("catalog_dwell_s")) or 0.0
    incidence = as_float(row.get("incidence_deg"))
    ocean = as_float(row.get("ocean_fraction_ne10m")) or 0.0
    delta = as_float(row.get("delta_swell_propagation_to_range_axis_deg"))
    peak = as_float(row.get("swell_wave_peak_period_s"))
    swell_h = as_float(row.get("swell_significant_height_m"))
    ratio = as_float(row.get("swell_to_total_height_ratio"))
    dwell_score = min(1.0, max(0.0, (dwell - 15.0) / 10.0 + 0.5)) if row["screen_band"] == "long_dwell" else max(0.0, 1.0 - abs(dwell - 6.0))
    if incidence is None:
        incidence_score = 0.0
    elif 15.0 <= incidence <= 35.0:
        incidence_score = 1.0
    elif 10.0 <= incidence < 15.0 or 35.0 < incidence <= 45.0:
        incidence_score = 0.6
    else:
        incidence_score = 0.15
    direction_score = 0.0 if delta is None else 1.0 if delta <= 5.0 else 0.75 if delta <= 10.0 else max(0.0, 0.75 * (30.0 - delta) / 20.0)
    period_score = 0.0 if peak is None else min(1.0, max(0.0, (peak - 7.0) / 3.0))
    swell_score = 0.0 if swell_h is None else min(1.0, swell_h / 2.0)
    dominance_score = 0.0 if ratio is None else min(1.0, ratio / 0.8)
    ocean_score = min(1.0, max(0.0, (ocean - 0.80) / 0.18))
    # Direction is intentionally the largest term: this is a phase-period
    # validation search, not a generic image-quality ranking.
    return 100.0 * (0.30 * direction_score + 0.17 * dwell_score + 0.15 * period_score + 0.13 * swell_score + 0.10 * dominance_score + 0.07 * incidence_score + 0.08 * ocean_score)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    with INPUT.open(newline="", encoding="utf-8") as handle:
        source = list(csv.DictReader(handle))
    candidates = [r for r in source if as_float(r.get("ocean_fraction_ne10m")) is not None and as_float(r["ocean_fraction_ne10m"]) >= 0.80 and str(r.get("excluded_development_vandenberg", "")).lower() != "true"]
    gathered = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch, row) for row in candidates]
        for index, future in enumerate(as_completed(futures), 1):
            gathered.append(future.result())
            if index % 20 == 0 or index == len(futures):
                print(f"wave queries {index}/{len(futures)}", flush=True)

    output, errors = [], []
    for row, payload, cache_path, error in gathered:
        result = dict(row)
        result["wave_model"] = MODEL
        result["wave_model_role"] = "screening_not_independent_validation"
        result["wave_model_cache"] = cache_path
        result["wave_model_error"] = error or ""
        if error or payload is None:
            errors.append({"collect_name": row["collect_name"], "error": error})
            values, model_time, offset = {}, None, None
        else:
            values, model_time, offset = extract_nearest(payload, parse_time(row["datetime_utc"]))
        mapping = {
            "total_significant_wave_height_m": "wave_height",
            "total_wave_mean_period_s": "wave_period",
            "total_wave_peak_period_s": "wave_peak_period",
            "wind_wave_significant_height_m": "wind_wave_height",
            "wind_wave_mean_period_s": "wind_wave_period",
            "wind_wave_peak_period_s": "wind_wave_peak_period",
            "swell_significant_height_m": "swell_wave_height",
            "swell_direction_from_deg": "swell_wave_direction",
            "swell_wave_mean_period_s": "swell_wave_period",
            "swell_wave_peak_period_s": "swell_wave_peak_period",
            "secondary_swell_significant_height_m": "secondary_swell_wave_height",
            "secondary_swell_direction_from_deg": "secondary_swell_wave_direction",
            "secondary_swell_wave_mean_period_s": "secondary_swell_wave_period",
        }
        for destination, source_name in mapping.items():
            result[destination] = values.get(source_name)
        swell_from = as_float(result.get("swell_direction_from_deg"))
        propagation = None if swell_from is None else (swell_from + 180.0) % 360.0
        range_axis = as_float(result.get("range_axis_deg_mod180"))
        result["direction_source_convention"] = "from"
        result["swell_propagation_to_deg"] = propagation
        result["range_axis_convention"] = "undirected_modulo_180"
        result["delta_swell_propagation_to_range_axis_deg"] = None if propagation is None or range_axis is None else axial_delta_deg(propagation, range_axis)
        total_h = as_float(result.get("total_significant_wave_height_m"))
        swell_h = as_float(result.get("swell_significant_height_m"))
        result["swell_to_total_height_ratio"] = safe_ratio(swell_h, total_h)
        ratio = as_float(result["swell_to_total_height_ratio"])
        result["swell_to_total_energy_proxy_ratio"] = None if ratio is None else ratio * ratio
        result["wave_model_time_utc"] = None if model_time is None else model_time.isoformat().replace("+00:00", "Z")
        result["wave_model_time_offset_s"] = offset
        result["wave_model_grid_lat"] = None if payload is None else payload.get("latitude")
        result["wave_model_grid_lon"] = None if payload is None else payload.get("longitude")
        result["wave_model_query_url"] = None if payload is None else payload.get("_query_url")
        result["preliminary_physics_score_0_100"] = preliminary_score(result)
        output.append(result)

    output.sort(key=lambda r: (r["screen_band"], -float(r["preliminary_physics_score_0_100"]), str(r["collect_name"])))
    destination = RESULTS / "wave_model_screen.csv"
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader(); writer.writerows(output)
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "long_dwell_count": sum(r["screen_band"] == "long_dwell" for r in output),
        "short_5_7s_count": sum(r["screen_band"] == "short_5_7s" for r in output),
        "errors": errors,
        "endpoint": ENDPOINT,
        "model": MODEL,
        "direction_conversion": "propagation_to = (reported_from + 180 deg) mod 360; delta uses undirected range axis modulo 180",
        "period_semantics": "swell_wave_period is retained as mean; only swell_wave_peak_period is named swell peak period",
        "source_documentation": "https://open-meteo.com/en/docs/marine-weather-api",
        "output_csv": str(destination.resolve()),
        "output_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }
    (RESULTS / "WAVE_MODEL_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

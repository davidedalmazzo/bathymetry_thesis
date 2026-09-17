"""Strict mission-neutral input, explicit separate legacy catalogue adapters."""
import csv
import json
from pathlib import Path
from .data import utc
from .geometry import polygon


def validate(record):
    record = dict(record)
    allowed={"acquisition_id","timestamp_utc","start_utc","end_utc","timestamp_semantics","footprint","roi","source"}
    if set(record)-allowed:
        raise ValueError("Unsupported acquisition properties; do not pass assets or credentials")
    if not record.get("acquisition_id"):
        raise ValueError("acquisition_id required")
    record["timestamp_utc"] = utc(record["timestamp_utc"]).isoformat()
    for key in ("start_utc", "end_utc"):
        if record.get(key):
            record[key] = utc(record[key]).isoformat()
    if record.get("start_utc") and record.get("end_utc"):
        if utc(record["start_utc"]) > utc(record["end_utc"]):
            raise ValueError("Acquisition interval reversed")
    for key in ("footprint", "roi"):
        polygon(record.get(key))
    if not record.get("timestamp_semantics"):
        record["timestamp_semantics"]="user_supplied_acquisition_timestamp_not_verified_aperture_center"
    return record


def read_acquisitions(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
        for row in rows:
            for key in ("footprint", "roi"):
                value=row.pop(key+"_geojson",None)
                row[key] = json.loads(value) if value else None
        return [validate(row) for row in rows]
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if obj.get("type") == "FeatureCollection":
        records = [dict(f["properties"], footprint=f.get("geometry")) for f in obj["features"]]
    elif obj.get("type") == "Feature":
        records = [dict(obj["properties"], footprint=obj.get("geometry"))]
    else:
        records = obj.get("acquisitions", [obj])
    result = [validate(r) for r in records]
    if len({r["acquisition_id"] for r in result}) != len(result):
        raise ValueError("Duplicate acquisition IDs")
    return result


def adapt_cleos(path, product_ids):
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    records = []
    for feature in obj["features"]:
        p = feature["properties"]
        if str(p["product_identifier"]) in set(map(str,product_ids)):
            records.append(validate({"acquisition_id": "COSMO_"+str(p["product_identifier"]),
                                    "timestamp_utc": p["start_datetime"],
                                    "start_utc": p["start_datetime"], "end_utc": p["end_datetime"],
                                    "timestamp_semantics": "catalogue_start_not_verified_aperture_center",
                                    "footprint": feature["geometry"], "source": str(path)}))
    if len(records) != len(product_ids):
        raise ValueError("Catalogue products missing or duplicated")
    return records


def adapt_eoweb(path, record_numbers):
    rows = list(csv.DictReader(Path(path).open(encoding="utf-8-sig",newline=""), delimiter=";"))
    result = []
    for row in rows:
        if not row.get("recordNum") or not row["recordNum"].strip().isdigit():
            continue  # EOWEB export contains a non-record footer, never an acquisition.
        if int(row["recordNum"]) not in record_numbers:
            continue
        ring = [[float(x) for x in pair.split(",")] for pair in row["footprint"].split()]
        result.append(validate({"acquisition_id": row["platformSerialIdentifier"]+"_record_"+row["recordNum"],
                                "timestamp_utc": row["startdate"], "start_utc": row["startdate"], "end_utc": row["enddate"],
                                "timestamp_semantics": "timestamp_of_catalogue_record_not_verified_aperture_center",
                                "footprint": {"type": "Polygon", "coordinates": [ring]},
                                "source": str(path)}))
    if len(result) != len(record_numbers):
        raise ValueError("EOWEB record missing or duplicated")
    return result

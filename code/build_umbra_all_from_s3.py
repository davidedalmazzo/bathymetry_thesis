"""Build the complete Block-8 umbra_all.csv from every public STAC v2 sidecar.

S3 object sizes come from the metadata-only bucket listing.  Product payloads
are never downloaded.  Raw sidecars are retained in a compressed JSONL file.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/"Block8_validation";RAW=BASE/"catalog_raw"
ENDPOINT="https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/"


def normalize_listing_key(key):
    """Undo ListObjectsV2 form-style spaces in the human task-name segment.

    Umbra's listing returns e.g. ``Bingham+Copper+Mine`` for an S3 key whose
    actual task-name segment contains spaces.  Encoding that plus as ``%2B``
    produces a 404, while the space encoded as ``%20`` is the real object.
    UUID, collect, and filename segments are intentionally left untouched.
    """
    parts=key.split("/")
    if len(parts)>3 and parts[0]=="sar-data" and parts[1]=="tasks":
        uuid_index=next((i for i,p in enumerate(parts[2:],2) if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}",p)),None)
        stop=uuid_index if uuid_index is not None else 3
        for i in range(2,stop):
            parts[i]=parts[i].replace("+"," ")
    return "/".join(parts)


def fetch(key):
    url=ENDPOINT+urllib.parse.quote(key,safe="/")
    for attempt in range(6):
        try:
            request=urllib.request.Request(url,headers={"User-Agent":"Umbra-Block8-full-catalog/1.0"})
            with urllib.request.urlopen(request,timeout=40) as response:payload=response.read()
            return key,json.loads(payload),len(payload),None
        except Exception as exc:
            if attempt==5:return key,None,0,repr(exc)
            # The public bucket can return SlowDown after large catalog walks.
            # A deliberately gentle linear backoff is cheaper than restarting.
            time.sleep(2.0*(attempt+1))


def parse_time(value):return datetime.fromisoformat(value.replace("Z","+00:00")) if value else None


def centroid(geometry):
    if not geometry or geometry.get("type")!="Polygon":return None,None
    ring=geometry.get("coordinates",[[]])[0];ring=ring[:-1] if len(ring)>1 else ring
    return (sum(float(p[0]) for p in ring)/len(ring),sum(float(p[1]) for p in ring)/len(ring)) if ring else (None,None)


def area_km2(geometry):
    if not geometry or geometry.get("type")!="Polygon":return None
    ring=geometry.get("coordinates",[[]])[0]
    if not ring:return None
    lat0=math.radians(sum(float(p[1]) for p in ring)/len(ring));xy=[(6371.0088*math.radians(float(p[0]))*math.cos(lat0),6371.0088*math.radians(float(p[1]))) for p in ring]
    return abs(sum(xy[i][0]*xy[(i+1)%len(xy)][1]-xy[(i+1)%len(xy)][0]*xy[i][1] for i in range(len(xy)))/2)


def location_from_key(key):
    parts=key.split("/")
    if len(parts)>3 and parts[2]=="tasks":return urllib.parse.unquote_plus(parts[3])
    if len(parts)>3 and parts[2]=="task-data":return "task-data"
    return parts[2] if len(parts)>2 else ""


def main():
    with (RAW/"umbra_s3_objects.csv").open(newline="",encoding="utf-8") as f:objects=list(csv.DictReader(f))
    by_dir=defaultdict(list)
    for row in objects:
        row["key"]=normalize_listing_key(row["key"])
        row["size_bytes"]=int(row["size_bytes"]);by_dir[row["key"].rsplit("/",1)[0]].append(row)
    stac_rows=[row for row in objects if row["key"].lower().endswith(".stac.v2.json")]
    keys=sorted(row["key"] for row in stac_rows);errors=[];downloaded=0
    cache={}
    raw_cache=RAW/"umbra_stac_v2_sidecars.jsonl.gz"
    if raw_cache.exists():
        with gzip.open(raw_cache,"rt",encoding="utf-8") as f:
            for line in f:
                record=json.loads(line);cache[normalize_listing_key(record["key"])]=(record["item"],int(record.get("content_length",0)))
    journal=RAW/"umbra_stac_v2_recovery.jsonl"
    if journal.exists():
        with journal.open(encoding="utf-8") as f:
            for line in f:
                record=json.loads(line);cache[normalize_listing_key(record["key"])]=(record["item"],int(record.get("content_length",0)))
    missing=[key for key in keys if key not in cache]
    print(f"cached={len(cache)} missing={len(missing)}",flush=True)
    with journal.open("a",encoding="utf-8") as journal_handle, ThreadPoolExecutor(max_workers=48) as pool:
        futures=[pool.submit(fetch,key) for key in missing]
        for index,future in enumerate(as_completed(futures),1):
            key,item,size,error=future.result();downloaded+=size
            if downloaded>500_000_000:raise RuntimeError("STAC sidecars exceeded 500 MB metadata guardrail")
            if error:errors.append({"key":key,"error":error})
            else:
                cache[key]=(item,size)
                journal_handle.write(json.dumps({"key":key,"content_length":size,"item":item},separators=(",",":"))+"\n")
                journal_handle.flush()
            if index%100==0 or index==len(futures):print(f"recovery {index}/{len(futures)} cached={len(cache)} errors={len(errors)}",flush=True)
    key_set=set(keys)
    results=[(key,item,size) for key,(item,size) in cache.items() if key in key_set]
    downloaded=sum(size for _,_,size in results)
    rows=[]
    for key,item,_ in results:
        directory=key.rsplit("/",1)[0];members=by_dir[directory];props=item.get("properties",{});geometry=item.get("geometry")
        start=parse_time(props.get("start_datetime"));end=parse_time(props.get("end_datetime"));lon,lat=centroid(geometry)
        cphd=[x for x in members if x["key"].lower().endswith(".cphd")];sicd=[x for x in members if "_sicd" in x["key"].lower() and x["key"].lower().endswith(".nitf")]
        base=Path(key).name.rsplit(".stac.v2.json",1)[0]
        rows.append({"stac_item_id":item.get("id"),"collect_id":props.get("umbra:collect_id"),"task_id":props.get("umbra:task_id"),"collect_name":base,
            "catalog_location":location_from_key(key),"datetime_utc":props.get("datetime"),"start_datetime_utc":props.get("start_datetime"),"end_datetime_utc":props.get("end_datetime"),"catalog_dwell_s":((end-start).total_seconds() if start and end else None),
            "centroid_lon_deg":lon,"centroid_lat_deg":lat,"bbox_west":item.get("bbox",[None]*4)[0],"bbox_south":item.get("bbox",[None]*4)[1],"bbox_east":item.get("bbox",[None]*4)[2],"bbox_north":item.get("bbox",[None]*4)[3],"footprint_area_km2_approx":area_km2(geometry),
            "platform":props.get("platform"),"incidence_deg":props.get("view:incidence_angle"),"range_view_azimuth_deg":props.get("view:azimuth"),"grazing_deg":props.get("umbra:grazing_angle_degrees"),"look_side":props.get("sar:observation_direction"),"orbit_state":props.get("sat:orbit_state"),
            "polarizations":",".join(props.get("sar:polarizations",[])),"instrument_mode":props.get("sar:instrument_mode"),"resolution_range_m":props.get("sar:resolution_range"),"resolution_azimuth_m":props.get("sar:resolution_azimuth"),"best_resolution_range_m":props.get("umbra:best_resolution_range_meters"),"best_resolution_azimuth_m":props.get("umbra:best_resolution_azimuth_meters"),
            "has_cphd":bool(cphd),"has_sicd":bool(sicd),"cphd_count":len(cphd),"sicd_count":len(sicd),"cphd_size_bytes":max((x["size_bytes"] for x in cphd),default=None),"sicd_size_bytes":max((x["size_bytes"] for x in sicd),default=None),
            "cphd_total_size_bytes":sum(x["size_bytes"] for x in cphd),"sicd_total_size_bytes":sum(x["size_bytes"] for x in sicd),"cphd_asset_names":"|".join(Path(x["key"]).name for x in sorted(cphd,key=lambda x:x["key"])),"sicd_asset_names":"|".join(Path(x["key"]).name for x in sorted(sicd,key=lambda x:x["key"])),
            "stac_s3_key":key,"stac_public_url":ENDPOINT+urllib.parse.quote(key,safe="/"),"geometry_json":json.dumps(geometry,separators=(",",":"))})
    rows.sort(key=lambda x:(str(x["datetime_utc"]),str(x["collect_name"]),str(x["stac_item_id"])))
    static=BASE/"umbra_all.csv"
    if static.exists():
        archived=RAW/"umbra_static_stac_all.csv"
        if not archived.exists():static.replace(archived)
    with static.open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with gzip.open(RAW/"umbra_stac_v2_sidecars.jsonl.gz","wt",encoding="utf-8") as f:
        for key,item,size in sorted(results):f.write(json.dumps({"key":key,"content_length":size,"item":item},separators=(",",":"))+"\n")
    manifest={"generated_utc":datetime.now(timezone.utc).isoformat(),"s3_sidecar_count_in_listing":len(keys),"parsed_sidecar_count":len(results),"errors":errors,"row_count":len(rows),"rows_with_cphd":sum(bool(r["has_cphd"]) for r in rows),"rows_with_sicd":sum(bool(r["has_sicd"]) for r in rows),"sidecar_payload_bytes":downloaded,
        "umbra_all_csv":str(static.resolve()),"umbra_all_sha256":hashlib.sha256(static.read_bytes()).hexdigest(),"scope":"All public *.stac.v2.json under sar-data/ at listing time; sizes joined from ListObjectsV2. No SAR payloads downloaded.","metadata_download_guardrail_bytes":500_000_000}
    (RAW/"FULL_CATALOG_MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8");print(json.dumps({k:v for k,v in manifest.items() if k!="errors"},indent=2))


if __name__=="__main__":main()

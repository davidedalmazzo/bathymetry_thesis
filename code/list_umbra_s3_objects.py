"""List public Umbra S3 objects and sizes; download no object payloads."""

from __future__ import annotations

import csv
import hashlib
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/"Block8_validation";RAW=BASE/"catalog_raw"
ENDPOINT="https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/"


def main():
    RAW.mkdir(parents=True,exist_ok=True);rows=[];token=None;pages=0;metadata_bytes=0
    while True:
        query={"list-type":"2","prefix":"sar-data/","max-keys":"1000","encoding-type":"url"}
        if token:query["continuation-token"]=token
        url=ENDPOINT+"?"+urllib.parse.urlencode(query)
        req=urllib.request.Request(url,headers={"User-Agent":"Umbra-Block8-object-index/1.0"})
        with urllib.request.urlopen(req,timeout=60) as response:payload=response.read()
        metadata_bytes+=len(payload);pages+=1
        if metadata_bytes>500_000_000:raise RuntimeError("S3 listing metadata exceeded 500 MB guardrail")
        root=ET.fromstring(payload);ns={"s3":"http://s3.amazonaws.com/doc/2006-03-01/"}
        for obj in root.findall("s3:Contents",ns):
            rows.append({"key":urllib.parse.unquote(obj.findtext("s3:Key",namespaces=ns)),"size_bytes":int(obj.findtext("s3:Size",namespaces=ns)),
                "last_modified":obj.findtext("s3:LastModified",namespaces=ns),"etag":obj.findtext("s3:ETag",namespaces=ns).strip('"'),"storage_class":obj.findtext("s3:StorageClass",namespaces=ns)})
        truncated=root.findtext("s3:IsTruncated",namespaces=ns)=="true";token=root.findtext("s3:NextContinuationToken",namespaces=ns)
        print(f"pages={pages} objects={len(rows)}",flush=True)
        if not truncated:break
    path=RAW/"umbra_s3_objects.csv"
    with path.open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    lower=[(r,r["key"].lower()) for r in rows]
    manifest={"generated_utc":datetime.now(timezone.utc).isoformat(),"endpoint":ENDPOINT,"prefix":"sar-data/","page_count":pages,"object_count":len(rows),"listing_metadata_bytes":metadata_bytes,
        "cphd_object_count":sum(k.endswith(".cphd") for _,k in lower),"sicd_nitf_object_count":sum("_sicd" in k and k.endswith(".nitf") for _,k in lower),
        "stac_v2_json_count":sum(k.endswith(".stac.v2.json") for _,k in lower),"total_cphd_bytes":sum(r["size_bytes"] for r,k in lower if k.endswith(".cphd")),
        "csv":str(path.resolve()),"csv_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"guardrail":"ListObjectsV2 metadata only; no object payloads downloaded."}
    (RAW/"S3_LISTING_MANIFEST.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8");print(json.dumps(manifest,indent=2))


if __name__=="__main__":main()

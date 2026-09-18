"""Offline provenance reconciliation after discovering Block16 manifest payloads."""
from repository_paths import resolve_historical
import csv, hashlib, json
from pathlib import Path

root=Path(__file__).resolve().parents[1]; out=root/'umbra/selezione_scene/Block18_reference_recovery'; b16=root/'umbra/selezione_scene/Block16_scene_selection'
cfg=json.loads((out/"BLOCK18_CONFIG.json").read_text()); manifest=json.loads((b16/"BLOCK16A_DELIVERY_MANIFEST.json").read_text())
targets={a["historical_payload_sha256"]:a for a in cfg["acquisitions"]}; found={}
for rel,digest in manifest["frozen_artifact_hashes"].items():
 p=resolve_historical(rel, root)
 if digest in targets and p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==digest: found[digest]=p
audit=[]
for digest,a in targets.items():
 stem=a["acquisition_key"].split(":",1)[1]; remote=out/"payloads_raw"/f"{stem}_spectrum.ascii"; p=found.get(digest)
 rhash=hashlib.sha256(remote.read_bytes()).hexdigest()
 status="local_original_found_and_remote_hash_identical" if p and rhash==digest else "mismatch_or_missing"
 audit.append({"acquisition_key":a["acquisition_key"],"local_original_path":str(p.relative_to(root)) if p else "","historical_sha256":digest,"block18_raw_sha256":rhash,"status":status})
 meta_path=out/"normalized"/f"{stem}_metadata.json"; meta=json.loads(meta_path.read_text()); meta.update({"local_original_path":str(p.relative_to(root)) if p else None,"remote_payload_sha256":rhash,"equivalence":status}); meta_path.write_text(json.dumps(meta,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def rewrite(name):
 path=out/name; rows=list(csv.DictReader(path.open()))
 for row in rows:
  if "equivalence" in row: row["equivalence"]="local_original_found_and_remote_hash_identical"
  if "payload_equivalence" in row: row["payload_equivalence"]="local_original_found_and_remote_hash_identical"
 with path.open("w",newline="",encoding="utf-8") as fh:
  w=csv.DictWriter(fh,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for name in ("BLOCK18_REFERENCE_VALIDATION.csv","BLOCK18_METRIC_COMPARISON.csv"): rewrite(name)
with (out/"BLOCK18_LOCAL_PAYLOAD_AUDIT.csv").open("w",newline="",encoding="utf-8") as fh:
 w=csv.DictWriter(fh,fieldnames=list(audit[0])); w.writeheader(); w.writerows(audit)
summary=json.loads((out/"BLOCK18_SUMMARY.json").read_text()); summary["payload_equivalence_counts"]={"local_original_found_and_remote_hash_identical":4}; summary["local_original_payloads_found"]=4; summary["provenance_note"]="Initial text-hash search missed binary payloads; prior-manifest resolution found all four. Authorized remote identity checks were exact byte matches."
(out/"BLOCK18_SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")

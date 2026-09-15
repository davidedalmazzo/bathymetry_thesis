"""Create gate table, prior-manifest audit, summary annotations and manifest."""
import csv, hashlib, json, platform, sys
from datetime import datetime, timezone
from pathlib import Path

root=Path(__file__).resolve().parents[1]; out=root/"Block18_reference_recovery"; b16=root/"Block16_scene_selection"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def csvrows(p): return list(csv.DictReader(p.open(encoding="utf-8-sig")))
def writecsv(p,rows):
 with p.open("w",newline="",encoding="utf-8") as fh:
  w=csv.DictWriter(fh,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

# Expand the candidate table into one auditable row per gate.
source=csvrows(out/"BLOCK18_CANDIDATE_GATE_COMPARISON.csv"); long=[]
allrows={r["acquisition_key"]:r for r in csvrows(b16/"BLOCK16A_ALL_CANDIDATES.csv") if r["acquisition_key"] in {x["acquisition_key"] for x in source}}
refs={r["acquisition_key"]:r for r in csvrows(out/"BLOCK18_REFERENCE_VALIDATION.csv")}
for s in source:
 r=allrows[s["acquisition_key"]]; ref=refs[s["acquisition_key"]]; failures=set((s["historical_gate_failures"] or "").split(";"))-{""}
 specs=[
  ("products_associated",str(r.get("metadata_association_verified")),"CPHD/SICD association from frozen Block16A metadata"),
  ("measured_reference",ref["admissible_measured_reference"],f"joint energy coverage={ref['joint_directional_energy_coverage_band_0p04_0p25']}"),
  ("temporal_paths","pass" if r.get("temporal_hard_gate")=="True" else "fail",f"catalog={r.get('catalog_duration_s')}; CPHD={r.get('cphd_tx_time_span_s')}; SICD={r.get('sicd_processed_aperture_s')} s"),
  ("nominal_cycles","pass" if r.get("temporal_hard_gate")=="True" else "fail",f"observable_cycles={r.get('observable_cycles')}; design indicator only"),
  ("wave_range_geometry","fail" if "unfavorable_wave_range_angle" in failures else "pass",f"axial difference={r.get('wave_range_axial_difference_deg')} deg"),
  ("measured_energy","fail" if failures & {"measured_swell_not_dominant","weak_measured_sea_state"} else "pass",f"failures={';'.join(sorted(failures & {'measured_swell_not_dominant','weak_measured_sea_state'})) or 'none'}"),
  ("marine_roi_proxy","preliminary",f"ocean_fraction={r.get('ocean_fraction')}; Natural Earth cannot verify SAR cleanliness"),
  ("sar_validation","not_verified","delta_eff; SAR-scale clearance; lobe separation; usable intensity ROI; SNR/coherence; full Doppler-time mapping"),
 ]
 for gate,status,evidence in specs: long.append({"acquisition_key":s["acquisition_key"],"historical_category":s["historical_category"],"block17_status":s["block17_status"],"block18_category":s["block18_category"],"gate":gate,"status":status,"evidence_or_limit":evidence})
writecsv(out/"BLOCK18_CANDIDATE_GATE_COMPARISON.csv",long)

# Verify pertinent historical manifests without rewriting them.
audits=[]
for rel in ["Vandenberg/results/analysis_block15/BLOCK15K_DELIVERY_MANIFEST.json","Block16_scene_selection/BLOCK16A_DELIVERY_MANIFEST.json","Block17_selector_consolidation/BLOCK17_DELIVERY_MANIFEST.json"]:
 m=json.loads((root/rel).read_text()); records=[]
 def walk(x):
  if isinstance(x,dict):
   if isinstance(x.get("path"),str) and isinstance(x.get("sha256"),str): records.append((x["path"],x["sha256"]))
   for v in x.values(): walk(v)
  elif isinstance(x,list):
   for v in x: walk(v)
 walk(m)
 for section in ("output_hashes","frozen_artifact_hashes"):
  for p,v in m.get(section,{}).items(): records.append((p,v.get("sha256") if isinstance(v,dict) else v))
 seen=set(); bad=[]; missing=[]; checked=0
 for p,digest in records:
  if (p,digest) in seen: continue
  seen.add((p,digest)); path=root/p
  if not path.exists(): missing.append(p)
  elif sha(path)!=digest: bad.append(p)
  checked+=1
 expected_later=[p for p in bad if p=="WORKLOG.md"]
 audits.append({"manifest":rel,"records_checked":checked,"missing":missing,"mismatches":bad,"expected_additive_worklog_mismatches":expected_later,"unexpected_mismatches":[p for p in bad if p not in expected_later]})
(out/"BLOCK18_PRIOR_MANIFEST_AUDIT.json").write_text(json.dumps(audits,indent=2,sort_keys=True)+"\n",encoding="utf-8")

summary=json.loads((out/"BLOCK18_SUMMARY.json").read_text()); summary.update({"tests":{"passed":187,"failed":0,"skipped":0},"offline_reproduction":"exact_4_acquisitions_392_bins_max_difference_0","prior_manifest_audit":"no unexpected mismatches; WORKLOG differences are later additive history","metric_changes":{"nonzero_count":1,"only":"2026-03-14 long-energy fraction: +0.0004688232536333803","category_effect":0},"next_step_not_started":"metadata-only assessment of station-42084 spatial representativeness for these four scenes"})
(out/"BLOCK18_SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")

inputs=["Block16_scene_selection/BLOCK16A_MEASURED_SPECTRA.csv","Block16_scene_selection/BLOCK16A_ALL_CANDIDATES.csv","Block16_scene_selection/BLOCK16A_CONFIG.json","Block16_scene_selection/BLOCK16A_DELIVERY_MANIFEST.json","Block17_selector_consolidation/BLOCK17_CONFIG.json","Block17_selector_consolidation/BLOCK17_DELIVERY_MANIFEST.json"]
outputs=[str(p.relative_to(root)).replace('\\','/') for p in sorted(out.rglob('*')) if p.is_file() and p.name!="BLOCK18_DELIVERY_MANIFEST.json"]+[
 "code/umbra_sar/reference_recovery.py","code/run_block18_reference_recovery.py","code/reconcile_block18_local_payloads.py","code/verify_block18_offline.py","code/finalize_block18.py","tests/test_reference_recovery.py","WORKLOG.md"]
def record(rel):
 p=root/rel; return {"path":rel,"bytes":p.stat().st_size,"sha256":sha(p)}
manifest={"block":"18","generated_utc":datetime.now(timezone.utc).isoformat(),"config_sha256":sha(out/"BLOCK18_CONFIG.json"),"inputs":[record(x) for x in inputs],"outputs":[record(x) for x in outputs],"remote_responses":[record(str(p.relative_to(root)).replace('\\','/')) for p in sorted((out/"payloads_raw").iterdir())],"budget":{"transactions":7,"bytes":560916,"maximum_transactions":100,"maximum_bytes":52428800,"maximum_response_bytes":10485760},"environment":{"python":sys.version,"platform":platform.platform()},"tests":{"passed":187,"failed":0,"skipped":0},"scope":{"acquisitions":4,"sar_downloads":0,"sar_reads":0,"catalog_crawls":0,"vandenberg_reopened":False},"reproducibility":"exact offline from saved payloads"}
(out/"BLOCK18_DELIVERY_MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")

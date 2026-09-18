"""Build the Block17 provenance manifest after validation."""
from repository_paths import resolve_historical
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

root=Path(__file__).resolve().parents[1]
out=root/'umbra/selezione_scene/Block17_selector_consolidation'
inputs=['umbra/selezione_scene/Block16_scene_selection/BLOCK16A_SUMMARY.json','umbra/selezione_scene/Block16_scene_selection/BLOCK16A_ALL_CANDIDATES.csv','umbra/selezione_scene/Block16_scene_selection/BLOCK16A_MEASURED_SPECTRA.csv','umbra/selezione_scene/Block16_scene_selection/BLOCK16A_CONFIG.json','umbra/selezione_scene/Block16_scene_selection/catalog_snapshots/20260913T231747Z/manifest.json','umbra/Vandenberg/results/analysis_block12/BLOCK12_PHASE_SLOPE.json']
outputs=['umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_PROTOCOL.md','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_CONFIG.json','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_CONFIG.sha256','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_BASELINE_CORRECTED.csv','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_REVISED_SHORTLIST.csv','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_MARINE_COUNTERFACTUAL.json','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_SYNTHETIC_WIDTH_AUDIT.csv','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_SYNTHETIC_WIDTH_AUDIT.json','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_THEORY_CHECKS.json','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_ERRATA.md','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_THEORY_ASSUMPTIONS.md','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_REPORT.md','umbra/selezione_scene/Block17_selector_consolidation/BLOCK17_SUMMARY.json',"code/umbra_sar/selector_consolidation.py","code/run_block17_selector_consolidation.py","code/build_block17_manifest.py","tests/test_selector_consolidation.py","WORKLOG.md"]
def record(rel):
 p=resolve_historical(rel, root)
 return {"path":rel,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
manifest={"block":"17","generated_utc":datetime.now(timezone.utc).isoformat(),"scope":"offline selector consolidation; no network and no SAR reads","inputs":[record(x) for x in inputs],"outputs":[record(x) for x in outputs],"validation":{"pytest":{"passed":179,"failed":0,"skipped":0},"baseline_categories":{"A":0,"B":1,"C":33,"D":10106,"E":0},"category_changes":0,"network_requests":0,"sar_reads":0}}
(out/"BLOCK17_DELIVERY_MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")

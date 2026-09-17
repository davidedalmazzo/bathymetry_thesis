"""Offline evidence/manifest collector; never performs HTTP or reads SAR."""
import csv
import json
import platform
from pathlib import Path
from frf_client.transport import digest, save_json

BASE=Path("Block32_frf_client")


def main():
    state=json.loads((BASE/"cache/NETWORK_STATE.json").read_text())
    ledger=[json.loads(x) for x in (BASE/"cache/requests.jsonl").read_text().splitlines()]
    imports=json.loads((BASE/"results/LEGACY_CACHE_AUDIT.json").read_text())
    endpoint={"network":state,"started_transactions":sum(x.get("status")=="started" for x in ledger),
              "complete_responses":sum(x.get("status")=="response" for x in ledger),
              "bytes_in_complete_responses":sum(x.get("bytes",0) for x in ledger),
              "partial_failed_transfer_bytes_from_persistent_counter":state["bytes"]-sum(x.get("bytes",0) for x in ledger),
              "partial_transfer_note":"One failed AWAC June spectral transfer; incomplete payload NOT reused. Streaming counter includes its chunks; earlier error log lacked per-error byte field (now corrected).",
              "verified_legacy_unique_urls":len({x["url"] for x in imports if x["status"]=="verified_legacy_reused"}),
              "legacy_hash_mismatches":[x for x in imports if x["status"]!="verified_legacy_reused"],
              "cases":[]}
    mismatches=[]
    for folder in sorted((BASE/"results").iterdir()):
        if not folder.is_dir():continue
        observations=list(csv.DictReader((folder/"OBSERVATIONS.csv").open(encoding="utf-8",newline="")))
        spatial=list(csv.DictReader((folder/"DISTANCES.csv").open(encoding="utf-8",newline="")))
        selected=[r for r in observations if r["role"]=="nearest_context" and r["variable"] in ("waveHs","waveTp","waveMeanDirection","waveMeanDirectionPeakFrequency","windSpeed","windDirection","windGust","currentSpeed","waterLevel","gapGauge")]
        endpoint["cases"].append({"acquisition":json.loads((folder/"ACQUISITION.json").read_text()),
                                  "observations":selected,"distances":spatial,
                                  "spectral_summaries":json.loads((folder/"SPECTRAL_SUMMARIES.json").read_text())})
        manifest=json.loads((folder/"MANIFEST.json").read_text())
        for e in manifest["artifacts"]+manifest["code_sources"]:
            if digest(Path(e["path"]).read_bytes())!=e["sha256"]:mismatches.append(e["path"])
    save_json(BASE/"REAL_ENDPOINT_REPORT.json",endpoint)
    for e in json.loads((BASE/"FROZEN_INPUT_HASHES.json").read_text()):
        if digest(Path(e["path"]).read_bytes())!=e["sha256"]:mismatches.append(e["path"])
    for p in (BASE/"cache").glob("*.json"):
        e=json.loads(p.read_text())
        if e.get("status")=="ok" and digest(p.with_suffix(".payload").read_bytes())!=e["sha256"]:mismatches.append(str(p))
    oversized=[str(p) for p in BASE.rglob("*") if p.is_file() and p.stat().st_size>=100*1024**2]
    audit={"mismatches":mismatches,"files_ge_100_MiB":oversized,
           "network_within_budget":state["transactions"]<=40 and state["bytes"]<=100*1024**2,
           "ledger_transaction_count_matches":endpoint["started_transactions"]==state["transactions"]}
    save_json(BASE/"DELIVERY_AUDIT.json",audit)
    sources=sorted(Path("code/frf_client").glob("*.py"))+[Path("code/run_block32_frf_client.py"),Path(__file__),Path("tests/test_frf_client.py"),Path("code/README_FRF_CLIENT.md")]
    artifacts=[p for p in sorted(BASE.rglob("*")) if p.is_file() and "cache" not in p.parts and p.name!="DELIVERY_MANIFEST.json"]+[Path("CHECKPOINT_32.md")]
    save_json(BASE/"DELIVERY_MANIFEST.json",{"python":platform.python_version(),"network":state,
        "artifacts":[{"path":str(p),"bytes":p.stat().st_size,"sha256":digest(p.read_bytes())} for p in artifacts if p.exists()],
        "code_sources":[{"path":str(p),"sha256":digest(p.read_bytes())} for p in sources]})
    print(json.dumps(audit,indent=2))
    return int(bool(mismatches or oversized or not audit["network_within_budget"] or not audit["ledger_transaction_count_matches"]))


if __name__=="__main__":raise SystemExit(main())

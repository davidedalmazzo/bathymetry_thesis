"""Block37 frozen-input audit and provenance manifest."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from frf_client.transport import digest, save_json
from repository_paths import ROOT, resolve_historical

BASE = ROOT / "duck_frf" / "Block37_s1_iw_spatial_trial"
BASELINE = ROOT / "duck_frf" / "Block34_frf_operational" / "FROZEN_BASELINE.json"


def frozen_audit():
    rows=json.loads(BASELINE.read_text(encoding="utf-8")); mismatches=[]
    for row in rows:
        path=resolve_historical(row["path"])
        if not path.is_file(): mismatches.append({"path":row["path"],"status":"missing"})
        elif ((row.get("bytes") is not None and path.stat().st_size != row["bytes"])
              or digest(path.read_bytes()) != row["sha256"]):
            mismatches.append({"path":row["path"],"status":"hash_or_size_mismatch"})
    result={"baseline":BASELINE.relative_to(ROOT).as_posix(),"verified":len(rows)-len(mismatches),
            "mismatches":mismatches,"historical_files_not_rewritten":True}
    save_json(BASE/"FROZEN_AUDIT.json",result)
    if mismatches: raise RuntimeError("Frozen baseline mismatch")


def manifest():
    excluded={"source_products","extracted_safe","cache"}; artifacts=[]
    for path in sorted(BASE.rglob("*")):
        if not path.is_file() or excluded & set(path.relative_to(BASE).parts) or path.name=="MANIFEST.json": continue
        if path.stat().st_size >= 100*1024**2: raise RuntimeError(f"Oversized versionable artifact: {path}")
        artifacts.append({"path":path.relative_to(ROOT).as_posix(),"bytes":path.stat().st_size,"sha256":digest(path.read_bytes())})
    sources=[ROOT/x for x in ["code/download_block37_s1.py","code/prepare_block37_safe.py","code/s1_spatial_trial.py",
        "code/run_block37_spatial.py","code/s1_spatial_trial_validate.py","tests/test_block37_download.py",
        "tests/test_block37_spatial.py","requirements-thesis.txt",".gitignore"]]
    save_json(BASE/"MANIFEST.json",{"block":37,"created_utc":datetime.now(timezone.utc).isoformat(),
        "artifacts":artifacts,"code_sources":[{"path":p.relative_to(ROOT).as_posix(),"bytes":p.stat().st_size,
        "sha256":digest(p.read_bytes())} for p in sources],"archive_in_git_ignored_directory":True,
        "measurement_tiff_not_versioned":True,"credentials_not_versioned":True,"no_commit_push":True,
        "frozen_audit":"FROZEN_AUDIT.json","full_suite":"FULL_SUITE.json"})


def main():
    if Path.cwd().resolve()!=ROOT: raise RuntimeError("Run from repository root")
    frozen_audit(); manifest(); print("Block37 manifest complete; frozen audit passed")


if __name__=="__main__": main()

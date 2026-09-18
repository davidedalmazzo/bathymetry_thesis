"""Offline Block33 verification; only tests/mocks and local files, never HTTP."""
import argparse
import hashlib
import json
import os
import subprocess
import shutil
from pathlib import Path
from frf_client.transport import save_json, digest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"Block33_frf_offline_correction"


def relative(path): return path.resolve().relative_to(ROOT).as_posix()


def snapshot():
    files=[p for p in (ROOT/"Block32_frf_client").rglob("*") if p.is_file()]
    files += [ROOT/"CHECKPOINT_32.md"]
    save_json(BASE/"FROZEN_BASELINE.json",[{"path":relative(p),"sha256":digest(p.read_bytes()),"bytes":p.stat().st_size} for p in sorted(files)])
    result=subprocess.run(["git","-c",f"safe.directory={ROOT.as_posix()}","status","--short"],capture_output=True,text=True)
    save_json(BASE/"INITIAL_GIT.json",{"head":subprocess.check_output(["git","-c",f"safe.directory={ROOT.as_posix()}","rev-parse","HEAD"],text=True).strip(),"status":result.stdout})


def resolve(path,remaps=None):
    # Frozen Windows absolute paths require an explicit prefix remap, never basename guessing.
    import ntpath
    if ntpath.isabs(path):
        for prefix,destination in (remaps or {}).items():
            if path.lower().replace('\\','/').startswith(prefix.lower().replace('\\','/').rstrip('/')+'/'):
                suffix=path[len(prefix.rstrip('/\\')):].lstrip('/\\').replace('\\','/')
                return ROOT/destination/suffix
        return None
    return ROOT/path.replace('\\','/')


def audit_entries(entries,remaps=None):
    rows=[]
    for entry in entries:
        p=resolve(entry["path"],remaps)
        status="unresolved_path" if p is None or not p.resolve().is_relative_to(ROOT) else "file_unavailable" if not p.is_file() else "hash_verified" if digest(p.read_bytes())==entry["sha256"] else "mismatch"
        rows.append({"original_path":entry["path"],"resolved_path":relative(p) if p and p.resolve().is_relative_to(ROOT) else None,"status":status})
    return rows


def test_run(name,args,cwd=ROOT):
    result=subprocess.run([str(ROOT/".venv-umbra-thesis/Scripts/python.exe"),"-m","pytest",*args],cwd=cwd,capture_output=True,text=True)
    save_json(BASE/(name+".json"),{"command":[".venv-umbra-thesis/Scripts/python.exe","-m","pytest",*args],"cwd":relative(cwd),"exit_code":result.returncode,"stdout":result.stdout,"stderr":result.stderr,"actual_http_transactions":0})
    print(result.stdout)
    return result.returncode


def main():
    ap=argparse.ArgumentParser();ap.add_argument("phase",choices=["snapshot","reproduce","tests","audit","clean","regressions"]);args=ap.parse_args()
    if Path.cwd().resolve()!=ROOT:raise ValueError("Repository root required")
    os.environ.update(TEMP=str(ROOT/"_tmp"),TMP=str(ROOT/"_tmp"),MPLCONFIGDIR=str(ROOT/"_cache/matplotlib"))
    if args.phase=="snapshot":snapshot();return 0
    if args.phase=="reproduce":return test_run("REPRODUCTION",["tests/test_frf_block33.py","-q","--tb=short"])
    if args.phase=="tests":return test_run("FULL_SUITE",["-q"])
    if args.phase=="regressions":
        import socket
        def forbidden(*args,**kwargs):raise AssertionError("Actual HTTP prohibited")
        socket.create_connection=forbidden
        source=ROOT/"Block32_frf_client/cache";destination=BASE/"cache"
        if not source.is_dir():
            save_json(BASE/"REGRESSION_COMPARISON.json",{"status":"not_executable_private_cache_unavailable"});return 0
        if destination.exists():
            for path in source.rglob('*'):
                if path.is_file() and (not (destination/path.relative_to(source)).is_file() or digest(path.read_bytes())!=digest((destination/path.relative_to(source)).read_bytes())):
                    raise ValueError("Copied regression cache differs from frozen source; do not silently reset")
        else:shutil.copytree(source,destination)
        from frf_client.transport import Transport
        from frf_client.inputs import read_acquisitions
        from frf_client.client import Client
        cfg=json.loads((ROOT/"Block32_frf_client/CONFIG.json").read_text())
        transport=Transport(destination,offline=True,max_requests=cfg['max_requests'],max_bytes=cfg['max_bytes'])
        records=read_acquisitions(ROOT/"Block32_frf_client/REGRESSION_ACQUISITIONS.json")
        initial=transport.state.copy()
        Client(transport,cfg).run(records,BASE/"regressions",mode="offline")
        import csv
        comparisons=[]
        for acquisition in records:
            identifier=acquisition['acquisition_id']
            old=ROOT/'Block32_frf_client/results'/identifier;new=BASE/'regressions'/identifier
            before=list(csv.DictReader((old/'OBSERVATIONS.csv').open(encoding='utf-8')))
            after=list(csv.DictReader((new/'OBSERVATIONS.csv').open(encoding='utf-8')))
            key=lambda r:(r['instrument_id'],r['family'],r['variable'],r['role'])
            old_rows={key(r):r for r in before};new_rows={key(r):r for r in after}
            fields=['product','sensor_time_utc','timestamp_original','timestamp_original_units','offset_seconds','qc_flag','value','status','within_tolerance','representative_eligible','valid_fraction']
            common=old_rows.keys()&new_rows.keys()
            changed=[{'key':list(k),'differences':{f:{'old':old_rows[k].get(f),'new':new_rows[k].get(f)} for f in fields if old_rows[k].get(f)!=new_rows[k].get(f)}} for k in sorted(common) if any(old_rows[k].get(f)!=new_rows[k].get(f) for f in fields)]
            old_spec=json.loads((old/'SPECTRAL_SUMMARIES.json').read_text());new_spec=json.loads((new/'SPECTRAL_SUMMARIES.json').read_text())
            spectral=[]
            for s in old_spec:
                other=next((v for v in new_spec if v['instrument_id']==s['instrument_id']),None)
                spectral.append({'instrument_id':s['instrument_id'],'differences':{f:{'old':s.get(f),'new':other.get(f) if other else None} for f in ('m0_m2','Hm0_m','Tm01_s','Tm02_s','Tp_bin_s','published_peak_band','missing_bin_indices') if other is None or s.get(f)!=other.get(f)}})
            old_distances=list(csv.DictReader((old/'DISTANCES.csv').open(encoding='utf-8')))
            new_distances=list(csv.DictReader((new/'DISTANCES.csv').open(encoding='utf-8')))
            geo=[]
            for r in old_distances:
                observation=next((v for v in new_rows.values() if v['instrument_id']==r['instrument_id'] and v['family']==r['family'] and v['role']=='nearest_context'),None)
                actual=next((v for v in new_distances if observation and v['position_id']==observation['position_id']),None)
                geo.append({'instrument_id':r['instrument_id'],'family':r['family'],'differences':{f:{'old':r.get(f),'new':actual.get(f) if actual else None} for f in r if actual is None or r.get(f)!=actual.get(f)}})
            comparisons.append({'acquisition_id':identifier,'old_rows':len(before),'new_rows':len(after),'common_rows':len(common),'changed':changed,'removed_keys':[list(k) for k in sorted(old_rows.keys()-new_rows.keys())],'added_keys':[list(k) for k in sorted(new_rows.keys()-old_rows.keys())],'spectral_comparison':spectral,'nearest_context_position_comparison':geo})
        save_json(BASE/'REGRESSION_COMPARISON.json',{'actual_http_transactions':0,'initial_copied_state':initial,'final_copied_state':transport.state,'cases':comparisons})
        assert transport.state==initial
        return 0
    if args.phase=="clean":
        destination=BASE/"clean_tree"
        sequence=1
        while destination.exists():
            sequence+=1;destination=BASE/f"clean_tree_{sequence}"
        paths=subprocess.check_output(["git","-c",f"safe.directory={ROOT.as_posix()}","ls-files"],text=True).splitlines()
        extra=["tests/test_block30_frf_conditions.py","tests/test_frf_block33.py","code/run_block33_frf_verification.py"]+[relative(p) for p in (ROOT/"tests/fixtures/frf_block33").glob("*")]+[relative(p) for p in (ROOT/"code/frf_client").glob("*.py")]
        selected=[p for p in paths if p.startswith("code/") or p.startswith("tests/") or p=="requirements-thesis.txt"]
        copied=[]
        for name in sorted(set(selected+extra)):
            source=ROOT/name
            if not source.is_file():continue
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            copied.append({"path":name,"sha256":digest(source.read_bytes()),"tracked":name in paths})
        save_json(BASE/"CLEAN_TREE_INPUTS.json",{"note":"Tracked working-tree snapshot plus explicitly listed pending lightweight tests/fixtures; no cache/radar/env. Not a claim that uncommitted files are already in Git.","files":copied})
        return test_run("CLEAN_CLIENT_TESTS",["tests/test_frf_client.py","tests/test_frf_block33.py","tests/test_block30_frf_conditions.py","--basetemp","Block33_test_tmp","-q"],destination)
    baseline=json.loads((BASE/"FROZEN_BASELINE.json").read_text())
    historical=json.loads((ROOT/"Block32_frf_client/FROZEN_INPUT_HASHES.json").read_text())
    remaps={"D:/Dati Tesi/Umbra":"."}
    save_json(BASE/"FROZEN_AUDIT.json",{"block32_artifacts_and_cache":audit_entries(baseline),"historical_inputs":audit_entries(historical,remaps),"absolute_path_remapping":remaps})
    original_manifest=json.loads((ROOT/'Block32_frf_client/DELIVERY_MANIFEST.json').read_text())
    save_json(BASE/'HISTORICAL_MANIFEST_AUDIT.json',{'frozen_artifact_references':audit_entries(original_manifest['artifacts'],remaps),
        'historical_code_references':audit_entries(original_manifest['code_sources'],remaps),
        'note':'Source mismatches due to authorized Block33 correction are expected and distinct from unchanged frozen artifacts. The historical manifest is preserved.'})
    import importlib.metadata
    tracked=set(subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}','ls-files'],text=True).splitlines())
    dependencies=[]
    for line in (ROOT/'requirements-thesis.txt').read_text().splitlines():
        if '==' not in line:continue
        package,pin=line.split('==',1)
        try:installed=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:installed=None
        dependencies.append({'package':package,'pinned':pin,'installed':installed,'status':'pinned_installed_match' if installed==pin else 'missing_or_version_mismatch'})
    required=[relative(p) for p in (ROOT/'code/frf_client').glob('*.py')]+['code/run_block32_frf_client.py','code/run_block30_frf_conditions.py','code/run_block33_frf_verification.py','tests/test_frf_client.py','tests/test_frf_block33.py','tests/test_block30_frf_conditions.py','tests/conftest.py','requirements-thesis.txt','Block32_frf_client/REGRESSION_ACQUISITIONS.json']+[relative(p) for p in (ROOT/'tests/fixtures/frf_block33').glob('*')]
    save_json(BASE/'REPRODUCIBILITY_AUDIT.json',{'dependencies':dependencies,'files':[{'path':path,'available':(ROOT/path).is_file(),'tracked':path in tracked,'sha256':digest((ROOT/path).read_bytes()) if (ROOT/path).is_file() else None} for path in sorted(required)],
        'ordinary_offline_tests':['tests/test_frf_client.py','tests/test_frf_block33.py','tests/test_block30_frf_conditions.py'],
        'cache_regression_requires':'Verified private Block32 cache; otherwise explicitly not executable. No request or fabricated cache.',
        'historical_audit_requires':'Historical original exports/artifacts are not all tracked; statuses distinguish unavailable/unresolved/mismatch/verified.',
        'pending_versioning_note':'No commit/push authorized; clean-tree snapshot includes explicitly listed pending files, not a claim about current remote HEAD.',
        'actual_http_transactions':0})
    artifacts=[p for p in BASE.rglob("*") if p.is_file() and not any(x.startswith("clean_tree") or x=="cache" for x in p.parts) and p.name!="MANIFEST.json"]
    code=[ROOT/"code/run_block33_frf_verification.py",ROOT/"code/run_block32_frf_client.py",ROOT/"tests/test_frf_block33.py",ROOT/"tests/test_block30_frf_conditions.py",ROOT/"code/README_FRF_CLIENT.md",ROOT/"CHECKPOINT_33.md"]+list((ROOT/"code/frf_client").glob("*.py"))+list((ROOT/"tests/fixtures/frf_block33").glob("*"))
    save_json(BASE/"MANIFEST.json",{"actual_http_transactions":0,"artifacts":[{"path":relative(p),"sha256":digest(p.read_bytes()),"bytes":p.stat().st_size} for p in sorted(artifacts+ [p for p in code if p.exists()])]})
    return 0


if __name__=="__main__":raise SystemExit(main())

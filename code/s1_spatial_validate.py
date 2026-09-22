"""Offline full-suite evidence and current Block35 provenance manifest."""
import json
import os
import subprocess
import sys
import uuid
import argparse
from datetime import datetime, timezone
from pathlib import Path
from repository_paths import ROOT
from frf_client.transport import save_json, digest
from s1_spatial_compare import BASE


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest-only',action='store_true')
    args=p.parse_args(argv)
    if Path.cwd().resolve()!=ROOT:raise ValueError('Run from repository root')
    env=os.environ.copy();env.update(TEMP=str(ROOT/'_tmp'),TMP=str(ROOT/'_tmp'),MPLCONFIGDIR=str(ROOT/'_cache/matplotlib'))
    if not args.manifest_only:
        temporary=ROOT/'_tmp'/('pytest_block35_'+uuid.uuid4().hex)
        if temporary.exists():raise ValueError('Fresh isolated test directory required')
        cmd=[sys.executable,'-m','pytest','-q','--basetemp='+str(temporary)]
        result=subprocess.run(cmd,text=True,capture_output=True,env=env)
        save_json(BASE/'FULL_SUITE.json',{'command':cmd,'exit_code':result.returncode,'stdout':result.stdout,
            'stderr':result.stderr,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'offline_tests_not_live_api_proof':True,'interpreter':sys.executable})
        print(result.stdout[-1500:]);print(result.stderr[-1500:])
    evidence=json.loads((BASE/'FULL_SUITE.json').read_text())
    artifacts=[]
    for path in sorted(BASE.rglob('*')):
        if not path.is_file() or {'cache','network'} & set(path.relative_to(BASE).parts) or path.name=='MANIFEST.json':continue
        if path.stat().st_size>=100*1024**2:raise ValueError('Oversized versionable artifact: '+str(path))
        artifacts.append({'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':digest(path.read_bytes())})
    sources=[*ROOT.glob('code/s1_*.py'),ROOT/'code/README_S1_SPATIAL.md',*ROOT.glob('code/frf_client/*.py'),
        ROOT/'code/run_block33_s1_catalogue_query.py',ROOT/'code/run_block33_spatial_gate.py',ROOT/'tests/test_s1_spatial.py',
        ROOT/'code/repository_paths.py',ROOT/'repository_paths.json',ROOT/'requirements-thesis.txt']
    cache=[]
    for p in sorted((BASE/'cache').glob('*.json')):
        meta=json.loads(p.read_text())
        if meta.get('status')=='ok':
            payload=p.with_suffix('.payload')
            if not payload.exists() or payload.stat().st_size!=meta['bytes'] or digest(payload.read_bytes())!=meta['sha256']:
                raise ValueError('Cache provenance mismatch: '+str(p))
            cache.append({k:meta.get(k) for k in ('url','final_url','sha256','bytes','verified','legacy_source')})
    save_json(BASE/'MANIFEST.json',{'block':35,'created_utc':datetime.now(timezone.utc).isoformat(),
        'artifacts':artifacts,'code_sources':[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p.read_bytes())} for p in sorted(set(sources))],
        'verified_cache_payload_provenance':cache,'cache_local_only':True,'network_audit':'NETWORK_AUDIT.json',
        'frozen_audit':'FROZEN_AUDIT.json','test_report':'FULL_SUITE.json',
        'no_sar_pixels_or_full_product_download':True,'no_commit_push':True})
    return evidence['exit_code']


if __name__=='__main__':raise SystemExit(main())

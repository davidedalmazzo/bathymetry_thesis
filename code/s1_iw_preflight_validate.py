"""Offline Block36 regression, frozen-input audit and provenance manifest."""
from __future__ import annotations
import argparse,json,os,subprocess,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
from repository_paths import ROOT,resolve_historical
from frf_client.transport import save_json,digest

BASE=ROOT/'duck_frf/Block36_s1_iw_annotation_preflight'
BASELINE=ROOT/'duck_frf/Block34_frf_operational/FROZEN_BASELINE.json'


def frozen_audit():
    mismatches=[];rows=json.loads(BASELINE.read_text())
    for row in rows:
        path=resolve_historical(row['path'])
        if not path.is_file():mismatches.append({'path':row['path'],'status':'missing'})
        elif (row.get('bytes') is not None and path.stat().st_size!=row['bytes']) or digest(path.read_bytes())!=row['sha256']:
            mismatches.append({'path':row['path'],'status':'hash_or_size_mismatch'})
    result={'baseline':BASELINE.relative_to(ROOT).as_posix(),'verified':len(rows)-len(mismatches),'mismatches':mismatches,
            'historical_files_not_rewritten':True}
    save_json(BASE/'FROZEN_AUDIT.json',result)
    if mismatches:raise ValueError('Frozen baseline mismatch')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest-only',action='store_true');a=p.parse_args(argv)
    if Path.cwd().resolve()!=ROOT:raise ValueError('Run from repository root')
    frozen_audit();env=os.environ.copy();env.update(TEMP=str(ROOT/'_tmp'),TMP=str(ROOT/'_tmp'),MPLCONFIGDIR=str(ROOT/'_cache/matplotlib'))
    if not a.manifest_only:
        temporary=ROOT/'_tmp'/('pytest_block36_'+uuid.uuid4().hex)
        cmd=[sys.executable,'-m','pytest','-q','--basetemp='+str(temporary)]
        result=subprocess.run(cmd,text=True,capture_output=True,env=env)
        save_json(BASE/'FULL_SUITE.json',{'command':cmd,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
            'timestamp_utc':datetime.now(timezone.utc).isoformat(),'offline_tests_not_live_api_proof':True,'interpreter':sys.executable})
        print(result.stdout[-2000:]);print(result.stderr[-2000:])
    evidence=json.loads((BASE/'FULL_SUITE.json').read_text())
    artifacts=[]
    for path in sorted(BASE.rglob('*')):
        if not path.is_file() or {'cache','network'} & set(path.relative_to(BASE).parts) or path.name=='MANIFEST.json':continue
        if path.stat().st_size>=100*1024**2:raise ValueError('Oversized versionable artifact: '+str(path))
        artifacts.append({'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':digest(path.read_bytes())})
    sources=[ROOT/'code/cdse_credentials.py',ROOT/'code/download_cdse_product.py',ROOT/'code/run_block36_s1_iw_preflight.py',
        ROOT/'code/s1_iw_annotation.py',ROOT/'code/s1_iw_preflight_validate.py',ROOT/'code/frf_client/transport.py',
        ROOT/'code/repository_paths.py',ROOT/'repository_paths.json',ROOT/'.env.example',ROOT/'requirements-thesis.txt',ROOT/'tests/test_s1_iw_annotation.py']
    gate=json.loads((BASE/'GATE.json').read_text())['gate'];metadata_count=len(list((BASE/'metadata_original').glob('*'))) if (BASE/'metadata_original').exists() else 0
    save_json(BASE/'MANIFEST.json',{'block':36,'created_utc':datetime.now(timezone.utc).isoformat(),'gate':gate,
        'artifacts':artifacts,'code_sources':[{'path':x.relative_to(ROOT).as_posix(),'bytes':x.stat().st_size,'sha256':digest(x.read_bytes())} for x in sources],
        'metadata_payloads_retrieved':metadata_count,'network_audit':'NETWORK_AUDIT.json','frozen_audit':'FROZEN_AUDIT.json','test_report':'FULL_SUITE.json',
        'no_sar_pixels_or_full_product_download':True,'no_commit_push':True})
    return evidence['exit_code']


if __name__=='__main__':raise SystemExit(main())

"""Explicit source delivery snapshot, offline CLI smoke and manifest checks."""
from repository_paths import resolve_historical
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from .transport import save_json,digest


def sources(root):
    files=[p.relative_to(root).as_posix() for p in (root/'code/frf_client').glob('*.py')]
    files+=['code/frf_client_cli.py','code/run_block32_frf_client.py','code/run_block30_frf_conditions.py','code/run_block33_frf_verification.py','code/run_block34_frf_operational.py',
            'tests/test_frf_client.py','tests/test_frf_block33.py','tests/test_frf_operational.py','tests/test_block30_frf_conditions.py','tests/conftest.py','requirements-thesis.txt','pytest.ini','code/README_FRF_CLIENT.md','docs/FRF_QUICKSTART.md']
    files+=[p.relative_to(root).as_posix() for p in (root/'tests/fixtures/frf_block33').glob('*')]
    files+=[p.relative_to(root).as_posix() for p in (root/'examples/frf').glob('*')]
    files += ['code/repository_paths.py', 'repository_paths.json']
    return sorted(set(files))


def verify_delivery(root,base):
    destination=base/'delivery_copy';n=1
    while destination.exists():n+=1;destination=base/f'delivery_copy_{n}'
    for name in sources(root):
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(resolve_historical(name, root),target)
    (destination/'_tmp').mkdir(parents=True,exist_ok=True)
    cmd=[sys.executable,'-m','pytest','tests/test_frf_client.py','tests/test_frf_block33.py','tests/test_frf_operational.py','tests/test_block30_frf_conditions.py','--basetemp','_tmp/tests','-q']
    result=subprocess.run(cmd,cwd=destination,capture_output=True,text=True)
    save_json(base/'ISOLATED_TESTS.json',{'command':['.venv-umbra-thesis/Scripts/python.exe',*cmd[1:]],'source_copy':destination.relative_to(root).as_posix(),'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
        'not_a_github_clone':True,'private_cache_radar_credentials':False,'actual_http_transactions':0})
    smoke=[]
    common=['--mode','offline','--config','examples/frf/client.json','--cache','_cache/frf','--output']
    scenarios=[('single',['--acquisition-id','single','--timestamp-utc','2021-10-12T11:07:16.616Z','--footprint','examples/frf/footprint.geojson']),
               ('roi',['--acquisition-id','roi','--timestamp-utc','2021-10-12T11:07:16.616Z','--footprint','examples/frf/footprint.geojson','--roi','examples/frf/roi.geojson']),
               ('batch',['--input','examples/frf/acquisitions.json']),('time_only',['--acquisition-id','time','--timestamp-utc','2021-10-12T11:07:16.616Z']),
               ('inventory',['--mode','inventory','--dry-run','--input','examples/frf/acquisitions.json'])]
    for name,args in scenarios:
        cmd=[sys.executable,'code/frf_client_cli.py',*common,'outputs/'+name,*args]
        p=subprocess.run(cmd,cwd=destination,capture_output=True,text=True)
        generated=list((destination/'outputs'/name).glob('*/ACQUISITION.json'))
        covers=[json.loads((g.parent/'SEARCH_COVERAGE.json').read_text()) for g in generated]
        smoke.append({'scenario':name,'command':['.venv-umbra-thesis/Scripts/python.exe',*cmd[1:]],'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,
            'acquisition_count':len(generated),'missing_cache_explicit':all(any(s['status']=='incomplete_search' for s in c) for c in covers),
            'actual_http_transactions':0})
    save_json(base/'CLI_SMOKE.json',smoke)
    if result.returncode or any(s['exit_code'] or not s['missing_cache_explicit'] for s in smoke):raise RuntimeError('Delivery tests/smoke failed; inspect reports')


def delivery_manifest(root,base):
    listed=sources(root)
    git=['git','-c',f'safe.directory={root.as_posix()}'];tracked=set(subprocess.check_output(git+['ls-files'],text=True).splitlines())
    modified=set(subprocess.check_output(git+['diff','--name-only','HEAD'],text=True).splitlines())
    rows=[]
    for name in listed:
        ignored=subprocess.run(git+['check-ignore','--no-index',name],capture_output=True,text=True).returncode==0
        rows.append({'path':name,'bytes':(resolve_historical(name, root)).stat().st_size,'sha256':digest((resolve_historical(name, root)).read_bytes()),'tracked':name in tracked,'modified_or_new':name not in tracked or name in modified,'gitignored':ignored})
    save_json(base/'FILES_TO_VERSION.json',{'required_sources':rows,'new_block_directory':base.relative_to(root).as_posix(),'additional_modified_docs':['README.md','WORKLOG.md','.gitignore','docs/checkpoints/CHECKPOINT_34.md'],
        'excluded':['cache/','network/','delivery_copy*/'],'no_commit_push':True})
    artifacts=[p for p in base.rglob('*') if p.is_file() and not any(x in ('cache','network') or x.startswith('delivery_copy') for x in p.parts) and p.name!='MANIFEST.json']
    extras=[root/'docs/checkpoints/CHECKPOINT_34.md',root/'README.md',root/'WORKLOG.md',root/'.gitignore']
    state=json.loads((base/'network/block34_october_2021/NETWORK_STATE.json').read_text())
    logs=[json.loads(line) for line in (base/'network/block34_october_2021/requests.jsonl').read_text().splitlines()]
    save_json(base/'NETWORK_AUDIT.json',{'state':state,'started_transactions':sum(e.get('status')=='started' for e in logs),
        'complete_response_bytes':sum(e.get('bytes',0) for e in logs),'non_response_bytes_in_streaming_counter':state['bytes']-sum(e.get('bytes',0) for e in logs),
        'timeouts_or_failures':[e for e in logs if e.get('status') not in ('started','response')],
        'within_authorized_budget':state['transactions']<=50 and state['bytes']<=104857600,
        'ledger':logs,'note':'Named tranche only; verified local reuse is not charged. Prior historical consumption not determinable, never zero.'})
    artifacts=[p for p in base.rglob('*') if p.is_file() and not any(x in ('cache','network') or x.startswith('delivery_copy') for x in p.parts) and p.name!='MANIFEST.json']
    save_json(base/'MANIFEST.json',{'named_tranche':state,'root_relative_paths':True,'artifacts':[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())} for p in sorted(set(artifacts+[resolve_historical(n, root) for n in listed]+[p for p in extras if p.exists()]))]})
    if any(row['gitignored'] for row in rows):raise RuntimeError('Required delivery sources are ignored')

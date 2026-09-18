"""Bounded FRF operational verification orchestrator; no radar/Git mutations."""
from repository_paths import resolve_historical
import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from frf_client.transport import save_json,digest
from frf_client.inputs import adapt_cleos,adapt_eoweb,validate_batch
from frf_client.provenance import audit

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'duck_frf/Block34_frf_operational'
TRANCHE='block34_october_2021'


def rel(path):return Path(path).resolve().relative_to(ROOT).as_posix()


def command(mode,output,extra=None):
    return [sys.executable,'code/frf_client_cli.py','--mode',mode,'--config',rel(BASE/'CLIENT_CONFIG.json'),
        '--budget-config',rel(BASE/'BUDGET_AUTHORIZED.json'),'--input',rel(BASE/'ACQUISITIONS.json'),
        '--cache',rel(BASE/'cache'),'--output',rel(output),*(extra or [])]


def execute(name,cmd):
    result=subprocess.run(cmd,capture_output=True,text=True)
    save_json(BASE/(name+'.json'),{'command':[str(Path(c).relative_to(ROOT)) if Path(c).is_absolute() and Path(c).is_relative_to(ROOT) else c for c in cmd],
                                 'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    print(result.stdout);print(result.stderr,file=sys.stderr);return result.returncode


def prepare():
    eoweb=ROOT/'duck_frf/Block31_tsx_duck_query/eoweb_export/resultTableExport_1789663304925.csv'
    cleos=ROOT/'duck_frf/Block30_duck_csk_preflight/cleos_export/results_COSMO-SkyMed_20190911_20260916.json'
    records=adapt_eoweb(eoweb,[12,11])+adapt_cleos(cleos,['2098202'])
    for r in records:
        r['source']=rel(eoweb if r['acquisition_id'].startswith(('TSX','TDX')) else cleos)
        if r['acquisition_id']=='COSMO_2098202':
            r['timestamp_utc']='2021-10-13T22:45:03+00:00'
            r['timestamp_semantics']='requested_catalogue_timestamp_at_second_precision_not_verified_aperture_center'
    records,warnings=validate_batch(records)
    records.sort(key=lambda r:r['timestamp_utc'])
    save_json(BASE/'ACQUISITIONS.json',{'acquisitions':records})
    save_json(BASE/'INPUT_PROVENANCE.json',{'original_exports':[{'path':rel(p),'sha256':digest(p.read_bytes())} for p in (eoweb,cleos)],'input_warnings':warnings,'roi':'none supplied; not invented'})
    for r in records:save_json(BASE/(r['acquisition_id']+'_footprint.geojson'),r['footprint'])
    frozen=[]
    for name in ('duck_frf/Block32_frf_client','duck_frf/Block33_frf_offline_correction'):
        for p in (resolve_historical(name, ROOT)).rglob('*'):
            if p.is_file() and not any(part.startswith('clean_tree') for part in p.parts):frozen.append({'path':rel(p),'sha256':digest(p.read_bytes()),'bytes':p.stat().st_size})
    frozen.append({'path':'docs/checkpoints/CHECKPOINT_32.md','sha256':digest((ROOT/'docs/checkpoints/CHECKPOINT_32.md').read_bytes())})
    frozen.append({'path':'docs/checkpoints/CHECKPOINT_33.md','sha256':digest((ROOT/'docs/checkpoints/CHECKPOINT_33.md').read_bytes())})
    save_json(BASE/'FROZEN_BASELINE.json',frozen)
    status=subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}','status','--short'],text=True)
    save_json(BASE/'INITIAL_GIT.json',{'status':status,'note':'Block33 local changes retained; no assumption of publication, no commit/push'})


def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['prepare','dry','live','resume','offline','compare','verify','delivery','surveys','cache-check','refresh']);args=ap.parse_args()
    if Path.cwd().resolve()!=ROOT:raise ValueError('Repository root required')
    os.environ.update(TEMP=str(ROOT/'_tmp'),TMP=str(ROOT/'_tmp'),MPLCONFIGDIR=str(ROOT/'_cache/matplotlib'))
    if args.phase=='prepare':prepare();return 0
    if args.phase=='dry':return execute('DRY_RUN',command('offline',BASE/'dry_run',['--dry-run','--reuse-cache','duck_frf/Block32_frf_client/cache']))
    if args.phase in ('live','resume'):
        extra=['--tranche',TRANCHE,'--tranche-root',rel(BASE/'network')]
        if args.phase=='live':extra+=['--new-tranche']
        return execute('LIVE_RUN' if args.phase=='live' else 'RESUMED_RUN',command('fetch',BASE/'results',extra))
    if args.phase=='offline':return execute('OFFLINE_REUSE',command('offline',BASE/'offline_reuse',['--tranche',TRANCHE,'--tranche-root',rel(BASE/'network')]))
    if args.phase=='cache-check':
        previous=BASE/'CACHE_REUSE_COMPARISON.json';initial=BASE/'CACHE_REUSE_COMPARISON_INITIAL.json'
        if previous.exists() and not initial.exists():
            save_json(initial,json.loads(previous.read_text()))
        comparisons=[]
        records=json.loads((BASE/'ACQUISITIONS.json').read_text())['acquisitions']
        for r in records:
            identifier=r['acquisition_id'];before=BASE/'results'/identifier;after=BASE/'offline_reuse'/identifier
            items=[]
            for name in ('OBSERVATIONS.csv','DISTANCES.csv','TENSORS.json','SPECTRAL_SUMMARIES.json','SEARCH_COVERAGE.json'):
                if name.endswith('.csv'):
                    old=list(csv.DictReader((before/name).open(encoding='utf-8')));new=list(csv.DictReader((after/name).open(encoding='utf-8')))
                else:old=json.loads((before/name).read_text());new=json.loads((after/name).read_text())
                # Processing-code provenance changes are not original observation changes.
                if name=='TENSORS.json':
                    old={k:v['variables'] for k,v in old.items()};new={k:v['variables'] for k,v in new.items()}
                items.append({'file':name,'numerical_semantic_equal':old==new,'before_sha256':digest((before/name).read_bytes()),'after_sha256':digest((after/name).read_bytes())})
            comparisons.append({'acquisition_id':identifier,'comparisons':items})
        save_json(BASE/'CACHE_REUSE_COMPARISON.json',{'cases':comparisons,'offline_run_state':json.loads((BASE/'offline_reuse/RUN_STATE.json').read_text()),'actual_http_transactions':0})
        return int(any(not i['numerical_semantic_equal'] for c in comparisons for i in c['comparisons']))
    if args.phase=='refresh':return execute('FINAL_CACHED_REFRESH',command('offline',BASE/'results',['--tranche',TRANCHE,'--tranche-root',rel(BASE/'network')]))
    if args.phase=='surveys':
        from frf_client.transport import Transport
        from frf_client.survey import fetch_points
        from frf_client.geometry import polygon
        from shapely.ops import unary_union
        from shapely.geometry import mapping
        from frf_client.transport import FetchError
        records=json.loads((BASE/'ACQUISITIONS.json').read_text())['acquisitions']
        region=mapping(unary_union([polygon(r['footprint']) for r in records]))
        budget=json.loads((BASE/'BUDGET_AUTHORIZED.json').read_text())
        transport=Transport(BASE/'cache',tranche_directory=BASE/'network'/TRANCHE,tranche_name=TRANCHE,**{k:budget[k] for k in ('max_requests','max_bytes','max_response')})
        inventory=json.loads((BASE/'results/INVENTORY.json').read_text());results=[]
        for item in inventory:
            if item.get('status')!='nearby_candidate_metadata_verified':continue
            meta=item['metadata'];shapes=meta['shapes'];attrs=meta['attributes']
            if not all(name in shapes for name in ('lat','lon','elevation')):continue
            if not (shapes['lat']==shapes['lon']==shapes['elevation'] and len(shapes['lat'])==1):continue
            if attrs.get('lat',{}).get('units') not in ('degrees_north','degree_north') or attrs.get('lon',{}).get('units') not in ('degrees_east','degree_east'):
                results.append({'product':item['survey_reference'],'status':'unsupported_unverified_geographic_units'});continue
            selection=[0,min(shapes['lat'][0],3000)-1]
            try:
                subset=fetch_points(transport,item['survey_reference'],selection,region)
                results.append({'product':item['survey_reference'],'status':'bounded_supported_point_subset','subset':subset,
                    'selection_caveat':'First declared 3000 indices only, no complete/optimal coverage claim; retained only inside union of real catalogue footprints.'})
            except (FetchError,ValueError) as exc:results.append({'product':item['survey_reference'],'status':getattr(exc,'status','unsupported_subset')})
        save_json(BASE/'SURVEY_SUBSETS.json',{'region_source':'union of three original catalogue footprints, not an invented ROI','results':results,'network_state':transport.state})
        print(json.dumps(transport.state));return 0
    if args.phase=='compare':
        from frf_client.comparison import compare
        compare(json.loads((BASE/'ACQUISITIONS.json').read_text())['acquisitions'],BASE/'results',BASE/'comparison');return 0
    if args.phase=='verify':
        rc=execute('FULL_SUITE',[sys.executable,'-m','pytest','-q'])
        from frf_client.delivery import verify_delivery
        verify_delivery(ROOT,BASE);return rc
    frozen=audit(json.loads((BASE/'FROZEN_BASELINE.json').read_text()),ROOT)
    save_json(BASE/'FROZEN_AUDIT.json',{'entries':frozen,'statuses':{s:sum(r['status']==s for r in frozen) for s in ('hash_verified','mismatch','file_unavailable','unresolved_path')}})
    from frf_client.delivery import delivery_manifest
    delivery_manifest(ROOT,BASE)
    return int(any(r['status']!='hash_verified' for r in frozen))


if __name__=='__main__':raise SystemExit(main())

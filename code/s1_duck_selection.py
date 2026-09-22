"""Stable CDSE catalogue and FRF spatial-validation screening, no SAR pixels."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlencode
from shapely.geometry import shape
from repository_paths import ROOT
from frf_client.transport import Transport, save_json, FetchError
from frf_client.output import table
from s1_spatial import normalize, representatives, next_page, catalogue_pages, deduplicate_entries, quicklook_url

BASE = ROOT / 'duck_frf/Block35_s1_spatial_selection'
ODATA = 'https://catalogue.dataspace.copernicus.eu/odata/v1/Products'
DOC = 'https://documentation.dataspace.copernicus.eu/APIs/OData.html'
HOSTS = ('catalogue.dataspace.copernicus.eu','documentation.dataspace.copernicus.eu',
         'chldata.erdc.dren.mil','download.dataspace.copernicus.eu')


def transport(offline=False, new=False):
    cfg = json.loads((BASE / 'CONFIG.json').read_text())
    return Transport(BASE / 'cache', offline=offline, hosts=HOSTS, timeout=cfg['timeout_seconds'],
        retries=cfg['retries'], max_requests=cfg['max_requests'], max_bytes=cfg['max_bytes'],
        max_response=cfg['max_response'], tranche_name=cfg['tranche'],
        tranche_directory=BASE / 'network' / cfg['tranche'], new_tranche=new)


def catalogue_url(cfg):
    polygon = shape(cfg['aoi']).wkt
    filters = ("Collection/Name eq 'SENTINEL-1' and contains(Name,'_IW_SLC_') and "
               f"ContentDate/Start ge {cfg['start_utc']} and ContentDate/Start lt {cfg['end_exclusive_utc']} and "
               f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}')")
    return ODATA + '?' + urlencode({'$filter':filters,'$expand':'Attributes','$top':cfg['page_size'],
                                   '$orderby':'ContentDate/Start asc','$count':'true'})


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('phase', choices=('init','probe','catalogue','frf-a','frf-b','frf-refined','surveys','metadata','inspect','compare','deliver'))
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--retry-transport', action='store_true', help='Retry a previously failed probe only after diagnosed transport change')
    args=ap.parse_args(argv)
    if Path.cwd().resolve()!=ROOT:ap.error('Run from actual Git repository root')
    actual=Path(subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}','rev-parse','--show-toplevel'],text=True).strip()).resolve()
    if actual!=ROOT:ap.error('Git root does not match source-derived root')
    os.environ.update(TEMP=str(ROOT/'_tmp'),TMP=str(ROOT/'_tmp'),MPLCONFIGDIR=str(ROOT/'_cache/matplotlib'))
    if args.phase=='init':
        t=transport(new=True)
        imported=[]
        for path in ('duck_frf/Block32_frf_client/cache','duck_frf/Block33_frf_offline_correction/cache','duck_frf/Block34_frf_operational/cache'):
            imported.extend(t.import_verified(ROOT/path))
        t.import_legacy(ROOT/'duck_frf/Block30_duck_csk_preflight/http_cache')
        save_json(BASE/'CACHE_IMPORT.json',imported)
        return 0
    t=transport(offline=args.offline)
    cfg=json.loads((BASE/'CONFIG.json').read_text())
    if args.phase=='probe':
        url=catalogue_url({**cfg,'page_size':1})
        if args.retry_transport:
            _,meta=t._paths(url)
            previous=json.loads(meta.read_text()) if meta.exists() else {}
            if previous.get('status')!='transport_error':ap.error('No diagnosed transport failure to retry')
            save_json(BASE/'TRANSPORT_DIAGNOSTIC.json',{'previous_status':'transport_error',
                'cause':'sandbox process proxy points to loopback port 9; approved direct public route requested',
                'tls_verification':True,'no_access_control_bypass':True,'historical_failure_in_ledger':True})
            previous['expires']=0;save_json(meta,previous)
        raw=t.get(url)
        save_json(BASE/'CATALOGUE_PROBE.json',json.loads(raw))
        t.get(DOC)
        print(json.dumps(t.state));return 0
    if args.phase=='catalogue':
        entries=[]; pages=[]; visited=set(); url=catalogue_url(cfg); error=None
        try:
            for record in catalogue_pages(t,url):
                page=record['payload'];pages.append(record)
                save_json(BASE/'CATALOGUE_PAGES.json',pages)
                entries.extend(page['value'])
        except (FetchError,ValueError) as exc:
            error=str(exc)
        try:unique,duplicates=deduplicate_entries(entries)
        except ValueError as exc:unique=[];duplicates=[];error=str(exc)
        rows=[normalize(e,cfg['marine_screening_area']) for e in unique]
        save_json(BASE/'INVENTORY.json',rows)
        table(BASE/'INVENTORY.csv',[{k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows])
        save_json(BASE/'CATALOGUE_STATUS.json',{'complete':error is None,'error':error,'pages':len(pages),
            'reported_count':pages[0]['payload'].get('@odata.count') if pages else None,
            'unique_products':len(rows),'physical_acquisitions':len(representatives(rows)),'duplicates':duplicates})
        return 1 if error else 0
    if args.phase in ('frf-a','frf-b','frf-refined'):
        from frf_client.client import Client, VARIABLES
        inventory=json.loads((BASE/'INVENTORY.json').read_text())
        chosen=representatives(inventory) if args.phase=='frf-a' else json.loads((BASE/'FINALISTS.json').read_text())
        acquisitions=[{'acquisition_id':r['uuid'],'timestamp_utc':r['start_utc'],'footprint':r['footprint'],
            'timestamp_semantics':r['timestamp_semantics']} for r in chosen]
        client_cfg=json.loads((ROOT/'duck_frf/Block34_frf_operational/CLIENT_CONFIG.json').read_text())
        client_cfg.update(wave_instruments=['waverider-17m','awac-11m'],spectral_instruments=['waverider-17m','awac-11m'],
            event_context_seconds=1800,max_survey_metadata_products=1,compact_survey_inventory=True)
        if args.phase=='frf-a':
            excluded={'waveFrequency','waveDirectionBins','waveEnergyDensity','directionalWaveEnergyDensity',
                'waveA1Value','waveB1Value','waveA2Value','waveB2Value','waveFrequencyBandwidth','frequencyBounds'}
            client_cfg.update(families=['waves'],spectral_instruments=[],monthly_scalar_subset=True,max_event_samples=4000,
                observation_variables={'waves':[v for v in VARIABLES['waves'] if v not in excluded]})
        if args.phase=='frf-refined':
            client_cfg.update(families=['waves'],observation_variables={'waves':
                [v for v in VARIABLES['waves'] if v not in ('directionalWaveEnergyDensity','waveDirectionBins')]})
            save_json(BASE/'REFINED_REASON.json',{'cause':'waverider 3D directional ASCII request timed out',
                'new_information':'smaller projection preserves native energy spectrum and four directional moments; no repeat of failed URL',
                'original_attempt_preserved':'frf-b/STATUS.json; persistent network ledger',
                'currents':'timed-out attempt not repeated; missing is an uncertainty'})
        save_json(BASE/(args.phase.upper()+'_CONFIG.json'),client_cfg)
        save_json(BASE/(args.phase.upper()+'_ACQUISITIONS.json'),acquisitions)
        status=BASE/args.phase/'STATUS.json'
        if status.exists() and not (BASE/(args.phase.upper()+'_INITIAL_STATUS.json')).exists():
            save_json(BASE/(args.phase.upper()+'_INITIAL_STATUS.json'),json.loads(status.read_text()))
        Client(t,client_cfg).run(acquisitions,BASE/args.phase,mode='offline' if args.offline else 'fetch')
        print(json.dumps(t.state));return 0
    if args.phase=='compare':
        from s1_spatial_compare import compare
        compare('frf-b' if (BASE/'frf-b/STATUS.json').exists() else 'frf-a')
        return 0
    if args.phase=='metadata':
        rows=json.loads((BASE/'FINALISTS.json').read_text());results=[];node_blocked=False
        for row in rows:
            result={'uuid':row['uuid'],'full_product_not_requested':True}
            try:
                detail=json.loads(t.get(ODATA+'('+row['uuid']+')?'+urlencode({'$expand':'Assets'})))
                save_json(BASE/'asset_metadata'/(row['uuid']+'.json'),detail)
                result['assets']=detail.get('Assets',[])
            except (FetchError,ValueError) as exc:
                result['asset_error']=str(exc)
                result['asset_error_code']=getattr(exc,'code',None)
            if not node_blocked:
                try:
                    nodes=json.loads(t.get('https://download.dataspace.copernicus.eu/odata/v1/Products('+row['uuid']+')/Nodes'))
                    save_json(BASE/'nodes'/(row['uuid']+'.json'),nodes)
                    result['nodes']=nodes
                except (FetchError,ValueError) as exc:
                    result['node_error']=str(exc)
                    if getattr(exc,'code',None) in (401,403):node_blocked=True
            else:result['node_error']='same protected endpoint: not retried after authorization failure'
            results.append(result);save_json(BASE/'ASSET_STATUS.json',results)
        return 0
    if args.phase=='surveys':
        from frf_client.survey import fetch_complete_points
        entries=json.loads((BASE/'frf-b/INVENTORY.json').read_text())
        surveys=[e for e in entries if e.get('status')=='nearby_candidate_metadata_verified']
        summary=[]
        for entry in surveys:
            product=entry['survey_reference']; source=product['services']['OpenDAP']
            try:
                points=fetch_complete_points(t,product,cfg['aoi'])
                save_json(BASE/'surveys'/(product['name']+'.json'),points)
                summary.append({'source':source,'file':product['name']+'.json',
                    'all_indices_traversed':True,'inside_points':len(points['points']),
                    'source_points':points['source_point_count'],'datum':points['vertical_datum']})
            except (FetchError,ValueError) as exc:summary.append({'source':source,'error':str(exc)})
            save_json(BASE/'SURVEY_STATUS.json',summary)
        return 0
    if args.phase=='inspect':
        assets=json.loads((BASE/'ASSET_STATUS.json').read_text());results=[];content_blocked=False
        # Predeclared first two evidence candidates, not a new API search.
        for entry in assets[:2]:
            row={'uuid':entry['uuid'],'credentials_configured':bool(os.environ.get('CDSE_ACCESS_TOKEN')),
                 'protected_content_not_bypassed':True}
            for asset in entry.get('assets',[]):
                if asset.get('Type')=='QUICKLOOK':
                    try:
                        raw=t.get(quicklook_url(asset))
                        from PIL import Image
                        import io
                        img=Image.open(io.BytesIO(raw));img.verify()
                        extension='jpg' if raw.startswith(b'\xff\xd8') else 'png'
                        path=BASE/'previews'/(entry['uuid']+'.'+extension);path.parent.mkdir(exist_ok=True)
                        path.write_bytes(raw)
                        row['preview']={'source':asset['DownloadLink'],'file':str(path.relative_to(BASE)),
                                        'bytes':len(raw),'interpretation':'compressed auxiliary only; no k or recoverability measurement'}
                    except (FetchError,ValueError,OSError) as exc:row['preview_error']=str(exc)
            try:
                safe=entry['nodes']['result'][0]
                tree=json.loads(t.get(safe['Nodes']['uri']));save_json(BASE/'nodes'/(entry['uuid']+'_safe.json'),tree)
                annotation=next((n for n in tree.get('result',[]) if n['Name']=='annotation'),None)
                if annotation:
                    listing=json.loads(t.get(annotation['Nodes']['uri']))
                    save_json(BASE/'nodes'/(entry['uuid']+'_annotations.json'),listing)
                    row['annotations']=listing
                    if not content_blocked:
                        vv=next((n for n in listing['result'] if n['Name'].endswith('.xml') and '-vv-' in n['Name']),None)
                        if vv:
                            # No measurement node; only an annotation XML bounded by transport.
                            url=annotation['Nodes']['uri'].removesuffix('/Nodes')+'/Nodes('+vv['Name']+')/$value'
                            try:
                                raw=t.get(url)
                                from lxml import etree
                                etree.fromstring(raw,etree.XMLParser(resolve_entities=False,no_network=True))
                                path=BASE/'annotations'/vv['Name'];path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
                                row['annotation_xml_file']=str(path.relative_to(BASE))
                            except FetchError as exc:
                                row['annotation_content_error']={'status':exc.status,'code':exc.code,'url':url}
                                if exc.code in (401,403):content_blocked=True
                    else:row['annotation_content_error']='content endpoint protected: not retried without credentials'
            except (FetchError,ValueError,KeyError) as exc:row['nodes_error']=str(exc)
            results.append(row);save_json(BASE/'INSPECTION.json',results)
        return 0
    if args.phase=='deliver':
        from s1_spatial_delivery import main as deliver
        deliver();return 0
    raise NotImplementedError(args.phase)


if __name__=='__main__':raise SystemExit(main())

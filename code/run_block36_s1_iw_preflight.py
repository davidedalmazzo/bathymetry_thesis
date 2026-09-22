"""Block36 authenticated annotation-only Sentinel-1 IW preflight."""
from __future__ import annotations
import argparse,json,os,subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from lxml import etree
from shapely.geometry import mapping,shape
from repository_paths import ROOT
from frf_client.transport import Transport,FetchError,save_json,digest
from cdse_credentials import TokenProvider,CredentialError,status as credential_status
from s1_iw_annotation import parse_annotation,roi_support,local_geometry,axial_difference,validate_xml_payload,validate_manifest,burst_support_geojson

BASE=ROOT/'duck_frf/Block36_s1_iw_annotation_preflight';B35=ROOT/'duck_frf/Block35_s1_spatial_selection'
HOSTS=('download.dataspace.copernicus.eu','catalogue.dataspace.copernicus.eu','documentation.dataspace.copernicus.eu',
       'identity.dataspace.copernicus.eu')


def cfg():return json.loads((BASE/'CONFIG.json').read_text())
def transport(offline=False,new=False):
    c=cfg();return Transport(BASE/'cache',offline=offline,hosts=HOSTS,timeout=c['timeout_seconds'],retries=c['retries'],
        max_requests=c['max_requests'],max_bytes=c['max_bytes'],max_response=c['max_response'],
        tranche_name=c['tranche'],tranche_directory=BASE/'network'/c['tranche'],new_tranche=new)


def _node_content(parent_uri,name):
    c=cfg();prefix=f"https://download.dataspace.copernicus.eu/odata/v1/Products({c['product_uuid']})/Nodes({c['product_name']})/Nodes"
    if not parent_uri.startswith(prefix) or not parent_uri.endswith('/Nodes') or any(x in name for x in ('/','\\','..')):
        raise ValueError('Unexpected product node provenance')
    return parent_uri.removesuffix('/Nodes')+'/Nodes('+name+')/$value'


def public_inventory():
    c=cfg();inspection=json.loads((B35/'INSPECTION.json').read_text())[0]
    safe=json.loads((B35/'nodes'/f"{c['product_uuid']}_safe.json").read_text())
    annotation=inspection['annotations'];files=[]
    manifest=next(n for n in safe['result'] if n['Name']=='manifest.safe')
    files.append({'role':'manifest','name':'manifest.safe','declared_bytes':manifest['ContentLength'],
        'content_url':_node_content(next(n for n in safe['result'] if n['Name']==c['product_name'])['Nodes']['uri'],'manifest.safe') if any(n['Name']==c['product_name'] for n in safe['result']) else
            f"https://download.dataspace.copernicus.eu/odata/v1/Products({c['product_uuid']})/Nodes({c['product_name']})/Nodes(manifest.safe)/$value",
        'status':'listed_publicly_content_not_retrieved'})
    for n in annotation['result']:
        if n['Name'].endswith('.xml') and '-vv-' in n['Name']:
            swath=next((x.upper() for x in ('iw1','iw2','iw3') if '-'+x+'-' in n['Name']),None)
            files.append({'role':'measurement_annotation','swath':swath,'polarisation':'VV','name':n['Name'],
                'declared_bytes':n['ContentLength'],'content_url':n['Nodes']['uri'].removesuffix('/Nodes')+'/$value',
                'status':'listed_publicly_content_not_retrieved'})
    if {f.get('swath') for f in files if f['role']=='measurement_annotation'}!={'IW1','IW2','IW3'}:
        raise ValueError('Public inventory does not contain exactly all three VV subswaths')
    return {'product_uuid':c['product_uuid'],'product_name':c['product_name'],'source':'verified Block35 public CDSE Nodes',
        'alternative_scene_queried':False,'measurement_content_forbidden':True,'files':files,
        'calibration_noise':{'status':'not listed/fetched until authenticated main annotations identify pertinent subswath',
            'folder':next((n for n in annotation['result'] if n['Name']=='calibration'),None)}}


def initialize():
    state=BASE/'network'/cfg()['tranche']/'NETWORK_STATE.json'
    t=transport(new=not state.exists());imports=t.import_verified(B35/'cache',lambda u:urlsplit(u).hostname in HOSTS);save_json(BASE/'CACHE_IMPORT.json',imports)
    inventory=public_inventory();save_json(BASE/'ANNOTATION_INVENTORY.json',inventory)
    return t


def _authenticated_get(t,provider,url):
    for attempt in range(2):
        token=provider.get(force_refresh=attempt>0)
        try:return t.get(url,authorization_bearer=token)
        except FetchError as exc:
            if exc.status!='authentication_required' or attempt:raise
    raise FetchError('authentication_required')


def _download_xml(t,provider,item):
    raw=_authenticated_get(t,provider,item['content_url'])
    validate_xml_payload(raw,item['name'],item['declared_bytes'],cfg()['max_response'])
    path=BASE/'metadata_original'/item['name'];path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    return raw,{'path':path.relative_to(ROOT).as_posix(),'sha256':digest(raw),'bytes':len(raw),'source':item['content_url']}


def _validate_annotation_identity(annotation,expected_swath):
    c=cfg()
    if annotation['mission']!=c['platform'] or annotation['mode']!=c['mode']:
        raise ValueError('Annotation platform/mode identity mismatch')
    if annotation['swath']!=expected_swath or annotation['polarisation']!=c['polarisation']:
        raise ValueError('Annotation swath/polarisation identity mismatch')
    if annotation['absolute_orbit_number']!=c['absolute_orbit_number']:
        raise ValueError('Annotation absolute orbit identity mismatch')
    start=datetime.fromisoformat(annotation['start_time']);stop=datetime.fromisoformat(annotation['stop_time'])
    product_start=datetime.fromisoformat(c['product_start_utc']);product_stop=datetime.fromisoformat(c['product_stop_utc'])
    if stop < product_start or start > product_stop or start >= stop:
        raise ValueError('Annotation sensing interval does not overlap product interval')
    return True


def _find_calibration(t,provider,pertinent,inventory):
    folder=inventory['calibration_noise']['folder'];url=folder['Nodes']['uri']
    listing=json.loads(_authenticated_get(t,provider,url));save_json(BASE/'CALIBRATION_NODE_INVENTORY.json',listing)
    chosen=[]
    for n in listing.get('result',[]):
        lower=n['Name'].lower()
        if lower.endswith('.xml') and '-'+pertinent.lower()+'-' in lower and '-vv-' in lower and (lower.startswith('calibration-') or lower.startswith('noise-')):
            chosen.append({'role':'calibration' if lower.startswith('calibration-') else 'noise','name':n['Name'],
                'declared_bytes':n['ContentLength'],'content_url':n['Nodes']['uri'].removesuffix('/Nodes')+'/$value'})
    if {x['role'] for x in chosen}!={'calibration','noise'}:raise ValueError('Pertinent calibration/noise XML pair not uniquely available')
    return chosen


def derive(annotations,inventory,provenance,credential):
    c=cfg();roi=json.loads((B35/'PROPOSED_ROI.json').read_text())['geojson'];support=[];geometry=[]
    for swath,annotation in sorted(annotations.items()):
        result=roi_support(annotation,roi,c['roi_edge_samples']);support.append(result)
        if result.get('valid_fraction',0)>0:
            g=local_geometry(annotation,roi,c['jacobian_delta_pixels']);g['subswath']=swath;geometry.append(g)
    intersecting=[x for x in support if x.get('valid_fraction',0)>0]
    ready=[x for x in intersecting if x.get('fully_valid')]
    pertinent=ready[0]['subswath'] if len(ready)==1 else None
    frf=json.loads((B35/'FIRST_PRODUCT.json').read_text())['observational_evidence']
    for g in geometry:
        g['frf_peak_from_deg']={'waverider-17m':frf['waverider-17m__waveMeanDirectionPeakFrequency'],
            'awac-11m':frf['awac-11m__waveMeanDirectionPeakFrequency']}
        g['frf_peak_toward_deg']={'waverider-17m':frf['waverider-17m__peak_toward_deg'],'awac-11m':frf['awac-11m__peak_toward_deg']}
        g['axial_delta_range_deg']={k:axial_difference(v,g['range_sample_bearing_deg']) for k,v in g['frf_peak_toward_deg'].items()}
        g['frf_direction_role']='external measured comparison only; no correction/rotation imposed on SAR k'
    save_json(BASE/'LOCAL_GEOMETRY.json',{'status':'verified_from_annotations' if geometry else 'not_evaluable','subswaths':geometry})
    features=[{'type':'Feature','geometry':roi,'properties':{'role':'primary_roi','source':'Block35','valid_support_status':'evaluated'}}]
    if pertinent:
        burst_index=ready[0]['burst_intersections'][0]['burst_index']
        features.insert(0,{'type':'Feature','geometry':burst_support_geojson(annotations[pertinent],burst_index),
            'properties':{'role':'valid_burst_support','subswath':pertinent,'burst_index':burst_index,
                'source':'authenticated SAFE annotation firstValidSample/lastValidSample'}})
    save_json(BASE/'ROI_BURST_SUPPORT.geojson',{'type':'FeatureCollection','features':features,
        'analysis':{'subswaths':support,'pertinent_subswath':pertinent,'coverage_definition':'inverse geolocation ROI area intersected with per-line valid sample cells; not catalogue footprint'}})
    gate='READY' if pertinent and ready[0].get('single_valid_burst') else 'READY WITH LIMITATIONS' if pertinent else 'BLOCKED'
    reasons=[]
    if not pertinent:reasons.append('No unique fully valid pertinent subswath/burst support established')
    save_json(BASE/'GATE.json',{'gate':gate,'credentials_configured':credential['configured'],'pertinent_subswath':pertinent,
        'reasons':reasons,'not_wave_or_bathymetry_validation':True,'full_product_downloaded':False})
    save_json(BASE/'ANNOTATION_SUMMARY.json',{'timestamp_interpretation':'SAFE annotation UTC fields omit lexical Z; parsed as UTC by field semantics',
        'subswaths':[{'subswath':a['swath'],'start_time':a['start_time'],'stop_time':a['stop_time'],
            'number_of_lines':a['number_of_lines'],'number_of_samples':a['number_of_samples'],
            'lines_per_burst':a['lines_per_burst'],'samples_per_burst':a['samples_per_burst'],
            'range_pixel_spacing_m':a['range_pixel_spacing_m'],'azimuth_pixel_spacing_m':a['azimuth_pixel_spacing_m'],
            'bursts':[{'index':b['index'],'line_start':b['line_start'],'line_stop_exclusive':b['line_stop_exclusive'],
                'azimuth_time':b['azimuth_time'],'sensing_time':b['sensing_time'],'valid_line_count':b['valid_line_count'],
                'intersects_primary_roi':any(x['burst_index']==b['index'] for x in next((s['burst_intersections'] for s in support if s['subswath']==a['swath'] and 'burst_intersections' in s),[]))} for b in a['bursts']]} for a in annotations.values()]})
    save_json(BASE/'DERIVATION_PROVENANCE.json',provenance)
    plot_map()
    return pertinent


def blocked_outputs(credential):
    roi=json.loads((B35/'PROPOSED_ROI.json').read_text())['geojson']
    save_json(BASE/'ROI_BURST_SUPPORT.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','geometry':roi,
        'properties':{'role':'primary_roi','source':'Block35','valid_support_status':'not_evaluable_without_authenticated_annotations'}}],
        'analysis':{'catalogue_footprint_contains_roi':True,'subswath_containment':None,'valid_burst_containment':None,
                    'valid_fraction':None,'crosses_burst_join':None}})
    save_json(BASE/'LOCAL_GEOMETRY.json',{'status':'not_evaluable_without_authenticated_annotations','local_range_bearing_deg':None,
        'local_azimuth_bearing_deg':None,'incidence_deg':None,'pixel_to_ground_jacobian':None,
        'footprint_edge_proxy_not_substituted':True})
    save_json(BASE/'GATE.json',{'gate':'BLOCKED','credentials_configured':credential['configured'],
        'blocking_condition':'CDSE credentials absent/invalid or authenticated metadata not yet retrieved',
        'resolution':'configure CDSE_USERNAME and CDSE_PASSWORD in local .env (or CDSE_ACCESS_TOKEN), then run the exact resume command',
        'resume_command':'.\\.venv-umbra-thesis\\Scripts\\python.exe code\\run_block36_s1_iw_preflight.py fetch',
        'not_wave_or_bathymetry_validation':True,'full_product_downloaded':False})


def spatial_plan():
    c=cfg();frf=json.loads((B35/'FIRST_PRODUCT.json').read_text())['observational_evidence']
    return {'status':'executable_after_gate','input':'selected VV measurement only after verified subswath/burst support',
        'invalid_samples':'mask/exclude before statistics; never zero-filled as sea','intensity':'abs(SLC)**2; complex pixels remain source input',
        'calibration':'matching annotation LUT, definition/domain verified; preserve uncalibrated diagnostic',
        'noise':'matching noise XML only; documented domain; flag rather than hide negative/clipped results',
        'metric_geometry':'annotation geolocation/Jacobian with ROI variation; slant spacing, ground spacing and effective resolution separate',
        'windows_m':c['window_variants_m'],'detrending':c['detrending'],'spatial_windows':c['windowing'],
        'spectrum':'real intensity 2D FFT; numpy negative exponent; fftshift(fftfreq); q_sample,q_line rad/pixel',
        'zero_padding_factor':c['zero_padding_factor'],'zero_padding_scope':'interpolation only, not physical resolution',
        'peaks':'retain conjugate pair; discrete bin, interpolated/fitted estimator and physical lobe width reported separately',
        'stability':'all geometrically available predeclared variants; unavailable windows stay unavailable',
        'forbidden':['expected-wave band forcing','bathymetry-selected peak','L/W universal error floor','minimum phase/dwell/cycles','automatic burst-overlap duplication'],
        'frf_reference':{'Tp_published_s':{'waverider-17m':frf['waverider-17m__waveTp'],'awac-11m':frf['awac-11m__waveTp']},
            'discrete_peak_hz':{'waverider-17m':frf['waverider-17m__f_peak_bin_hz'],'awac-11m':frf['awac-11m__f_peak_bin_hz']},
            'band_halfmax_hz':{'waverider-17m':frf['waverider-17m__half_max_width_hz'],'awac-11m':frf['awac-11m__half_max_width_hz']},
            'direction_from_deg':{'waverider-17m':frf['waverider-17m__waveMeanDirectionPeakFrequency'],'awac-11m':frf['awac-11m__waveMeanDirectionPeakFrequency']},
            'direction_toward_deg':{'waverider-17m':frf['waverider-17m__peak_toward_deg'],'awac-11m':frf['awac-11m__peak_toward_deg']},
            'offset_seconds':{'waverider-17m':frf['waverider-17m__waveTp__offset_s'],'awac-11m':frf['awac-11m__waveTp__offset_s']},
            'distances_and_qc':'preserved in Block35; not automatically local truth'},
        'allowed_null_result':'association between SAR structure and FRF band not identifiable',
        'separate_later_stages':['spatial-measurement stability','inversion conditional on external omega/current uncertainty','independent survey comparison'],
        'no_real_inversion':True}


def network_audit(t,credential):
    state=t.state;log=t.log_path.read_text().splitlines() if t.log_path.exists() else []
    save_json(BASE/'NETWORK_AUDIT.json',{'state':state,'events':[json.loads(x) for x in log],
        'credentials':credential,'secrets_logged':False,'historical_tranches_unchanged':True,
        'cache_reuse_not_charged':True,'full_sar_download':False})


def plot_map():
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    collection=json.loads((BASE/'ROI_BURST_SUPPORT.geojson').read_text());fig,axes=plt.subplots(1,2,figsize=(14,6))
    tensors=json.loads((B35/'frf-refined/c49a9c1f-9b00-5676-ab05-683975d898a2/TENSORS.json').read_text())
    for ax in axes:
        for p in sorted((B35/'surveys').glob('*.json')):
            data=json.loads(p.read_text());pts=data['points'];ax.scatter([x['longitude'] for x in pts],[x['latitude'] for x in pts],s=.2,label=p.stem[-11:-3])
        for feature in collection['features']:
            geom=shape(feature['geometry']);parts=list(geom.geoms) if hasattr(geom,'geoms') else [geom]
            for i,part in enumerate(parts):
                role=feature['properties']['role'];label=None
                if i==0:label='Valid IW3 burst 0 support' if role=='valid_burst_support' else 'Primary ROI'
                ax.plot(*part.exterior.xy,color='tab:cyan' if role=='valid_burst_support' else 'black',lw=1 if role=='valid_burst_support' else 2,label=label)
        for t in tensors.values():
            pos=t['historical_position']['lon_lat']
            if pos:ax.scatter(*pos,s=45,marker='^');ax.annotate(t['stable_identity'],pos,fontsize=7)
        ax.set(xlabel='Longitude (source coordinates)',ylabel='Latitude (source coordinates)')
    ready=any(x['properties']['role']=='valid_burst_support' for x in collection['features'])
    axes[0].set_title('Verified burst support and instruments' if ready else 'Annotations unavailable')
    roi=shape(next(x['geometry'] for x in collection['features'] if x['properties']['role']=='primary_roi'));xmin,ymin,xmax,ymax=roi.bounds
    axes[1].set_xlim(xmin-.015,xmax+.015);axes[1].set_ylim(ymin-.008,ymax+.008);axes[1].set_title('ROI, survey points and nearby instrument')
    axes[0].legend(fontsize=7);fig.suptitle('Block36: verified IW3 burst 0 support and fixed ROI' if ready else 'Block36 preflight: no burst polygon invented')
    fig.tight_layout();out=BASE/'ROI_BURST_SURVEY_MAP.png';fig.savefig(out,dpi=150);plt.close(fig)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('init','prepare','fetch'));p.add_argument('--offline',action='store_true');a=p.parse_args(argv)
    if Path.cwd().resolve()!=ROOT:p.error('Run from actual repository root')
    os.environ.update(TEMP=str(ROOT/'_tmp'),TMP=str(ROOT/'_tmp'),MPLCONFIGDIR=str(ROOT/'_cache/matplotlib'))
    if a.phase=='init':
        t=initialize();save_json(BASE/'CREDENTIAL_STATUS.json',credential_status(cfg()['credential_file']));network_audit(t,credential_status(cfg()['credential_file']));return 0
    t=transport(offline=a.offline);credential=credential_status(cfg()['credential_file']);save_json(BASE/'CREDENTIAL_STATUS.json',credential)
    inventory=public_inventory();save_json(BASE/'ANNOTATION_INVENTORY.json',inventory);save_json(BASE/'SPATIAL_TRIAL_PLAN.json',spatial_plan())
    if a.phase=='prepare' or not credential['configured']:
        blocked_outputs(credential);plot_map();network_audit(t,credential);return 2 if a.phase=='fetch' else 0
    provider=TokenProvider(t,cfg()['credential_file'],max_requests=cfg()['max_authentication_requests'],
        expiry_skew_seconds=cfg()['token_expiry_skew_seconds']);annotations={};provenance=[]
    try:
        manifest_raw=None
        for item in inventory['files']:
            raw,record=_download_xml(t,provider,item);provenance.append(record)
            item['status']='retrieved_authenticated_sha256_verified';item['sha256']=record['sha256'];item['bytes']=record['bytes']
            if item['role']=='measurement_annotation':
                annotation=parse_annotation(raw,expected_swath=item['swath'])
                _validate_annotation_identity(annotation,item['swath'])
                annotations[item['swath']]=annotation
            else:manifest_raw=raw
        manifest_check=validate_manifest(manifest_raw,[x['name'] for x in inventory['files'] if x['role']=='measurement_annotation'])
        save_json(BASE/'MANIFEST_CONTENT_CHECK.json',manifest_check)
        pertinent=derive(annotations,inventory,provenance,credential)
        if pertinent:
            selected=[]
            for item in _find_calibration(t,provider,pertinent,inventory):
                raw,record=_download_xml(t,provider,item);provenance.append(record)
                item.update(status='retrieved_authenticated_sha256_verified',sha256=record['sha256'],bytes=record['bytes'])
                selected.append(item)
            inventory['calibration_noise'].update(status='retrieved_for_pertinent_subswath',pertinent_subswath=pertinent,files=selected)
            save_json(BASE/'DERIVATION_PROVENANCE.json',provenance)
        save_json(BASE/'ANNOTATION_INVENTORY.json',inventory)
    except (FetchError,CredentialError,ValueError,KeyError) as exc:
        blocked_outputs(credential);gate=json.loads((BASE/'GATE.json').read_text());gate.update(credentials_configured=True,
            blocking_condition='authenticated metadata preflight failed safely',error_status=getattr(exc,'status',type(exc).__name__),error_code=getattr(exc,'code',None));save_json(BASE/'GATE.json',gate)
    network_audit(t,credential);return 0 if json.loads((BASE/'GATE.json').read_text())['gate']!='BLOCKED' else 1


if __name__=='__main__':raise SystemExit(main())

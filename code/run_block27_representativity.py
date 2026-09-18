"""Resume Block27 with provenance-first, bounded observation recovery; no SAR."""
from __future__ import annotations
from repository_paths import resolve_historical
import argparse, csv, hashlib, json, math, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from shapely.geometry import shape, Point, LineString, box
from shapely.ops import transform, unary_union
from shapely import STRtree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'code'))
from run_block21_frequency_selector import parse_stations, nearest_stations
from run_block16a_scene_selection import read_esri_polygon_shapefile
from run_block22_geographic_preflight import atomic, dump, table
from umbra_sar.geographic_preflight import local_projection, scale_bar_length
from umbra_sar.reference_recovery import (HTTPBudget, fetch_limited, normalize_payload,
    parse_dds_dimensions, parse_ascii_vector, nearest_time_index, VARIABLES, spectrum_metrics)

BASE = ROOT/'umbra/selezione_scene/Block27_frequency_query'
OUT = BASE/'representativity_v1'
TARGETS = {'51209':'Samoa','42087':'Tobago','41052':'Virgin_Islands','42094':'Louisiana'}
def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def epoch(text): return datetime.fromisoformat(text.replace('Z','+00:00')).timestamp()
def serial(value):
    if isinstance(value, dict): return {k:serial(v) for k,v in value.items()}
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    return value
def bearing(a,b):
    lon1,lat1,lon2,lat2=map(math.radians,(a.x,a.y,b.x,b.y))
    return math.degrees(math.atan2(math.sin(lon2-lon1)*math.cos(lat2),
        math.cos(lat1)*math.sin(lat2)-math.sin(lat1)*math.cos(lat2)*math.cos(lon2-lon1)))%360
def same_band(n):
    f=n['frequency_hz']; e=n['arrays']['spectral_wave_density']; valid=n['masks']['spectral_wave_density']
    i=int(np.argmax(np.where(valid,e,-np.inf))); lo=hi=i
    while lo>0 and valid[lo-1] and e[lo-1]>=.5*e[i]: lo-=1
    while hi+1<len(f) and valid[hi+1] and e[hi+1]>=.5*e[i]: hi+=1
    ids=np.arange(lo,hi+1); mask=n['masks']['mean_wave_dir'][ids]&n['masks']['wave_spectrum_r1'][ids]
    ids=ids[mask]; weights=e[ids]*n['band_width_hz'][ids]*n['arrays']['wave_spectrum_r1'][ids]
    z=np.sum(weights*np.exp(1j*np.deg2rad(n['arrays']['mean_wave_dir'][ids])))
    direction=float(np.rad2deg(np.angle(z))%360) if weights.sum()>0 and abs(z)>0 else None
    return {'band_low_hz':float(f[lo]),'band_high_hz':float(f[hi]),
        'band_direction_from_deg':direction,'band_propagation_to_deg':(direction+180)%360 if direction is not None else None,
        'band_energy_m2':float(np.sum(e[lo:hi+1]*n['band_width_hz'][lo:hi+1]))}

def offline():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'REQUEST_LOG.json').exists():
        raise RuntimeError('Existing recovery ledger: offline reset forbidden; use report/recover.')
    queue=read(BASE/'BLOCK27_QUERY_QUEUE.csv')
    allrows={r['acquisition_key']:r for r in read(ROOT/'umbra/selezione_scene/Block21_frequency_validation_selector/BLOCK21_ALL_CANDIDATES.csv')}
    refs={r['acquisition_key']:r for r in read(ROOT/'umbra/selezione_scene/Block21_frequency_validation_selector/BLOCK21_REFERENCE_AVAILABILITY.csv')}
    old={r['acquisition_key']:r for r in read(ROOT/'umbra/selezione_scene/Block18_reference_recovery/BLOCK18_REFERENCE_VALIDATION.csv')}
    stations=parse_stations(ROOT/'umbra/selezione_scene/Block16_scene_selection/cache/ndbc_stationmetadata.xml')
    records=[]; inventory=[]
    for name in ['umbra/selezione_scene/Block18_reference_recovery/BLOCK18_NORMALIZED_BINS.csv',
                 'umbra/selezione_scene/Block21_frequency_validation_selector/BLOCK21_REFERENCE_BINS.csv']:
        rr=read(resolve_historical(name, ROOT)); keys=sorted({r['acquisition_key'] for r in rr})
        inventory.append({'path':name,'sha256':sha(resolve_historical(name, ROOT)),'bin_rows':len(rr),'acquisition_keys':keys})
    dump(OUT/'LOCAL_BIN_INVENTORY.json',inventory)
    for idx,q in enumerate(queue,1):
        if q['station_id'] not in TARGETS: continue
        a=allrows[q['acquisition_key']]; fp=shape(json.loads(a['geometry_json'])); roi=shape(json.loads(a['roi_polygon_json']))
        c=roi.centroid; fwd,_=local_projection(c.x,c.y)
        active=nearest_stations(c.x,c.y,stations,date_utc=q['datetime_utc'])
        r={**q,'queue_order':idx,'zone':TARGETS[q['station_id']],
           'roi_polygon_json':a['roi_polygon_json'],'footprint_json':a['geometry_json'],
           'roi_source':'Block21 deterministic fully-water square; independently selected per footprint',
           'catalog_footprint_centroid_lon':fp.centroid.x,'catalog_footprint_centroid_lat':fp.centroid.y,
           'roi_contained_in_catalog_footprint':transform(fwd,fp).covers(transform(fwd,roi)),
           'queue_center_matches_roi':abs(c.x-float(q['roi_lon']))<1e-8 and abs(c.y-float(q['roi_lat']))<1e-8,
           'coordinate_fallback':False,'product_pixel_support_verified':False,
           'nearest_historical_station':active[0]['station_id'] if active else '',
           'nearest_historical_distance_km':active[0]['station_distance_km'] if active else '',
           'reference_station_id':'','reference_status':'archive_not_queried','payload_path':'',
           'decision':'not_evaluable','missing_checks':'SAR local range/valid-data; common exposure; event model'}
        prior=refs.get(q['acquisition_key'],{})
        r['prior_reference_table_status']=prior.get('status','not_in_table')
        if q['acquisition_key'] in old:
            v=old[q['acquisition_key']]; raw=ROOT/'umbra/selezione_scene/Block18_reference_recovery/payloads_raw'/f"{q['collect_id']}_spectrum.ascii"
            das=ROOT/'umbra/selezione_scene/Block18_reference_recovery/payloads_raw/42084w9999.das'
            expected=next(t['historical_payload_sha256'] for t in json.loads((ROOT/'umbra/selezione_scene/Block18_reference_recovery/BLOCK18_CONFIG.json').read_text())['acquisitions'] if t['acquisition_key']==q['acquisition_key'])
            if sha(raw)!=expected: raise ValueError('Block18 payload hash mismatch')
            n=normalize_payload(raw.read_text(),das.read_text(),observation_epoch_s=epoch(v['observation_utc']))
            dump(OUT/'normalized'/f"{q['collect_id']}.json",serial(n))
            r.update(spectrum_metrics(n));r.update(same_band(n))
            r.update(reference_station_id='42084',reference_status='verified_local_Block18',
                payload_path=str(raw.relative_to(ROOT)),payload_sha256=sha(raw),
                observation_utc=v['observation_utc'],observation_offset_s=v['observation_offset_s'],
                joint_energy_coverage=n['joint_band_energy_coverage'],decision='conditional',
                prior_admissible_reference=v['admissible_measured_reference'])
        station=next((s for s in active if s['station_id']==(r['reference_station_id'] or q['station_id'])),None)
        if station:
            r.update(station_lon=station['station_lon'],station_lat=station['station_lat'],
                station_owner=station['station_owner'],deployment_start=station['active_start'],deployment_stop=station['active_stop'])
        records.append(r)
    table(OUT/'ACQUISITION_AUDIT.csv',records)
    dump(OUT/'STATE.json',{'stage':'offline_reconciled','transactions':0,'total_bytes':0,
        'prior_spending_evidence':'No recovery payload/log/state found under Blocks25–27; earlier Block18/21 budgets are separate historical phases. Unlogged previous spending cannot be reconstructed.',
        'prior_budget_reconciled':False,'max_transactions':30,'max_total_bytes':20*1024**2,'queue_sha256':sha(BASE/'BLOCK27_QUERY_QUEUE.csv')})
    dump(OUT/'STATION_HISTORY.json',[s for s in stations if s['station_id'] in {*TARGETS,'42084'}])
    return records

def recover():
    state=json.loads((OUT/'STATE.json').read_text()); records=read(OUT/'ACQUISITION_AUDIT.csv')
    if not state.get('prior_budget_reconciled'):
        raise RuntimeError('Remote recovery paused: prior cumulative spending not verified. Supply the existing ledger before continuing.')
    budget=HTTPBudget(30,20*1024**2,3*1024**2,15,0,transactions=state['transactions'],total_bytes=state['total_bytes'])
    logpath=OUT/'REQUEST_LOG.json'; prior=json.loads(logpath.read_text()) if logpath.exists() else []
    def persist():
        state.update(stage='recovery_partial',transactions=budget.transactions,total_bytes=budget.total_bytes)
        dump(OUT/'STATE.json',state);dump(logpath,prior+budget.log);table(OUT/'ACQUISITION_AUDIT.csv',records)
    def get(url,purpose,key=''):
        p=OUT/'raw'/f'{hashlib.sha256(url.encode()).hexdigest()}.txt'
        if p.exists(): return p.read_text(encoding='utf-8'),p
        try:
            data=fetch_limited(url,budget,purpose=purpose,acquisition_key=key);atomic(p,data)
            return data.decode('utf-8','replace'),p
        finally: persist()
    # Operator and station documentation are part of the same hard budget.
    docs=[('42087','https://www.ndbc.noaa.gov/station_page.php?station=42087'),
          ('42087_operator','https://www.coral.noaa.gov/'),
          ('51209','https://www.ndbc.noaa.gov/station_page.php?station=51209'),
          ('41052','https://www.ndbc.noaa.gov/station_page.php?station=41052'),
          ('42094','https://www.ndbc.noaa.gov/station_page.php?station=42094')]
    for sid,url in docs:
        try: get(url,'station_or_operator_documentation',sid)
        except Exception: pass
    cache={}; failed=set()
    for r in records:
        if r['reference_status']=='verified_local_Block18' or r['reference_status']=='recovered': continue
        if budget.transactions>=30: break
        sid=r['station_id'];year=r['datetime_utc'][:4]
        root=f'https://dods.ndbc.noaa.gov/thredds/dodsC/data/swden/{sid}/{sid}w9999.nc'
        try:
            for dataset in [root,root.replace('9999',year)]:
                if dataset in failed: continue
                try:
                    if dataset not in cache:
                        dds,_=get(dataset+'.dds','dds',sid);dims=parse_dds_dimensions(dds)
                        das,_=get(dataset+'.das','das',sid);tv,_=get(dataset+'.ascii?time','time',sid)
                        times=parse_ascii_vector(tv,'time');cache[dataset]=(dims,das,times)
                    dims,das,times=cache[dataset];i,obs=nearest_time_index(times,epoch(r['datetime_utc']))
                    offset=obs-epoch(r['datetime_utc'])
                    r.update(observation_offset_s=offset,observation_utc=datetime.fromtimestamp(obs,timezone.utc).isoformat())
                    if abs(offset)>3600:
                        r['reference_status']='outside_time_tolerance';continue
                    nf=dims['frequency'];sel=','.join(f'{v}[{i}:1:{i}][0:1:{nf-1}][0:1:0][0:1:0]' for v in VARIABLES)
                    url=dataset+'.ascii?frequency,'+sel
                    text,path=get(url,'spectrum',r['acquisition_key'])
                    try: n=normalize_payload(text,das,observation_epoch_s=obs)
                    except Exception as exc:
                        r.update(reference_status='parse_failed',reference_error=repr(exc));break
                    dump(OUT/'normalized'/f"{r['collect_id']}.json",serial(n))
                    r.update(spectrum_metrics(n));r.update(same_band(n))
                    r.update(reference_status='recovered',reference_station_id=sid,payload_path=str(path.relative_to(ROOT)),
                        payload_sha256=sha(path),source_url=url,joint_energy_coverage=n['joint_band_energy_coverage'],
                        decision='conditional' if n['joint_band_energy_coverage']>=.9 else 'not_evaluable')
                    break
                except Exception as exc:
                    failed.add(dataset);r.update(reference_status='request_failed',reference_error=repr(exc))
            persist()
        except Exception as exc:
            r.update(reference_status='request_failed',reference_error=repr(exc));persist()
    persist()

def maps_report():
    records=read(OUT/'ACQUISITION_AUDIT.csv')
    land=read_esri_polygon_shapefile(ROOT/'umbra/validazione/Block8_validation/catalog_raw/ne_10m_land/ne_10m_land.shp')
    tree=STRtree(land); (OUT/'maps').mkdir(exist_ok=True)
    for zone in TARGETS.values():
        rr=[r for r in records if r['zone']==zone]; c=shape(json.loads(rr[0]['roi_polygon_json'])).centroid
        fwd,_=local_projection(c.x,c.y)
        context=box(c.x-.5,c.y-.5,c.x+.5,c.y+.5)
        coast=unary_union([land[int(i)] for i in tree.query(context)])
        fig,ax=plt.subplots(figsize=(9,7));lc=transform(fwd,coast)
        geoms=list(lc.geoms) if hasattr(lc,'geoms') else [lc]
        for g in geoms:
            if g.geom_type=='Polygon':
                x,y=g.exterior.xy;ax.fill(x,y,color='.8')
        points=[]
        for j,r in enumerate(rr):
            fp=shape(json.loads(r['footprint_json']));roi=shape(json.loads(r['roi_polygon_json']));rp=transform(fwd,roi)
            for p,color,label in [(transform(fwd,fp),'steelblue','catalog footprint'),(rp,'darkgreen','actual ROI')]:
                x,y=p.exterior.xy;ax.plot(x,y,color=color,alpha=.6,label=label if j==0 else None)
                points.extend(zip(x,y))
            buoy=Point(float(r['station_lon']),float(r['station_lat']));line=LineString([buoy,roi.centroid])
            segment=transform(fwd,line);x,y=segment.xy;ax.plot(x,y,'r--',alpha=.4)
            ax.plot(x[0],y[0],'r^');ax.text(x[0],y[0],r['reference_station_id'] or r['station_id'],fontsize=7)
            points.append((x[0],y[0]))
            r.update(segment_land_intersection=coast.intersects(line),
                segment_land_length_m=transform(fwd,coast.intersection(line)).length,
                buoy_roi_bearing_deg=bearing(buoy,roi.centroid),buoy_roi_distance_m=segment.length,
                roi_land_overlap_m2=rp.intersection(lc).area,
                coastline_source='Natural Earth 1:10m land; cartographic scale, not 10 m resolution; preliminary only')
            if r['reference_status'] in {'verified_local_Block18','recovered'} and r.get('band_propagation_to_deg','')!='':
                r['preliminary_axial_difference_deg']=abs((float(r['local_range_axis_deg'])-float(r['band_propagation_to_deg'])+90)%180-90)
                r['range_geometry_status']='vendor azimuth proxy only; SICD local surface projection unverified'
            r['exposure_evidence']='land intersection is exposure clue only' if coast.intersects(line) else 'no land intersection in coarse mask; common wave field not established'
        pts=np.asarray(points);mins=pts.min(axis=0);maxs=pts.max(axis=0);pad=.15*max(maxs-mins)
        ax.set_xlim(mins[0]-pad,maxs[0]+pad);ax.set_ylim(mins[1]-pad,maxs[1]+pad)
        scale=scale_bar_length(ax.get_xlim()[1]-ax.get_xlim()[0]);xx=ax.get_xlim()[0]+pad/2;yy=ax.get_ylim()[0]+pad/2
        ax.plot([xx,xx+scale],[yy,yy],'k-',lw=3);ax.text(xx,yy,f'{scale/1000:g} km',va='bottom')
        ax.annotate('N',xy=(.95,.95),xytext=(.95,.8),xycoords='axes fraction',arrowprops={'arrowstyle':'->'})
        ax.set_aspect('equal');ax.set_xlabel('local east [m]');ax.set_ylabel('local north [m]');ax.set_title(zone+' — station / catalog footprints / frozen ROI');ax.legend();fig.tight_layout()
        fig.savefig(OUT/'maps'/f'{zone}.png',dpi=140);plt.close(fig)
    table(OUT/'ACQUISITION_AUDIT.csv',records)
    state=json.loads((OUT/'STATE.json').read_text());counts={s:sum(r['reference_status']==s for r in records) for s in sorted({r['reference_status'] for r in records})}
    summary={'status':'partial_not_scientifically_complete','acquisitions':len(records),'reference_status_counts':counts,
        'roi_containment_failures':sum(r['roi_contained_in_catalog_footprint']=='False' for r in records),
        'transactions':state['transactions'],'total_bytes':state['total_bytes'],'priority_candidate':None,
        'unresolved':['adequate Tobago coastline','historical instrument/product coverage documentation','event model native resolution and assimilation','unlogged prior spending cannot be excluded']}
    dump(OUT/'SUMMARY.json',summary)
    report=f'''# Block27 — buoy–ROI representativity continuation v1

This is a provenance/recovery checkpoint, not completed physical validation.
Frozen queue/report retained without overwriting; four zones, {len(records)} acquisitions.

## Input reconciliation

ROI polygons are reused verbatim from Block21, not reconstructed from rounded coordinates.
The Gulf centers are **not exactly identical**: near 29 N / 90 W because repeated acquisition footprints cover the same target and the deterministic square search selects near the central interior. No fallback coordinates are present in these queue entries; footprint centroid and ROI remain separate columns. Containment is checked against catalog polygons only, not SICD pixel support. See per-acquisition table.

The queue wave-station target 42094 does not replace the actual verified Block18 reference 42084. The nearest station of any instrument type is separately recomputed (GRBL1 in the Gulf); proximity alone does not establish spectral capability. Four Block18 raw hashes are checked before offline reparsing; their normalized individual masks and joint masks are retained. Block21 bins contain only newly recovered acquisitions; the separate availability table and Block18 bin archive are inventoried rather than interpreted as no-data evidence.

## Observations and decisions

Statuses: `{json.dumps(counts)}`. Recovered spectra use dynamic DDS dimensions, variable-specific masks and midpoint reconstructed frequency widths. Direction is propagation=(from+180) mod360; period and direction refer to the same contiguous half-power lobe. No added energy/wavelength/kh/phase gate, no Snell correction, no tuning to Vandenberg.

References with usable payloads are **conditional**, not proof of common exposure. Failed source requests are not documented product absence. Unqueried dates retain frozen order. No candidate is promoted using unsupported clean-water/traffic/plume descriptions in the legacy report.

## Geography and models

Four maps show frozen ROI, catalog footprints, reference/target stations, north and metric scale. Bearings, distances and land intersection lengths are tabulated. Natural Earth 1:10m is a cartographic-scale preliminary land mask, not a high-resolution coastline certification for reef-scale Tobago exposure. Intersections indicate possible different exposure only; non-intersections do not establish identical sea state. GEBCO point depths in the input queue are not used for refraction or validation: exact source/datum has not been reconciled.

Existing Block8/16 wave-model caches are historical screening, not verified paired event predictions at native buoy/ROI cells. No model comparison or climatology substitute is claimed; native resolution, mask, event coverage, partitions, currents and assimilation remain to be documented before model retrieval.

## Budget / resumability

Recorded recovery spending: {state['transactions']}/30 transactions, {state['total_bytes']}/20971520 response bytes; retries disabled, redirects counted by Block18 budget. Existing Blocks25–27 contain no request ledger or recovery payloads, so unlogged prior spending cannot be reconstructed. State and raw URL-hash cache avoid repeated successful requests. This uncertainty prevents claiming a certified cumulative pre-existing budget.

No SAR, AIS, inversion or Vandenberg processing. No justified priority yet. Next single step: resolve the outstanding provenance/documentation gaps before any SAR preflight.
'''
    atomic(OUT/'REPORT.md',report.encode('utf-8'))
    artifacts=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='MANIFEST.json']
    dump(OUT/'MANIFEST.json',{'artifacts':artifacts,'version':'representativity_v1','source_queue_sha256':sha(BASE/'BLOCK27_QUERY_QUEUE.csv')})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['offline','recover','report']);args=ap.parse_args()
    if args.stage=='offline': offline()
    elif args.stage=='recover': recover()
    else: maps_report()

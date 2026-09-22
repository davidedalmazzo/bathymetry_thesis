"""Reproducible offline plots/evidence/conditional first-product card for Block35."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
from scipy.signal import find_peaks, peak_prominences
from shapely.geometry import shape, Polygon, Point, mapping
from shapely.ops import transform
from repository_paths import ROOT, resolve_historical
from frf_client.transport import save_json, digest
from frf_client.output import table
from frf_client.geometry import inverse, distances
from s1_spatial import axial_difference, dispersion_sensitivity
from s1_spatial_compare import BASE, compare, observations


def read(path):return json.loads(path.read_text())


def band_diagnostic(folder, uuid):
    """Descriptive numeric half-maximum lobes, NOT a physical system partition."""
    tensors=read(folder/uuid/'TENSORS.json');out=[]
    for row in observations(folder,uuid):
        if row['variable']!='waveEnergyDensity' or row['role']!='nearest_qc' or row['representative_eligible']!='True':continue
        key=row['tensor_pointer'].split('/')[0];j=int(row['tensor_pointer'].split('/')[-1]);v=tensors[key]['variables']
        f=np.asarray(v['waveFrequency']['raw_values'],float);e=np.asarray(v['waveEnergyDensity']['raw_values'][j],float)
        mask=np.asarray(v['waveEnergyDensity']['valid_mask'][j],bool)&np.isfinite(e)&(e>=0)
        if not np.any(mask):continue
        en=np.where(mask,e,0);peak=int(np.argmax(en));lo=hi=peak
        while lo>0 and mask[lo-1] and en[lo-1]>=en[peak]/2:lo-=1
        while hi<len(f)-1 and mask[hi+1] and en[hi+1]>=en[peak]/2:hi+=1
        # Width convention matches existing FRF scalar summary midpoint edges.
        edges=np.r_[f[0]-(f[1]-f[0])/2,(f[1:]+f[:-1])/2,f[-1]+(f[-1]-f[-2])/2]
        df=np.diff(edges);m0=float(np.sum(en*df));peaks,_=find_peaks(en)
        prominences=peak_prominences(en,peaks)[0] if len(peaks) else []
        out.append({'instrument_id':row['instrument_id'],'time_utc':row['sensor_time_utc'],
            'offset_seconds':float(row['offset_seconds']),'qc_flag':row['qc_flag'],'source':row['product'],
            'original_sample_index':int(row['original_sample_index']),'tensor_pointer':row['tensor_pointer'],
            'f_peak_bin_hz':float(f[peak]),'T_peak_bin_s':float(1/f[peak]),'m0_m2':m0,'Hm0_m':float(4*np.sqrt(m0)),
            'valid_bin_fraction':float(mask.mean()),'half_max_interval_hz':[float(edges[lo]),float(edges[hi+1])],
            'half_max_width_hz':float(edges[hi+1]-edges[lo]),'half_max_energy_fraction':float(np.sum(en[lo:hi+1]*df[lo:hi+1])/m0),
            'all_numeric_local_maxima':[{'f_hz':float(f[k]),'E_m2_Hz':float(en[k]),'prominence_m2_Hz':float(p)} for k,p in zip(peaks,prominences)],
            'classification':'numeric peak/half-maximum description only, not independent physical wave systems',
            'published_at_same_spectral_sample':{n:(float(v[n]['raw_values'][j]) if v[n]['valid_mask'][j] else None)
                for n in ('waveTp','waveMeanDirectionPeakFrequency','wavePeakDirectionPeakFrequency','directionalPeakSpread') if n in v}})
    return out


def survey_roi(surveys):
    """Geography preselection independent of any k/omega depth agreement."""
    # North of the pier profiles 514/520, offshore of the beach. Fixed before
    # evaluating any depth statistics. This is not a universal window-size rule.
    bounds=[300.,850.,700.,1000.] # x_min,x_max,y_min,y_max, metres in native FRF frame
    source=next(s for s in surveys if '20211024' in s['metadata']['source'])
    points=source['points'];xy=np.array([[p['xFRF'],p['yFRF']] for p in points]);ll=np.array([[p['longitude'],p['latitude']] for p in points])
    design=np.c_[np.ones(len(xy)),xy];coef=np.linalg.lstsq(design,ll,rcond=None)[0]
    predicted=design@coef
    residual=np.array([inverse(*a,*b)[0] for a,b in zip(ll,predicted)])
    corners=np.array([[bounds[0],bounds[2]],[bounds[1],bounds[2]],[bounds[1],bounds[3]],[bounds[0],bounds[3]]])
    roi=Polygon(np.c_[np.ones(4),corners]@coef)
    summary={'frf_bounds_m':bounds,'geojson':mapping(roi),
        'coordinate_mapping':'local affine approximation fitted to source xFRF/yFRF and geographic point pairs; not a SAR pixel geolocator',
        'coordinate_mapping_residual_p95_m':float(np.percentile(residual,95)),
        'coordinate_mapping_source':source['metadata']['source'],
        'selection_reason':'north of pier profiles 514/520, away from beach; actual survey point envelope, no predicted k/depth agreement criterion',
        'marine_status':'preliminary offshore FRF location; negative measured bed elevations support water, exact shoreline/structures and SAR valid pixels still require confirmation',
        'pier_alongshore_min_separation_m':bounds[2]-520,'survey_checks':[]}
    gx,gy=np.meshgrid(np.linspace(bounds[0],bounds[1],23),np.linspace(bounds[2],bounds[3],13));grid=np.c_[gx.ravel(),gy.ravel()]
    for survey in surveys:
        inside=[p for p in survey['points'] if bounds[0]<=p['xFRF']<=bounds[1] and bounds[2]<=p['yFRF']<=bounds[3]]
        entry={'source':survey['metadata']['source'],'points_in_roi':len(inside),'complete_source_indices':survey['all_indices_traversed'],
            'vertical_datum':survey['vertical_datum'],'water_depth_status':'bed elevation NAVD88, NOT instantaneous water depth'}
        if inside:
            z=np.array([p['elevation'] for p in inside]);coords=np.array([[p['xFRF'],p['yFRF']] for p in inside])
            times=np.array([p['time'] for p in inside if p['time'] is not None])
            d,_=cKDTree(coords).query(grid)
            entry.update(elevation_percentiles_NAVD88_m=np.percentile(z,[5,50,95]).tolist(),
                survey_point_time_min_utc=datetime.fromtimestamp(float(times.min()),timezone.utc).isoformat() if len(times) else None,
                survey_point_time_max_utc=datetime.fromtimestamp(float(times.max()),timezone.utc).isoformat() if len(times) else None,
                profiles=sorted(set(p['profileNumber'] for p in inside if p['profileNumber'] is not None)),
                roi_grid_nearest_point_distance_p50_p95_max_m=[float(np.percentile(d,50)),float(np.percentile(d,95)),float(d.max())],
                all_measured_elevations_below_NAVD88_zero=bool(np.all(z<0)),
                gradient_status='not a continuous surface; global planar gradient deliberately not asserted')
            slopes=[]
            for profile in entry['profiles']:
                pts=sorted([p for p in inside if p['profileNumber']==profile],key=lambda p:p['source_index'])
                for a,b in zip(pts[:-1],pts[1:]):
                    ds=np.hypot(a['xFRF']-b['xFRF'],a['yFRF']-b['yFRF'])
                    if b['source_index']==a['source_index']+1 and 1<=ds<=20:
                        slopes.append({'ds_m':float(ds),'dz_m':b['elevation']-a['elevation'],
                            'magnitude':abs(b['elevation']-a['elevation'])/float(ds)})
            entry['adjacent_observed_segment_diagnostic']={'scale_policy':'only consecutive source indices, same profile, spacing 1-20 m; not cross-profile surface gradient',
                'count':len(slopes),'spacing_p50_m':float(np.median([s['ds_m'] for s in slopes])) if slopes else None,
                'absolute_slope_p50_p95':np.percentile([s['magnitude'] for s in slopes],[50,95]).tolist() if slopes else None}
        summary['survey_checks'].append(entry)
    return summary


def figures(rows, finalists, surveys, roi, spectra):
    out=BASE/'figures';out.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(10,8))
    for row in read(BASE/'INVENTORY.json'):
        geo=shape(row['footprint']);polys=[geo] if geo.geom_type=='Polygon' else geo.geoms
        for poly in polys:ax.plot(*poly.exterior.xy,lw=.8,label=row['start_utc'][:10]+' slice '+str(row['slice_number']))
    station_positions={}
    for finalist in finalists:
        for tensor in read(BASE/'frf-b'/finalist['uuid']/'TENSORS.json').values():
            pos=tensor['historical_position']['lon_lat']
            if pos:station_positions[tensor['stable_identity']]=pos
    for name,pos in station_positions.items():ax.scatter(*pos,s=35);ax.annotate(name,pos,fontsize=8)
    ax.set(xlim=(-78.6,-72.9),ylim=(34,38),xlabel='Longitude WGS84',ylabel='Latitude WGS84',title='CDSE catalogue footprints, not valid burst support')
    ax.legend(fontsize=6,loc='lower right');fig.tight_layout();fig.savefig(out/'REGIONAL_FOOTPRINTS.png',dpi=130);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for survey in surveys:
        pts=survey['points'];label=Path(survey['metadata']['source']).stem[-8:]
        axes[0].scatter([p['xFRF'] for p in pts],[p['yFRF'] for p in pts],s=.3,label=label)
        axes[1].scatter([p['longitude'] for p in pts],[p['latitude'] for p in pts],s=.3)
    b=roi['frf_bounds_m'];axes[0].plot([b[0],b[1],b[1],b[0],b[0]],[b[2],b[2],b[3],b[3],b[2]],'k--',label='Proposed ROI')
    axes[0].axhspan(514,520,color='red',alpha=.3,label='Pier profiles (metadata)');axes[0].set(xlabel='xFRF cross-shore (m)',ylabel='yFRF alongshore (m)',title='Actual points only, no continuous surface');axes[0].legend(fontsize=7)
    axes[1].plot(*shape(roi['geojson']).exterior.xy,'k--')
    for name,pos in station_positions.items():axes[1].scatter(*pos,s=25);axes[1].annotate(name,pos,fontsize=6)
    axes[1].set(xlabel='Longitude WGS84',ylabel='Latitude WGS84',title='ROI / dated nominal instruments');fig.tight_layout();fig.savefig(out/'ROI_SURVEYS.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(len(finalists),1,figsize=(9,3*len(finalists)))
    for ax,finalist in zip(axes,finalists):
        uuid=finalist['uuid'];tensors=read(BASE/'frf-refined'/uuid/'TENSORS.json')
        for row in observations(BASE/'frf-refined',uuid):
            if row['variable']!='waveEnergyDensity' or row['role']!='nearest_qc' or row['representative_eligible']!='True':continue
            key=row['tensor_pointer'].split('/')[0];j=int(row['tensor_pointer'].split('/')[-1]);v=tensors[key]['variables']
            e=np.asarray(v['waveEnergyDensity']['raw_values'][j],float);mask=np.asarray(v['waveEnergyDensity']['valid_mask'][j])
            ax.plot(v['waveFrequency']['raw_values'],np.where(mask,e,np.nan),label=row['instrument_id']+' '+row['sensor_time_utc'][11:19]+f" dt={float(row['offset_seconds']):.0f}s")
        ax.set(xlabel='f (Hz)',ylabel='E (m2/Hz)',title=finalist['start_utc']+' — QC-eligible spectra, numeric lobes not wave-system partitions',xlim=(.035,.35));ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/'SPECTRA_FINALISTS.png',dpi=130);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(11,7));labels=[r['start_utc'][:10] for r in finalists];merged={r['uuid']:r for r in rows}
    for ax,var,title in zip(axes.flat,['waveHs','waveTp','directionalPeakSpread','axial_delta_footprint_proxy_deg'],['Published Hs (m)','Published Tp (s), not mean period','Published peak spread (deg)','Peak toward / footprint proxy axial difference (deg)']):
        for inst in ('waverider-17m','awac-11m'):
            vals=[merged[r['uuid']].get(inst+'__'+var) for r in finalists]
            ax.plot(labels,[np.nan if v is None else v for v in vals],'o-',label=inst)
        ax.set_title(title);ax.tick_params(axis='x',rotation=30);ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/'CONDITIONS.png',dpi=140);plt.close(fig)


def main():
    compare('frf-b');refined=compare('frf-refined')
    allrows=read(BASE/'FRF-A_COMPARISON.json');more={r['uuid']:r for r in refined}
    inventory=read(BASE/'INVENTORY.json');finalists=read(BASE/'FINALISTS.json');final_ids={r['uuid'] for r in finalists}
    surveys=[read(p) for p in sorted((BASE/'surveys').glob('*.json'))]
    roi=survey_roi(surveys);save_json(BASE/'PROPOSED_ROI.json',roi)
    spectra={r['uuid']:band_diagnostic(BASE/'frf-refined',r['uuid']) for r in finalists}
    save_json(BASE/'SPECTRAL_BAND_DIAGNOSTICS.json',spectra)
    common=[]
    for row in allrows:
        uuid=row['uuid']
        if uuid in final_ids:
            for k,v in more[uuid].items():
                if v is not None:row[k]=v
            row['roi_contained_in_catalogue_footprint']=shape(next(r for r in inventory if r['uuid']==uuid)['footprint']).covers(shape(roi['geojson']))
            footprint=shape(next(r for r in inventory if r['uuid']==uuid)['footprint']);roi_geo=shape(roi['geojson'])
            lat0=roi_geo.centroid.y
            projector=lambda x,y,z=None:(6371008.8*np.radians(x)*np.cos(np.radians(lat0)),
                                        6371008.8*np.sin(np.radians(y))/np.cos(np.radians(lat0)))
            row['catalogue_roi_boundary_margin_approx_m']=float(transform(projector,roi_geo).distance(transform(projector,footprint.boundary))) if row['roi_contained_in_catalogue_footprint'] else None
            row['catalogue_margin_scope']='local cylindrical equal-area distance approximation; NOT valid burst/pixel margin'
            row['reference_spectra_available']=len(spectra[uuid])
            row['reference_is_local_truth']=False
            ancillary=observations(BASE/'frf-b',uuid)
            for tensor in read(BASE/'frf-refined'/uuid/'TENSORS.json').values():
                inst=tensor['stable_identity'].removeprefix('FRF:');position=tensor['historical_position']['lon_lat']
                d=distances(position,roi_geo)
                row[inst+'__roi_min_distance_m']=d['minimum_m'];row[inst+'__roi_center_distance_m']=d['center_m']
                row[inst+'__position_status']=tensor['historical_position']['status']
            for obs in ancillary:
                if obs['role']=='nearest_qc' and obs['representative_eligible']=='True' and obs['value'] and obs['variable'] in ('windSpeed','windDirection','gaugeElevation','waterLevel','predictedWaterLevel','residualWaterLevel'):
                    prefix=obs['instrument_id']+'__'+obs['variable'];row[prefix]=float(obs['value']);row[prefix+'__offset_s']=float(obs['offset_seconds']);row[prefix+'__qc']=obs['qc_flag'];row[prefix+'__source']=obs['product']
            for tensor in read(BASE/'frf-b'/uuid/'TENSORS.json').values():
                if tensor['stable_identity']=='FRF:eopNoaaTide':
                    row['water_level_reference_datum']=tensor['metadata']['attributes'].get('NC_GLOBAL',{}).get('datum')
                    row['water_level_source_caveat']='source says NOAA preliminary, possibly substitute gauges; archive QA and dataSource not resolved'
            for obs in ancillary:
                if obs['family']=='water_level' and obs['variable']=='waterLevel' and obs['role']=='nearest_context':
                    row['water_level_context_m']=float(obs['value']) if obs['value'] else None
                    row['water_level_context_offset_s']=float(obs['offset_seconds'])
                    row['water_level_context_qc_status']=obs['status']
                    row['water_level_context_NOT_representative']=obs['representative_eligible']!='True'
            row['wind_averaging_definition']='10-minute source mean; timestamp anchor unresolved'
            row['wind_elevation_definition']='gaugeElevation above NAVD88, not corrected to 10 m or instantaneous water'
            for summary in spectra[uuid]:
                inst=summary['instrument_id'].removeprefix('FRF:')
                for k in ('Hm0_m','f_peak_bin_hz','T_peak_bin_s','half_max_width_hz','half_max_energy_fraction','valid_bin_fraction'):
                    row[inst+'__'+k]=summary[k]
                common.append({'uuid':uuid,'source':summary['source'],'original_sample_index':summary['original_sample_index'],
                               'time_utc':summary['time_utc'],'instrument':inst})
        else:
            row['reference_spectra_available']=None
            row['spectral_scope']='not a finalist; pass-A QC bulk kept, pass-B intentionally not expanded'
        row['currents_status']='profile query timeout; no wave-effective current inferred'
        row['local_geometry_status']='annotation inventory public, XML content requires CDSE authentication; not verified'
    table(BASE/'ALL_CANDIDATES.csv',allrows);save_json(BASE/'ALL_CANDIDATES.json',allrows)
    groups={}
    for r in common:groups.setdefault((r['source'],r['original_sample_index']),[]).append(r['uuid'])
    save_json(BASE/'SHARED_REFERENCES.json',[{'source':k[0],'sample_index':k[1],'products':v,'independent_records':1} for k,v in groups.items()])
    figures(allrows,finalists,surveys,roi,spectra)
    first=finalists[0];selected=next(r for r in allrows if r['uuid']==first['uuid'])
    save_json(BASE/'FIRST_PRODUCT.json',{'decision':'conditional first technical IW SLC download, NOT method validation',
        'product':first,'observational_evidence':selected,'roi':roi,
        'why':'predeclared narrower measured peak spread first; substantial wave energy, both spectral references available; no alignment gate based on footprint proxy',
        'alternative':finalists[1],'remaining_checks':['authenticate to retrieve VV annotations of all three subswaths and manifest',
            'geolocate marine ROI onto burst valid support, margins and burst seams; local projected range/incidence',
            'confirm actual wave signature/spatial convergence in complex SAR, without imposed predicted k',
            'verify tide gauge source/archive QC and local water-level representativity; metadata datum NAVD88 retained separately from bed epoch; absent representative currents'],
        'no_download_executed':True,'no_temporal_validation_claim':True})
    # Analytic examples are explicit scenarios, not inferred actual scene depths.
    save_json(BASE/'DISPERSION_SENSITIVITY_SCENARIOS.json',[{'k_rad_m':k,'h_m':h,**dispersion_sensitivity(k,h),
        'scope':'illustrative analytic sensitivity only; no actual-scene depth inversion'} for k,h in ((.04,5),(.06,12),(.02,25))])
    baseline=read(ROOT/'duck_frf/Block34_frf_operational/FROZEN_BASELINE.json')
    mismatches=[]
    for item in baseline:
        p=resolve_historical(item['path'])
        if not p.exists() or digest(p.read_bytes())!=item['sha256']:mismatches.append(item['path'])
    save_json(BASE/'FROZEN_AUDIT.json',{'baseline':'duck_frf/Block34_frf_operational/FROZEN_BASELINE.json',
        'verified':len(baseline),'mismatches':mismatches,'historical_files_not_rewritten':True})
    ledger=BASE/'network/s1_duck_spatial_202110';events=[json.loads(l) for l in (ledger/'requests.jsonl').read_text().splitlines()]
    state=read(ledger/'NETWORK_STATE.json');save_json(BASE/'NETWORK_AUDIT.json',{'state':state,'events':events,
        'started_http_attempts':sum(e['status']=='started' for e in events),
        'conservative_reserved_attempts':state.get('conservative_reserved_attempts',0),
        'historic_consumption':'not part of this tranche; not determinable from this ledger',
        'no_historical_cumulative_limit_claim':True})
    print(json.dumps({'first_uuid':first['uuid'],'frozen_checked':len(baseline),'mismatches':len(mismatches),'network':state}))


if __name__=='__main__':main()

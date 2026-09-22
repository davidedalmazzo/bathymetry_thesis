"""Offline, unweighted Sentinel-1/FRF evidence comparison (no SAR processing)."""
import csv
import json
import math
from pathlib import Path
from repository_paths import ROOT
from frf_client.transport import save_json
from frf_client.output import table
from s1_spatial import representatives, axial_difference

BASE = ROOT/'duck_frf/Block35_s1_spatial_selection'


def observations(base, uuid):
    path=base/uuid/'OBSERVATIONS.csv'
    if not path.exists():return []
    return list(csv.DictReader(path.open(encoding='utf-8',newline='')))


def compare(phase='frf-a'):
    rows=[]
    for item in json.loads((BASE/'INVENTORY.json').read_text()):
        obs=observations(BASE/phase,item['uuid'])
        row={k:item[k] for k in ('uuid','name','acquisition_key','start_utc','end_utc','bytes','online',
             'relative_orbit','orbit_direction','marine_screening_fraction','range_edge_proxy_axial_deg')}
        row.update(local_range_deg=item.get('local_range_deg'),local_incidence_deg=item.get('local_incidence_deg'),
            technical_status='catalogue marine coverage' if item['marine_screening_fraction'] else 'AOI intersection but selected marine area absent',
            geometry_status='conditional: catalogue footprint is not burst valid support')
        for inst in ('waverider-17m','awac-11m'):
            selected={}
            for o in obs:
                if o['instrument_id']=='FRF:'+inst and o['role']=='nearest_qc' and o['representative_eligible']=='True' and o['value']:
                    selected[o['variable']]=o
            for var in ('waveHs','waveTp','waveTm','waveMeanDirectionPeakFrequency',
                        'wavePeakDirectionPeakFrequency','directionalPeakSpread'):
                o=selected.get(var)
                row[inst+'__'+var]=float(o['value']) if o else None
                row[inst+'__'+var+'__offset_s']=float(o['offset_seconds']) if o else None
                row[inst+'__'+var+'__time_utc']=o['sensor_time_utc'] if o else None
            direction=selected.get('waveMeanDirectionPeakFrequency') or selected.get('wavePeakDirectionPeakFrequency')
            row[inst+'__direction_estimator']=direction['variable'] if direction else None
            if direction:
                toward=(float(direction['value'])+180)%360
                row[inst+'__peak_toward_deg']=toward
                row[inst+'__axial_delta_footprint_proxy_deg']=axial_difference(toward,item['range_edge_proxy_axial_deg']) if item['range_edge_proxy_axial_deg'] is not None else None
            else:
                row[inst+'__peak_toward_deg']=None
                row[inst+'__axial_delta_footprint_proxy_deg']=None
            row[inst+'__reference_status']='QC-checked event scalars; not automatically local truth' if selected.get('waveTp') else 'missing or unverified, not physically unfavorable'
            nearest=[abs(float(o['offset_seconds'])) for o in obs if o['instrument_id']=='FRF:'+inst and o['role']=='nearest_context']
            row[inst+'__nearest_raw_gt_60min']=min(nearest)>3600 if nearest else None
        rows.append(row)
    table(BASE/(phase.upper()+'_COMPARISON.csv'),rows)
    save_json(BASE/(phase.upper()+'_COMPARISON.json'),rows)
    if phase=='frf-a':
        reps={r['uuid']:r for r in representatives(json.loads((BASE/'INVENTORY.json').read_text()))}
        def rank(row):
            known=row.get('waverider-17m__waveTp') is not None or row.get('awac-11m__waveTp') is not None
            spread=row.get('waverider-17m__directionalPeakSpread')
            hs=row.get('waverider-17m__waveHs')
            return (not known, spread if spread is not None else math.inf, -(hs or 0),row['start_utc'])
        candidates=[r for r in rows if r['uuid'] in reps and r['online'] is True and (r['marine_screening_fraction'] or 0)>0]
        finalists=[reps[r['uuid']] for r in sorted(candidates,key=rank)[:5]]
        save_json(BASE/'FINALISTS.json',finalists)
        save_json(BASE/'SHORTLIST_REASON.json',{'rule':'predeclared protocol; all technically covered acquisitions fit maximum five',
            'all_products_retained':len(rows),'finalists':len(finalists), 'no_physical_cutoff':True,
            'footprint_proxy_not_used_to_reject':True, 'no_date_extension_needed':bool(finalists)})
    return rows


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=('frf-a','frf-b','frf-refined'),default='frf-a')
    compare(p.parse_args().phase)

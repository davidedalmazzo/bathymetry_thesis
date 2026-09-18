"""Offline operational CLI/tranche behavior, no actual endpoints."""
import io
import json
from pathlib import Path
import numpy as np
import pytest
from frf_client.transport import Transport,FetchError,digest
from frf_client.inputs import validate_batch

URL='https://chldata.erdc.dren.mil/thredds/synthetic'


class Response(io.BytesIO):
    status=200
    def __init__(self,body=b'ok'):super().__init__(body);self.headers={'Content-Length':str(len(body))}


class Opener:
    def __init__(self):self.calls=0
    def open(self,*args,**kwargs):self.calls+=1;return Response()


def test_named_tranche_resume_no_reset_or_enlargement(tmp_path):
    cache=tmp_path/'cache';budget=tmp_path/'tranches/one';opener=Opener()
    kwargs=dict(tranche_directory=budget,tranche_name='one',max_requests=1,max_bytes=10,max_response=5,rate_seconds=0,opener=opener)
    with pytest.raises(ValueError,match='explicit'):Transport(cache,**kwargs)
    t=Transport(cache,new_tranche=True,**kwargs);assert t.state_path.exists()
    assert t.get(URL)==b'ok'
    resumed=Transport(cache,**kwargs);assert resumed.get(URL)==b'ok' and opener.calls==1
    with pytest.raises(FetchError,match='incomplete_budget'):resumed.get(URL+'2')
    with pytest.raises(ValueError,match='already exists'):Transport(cache,new_tranche=True,**kwargs)
    with pytest.raises(ValueError,match='budget'):Transport(cache,**{**kwargs,'max_requests':2})
    with pytest.raises(ValueError,match='response limit'):Transport(cache,**{**kwargs,'max_response':6})
    with pytest.raises(ValueError,match='safe tranche'):Transport(cache,**{**kwargs,'tranche_name':'..'})


def test_new_named_tranche_reuses_verified_cache_no_network_charge(tmp_path):
    opener=Opener();t=Transport(tmp_path/'payloads',tranche_directory=tmp_path/'one',tranche_name='one',new_tranche=True,opener=opener,rate_seconds=0)
    assert t.get(URL)==b'ok'
    second=Transport(tmp_path/'payloads',tranche_directory=tmp_path/'two',tranche_name='two',new_tranche=True,opener=opener,rate_seconds=0)
    assert second.get(URL)==b'ok' and second.state['transactions']==second.state['bytes']==0
    assert t.state['transactions']==1 and opener.calls==1


def test_verified_import_does_not_import_old_budget(tmp_path):
    source=Transport(tmp_path/'source',opener=Opener(),rate_seconds=0)
    source.get(URL)
    target=Transport(tmp_path/'destination',offline=True)
    assert target.import_verified(source.directory)[0]['status']=='verified_payload_reused_no_network'
    assert target.get(URL)==b'ok' and target.state['transactions']==0
    source._paths(URL)[0].write_bytes(b'corrupt')
    assert target.import_verified(source.directory)[0]['status']=='hash_mismatch_not_reused'


def rectangle(x=0):return {'type':'Polygon','coordinates':[[[x,0],[x+1,0],[x+1,1],[x,1],[x,0]]]}


def test_roi_outside_explicit_no_clipping_and_id_collisions():
    record={'acquisition_id':'example','timestamp_utc':'2021-10-12T11:07:16.616Z','footprint':rectangle(),'roi':rectangle(.5)}
    with pytest.raises(ValueError,match='ROI outside'):validate_batch([record])
    rows,warnings=validate_batch([record],'allow')
    assert rows[0]['roi']==record['roi'] and warnings[0]['no_clipping']
    with pytest.raises(ValueError,match='colliding'):validate_batch([{**record,'roi':None,'acquisition_id':'a b'},{**record,'roi':None,'acquisition_id':'a_b'}])


def test_timestamp_and_interval_validated_without_aperture_inference():
    record={'acquisition_id':'x','timestamp_utc':'2021-10-12T11:07:16.616Z','start_utc':'2021-10-12T11:07:17Z','end_utc':'2021-10-12T11:07:18Z'}
    with pytest.raises(ValueError,match='precedes'):validate_batch([record])
    with pytest.raises(ValueError,match='timezone'):validate_batch([{**record,'timestamp_utc':'2021-10-12T11:07:16'}])
    with pytest.raises(ValueError,match='string acquisition_id'):validate_batch([{'acquisition_id':123,'timestamp_utc':'2021-10-12T11:07:16Z'}])


def test_invalid_input_precedes_transport_creation(tmp_path,monkeypatch):
    import run_block32_frf_client as cli
    def forbidden(*args,**kwargs):raise AssertionError('Transport created before validation')
    monkeypatch.setattr(cli,'Transport',forbidden)
    with pytest.raises(SystemExit):cli.main(['--acquisition-id','bad','--timestamp-utc','2021-10-12T11:07:16','--output',str(tmp_path/'out')])


def test_live_requires_named_tranche_before_any_transport(tmp_path,monkeypatch):
    import run_block32_frf_client as cli
    monkeypatch.setattr(cli,'Transport',lambda *a,**k:pytest.fail('unexpected transport'))
    with pytest.raises(SystemExit):cli.main(['--mode','fetch','--acquisition-id','event','--timestamp-utc','2021-10-12T11:07:16Z','--output',str(tmp_path/'out')])


def test_planner_and_time_only_empty_cache_dossier(tmp_path,monkeypatch):
    from frf_client.operational import PlanningTransport,plan,execution_summary
    from frf_client.client import Client
    from frf_client.inputs import validate
    cfg={'families':['waves'],'wave_instruments':['new'],'time_tolerance_seconds':{'waves':3600},'event_context_seconds':7200,'accepted_qc_flags':[1],'accept_unknown_qc':False}
    t=PlanningTransport(tmp_path/'cache');acq=validate({'acquisition_id':'time','timestamp_utc':'2021-10-12T11:07:16.616Z'})
    with pytest.raises(FetchError):t.get(URL)
    c=Client(t,cfg);monkeypatch.setattr(c,'discover',lambda a:[])
    c.run([acq],tmp_path/'out')
    execution_summary([acq],tmp_path/'out',[],t,t.state.copy())
    assert plan([acq],cfg,t)['actual_http_transactions']==0
    assert t.state['transactions']==0
    assert 'NOT physical representativity' in (tmp_path/'out/SUMMARY.md').read_text()
    coverage=json.loads((tmp_path/'out/time/SEARCH_COVERAGE.json').read_text())[0]
    assert coverage['status']=='incomplete_search'


def test_gross_nominal_longitude_conflict_not_automatically_flipped():
    from frf_client.client import historical_position
    attrs={'NC_GLOBAL':{'geospatial_lat_min':36.1872375,'geospatial_lon_min':-75.7428906}}
    result=historical_position(attrs,{'latitude':np.asarray(36.1872331),'longitude':np.asarray(75.7428842)},0)
    assert result['lon_lat'] is None and result['gross_coordinate_conflict']
    assert result['dated_coordinate_candidate_lon_lat'][0]==75.7428842
    assert result['global_nominal_lon_lat'][0]==-75.7428906


def test_missing_qc_flag_not_called_measured_failure(tmp_path):
    import csv
    from frf_client.output import dossier
    from frf_client.inputs import validate
    from frf_client.data import mask_values
    arrays={'time':np.array([0.]),'waveHs':np.array([1.]),'qcFlagE':np.array([-999.])}
    attrs={'time':{'units':'seconds since 1970-01-01 00:00:00'},'qcFlagE':{'_FillValue':-999}}
    loaded={'metadata':{'attributes':attrs,'source':URL},'arrays':arrays,'masks':{k:mask_values(v,attrs.get(k,{})) for k,v in arrays.items()},'times':arrays['time'],'coverage':{}}
    config={'time_tolerance_seconds':{'waves':3600},'accepted_qc_flags':[1],'accept_unknown_qc':False}
    dossier(validate({'acquisition_id':'unknown','timestamp_utc':'1970-01-01T00:00:00Z'}),[{'family':'waves','instrument':'fixture','source':URL,'loaded':loaded}],[],[],config,tmp_path,Transport(tmp_path/'cache',offline=True))
    rows=list(csv.DictReader((tmp_path/'unknown/OBSERVATIONS.csv').open()))
    selected=next(r for r in rows if r['variable']=='waveHs' and r['role']=='nearest_context')
    assert selected['status']=='qc_unknown' and selected['qc_flag']=='' and selected['representative_eligible']=='False'

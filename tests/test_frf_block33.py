"""Behavior regressions: no real network, private cache or radar dependency."""
import csv
import io
import json
from pathlib import Path
import numpy as np
import pytest
from frf_client.client import Client, historical_position
from frf_client.data import spectral_summary, utc, mask_values
from frf_client.inputs import validate
from frf_client.output import dossier
from frf_client.transport import Transport, FetchError

URL = "https://chldata.erdc.dren.mil/thredds/dodsC/frf/new_202402.nc"
FIXTURES = Path(__file__).parent / "fixtures/frf_block33"


@pytest.fixture(autouse=True)
def prohibit_actual_network(monkeypatch):
    import urllib.request
    def forbidden(*args,**kwargs):raise AssertionError("Actual network prohibited in Block33")
    monkeypatch.setattr(urllib.request.OpenerDirector,"open",forbidden)


def config():
    return {"families":["waves"],"wave_instruments":["new-gauge"],
            "event_context_seconds":7200,"time_tolerance_seconds":{"waves":3600,"wind":1800},
            "accepted_qc_flags":[1],"accept_unknown_qc":False}


class Recorded:
    offline=True
    state={"transactions":0,"bytes":0,"max_transactions":40}
    def __init__(self, directory): self.directory=directory; self.calls=[]
    def get(self,url):
        self.calls.append(url)
        if url.endswith(".das"): return (FIXTURES/"new.das").read_bytes()
        if url.endswith(".dds"): return (FIXTURES/"new.dds").read_bytes()
        raise FetchError("unexpected_observations_requested")


def test_inventory_new_product_metadata_only(tmp_path,monkeypatch):
    from frf_client.catalog import catalog
    transport=Recorded(tmp_path)
    # Fixture catalog is parsed by the real discovery parser, not a fabricated product.
    original=transport.get
    transport.get=lambda url: (FIXTURES/"catalog.xml").read_bytes() if url.endswith("catalog.xml") else original(url)
    product=catalog(transport,"https://chldata.erdc.dren.mil/thredds/catalog/new/catalog.xml")["products"][0]
    product.update(family="waves",instrument="new-gauge",month="202402",source=URL)
    client=Client(transport,config())
    monkeypatch.setattr(client,"discover",lambda acquisitions:[product])
    client.run([validate({"acquisition_id":"new","timestamp_utc":"2024-02-15T12:00:00Z"})],tmp_path/"out",mode="inventory")
    assert not client.errors
    assert any(p.get("status")=="metadata_verified_not_observations_fetched" for p in client.inventory)
    assert not any(".ascii" in url for url in transport.calls)


def test_missing_spectrum_is_not_calm():
    result=spectral_summary([.05,.1],[1,2],[False,False])
    assert result["m0_m2"] is None and result["Hm0_m"] is None
    assert result["status"]=="no_valid_spectral_bins"


def test_zero_energy_has_no_peak():
    result=spectral_summary([.05,.1],[0,0],[True,True])
    assert result["Hm0_m"]==0 and result["Tp_bin_s"] is None


@pytest.mark.parametrize("frequencies,widths",[([.05,float('nan')],None),([.05,.1],[.01,float('nan')]),([0,.1],None)])
def test_invalid_spectral_coordinates_refused(frequencies,widths):
    with pytest.raises(ValueError): spectral_summary(frequencies,[1,2],[True,True],widths)


def test_deployment_end_invalidates_position():
    attrs={"time":{"units":"seconds since 1970-01-01 00:00:00"},
           "NC_GLOBAL":{"deployment_end":"2021-01-01T00:00:00Z"}}
    result=historical_position(attrs,{"time":np.array([utc("2022-01-01T00:00:00Z").timestamp()]),
                                    "latitude":np.asarray(36.2),"longitude":np.asarray(-75.7)},0)
    assert result["deployment_conflict"] and result["lon_lat"] is None


class Response(io.BytesIO):
    status=200
    def __init__(self,body,length=None):
        super().__init__(body); self.headers={} if length is None else {"Content-Length":str(length)}


class Opener:
    def __init__(self,responses): self.responses=list(responses)
    def open(self,*args,**kwargs): return self.responses.pop(0)


def test_silent_truncation_rejected_and_resumable(tmp_path):
    transport=Transport(tmp_path,opener=Opener([Response(b"short",20),Response(b"complete",8)]),failure_ttl=0,rate_seconds=0)
    with pytest.raises(FetchError,match="truncated_response"): transport.get(URL)
    metadata=json.loads(transport._paths(URL)[1].read_text())
    assert metadata["status"]=="truncated_response" and metadata["bytes_received"]==5
    assert not transport._paths(URL)[0].exists()
    assert transport.get(URL)==b"complete"
    assert transport.state["transactions"]==2 and transport.state["bytes"]==13


def poly(x,y,w=.02):
    return {"type":"Polygon","coordinates":[[[x,y],[x+w,y],[x+w,y+w],[x,y+w],[x,y]]]}


def test_qc_selected_gauge_has_own_distance(tmp_path):
    target=utc("2024-02-15T12:00:00Z").timestamp()
    arrays={"time":np.array([target,target+60]),"windSpeed":np.array([5.,6.]),"qcFlagS":np.array([4,1]),"id":np.array([10,20])}
    attrs={"time":{"units":"seconds since 1970-01-01 00:00:00"},"NC_GLOBAL":{"summary":"1 = 10 36.205 -75.745 5 first\n2 = 20 36.215 -75.735 6 second"}}
    loaded={"metadata":{"attributes":attrs,"source":URL},"arrays":arrays,"masks":{k:mask_values(v,attrs.get(k,{})) for k,v in arrays.items()},"times":arrays["time"],"coverage":{}}
    acquisition=validate({"acquisition_id":"switch","timestamp_utc":"2024-02-15T12:00:00Z","footprint":poly(-75.75,36.20),"roi":poly(-75.75,36.20,.01)})
    dossier(acquisition,[{"family":"wind","instrument":"derived","source":URL,"loaded":loaded}],[],[],config(),tmp_path,Transport(tmp_path/"cache",offline=True))
    rows=list(csv.DictReader((tmp_path/"switch/OBSERVATIONS.csv").open()))
    selected=next(r for r in rows if r["variable"]=="windSpeed" and r["role"]=="nearest_qc")
    distances=list(csv.DictReader((tmp_path/"switch/DISTANCES.csv").open()))
    position=next(d for d in distances if d["position_id"]==selected["position_id"])
    assert json.loads(position["lon_lat_json"])==[-75.735,36.215]
    assert position["footprint_inside"]=="True" and position["roi_inside"]=="False"


def wave_product(month,times,values,frequencies=None):
    source=URL.replace("202402",month)
    arrays={"time":np.asarray(times),"waveHs":np.asarray(values),"qcFlagE":np.ones(len(times))}
    if frequencies is not None:
        arrays.update(waveFrequency=np.array(frequencies),waveEnergyDensity=np.ones((len(times),len(frequencies))))
    attrs={"time":{"units":"seconds since 1970-01-01 00:00:00"}}
    return {"family":"waves","instrument":"new-gauge","month":month,"source":source,"services":{"OpenDAP":source},
            "loaded":{"metadata":{"attributes":attrs,"source":source},"arrays":arrays,"masks":{k:mask_values(v,{}) for k,v in arrays.items()},"times":arrays["time"],"coverage":{},"original_indices":np.arange(len(times))}}


def test_adjacent_month_best_observation_and_distinct_grids(tmp_path,monkeypatch):
    target=utc("2024-03-01T00:00:10Z").timestamp()
    products=[wave_product("202402",[target-20],[1.2],[.05,.10]),wave_product("202403",[target+1800],[2.3],[.04,.07,.12])]
    client=Client(Transport(tmp_path/"cache",offline=True),config())
    monkeypatch.setattr(client,"discover",lambda acquisitions:products)
    monkeypatch.setattr(client,"load",lambda p,*a,**k:p["loaded"])
    client.run([validate({"acquisition_id":"boundary","timestamp_utc":"2024-03-01T00:00:10Z"})],tmp_path/"out")
    base=tmp_path/"out/boundary"
    rows=list(csv.DictReader((base/"OBSERVATIONS.csv").open()))
    chosen=[r for r in rows if r["variable"]=="waveHs" and r["role"]=="nearest_qc"]
    assert len(chosen)==1 and float(chosen[0]["value"])==1.2
    tensors=json.loads((base/"TENSORS.json").read_text())
    grids=[v["variables"]["waveFrequency"]["raw_values"] for v in tensors.values()]
    assert [.05,.10] in grids and [.04,.07,.12] in grids


def test_far_events_do_not_request_intervening_observations(tmp_path):
    target=utc("2024-02-01T12:00:00Z").timestamp()
    times=target+np.arange(3000)*600
    class Subsets:
        def __init__(self): self.calls=[]
        def get(self,url):
            self.calls.append(url)
            if url.endswith(".das"): return (FIXTURES/"new.das").read_bytes()
            if url.endswith(".dds"): return b'Dataset { Float64 time[t = 3000]; Float32 waveHs[t = 3000]; } new;'
            if url.endswith(".ascii?time"): return ("Dataset {};\n--------------------\ntime[3000]\n"+", ".join(map(str,times))+"\n").encode()
            import re
            lo,hi=map(int,re.search(r"time\[(\d+):1:(\d+)\]",url).groups())
            n=hi-lo+1
            return (f"Dataset {{}};\n--------------------\ntime[{n}]\n"+", ".join(map(str,times[lo:hi+1]))+f"\nwaveHs[{n}]\n"+", ".join(["1"]*n)+"\n").encode()
    transport=Subsets();client=Client(transport,config())
    a=[validate({"acquisition_id":str(j),"timestamp_utc":datetime_utc}) for j,datetime_utc in enumerate(["2024-02-01T12:00:00Z","2024-02-21T12:00:00Z"])]
    p={"source":URL,"services":{"OpenDAP":URL},"family":"waves","instrument":"new-gauge","month":"202402"}
    loaded=client.load(p,a)
    assert len(loaded["times"])<100
    assert len([url for url in transport.calls if ".ascii?time[" in url])==2


@pytest.mark.parametrize("timestamp,expected",[
    ("2024-03-01T00:00:10Z",["202403","202402"]),
    ("2024-02-29T23:59:50Z",["202403","202402"]),
    ("2023-12-31T23:59:50Z",["202401","202312"]),
    ("2024-01-01T00:00:10Z",["202401","202312"]),
    ("2023-03-01T00:00:10Z",["202303","202302"]),
])
def test_calendar_months_from_context(timestamp,expected):
    from frf_client.temporal import months_needed
    assert months_needed([{"timestamp_utc":timestamp}],config(),"waves")==expected


def test_tolerance_larger_than_context_and_window_union():
    from frf_client.temporal import months_needed,event_windows
    cfg=config();cfg["event_context_seconds"]=60;cfg["time_tolerance_seconds"]["waves"]=3600
    assert months_needed([{"timestamp_utc":"2024-03-01T00:30:00Z"}],cfg,"waves")==["202403","202402"]
    dates=[{"timestamp_utc":v} for v in ["2024-02-10T00:00:00Z","2024-02-10T00:30:00Z","2024-02-20T00:00:00Z"]]
    assert len(event_windows(dates,cfg,"waves"))==2


def test_real_discovery_parser_requests_adjacent_years(tmp_path):
    from frf_client.catalog import ROOT
    prefix='https://chldata.erdc.dren.mil/thredds/catalog/'
    def listing(refs=(),product=None):
        text='<catalog xmlns="http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0" xmlns:xlink="http://www.w3.org/1999/xlink"><service serviceType="OpenDAP" base="/thredds/dodsC/"/>'
        for name,path in refs:text+=f'<catalogRef name="{name}" xlink:href="{path}"/>'
        if product:text+=f'<dataset name="observed_{product}.nc" urlPath="frf/observed_{product}.nc"/>'
        return (text+'</catalog>').encode()
    mapping={ROOT:listing([('oceanography',prefix+'ocean.xml')]),prefix+'ocean.xml':listing([('waves',prefix+'waves.xml')]),prefix+'waves.xml':listing([('new-gauge',prefix+'instrument.xml')]),prefix+'instrument.xml':listing([('2023',prefix+'2023.xml'),('2024',prefix+'2024.xml')]),prefix+'2023.xml':listing(product='202312'),prefix+'2024.xml':listing(product='202401')}
    transport=Recorded(tmp_path);transport.get=lambda url:mapping[url]
    products=Client(transport,config()).discover([{'timestamp_utc':'2024-01-01T00:00:10Z'}])
    assert {p['month'] for p in products}=={'202312','202401'}


@pytest.mark.parametrize("conflict",[False,True])
def test_duplicates_not_averaged(tmp_path,conflict):
    target=utc('2024-03-01T00:00:00Z').timestamp()
    products=[wave_product('202402',[target],[1.2]),wave_product('202403',[target],[2.3 if conflict else 1.2])]
    acq=validate({'acquisition_id':'dups','timestamp_utc':'2024-03-01T00:00:00Z'})
    dossier(acq,products,[],[],config(),tmp_path,Transport(tmp_path/'cache',offline=True))
    rows=list(csv.DictReader((tmp_path/'dups/OBSERVATIONS.csv').open()))
    chosen=next(r for r in rows if r['variable']=='waveHs' and r['role']=='nearest_qc')
    assert float(chosen['value']) in (1.2,2.3)
    assert chosen['duplicate_status']==('conflicting_duplicate' if conflict else 'consistent_duplicate')
    assert chosen['representative_eligible']==str(not conflict)
    dups=json.loads((tmp_path/'dups/DUPLICATE_SAMPLES.json').read_text())
    assert len(dups[0]['samples'])==2


def test_missing_segment_explicit_incomplete(tmp_path,monkeypatch):
    target=utc('2024-03-01T00:00:10Z').timestamp();p=wave_product('202403',[target+30],[1.])
    p['loaded']['coverage']['observations_in_context_retrieved']=True
    client=Client(Transport(tmp_path/'cache',offline=True),config())
    monkeypatch.setattr(client,'discover',lambda a:[p]);monkeypatch.setattr(client,'load',lambda p,*a,**k:p['loaded'])
    client.run([validate({'acquisition_id':'missing','timestamp_utc':'2024-03-01T00:00:10Z'})],tmp_path/'out')
    coverage=json.loads((tmp_path/'out/missing/SEARCH_COVERAGE.json').read_text())[0]
    assert coverage['status']=='incomplete_search' and coverage['missing_or_unverified_months']==['202402']


def test_inventory_one_malformed_does_not_cancel_another(tmp_path,monkeypatch):
    product={'family':'waves','instrument':'new-gauge','month':'202402','source':URL,'services':{'OpenDAP':URL}}
    good={**product,'source':URL+'good','services':{'OpenDAP':URL+'good'}}
    client=Client(Recorded(tmp_path),config());original=client.transport.get
    def get(url):
        if url==URL+'.das':raise FetchError('path_not_found')
        return original(url)
    client.transport.get=get;monkeypatch.setattr(client,'discover',lambda a:[product,good])
    client.run([validate({'acquisition_id':'inventory','timestamp_utc':'2024-02-15T12:00:00Z'})],tmp_path/'out',mode='inventory')
    assert len(client.errors)==1
    assert any(p.get('source')==URL+'good' and p.get('status')=='metadata_verified_not_observations_fetched' for p in client.inventory)


@pytest.mark.parametrize('kind',['missing','zero','partial','complete'])
def test_spectral_states_numerically(kind):
    mask={'missing':[False,False],'zero':[True,True],'partial':[True,False],'complete':[True,True]}[kind]
    energy=[0,0] if kind=='zero' else [1,2]
    result=spectral_summary([.05,.1],energy,mask,[.01,.02])
    expected={'missing':'no_valid_spectral_bins','zero':'valid_zero_energy','partial':'partial_spectrum','complete':'complete_spectrum'}[kind]
    assert result['status']==expected
    assert result['m0_m2']==pytest.approx(.01 if kind=='partial' else .05 if kind=='complete' else 0) if kind!='missing' else result['m0_m2'] is None
    assert result['valid_mask']==mask and result['bin_width_origin']=='provided'


def test_missing_spectrum_propagates_json_csv_report(tmp_path):
    target=utc('2024-02-15T12:00:00Z').timestamp();p=wave_product('202402',[target],[1.],[.05,.10])
    p['loaded']['arrays']['waveEnergyDensity'][:]=np.nan
    p['loaded']['masks']['waveEnergyDensity'][:]=False
    dossier(validate({'acquisition_id':'empty','timestamp_utc':'2024-02-15T12:00:00Z'}),[p],[],[],config(),tmp_path,Transport(tmp_path/'cache',offline=True))
    base=tmp_path/'empty'
    assert json.loads((base/'SPECTRAL_SUMMARIES.json').read_text())[0]['Hm0_m'] is None
    summary=list(csv.DictReader((base/'SPECTRAL_SUMMARIES.csv').open()))[0]
    assert summary['Hm0_m']=='' and summary['status']=='no_valid_spectral_bins'
    assert 'no_valid_spectral_bins' in (base/'REPORT.md').read_text()
    rows=list(csv.DictReader((base/'OBSERVATIONS.csv').open()))
    assert next(r for r in rows if r['variable']=='waveEnergyDensity')['spectral_status']=='no_valid_spectral_bins'


@pytest.mark.parametrize('index,position',[(0,[-75.745,36.205]),(1,[-75.735,36.215])])
def test_sample_coordinates_follow_time(index,position):
    result=historical_position({}, {'latitude':np.array([36.205,36.215]),'longitude':np.array([-75.745,-75.735])},index)
    assert result['lon_lat']==position and 'nominal' in result['status']


def test_missing_position_and_unknown_wind_id():
    assert historical_position({}, {},0)['lon_lat'] is None
    arrays={'id':np.array([999]),'latitude':np.asarray(36.2),'longitude':np.asarray(-75.7)}
    assert historical_position({},arrays,0,'wind')['lon_lat'] is None


@pytest.mark.parametrize('length',[8,None])
def test_complete_and_unknown_http_length(tmp_path,length):
    transport=Transport(tmp_path,opener=Opener([Response(b'complete',length)]),rate_seconds=0)
    assert transport.get(URL)==b'complete' and transport.state['bytes']==8


def test_interrupted_stream_bytes_and_resume(tmp_path):
    import http.client
    class Broken(Response):
        def read(self,n=-1):raise http.client.IncompleteRead(b'part',20)
    transport=Transport(tmp_path,opener=Opener([Broken(b'',24),Response(b'ok',2)]),failure_ttl=0,rate_seconds=0)
    with pytest.raises(FetchError,match='truncated_response'):transport.get(URL)
    assert transport.state['bytes']==4 and not transport._paths(URL)[0].exists()
    assert transport.get(URL)==b'ok' and transport.state['bytes']==6


def test_chunked_content_length_not_compared(tmp_path):
    response=Response(b'complete',999);response.headers['Transfer-Encoding']='chunked'
    transport=Transport(tmp_path,opener=Opener([response]),rate_seconds=0)
    assert transport.get(URL)==b'complete'
    metadata=json.loads(transport._paths(URL)[1].read_text())
    assert metadata['content_length'] is None and metadata['transfer_encoding']=='chunked'


def test_capped_stream_not_cached(tmp_path):
    transport=Transport(tmp_path,opener=Opener([Response(b'0123456789')]),max_bytes=5,max_response=5,rate_seconds=0)
    with pytest.raises(FetchError,match='limit'):transport.get(URL)
    assert transport.state['bytes']==5 and transport.state['transactions']==1
    assert json.loads(transport._paths(URL)[1].read_text())['status']!='ok'


def test_audit_distinguishes_unavailable_unresolved_mismatch(tmp_path):
    from run_block33_frf_verification import audit_entries,ROOT,digest
    path=tmp_path/'small.txt';path.write_bytes(b'fixture')
    entries=[{'path':path.relative_to(ROOT).as_posix(),'sha256':digest(b'fixture')},
             {'path':path.relative_to(ROOT).as_posix(),'sha256':digest(b'other')},
             {'path':'duck_frf/Block33_frf_offline_correction/nonexistent','sha256':'x'},
             {'path':'C:/old_project/missing','sha256':'x'}]
    assert [r['status'] for r in audit_entries(entries)]==['hash_verified','mismatch','file_unavailable','unresolved_path']


@pytest.mark.parametrize('timestamp,months',[
    ('2024-02-29T23:59:50Z',('202402','202403')),
    ('2023-12-31T23:59:50Z',('202312','202401')),
    ('2024-01-01T00:00:10Z',('202312','202401')),
])
def test_cross_month_previous_next_numerically(tmp_path,timestamp,months):
    target=utc(timestamp).timestamp()
    products=[wave_product(months[0],[target-20],[1.2]),wave_product(months[1],[target+30],[2.3])]
    dossier(validate({'acquisition_id':'calendar','timestamp_utc':timestamp}),products,[],[],config(),tmp_path,Transport(tmp_path/'cache',offline=True))
    rows=list(csv.DictReader((tmp_path/'calendar/OBSERVATIONS.csv').open()))
    rows={r['role']:r for r in rows if r['variable']=='waveHs'}
    assert float(rows['previous_qc']['offset_seconds'])==-20
    assert float(rows['next_qc']['offset_seconds'])==30
    assert float(rows['nearest_qc']['value'])==1.2


def test_new_product_empty_cache_fetch_simulated(tmp_path,monkeypatch):
    target=utc('2024-02-15T12:00:00Z').timestamp()
    transport=Recorded(tmp_path/'empty');transport.directory.mkdir()
    original=transport.get
    def get(url):
        if '.ascii?' not in url:return original(url)
        transport.calls.append(url)
        text=f'Dataset {{}};\n--------------------\ntime[2]\n{target-60}, {target+60}\n'
        if not url.endswith('.ascii?time'):text+='waveHs[2]\n1.2, 1.4\n'
        return text.encode()
    transport.get=get;cfg=config();cfg['accept_unknown_qc']=True
    client=Client(transport,cfg)
    product={'family':'waves','instrument':'new-gauge','month':'202402','source':URL,'services':{'OpenDAP':URL}}
    monkeypatch.setattr(client,'discover',lambda a:[product])
    client.run([validate({'acquisition_id':'empty_cache','timestamp_utc':'2024-02-15T12:00:00Z'})],tmp_path/'out',mode='fetch')
    assert not client.errors
    rows=list(csv.DictReader((tmp_path/'out/empty_cache/OBSERVATIONS.csv').open()))
    nearest=next(r for r in rows if r['variable']=='waveHs' and r['role']=='nearest_qc')
    assert float(nearest['value'])==1.2 and int(nearest['original_sample_index'])==0
    assert not any('waveTp' in u for u in transport.calls)


def test_explicit_absolute_path_remapping(tmp_path):
    from frf_client.provenance import audit
    (tmp_path/'small').write_bytes(b'content')
    entries=[{'path':'C:/historical/root/small','sha256':__import__('hashlib').sha256(b'content').hexdigest()}]
    assert audit(entries,tmp_path)[0]['status']=='unresolved_path'
    assert audit(entries,tmp_path,{'C:/historical/root':'.'})[0]['status']=='hash_verified'

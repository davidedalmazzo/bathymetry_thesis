"""Offline checks distinct from the live catalogue/FRF verification."""
import json
import numpy as np
import pytest
from shapely.geometry import Polygon, MultiPolygon, mapping
from s1_spatial import normalize, next_page, representatives, axial_difference, utc, dispersion_sensitivity, catalogue_pages, deduplicate_entries, quicklook_url
from s1_duck_selection import catalogue_url, BASE
from frf_client.client import Client


def entry(uuid='a', footprint=None):
    return {'Id':uuid,'Name':'S1A_IW_SLC__1SDV_20211004T230636_20211004T230703_039976_04BB45_AAAA.SAFE',
        'ContentDate':{'Start':'2021-10-04T23:06:36.304000Z','End':'2021-10-04T23:07:03.252000Z'},
        'GeoFootprint':footprint,'Online':True,'Attributes':[]}


def test_utc_fraction_timezone_and_query_bounds():
    r=normalize(entry(),{'type':'Polygon','coordinates':[[[0,0],[1,0],[1,1],[0,0]]]})
    assert utc(r['start_utc']).microsecond == 304000
    with pytest.raises(ValueError):utc('2021-10-04T23:06:36')
    from urllib.parse import unquote_plus
    query=unquote_plus(catalogue_url(json.loads((BASE/'CONFIG.json').read_text())))
    assert 'Start ge 2021-10-01T00:00:00Z' in query
    assert 'Start lt 2021-11-01T00:00:00Z' in query
    assert 'POLYGON' in query


def test_actual_nextlink_capitalization_and_endpoint_safety():
    url='https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$skip=100'
    assert next_page({'@OData.nextLink':url})==url
    assert next_page({'value':[]}) is None
    with pytest.raises(ValueError):next_page({'@odata.nextLink':'https://evil.example/odata/v1/Products'})
    with pytest.raises(ValueError):next_page({'@odata.nextLink':'https://catalogue.dataspace.copernicus.eu/odata/v1/Products(a)/$value'})


def test_pagination_empty_duplicates_and_cycle():
    u='https://catalogue.dataspace.copernicus.eu/odata/v1/Products'
    class T:
        def __init__(self,pages):self.pages=pages
        def get(self,url):return json.dumps(self.pages[url]).encode()
    t=T({u:{'value':[entry()],'@odata.nextLink':u+'?$skip=1'},u+'?$skip=1':{'value':[entry()]}})
    pages=list(catalogue_pages(t,u));unique,dup=deduplicate_entries([e for p in pages for e in p['payload']['value']])
    assert len(unique)==1 and dup==['a']
    assert list(catalogue_pages(T({u:{'value':[]}}),u))[0]['payload']['value']==[]
    with pytest.raises(ValueError):list(catalogue_pages(T({u:{'value':[],'@odata.nextLink':u}}),u))
    with pytest.raises(ValueError):deduplicate_entries([entry(),{**entry(),'Online':False}])


def test_polygon_holes_multipolygon_missing_preserved():
    p=Polygon([(-76,36),(-75,36),(-75,37),(-76,37)],holes=[[(-75.8,36.2),(-75.6,36.2),(-75.6,36.4),(-75.8,36.4)]])
    geo=mapping(MultiPolygon([p]))
    r=normalize(entry(footprint=geo),mapping(Polygon([(-75.8,36.2),(-75.6,36.2),(-75.6,36.4),(-75.8,36.4)])))
    assert r['footprint']==geo and r['marine_screening_fraction']==pytest.approx(0,abs=1e-12)
    r=normalize(entry(),mapping(p))
    assert r['footprint'] is None and r['marine_screening_fraction'] is None
    assert r['local_incidence_deg'] is None and r['processing_version'] is None


def test_dedup_versions_not_independent_acquisitions():
    marine=mapping(Polygon([(0,0),(1,0),(1,1),(0,1)]))
    a=normalize(entry('a'),marine); b=normalize(entry('b'),marine)
    a['modification_utc']='2021-01-01';b['modification_utc']='2025-01-01'
    assert len(representatives([a,b]))==1
    assert representatives([a,b])[0]['uuid']=='b'
    assert representatives([])==[]


@pytest.mark.parametrize('from_deg,axis,expected',[(90,90,0),(270,90,0),(250,70,0),(80,90,10),(0,170,10)])
def test_measured_from_to_toward_and_axial_convention(from_deg,axis,expected):
    assert axial_difference((from_deg+180)%360,axis)==pytest.approx(expected)


@pytest.mark.parametrize('k,h',[(.04,5),(.06,12),(.02,25)])
def test_analytic_sensitivities_finite_difference(k,h):
    g=9.80665; result=dispersion_sensitivity(k,h); w=result['omega_rad_s']
    # Toy inversion ONLY for verifying derivatives; not applied to any actual SAR scene.
    depth=lambda kk,ww: np.arctanh(ww**2/(g*kk))/kk
    eps=1e-6
    dk=(depth(k*(1+eps),w)-depth(k*(1-eps),w))/(2*k*eps)
    dw=(depth(k,w*(1+eps))-depth(k,w*(1-eps)))/(2*w*eps)
    assert result['dh_dk_fixed_omega_m2']==pytest.approx(dk,rel=1e-7)
    assert result['dh_domega_fixed_k_m_s']==pytest.approx(dw,rel=1e-7)
    for key in ('dh_dk_fixed_omega_m2','dh_domega_fixed_k_m_s'):assert np.isfinite(result[key])


def test_frf_projection_uses_existing_client_and_validates_names():
    c=Client(None,{'observation_variables':{'waves':['waveHs','waveTp','qcFlagE']}})
    assert c.config['observation_variables']['waves'][1]=='waveTp'
    with pytest.raises(ValueError):Client(None,{'observation_variables':{'waves':['inventedWaveTp']}})
    with pytest.raises(ValueError):Client(None,{'observation_variables':{'radar':['signal']}})


def test_monthly_scalar_projection_in_existing_loader(monkeypatch):
    import frf_client.client as module
    attributes={'time':{'units':'seconds since 1970-01-01 00:00:00'}}
    shapes={'time':[3],'waveHs':[3],'qcFlagE':[3],'nominalDepth':[],'waveEnergyDensity':[3,2]}
    monkeypatch.setattr(module,'metadata',lambda *a:{'attributes':attributes,'shapes':shapes,'source':'https://example.test/x'})
    class T:
        def __init__(self):self.urls=[]
        def get(self,url):
            self.urls.append(url)
            if url.endswith('?time'):return b'Dataset {};\n--------------------\ntime[3]\n0, 60, 120\n'
            return b'Dataset {};\n--------------------\ntime[3]\n0, 60, 120\nwaveHs[3]\n1, 2, 3\nqcFlagE[3]\n1, 1, 1\nnominalDepth, 17\n'
    cfg={'time_tolerance_seconds':{'waves':1},'event_context_seconds':1,'monthly_scalar_subset':True,
         'observation_variables':{'waves':['waveHs','qcFlagE','nominalDepth']}}
    acq=[{'timestamp_utc':'1970-01-01T00:01:00Z'}];product={'source':'https://example.test/x','family':'waves'}
    t=T();loaded=Client(t,cfg).load(product,acq)
    assert loaded['times'].tolist()==[0,60,120]
    assert 'waveHs[0:1:2]' in t.urls[-1] and 'waveEnergyDensity' not in t.urls[-1]
    assert loaded['coverage']['subset_scope']=='monthly scalar/QC vectors only'
    bad={**cfg,'observation_variables':{'waves':['waveEnergyDensity']}}
    with pytest.raises(ValueError,match='spectral'):Client(T(),bad).load(product,acq)


def test_complete_survey_traverses_all_chunks_before_filter(monkeypatch):
    import re
    import frf_client.survey as module
    meta={'source':'https://example.test/s','shapes':{n:[6] for n in ('lat','lon','elevation','time','profileNumber')},
          'attributes':{'NC_GLOBAL':{'geospatial_vertical_origin':'NAVD88'}}}
    monkeypatch.setattr(module,'metadata',lambda *a:meta)
    class T:
        def __init__(self):self.urls=[]
        def get(self,url):
            self.urls.append(url);lo,hi=map(int,re.search(r'\[(\d+):1:(\d+)\]',url).groups());count=hi-lo+1
            return ('Dataset {};\n--------------------\n'+''.join(n+f'[{count}]\n'+', '.join(str(v) for v in values[lo:hi+1])+'\n' for n,values in
               {'lat':[0]*6,'lon':list(range(6)),'elevation':[-3]*6,'time':list(range(6)),'profileNumber':[1]*6}.items())).encode()
    t=T();region=mapping(Polygon([(2.5,-1),(6,-1),(6,1),(2.5,1)]))
    result=module.fetch_complete_points(t,{},region,chunk_size=2)
    assert len(t.urls)==3 and result['all_indices_traversed']
    assert [p['source_index'] for p in result['points']]==[3,4,5]
    assert result['source_valid_point_count']==6 and result['vertical_datum']=='NAVD88'


def test_windows_persistence_retry_is_not_http_retry(monkeypatch,tmp_path):
    import frf_client.transport as module
    from pathlib import Path
    original=Path.replace;calls=[]
    def transient(self,target):
        calls.append(1)
        if len(calls)==1:raise PermissionError('transient sharing violation')
        return original(self,target)
    monkeypatch.setattr(Path,'replace',transient);monkeypatch.setattr(module.time,'sleep',lambda *a:None)
    path=tmp_path/'state.json';module.save_json(path,{'transactions':7})
    assert len(calls)==2 and json.loads(path.read_text())['transactions']==7


def test_inline_scalar_boundary_and_scalar_only_in_shared_dap_parser():
    from frf_client.data import ascii_arrays
    a=ascii_arrays('Dataset {};\n--------------------\na[2]\n1, 2\nnominalDepth, 17\n')
    assert a['a'].tolist()==[1,2] and a['nominalDepth']==17
    assert ascii_arrays('Dataset {};\n--------------------\nnominalDepth, 17\n')['nominalDepth']==17


def test_preview_never_follows_full_product_or_measurement_link():
    asset={'Id':'a','Type':'QUICKLOOK','DownloadLink':'https://catalogue.dataspace.copernicus.eu/odata/v1/Assets(a)/$value'}
    assert quicklook_url(asset)==asset['DownloadLink']
    with pytest.raises(ValueError):quicklook_url({**asset,'DownloadLink':'https://download.dataspace.copernicus.eu/odata/v1/Products(a)/$value'})

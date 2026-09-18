"""Samoa metadata, geometry, bounded ranges and nominal-plan regressions."""
from repository_paths import resolve_historical
import json,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
import run_block28_samoa_preflight as m
from sarpy.io.complex.sicd_elements.SICD import SICDType
from umbra_sar.subaperture import SicdSubapertureContext,image_to_shifted_spectrum
BASE=ROOT/'umbra/samoa/Block28_Samoa_metadata_preflight'
def load(name):return json.loads((BASE/name).read_text())

def test_identity_and_distinct_apertures():
    assert load('IDENTITY.json')['association_verified']
    s=load('SUMMARY.json')
    assert s['SICD_processed_aperture_s']==pytest.approx(2.975363044143692)
    assert s['catalog_duration_s']==3.6
    assert s['CPHD_first_last_TxTime_span_s']==pytest.approx(3.6917706986666667)
    assert s['automatic_download'] is False and s['decision']=='B'
    assert load('CPHD_METADATA.json')['size_matches_listing']

def test_no_sicd_image_or_cphd_signal_range_read():
    layout=load('NITF_SEGMENT_LAYOUT.json');image=next(s for s in layout if s['kind']=='ImageSegments')
    cp=load('CPHD_METADATA.json')
    for log in load('REQUEST_LOG.json'):
        span=log['range']
        if not span:continue
        if log['url'].endswith('_SICD.nitf'):
            assert span[1]<image['data_offset'] or span[0]>=image['data_offset']+image['data_size']
        if log['url'].endswith('_CPHD.cphd'):assert span[1]<cp['signal_block_byte_offset']
    header=(BASE/'raw/nitf_main_header.bin').read_bytes()
    assert m.nitf_segments(header,load('SUMMARY.json')['SICD_size_bytes'])==layout

def test_ignored_range_rejected_before_body(monkeypatch):
    class Response:
        status=200
        headers={'Content-Length':'2551099862'}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):raise AssertionError('MUST NOT READ IGNORED RANGE BODY')
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr(m,'build_opener',lambda *args:Opener())
    monkeypatch.setattr(m.Client,'save',lambda self:None)
    c=m.Client();before=c.state['total_bytes']
    with pytest.raises(RuntimeError,match='honor exact byte range'):
        c.request(m.ENDPOINT+'test.nitf','synthetic_ignored_range',span=(0,359))
    assert c.state['total_bytes']==before

def test_surface_coordinate_axis_not_horizontal_uvect():
    g=load('GEOMETRY.json')
    assert g['band_reselected'] is False and g['Snell_applied'] is False
    assert g['buoy_band_hz']==[.07,.075]
    assert g['buoy_propagation_to_deg']==pytest.approx(20.878036517434737)
    assert g['sicd_surface_LOS_axial_difference_at_ROI_deg']==pytest.approx(39.09561004623198)
    assert abs(g['ROI_image_coordinate_pushforward']['row_surface_bearing_deg']-g['grid_Row_UVect_horizontal_projection_bearing_deg'])>30
    s=SICDType.from_xml_file(str(BASE/'raw/sicd.xml'))
    center,_,_=s.project_ground_to_image_geo([-14.286579014933421,-170.56379591085346,g['surface_HAE_m']])
    a=m.projected_axes(s,center,g['surface_HAE_m'],step=5)
    assert a['row_surface_bearing_deg']==pytest.approx(g['ROI_image_coordinate_pushforward']['row_surface_bearing_deg'],abs=1e-4)

def test_roi_convergence_and_nominal_plans():
    rr=load('ROI_VALID_SUPPORT.json')['projections']
    assert all(r['whole_sampled_roi_within_ValidData'] for r in rr)
    assert abs(rr[0]['minimum_valid_edge_margin_image_plane_m']-rr[1]['minimum_valid_edge_margin_image_plane_m'])<.1
    plans=load('SUBAPERTURE_METADATA_AND_PLANS.json')
    assert [p['look_count'] for p in plans['plans']]==[2,3,2]
    for p in plans['plans']:
        assert p['statistically_independent'] is False
        assert p['col_impulse_width_surface_m_approx']>0
        assert all(b['start']>=plans['support']['start'] and b['stop']<=plans['support']['stop'] for b in p['bands'])

def test_samoa_actual_metadata_fft_sign_numerical():
    s=SICDType.from_xml_file(str(BASE/'raw/sicd.xml'));c=SicdSubapertureContext.from_sicd(s)
    assert c.axis.azimuth_sgn==-1 and c.axis.forward_transform_name=='fft'
    x=np.tile(np.exp(2j*np.pi*3*np.arange(32)/32),(2,1))
    f=image_to_shifted_spectrum(x,axis=c.axis.azimuth_axis,sgn=c.axis.azimuth_sgn)
    assert np.argmax(abs(f[0]))==32//2+3

def test_budget_and_input_hashes():
    state=load('STATE.json');logs=load('REQUEST_LOG.json')
    assert state['transactions']<=20 and state['total_bytes']<=20*1024**2
    assert sum(l['bytes'] for l in logs)==state['total_bytes']
    assert all(l['bytes']<=5*1024**2 for l in logs)
    for p in load('INPUT_PROVENANCE.json'):assert m.sha(resolve_historical(p['path'], ROOT))==p['sha256']

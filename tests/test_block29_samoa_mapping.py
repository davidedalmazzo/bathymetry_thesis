"""PVP/PFA/units/sign/support regressions; no real radar signal tests."""
import json,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
from sarpy.io.phase_history.cphd1_elements.CPHD import CPHDType
from sarpy.io.complex.sicd_elements.SICD import SICDType
from umbra_sar.pfa_time_mapping import parse_pvp_bytes,band_kernel,image_to_ground_wavevector,geometry_jacobian,invert_monotone
from umbra_sar.cross_spectrum import spatial_cross_spectrum
import run_block29_samoa_mapping as m
BASE=m.BASE
def load(name):return json.loads((BASE/name).read_text())

def test_pvp_structured_offsets_integers_endian_and_continuity():
    c=CPHDType.from_xml_file(str(m.B28/'raw/cphd.xml'));p=(BASE/'raw/pvp_block.bin').read_bytes();r=parse_pvp_bytes(p,c)
    assert len(r)==21716 and r.dtype.itemsize==376
    assert r.dtype['SIGNAL'].kind=='i' and r.dtype['PulseNumber'].kind=='u'
    assert r.dtype.fields['SIGNAL'][1]==360 and r.dtype.fields['TxPos'][1]==8
    assert set(np.unique(r['SIGNAL']))=={1}
    assert np.all(np.diff(r['TxTime'])>0)
    with pytest.raises(ValueError,match='truncated'):parse_pvp_bytes(p[:-1],c)

def test_pfa_metadata_geometry_coherence_and_units():
    a=load('PVP_AUDIT.json')
    assert a['all_time_continuity_verified'] and a['required_fields_finite']
    assert a['CPHD_ETag_matches_frozen_public_listing']
    assert a['poly_geometry_equivalent_time_error_max_s']<1e-6
    assert a['ARP_vs_PVP_angle_equivalent_time_error_max_s']<1e-5
    assert a['PFA_scale_geometry_vs_polynomial_max_absolute_residual']<1e-6
    assert 'cycles/m' in a['units']

def test_radial_coupling_of_uniform_col_band_kernel():
    t=np.linspace(0,4,10001);theta=.02-.01*t
    a=band_kernel(theta,t,10.,-.05,.05);b=band_kernel(theta,t,5.,-.05,.05)
    assert a['centre_uniform_output_k_s']==pytest.approx(2.,abs=1e-12)
    assert b['support_duration_s']>1.9*a['support_duration_s']
    with pytest.raises(ValueError,match='outside'):invert_monotone(theta,t,[.1])

def test_inverse_transpose_phase_invariant_with_real_geometry():
    s=SICDType.from_xml_file(str(m.B28/'raw/sicd.xml'));J=geometry_jacobian(s,s.ImageData.SCPPixel.get_array(),s.GeoData.SCP.LLH.HAE)
    kg=np.array([.03,-.017]);ki=J.T@kg
    assert np.allclose(image_to_ground_wavevector(ki,J),kg,rtol=1e-12,atol=1e-12)
    x=np.array([123.,-55.]);assert ki@x==pytest.approx(kg@(J@x))
    assert not np.allclose(J.T@J,np.eye(2)) # cannot replace with rotation

def test_cross_phase_sign_and_conjugate_lobe_known_dynamic():
    rr,cc=np.mgrid[:32,:64];p=2*np.pi*(3*rr/32+5*cc/64)
    reference=1+.15*np.cos(p);secondary=1+.15*np.cos(p-.7)
    cross=spatial_cross_spectrum(reference,secondary)
    # Function conventions and ordering from existing library.
    f1=np.fft.fft2(reference-reference.mean());f2=np.fft.fft2(secondary-secondary.mean());c=f2*np.conj(f1)
    assert np.angle(c[3,5])==pytest.approx(-.7)
    assert np.angle(c[-3,-5])==pytest.approx(.7)
    assert np.allclose(c,np.fft.ifftshift(cross))

def test_gate_freeze_and_no_download():
    cfg=load('CONFIG.json');gate=load('GATE_A.json')
    assert cfg['criteria_frozen_before_pvp']
    assert m.sha(BASE/'CONFIG.json')==(BASE/'CONFIG.sha256').read_text().strip()
    assert gate['config_sha256']==m.sha(BASE/'CONFIG.json')
    assert gate['result']=='CONDITIONAL' and gate['SICD_download_authorized_by_gate'] is False
    assert load('PHASE_B_DOWNLOAD_STATE.json')['SICD_downloaded'] is False

def test_budget_range_and_frozen_input_provenance():
    state=load('PHASE_A_STATE.json');logs=load('PHASE_A_REQUEST_LOG.json')
    assert state['transactions']<=60 and state['total_bytes']<=100*1024**2
    assert sum(l['bytes'] for l in logs)==state['total_bytes']
    signal=json.loads((m.B28/'CPHD_METADATA.json').read_text())['signal_block_byte_offset']
    assert all(l['range'][1]<signal for l in logs if l['range'])
    assert all(l['bytes']<=10*1024**2 for l in logs)
    assert all(m.sha(ROOT/p['path'])==p['sha256'] for p in load('INPUT_PROVENANCE.json'))

def test_mask_synthetic_is_explicit_image_domain_not_real_sar():
    d=load('SYNTHETIC_SUPPORT_DIAGNOSTIC.json')
    for name,r in d.items():
        assert 'IMAGE' in r['model'] and r['diagnostic_only_not_phase_C_real_data']
        assert r['masked_invalid_values_explicitly_zero_not_claimed_valid_data']
        assert set(r['cases'])=={'no_mask_reference','primary_explicit_hard_valid_mask','single_8pixel_edge_taper'}
        expected=0 if name=='static' else -.7
        assert r['cases']['no_mask_reference']['fitted_image_domain_slope_rad_s']==pytest.approx(expected,abs=1e-7)

def test_phase_A_rejects_ignored_range_before_body(monkeypatch):
    import urllib.request
    class Response:
        status=200
        headers={'Content-Length':'25234138880'}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):raise AssertionError('forbidden ignored-range body read')
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    monkeypatch.setattr(m.Client,'save',lambda self:None)
    c=m.Client();before=c.state['total_bytes']
    with pytest.raises(RuntimeError,match='honor exact byte range'):c.request(m.b28.ENDPOINT+'test.cphd','synthetic_guard',span=(0,511))
    assert c.state['total_bytes']==before

def test_actual_pfa_doppler_band_chronology_is_reverse_index_order():
    rows=m.b28.read(BASE/'BAND_TIMES.csv')
    kr=.5*(SICDType.from_xml_file(str(m.B28/'raw/sicd.xml')).PFA.Krg1+SICDType.from_xml_file(str(m.B28/'raw/sicd.xml')).PFA.Krg2)
    r=sorted([r for r in rows if r['point']=='SCP' and r['plan']=='three_nonoverlap' and float(r['k_row_cycles_per_m'])==kr],key=lambda r:int(r['look_index']))
    t=np.array([float(x['centre_uniform_output_k_s']) for x in r])
    assert len(t)==3 and np.all(np.diff(t)<0)
    assert list(np.argsort(t))==[2,1,0]

import json
from pathlib import Path
import numpy as np
import pytest
from umbra_sar.formation_path_comparison import *

def test_time_intersection(): assert temporal_intersection((0,18),(0.003,22.5))==(0.003,18.0)
def test_disjoint_time_support_rejected():
    with pytest.raises(ValueError): temporal_intersection((0,1),(2,3))
def test_normalized_temporal_kernel():
    t=np.linspace(0,10,10001); w=normalized_kernel(t,(2,8)); assert np.isclose(np.trapezoid(w,t),1)
def test_equal_kernels_have_equal_centres():
    t=np.linspace(0,10,1001); w=normalized_kernel(t,(2,8)); m=kernel_metrics(t,w,w); assert m['center_abs_error_s']<1e-12 and m['cosine_similarity']>1-1e-12
def test_monotone_doppler_to_slow_time_conversion_preserves_order_and_sign():
    k=np.array([3.,2.,1.,0.]); t=np.array([0.,1.,2.,3.]); got=doppler_to_slow_time([2.5,.5],k,t); assert np.allclose(got,[.5,2.5])
def test_nonmonotone_doppler_mapping_is_rejected():
    with pytest.raises(ValueError): doppler_to_slow_time([1.], [0.,2.,1.], [0.,1.,2.])
def test_bp_kernel_projection_normalizes_coefficients():
    t=np.linspace(0,4,4001); w=normalized_kernel(t,(1,3)); c,a=project_kernel_to_bins(t,w,[0,1,2,3,4],[10]*4); assert np.isclose(c.sum(),1) and np.all(c>=0)
def test_kernel_normalization_uses_no_out_of_support_samples():
    t=np.linspace(0,4,4001); w=normalized_kernel(t,(1,3)); assert np.all(w[(t<1)|(t>3)]==0)
def test_physical_k_match_is_nearest_not_power_selected():
    idx,k,e=fixed_k_index((288,130),5,.0481,0); assert idx==(155,65) and e<.5*(2*np.pi/1440)
def test_cross_convention_and_sign():
    t=np.array([0.,1.,2.,3.]); z=np.exp(-.4j*t); f=signed_phase_fit(z,t); assert np.isclose(f['slope_rad_s'],-.4) and CROSS_CONVENTION.startswith('F_secondary')
def test_known_rotation_response():
    a=2+3j; phi=.37; assert np.isclose(np.angle((a*np.exp(1j*phi))*np.conj(a)),phi)
def test_conjugate_lobe_index(): assert conjugate_index((155,65),(288,130))==(133,65)
def test_conjugate_slope_is_antisymmetric():
    t=np.arange(5.); z=np.exp(-.3j*t); assert abs(signed_phase_fit(z,t)['slope_rad_s']+signed_phase_fit(np.conj(z),t)['slope_rad_s'])<1e-12
def test_fixed_patch_refuses_outside_support():
    with pytest.raises(ValueError): fixed_patch_coefficients(np.ones((3,5,5)),(0,0),1)
def test_comparison_is_reproducible():
    t=np.array([0.,.7,1.9,3.]); z=np.exp(-.2j*t); assert signed_phase_fit(z,t)==signed_phase_fit(z,t)
def test_gate_classification_and_abstention_are_deterministic():
    th={'level1_min_cycles':.5,'level1_min_r2':.97,'level1_max_adjacent_phase_rad':1.57,'level1_min_patch_msc':.5,'level2_min_separation_delta_eff':2,'level3_min_independent_radial_elements':4}
    m={'cycles':1,'r2':.99,'max_step':.4,'msc':.8,'sign_ok':True,'separation_delta_eff':1.35,'formation_stable':False,'persistent_resolved':False,'external_compatible':False,'independent_radial_elements':2,'omega_k_resolved':False,'current_constrained':False}
    assert classify_gates(m,th)=={'level1':True,'level2':False,'level3':False,'mandatory_abstention':True}
def test_calibration_and_outputs_are_separate_from_frozen_values():
    cfg=json.loads((Path(__file__).parents[1]/'umbra/Vandenberg/results/analysis_block15/BLOCK15K_CONFIG.json').read_text()); assert cfg['status']=='protocol frozen before matched calculations' and 'frozen_values' in cfg
def test_prior_artifact_hash_guard():
    root=Path(__file__).parents[1]; cfg=json.loads((root/'umbra/Vandenberg/results/analysis_block15/BLOCK15K_CONFIG.json').read_text()); assert verify_hashes(root,cfg['input_sha256'])==[]

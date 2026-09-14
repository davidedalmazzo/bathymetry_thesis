import numpy as np
import pytest
import json, hashlib
from pathlib import Path
from umbra_sar.spatial_resolution import tukey_1d, window_axis_metrics, kernel_overlap, count_local_maxima
from umbra_sar.two_component_separability import window_response

def test_delta_bin_and_enbw_are_defined():
 m=window_axis_metrics(288,.1,32768)
 assert m['delta_bin']==pytest.approx(1/288) and m['fwhm_power_bins']>.5 and m['enbw_bins']>1

def test_tukey_response_has_main_lobe_and_sidelobe():
 m=window_axis_metrics(130,.1,32768)
 assert m['main_lobe_energy_fraction']>.85 and m['first_sidelobe_power']<.1 and not m['exact_first_zero_defined']

def test_same_window_bin_overlap_decreases_with_distance():
 assert kernel_overlap((288,130),.1,0,0)==pytest.approx(1)
 assert kernel_overlap((288,130),.1,1,0)<1
 assert kernel_overlap((288,130),.1,6,0)<kernel_overlap((288,130),.1,1,0)

def test_single_and_separated_synthetic_centres_are_recoverable():
 q=np.array([[r,65.] for r in range(125,143)])
 a=abs(window_response((288,130),q,[133.,65.]));b=abs(window_response((288,130),q,[139.,65.]))
 assert np.argmax(a)==8 and np.argmax(b)==14

def test_overlapped_templates_are_more_correlated_than_six_bin_templates():
 q=np.array([[r,65.] for r in range(120,147)])
 a=window_response((288,130),q,[133.,65.]);one=window_response((288,130),q,[134.,65.]);six=window_response((288,130),q,[139.,65.])
 corr=lambda x:abs(np.vdot(a,x))/np.sqrt(np.vdot(a,a).real*np.vdot(x,x).real)
 assert corr(one)>corr(six)

def test_local_maxima_does_not_count_conjugate_or_border_by_wrap():
 p=np.zeros((7,7));p[3,3]=1;p[0,0]=.9
 assert count_local_maxima(p,.05)==[(3,3)]

def test_block15h_keeps_the_real_peak_and_signed_convention_frozen():
 root=Path(__file__).resolve().parents[1]
 cfg=json.loads((root/'Vandenberg/results/analysis_block15/BLOCK15H_CONFIG.json').read_text())
 assert cfg['fixed_peak']==[133,65]
 assert 'signed slope' in cfg['preprocessing']['phase_estimator']

def test_block15h_prior_artifact_guards_match():
 root=Path(__file__).resolve().parents[1]
 cfg=json.loads((root/'Vandenberg/results/analysis_block15/BLOCK15H_CONFIG.json').read_text())
 assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in cfg['guard_sha256'].items())

import numpy as np
import pytest
from umbra_sar.look_transfer_geometry import finite_depth_omega,phase_slope,transfer_terms


def test_finite_depth_deep_limit_and_units():
    k=.05; assert finite_depth_omega(k,1e5)==pytest.approx(np.sqrt(9.80665*k),rel=1e-12)
    r=transfer_terms(k_vector=[.05,0,0],los_horizontal=[1,0,0],flight_horizontal=[0,1,0],incidence_rad=.4,range_over_speed_s=80,omega_rad_s=.5,depth_m=10)
    assert r['T_t'].imag!=0 and r['T_vb']==0j and r['H']==r['T_t']


def test_constant_transfer_cancels_and_imposed_drift_sign():
    t=np.array([0,.7,1.5,2.2]);sw=.41;h=(2-3j)*np.ones(4)
    assert phase_slope(t,h*np.exp(1j*sw*t))[0]==pytest.approx(sw)
    assert phase_slope(t,h*np.exp(1j*(sw-.12)*t))[0]==pytest.approx(sw-.12)


def test_cross_reference_swap_and_conjugate_sign():
    t=np.array([0,.7,1.5,2.2]);z=np.exp(1j*.4*t); i,j=1,3
    assert np.angle(z[j]*z[i].conjugate())==pytest.approx(.4*(t[j]-t[i]))
    assert np.angle(z[i]*z[j].conjugate())==pytest.approx(-.4*(t[j]-t[i]))
    assert phase_slope(t,z.conjugate())[0]==pytest.approx(-.4)


def test_near_cancellation_is_exposed():
    t=np.arange(4.); h=np.array([1,1e-16,1,1],complex)
    with pytest.raises(ValueError):phase_slope(t,h)

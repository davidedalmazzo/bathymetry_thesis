"""Analytic checks independent of real ocean slopes; small coefficient arrays."""
import json
from pathlib import Path
import numpy as np
import pytest
from umbra_sar.contamination_diagnostic import (
    components,instantaneous_slope,complex_noise,patch_coherences,
    patch_profiles,fit_three,grid_cases,
)

CFG=json.loads((Path(__file__).resolve().parents[1]/'Vandenberg/results/analysis_block15/BLOCK15B_CONFIG.json').read_text())
T=np.array(CFG['time_s'])


@pytest.mark.parametrize('slope',[.3,.5,.7,-.5])
def test_single_component_and_equal_slope(slope):
    for ratio,phase in [(0,0),(.5,1.2),(2,.6)]:
        a,b=components(T,slope,ratio,slope,phase)
        np.testing.assert_allclose(instantaneous_slope(T,slope,ratio,slope,phase),slope,atol=1e-12)
        for fit in fit_three(a+b,T,CFG).values():
            assert fit['s_phi']==pytest.approx(slope,abs=1e-6)
            assert fit['valid']


def test_static_formula_and_phase_derivative():
    t=np.linspace(0,10,101);s=.7;r=.6;phase=.8
    theta=s*t-phase
    expected=s*(1+r*np.cos(theta))/(1+r*r+2*r*np.cos(theta))
    actual=instantaneous_slope(t,s,r,0,phase)
    np.testing.assert_allclose(actual,expected,atol=1e-12)
    step=1e-6
    am,bm=components(t-step,s,r,0,phase)
    ap,bp=components(t+step,s,r,0,phase)
    numeric=np.angle((ap+bp)*np.conj(am+bm))/(2*step)
    np.testing.assert_allclose(actual,numeric,atol=1e-8)
    assert actual.min()<s<actual.max()  # contamination need not lower phase rate


def test_cancellation_and_sign_inversion():
    a,b=components(T,.5,1.,.5,np.pi)
    assert np.max(abs(a+b))<1e-14
    assert np.isnan(instantaneous_slope(T,.5,1,.5,np.pi)).all()
    # Near a cancellation: a tiny but nonzero denominator amplifies derivative.
    near=instantaneous_slope(np.array([0.]),.5,1.0001,0,np.pi)
    assert abs(near[0])>100
    p=instantaneous_slope(T,.5,.7,-.1,.3)
    q=instantaneous_slope(T,-.5,.7,.1,-.3)
    np.testing.assert_allclose(p,-q,atol=1e-12)
    a,b=components(T,.5,.7,-.1,.3)
    a2,b2=components(T,-.5,.7,.1,-.3)
    np.testing.assert_allclose(a2+b2,(a+b).conj(),atol=1e-12)
    first=fit_three(a+b,T,CFG);second=fit_three(a2+b2,T,CFG)
    for method in first:
        assert first[method]['s_phi']==pytest.approx(-second[method]['s_phi'],abs=1e-6)


def test_complex_noise_variance_and_seed():
    rng=np.random.default_rng(150301)
    z=complex_noise(rng,(100000,),.3)
    assert np.mean(abs(z)**2)==pytest.approx(.09,rel=.015)
    assert np.var(z.real)==pytest.approx(.045,rel=.02)
    assert np.var(z.imag)==pytest.approx(.045,rel=.02)
    np.testing.assert_array_equal(z,complex_noise(np.random.default_rng(150301),(100000,),.3))


def test_patch_msc_not_single_product_and_profile_dependence():
    a,b=components(T,.5,2.,0,.8)
    noise=np.zeros((len(T),3,3),complex)
    result=patch_coherences(a,b,noise)
    assert result['proportional']['endpoint_MSC']==pytest.approx(1.,abs=1e-12)
    assert result['different']['endpoint_MSC']<.99
    h,q=patch_profiles();assert h[1,1]==q['different'][1,1]==1
    assert abs(fit_three(a+b,T,CFG)['A']['s_phi']-.5)>.05


def test_finite_record_temporal_mean_not_exact_contaminant():
    a,b=components(T,.3,.5,0,.8)
    np.testing.assert_allclose((a+b)-b,a,atol=1e-15)
    assert abs(a.mean())>.01
    assert np.max(abs(((a+b)-(a+b).mean())-a))>.01


def test_design_deduplication_and_counts():
    cases=grid_cases()
    assert len(cases)==291
    assert sum(c['ratio']==0 for c in cases)==3
    assert len({(c['s_true'],c['ratio'],c['s_cont'],c['relative_phase']) for c in cases})==291

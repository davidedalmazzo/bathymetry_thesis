import json
from pathlib import Path
import numpy as np
import pytest
from umbra_sar.static_offset_diagnostic import linear_parameters,fit_profile,compare_models,predict

OLD=json.loads((Path(__file__).resolve().parents[1]/'umbra/Vandenberg/results/analysis_block15/BLOCK15B_CONFIG.json').read_text())
T=np.array(OLD['time_s']);T0=T.mean()


@pytest.mark.parametrize('offset',[False,True])
def test_identifiable_parameters_and_prediction(offset):
    a=1.2+.3j;c=.4-.2j if offset else 0j;s=.5
    z=a*np.exp(1j*s*(T-T0))+c
    f=fit_profile(z,T,T0,offset,OLD['search']['bounds'])
    assert f['s']==pytest.approx(s,abs=1e-6)
    assert complex(*f['a'])==pytest.approx(a,abs=1e-6)
    assert complex(*f['c'])==pytest.approx(c,abs=1e-6)
    np.testing.assert_allclose(predict(f,T,T0),z,atol=1e-6)


def test_profile_cost_matches_linear_projection_and_nesting():
    z=np.exp(.7j*(T-T0))+.5*np.exp(.4j)
    f0=fit_profile(z,T,T0,False,(-2,2));f1=fit_profile(z,T,T0,True,(-2,2))
    assert f1['sse']<=f0['sse']+1e-12
    for idx in (0,501,1000,1300,2000):
        _,p,_,_=linear_parameters(z,T,f1['profile_grid'][idx],T0,True)
        assert f1['profile_cost'][idx]==pytest.approx(np.sum(abs(z-p)**2)/np.sum(abs(z)**2),abs=1e-12)


def test_flat_constant_and_boundary_are_reported():
    f=fit_profile(np.ones(32,complex),T,T0,True,(-2,2))
    assert f['flat'] and f['ambiguous']
    _,_,rank,condition=linear_parameters(np.ones(32),T,0,T0,True)
    assert rank==1 and condition>1e6
    z=np.exp(.9j*(T-T0))
    f=fit_profile(z,T,T0,False,(.8,.85))
    assert f['boundary']


def test_conjugate_sign_and_offset():
    z=np.exp(.5j*(T-T0))+.4j
    a=fit_profile(z,T,T0,True,(-2,2));b=fit_profile(z.conj(),T,T0,True,(-2,2))
    assert a['s']==pytest.approx(-b['s'],abs=1e-6)
    assert complex(*a['c']).conjugate()==pytest.approx(complex(*b['c']),abs=1e-6)


def test_holdout_fit_does_not_use_test_values():
    train=np.arange(8,32);z=np.exp(.5j*(T-T0))+.4j
    altered=z.copy();altered[:8]+=100
    first=fit_profile(z[train],T[train],T0,True,(-2,2))
    second=fit_profile(altered[train],T[train],T0,True,(-2,2))
    assert first==second

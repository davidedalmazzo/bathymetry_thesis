import numpy as np
import pytest
from umbra_sar.correlated_offset_validation import exponential_noise,blocked_partition,fit_fold


def test_ou_irregular_time_covariance_stationary_initial():
    t=np.array([0.,.1,.9,2.4,5.]);rng=np.random.default_rng(150501)
    z=np.array([exponential_noise(t,2.,2.,rng) for _ in range(12000)])
    cov=z.T@z.conj()/len(z);expected=4*np.exp(-abs(t[:,None]-t)/2)
    np.testing.assert_allclose(cov,expected,atol=.12)
    np.testing.assert_allclose(z.T@z/len(z),0,atol=.13)


def test_independent_noise_reproducible_and_invalid():
    t=np.arange(10000.)
    z=exponential_noise(t,1,0,np.random.default_rng(6))
    assert abs(np.mean(abs(z)**2)-1)<.04
    assert abs(np.mean(z[1:]*z[:-1].conj()))<.04
    np.testing.assert_array_equal(z,exponential_noise(t,1,0,np.random.default_rng(6)))
    with pytest.raises(ValueError):exponential_noise([0,0],1,2,np.random.default_rng(1))


def test_purged_partition_support():
    p=blocked_partition()
    assert sorted(sum([q['test'] for q in p],[]))==list(range(32))
    assert [len(q['train']) for q in p]==[26,24,24,24,24,24,24,26]
    for q in p:
        assert min(abs(i-j) for i in q['train'] for j in q['test'])>=3
        assert set(q['train'])|set(q['test'])|set(q['guard'])==set(range(32))


def test_purged_fit_excludes_test_and_guard_values():
    t=np.arange(32)*.7;z=np.exp(.5j*(t-t.mean()))+.3j;p=blocked_partition()[2]
    cfg=dict(t0=t.mean(),bounds=[-3.2,3.2],grid_size=2001,profile_cost_margin=.01)
    first=fit_fold(z,t,cfg,p);changed=z.copy();changed[p['test']+p['guard']]+=100-50j
    second=fit_fold(changed,t,cfg,p)
    for m in ('M0','M1'):
        for field in ('s','a','c','profile_cost','test_prediction_real','test_prediction_imag'):
            assert first[m][field]==second[m][field]
        assert first[m]['test_sse']!=second[m]['test_sse']

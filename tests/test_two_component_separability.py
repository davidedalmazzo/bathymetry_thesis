import numpy as np
import pytest
from umbra_sar.two_component_separability import window_response,window_noise_cov,correlated_noise,fit_q,purged_folds,block15d_folds

def test_window_response_peak_and_leakage():
 q=np.array([[133.,65.],[134.,65.],[136.,65.]])
 w=window_response((288,130),q,[133.,65.])
 assert w[0]==pytest.approx(1) and abs(w[1])<1 and abs(w[2])<abs(w[1])

def test_noiseless_identifiable_two_component_and_label_symmetry():
 t=np.linspace(0,22,32);q=np.array([[131.,65.],[132.,65.],[133.,65.],[134.,65.],[135.,65.],[136.,65.],[137.,65.],[138.,65.]])
 w1=window_response((288,130),q,[133.,65.]);w2=window_response((288,130),q,[136.,65.]);z=np.exp(.3j*t)[:,None]*w1+.7*np.exp(.62j*t)[:,None]*w2
 f=fit_q(z,t,[w1,w2],[np.ones(32),np.ones(32)],(-1,1),'Q2',31)
 assert sorted(f['s'])==pytest.approx([.3,.6],abs=.04)

def test_covariance_is_hermitian_and_seed_reproducible():
 q=np.array([[132.,65.],[133.,65.],[134.,65.]]);c=window_noise_cov((288,130),q);np.testing.assert_allclose(c,c.conj().T);np.testing.assert_allclose(np.diag(c),1)
 t=np.array([0.,.7,1.5]);a=correlated_noise(t,c,.1,5,np.random.default_rng(2));b=correlated_noise(t,c,.1,5,np.random.default_rng(2));np.testing.assert_allclose(a,b)

def test_purged_support_no_leakage():
 for train,test,guard in purged_folds():
  assert not(set(train)&set(test)) and not(set(train)&set(guard))
  assert min(abs(i-j) for i in train for j in test)>=3

def test_block15d_secondary_partition_is_complete_and_disjoint():
 folds=block15d_folds()
 assert len(folds)==4
 assert sorted(np.concatenate([test for _,test,_ in folds]).tolist())==list(range(32))
 for train,test,guard in folds:
  assert len(test)==8 and len(guard)==0 and not(set(train)&set(test))

def test_degenerate_modes_are_not_asserted_identifiable():
 t=np.arange(32.);q=np.array([[133.,65.]]) ;w=window_response((288,130),q,[133.,65.]);f=fit_q(np.exp(.4j*t)[:,None]*w,t,[w,w],[np.ones(32),np.ones(32)],(-1,1),'Q2',21)
 assert f['rank']<2 or f['alternatives']>=0

"""Block15I compact synthetic A (extended wave) vs B (persistent neighbor)."""
from repository_paths import resolve_historical
import argparse,csv,json,hashlib
from pathlib import Path
import numpy as np
from umbra_sar.two_component_separability import correlated_noise,tukey
from umbra_sar.frequency_comparison import reference_fit,estimate_circular
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'umbra/Vandenberg/results/analysis_block15';CFG=OUT/'BLOCK15I_CONFIG.json'
TEMPLATE_CACHE={}
NOISE_CACHE={}
def response(shape,q,k):
 """Separable exact DFT of the same 2-D Tukey, avoiding per-mode 2-D arrays."""
 r=np.arange(shape[0]);c=np.arange(shape[1]);wr=tukey(shape[0]);wc=tukey(shape[1])
 a=np.exp(-2j*np.pi*(q[:,0,None]-k[0])*r/shape[0])@wr/wr.sum()
 b=np.exp(-2j*np.pi*(q[:,1,None]-k[1])*c/shape[1])@wc/wc.sum()
 return a*b
def noise_cov(shape,q):
 wr=tukey(shape[0])**2;wc=tukey(shape[1])**2;r=np.arange(shape[0]);c=np.arange(shape[1])
 dr=q[:,0,None]-q[None,:,0];dc=q[:,1,None]-q[None,:,1]
 a=np.exp(-2j*np.pi*dr[...,None]*r/shape[0])@wr/wr.sum();b=np.exp(-2j*np.pi*dc[...,None]*c/shape[1])@wc/wc.sum();return a*b
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else TypeError())
def prep():
 c=json.loads((OUT/'BLOCK15G_CONFIG.json').read_text()); guards=[OUT/'BLOCK15H_DELIVERY_MANIFEST.json',OUT/'BLOCK15G_DELIVERY_MANIFEST.json',OUT/'BLOCK15F_CONFIG.json',OUT/'BLOCK15B_CONFIG.json',OUT/'BLOCK15E_CONFIG.json']
 cfg=dict(scope='synthetic intensity-Fourier coefficients only; no real classifier or correction',times_s=c['times_s'],shape=[288,130],peak=[133.,65.],patch_rows=[125,142],patch_cols=[62,69],window='same BP12 Tukey alpha .1 response; no extra observed-FWHM blur',transfer='Block15F T13_depth10 geometry not applied: constant-H control selected before results because persistent B terms have no wave MTF',noise=dict(snr=10,tau_s=[0,5],seed_calibration=150900,seed_evaluation=150901),families=dict(A='finite spatial-band propagating system: three modes with finite-depth-like ordered slopes; no static additive term',B='one propagating primary plus nearby static or OU-slow coefficient; persistent term has unit observation operator, not wave MTF'),separations=dict(radial_bins=[2.223,3.0],tangential_bins=[1.452],observed_fwhm_scales='Block15H descriptive scales only'),amplitude_ratios=[.3,.7,1.0],conditional_power_ratio=.705,calibration=dict(replicates=8,radial_bin=2.223,ratios=[.3,.7],families=['A','B_static','B_slow']),evaluation=dict(replicates=8,radial_bin=3.0,ratio=1.0,include_tangential=True),rule='Block15I persistent-score: |amplitude-correlation|>=0.85 AND M1 predictive gain>=0.10; calibrated only on calibration sequences; otherwise indeterminate',guard_sha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in guards})
 dump(CFG,cfg)
def templates(cfg,delta,axis=0):
 key=(float(delta),int(axis))
 if key in TEMPLATE_CACHE:return TEMPLATE_CACHE[key]
 q=np.array([[r,c] for r in range(*cfg['patch_rows']) for c in range(*cfg['patch_cols'])],float);k=np.array(cfg['peak']);d=np.array([delta,0.]) if axis==0 else np.array([0.,delta]); TEMPLATE_CACHE[key]=(q,response(tuple(cfg['shape']),q,k),response(tuple(cfg['shape']),q,k+d)); return TEMPLATE_CACHE[key]
def m1gain(z,t,a):
 # fixed signed grid, training-only caller splits; M0 vs M1=a*exp(ist)+c
 grid=np.linspace(.1,.8,21);best=[]
 for static in (False,True):
  costs=[]
  for s in grid:
   X=(a[None,:]*np.exp(1j*s*t[:,None])).reshape(-1,1)
   if static:X=np.c_[X,np.tile(a,len(t))]
   coef=np.linalg.lstsq(X,z.ravel(),rcond=None)[0];cost=np.sum(abs(z.ravel()-X@coef)**2);costs.append((cost,s))
  best.append(min(costs))
 return 1-best[1][0]/best[0][0],best[1][1]
def synth(cfg,fam,rep,seed,delta,ratio,axis=0):
 t=np.array(cfg['times_s']);q,a,b=templates(cfg,delta,axis); rng=np.random.default_rng(np.random.SeedSequence([seed,rep,int(delta*100),axis]));
 primary=np.exp(.4j*t)[:,None]*a
 if fam=='A':
  # distributed finite band, explicitly no unique single truth slope
  km=('minus',float(delta),axis)
  if km not in TEMPLATE_CACHE:TEMPLATE_CACHE[km]=response(tuple(cfg['shape']),q,np.array(cfg['peak'])-np.array([delta,0.] if axis==0 else [0.,delta]))
  z=primary+.45*np.exp(.48j*t)[:,None]*b+.25*np.exp(.34j*t)[:,None]*TEMPLATE_CACHE[km][None,:]; truth=None
 elif fam=='B_static':z=primary+ratio*np.exp(.7j)*b;truth=.4
 else:
  n=correlated_noise(t,np.ones((1,1)),ratio,5,rng)[:,0];z=primary+n[:,None]*b;truth=.4
 nk=(float(delta),int(axis))
 if nk not in NOISE_CACHE:NOISE_CACHE[nk]=noise_cov(tuple(cfg['shape']),q)
 z+=correlated_noise(t,NOISE_CACHE[nk],1/cfg['noise']['snr'],5 if rep%2 else 0,rng)
 return z,a,truth
def row(cfg,fam,rep,seed,delta,ratio,axis):
 z,a,truth=synth(cfg,fam,rep,seed,delta,ratio,axis);t=np.array(cfg['times_s']);i=np.argmax(np.mean(abs(z)**2,axis=0));fit=reference_fit(z[:,i],t,16);circ=estimate_circular(z[:,i],t,(1,2,4,8),[-1,1]);gain,s=m1gain(z,t,a); amps=abs(z); corr=float(np.corrcoef(amps[:,i],np.mean(amps,axis=1))[0,1]); pred=(abs(corr)>=.85 and gain>=.1); err=None if truth is None else abs(fit['s_phi']-truth)/truth
 return dict(family=fam,replicate=rep,axis='radial' if axis==0 else 'tangential',separation_bins=delta,ratio=ratio,truth_s=truth,ols_s=fit['s_phi'],circular_s=circ['s_phi'],agreement=abs(fit['s_phi']-circ['s_phi']),r2=fit['r2'],phase_rmse=fit['rmse'],m1_gain=gain,amplitude_correlation=corr,persistent_score=pred,relative_slope_error=err,distorted_over_10pct=(err is not None and err>.1),frozen_criteria_pass=(fit['r2']>=.97 and circ['valid']))
def run():
 cfg=json.loads(CFG.read_text());assert all(sha(resolve_historical(p, ROOT))==h for p,h in cfg['guard_sha256'].items());rows=[]
 for fam in cfg['calibration']['families']:
  for r in range(8):rows.append(dict(phase='calibration',**row(cfg,fam,r,cfg['noise']['seed_calibration'],2.223,.3 if r<4 else .7,0)))
 for fam in ['A','B_static','B_slow']:
  for ax in (0,1):
   for r in range(8):rows.append(dict(phase='evaluation',**row(cfg,fam,r,cfg['noise']['seed_evaluation'],3.0 if ax==0 else 1.452,1.,ax)))
 with (OUT/'BLOCK15I_RESULTS.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 ev=[r for r in rows if r['phase']=='evaluation'];A=[r for r in ev if r['family']=='A'];B=[r for r in ev if r['family']!='A']; fp=sum(r['persistent_score'] for r in A);tp=sum(r['persistent_score'] for r in B);ind=len(ev)-fp-tp; distorted=[r for r in B if r['distorted_over_10pct']];summary=dict(independent_sequences=len(rows),evaluation_sequences=len(ev),rule='persistent-score above',A_as_B=fp,B_detected=tp,A_total=len(A),B_total=len(B),indeterminate=ind,distorted_B=len(distorted),distorted_pass_frozen=sum(r['frozen_criteria_pass'] for r in distorted),note='Rule is exploratory and evaluates held-out separation/direction, not Vandenberg.')
 dump(OUT/'BLOCK15I_SUMMARY.json',summary);(OUT/'BLOCK15I_REPORT.md').open('x').write('# Block15I report\n\n'+json.dumps(summary,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else None)+'\n\nConclusion: under these compact coefficient-only conditions, the diagnostics have parameter-dependent discrimination and retain indeterminate cases; they do not assign a Vandenberg cause.\n')
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','run']);x=a.parse_args();prep() if x.mode=='prepare' else run()

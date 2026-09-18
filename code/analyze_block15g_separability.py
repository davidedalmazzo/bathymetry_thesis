"""Block15G compact synthetic two-wave separability; no real coefficient fit."""
from repository_paths import resolve_historical
import argparse,csv,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from umbra_sar.two_component_separability import window_response,window_noise_cov,correlated_noise,fit_q,validate,block15d_folds
from umbra_sar.look_transfer_geometry import finite_depth_omega,transfer_terms,unit
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'umbra/Vandenberg/results/analysis_block15';CFG=OUT/'BLOCK15G_CONFIG.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x,overwrite=False):
 with Path(p).open('w' if overwrite else 'x') as f:json.dump(x,f,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else (_ for _ in ()).throw(TypeError(type(v).__name__)))
def setup():
 f=json.loads((OUT/'BLOCK15F_GEOMETRY.json').read_text());d=json.loads((OUT/'BLOCK15D_CONFIG.json').read_text());t=np.array(d['previous_config']['time_s']);guards={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [OUT/'BLOCK15F_CONFIG.json',OUT/'BLOCK15F_RESULTS.json',OUT/'BLOCK15F_GEOMETRY.json',OUT/'BLOCK15F_REPORT.md',OUT/'BLOCK15D_CONFIG.json',OUT/'BLOCK15E_CONFIG.json']}
 cfg=dict(created_utc=datetime.now(timezone.utc).isoformat(),scope='synthetic intensity-Fourier coefficients only; no real Q2 fit',times_s=t.tolist(),shape=[288,130],dominant_mode=[133.,65.],patch_modes=[[float(r),float(c)] for r in range(127,142) for c in range(64,67)],
  transfer_scenario=dict(period_s=13.33,depth_m=10.,source='Block15F diagnostic scenario; supplied to geometry-informed fit only'),bounds=[-1.,1.],grid_size=31,
  noise=dict(SNR_dominant=10.,tau_s=[0.,5.],definition='sigma=1/SNR times dominant complex coefficient at its template peak; proper complex noise, temporal OU and spatial covariance from BP12 Tukey-window-squared DFT',seed_calibration=150700,seed_evaluation=150701),
  calibration=[dict(name='single_constant',kind='single',transfer='constant',replicates=12,tau=0.),dict(name='single_geometry',kind='single',transfer='geometry',replicates=12,tau=5.),dict(name='static_offset',kind='offset',transfer='geometry',replicates=12,tau=5.,offset_ratio=.5)],
  evaluation=[dict(name='stress_unresolved',kind='two',spatial_delta=.25,delta_s=.023,ratio=.7,phase=0.,tau=0.,replicates=12,physical=False),dict(name='stress_temporal',kind='two',spatial_delta=3.,delta_s=.138,ratio=.7,phase=1.57079632679,tau=0.,replicates=12,physical=False),dict(name='physical_overlap',kind='physical',spatial_delta=1.,ratio=.7,phase=0.,tau=5.,replicates=12,physical=True),dict(name='physical_separable',kind='physical',spatial_delta=6.,ratio=.7,phase=1.57079632679,tau=0.,replicates=12,physical=True),dict(name='physical_weak_persistent',kind='physical',spatial_delta=6.,ratio=.3,phase=0.,tau=5.,replicates=12,physical=True)],
  selection_rule='After separate calibration, threshold=max(0.10, empirical 95th percentile of Q2-vs-best(Q0,Q1) purged predictive gain across calibration; Q2 selected only above threshold and no boundary, no alternative grid minimum within 1% SSE, and |s1-s2|>0.02 rad/s. Recovery pair error <= min(0.03,0.25*true separation), labels interchangeable.',
  guard_sha256=guards,source_sha256={p:sha(resolve_historical(p, ROOT)) for p in ['code/analyze_block15g_separability.py','code/umbra_sar/two_component_separability.py','tests/test_two_component_separability.py']})
 save(CFG,cfg)
def hs(cfg,k_modes,omegas,which):
 geo=json.loads((OUT/'BLOCK15F_GEOMETRY.json').read_text());up=np.array(geo['up_ecf']);ax=np.array(geo['axis0_ecf']);ay=np.array(geo['axis1_ecf']);target=np.array(geo['target_ecf_m']);arr=[]
 for mode,omega in zip(k_modes,omegas):
  kvec=(mode[0]-144)*2*np.pi/(288*5)*ax+(mode[1]-65)*2*np.pi/(130*5)*ay;one=[]
  for row,detail in zip(geo['rows'],geo['looks']):
   los=unit(np.array(detail['position_mean_ecf_m'])-target).reshape(3);lh=unit(los-(los@up)*up).reshape(3);v=np.array(detail['velocity_mean_ecf_m_s']);fh=unit(v-(v@up)*up).reshape(3);q=transfer_terms(k_vector=kvec,los_horizontal=lh,flight_horizontal=fh,incidence_rad=np.deg2rad(row['incidence_mean_deg']),range_over_speed_s=row['R_over_V_mean_s'],omega_rad_s=omega,depth_m=cfg['transfer_scenario']['depth_m']);one.append(q['H'])
  h=np.array(one);arr.append(h/np.median(abs(h)) if which=='geometry' else np.ones_like(h))
 return arr
def synth(cfg,case,rep,phase_seed):
 t=np.array(cfg['times_s']);q=np.array(cfg['patch_modes']);k1=np.array(cfg['dominant_mode']);k2=k1+np.array([case.get('spatial_delta',0.),0.]);temps=[window_response(cfg['shape'],q,k1),window_response(cfg['shape'],q,k2)]
 s1=.4
 if case.get('physical'):
  dk=2*np.pi/(288*5);s1=float(finite_depth_omega(abs((k1[0]-144)*dk),10));s2=float(finite_depth_omega(abs((k2[0]-144)*dk),10))
 else:s2=s1+case.get('delta_s',0.)
 H=hs(cfg,[k1,k2],[s1,s2],case.get('transfer','geometry'))
 z=(np.exp(1j*s1*t)[:,None]*H[0][:,None]*temps[0][None,:]+case.get('ratio',0.)*np.exp(1j*case.get('phase',0.))*np.exp(1j*s2*t)[:,None]*H[1][:,None]*temps[1][None,:])
 if case['kind']=='offset':z+=case['offset_ratio']*temps[0][None,:]
 cov=window_noise_cov(cfg['shape'],q);rng=np.random.default_rng(np.random.SeedSequence([phase_seed,rep]));z+=correlated_noise(t,cov,1/cfg['noise']['SNR_dominant'],case.get('tau',0.),rng)
 return z,temps,H,[s1,s2]
def fitall(z,cfg,temps,H,transfer):
 hh=H if transfer=='geometry' else [np.ones_like(H[0]),np.ones_like(H[1])];out={}
 for m in ('Q0','Q1','Q2'):
  full=fit_q(z,np.array(cfg['times_s']),temps,hh,cfg['bounds'],m,cfg['grid_size']);val=validate(z,np.array(cfg['times_s']),temps,hh,cfg['bounds'],m);secondary=validate(z,np.array(cfg['times_s']),temps,hh,cfg['bounds'],m,block15d_folds());out[m]=dict(full=full,sse=val['sse'],fold_sse=[x[0] for x in val['folds']],fold_fit=[x[1] for x in val['folds']],secondary_sse=secondary['sse'],secondary_fold_sse=[x[0] for x in secondary['folds']])
 return out
def execute(kind):
 cfg=json.loads(CFG.read_text()); cases=cfg['calibration'] if kind=='calibration' else cfg['evaluation']; seed=cfg['noise']['seed_calibration'] if kind=='calibration' else cfg['noise']['seed_evaluation'];path=OUT/f'BLOCK15G_{kind.upper()}.json'
 rows=[]
 for case in cases:
  for rep in range(case['replicates']):
   z,temps,H,truth=synth(cfg,case,rep,seed);fits={tr:fitall(z,cfg,temps,H,tr) for tr in ('constant','geometry')};rows.append(dict(case=case,replicate=rep,truth_s=truth,fits=fits))
 save(path,rows)
def secondary():
 """Rebuild only the predeclared 4x8 descriptive validation from frozen seeds."""
 cfg=json.loads(CFG.read_text())
 for kind,cases,seed in [('calibration',cfg['calibration'],cfg['noise']['seed_calibration']),('evaluation',cfg['evaluation'],cfg['noise']['seed_evaluation'])]:
  path=OUT/f'BLOCK15G_{kind.upper()}.json';rows=json.loads(path.read_text())
  for row in rows:
   z,temps,H,_=synth(cfg,row['case'],row['replicate'],seed)
   for transfer,fit in row['fits'].items():
    hh=H if transfer=='geometry' else [np.ones_like(H[0]),np.ones_like(H[1])]
    for model,record in fit.items():
     check=validate(z,np.array(cfg['times_s']),temps,hh,cfg['bounds'],model,block15d_folds())
     record['secondary_sse']=check['sse'];record['secondary_fold_sse']=[x[0] for x in check['folds']]
  save(path,rows,overwrite=True)
def summary():
 cfg=json.loads(CFG.read_text());cal=json.loads((OUT/'BLOCK15G_CALIBRATION.json').read_text());gains=[]
 for r in cal:
  for tr in r['fits'].values():gains.append(1-tr['Q2']['sse']/min(tr['Q0']['sse'],tr['Q1']['sse']))
 threshold=max(.1,float(np.quantile(gains,.95)));ev=json.loads((OUT/'BLOCK15G_EVALUATION.json').read_text());table=[];groups=[]
 for phase,rows in [('calibration',cal),('evaluation',ev)]:
  for r in rows:
   for transfer,fit in r['fits'].items():
    gain=1-fit['Q2']['sse']/min(fit['Q0']['sse'],fit['Q1']['sse']);f=fit['Q2']['full'];ss=sorted(f['s']);truth=sorted(r['truth_s']);sep=truth[1]-truth[0];tol=min(.03,.25*sep) if sep>0 else 0.; rec=sep>0 and max(abs(a-b) for a,b in zip(ss,truth))<=tol;selected=gain>=threshold and not f['boundary'] and f['alternatives']==0 and abs(ss[1]-ss[0])>.02
    table.append(dict(phase=phase,case=r['case']['name'],replicate=r['replicate'],transfer=transfer,gain=gain,selected=selected,recovered=rec,s1_hat=ss[0],s2_hat=ss[1],s1_true=truth[0],s2_true=truth[1],separation_true=sep,tolerance=tol,alternatives=f['alternatives'],boundary=f['boundary']))
 for case in sorted(set(x['case'] for x in table)):
  for tr in ('constant','geometry'):
   a=[x for x in table if x['case']==case and x['transfer']==tr];groups.append(dict(case=case,transfer=tr,n=len(a),selected=sum(x['selected'] for x in a),recovered=sum(x['recovered'] for x in a),selected_not_recovered=sum(x['selected'] and not x['recovered'] for x in a),mean_gain=float(np.mean([x['gain'] for x in a]))))
 # Summary products are reproducible from frozen calibration and evaluation
 # records; only these derived products are overwritten on re-render.
 with (OUT/'BLOCK15G_RESULTS.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
 save(OUT/'BLOCK15G_SUMMARY.json',dict(threshold=threshold,calibration_gains=gains,groups=groups,fold_partition='Primary selection/recovery: 8x4 purged with two-look guards. Secondary descriptive control executed: Block15D 4x8 without guards. Neither fold family creates independent realizations.',notes='Monte Carlo realization is unit; no independent bins or temporal pairs.'),overwrite=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['setup','calibration','evaluation','secondary','summary']);a=p.parse_args(); {'setup':setup,'calibration':lambda:execute('calibration'),'evaluation':lambda:execute('evaluation'),'secondary':secondary,'summary':summary}[a.mode]()

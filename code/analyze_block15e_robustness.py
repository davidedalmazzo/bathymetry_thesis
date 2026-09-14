"""Frozen Block15E design; OU nulls and one purged partition. No radar reads."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse,csv,gzip,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import numpy as np
from umbra_sar.static_offset_diagnostic import compare_models
from umbra_sar.correlated_offset_validation import exponential_noise,blocked_partition,alternative_compare

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'Vandenberg/results/analysis_block15'
CFG=OUT/'BLOCK15E_CONFIG.json'


def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,data):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(data,f,indent=2)


def residual_stats(f,t):
    z=np.array(f['residual_real'])+1j*np.array(f['residual_imag']);center=z-z.mean()
    acf=[]
    for lag in range(1,9):
        v=np.mean(center[lag:]*center[:-lag].conj())/np.mean(abs(center)**2)
        acf.append(dict(lag=lag,mean_dt=float(np.mean(t[lag:]-t[:-lag])),real=float(v.real),imag=float(v.imag)))
    return dict(rms=float(np.sqrt(np.mean(abs(z)**2))),centered_rms=float(np.sqrt(np.mean(abs(center)**2))),
                mean=[float(z.mean().real),float(z.mean().imag)],acf=acf,
                real_imag_covariance=np.cov(np.array([z.real,z.imag]),bias=True).tolist(),
                block8_rms=[float(np.sqrt(np.mean(abs(q)**2))) for q in np.array_split(z,4)])


def prepare():
    old=read('BLOCK15D_CONFIG.json');data=read('BLOCK15D_RESULTS.json');t=np.array(old['previous_config']['time_s']);peak=data['133,65']
    stats={key:{m:residual_stats(d['full'][m],t) for m in ('M0','M1')} for key,d in data.items()}
    guards=dict(old['guard_sha256']);guards.update(old['source_sha256'])
    for p in OUT.glob('BLOCK15D_*'):guards[p.relative_to(ROOT).as_posix()]=digest(p)
    guards['code/plot_block15d_static_offset.py']=digest(ROOT/'code/plot_block15d_static_offset.py')
    for p,h in guards.items():assert digest(ROOT/p)==h,p
    parts=blocked_partition();support=[dict(**p,train_span_s=float(np.ptp(t[p['train']])),
        minimum_train_test_gap_s=float(min(abs(t[i]-t[j]) for i in p['train'] for j in p['test']))) for p in parts]
    cfg=dict(created_utc=datetime.now(timezone.utc).isoformat(),fitting=old['fitting'],time_s=t.tolist(),bins=list(data),
        fixed_peak='133,65',null_M0=peak['full']['M0'],residual_diagnostics=stats,
        noise=dict(correlation_s=[0,.5,2,5],primary_sigma=stats['133,65']['M0']['rms'],alternative_sigma=stats['133,65']['M1']['rms'],
            primary_replicates=300,alternative_replicates=100,seed=150500,
            provenance='RMS uncentered full-fit residual; M0 primary may contain signal mismatch, M1 sensitivity may understate noise. Neither pure noise estimate.',
            formula='E eps_i conj(eps_j)=sigma^2 exp(-abs(t_i-t_j)/tau); proper circular Gaussian, real/imag variances sigma^2/2 and cross covariance zero. Stationary initial CN(0,sigma^2). tau=0 iid.',
            pairing='SeedSequence [150500,regime,replicate]; same unit innovations across noise scales, same series across partitions. Estimated null parameters, not independent synthetic truth.'),
        alternative_partition=support,alternative_gate='Same parameter gates; >=6/8 improved (75%), >=10% total gain and both edge folds positive. Continuous values always retained.',
        statistics='Gain quantiles; all folds improve; gain>=real; gain>=real AND all folds improve; stable; repeated/stable; gain>=real AND all folds improve AND stable. No exclusions from denominators; errors explicit.',
        allocation='Both partitions on every synthetic replicate, 4x300 primary +4x100 sensitivity =1600 series; no further partition search.',
        guard_sha256=guards,source_sha256={p:digest(ROOT/p) for p in ['code/analyze_block15e_robustness.py','code/umbra_sar/correlated_offset_validation.py','tests/test_correlated_offset_validation.py']})
    write('BLOCK15E_CONFIG.json',cfg)
    print(json.dumps(dict(noise=cfg['noise'],support=support),indent=2))


def verify(cfg):
    for p,h in cfg['guard_sha256'].items():assert digest(ROOT/p)==h,p


def compact(obj):
    omit={'profile_grid','profile_cost','residual_real','residual_imag','predicted_real','predicted_imag','test_prediction_real','test_prediction_imag'}
    if isinstance(obj,dict):return {k:compact(v) for k,v in obj.items() if k not in omit}
    if isinstance(obj,list):return [compact(v) for v in obj]
    return obj


def simulation(job):
    scale,regime,rep,cfg=job;t=np.array(cfg['time_s']);noise=cfg['noise'];f=cfg['null_M0']
    sigma=noise['primary_sigma' if scale==0 else 'alternative_sigma'];tau=noise['correlation_s'][regime]
    seed=[noise['seed'],regime,rep];rng=np.random.default_rng(np.random.SeedSequence(seed))
    z=complex(*f['a'])*np.exp(1j*f['s']*(t-cfg['fitting']['t0']))+exponential_noise(t,sigma,tau,rng)
    row=dict(scale=scale,regime=regime,replicate=rep,seed=seed)
    try:
        primary=compare_models(z,t,cfg['fitting'])
        alt=alternative_compare(z,t,cfg['fitting'],cfg['alternative_partition'],primary['full'])
        row.update(primary=compact(primary),alternative=compact(alt),error=None)
    except Exception as exc:row['error']=repr(exc)
    return row


def run():
    cfg=read('BLOCK15E_CONFIG.json');verify(cfg);data=read('BLOCK15D_RESULTS.json');t=np.array(cfg['time_s'])
    realpath=OUT/'BLOCK15E_REAL.json'
    if not realpath.exists():
        real={}
        for key in cfg['bins']:
            d=data[key];z=np.array(d['z_real'])+1j*np.array(d['z_imag'])
            alt=alternative_compare(z,t,cfg['fitting'],cfg['alternative_partition'],d['full'])
            real[key]=dict(primary=compact(d),alternative=compact(alt))
        write(realpath.name,real)
        print('Real fixed sample completed',flush=True)
    for scale,count in [(0,cfg['noise']['primary_replicates']),(1,cfg['noise']['alternative_replicates'])]:
        for regime in range(4):
            path=OUT/f'BLOCK15E_NULL_{scale}_{regime}.jsonl.gz'
            if path.exists():
                with gzip.open(path,'rt') as f:rows=[json.loads(line) for line in f]
                assert len(rows)==count,'Partial file: do not silently resume'
                continue
            # Sequential fallback: Windows sandbox disallows multiprocessing pipes.
            # Statistical design, seeds, fitting and sample allocation unchanged.
            with gzip.open(path,'xt',encoding='utf-8') as f:
                for i,result in enumerate(map(simulation,[(scale,regime,r,cfg) for r in range(count)])):
                    f.write(json.dumps(result)+'\n')
                    if (i+1)%50==0:print(f'scale {scale}, tau {cfg["noise"]["correlation_s"][regime]}: {i+1}/{count}',flush=True)
            print('Saved',path.name,flush=True)
    verify(cfg)


def summarize():
    cfg=read('BLOCK15E_CONFIG.json');verify(cfg);real=read('BLOCK15E_REAL.json');groups=[];records=[]
    for scale in (0,1):
        for regime in range(4):
            with gzip.open(OUT/f'BLOCK15E_NULL_{scale}_{regime}.jsonl.gz','rt') as f:rows=[json.loads(line) for line in f]
            for partition in ('primary','alternative'):
                threshold=real[cfg['fixed_peak']][partition]['relative_predictive_gain'];valid=[r[partition] for r in rows if not r['error']]
                gains=np.array([d['relative_predictive_gain'] for d in valid]);allgood=[d['improved_folds']==len(d['folds']) for d in valid]
                stable=[not d['stability_flags'] for d in valid];joint=[g>=threshold and a and s for g,a,s in zip(gains,allgood,stable)]
                group=dict(scale=scale,correlation_s=cfg['noise']['correlation_s'][regime],partition=partition,n=len(rows),failures=len(rows)-len(valid),real_gain=threshold,
                    gain_quantiles=dict(zip(['q05','q25','median','q75','q95'],np.quantile(gains,[.05,.25,.5,.75,.95]).tolist())),
                    all_folds_improved=sum(allgood),gain_at_least_real=int(sum(gains>=threshold)),
                    gain_and_all=int(sum(g>=threshold and a for g,a in zip(gains,allgood))),stable=int(sum(stable)),joint_at_least_real=int(sum(joint)),
                    categories=dict(Counter(d['category'] for d in valid)),
                    flags=dict(Counter(flag for d in valid for flag in d['stability_flags'])),
                    delta_s_quantiles=np.quantile([d['full']['M1']['s']-d['full']['M0']['s'] for d in valid],[.05,.5,.95]).tolist())
                groups.append(group)
                for r in rows:
                    rec=dict(scale=scale,correlation_s=cfg['noise']['correlation_s'][regime],partition=partition,replicate=r['replicate'],error=r['error'])
                    if not r['error']:
                        d=r[partition];rec.update(gain=d['relative_predictive_gain'],improved_folds=d['improved_folds'],stable=not d['stability_flags'],category=d['category'],slope_span=d['slope_span'],offset_ratio_cv=d['offset_ratio_cv'],offset_ratio=d['full']['M1']['offset_ratio'],delta_s=d['full']['M1']['s']-d['full']['M0']['s'])
                    records.append(rec)
    write('BLOCK15E_SUMMARY.json',dict(groups=groups,real_categories={p:dict(Counter(d[p]['category'] for d in real.values())) for p in ('primary','alternative')},fixed_peak={p:compact(real[cfg['fixed_peak']][p]) for p in ('primary','alternative')}))
    with (OUT/'BLOCK15E_NULL_DISTRIBUTIONS.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in records for k in r)));writer.writeheader();writer.writerows(records)
    table=[]
    for key,d in real.items():
        for partition,result in d.items():
            for i,fold in enumerate(result['folds']):
                r=dict(bin=key,partition=partition,fold=i,gain=fold['relative_SSE_gain'])
                for model in ('M0','M1'):
                    fit=fold[model]
                    for k in ('s','a','c','offset_ratio','test_nmse','ambiguous','boundary'):r[model+'_'+k]=fit[k]
                table.append(r)
    with (OUT/'BLOCK15E_REAL_FOLDS.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    print(json.dumps(dict(groups=groups,real_categories={p:dict(Counter(d[p]['category'] for d in real.values())) for p in ('primary','alternative')}),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','run','summarize']);args=parser.parse_args()
    globals()[args.mode]()

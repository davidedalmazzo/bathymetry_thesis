"""Frozen-design diagnostic Monte Carlo in intensity coefficient space only."""
from repository_paths import resolve_historical
import argparse
import csv
import itertools
import json
import time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

import numpy as np

from analyze_block15b_frequency import OUT,ROOT,digest,write_json,clean
from umbra_sar.contamination_diagnostic import (
    components,instantaneous_slope,complex_noise,patch_coherences,fit_three,grid_cases,
)
from umbra_sar.frequency_comparison import estimate_circular

CONFIG=OUT/'BLOCK15C_CONFIG.json'


def documentary_attrition():
    with (OUT/'BLOCK15B_BINS.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    selected=[r for r in rows if r['common_candidate']=='True']
    criteria={'A':['large_wrapped_step','high_unwrapped_RMSE','outside_search'],
              'B':['high_circular_RMS','alternative_minimum','search_boundary'],
              'C':['high_circular_RMS','alternative_minimum','search_boundary']}
    sets={f'{m}:{reason}':{(r['row'],r['col']) for r in selected if reason in r[m+'_exclusions'].split(';')}
          for m,reasons in criteria.items() for reason in reasons}
    return dict(source='BLOCK15B_BINS.csv; documentary counts only, no reselection',
        common_candidates=len(selected),intersection=sum(r['intersection']=='True' for r in selected),
        individual_counts={k:len(v) for k,v in sets.items()},
        pairwise_overlap={a+' & '+b:len(sets[a]&sets[b]) for a,b in itertools.combinations(sets,2)},
        exact_criterion_patterns=dict(Counter('|'.join(k for k,v in sets.items() if (r['row'],r['col']) in v) or 'none' for r in selected)),
        exact_method_validity_patterns=dict(Counter(''.join(m if r[m+'_valid']=='True' else '-' for m in 'ABC') for r in selected)))


def prepare():
    if CONFIG.exists():raise RuntimeError('Preserve existing Block15C config')
    old=json.loads((OUT/'BLOCK15B_CONFIG.json').read_text())
    guarded=list(OUT.glob('BLOCK15A_*'))+list(OUT.glob('BLOCK15B_*'))
    guarded += [ROOT/'code/umbra_sar/frequency_comparison.py',ROOT/'tests/test_frequency_comparison.py']
    cfg=dict(created_utc=datetime.now(timezone.utc).isoformat(),
        scope='Synthetic intensity-Fourier coefficients at fixed nonzero spatial k; not raw SAR or full speckle',
        inherited_Block15B=old,cases=grid_cases(),case_count=291,
        model='F=exp(i*s_true*t)+ratio*exp(i*s_cont*t+i*relative_phase)+epsilon; A=1, phi_A=0',
        noise=dict(levels=[0.,.1,.3],replicates=[1,50,50],master_seed=150300,
                   variance='E|epsilon|^2=sigma^2; independent real/imag N(0,sigma^2/2)',
                   seed_rule='numpy default_rng(SeedSequence([150300,case_id,noise_index,replicate])); full (32,3,3) noise; center reused by all methods',
                   independence='Independent across realizations/cases/noise levels; methods and patch layouts paired within each realization'),
        patch=dict(shape=[3,3],moving='h=exp(-(u^2+v^2)/4)*exp(i*(0.3u-0.2v))',
                   contaminant_proportional='q=h',contaminant_different='q=h*(1+0.4u+0.2v)*exp(i*0.7*(u-v))',
                   coordinates='u,v in -1,0,1; center h=q=1',
                   noise='Independent absolute-variance noise per neighboring bin and time; same noise across layouts',
                   coherence='Use frozen local_msc on explicit first/last 3x3 arrays; do not infer MSC from center series'),
        event=dict(relative_abs_bias_threshold=.10,agreement_rad_s=.02,
                   definition='At least one pair of methods both valid, both relative absolute bias>0.1 and signed slopes within 0.02',
                   high_MSC=.8,high_R2=.97,
                   extra_quality='Also report event AND high A R2, event AND high endpoint MSC, and all three jointly; not estimator validity changes'),
        diagnostics=dict(amplitude_cv_alert=.3,min_amplitude_alert=.1,
                         lag_residual_rms_span_alert=.2,
                         dense_noiseless_time_samples=2049,
                         near_zero_analytic_floor=1e-12,
                         standalone_lag_fits='Noiseless configurations only, lags2/4/8; MC uses per-class residuals of C for lag diagnostics',
                         examples='Fixed s_true=.5 static cases: (ratio,phase_index)=(0,0),(.5,0),(.5,4),(1,4),(2,0); plus first lexicographic noiseless joint event with A_R2>=.97 and proportional_MSC>=.8 if present',
                         corrections='No real correction; no optional temporal-mean experiment beyond analytic unit test'),
        totals=dict(noiseless=291,monte_carlo=29100,all=29391),
        output_precision='Fits and CSV float64; residual archive float32, rounded storage only',
        guard_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in guarded if p.is_file()},
        source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in [Path(__file__),ROOT/'code/umbra_sar/contamination_diagnostic.py',ROOT/'tests/test_contamination_diagnostic.py']})
    write_json(OUT/'BLOCK15C_ATTRITION_AUDIT.json',documentary_attrition())
    write_json(CONFIG,cfg)
    print('Configuration frozen: 291 noiseless + 29100 noisy realizations; no real stack reads.')


def trial(case,sigma,noise_index,rep,cfg):
    t=np.asarray(cfg['inherited_Block15B']['time_s'])
    a,b=components(t,case['s_true'],case['ratio'],case['s_cont'],case['relative_phase'])
    rng=np.random.default_rng(np.random.SeedSequence([cfg['noise']['master_seed'],case['case_id'],noise_index,rep]))
    noise=complex_noise(rng,(len(t),3,3),sigma)
    z=a+b+noise[:,1,1]
    fits=fit_three(z,t,cfg['inherited_Block15B'])
    coherence=patch_coherences(a,b,noise)
    row=dict(**case,sigma=sigma,noise_index=noise_index,replicate=rep,
             min_amplitude=float(abs(z).min()),mean_amplitude=float(abs(z).mean()),
             amplitude_cv=float(abs(z).std()/abs(z).mean()),
             proportional_MSC=coherence['proportional']['endpoint_MSC'],
             different_MSC=coherence['different']['endpoint_MSC'],
             proportional_MSC_support=coherence['proportional']['valid'],
             different_MSC_support=coherence['different']['valid'])
    for method,fit in fits.items():
        error=fit['s_phi']-case['s_true']
        row.update({method+'_s_phi':fit['s_phi'],method+'_error':error,method+'_abs_error':abs(error),
                    method+'_relative_abs_error':abs(error)/abs(case['s_true']),
                    method+'_valid':fit['valid'],method+'_exclusions':fit['exclusions']})
        if method=='A':
            row.update(A_rmse=fit['rmse'],A_R2=fit['r2'],A_max_step=fit['max_adjacent_step'],
                       A_unwrap_valid=fit['unwrap_continuity_valid'])
        else:
            row.update({method+'_rms':fit['circular_rms'],method+'_cost':fit['cost'],
                        method+'_ambiguous':fit['ambiguous'],method+'_boundary':fit['boundary'],
                        method+'_minima':json.dumps(fit['minima'],separators=(',',':'))})
    agreement=cfg['event']['agreement_rad_s'];bias=cfg['event']['relative_abs_bias_threshold']
    pairs=[]
    for m,n in [('A','B'),('A','C'),('B','C')]:
        agrees=abs(fits[m]['s_phi']-fits[n]['s_phi'])<=agreement
        biased=row[m+'_relative_abs_error']>bias and row[n+'_relative_abs_error']>bias
        valid=fits[m]['valid'] and fits[n]['valid']
        row[m+n+'_agree']=agrees;row[m+n+'_joint_event']=bool(agrees and biased and valid)
        if row[m+n+'_joint_event']:pairs.append(m+n)
    row['joint_event']=bool(pairs);row['joint_pairs']=';'.join(pairs)
    row['estimator_spread']=float(np.ptp([f['s_phi'] for f in fits.values()]))
    C=fits['C'];res=np.asarray(C['residual']);labels=np.asarray(C['pair_lags'])
    lagrms=[float(np.sqrt(np.mean(res[labels==lag]**2))) for lag in (1,2,4,8)]
    row['lag_residual_rms_span']=max(lagrms)-min(lagrms)
    for lag,rms in zip((1,2,4,8),lagrms):row[f'C_lag{lag}_rms']=rms
    return row,fits,z


def run():
    cfg=json.loads(CONFIG.read_text());old=cfg['inherited_Block15B']
    for path,expected in cfg['guard_sha256'].items():assert digest(resolve_historical(path, ROOT))==expected,path
    target=OUT/'BLOCK15C_RESULTS.csv'
    if target.exists():raise RuntimeError('Preserve existing Block15C results; use explicit revision')
    total=cfg['totals']['all'];residuals={m:np.empty((total,n),np.float32) for m,n in [('A',32),('B',31),('C',113)]}
    examples=[];analytic=[];counter=0;start=time.time();last=time.time();selected_event=False
    time_axis=np.asarray(old['time_s']);dense=np.linspace(time_axis[0],time_axis[-1],cfg['diagnostics']['dense_noiseless_time_samples'])
    with target.open('x',newline='',encoding='utf-8') as stream:
        writer=None
        # All noiseless cases before either Monte Carlo noise level.
        for noise_index,(sigma,reps) in enumerate(zip(cfg['noise']['levels'],cfg['noise']['replicates'])):
            for case in cfg['cases']:
                if sigma==0:
                    inst=instantaneous_slope(dense,case['s_true'],case['ratio'],case['s_cont'],case['relative_phase'])
                    aa,bb=components(dense,case['s_true'],case['ratio'],case['s_cont'],case['relative_phase'])
                    finite=np.isfinite(inst)
                    analytic.append(dict(**case,min_dense_amplitude=float(abs(aa+bb).min()),
                        instantaneous_slope_min=float(inst[finite].min()) if finite.any() else None,
                        instantaneous_slope_max=float(inst[finite].max()) if finite.any() else None,
                        instantaneous_slope_mean_over_finite_samples=float(inst[finite].mean()) if finite.any() else None,
                        analytic_undefined_samples=int((~finite).sum()),
                        warning='At cancellations phase jumps are not represented by pointwise derivative; finite-sample mean is not necessarily net phase/record duration'))
                for rep in range(reps):
                    row,fits,z=trial(case,sigma,noise_index,rep,cfg)
                    row['realization_id']=counter
                    if writer is None:writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader()
                    writer.writerow(row)
                    for m in residuals:residuals[m][counter]=fits[m]['residual']
                    if sigma==0:
                        extra={}
                        options=dict(grid_size=old['search']['grid_size'],alternative_cost_margin=old['search']['alternative_cost_margin'],max_rms=old['validity']['circular_max_rms_rad'])
                        for lag in (2,4,8):
                            f=estimate_circular(z,time_axis,(lag,),old['search']['bounds'],**options)
                            extra[str(lag)]={k:f[k] for k in ('s_phi','valid','ambiguous','circular_rms','minima')}
                        analytic[-1]['standalone_lags']=extra
                        fixed=case['s_true']==.5 and case['s_cont']==0 and (case['ratio'],case['phase_index']) in [(0,0),(.5,0),(.5,4),(1,4),(2,0)]
                        joint=(not selected_event and row['joint_event'] and row['A_R2']>=cfg['event']['high_R2'] and row['proportional_MSC']>=cfg['event']['high_MSC'])
                        if fixed or joint:
                            examples.append(dict(selection='fixed parameter example' if fixed else 'first lexicographic high-quality biased-agreement event',
                                                 row=row,time_s=time_axis,z_real=z.real,z_imag=z.imag,fits=fits,
                                                 instantaneous_slope=instantaneous_slope(time_axis,case['s_true'],case['ratio'],case['s_cont'],case['relative_phase'])))
                        if joint:selected_event=True
                    counter+=1
                    if time.time()-last>20:
                        print(f'{counter}/{total} realizations; {time.time()-start:.1f}s',flush=True);last=time.time()
    assert counter==total
    np.savez_compressed(OUT/'BLOCK15C_RESIDUALS.npz',**residuals)
    write_json(OUT/'BLOCK15C_ANALYTIC_NOISELESS.json',analytic)
    write_json(OUT/'BLOCK15C_EXAMPLES.json',examples)
    for path,expected in cfg['guard_sha256'].items():assert digest(resolve_historical(path, ROOT))==expected,path
    write_json(OUT/'BLOCK15C_RUN_MANIFEST.json',dict(generated_utc=datetime.now(timezone.utc).isoformat(),
        configuration_sha256=digest(CONFIG),completed_realizations=counter,elapsed_s=time.time()-start,
        source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in [Path(__file__),ROOT/'code/umbra_sar/contamination_diagnostic.py']},
        previous_blocks_unchanged=True,real_arrays_read=False,seed_rule=cfg['noise']['seed_rule']))
    print('Finished',counter,'realizations in',time.time()-start,'s')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','run'])
    prepare() if p.parse_args().mode=='prepare' else run()

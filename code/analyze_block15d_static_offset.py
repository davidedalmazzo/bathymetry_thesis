"""M0/M1 predictive diagnostics on a frozen set of BP12 spectral bins."""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from analyze_block15b_frequency import ROOT,OUT,digest,write_json
from analyze_block12_phase_slope import tukey2d,detrended_spectrum
from umbra_sar.frequency_comparison import local_msc
from umbra_sar.static_offset_diagnostic import compare_models,fit_profile

CONFIG=OUT/'BLOCK15D_CONFIG.json'


def prepare():
    old=json.loads((OUT/'BLOCK15B_CONFIG.json').read_text())
    with (OUT/'BLOCK15B_BINS.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    bins=[(int(r['row']),int(r['col'])) for r in rows if r['intersection']=='True']
    peak=tuple(old['fixed_peak_index']);bins=sorted(set(bins)|{peak});bins.remove(peak);bins.insert(0,peak)
    guarded=list(OUT.glob('BLOCK15[ABC]_*'))+[ROOT/'code/umbra_sar/frequency_comparison.py',ROOT/'code/analyze_block12_phase_slope.py']
    t=np.asarray(old['time_s'])
    cfg=dict(created_utc=datetime.now(timezone.utc).isoformat(),previous_config=old,bins=bins,fixed_peak=peak,
        scope='Original intensity Fourier coefficients, no unit-modulus normalization, same BP12 preprocessing; no correction',
        fitting=dict(t0=float(t.mean()),bounds=old['search']['bounds'],grid_size=2001,
            profile_cost_margin=.01,folds=[list(range(i,i+8)) for i in (0,8,16,24)],
            criteria=dict(predictive_gain_min=.1,profile_width_max=.2,slope_span_max=.05,
                          ratio_cv_max=.5,offset_dispersion_max=.25,condition_max=1e6)),
        rationale=dict(profile='SSE normalized by observed training energy, margin 0.01; connected basin width, NOT a confidence interval',
            repeated_predictive='At least 10% aggregate held-out SSE improvement, improvement in >=3 folds including both edge blocks',
            stable='Full+four-fold M1 fits: no ambiguous/flat/boundary/rank-deficient profiles; width<=0.2 rad/s, slope span<=0.05 rad/s, ratio CV<=0.5, RMS complex c displacement / full |a|<=0.25',
            thresholds='Operational predeclared descriptors, not fitted to data or calibrated false-positive probabilities; report continuous values',
            categories='gain<=0: no_predictive_advantage; repeated and stable: repeated_predictive_stable; otherwise: descriptive_or_unstable'),
        synthetic=dict(slope=.5,a_phase=.3,offset_amplitude=.5,offset_phase=.8,
            slow_slope=.1,AM_depth=.4,AM_rate=.08,AM_phase=.5,
            noise_sigma=.1,AR1_rho=.8,replicates_each_noise=5,master_seed=150400,
            cases=['single','static_offset','amplitude_modulation','slow_contaminant'],
            noise_models=['none','white','AR1'],
            description='44 controls; stationary circular AR1 indexed by look, E|epsilon|^2=0.01, innovations scaled sqrt(1-rho^2); same realization for M0/M1'),
        figures='Show every selected bin (fixed peak first), including contrary cases; no fit-dependent bin reselection',
        dependence='Report grid distances, overlapping 3x3 support and empirical complex coefficient correlation; no independent component count or p-value',
        guard_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in guarded if p.is_file()},
        source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in [Path(__file__),ROOT/'code/umbra_sar/static_offset_diagnostic.py',ROOT/'tests/test_static_offset_diagnostic.py']})
    write_json(CONFIG,cfg);print('Frozen bins:',bins)


def synthetic():
    cfg=json.loads(CONFIG.read_text());spec=cfg['synthetic'];t=np.asarray(cfg['previous_config']['time_s']);tau=t-cfg['fitting']['t0']
    results=[]
    for ci,case in enumerate(spec['cases']):
        base=np.exp(1j*(spec['slope']*tau+spec['a_phase']))
        if case=='static_offset':base=base+spec['offset_amplitude']*np.exp(1j*spec['offset_phase'])
        if case=='amplitude_modulation':base=base*(1+spec['AM_depth']*np.cos(spec['AM_rate']*tau+spec['AM_phase']))
        if case=='slow_contaminant':base=base+spec['offset_amplitude']*np.exp(1j*(spec['slow_slope']*tau+spec['offset_phase']))
        for ni,model in enumerate(spec['noise_models']):
            for rep in range(1 if model=='none' else spec['replicates_each_noise']):
                rng=np.random.default_rng(np.random.SeedSequence([spec['master_seed'],ci,ni,rep]))
                innovation=spec['noise_sigma']/np.sqrt(2)*(rng.normal(size=32)+1j*rng.normal(size=32))
                if model=='none':noise=np.zeros(32,complex)
                elif model=='white':noise=innovation
                else:
                    noise=innovation.copy();rho=spec['AR1_rho']
                    for k in range(1,32):noise[k]=rho*noise[k-1]+np.sqrt(1-rho*rho)*innovation[k]
                result=compare_models(base+noise,t,cfg['fitting'])
                results.append(dict(case=case,noise=model,replicate=rep,result=result))
    write_json(OUT/'BLOCK15D_SYNTHETIC.json',results)
    print('Synthetic categories:',dict(Counter((r['case'],r['result']['category']) for r in results)))


def run():
    cfg=json.loads(CONFIG.read_text());assert (OUT/'BLOCK15D_SYNTHETIC.json').exists(),'Run synthetic controls first'
    for p,h in cfg['guard_sha256'].items():assert digest(ROOT/p)==h,p
    if (OUT/'BLOCK15D_RESULTS.json').exists():raise RuntimeError('Preserve existing outputs')
    old=cfg['previous_config'];stackpath=ROOT/old['stack']['path']
    assert stackpath.stat().st_size==old['stack']['bytes'] and stackpath.stat().st_mtime_ns==old['stack']['mtime_ns']
    stack=np.load(stackpath,mmap_mode='r');n,nr,nc=stack.shape;t=np.asarray(old['time_s'])
    window=tukey2d(nr,nc,.1);F=np.array([detrended_spectrum(abs(np.asarray(z))**2,window) for z in stack])
    msc,_=local_msc(F[0],F[-1]);bins=[tuple(x) for x in cfg['bins']]
    olddetails=json.loads((OUT/'BLOCK15B_ESTIMATOR_DETAILS.json').read_text())
    with (OUT/'BLOCK15B_BINS.csv').open(newline='') as f:oldrows={(int(r['row']),int(r['col'])):r for r in csv.DictReader(f)}
    results={};table=[];controls=[]
    for ix in bins:
        key=f'{ix[0]},{ix[1]}';z=F[:,ix[0],ix[1]]
        result=compare_models(z,t,cfg['fitting']);result.update(bin=list(ix),z_real=z.real.tolist(),z_imag=z.imag.tolist(),
            endpoint_MSC=float(msc[ix]),historical_phase=olddetails[key]['references']['16'],
            historical_lags=olddetails[key]['per_lag'])
        other=((-ix[0])%nr,(-ix[1])%nc);zz=F[:,other[0],other[1]]
        conjugate_error=float(np.max(abs(zz-z.conj()))/max(np.max(abs(z)),1e-30))
        mirror=fit_profile(zz,t,offset=True,t0=cfg['fitting']['t0'],bounds=cfg['fitting']['bounds'])
        controls.append(dict(bin=list(ix),conjugate=list(other),conjugate_in_sample=other in bins,
                             max_relative_coefficient_error=conjugate_error,slope_sign_closure=float(result['full']['M1']['s']+mirror['s']),
                             c_conjugate_error=float(abs(complex(*mirror['c'])-complex(*result['full']['M1']['c']).conjugate()))))
        row=dict(row=ix[0],col=ix[1],fixed_peak=list(ix)==cfg['fixed_peak'],
            wavelength_m=float(oldrows[ix]['wavelength_m']),kx=float(oldrows[ix]['kx_rad_m']),ky=float(oldrows[ix]['ky_rad_m']),
            endpoint_MSC=msc[ix],A_s_phi=float(oldrows[ix]['s_phi_A']),category=result['category'],
            training_relative_gain=result['training_relative_gain'],predictive_gain=result['relative_predictive_gain'],
            improved_folds=result['improved_folds'],slope_span=result['slope_span'],offset_ratio_cv=result['offset_ratio_cv'],
            complex_offset_dispersion=result['complex_offset_dispersion'],stability_flags=';'.join(result['stability_flags']))
        for m in ('M0','M1'):
            fit=result['full'][m]
            row.update({m+'_s':fit['s'],m+'_a_real':fit['a'][0],m+'_a_imag':fit['a'][1],m+'_c_real':fit['c'][0],m+'_c_imag':fit['c'][1],
                        m+'_offset_ratio':fit['offset_ratio'],m+'_train_SSE':fit['sse'],m+'_predictive_NMSE':result['predictive_nmse'][m],
                        m+'_ambiguous':fit['ambiguous'],m+'_boundary':fit['boundary'],m+'_profile_width':fit['profile_width']})
            for fold in result['folds']:row[f'{m}_fold{fold["index"]}_test_NMSE']=fold[m]['test_nmse']
        for fold in result['folds']:row[f'fold{fold["index"]}_gain']=fold['relative_SSE_gain']
        results[key]=result;table.append(row)
    dependence=[]
    for i,ix in enumerate(bins):
        for jx in bins[i+1:]:
            a=F[:,ix[0],ix[1]];b=F[:,jx[0],jx[1]];a=a-a.mean();b=b-b.mean()
            dr,dc=abs(ix[0]-jx[0]),abs(ix[1]-jx[1])
            dependence.append(dict(first=list(ix),second=list(jx),delta_row=dr,delta_col=dc,
                overlapping_MSC_cells=max(0,3-dr)*max(0,3-dc),
                centered_complex_correlation=float(abs(np.vdot(a,b))/np.sqrt(np.vdot(a,a).real*np.vdot(b,b).real))))
    write_json(OUT/'BLOCK15D_RESULTS.json',results)
    with (OUT/'BLOCK15D_BINS.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    syn=json.loads((OUT/'BLOCK15D_SYNTHETIC.json').read_text())
    summary=dict(bin_count=len(bins),fixed_peak=table[0],categories=dict(Counter(r['category'] for r in table)),
        predictive_gains=[r['predictive_gain'] for r in table],conjugate_controls=controls,
        spatial_dependence=dependence,
        synthetic_counts={case:{model:dict(Counter(r['result']['category'] for r in syn if r['case']==case and r['noise']==model)) for model in cfg['synthetic']['noise_models']} for case in cfg['synthetic']['cases']},
        note='Selected bins share pixels, spectral window and looks; neither bins nor folds are independent components/replicates. No corrected frequency.')
    write_json(OUT/'BLOCK15D_SUMMARY.json',summary)
    for p,h in cfg['guard_sha256'].items():assert digest(ROOT/p)==h,p
    print(json.dumps(dict(categories=summary['categories'],fixed=table[0]),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','synthetic','run'])
    mode=p.parse_args().mode
    {'prepare':prepare,'synthetic':synthetic,'run':run}[mode]()

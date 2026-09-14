"""Prepare a frozen config, then compare raw-bin estimators on BP12 only.

No CPHD/SICD reads, no inversion or external wave references. Existing results
are protected by exclusive creation and input SHA checks (small files only).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from analyze_block12_phase_slope import detrended_spectrum, tukey2d
from umbra_sar.frequency_comparison import local_msc, reference_fit, estimate_circular

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'Vandenberg/results/analysis_block15'
BP = ROOT/'Vandenberg/results/block12_backprojection'
CONFIG = OUT/'BLOCK15B_CONFIG.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict): return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, np.ndarray): return clean(value.tolist())
    if isinstance(value, np.generic): return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value): return None
    return value


def write_json(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(clean(value), f, indent=2, allow_nan=False)


def prepare():
    OUT.mkdir(exist_ok=True)
    manifest = json.loads((BP/'BLOCK12_SUBLOOK_MANIFEST.json').read_text())
    historical = ROOT/'Vandenberg/results/analysis_block12/BLOCK12_PHASE_SLOPE.json'
    old = json.loads(historical.read_text())
    inventory = json.loads((OUT/'BLOCK15A_INPUT_INVENTORY.json').read_text())
    audited = inventory['bp'][0]['verified_PVP_looks']
    t = np.asarray(manifest['mean_tx_time_per_look_s'])
    assert np.allclose(t, [x['verified_mean_TxTime_s'] for x in audited], atol=1e-12, rtol=0)
    stack = BP/'BLOCK12_SUBLOOKS_complex64.npy'
    header = np.load(stack, mmap_mode='r')
    guards = [BP/'BLOCK12_SUBLOOK_MANIFEST.json', historical,
              ROOT/'Vandenberg/results/analysis_block4/BLOCK4_PHASE_METRICS_SAR_ONLY.json',
              OUT/'BLOCK15A_AUDIT.md', OUT/'BLOCK15A_INPUT_INVENTORY.json',
              ROOT/'code/analyze_block12_phase_slope.py']
    cfg = dict(created_utc=datetime.now(timezone.utc).isoformat(),
        scope='BP12 estimator comparison, not CPHD formation validation',
        stack=dict(path=stack.relative_to(ROOT).as_posix(), bytes=stack.stat().st_size,
                   mtime_ns=stack.stat().st_mtime_ns, shape=list(header.shape), dtype=str(header.dtype)),
        manifest_path=(BP/'BLOCK12_SUBLOOK_MANIFEST.json').relative_to(ROOT).as_posix(),
        time_s=t.tolist(), grid=manifest['grid'],
        axes='axis0 k_parallel, axis1 k_perpendicular, rad/m; bearing from UTM grid north; not true north',
        preprocessing=dict(intensity='abs(complex64 z)**2 then float64 detrending',
                           detrend='historical global plane', tukey_alpha=0.1,
                           Fourier='historical fftshift(fft2); no padding; same coefficients A/B/C',
                           functions='analyze_block12_phase_slope.tukey2d/detrended_spectrum'),
        cross_convention='F_secondary * conj(F_reference)',
        coherence=dict(kind='magnitude_squared_coherence', box_size=3,
                       phase_smoothed=False, endpoint_threshold=0.3**2,
                       threshold_reason='square of original Block12 magnitude threshold 0.3; later 0.25 would map to 0.0625, only reported as sensitivity',
                       borders='invalid complete 3x3 patches; nonfinite or zero power invalid'),
        selection=dict(wavelength_m=[40.,500.], relative_power_min=0.05,
                       power_reference='max mean power in full wavelength band, no phase gate',
                       canonical_halfplane='kx<0 or (kx==0 and ky<0)',
                       common_quality='finite nonzero coefficients all looks, complete MSC patch, endpoint MSC>=0.09',
                       no_r2_or_dispersion_selection=True),
        fixed_peak_index=old['peak']['index'],
        methods=dict(A='raw reference OLS with free intercept; references 0,16,31',
                     B='direct consecutive circular objective, uniform pair weights',
                     C='direct circular objective, lags1,2,4,8; equal total weight per class',
                     lags=[1,2,4,8], reference_indices=[0,16,31]),
        search=dict(bounds=[float(-0.8*np.pi/max(np.diff(t))), float(0.8*np.pi/max(np.diff(t)))],
                    rationale='80% of pi/max adjacent dt; acquisition-only slow-branch restriction, not proof of absence of faster aliases',
                    grid_size=2001, alternative_cost_margin=0.01),
        validity=dict(A_max_step_rad=float(0.8*np.pi), A_max_rmse_rad=0.5,
                      circular_max_rms_rad=0.5, A_must_be_inside_search=True,
                      circular='unique minimum within cost margin, not boundary, RMS<=0.5',
                      differing_estimator_threshold_rad_s=0.02),
        frequency_reporting='s_phi signed only; ocean omega and period not identified; abs(s) only historical reproduction',
        uncertainty='descriptive; no independent-pair standard errors or confidence intervals',
        frozen_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in guards},
        source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in
                       [Path(__file__), ROOT/'code/umbra_sar/frequency_comparison.py']})
    write_json(CONFIG, cfg)
    print('Frozen configuration:', CONFIG)


def distribution(values):
    x = np.asarray(values, float)
    x = x[np.isfinite(x)]
    return dict(n=len(x), min=float(x.min()), median=float(np.median(x)),
                p90=float(np.percentile(x,90)), max=float(x.max())) if len(x) else dict(n=0)


def run():
    cfg = json.loads(CONFIG.read_text())
    if any(OUT.glob('BLOCK15B_SUMMARY*.json')) or (OUT/'BLOCK15B_BINS.csv').exists():
        raise RuntimeError('Block15B outputs already exist; preserve them and use an explicit revision')
    for path, expected in cfg['frozen_sha256'].items():
        assert digest(ROOT/path) == expected, f'Frozen input changed: {path}'
    p = ROOT/cfg['stack']['path']
    assert p.stat().st_size == cfg['stack']['bytes'] and p.stat().st_mtime_ns == cfg['stack']['mtime_ns']
    stack = np.load(p, mmap_mode='r')
    n, nr, nc = stack.shape; t = np.asarray(cfg['time_s']); bounds=cfg['search']['bounds']
    window = tukey2d(nr, nc, cfg['preprocessing']['tukey_alpha'])
    F = np.array([detrended_spectrum(np.abs(np.asarray(z))**2, window) for z in stack])
    if not np.isfinite(F).all(): raise ValueError('Nonfinite BP12 spectra: stop, do not silently repair input')
    power = np.mean(abs(F)**2, axis=0)
    spacing=cfg['grid']['spacing_m']
    kx, ky = np.meshgrid(2*np.pi*np.fft.fftshift(np.fft.fftfreq(nr,spacing)),
                         2*np.pi*np.fft.fftshift(np.fft.fftfreq(nc,spacing)), indexing='ij')
    k = np.hypot(kx,ky); wavelength=np.full(k.shape,np.inf)
    np.divide(2*np.pi,k,out=wavelength,where=k>0)
    low,high=cfg['selection']['wavelength_m'];band=(wavelength>=low)&(wavelength<=high)
    half=(kx<0)|((kx==0)&(ky<0));domain=band&half
    fixed=tuple(cfg['fixed_peak_index']);peakpower=power[band].max();relative=power/peakpower
    endpoint, supported=local_msc(F[0],F[-1])
    adjacent=np.array([local_msc(a,b)[0] for a,b in zip(F[:-1],F[1:])])
    nonzero=np.all(abs(F)>0,axis=0)
    pre=domain&(relative>cfg['selection']['relative_power_min'])&nonzero
    common=pre&supported&(endpoint>=cfg['coherence']['endpoint_threshold'])
    evaluate=pre.copy();evaluate[fixed]=True
    # Historical reproduction, unchanged raw phase and buggy gate, diagnostic only.
    phase=np.unwrap(np.angle(F*F[16].conj()),axis=0)
    tc=t-t.mean(); historical_s=np.tensordot(tc,phase,axes=(0,0))/np.dot(tc,tc)
    legacy_gamma=abs(F[0]*F[-1].conj())/np.sqrt(abs(F[0])**2*abs(F[-1])**2+1e-30)
    legacy_mask=band&(legacy_gamma>=0.3)&np.isfinite(historical_s)
    historical_peak=tuple(np.unravel_index(np.argmax(np.where(legacy_mask,power,-np.inf)),power.shape))
    oldmap=ROOT/'Vandenberg/results/analysis_block12/BLOCK12_PHASE_SLOPE_MAP.npz'
    with np.load(oldmap) as old:
        reproduction=dict(historical_peak_index=list(historical_peak), fixed_peak_index=list(fixed),
            max_slope_difference_rad_s=float(np.max(abs(historical_s-old['slope_rad_per_s']))),
            fixed_signed_s_phi=float(historical_s[fixed]),
            fixed_abs_s_difference=float(abs(historical_s[fixed])-0.4120656492031189),
            mask_equal=bool(np.array_equal(legacy_mask,old['valid_mask'])))
    rows=[];details={};cs_kwargs=dict(grid_size=cfg['search']['grid_size'],
        alternative_cost_margin=cfg['search']['alternative_cost_margin'], max_rms=cfg['validity']['circular_max_rms_rad'])
    for i,j in zip(*np.where(domain | evaluate)):
        ix=(i,j); isfixed=ix==fixed
        reasons=[]
        if not pre[ix]: reasons.append('below_power_or_outside_canonical_band_or_zero')
        if not supported[ix]:reasons.append('MSC_patch_invalid')
        if endpoint[ix]<cfg['coherence']['endpoint_threshold']:reasons.append('low_endpoint_MSC')
        row=dict(row=int(i),col=int(j),kx_rad_m=kx[ix],ky_rad_m=ky[ix],k_rad_m=k[ix],
                 wavelength_m=wavelength[ix],angle_from_parallel_deg=np.degrees(np.arctan2(ky[ix],kx[ix])),
                 vector_bearing_grid_north_deg=(cfg['grid']['bearing_deg']+np.degrees(np.arctan2(ky[ix],kx[ix])))%360,
                 power=power[ix],relative_power=relative[ix],endpoint_MSC=endpoint[ix],
                 min_adjacent_MSC=float(adjacent[:,i,j].min()),fixed_diagnostic=isfixed,
                 pre_coherence_candidate=bool(pre[ix]),common_candidate=bool(common[ix]),
                 common_exclusions=';'.join(reasons),evaluated=bool(evaluate[ix]),
                 s_phi_A=None,s_phi_B=None,s_phi_C=None,A_valid=False,B_valid=False,C_valid=False,intersection=False)
        if evaluate[ix] and nonzero[ix]:
            z=F[:,i,j]
            refs={str(ref):reference_fit(z,t,ref,cfg['validity']['A_max_step_rad']) for ref in (0,16,31)}
            A=refs['16'];B=estimate_circular(z,t,(1,),bounds,**cs_kwargs)
            C=estimate_circular(z,t,(1,2,4,8),bounds,**cs_kwargs)
            bylag={'1':B,**{str(lag):estimate_circular(z,t,(lag,),bounds,**cs_kwargs) for lag in (2,4,8)}}
            av=A['unwrap_continuity_valid'] and A['rmse']<=cfg['validity']['A_max_rmse_rad'] and bounds[0]<A['s_phi']<bounds[1]
            row.update(s_phi_A=A['s_phi'],s_phi_B=B['s_phi'],s_phi_C=C['s_phi'],
                       A_valid=bool(av),B_valid=B['valid'],C_valid=C['valid'],
                       intersection=bool(common[ix] and av and B['valid'] and C['valid']),
                       A_rmse=A['rmse'],A_R2=A['r2'],A_max_step=A['max_adjacent_step'],
                       A_unwrap_valid=A['unwrap_continuity_valid'],
                       reference_slope_span=float(np.ptp([v['s_phi'] for v in refs.values()])),
                       telescoping_error=A['telescoping_error'],
                       B_rms=B['circular_rms'],C_rms=C['circular_rms'],
                       B_ambiguous=B['ambiguous'],C_ambiguous=C['ambiguous'],
                       B_boundary=B['boundary'],C_boundary=C['boundary'],
                       delta_B_A=B['s_phi']-A['s_phi'],delta_C_A=C['s_phi']-A['s_phi'])
            for name, fit in [('A',A),('B',B),('C',C)]:
                why=[]
                if name=='A':
                    if not A['unwrap_continuity_valid']:why.append('large_wrapped_step')
                    if A['rmse']>0.5:why.append('high_unwrapped_RMSE')
                    if not bounds[0]<A['s_phi']<bounds[1]:why.append('outside_search')
                else:
                    if fit['ambiguous']:why.append('alternative_minimum')
                    if fit['boundary']:why.append('search_boundary')
                    if fit['circular_rms']>0.5:why.append('high_circular_RMS')
                row[name+'_exclusions']=';'.join(why)
            for lag,fit in bylag.items():
                row.update({f'lag{lag}_s_phi':fit['s_phi'],f'lag{lag}_valid':fit['valid'],
                            f'lag{lag}_ambiguous':fit['ambiguous']})
            details[f'{i},{j}']=dict(references=refs,B=B,C=C,per_lag=bylag)
        rows.append(row)
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with (OUT/'BLOCK15B_BINS.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    accepted=[r for r in rows if r['intersection']]
    evaluated=[r for r in rows if r['evaluated'] and r['s_phi_A'] is not None]
    threshold=cfg['validity']['differing_estimator_threshold_rad_s']
    differences=lambda group:dict(count=len(group),
        abs_B_minus_A=distribution([abs(r['delta_B_A']) for r in group]),
        abs_C_minus_A=distribution([abs(r['delta_C_A']) for r in group]),
        over_threshold_B=sum(abs(r['delta_B_A'])>threshold for r in group),
        over_threshold_C=sum(abs(r['delta_C_A'])>threshold for r in group))
    fixedrow=next(r for r in rows if r['fixed_diagnostic'])
    # Synthetic same-k static contamination, no SAR formation and no tuning.
    synthetic=[]
    for static in (0.,0.5,1.4):
        z=np.exp(-0.61j*t)+static*np.exp(0.4j)
        A=reference_fit(z,t,16);B=estimate_circular(z,t,(1,),bounds,**cs_kwargs)
        C=estimate_circular(z,t,(1,2,4,8),bounds,**cs_kwargs)
        synthetic.append(dict(static_amplitude=static,mobile_s_phi=-0.61,A=A,B=B,C=C))
    summary=dict(generated_utc=datetime.now(timezone.utc).isoformat(),reproduction=reproduction,
        counts=dict(domain=int(domain.sum()),pre_MSC=int(pre.sum()),common=int(common.sum()),
                    rejected_by_MSC=int((pre&~common).sum()),
                    alternative_threshold_00625=int((pre&supported&(endpoint>=0.0625)).sum()),
                    intersection=len(accepted),A_valid_common=sum(r['common_candidate'] and r['A_valid'] for r in rows),
                    B_valid_common=sum(r['common_candidate'] and r['B_valid'] for r in rows),
                    C_valid_common=sum(r['common_candidate'] and r['C_valid'] for r in rows)),
        all_evaluated=differences(evaluated),intersection=differences(accepted),
        common_candidates=differences([r for r in evaluated if r['common_candidate']]),
        low_MSC=differences([r for r in evaluated if not r['common_candidate']]),
        reference_span=distribution([r['reference_slope_span'] for r in evaluated]),
        telescoping_error=distribution([abs(r['telescoping_error']) for r in evaluated]),
        fixed_peak=fixedrow, conditional_ocean_frequency=None,
        caution='Same coefficients and dependent pairs: agreement is not independent ocean-frequency validation; branch conditional on configured bounds.',
        per_lag={str(l):dict(valid_evaluated=sum(r[f'lag{l}_valid'] for r in evaluated),
                            ambiguous_evaluated=sum(r[f'lag{l}_ambiguous'] for r in evaluated)) for l in (1,2,4,8)})
    write_json(OUT/'BLOCK15B_SUMMARY.json',summary)
    write_json(OUT/'BLOCK15B_ESTIMATOR_DETAILS.json',details)
    write_json(OUT/'BLOCK15B_SYNTHETIC_CONTAMINATION.json',synthetic)
    figures(rows, details, cfg, fixed, synthetic)
    for path, expected in cfg['frozen_sha256'].items():assert digest(ROOT/path)==expected
    write_json(OUT/'BLOCK15B_MANIFEST.json',dict(config_sha256=digest(CONFIG),input=cfg['stack'],
        config_written_before_analysis=True, interpreter=sys.executable,
        source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in [Path(__file__),ROOT/'code/umbra_sar/frequency_comparison.py']},
        frozen_inputs_unchanged=True,radar_sources_read=False,formation_validated=False,
        outputs=[p.name for p in sorted(OUT.glob('BLOCK15B_*'))]))
    print(json.dumps(clean(summary),indent=2))


def figures(rows,details,cfg,fixed,synthetic):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    good=[r for r in rows if r['intersection']]
    evaluated=[r for r in rows if r['evaluated'] and r['s_phi_A'] is not None]
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    for key,color,label in [('s_phi_B','C0','B consecutive'),('s_phi_C','C1','C multi-lag')]:
        axes[0].scatter([r['s_phi_A'] for r in good],[r[key] for r in good],s=18,label=label,color=color)
    if good:
        lim=[min(r['s_phi_A'] for r in good),max(r['s_phi_A'] for r in good)]
        axes[0].plot(lim,lim,'k--',lw=1)
    axes[0].set(xlabel='A s_phi [rad/s]',ylabel='B / C s_phi [rad/s]',title='Common valid intersection');axes[0].legend()
    for ax,key,title in zip(axes[1:],['delta_B_A','delta_C_A'],['B - A','C - A']):
        vals=[r[key] for r in evaluated];limit=max(0.02,max(abs(v) for v in vals))
        im=ax.scatter([r['kx_rad_m'] for r in evaluated],[r['ky_rad_m'] for r in evaluated],c=vals,cmap='coolwarm',vmin=-limit,vmax=limit,s=25)
        bad=[r for r in evaluated if not r['intersection']]
        ax.scatter([r['kx_rad_m'] for r in bad],[r['ky_rad_m'] for r in bad],facecolors='none',edgecolors='k',s=42,linewidths=.5)
        ax.set(xlabel='k_parallel [rad/m]',ylabel='k_perp [rad/m]',title=title+' (rings: excluded)');fig.colorbar(im,ax=ax,label='rad/s')
    fig.savefig(OUT/'BLOCK15B_COMPARISON.png',dpi=170);plt.close(fig)
    d=details[f'{fixed[0]},{fixed[1]}'];a=d['references']['16'];t=np.asarray(cfg['time_s'])
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    axes[0,0].plot(t,a['wrapped'],'o',label='wrapped');axes[0,0].plot(t,a['unwrapped'],'.-',label='unwrapped');axes[0,0].plot(t,a['fitted'],'--',label='A fit')
    axes[0,0].set(ylabel='Phase [rad]',title=f'Fixed BP12 bin {fixed}');axes[0,0].legend()
    axes[0,1].plot(t,a['residual'],'o-');axes[0,1].axhline(0,color='k',lw=.5);axes[0,1].set(ylabel='A residual [rad]',title='Descriptive residuals, no iid CI')
    for lag, fit in d['per_lag'].items():
        x=np.mean(fit['delta_t']);axes[1,0].plot(x,fit['s_phi'],'o',mfc='none' if not fit['valid'] else 'C0',color='C0')
        axes[1,0].annotate(lag,(x,fit['s_phi']))
        for alt in fit['minima'][1:]:
            if alt['cost']<=fit['cost']+cfg['search']['alternative_cost_margin']:
                axes[1,0].plot(x,alt['s_phi'],'x',color='0.6')
    axes[1,0].axhline(a['s_phi'],label='A',color='C1');axes[1,0].axhline(d['C']['s_phi'],label='C',color='C2',ls='--')
    axes[1,0].set(xlabel='Mean actual lag [s]',ylabel='s_phi [rad/s]',title='Open: invalid; x: competing minima');axes[1,0].legend()
    grid=np.linspace(*cfg['search']['bounds'],1001)
    for name in ('B','C'):
        fit=d[name];p=np.array(fit['pair_phase']);dt=np.array(fit['delta_t']);w=np.array(fit['pair_weights'])
        axes[1,1].plot(grid,(1-np.cos(p[None]-grid[:,None]*dt))@w,label=name)
    axes[1,1].set(xlabel='s_phi [rad/s]',ylabel='Circular cost',title='Entire predeclared search interval');axes[1,1].legend()
    for ax in axes[0]:ax.set_xlabel('Physical mean TxTime [s]')
    fig.savefig(OUT/'BLOCK15B_FIXED_PEAK.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4),layout='constrained')
    for r in good:
        ax.plot([1,2,4,8],[r[f'lag{l}_s_phi'] for l in (1,2,4,8)],color='0.7',alpha=.5)
    ax.plot([1,2,4,8],[d['per_lag'][str(l)]['s_phi'] for l in (1,2,4,8)],'o-',color='C3',label='fixed peak')
    ax.set(xlabel='Lag [look count; fit uses actual delta_t]',ylabel='s_phi [rad/s]',title='Per-lag global minima: aliases may be invalid');ax.legend()
    fig.savefig(OUT/'BLOCK15B_LAG_DEPENDENCE.png',dpi=170);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','run']);args=parser.parse_args()
    prepare() if args.mode=='prepare' else run()

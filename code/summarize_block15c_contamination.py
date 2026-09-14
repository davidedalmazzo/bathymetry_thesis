"""Summaries with explicit denominators; descriptive diagnostics, not tuning."""
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from analyze_block15b_frequency import OUT,write_json


def quantiles(values):
    x=np.asarray(values,float);x=x[np.isfinite(x)]
    if not len(x):return dict(n=0)
    return dict(n=len(x),mean=float(x.mean()),min=float(x.min()),q05=float(np.percentile(x,5)),
                q25=float(np.percentile(x,25)),median=float(np.median(x)),q75=float(np.percentile(x,75)),
                q95=float(np.percentile(x,95)),max=float(x.max()))


def load_rows():
    with (OUT/'BLOCK15C_RESULTS.csv').open(newline='') as f:
        data=list(csv.DictReader(f))
    for r in data:
        for k,v in r.items():
            if v in ('True','False'):r[k]=v=='True'
            elif k.endswith('_minima') or k.endswith('_exclusions') or k=='joint_pairs':continue
            else:r[k]=float(v)
    return data


def summarize(rows,cfg):
    n=len(rows);event=[r for r in rows if r['joint_event']]
    high_r2=cfg['event']['high_R2'];high_msc=cfg['event']['high_MSC']
    result=dict(n=n,joint_event_count=len(event),joint_event_fraction=len(event)/n,
        high_R2_joint_count=sum(r['A_R2']>=high_r2 for r in event),
        proportional_high_MSC_joint_count=sum(r['proportional_MSC']>=high_msc for r in event),
        different_high_MSC_joint_count=sum(r['different_MSC']>=high_msc for r in event),
        high_R2_and_proportional_high_MSC_joint_count=sum(r['A_R2']>=high_r2 and r['proportional_MSC']>=high_msc for r in event),
        high_R2_and_different_high_MSC_joint_count=sum(r['A_R2']>=high_r2 and r['different_MSC']>=high_msc for r in event),
        all_three_valid_count=sum(all(r[m+'_valid'] for m in 'ABC') for r in rows),
        methods={})
    for m in 'ABC':
        accepted=[r for r in rows if r[m+'_valid']]
        result['methods'][m]=dict(accepted=len(accepted),acceptance_fraction=len(accepted)/n,
            all_signed_error=quantiles([r[m+'_error'] for r in rows]),
            all_relative_abs_error=quantiles([r[m+'_relative_abs_error'] for r in rows]),
            accepted_signed_error=quantiles([r[m+'_error'] for r in accepted]),
            accepted_relative_abs_error=quantiles([r[m+'_relative_abs_error'] for r in accepted]),
            accepted_biased_count=sum(r[m+'_relative_abs_error']>cfg['event']['relative_abs_bias_threshold'] for r in accepted))
    return result


def main(plot_only=False):
    cfg=json.loads((OUT/'BLOCK15C_CONFIG.json').read_text());rows=load_rows()
    assert len(rows)==cfg['totals']['all']
    if plot_only:
        figures(rows,json.loads((OUT/'BLOCK15C_SUMMARY.json').read_text()),cfg)
        return
    report=dict(total_count=len(rows),denominator_warning='Fractions refer to this designed grid, not a prior probability of ocean contamination. Noise levels reported separately. Phase duplicates omitted only at ratio=0.',
        by_noise={},by_ratio_and_noise={},by_contaminant_and_noise={},diagnostic_alerts={})
    d=cfg['diagnostics'];alerts={
        'amplitude_cv_gt_03':lambda r:r['amplitude_cv']>d['amplitude_cv_alert'],
        'min_amplitude_lt_01':lambda r:r['min_amplitude']<d['min_amplitude_alert'],
        'A_R2_below_097':lambda r:r['A_R2']<cfg['event']['high_R2'],
        'any_method_invalid':lambda r:not all(r[m+'_valid'] for m in 'ABC'),
        'estimator_spread_gt_002':lambda r:r['estimator_spread']>cfg['event']['agreement_rad_s'],
        'lag_residual_rms_span_gt_02':lambda r:r['lag_residual_rms_span']>d['lag_residual_rms_span_alert'],
        'proportional_MSC_below_08':lambda r:r['proportional_MSC']<cfg['event']['high_MSC'],
        'different_MSC_below_08':lambda r:r['different_MSC']<cfg['event']['high_MSC']}
    for noise in cfg['noise']['levels']:
        group=[r for r in rows if r['sigma']==noise];key=str(noise)
        report['by_noise'][key]=summarize(group,cfg)
        event=[r for r in group if r['joint_event']];control=[r for r in group if r['ratio']==0]
        report['diagnostic_alerts'][key]={name:dict(event_n=len(event),event_flagged=sum(fn(r) for r in event),
             control_n=len(control),control_false_alerts=sum(fn(r) for r in control)) for name,fn in alerts.items()}
        report['diagnostic_alerts'][key]['any_alert']=dict(event_n=len(event),
            event_flagged=sum(any(fn(r) for fn in alerts.values()) for r in event),control_n=len(control),
            control_false_alerts=sum(any(fn(r) for fn in alerts.values()) for r in control))
        for ratio in (0.,.25,.5,1.,2.):
            report['by_ratio_and_noise'][f'{noise}:{ratio}']=summarize([r for r in group if r['ratio']==ratio],cfg)
        for frac in (0.,-.2,.2):
            subgroup=[r for r in group if r['cont_fraction']==frac and r['ratio']>0]
            report['by_contaminant_and_noise'][f'{noise}:{frac}']=summarize(subgroup,cfg)
    write_json(OUT/'BLOCK15C_SUMMARY.json',report)
    groups=defaultdict(list)
    for r in rows:groups[(r['case_id'],r['sigma'])].append(r)
    aggregates=[]
    for (case_id,sigma),group in groups.items():
        row={k:group[0][k] for k in ('case_id','s_true','ratio','cont_fraction','relative_phase','phase_index','sigma')}
        summary=summarize(group,cfg)
        row.update(n=len(group),joint_event_fraction=summary['joint_event_fraction'],
                   joint_high_R2_fraction=summary['high_R2_joint_count']/len(group),
                   joint_high_MSC_proportional_fraction=summary['proportional_high_MSC_joint_count']/len(group),
                   joint_high_MSC_different_fraction=summary['different_high_MSC_joint_count']/len(group))
        for method in 'ABC':
            s=summary['methods'][method]
            row.update({method+'_acceptance_fraction':s['acceptance_fraction'],
                        method+'_mean_signed_error':s['all_signed_error']['mean'],
                        method+'_median_relative_abs_error':s['all_relative_abs_error']['median'],
                        method+'_accepted_median_relative_abs_error':s['accepted_relative_abs_error'].get('median')})
        aggregates.append(row)
    with (OUT/'BLOCK15C_AGGREGATES.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(aggregates[0]));writer.writeheader();writer.writerows(aggregates)
    figures(rows,report,cfg)
    print(json.dumps({k:{name:value for name,value in v.items() if name!='methods'} for k,v in report['by_noise'].items()},indent=2))


def figures(rows,summary,cfg):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    # Fixed slice, specified before inspection: s_true=.5, no noise, all fractions.
    ratios=[0.,.25,.5,1.,2.];fractions=[0.,-.2,.2]
    fig,axes=plt.subplots(3,3,figsize=(12,10),layout='constrained')
    for i,frac in enumerate(fractions):
        for j,m in enumerate('ABC'):
            a=np.empty((5,8));accepted=np.empty((5,8),bool)
            for ri,ratio in enumerate(ratios):
                for phase in range(8):
                    r=next(r for r in rows if r['sigma']==0 and r['s_true']==.5 and r['ratio']==ratio and
                           (ratio==0 or (r['cont_fraction']==frac and r['phase_index']==phase)))
                    a[ri,phase]=r[m+'_error']/.5;accepted[ri,phase]=r[m+'_valid']
            im=axes[i,j].imshow(a,origin='lower',aspect='auto',vmin=-1.5,vmax=1.5,cmap='coolwarm')
            y,x=np.where(~accepted);axes[i,j].scatter(x,y,marker='x',s=18,c='k')
            axes[i,j].set(xticks=range(8),xticklabels=[str(x) for x in range(8)],yticks=range(5),yticklabels=ratios,
                          xlabel='Relative phase / (pi/4)',ylabel='B/A (amplitude)',title=f'{m}: s_cont/s_true={frac:g}')
    fig.colorbar(im,ax=axes,label='Signed error / s_true; x = invalid',shrink=.8)
    fig.savefig(OUT/'BLOCK15C_BIAS_PHASE.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(12,7),layout='constrained')
    for j,sigma in enumerate(cfg['noise']['levels']):
        for method in 'ABC':
            values=[summary['by_ratio_and_noise'][f'{sigma}:{r}']['methods'][method] for r in ratios]
            color={'A':'C0','B':'C1','C':'C2'}[method]
            axes[0,j].plot(ratios,[v['acceptance_fraction'] for v in values],'o-',label=method,color=color)
            axes[1,j].plot(ratios,[v['all_relative_abs_error']['median'] for v in values],'o-',label=method+' all',color=color)
            axes[1,j].plot(ratios,[v['accepted_relative_abs_error'].get('median',np.nan) for v in values],'x--',label=method+' accepted',color=color)
        axes[0,j].set(title=f'Noise RMS/A={sigma:g}',ylim=(-.03,1.03),ylabel='Acceptance fraction',xlabel='B/A')
        axes[1,j].set(ylabel='Median absolute relative bias',xlabel='B/A');axes[1,j].axhline(.1,color='k',lw=.6)
    axes[0,0].legend();axes[1,2].legend(fontsize=7)
    fig.savefig(OUT/'BLOCK15C_ACCEPTANCE.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
    # Show full noiseless set: no survivor filtering.
    selected=[r for r in rows if r['sigma']==0]
    color=[r['ratio'] for r in selected]
    for ax,key,label in zip(axes,['A_R2','proportional_MSC','different_MSC'],['A R squared','Proportional patch MSC','Different patch MSC']):
        im=ax.scatter([r[key] for r in selected],[r['A_relative_abs_error'] for r in selected],c=color,cmap='viridis',s=18)
        event=[r for r in selected if r['joint_event']]
        ax.scatter([r[key] for r in event],[r['A_relative_abs_error'] for r in event],facecolors='none',edgecolors='r',s=45,label='biased valid agreement pair')
        ax.axhline(.1,color='k',lw=.7);ax.set(xlabel=label,ylabel='A absolute relative bias',title='Noiseless: all cases')
    fig.colorbar(im,ax=axes,label='B/A');axes[0].legend(fontsize=7)
    fig.savefig(OUT/'BLOCK15C_QUALITY_MSC.png',dpi=150);plt.close(fig)
    examples=json.loads((OUT/'BLOCK15C_EXAMPLES.json').read_text());n=len(examples)
    fig,axes=plt.subplots(n,3,figsize=(12,2.6*n),layout='constrained',squeeze=False)
    for i,e in enumerate(examples):
        t=np.asarray(e['time_s']);z=np.asarray(e['z_real'])+1j*np.asarray(e['z_imag']);r=e['row'];a=e['fits']['A']
        axes[i,0].plot(t,abs(z),'o-',ms=3);axes[i,0].set(ylabel='|F|',title=f"s={r['s_true']}, B/A={r['ratio']}, phase/pi={r['relative_phase']/np.pi:.2g}")
        axes[i,1].plot(t,a['unwrapped'],'o-',ms=3,label='mixture phase');axes[i,1].plot(t,a['fitted'],'--',label='A');axes[i,1].set(ylabel='Phase [rad]')
        axes[i,2].plot(t,e['instantaneous_slope'],'.-',label='analytic instantaneous')
        axes[i,2].axhline(r['s_true'],color='k',ls='--',label='component truth')
        for m in 'ABC':axes[i,2].axhline(e['fits'][m]['s_phi'],label=m,alpha=.8,
            color={'A':'C1','B':'C2','C':'C3'}[m],ls={'A':'-','B':':','C':'-.'}[m])
        axes[i,2].set(ylabel='Phase rate [rad/s]')
        for ax in axes[i]:ax.set_xlabel('BP12 mean TxTime [s]')
    axes[0,1].legend(fontsize=7);axes[0,2].legend(fontsize=7,ncol=2)
    fig.savefig(OUT/'BLOCK15C_EXAMPLES.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plot-only',action='store_true')
    main(parser.parse_args().plot_only)

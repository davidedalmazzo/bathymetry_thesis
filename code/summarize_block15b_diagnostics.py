"""Descriptive post-fit summaries only; no selection or estimator changes."""
import csv
import json
from collections import Counter

import numpy as np

from analyze_block15b_frequency import OUT, CONFIG, write_json, distribution


def main(plot_only=False):
    cfg=json.loads(CONFIG.read_text())
    details=json.loads((OUT/'BLOCK15B_ESTIMATOR_DETAILS.json').read_text())
    synth=json.loads((OUT/'BLOCK15B_SYNTHETIC_CONTAMINATION.json').read_text())
    with (OUT/'BLOCK15B_BINS.csv').open(newline='') as f:
        rows=list(csv.DictReader(f))
    ev=[r for r in rows if r['evaluated']=='True']
    good=[r for r in ev if r['intersection']=='True']
    num=lambda r,k:float(r[k])
    def group_summary(group):
        return dict(n=len(group),signed_B_minus_A=distribution([num(r,'delta_B_A') for r in group]),
                    signed_C_minus_A=distribution([num(r,'delta_C_A') for r in group]),
                    k_perp=distribution([num(r,'ky_rad_m') for r in group]),
                    endpoint_MSC=distribution([num(r,'endpoint_MSC') for r in group]),
                    min_adjacent_MSC=distribution([num(r,'min_adjacent_MSC') for r in group]))
    categories={}
    for label,lo,hi in [('parallel_0_10_deg',0,10),('oblique_10_30_deg',10,30),('oblique_30_90_deg',30,90.001)]:
        selected=[r for r in ev if lo<=np.degrees(np.arctan2(abs(num(r,'ky_rad_m')),abs(num(r,'kx_rad_m'))))<hi]
        categories[label]=dict(evaluated=group_summary(selected),
                              intersection=group_summary([r for r in selected if r['intersection']=='True']))
    fixed=details[','.join(map(str,cfg['fixed_peak_index']))]
    t=np.asarray(cfg['time_s']);ph=np.asarray(fixed['references']['16']['unwrapped'])
    dt=np.asarray(fixed['B']['delta_t']);dp=np.asarray(fixed['B']['pair_phase'])
    s_endpoint=(ph[-1]-ph[0])/(t[-1]-t[0])
    pair_dt=t[None,:]-t[:,None];pair_dp=ph[None,:]-ph[:,None]
    tri=np.triu(np.ones(pair_dt.shape,dtype=bool),1)
    pair_ols=np.sum(pair_dt[tri]*pair_dp[tri])/np.sum(pair_dt[tri]**2)
    out=dict(scope='Post-fit descriptive summaries; no new cuts, branches or estimators applied to real input',
        intersection=group_summary(good),orientation_groups=categories,
        exclusions={method:dict(Counter(reason for r in ev for reason in r[method+'_exclusions'].split(';') if reason)) for method in ('A','B','C')},
        fixed_endpoint_s_phi=float(s_endpoint),
        fixed_linearized_consecutive_objective_s_phi=float(np.sum(dt*dp)/np.sum(dt**2)),
        fixed_all_pair_OLS_identity_s_phi=float(pair_ols),
        fixed_per_lag_minima={lag:dict(mean_delta_t=float(np.mean(fit['delta_t'])),minima=fit['minima']) for lag,fit in fixed['per_lag'].items()},
        synthetic=[dict(static_amplitude=s['static_amplitude'],mobile_s_phi=s['mobile_s_phi'],
                        A_s_phi=s['A']['s_phi'],B_s_phi=s['B']['s_phi'],C_s_phi=s['C']['s_phi'],
                        A_rmse=s['A']['rmse'],B_rms=s['B']['circular_rms'],C_rms=s['C']['circular_rms'],
                        B_valid=s['B']['valid'],C_valid=s['C']['valid']) for s in synth],
        limits='Orientation/quality associations are descriptive, not significance tests. Equal lag-class cost weights do not equalize curvature in slope: Hessian includes delta_t squared.')
    if not plot_only:
        write_json(OUT/'BLOCK15B_DIAGNOSTICS.json',out)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13,4.3),layout='constrained')
    for ax,key,title in zip(axes[:2],['delta_B_A','delta_C_A'],['B - A','C - A']):
        ax.scatter([num(r,'kx_rad_m') for r in ev],[num(r,'ky_rad_m') for r in ev],s=9,color='0.85')
        im=ax.scatter([num(r,'kx_rad_m') for r in good],[num(r,'ky_rad_m') for r in good],
                      c=[num(r,key) for r in good],cmap='coolwarm',vmin=-.05,vmax=.05,s=55,edgecolors='k',linewidths=.4)
        ax.set(xlabel='k_parallel [rad/m]',ylabel='k_perp [rad/m]',title=title+' : 15 jointly valid bins')
        fig.colorbar(im,ax=ax,label='rad/s')
    for name,color in [('A','C0'),('B','C1'),('C','C2')]:
        axes[2].plot([s['static_amplitude'] for s in synth],[s[name]['s_phi'] for s in synth],'o-',label=name,color=color)
    axes[2].axhline(-.61,color='k',ls='--',label='mobile truth')
    axes[2].set(xlabel='Static / moving amplitude at same k',ylabel='s_phi [rad/s]',title='Synthetic same-k mixture');axes[2].legend()
    fig.savefig(OUT/'BLOCK15B_VALID_BINS_AND_MIXTURE.png',dpi=170);plt.close(fig)
    if not plot_only:
        print(json.dumps(out,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plot-only', action='store_true')
    main(parser.parse_args().plot_only)

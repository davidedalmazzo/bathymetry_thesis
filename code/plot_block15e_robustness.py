"""Plots of stored Block15E diagnostics; no model fitting."""
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_block15e_robustness import OUT,read


def main():
    cfg=read('BLOCK15E_CONFIG.json');real=read('BLOCK15E_REAL.json');old=read('BLOCK15D_RESULTS.json');t=np.array(cfg['time_s'])
    with (OUT/'BLOCK15E_NULL_DISTRIBUTIONS.csv').open() as f:rows=list(csv.DictReader(f))
    fig,axes=plt.subplots(2,4,figsize=(14,7),layout='constrained')
    for scale in (0,1):
        for j,tau in enumerate(cfg['noise']['correlation_s']):
            ax=axes[scale,j]
            for partition,col in [('primary','C0'),('alternative','C1')]:
                gains=sorted(float(r['gain']) for r in rows if int(r['scale'])==scale and float(r['correlation_s'])==tau and r['partition']==partition and not r['error'])
                ax.plot(gains,np.arange(1,len(gains)+1)/len(gains),label=partition,color=col)
                ax.axvline(real['133,65'][partition]['relative_predictive_gain'],color=col,ls='--')
            ax.axvline(0,color='k',lw=.5);ax.set(title=f'scale {scale}, tau={tau} s',xlabel='Predictive gain',ylabel='Empirical CDF')
    axes[0,0].legend(fontsize=8);fig.savefig(OUT/'BLOCK15E_GAIN_DISTRIBUTIONS.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(14,7),layout='constrained');keys=list(real)
    for p,col in [('primary','C0'),('alternative','C1')]:
        axes[0].plot([real[k][p]['relative_predictive_gain'] for k in keys],range(15),'o-',label=p,color=col)
        d=real['133,65'][p]
        for model,style in [('M0','--'),('M1','-')]:
            mid=[np.mean(t[f['held_out'] if p=='primary' else f['partition']['test']]) for f in d['folds']]
            axes[1].plot(mid,[f[model]['test_nmse'] for f in d['folds']],'o'+style,color=col,label=p+' '+model)
        axes[2].plot(mid,[f['M1']['s'] for f in d['folds']],'o-',color=col,label=p)
    axes[0].set(yticks=range(15),yticklabels=keys,xlabel='Aggregate gain',title='All 15 dependent bins');axes[0].invert_yaxis();axes[0].axvline(0,color='k',lw=.5)
    axes[1].set(xlabel='Held-out midpoint [s]',ylabel='NMSE',title='Fixed peak: prediction')
    axes[2].set(xlabel='Held-out midpoint [s]',ylabel='M1 s [rad/s]',title='Fixed peak: training fits')
    for ax in axes:ax.legend(fontsize=7)
    fig.savefig(OUT/'BLOCK15E_PARTITIONS.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    for i,m in enumerate(('M0','M1')):
        f=old['133,65']['full'][m];r=np.array(f['residual_real'])+1j*np.array(f['residual_imag']);d=cfg['residual_diagnostics']['133,65'][m]
        axes[i,0].plot(t,r.real,'.-',label='Re');axes[i,0].plot(t,r.imag,'.-',label='Im');axes[i,0].set(title=m+' residual',xlabel='TxTime [s]',ylabel='FFT coefficient units')
        axes[i,1].plot([x['mean_dt'] for x in d['acf']],[x['real'] for x in d['acf']],'o-',label='Re ACF');axes[i,1].plot([x['mean_dt'] for x in d['acf']],[x['imag'] for x in d['acf']],'o-',label='Im ACF');axes[i,1].axhline(0,color='k',lw=.5);axes[i,1].set(xlabel='Mean lag [s]',title='Centered residual ACF; descriptive')
        axes[i,2].plot(range(4),d['block8_rms'],'o-');axes[i,2].set(xlabel='Consecutive 8-look block',ylabel='Residual RMS',title='Possible scale nonstationarity')
        axes[i,0].legend();axes[i,1].legend()
    fig.savefig(OUT/'BLOCK15E_RESIDUALS.png',dpi=140);plt.close(fig)


if __name__=='__main__':main()

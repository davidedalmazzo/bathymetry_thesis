"""All fixed bins shown, including negative M1 evidence. No new fitting."""
import json
import numpy as np
from analyze_block15b_frequency import OUT


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cfg=json.loads((OUT/'BLOCK15D_CONFIG.json').read_text())
    data=json.loads((OUT/'BLOCK15D_RESULTS.json').read_text());keys=list(data);t=np.asarray(cfg['previous_config']['time_s'])
    for page in range(5):
        fig,axes=plt.subplots(3,5,figsize=(18,9),layout='constrained')
        for row,key in enumerate(keys[page*3:page*3+3]):
            d=data[key];z=np.array(d['z_real'])+1j*np.array(d['z_imag']);ax=axes[row]
            ax[0].plot(z.real,z.imag,'.-',label='observed',lw=.8)
            for model,col in [('M0','C1'),('M1','C2')]:
                f=d['full'][model];pred=np.array(f['predicted_real'])+1j*np.array(f['predicted_imag'])
                ax[0].plot(pred.real,pred.imag,'--',color=col,label=model,lw=1)
                ax[1].plot(t,abs(pred),'--',color=col,lw=1)
            ax[0].plot(0,0,'k+',ms=7);ax[0].plot(*d['full']['M1']['c'],'rx',label='M1 c')
            ax[0].set(xlabel='Re F',ylabel='Im F',title=f'Bin {key}');ax[0].set_aspect('equal',adjustable='datalim')
            ax[1].plot(t,abs(z),'.-',lw=.8);ax[1].set(xlabel='TxTime [s]',ylabel='|F|')
            a=d['historical_phase'];ax[2].plot(t,a['unwrapped'],'.-',label='phase');ax[2].plot(t,a['fitted'],'--',label='A fit')
            ax[2].set(xlabel='TxTime [s]',ylabel='Phase [rad]')
            ax[3].plot(t,a['residual'],'.-');ax[3].axhline(0,color='k',lw=.6);ax[3].set(xlabel='TxTime [s]',ylabel='A residual [rad]')
            for lag,f in d['historical_lags'].items():
                x=np.mean(f['delta_t']);ax[4].plot(x,f['s_phi'],'o',color='C0',mfc='C0' if f['valid'] else 'none')
                for alt in f['minima'][1:]:
                    if alt['cost']<=f['cost']+.01:ax[4].plot(x,alt['s_phi'],'x',color='0.6')
            ax[4].axhline(a['s_phi'],color='C1',lw=1);ax[4].set(xlabel='Actual mean lag [s]',ylabel='s_phi [rad/s]',title='Open/x: ambiguous or invalid')
        axes[0,0].legend(fontsize=7);axes[0,2].legend(fontsize=7)
        fig.savefig(OUT/f'BLOCK15D_TRAJECTORIES_{page+1}.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(4,4,figsize=(13,11),layout='constrained')
    for ax,key in zip(axes.flat,keys):
        d=data[key]
        for model,col in [('M0','C1'),('M1','C2')]:
            fit=d['full'][model];ax.plot(fit['profile_grid'],fit['profile_cost'],color=col,label=model,lw=1)
            ax.plot(fit['s'],fit['normalized_cost'],'o',color=col,ms=4)
        ax.set(title=key,xlabel='s [rad/s]',ylabel='SSE / energy')
    axes.flat[-1].axis('off');axes.flat[0].legend()
    fig.savefig(OUT/'BLOCK15D_COST_PROFILES.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,7),layout='constrained')
    gains=np.array([[f['relative_SSE_gain'] for f in data[k]['folds']] for k in keys])
    limit=max(1.,np.max(abs(gains)));im=axes[0].imshow(gains,aspect='auto',cmap='coolwarm',vmin=-limit,vmax=limit)
    axes[0].set(yticks=range(15),yticklabels=keys,xticks=range(4),xticklabels=['edge 0','inner 1','inner 2','edge 3'],title='Held-out SSE improvement',xlabel='Fold')
    for i in range(15):
        for j in range(4):axes[0].text(j,i,f'{gains[i,j]:.2f}',ha='center',va='center',fontsize=7)
    fig.colorbar(im,ax=axes[0],label='1-SSE M1/SSE M0')
    g=[data[k]['relative_predictive_gain'] for k in keys]
    axes[1].barh(range(15),g,color=['C2' if x>0 else 'C3' for x in g]);axes[1].axvline(0,color='k',lw=.8)
    axes[1].set(yticks=range(15),yticklabels=keys,xlabel='Aggregate held-out gain',title='All fixed bins');axes[1].invert_yaxis()
    for i,k in enumerate(keys):
        d=data[k];s=[d['full']['M1']['s']]+[f['M1']['s'] for f in d['folds']]
        axes[2].plot(s,[i]*5,'o-',ms=3)
    axes[2].set(yticks=range(15),yticklabels=keys,xlabel='M1 signed s [rad/s]',title='Full + four training subsets');axes[2].invert_yaxis()
    fig.savefig(OUT/'BLOCK15D_PREDICTIVE.png',dpi=150);plt.close(fig)
    # Full profiles above; zoom on fixed peak for interpretable basin shape.
    peak=data[keys[0]];fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for name,col in [('M0','C1'),('M1','C2')]:
        fit=peak['full'][name];axes[0].plot(fit['profile_grid'],fit['profile_cost'],label=name,color=col)
        axes[0].axvline(fit['s'],color=col,ls=':')
        axes[1].plot(range(4),[f[name]['test_nmse'] for f in peak['folds']],'o-',label=name,color=col)
    axes[0].set(xlim=(.15,.7),ylim=(0,.65),xlabel='s [rad/s]',ylabel='Training SSE / energy',title=f'Fixed peak {keys[0]}')
    axes[1].set(xticks=range(4),xticklabels=['edge 0','inner 1','inner 2','edge 3'],ylabel='Held-out NMSE',title='Prediction, no refit on held-out samples')
    for ax in axes:ax.legend()
    fig.savefig(OUT/'BLOCK15D_FIXED_PEAK.png',dpi=160);plt.close(fig)
    # Wrapped phase differences, without another unwrap or frequency fit.
    fig,axes=plt.subplots(4,4,figsize=(14,11),layout='constrained')
    for ax,key in zip(axes.flat,keys):
        d=data[key];z=np.array(d['z_real'])+1j*np.array(d['z_imag'])
        for lag in (1,2,4,8):
            phase=np.angle(z[lag:]*z[:-lag].conj())
            ax.plot((t[lag:]+t[:-lag])/2,phase,'.-',lw=.7,ms=3,label=f'lag {lag}')
        ax.set(title=key,xlabel='Pair midpoint TxTime [s]',ylabel='arg(Fsec conj(Fref)) [rad]',ylim=(-np.pi,np.pi))
    axes.flat[-1].axis('off');axes.flat[0].legend(fontsize=7)
    fig.savefig(OUT/'BLOCK15D_PHASE_DIFFERENCES.png',dpi=150);plt.close(fig)


if __name__=='__main__':main()

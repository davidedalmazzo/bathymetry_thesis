"""Block15E: stationary proper complex OU noise and purged blocked prediction."""
import numpy as np
from .static_offset_diagnostic import fit_profile, predict


def exponential_noise(t, sigma, correlation_s, rng):
    t=np.asarray(t,float)
    if t.ndim!=1 or len(t)<2 or not np.isfinite(t).all() or np.any(np.diff(t)<=0):
        raise ValueError('Strictly increasing finite times required')
    if not np.isfinite(sigma) or not np.isfinite(correlation_s) or sigma<0 or correlation_s<0:
        raise ValueError('Nonnegative finite noise parameters required')
    w=sigma/np.sqrt(2)*(rng.normal(size=len(t))+1j*rng.normal(size=len(t)))
    out=w.copy()
    if correlation_s>0:
        rho=np.exp(-np.diff(t)/correlation_s)
        for i in range(1,len(t)):
            out[i]=rho[i-1]*out[i-1]+np.sqrt(-np.expm1(-2*(t[i]-t[i-1])/correlation_s))*w[i]
    return out


def blocked_partition(n=32, width=4, guard=2):
    if n%width or width<1 or guard<0:raise ValueError('Invalid partition')
    result=[]
    for start in range(0,n,width):
        test=np.arange(start,start+width)
        excluded=np.arange(max(0,start-guard),min(n,start+width+guard))
        train=np.setdiff1d(np.arange(n),excluded)
        if len(train)<8:raise ValueError('Insufficient training support')
        result.append(dict(test=test.tolist(),train=train.tolist(),
                           guard=np.setdiff1d(excluded,test).tolist(),
                           kind='edge_extrapolation' if start in (0,n-width) else 'internal_interpolation'))
    return result


def fit_fold(z,t,config,part):
    z=np.asarray(z);t=np.asarray(t);train=np.asarray(part['train']);test=np.asarray(part['test'])
    if set(train)&set(test) or set(train)&set(part['guard']):raise ValueError('Training leakage')
    result=dict(partition=part)
    for m in ('M0','M1'):
        f=fit_profile(z[train],t[train],t0=config['t0'],offset=m=='M1',bounds=config['bounds'],
                      grid_size=config['grid_size'],cost_margin=config['profile_cost_margin'])
        pred=predict(f,t[test],config['t0'])
        f.update(test_sse=float(np.sum(abs(z[test]-pred)**2)),
                 test_nmse=float(np.sum(abs(z[test]-pred)**2)/np.sum(abs(z[test])**2)),
                 test_prediction_real=pred.real.tolist(),test_prediction_imag=pred.imag.tolist())
        result[m]=f
    result['relative_SSE_gain']=float(1-result['M1']['test_sse']/max(result['M0']['test_sse'],1e-30))
    return result


def alternative_compare(z,t,config,parts,full):
    folds=[fit_fold(z,t,config,p) for p in parts]
    fits=[full['M1']]+[f['M1'] for f in folds];rules=config['criteria']
    slopes=[f['s'] for f in fits];ratios=[f['offset_ratio'] for f in fits]
    span=float(np.ptp(slopes));cv=float(np.std(ratios)/max(np.mean(ratios),1e-12)) if all(r is not None for r in ratios) else float('inf')
    c=np.array([complex(*f['c']) for f in fits]);a=abs(complex(*full['M1']['a']))
    dispersion=float(np.sqrt(np.mean(abs(c-c[0])**2))/max(a,1e-30))
    flags=[]
    for name,condition in [
        ('ambiguous_or_flat_profile',any(f['ambiguous'] for f in fits)),
        ('boundary_solution',any(f['boundary'] for f in fits)),
        ('ill_conditioned',any(f['rank']<2 or f['condition']>rules['condition_max'] for f in fits)),
        ('broad_profile',max(f['profile_width'] for f in fits)>rules['profile_width_max']),
        ('slope_unstable',span>rules['slope_span_max']),('offset_ratio_unstable',cv>rules['ratio_cv_max']),
        ('complex_offset_unstable',dispersion>rules['offset_dispersion_max'])]:
        if condition:flags.append(name)
    sse={m:sum(f[m]['test_sse'] for f in folds) for m in ('M0','M1')}
    gain=float(1-sse['M1']/max(sse['M0'],1e-30));improved=sum(f['relative_SSE_gain']>0 for f in folds)
    repeated=gain>=rules['predictive_gain_min'] and improved>=6 and folds[0]['relative_SSE_gain']>0 and folds[-1]['relative_SSE_gain']>0
    return dict(full=full,folds=folds,relative_predictive_gain=gain,
                predictive_nmse={m:sse[m]/float(np.sum(abs(z)**2)) for m in sse},improved_folds=improved,
                slope_span=span,offset_ratio_cv=cv,complex_offset_dispersion=dispersion,stability_flags=flags,
                category='no_predictive_advantage' if gain<=0 else 'repeated_predictive_stable' if repeated and not flags else 'descriptive_or_unstable')

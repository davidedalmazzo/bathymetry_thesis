"""Variable-projection M0/M1 on original complex intensity coefficients.

No frequency correction. Cost profiles and blocked prediction are descriptive;
their thresholds are operational, not confidence intervals or physical truth.
"""
import numpy as np
from scipy.optimize import minimize_scalar


def linear_parameters(z,t,s,t0,offset):
    x=np.exp(1j*s*(np.asarray(t)-t0))
    X=np.column_stack((x,np.ones_like(x))) if offset else x[:,None]
    beta,_,rank,_=np.linalg.lstsq(X,np.asarray(z),rcond=None)
    pred=X@beta
    return beta,pred,int(rank),float(np.linalg.cond(X))


def fit_profile(z,t,t0,offset,bounds,grid_size=2001,cost_margin=.01):
    z=np.asarray(z,complex);t=np.asarray(t,float)
    if z.ndim!=1 or z.shape!=t.shape or len(z)<4 or not np.isfinite(z).all() or not np.isfinite(t).all():
        raise ValueError('Finite matching vectors with at least four samples required')
    energy=float(np.vdot(z,z).real)
    if energy<=0:raise ValueError('Zero energy: frequency undefined')
    grid=np.linspace(*bounds,grid_size)
    X=np.exp(1j*grid[:,None]*(t-t0))
    if offset:
        centered=X-X.mean(axis=1,keepdims=True);zz=z-z.mean()
        den=np.sum(abs(centered)**2,axis=1)
        reduction=np.zeros(len(grid));np.divide(abs(centered.conj()@zz)**2,den,out=reduction,where=den>1e-12)
        cost=np.maximum(0.,float(np.vdot(zz,zz).real)-reduction)/energy
    else:cost=np.maximum(0.,energy-abs(X.conj()@z)**2/len(z))/energy
    def objective(s):
        _,p,_,_=linear_parameters(z,t,s,t0,offset)
        return float(np.sum(abs(z-p)**2)/energy)
    flat=bool(np.ptp(cost)<=cost_margin)
    indices=np.where((cost[1:-1]<=cost[:-2])&(cost[1:-1]<=cost[2:]))[0]+1
    minima=[]
    if flat:
        i=int(np.argmin(cost));minima=[dict(s=float(grid[i]),cost=objective(grid[i]),boundary=i in (0,len(grid)-1))]
    else:
        for i in indices:
            opt=minimize_scalar(objective,bounds=(grid[i-1],grid[i+1]),method='bounded',options={'xatol':1e-11})
            minima.append(dict(s=float(opt.x),cost=float(opt.fun),boundary=False))
        for i in (0,len(grid)-1):
            if cost[i]<=cost[1 if i==0 else -2]:minima.append(dict(s=float(grid[i]),cost=objective(grid[i]),boundary=True))
    minima.sort(key=lambda m:m['cost']);best=minima[0]
    beta,pred,rank,condition=linear_parameters(z,t,best['s'],t0,offset)
    a=beta[0];c=beta[1] if offset else 0j
    i=int(np.argmin(abs(grid-best['s'])));left=right=i
    while left>0 and cost[left-1]<=best['cost']+cost_margin:left-=1
    while right<len(grid)-1 and cost[right+1]<=best['cost']+cost_margin:right+=1
    ambiguous=flat or any(m['cost']<=best['cost']+cost_margin for m in minima[1:])
    return dict(s=best['s'],a=[float(a.real),float(a.imag)],c=[float(c.real),float(c.imag)],
                offset_ratio=float(abs(c)/abs(a)) if abs(a)>1e-12*np.sqrt(energy/len(z)) else None,
                sse=float(np.sum(abs(z-pred)**2)),normalized_cost=best['cost'],
                residual_real=(z-pred).real.tolist(),residual_imag=(z-pred).imag.tolist(),
                predicted_real=pred.real.tolist(),predicted_imag=pred.imag.tolist(),
                minima=minima,flat=flat,ambiguous=bool(ambiguous),boundary=best['boundary'],
                rank=rank,condition=condition,profile_width=float(grid[right]-grid[left]),
                profile_interval=[float(grid[left]),float(grid[right])],profile_grid=grid.tolist(),profile_cost=cost.tolist())


def predict(fit,t,t0):
    a=complex(*fit['a']);c=complex(*fit['c'])
    return a*np.exp(1j*fit['s']*(np.asarray(t)-t0))+c


def compare_models(z,t,config):
    z=np.asarray(z,complex);t=np.asarray(t);t0=config['t0']
    kw=dict(t0=t0,bounds=config['bounds'],grid_size=config['grid_size'],cost_margin=config['profile_cost_margin'])
    full={m:fit_profile(z,t,offset=m=='M1',**kw) for m in ('M0','M1')}
    folds=[]
    for index,test in enumerate(config['folds']):
        test=np.asarray(test,int);train=np.setdiff1d(np.arange(len(z)),test)
        record=dict(index=index,kind='edge_extrapolation' if index in (0,3) else 'internal_interpolation',held_out=test.tolist())
        for m in ('M0','M1'):
            fit=fit_profile(z[train],t[train],offset=m=='M1',**kw)
            pred=predict(fit,t[test],t0);err=z[test]-pred
            fit.update(test_sse=float(np.sum(abs(err)**2)),test_nmse=float(np.sum(abs(err)**2)/np.sum(abs(z[test])**2)),
                       test_prediction_real=pred.real.tolist(),test_prediction_imag=pred.imag.tolist())
            record[m]=fit
        record['relative_SSE_gain']=float(1-record['M1']['test_sse']/max(record['M0']['test_sse'],1e-30))
        folds.append(record)
    errors={m:sum(f[m]['test_sse'] for f in folds) for m in ('M0','M1')}
    gain=float(1-errors['M1']/max(errors['M0'],1e-30))
    fits=[full['M1']]+[f['M1'] for f in folds]
    slope_span=float(np.ptp([f['s'] for f in fits]));ratios=[f['offset_ratio'] for f in fits]
    ratio_cv=float(np.std(ratios)/max(np.mean(ratios),1e-12)) if all(x is not None for x in ratios) else float('inf')
    cs=np.array([complex(*f['c']) for f in fits]);a=abs(complex(*full['M1']['a']))
    offset_dispersion=float(np.sqrt(np.mean(abs(cs-cs[0])**2))/max(a,1e-30))
    rules=config['criteria'];flags=[]
    if any(f['ambiguous'] for f in fits):flags.append('ambiguous_or_flat_profile')
    if any(f['boundary'] for f in fits):flags.append('boundary_solution')
    if any(f['rank']<2 or f['condition']>rules['condition_max'] for f in fits):flags.append('ill_conditioned')
    if max(f['profile_width'] for f in fits)>rules['profile_width_max']:flags.append('broad_profile')
    if slope_span>rules['slope_span_max']:flags.append('slope_unstable')
    if ratio_cv>rules['ratio_cv_max']:flags.append('offset_ratio_unstable')
    if offset_dispersion>rules['offset_dispersion_max']:flags.append('complex_offset_unstable')
    improved=sum(f['relative_SSE_gain']>0 for f in folds)
    repeated=gain>=rules['predictive_gain_min'] and improved>=3 and folds[0]['relative_SSE_gain']>0 and folds[-1]['relative_SSE_gain']>0
    category=('no_predictive_advantage' if gain<=0 else
              'repeated_predictive_stable' if repeated and not flags else 'descriptive_or_unstable')
    return dict(full=full,folds=folds,relative_predictive_gain=gain,
                predictive_nmse={m:errors[m]/float(np.sum(abs(z)**2)) for m in errors},
                improved_folds=improved,slope_span=slope_span,offset_ratio_cv=ratio_cv,
                complex_offset_dispersion=offset_dispersion,stability_flags=flags,category=category,
                training_relative_gain=float(1-full['M1']['sse']/max(full['M0']['sse'],1e-30)))

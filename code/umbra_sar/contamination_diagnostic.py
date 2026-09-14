"""Intensity-Fourier coefficient mixtures, NOT raw SAR or full speckle.

Amplitude A=1; B/A is a coefficient amplitude ratio. Circular complex noise
has E|epsilon|^2=sigma^2, real/imag variances sigma^2/2. No correction of data.
"""
from __future__ import annotations
import numpy as np
from .frequency_comparison import reference_fit, estimate_circular, local_msc


def components(time, s_true, ratio, s_cont=0., relative_phase=0., phi_a=0.):
    t=np.asarray(time,float)
    moving=np.exp(1j*(s_true*t+phi_a))
    contaminant=ratio*np.exp(1j*(s_cont*t+phi_a+relative_phase))
    return moving,contaminant


def instantaneous_slope(time,s_true,ratio,s_cont=0.,relative_phase=0.,phi_a=0.):
    a,b=components(time,s_true,ratio,s_cont,relative_phase,phi_a)
    z=a+b;derivative=1j*(s_true*a+s_cont*b)
    out=np.full(z.shape,np.nan)
    np.divide(np.imag(z.conj()*derivative),abs(z)**2,out=out,where=abs(z)>1e-12)
    return out


def complex_noise(rng,shape,sigma):
    return sigma/np.sqrt(2)*(rng.standard_normal(shape)+1j*rng.standard_normal(shape))


def patch_profiles():
    u,v=np.mgrid[-1:2,-1:2]
    moving=np.exp(-(u*u+v*v)/4)*np.exp(1j*(.3*u-.2*v))
    different=moving*(1+.4*u+.2*v)*np.exp(.7j*(u-v))
    return moving,dict(proportional=moving.copy(),different=different)


def patch_coherences(moving,contaminant,noise):
    """Explicit nine coefficients, independent additive noises per bin/time.

    Center profiles equal one, so both layouts share the same central series.
    Noise arrays are also paired across layouts, not independent replicates.
    Only first/last look MSC is measured, matching the Block15B common gate.
    """
    h,profiles=patch_profiles();result={}
    for label,q in profiles.items():
        patch=moving[:,None,None]*h+contaminant[:,None,None]*q+noise
        msc,valid=local_msc(patch[0],patch[-1])
        result[label]=dict(endpoint_MSC=float(msc[1,1]),valid=bool(valid[1,1]))
    return result


def fit_three(z,time,config):
    """Direct calls to frozen B15 functions; identical method-specific gates."""
    bounds=config['search']['bounds'];rules=config['validity']
    a=reference_fit(z,time,16,max_step=rules['A_max_step_rad'])
    a_reasons=[]
    if not a['unwrap_continuity_valid']:a_reasons.append('large_wrapped_step')
    if a['rmse']>rules['A_max_rmse_rad']:a_reasons.append('high_unwrapped_RMSE')
    if not bounds[0]<a['s_phi']<bounds[1]:a_reasons.append('outside_search')
    a.update(valid=not a_reasons,exclusions=';'.join(a_reasons))
    options=dict(grid_size=config['search']['grid_size'],
                 alternative_cost_margin=config['search']['alternative_cost_margin'],
                 max_rms=rules['circular_max_rms_rad'])
    fits=dict(A=a)
    for name,lags in [('B',(1,)),('C',(1,2,4,8))]:
        fit=estimate_circular(z,time,lags,bounds,**options)
        why=[]
        if fit['circular_rms']>rules['circular_max_rms_rad']:why.append('high_circular_RMS')
        if fit['ambiguous']:why.append('alternative_minimum')
        if fit['boundary']:why.append('search_boundary')
        fit['exclusions']=';'.join(why);fits[name]=fit
    return fits


def grid_cases():
    cases=[]
    for slope in (.3,.5,.7):
        # B=0 duplicates in relative phase and contaminant speed are omitted.
        cases.append(dict(case_id=len(cases),s_true=slope,ratio=0.,s_cont=0.,
                          cont_fraction=0.,phase_index=0,relative_phase=0.))
        for ratio in (.25,.5,1.,2.):
            for fraction in (0.,-.2,.2):
                for phase in range(8):
                    cases.append(dict(case_id=len(cases),s_true=slope,ratio=ratio,
                        s_cont=fraction*slope,cont_fraction=fraction,phase_index=phase,
                        relative_phase=float(2*np.pi*phase/8)))
    return cases

"""Deterministic helpers for the frozen Block15K SICD/BP comparison."""
from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np
from scipy.signal.windows import tukey

CROSS_CONVENTION = "F_secondary * conj(F_reference)"


def temporal_intersection(a, b):
    lo, hi = max(float(a[0]), float(b[0])), min(float(a[1]), float(b[1]))
    if not lo < hi: raise ValueError("time supports do not intersect")
    return lo, hi


def doppler_to_slow_time(k_query, k_samples, time_samples):
    """Invert a strictly monotone sampled Doppler coordinate without sign guessing."""
    k=np.asarray(k_samples,float); t=np.asarray(time_samples,float); q=np.asarray(k_query,float)
    if k.shape!=t.shape or k.ndim!=1 or len(k)<2 or np.any(np.diff(t)<=0): raise ValueError("ordered PVP samples required")
    d=np.diff(k)
    if not (np.all(d>0) or np.all(d<0)): raise ValueError("Doppler mapping must be monotone on support")
    if d[0]<0: k,t=k[::-1],t[::-1]
    if np.any(q<k[0]) or np.any(q>k[-1]): raise ValueError("extrapolation is forbidden")
    return np.interp(q,k,t)


def normalized_kernel(time, support, alpha=.25):
    t=np.asarray(time,float); lo,hi=map(float,support)
    if not lo < hi or t.ndim!=1: raise ValueError("invalid kernel grid/support")
    u=(t-lo)/(hi-lo); w=np.zeros_like(t); inside=(u>=0)&(u<=1)
    if np.any(inside):
        # Evaluate the continuous symmetric Tukey shape.
        x=u[inside]; edge=alpha/2; v=np.ones_like(x)
        left=x<edge; right=x>1-edge
        v[left]=.5*(1+np.cos(np.pi*(2*x[left]/alpha-1)))
        v[right]=.5*(1+np.cos(np.pi*(2*x[right]/alpha-2/alpha+1)))
        w[inside]=v
    area=np.trapezoid(w,t)
    if area<=0: raise ValueError("zero kernel")
    return w/area


def kernel_metrics(time, first, second):
    t=np.asarray(time,float); a=np.asarray(first,float); b=np.asarray(second,float)
    norm=lambda x: x/np.trapezoid(x,t)
    a,b=norm(a),norm(b)
    center=lambda x: float(np.trapezoid(t*x,t))
    rms=lambda x: float(np.sqrt(np.trapezoid((t-center(x))**2*x,t)))
    cosine=float(np.trapezoid(a*b,t)/np.sqrt(np.trapezoid(a*a,t)*np.trapezoid(b*b,t)))
    return {'center_first_s':center(a),'center_second_s':center(b),'center_abs_error_s':abs(center(a)-center(b)),
            'rms_first_s':rms(a),'rms_second_s':rms(b),'rms_abs_error_s':abs(rms(a)-rms(b)),
            'l1_distance':float(np.trapezoid(abs(a-b),t)),'cosine_similarity':cosine}


def project_kernel_to_bins(grid_time, target, edges, pulse_counts):
    """Pulse-count-correct coefficients for averaged disjoint BP sublooks."""
    t=np.asarray(grid_time,float); target=np.asarray(target,float); e=np.asarray(edges,float); n=np.asarray(pulse_counts,float)
    if len(e)!=len(n)+1: raise ValueError("one more edge than bins required")
    mean=[]
    for lo,hi in zip(e[:-1],e[1:]):
        mask=(t>=lo)&(t<hi); mean.append(float(np.mean(target[mask])) if np.any(mask) else 0.)
    coeff=n*np.asarray(mean); total=coeff.sum()
    if total<=0: raise ValueError("target does not overlap BP bins")
    coeff/=total
    approx=np.zeros_like(t)
    for value,lo,hi in zip(mean,e[:-1],e[1:]): approx[(t>=lo)&(t<hi)]=value
    return coeff, approx


def common_spectrum(intensity, alpha=.1):
    x=np.asarray(intensity,float); nr,nc=x.shape
    r=np.linspace(-1,1,nr); c=np.linspace(-1,1,nc); y=x-x.mean()
    y-=((r@y.sum(1))/(nc*(r@r))*r)[:,None]
    y-=((c@y.sum(0))/(nr*(c@c))*c)[None,:]
    w=np.outer(tukey(nr,alpha),tukey(nc,alpha)); w*=np.sqrt(w.size/np.sum(w*w))
    return np.fft.fftshift(np.fft.fft2(y*w))


def fixed_k_index(shape, spacing_m, target_parallel_rad_m, target_perpendicular_rad_m=0.):
    kp=2*np.pi*np.fft.fftshift(np.fft.fftfreq(shape[0],spacing_m)); kq=2*np.pi*np.fft.fftshift(np.fft.fftfreq(shape[1],spacing_m))
    ip=int(np.argmin(abs(kp-target_parallel_rad_m))); iq=int(np.argmin(abs(kq-target_perpendicular_rad_m)))
    err=float(np.hypot(kp[ip]-target_parallel_rad_m,kq[iq]-target_perpendicular_rad_m))
    return (ip,iq), (float(kp[ip]),float(kq[iq])), err


def fixed_patch_coefficients(spectra, index, radius=1):
    s=np.asarray(spectra,complex); i,j=index
    patch=s[:,i-radius:i+radius+1,j-radius:j+radius+1]
    if patch.shape[1:]!=(2*radius+1,2*radius+1): raise ValueError("fixed patch outside array")
    g=np.exp(-.5*(np.mgrid[-radius:radius+1,-radius:radius+1][0]**2+np.mgrid[-radius:radius+1,-radius:radius+1][1]**2))
    g/=g.sum(); return np.sum(patch*g[None],axis=(1,2))


def signed_phase_fit(coefficients, times):
    z=np.asarray(coefficients,complex); t=np.asarray(times,float)
    if z.shape!=t.shape or len(t)<3 or np.any(np.diff(t)<=0): raise ValueError("ordered matching series required")
    phase=np.unwrap(np.angle(z*np.conj(z[0]))); X=np.column_stack((np.ones(len(t)),t)); beta=np.linalg.lstsq(X,phase,rcond=None)[0]
    fitted=X@beta; residual=phase-fitted; dof=len(t)-2; sse=float(residual@residual); cov=(sse/dof)*np.linalg.inv(X.T@X)
    total=float(np.sum((phase-phase.mean())**2)); steps=np.angle(z[1:]*np.conj(z[:-1]))
    return {'slope_rad_s':float(beta[1]),'intercept_rad':float(beta[0]),'slope_se_rad_s':float(np.sqrt(cov[1,1])),
            'r_squared':float(1-sse/total if total>0 else 1),'residual_rmse_rad':float(np.sqrt(np.mean(residual**2))),
            'residual_rad':residual.tolist(),'phase_rad':phase.tolist(),'max_adjacent_phase_rad':float(np.max(abs(steps))),
            'cycles_observed':float(abs(beta[1])*(t[-1]-t[0])/(2*np.pi)),'period_s':float(2*np.pi/abs(beta[1]))}


def patch_msc(spectra, radius=1):
    s=np.asarray(spectra,complex); out=[]
    for a,b in zip(s[:-1],s[1:]):
        cross=np.sum(b*np.conj(a)); den=np.sum(abs(a)**2)*np.sum(abs(b)**2)
        out.append(float(abs(cross)**2/den) if den>0 else np.nan)
    return out


def conjugate_index(index, shape):
    return tuple((2*(n//2)-i) % n for i,n in zip(index,shape))


def classify_gates(metrics, thresholds):
    l1=bool(metrics['cycles']>=thresholds['level1_min_cycles'] and metrics['r2']>=thresholds['level1_min_r2'] and
            metrics['max_step']<thresholds['level1_max_adjacent_phase_rad'] and metrics['msc']>=thresholds['level1_min_patch_msc'] and metrics['sign_ok'])
    l2=bool(l1 and metrics['separation_delta_eff']>=thresholds['level2_min_separation_delta_eff'] and metrics['formation_stable'] and metrics['persistent_resolved'] and metrics['external_compatible'])
    l3=bool(l2 and metrics['independent_radial_elements']>=thresholds['level3_min_independent_radial_elements'] and metrics['omega_k_resolved'] and metrics['current_constrained'])
    return {'level1':l1,'level2':l2,'level3':l3,'mandatory_abstention':not l3}


def verify_hashes(root, expected):
    bad=[]
    for rel,want in expected.items():
        got=hashlib.sha256((Path(root)/rel).read_bytes()).hexdigest()
        if got!=want: bad.append({'path':rel,'expected':want,'actual':got})
    return bad

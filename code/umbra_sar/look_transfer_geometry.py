"""Geometry and deliberately limited linear transfer diagnostic for Block15F.

This is an intensity-coefficient transfer model, not a raw SAR phase-history
model or an ocean-wave inversion.  Its velocity-bunching term is the first
order density/Jacobian term only; it must not be added to another shift MTF.
"""
from __future__ import annotations
import numpy as np


def unit(x):
    x=np.asarray(x,dtype=float); n=np.linalg.norm(x,axis=-1,keepdims=True)
    if np.any(n<=0):raise ValueError('zero vector')
    return x/n


def signed_angle(a,b,normal):
    """Signed angle a->b about normal, rad."""
    a=unit(a);b=unit(b);normal=unit(normal)
    return np.arctan2(np.sum(np.cross(a,b)*normal,axis=-1),np.sum(a*b,axis=-1))


def finite_depth_omega(k,depth,g=9.80665):
    return np.sqrt(g*k*np.tanh(k*depth))


def transfer_terms(*, k_vector, los_horizontal, flight_horizontal, incidence_rad,
                   range_over_speed_s, omega_rad_s, depth_m, tilt_scale=1.0):
    """Return T_t and T_vb per metre surface elevation.

    eta=Re{A exp(i(k.x-omega t))}; LOS velocity has phasor
    U/eta=sin(i) omega coth(kh)(khat.los_h)-i cos(i)omega.
    For y'=y+(R/V)u_LOS, conservative density gives -beta d u/dy.
    """
    k=np.asarray(k_vector,float); kmag=float(np.linalg.norm(k))
    if kmag<=0 or depth_m<=0 or omega_rad_s<=0 or range_over_speed_s<=0:raise ValueError('positive k, depth, omega, R/V required')
    lh=unit(los_horizontal).reshape(3); fh=unit(flight_horizontal).reshape(3)
    khat=k/kmag; k_range=float(k@lh); k_flight=float(k@fh)
    coth=1/np.tanh(kmag*depth_m)
    velocity_per_eta=(np.sin(incidence_rad)*omega_rad_s*coth*(k_range/kmag)
                      -1j*np.cos(incidence_rad)*omega_rad_s)
    # First-order geometric brightness for RAR proxy (n.LOS/cos i)^2.
    tilt=-2j*float(tilt_scale)*np.tan(incidence_rad)*k_range
    vb=-1j*range_over_speed_s*k_flight*velocity_per_eta
    return dict(T_t=complex(tilt),T_vb=complex(vb),T_h=0j,H=complex(tilt+vb),
                k_magnitude=kmag,k_range=k_range,k_flight=k_flight,coth_kh=float(coth),
                U_los_per_eta=complex(velocity_per_eta))


def phase_slope(t, z):
    t=np.asarray(t,float);z=np.asarray(z,complex)
    if len(t)!=len(z) or len(t)<3 or np.any(abs(z)<1e-14):raise ValueError('finite nonzero series with >=3 samples required')
    slope,intercept=np.polyfit(t,np.unwrap(np.angle(z)),1)
    return float(slope),float(intercept)


def transfer_slope(t,H):
    return phase_slope(t,H)[0]

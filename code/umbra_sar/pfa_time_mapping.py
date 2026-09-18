"""PFA rectangle-to-slow-time geometry, with explicit 2-D radial coupling.

Spatial frequencies here are cycles/metre; ocean-wave vectors are rad/metre.
No SAR signal reading or vendor temporal-kernel exactness is implied.
"""
from __future__ import annotations
import numpy as np
C=299792458.0

def parse_pvp_bytes(payload,cphd):
    dtype=cphd.PVP.get_vector_dtype()
    if dtype.itemsize!=cphd.Data.NumBytesPVP:raise ValueError('PVP record layout mismatch')
    if len(payload)%dtype.itemsize:raise ValueError('truncated PVP records')
    records=np.frombuffer(payload,dtype=dtype)
    if len(records)!=cphd.Data.Channels[0].NumVectors:raise ValueError('PVP vector count mismatch')
    return records

def pfa_phase_vectors(tx_pos,rx_pos,point,fpn,ipn,row,col):
    """Two-way phase-gradient vector projected along FPN into image plane.

    Returns coefficient per Hz: k_image = f * coefficient [cycles/m].
    Sensor-to-target vectors ensure Row carrier is positive in this SICD.
    Projection preserves the phase on the declared focus plane, not a simple
    horizontal/ENU projection; this is the quasi-planar PFA approximation.
    """
    tx=np.asarray(point)-np.asarray(tx_pos);rx=np.asarray(point)-np.asarray(rx_pos)
    tx/=np.linalg.norm(tx,axis=-1)[...,None];rx/=np.linalg.norm(rx,axis=-1)[...,None]
    v=(tx+rx)/C;fpn=np.asarray(fpn);ipn=np.asarray(ipn)
    denom=float(fpn@ipn)
    if abs(denom)<1e-6:raise ValueError('singular focus-to-image projection')
    projected=v-(v@ipn)[...,None]*fpn/denom
    return np.column_stack([projected@row,projected@col])

def scatter_time(records,point):
    tx=records['TxTime']+np.linalg.norm(records['TxPos']-point,axis=1)/C
    rx=records['RcvTime']-np.linalg.norm(records['RcvPos']-point,axis=1)/C
    return .5*(tx+rx),tx-rx

def invert_monotone(x,t,q):
    x=np.asarray(x);t=np.asarray(t);d=np.diff(x)
    if np.all(d<0):x=x[::-1];t=t[::-1]
    elif not np.all(d>0):raise ValueError('nonmonotone PFA angle')
    q=np.asarray(q)
    if np.any(q<x[0]) or np.any(q>x[-1]):raise ValueError('band outside geometric support')
    return np.interp(q,x,t)

def band_kernel(theta,time,krow,low,high,*,samples=513):
    # Uniform rectangular output-k weight, NOT unknown original pulse weights.
    k=np.linspace(low,high,samples);tt=invert_monotone(theta,time,np.arctan2(k,krow))
    return {'time_start_s':float(min(tt[0],tt[-1])),'time_stop_s':float(max(tt[0],tt[-1])),
        'centre_uniform_output_k_s':float(np.trapezoid(tt,k)/(high-low)),
        'centre_uniform_time_s':float((tt[0]+tt[-1])/2),
        'support_duration_s':float(abs(tt[-1]-tt[0])),'sampled_k_col':k,'sampled_times_s':tt}

def image_to_ground_wavevector(k_image_rad_per_m,jacobian_ground_m_per_image_m):
    return np.linalg.solve(np.asarray(jacobian_ground_m_per_image_m).T,np.asarray(k_image_rad_per_m))

def geometry_jacobian(sicd,pixel,hae,step=10):
    from shapely.geometry import Point
    from shapely.ops import transform
    from .geographic_preflight import local_projection
    p=np.asarray(pixel,float);g=sicd.project_image_to_ground_geo(p,projection_type='HAE',hae0=hae)
    fwd,_=local_projection(g[1],g[0]);cols=[]
    for axis,ss in [(0,sicd.Grid.Row.SS),(1,sicd.Grid.Col.SS)]:
        pp=np.tile(p,(2,1));pp[0,axis]-=step;pp[1,axis]+=step
        ll=sicd.project_image_to_ground_geo(pp,projection_type='HAE',hae0=hae)
        a=transform(fwd,Point(ll[0,1],ll[0,0]));b=transform(fwd,Point(ll[1,1],ll[1,0]))
        cols.append(np.array([b.x-a.x,b.y-a.y])/(2*step*ss))
    return np.column_stack(cols)

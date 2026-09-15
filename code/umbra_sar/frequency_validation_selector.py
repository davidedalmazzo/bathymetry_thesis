"""Pure, deterministic primitives for the Block21 frequency-validation selector."""
from __future__ import annotations

import math
from typing import Iterable, Mapping

import numpy as np


LABELS = (
    "MEASURED_PRODUCT_CHECK", "CONDITIONAL_REFERENCE_CHECK",
    "MODEL_EXPLORATORY", "EXCLUDED", "NOT_EVALUABLE",
)


def as_bool(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def temporal_scenarios(duration_s, look_durations=(1.5, 2.5, 4.0, 6.0), step_s=1.0,
                       period_s=None) -> list[dict]:
    """Describe all feasible look paths; duration/period are descriptors, not gates."""
    try: duration = float(duration_s)
    except (TypeError, ValueError): return []
    if not math.isfinite(duration) or duration <= 0 or step_s <= 0: return []
    out = []
    for look in look_durations:
        look = float(look)
        if look <= 0 or look > duration: continue
        centres = int(math.floor((duration-look)/step_s+1e-12))+1
        independent = int(math.floor(duration/look+1e-12))
        row = {"look_duration_s":look, "sliding_step_s":float(step_s),
               "sliding_center_count":centres,
               "sliding_center_span_s":max(0.0,(centres-1)*step_s),
               "nominal_nonoverlap_count":independent,
               "sliding_looks_statistically_independent":False,
               "overlap_fraction":max(0.0,1-step_s/look)}
        try:
            p=float(period_s)
            row["observable_cycles"] = duration/p if p > 0 else None
            row["phase_span_rad"] = 2*math.pi*row["sliding_center_span_s"]/p if p > 0 else None
        except (TypeError,ValueError):
            row["observable_cycles"]=row["phase_span_rad"]=None
        out.append(row)
    return out


def dominant_half_power_band(frequency_hz, density, alpha1_from_deg=None, r1=None,
                             valid=None) -> dict:
    """Find the contiguous half-power lobe and derive all metrics from that same band."""
    f=np.asarray(frequency_hz,float); e=np.asarray(density,float)
    if f.ndim != 1 or e.shape != f.shape or len(f)<2 or np.any(np.diff(f)<=0):
        raise ValueError("ordered, same-length one-dimensional frequency/density arrays required")
    ok=np.isfinite(f)&np.isfinite(e)&(f>0)&(e>=0)
    if valid is not None: ok &= np.asarray(valid,bool)
    if not np.any(ok): raise ValueError("no valid density bin")
    ip=int(np.argmax(np.where(ok,e,-np.inf))); threshold=.5*e[ip]
    lo=hi=ip
    while lo>0 and ok[lo-1] and e[lo-1]>=threshold: lo-=1
    while hi+1<len(e) and ok[hi+1] and e[hi+1]>=threshold: hi+=1
    edges=np.empty(len(f)+1); edges[1:-1]=(f[:-1]+f[1:])/2
    edges[0]=max(0.0,f[0]-(f[1]-f[0])/2); edges[-1]=f[-1]+(f[-1]-f[-2])/2
    widths=np.diff(edges); band=np.zeros(len(f),bool); band[lo:hi+1]=True; band &= ok
    weights=e*widths*band; total=float(weights.sum())
    result={"peak_bin":ip,"peak_frequency_hz":float(f[ip]),"peak_period_s":float(1/f[ip]),
            "band_low_hz":float(edges[lo]),"band_high_hz":float(edges[hi+1]),
            "band_bin_count":int(band.sum()),"band_energy_m2":total,
            "bandwidth_hz":float(edges[hi+1]-edges[lo]),
            "local_maxima_count":int(sum(ok[i-1:i+2].all() and e[i]>=e[i-1] and e[i]>e[i+1]
                                          for i in range(1,len(e)-1)))}
    if alpha1_from_deg is not None:
        a=np.asarray(alpha1_from_deg,float); dvalid=band&np.isfinite(a)
        if r1 is not None:
            rr=np.asarray(r1,float); dvalid &= np.isfinite(rr)&(rr>=0)&(rr<=1)
        else: rr=np.ones_like(a)
        w=weights*rr*dvalid
        if w.sum()>0:
            z=np.sum(w*np.exp(1j*np.deg2rad(a)))
            result["direction_from_deg"]=float(np.rad2deg(np.angle(z))%360)
            result["propagation_to_deg"]=float((result["direction_from_deg"]+180)%360)
            result["direction_resultant"] = float(abs(z)/w.sum())
        else:
            result.update(direction_from_deg=None, propagation_to_deg=None, direction_resultant=None)
    return result


def classify_candidate(*, fatal=False, geometry_known=True, internal_roi=False,
                       has_complex=False, measured_admissible=False,
                       station_query_possible=False, model_available=False) -> str:
    if fatal or (geometry_known and (not internal_roi or not has_complex)): return "EXCLUDED"
    if not geometry_known: return "NOT_EVALUABLE"
    if measured_admissible: return "MEASURED_PRODUCT_CHECK"
    if station_query_possible: return "CONDITIONAL_REFERENCE_CHECK"
    if model_available: return "MODEL_EXPLORATORY"
    return "NOT_EVALUABLE"


def pareto_front(rows: Iterable[Mapping], fields: tuple[str,...]) -> list[bool]:
    """Maximisation Pareto front; missing values are dominated."""
    rows=list(rows); values=[]
    for row in rows:
        values.append(tuple(float(row[x]) if row.get(x) not in (None,"") else -math.inf for x in fields))
    return [not any(all(b>=a for a,b in zip(v,other)) and any(b>a for a,b in zip(v,other))
                    for j,other in enumerate(values) if j!=i) for i,v in enumerate(values)]

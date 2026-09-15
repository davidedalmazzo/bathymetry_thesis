"""Budgeted NDBC per-bin retrieval and product-aware normalization (Block18)."""
from __future__ import annotations

import hashlib, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

import numpy as np

from .selector_consolidation import bin_widths


@dataclass
class HTTPBudget:
    max_transactions: int
    max_total_bytes: int
    max_response_bytes: int
    timeout_s: float
    max_retries: int
    chunk_bytes: int = 65536
    transactions: int = 0
    total_bytes: int = 0
    log: list[dict] = field(default_factory=list)

    def reserve_transaction(self):
        if self.transactions >= self.max_transactions:
            raise RuntimeError("http_transaction_budget_exhausted")
        self.transactions += 1

    def accept_chunk(self, response_bytes: int, chunk_bytes: int):
        if response_bytes + chunk_bytes > self.max_response_bytes:
            raise RuntimeError("http_response_byte_budget_exceeded")
        if self.total_bytes + chunk_bytes > self.max_total_bytes:
            raise RuntimeError("http_total_byte_budget_exceeded")
        self.total_bytes += chunk_bytes


class _CountingRedirect(HTTPRedirectHandler):
    def __init__(self, budget): self.budget = budget
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.budget.reserve_transaction()
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_limited(url: str, budget: HTTPBudget, *, purpose="", acquisition_key="") -> bytes:
    """Fetch bytes with transaction and streaming byte limits, logging every try."""
    last = None
    for retry in range(budget.max_retries + 1):
        started = datetime.now(timezone.utc).isoformat()
        response_bytes = 0; status = None; final_url = None
        try:
            budget.reserve_transaction()
            opener = build_opener(_CountingRedirect(budget))
            with opener.open(Request(url, headers={"User-Agent":"UmbraThesis-Block18/1.0"}), timeout=budget.timeout_s) as response:
                status = getattr(response, "status", 200); final_url = response.geturl()
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > budget.max_response_bytes:
                    raise RuntimeError("declared_response_too_large")
                chunks=[]
                while True:
                    chunk=response.read(budget.chunk_bytes)
                    if not chunk: break
                    budget.accept_chunk(response_bytes, len(chunk)); response_bytes += len(chunk); chunks.append(chunk)
            payload=b"".join(chunks)
            budget.log.append({"timestamp_utc":started,"acquisition_key":acquisition_key,"purpose":purpose,"url":url,"final_url":final_url,"retry":retry,"http_status":status,"bytes":response_bytes,"outcome":"recovered","error":"","sha256":hashlib.sha256(payload).hexdigest()})
            return payload
        except Exception as exc:
            last=exc
            outcome="not_found" if isinstance(exc,HTTPError) and exc.code==404 else ("network_error" if isinstance(exc,(HTTPError,URLError,TimeoutError)) else "budget_or_parse_error")
            budget.log.append({"timestamp_utc":started,"acquisition_key":acquisition_key,"purpose":purpose,"url":url,"final_url":final_url or "","retry":retry,"http_status":getattr(exc,"code",status) or "","bytes":response_bytes,"outcome":outcome,"error":repr(exc),"sha256":""})
            if outcome not in {"network_error"} or retry >= budget.max_retries: break
    raise RuntimeError(f"request_failed: {url}: {last!r}")


def parse_dds_dimensions(text: str) -> dict[str,int]:
    """Extract named OPeNDAP dimensions without assuming their sizes."""
    pairs=re.findall(r"\[\s*([A-Za-z_]\w*)\s*=\s*(\d+)\s*\]",text)
    out={}
    for name,size in pairs:
        if name in out and out[name] != int(size): raise ValueError(f"conflicting dimension {name}")
        out[name]=int(size)
    if "frequency" not in out or "time" not in out: raise ValueError("DDS lacks time/frequency dimensions")
    return out


def parse_ascii_vector(text: str, variable: str) -> np.ndarray:
    match=re.search(rf"(?m)^{re.escape(variable)}\[\d+\]\s*\n([^\n]+)",text)
    if not match: raise ValueError(f"vector {variable} absent")
    return np.asarray([float(x.strip()) for x in match.group(1).split(",")],float)


def parse_ascii_grid(text: str, variable: str) -> np.ndarray:
    match=re.search(rf"(?m)^{re.escape(variable)}\.{re.escape(variable)}[^\n]*\n(.*?)(?:\n\s*\n|\Z)",text,re.S)
    if not match: raise ValueError(f"grid {variable} absent")
    return np.asarray([float(line.rsplit(",",1)[-1].strip()) for line in match.group(1).splitlines() if line.strip()],float)


def variable_attributes(das: str, variable: str) -> dict[str,object]:
    match=re.search(rf"(?ms)^\s*{re.escape(variable)}\s*\{{(.*?)^\s*\}}",das)
    block=match.group(1) if match else ""
    attrs={}
    for typ,name,value in re.findall(r"(?m)^\s*(\w+)\s+(\w+)\s+([^;]+);",block):
        clean=value.strip().strip('"')
        try: attrs[name]=float(clean)
        except ValueError: attrs[name]=clean
    return attrs


def validity_mask(values, *, variable, attrs):
    x=np.asarray(values,float); valid=np.isfinite(x)
    for key in ("_FillValue","missing_value"):
        if key in attrs:
            valid &= ~np.isclose(x,float(attrs[key]))
    if variable=="spectral_wave_density": valid &= x>=0
    elif variable in {"mean_wave_dir","principal_wave_dir"}: valid &= (x>=0)&(x<=360)
    elif variable in {"wave_spectrum_r1","wave_spectrum_r2"}: valid &= (x>=0)&(x<=1)
    return valid


VARIABLES=("spectral_wave_density","mean_wave_dir","principal_wave_dir","wave_spectrum_r1","wave_spectrum_r2")


def nearest_time_index(epochs_s, target_epoch_s):
    epochs=np.asarray(epochs_s,float)
    if epochs.ndim!=1 or not epochs.size or not np.all(np.isfinite(epochs)) or np.any(np.diff(epochs)<0):
        raise ValueError("time coordinate must be finite, nonempty and ordered")
    index=int(np.argmin(np.abs(epochs-float(target_epoch_s))))
    return index,float(epochs[index])


def normalize_payload(text: str, das: str, *, observation_epoch_s: float, joint_band=(.04,.25)):
    f=parse_ascii_vector(text,"frequency")
    arrays={name:parse_ascii_grid(text,name) for name in VARIABLES}
    if any(v.shape != f.shape for v in arrays.values()): raise ValueError("inconsistent spectral dimensions")
    order=np.argsort(f); f=f[order]; arrays={k:v[order] for k,v in arrays.items()}
    if np.any(f<=0) or np.any(np.diff(f)<=0): raise ValueError("nonpositive or duplicate frequencies")
    attrs={name:variable_attributes(das,name) for name in VARIABLES}
    masks={name:validity_mask(arrays[name],variable=name,attrs=attrs[name]) for name in VARIABLES}
    joint=np.logical_and.reduce([masks[name] for name in VARIABLES])
    widths=bin_widths(f)  # explicitly reconstructed from documented centre coordinates
    density_valid=masks["spectral_wave_density"]
    band=(f>=joint_band[0])&(f<=joint_band[1])&density_valid
    denom=float(np.sum(arrays["spectral_wave_density"][band]*widths[band]))
    joint_energy=float(np.sum(arrays["spectral_wave_density"][band&joint]*widths[band&joint]))
    return {"frequency_hz":f,"band_width_hz":widths,"arrays":arrays,"attrs":attrs,"masks":masks,
            "joint_mask":joint,"observation_epoch_s":float(observation_epoch_s),
            "joint_band_energy_coverage":joint_energy/denom if denom>0 else 0.0,
            "band_width_source":"midpoint_edges_reconstructed_from_frequency_centres"}


def spectrum_metrics(normalized, *, long_max_hz=.1):
    f=normalized["frequency_hz"]; w=normalized["band_width_hz"]
    e=normalized["arrays"]["spectral_wave_density"]; valid=normalized["masks"]["spectral_wave_density"]
    m0=float(np.sum(e[valid]*w[valid])); peak_candidates=np.where(valid,e,-np.inf); ip=int(np.argmax(peak_candidates))
    long=valid&(f<=long_max_hz); long_m0=float(np.sum(e[long]*w[long]))
    out={"m0_m2":m0,"hm0_m":4*np.sqrt(max(m0,0)),"peak_frequency_hz":float(f[ip]),
         "peak_period_s":float(1/f[ip]),"peak_density_m2_hz":float(e[ip]),
         "long_energy_fraction_f_le_0p1":long_m0/m0 if m0>0 else None,
         "spectral_local_maxima_count":int(sum(valid[i-1:i+2].all() and e[i]>=e[i-1] and e[i]>e[i+1] and e[i]>=.25*e[ip] for i in range(1,len(e)-1)))}
    for name,label in (("mean_wave_dir","peak_alpha1_from_deg"),("principal_wave_dir","peak_alpha2_deg"),("wave_spectrum_r1","peak_r1"),("wave_spectrum_r2","peak_r2")):
        out[label]=float(normalized["arrays"][name][ip]) if normalized["masks"][name][ip] else None
    out["peak_propagation_to_deg"]=(out["peak_alpha1_from_deg"]+180)%360 if out["peak_alpha1_from_deg"] is not None else None
    return out

"""Independent NOAA bathymetry statistics and frozen Block-4 residual diagnostics."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.merge import merge


ROOT=Path(__file__).resolve().parents[1]
V=ROOT/'umbra/Vandenberg'; OUT=V/"results"/"analysis_block7"; B=V/"bathymetry"
BEARING=79.8357237; ORIGINAL=np.array([716210.6102416331,3827777.0937420740])
FROZEN_T=17.902230457045317; FROZEN_SLOPE=-0.3509722055168202


def unit(b):
    a=np.deg2rad(b);return np.array([np.sin(a),np.cos(a)])


def sample(z,tr,e,n):
    c=np.floor((e-tr.c)/tr.a).astype(int);r=np.floor((n-tr.f)/tr.e).astype(int)
    out=np.full(e.shape,np.nan,dtype=np.float32);g=(r>=0)&(r<z.shape[0])&(c>=0)&(c<z.shape[1]);out[g]=z[r[g],c[g]];return out


def roi_stats(z,tr,center,lp,lt,spacing=2.0):
    p=np.arange(-lp/2,lp/2+spacing/2,spacing);q=np.arange(-lt/2,lt/2+spacing/2,spacing);pp,qq=np.meshgrid(p,q)
    up=unit(BEARING);uq=unit(BEARING+90);en=center[:,None,None]+up[:,None,None]*pp+uq[:,None,None]*qq
    elev=sample(z,tr,en[0],en[1]);good=np.isfinite(elev);depth=-elev[good];design=np.column_stack((np.ones(good.sum()),pp[good]/1000,qq[good]/1000));coef=np.linalg.lstsq(design,depth,rcond=None)[0]
    return {"center_utm_e_n_m":center.tolist(),"L_parallel_m":lp,"L_perpendicular_m":lt,"sample_spacing_m":spacing,"valid_fraction":float(np.mean(good)),
        "elevation_NAVD88_percentiles_m":np.percentile(elev[good],[5,25,50,75,95]).tolist(),"depth_positive_down_NAVD88_percentiles_m":np.percentile(depth,[5,25,50,75,95]).tolist(),
        "depth_median_m":float(np.median(depth)),"depth_min_max_m":[float(np.min(depth)),float(np.max(depth))],
        "depth_plane_gradient_m_per_km_parallel_k":float(coef[1]),"depth_plane_gradient_m_per_km_perpendicular_k":float(coef[2]),
        "datum_warning":"Depth is -elevation relative to NAVD88, not chart depth relative to MLLW; no tidal conversion is applied."}, pp,qq,-elev


def residual_diagnostic():
    block=json.loads((V/"results"/"analysis_block4"/"BLOCK4_PHASE_METRICS_SAR_ONLY.json").read_text())
    times=np.asarray(block["time_axis"]["physical_slow_time_centers_s"],float)
    phase=block["results"]["nearshore"]["primary_fixed_patch_phase"]
    fit=phase["fit_direct_reference_phase"]
    if not math.isclose(fit["period_s"],FROZEN_T,abs_tol=1e-12) or not math.isclose(fit["slope_rad_per_s"],FROZEN_SLOPE,abs_tol=1e-14): raise RuntimeError("Frozen Block-4 result changed")
    residual=np.asarray(fit["residual_phase_rad"],float);centered=residual-np.mean(residual)
    ac=[]
    for lag in range(len(residual)):
        ac.append(float(np.dot(centered[:len(residual)-lag],centered[lag:])/np.dot(centered,centered)))
    periods=np.linspace(2.5,30,10000);best=None
    for period in periods:
        om=2*np.pi/period;X=np.column_stack((np.ones(times.size),np.cos(om*times),np.sin(om*times)));beta=np.linalg.lstsq(X,residual,rcond=None)[0];pred=X@beta;sse=float(np.sum((residual-pred)**2))
        if best is None or sse<best[0]:best=(sse,period,beta,pred)
    sse,period,beta,pred=best;amp=float(np.hypot(beta[1],beta[2]));base=float(np.sum(centered**2));n=len(residual)
    diag={"frozen_period_s":FROZEN_T,"frozen_slope_rad_per_s":FROZEN_SLOPE,"time_s":times.tolist(),"residual_rad":residual.tolist(),"autocorrelation_biased_lags_0_to_10":ac,
        "diagnostic_sinusoid":{"search_period_bounds_s":[2.5,30],"best_period_s":float(period),"amplitude_rad":amp,"offset_rad":float(beta[0]),"predicted_residual_rad":pred.tolist(),"residual_r_squared":float(1-sse/base),"delta_AIC_vs_constant":float(n*np.log(sse/base)+2*3),
        "warning":"Exploratory only: 11 correlated sliding looks, searched frequency, fewer than two robust independent cycles. This term is not used to alter/correct the frozen slope."}}
    return diag,times,residual,np.asarray(ac),pred


def main():
    OUT.mkdir(parents=True,exist_ok=True);support=json.loads((OUT/"BLOCK7_ROI_SUPPORT_PLAN.json").read_text());paths=sorted(B.glob("10SGD*.tif"));ds=[rasterio.open(p) for p in paths]
    crs=ds[0].crs.to_wkt();merged,tr=merge(ds,nodata=np.nan,dtype="float32");[d.close() for d in ds];z=merged[0]
    stats=[];anchored_stats=[];max_grid=None;max_lp=float(support["candidate_rois"][-1]["L_parallel_m"]);common=np.asarray(support["common_center_utm_e_n_m"])
    for roi in support["candidate_rois"]:
        rec,pp,qq,depth=roi_stats(z,tr,np.asarray(roi["center_utm_e_n_m"]),float(roi["L_parallel_m"]),float(roi["L_perpendicular_m"]));rec["roi"]=roi["name"];stats.append(rec)
        lp=float(roi["L_parallel_m"]); anchored_center=common+unit(BEARING)*(max_lp-lp)/2
        arec,*_=roi_stats(z,tr,anchored_center,lp,float(roi["L_perpendicular_m"]));arec["roi"]=f"nearshore_anchored_{int(lp):04d}x0650";anchored_stats.append(arec)
        if roi is support["candidate_rois"][-1]:max_grid=(pp,qq,depth)
    original,*_=roi_stats(z,tr,ORIGINAL,540,540);original["roi"]="original_center_540x540"
    bathy={"generated_utc":datetime.now(timezone.utc).isoformat(),"dataset":{"title":"2009-2011 CA Coastal California TopoBathy Merged Project DEM (Smoothed with Voids)","catalog_id":"NOAA InPort 49417","nominal_horizontal_resolution_m":1.0,
        "tile_crs_wkt":crs,"horizontal_reference":"Tile WKT: NAD83 / UTM zone 10N (EPSG:26910; product label includes NAD83(NSRS2007))","vertical_reference":"NAVD88 height, metres, EPSG:5703","tidal_datum":"None in delivered raster. Source bathymetry originally on several datums, including MLLW where applicable, was transformed with VDatum to NAVD88 during merging.",
        "publication":"2014-03; downloaded COG conversion dated 2024-07-23","source_age":"Statewide inputs vary. Topographic lidar 2009-2011; bathymetric lidar mainly 2009-2010; acoustic source dates vary and local per-cell acquisition age is not encoded in the GeoTIFF.",
        "product_identity_warning":"This 1 m OCM/NOAA California Topobathy product covers Point Arguello. The official California CUDEM 1/9 arc-second tile set begins near 36.75 N and does not cover this ROI; the DEM is therefore not relabelled as CUDEM."},
        "download_scope":{"tile_count":len(paths),"tiles":[p.name for p in paths],"mosaic_extent_utm_m":[tr.c,tr.c+tr.a*z.shape[1],tr.f+tr.e*z.shape[0],tr.f]},"roi_statistics":stats,"nearshore_anchored_roi_statistics":anchored_stats,"original_roi_statistics":original}
    (OUT/"BLOCK7_BATHYMETRY_STATS.json").write_text(json.dumps(bathy,indent=2),encoding="utf-8")
    diag,t,resid,ac,pred=residual_diagnostic();(OUT/"BLOCK7_FROZEN_RESIDUAL_DIAGNOSTIC.json").write_text(json.dumps(diag,indent=2),encoding="utf-8")
    pp,qq,depth=max_grid;fig,ax=plt.subplots(1,2,figsize=(13,5),constrained_layout=True);im=ax[0].imshow(depth,origin="lower",extent=[pp.min(),pp.max(),qq.min(),qq.max()],aspect="auto",cmap="viridis");ax[0].set(xlabel="parallel to k (m)",ylabel="perpendicular to k (m)",title="NOAA depth = -elevation NAVD88");fig.colorbar(im,ax=ax[0],label="m (positive down, NAVD88)")
    bins=np.linspace(pp.min(),pp.max(),37);cent=(bins[:-1]+bins[1:])/2;med=[np.nanmedian(depth[(pp>=a)&(pp<b)]) for a,b in zip(bins[:-1],bins[1:])];ax[1].plot(cent,med);ax[1].set(xlabel="parallel to k (m)",ylabel="median depth (m NAVD88)",title="Cross-shore depth profile");fig.savefig(OUT/"BLOCK7_BATHYMETRY_ROI.png",dpi=180);plt.close(fig)
    fig,ax=plt.subplots(2,2,figsize=(12,8),constrained_layout=True);phase=FROZEN_SLOPE*t+1.125810002490738+resid;ax[0,0].plot(t,phase,"o",label="unwrapped phase");ax[0,0].plot(t,FROZEN_SLOPE*t+1.125810002490738,label="frozen linear fit");ax[0,0].legend();ax[0,0].set(xlabel="PVP slow time (s)",ylabel="phase (rad)")
    ax[0,1].axhline(0,color="k",lw=.8);ax[0,1].plot(t,resid,"o-",label="residual");ax[0,1].plot(t,pred,"--",label="diagnostic sinusoid only");ax[0,1].legend();ax[0,1].set(xlabel="PVP slow time (s)",ylabel="residual (rad)")
    ax[1,0].stem(np.arange(len(ac)),ac);ax[1,0].axhline(1.96/np.sqrt(len(ac)),ls="--",color="gray");ax[1,0].axhline(-1.96/np.sqrt(len(ac)),ls="--",color="gray");ax[1,0].set(xlabel="lag (look steps)",ylabel="biased ACF")
    ax[1,1].axis("off");ax[1,1].text(0,.9,f"Frozen slope: {FROZEN_SLOPE:.9f} rad/s\nFrozen T_SAR: {FROZEN_T:.9f} s\nResidual RMSE: {np.sqrt(np.mean(resid**2)):.4f} rad\nDiagnostic sinusoid: {diag['diagnostic_sinusoid']['best_period_s']:.2f} s, amplitude {diag['diagnostic_sinusoid']['amplitude_rad']:.3f} rad\nNot used to correct slope",va="top")
    fig.suptitle("Block 7: frozen Block-4 residual diagnostic");fig.savefig(OUT/"BLOCK7_FROZEN_RESIDUAL_DIAGNOSTIC.png",dpi=180);plt.close(fig)
    print(json.dumps({"largest_bathy":stats[-1],"original_bathy":original,"residual":diag["diagnostic_sinusoid"]},indent=2))


if __name__=="__main__":main()

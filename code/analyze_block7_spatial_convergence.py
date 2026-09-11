"""Block-7 spatial-peak convergence and homogeneity on nested water ROIs."""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.signal.windows import tukey


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"
OUT = VANDENBERG / "results" / "analysis_block7"
FORMED = VANDENBERG / "results" / "block7_enlarged_nominal_sea_surface"
FROZEN_BEARING = 79.8357237
FROZEN_LAMBDA = 130.6028192373831
ORIGINAL_EN = np.array([716210.6102416331, 3827777.0937420740])
ORIGINAL_RC = np.array([10000.0,82800.0])
JAC = np.array([[-0.4428968144347891,-0.009929984691552818],[0.07684305729344487,-0.055618567392230034]])


def unit(bearing):
    a=np.deg2rad(bearing); return np.array([np.sin(a),np.cos(a)])


def detrend_window(data: np.ndarray, method: str) -> np.ndarray:
    y,x=np.mgrid[-1:1:complex(data.shape[0]),-1:1:complex(data.shape[1])]
    if method.startswith("mean"):
        residual=data-np.mean(data)
    else:
        columns=[np.ones(data.size),x.ravel(),y.ravel()]
        if method.startswith("quadratic"):
            columns += [(x*x).ravel(),(x*y).ravel(),(y*y).ravel()]
        design=np.column_stack(columns)
        beta=np.linalg.lstsq(design,data.ravel(),rcond=None)[0]
        residual=data-(design@beta).reshape(data.shape)
    if method=="mean_hann":
        wy=np.hanning(data.shape[0]); wx=np.hanning(data.shape[1])
    elif method=="plane_tukey10":
        wy=tukey(data.shape[0],.10); wx=tukey(data.shape[1],.10)
    elif method=="quadratic_tukey25":
        wy=tukey(data.shape[0],.25); wx=tukey(data.shape[1],.25)
    else: raise ValueError(method)
    return residual*wy[:,None]*wx[None,:]


def axial_diff(a,b): return abs(((a-b+90)%180)-90)


def measure(data: np.ndarray, dp: float, dq: float, method: str, pad_factor: int=2) -> dict:
    work=detrend_window(np.asarray(data,dtype=np.float64),method)
    ny,nx=work.shape; py=pad_factor*ny; px=pad_factor*nx
    power=np.abs(np.fft.fftshift(np.fft.fft2(work,s=(py,px))))**2
    power=gaussian_filter(power,0.65)
    fp=np.fft.fftshift(np.fft.fftfreq(px,dp)); fq=np.fft.fftshift(np.fft.fftfreq(py,dq))
    FP,FQ=np.meshgrid(fp,fq)
    up=unit(FROZEN_BEARING); uq=unit(FROZEN_BEARING+90)
    ke=FP*up[0]+FQ*uq[0]; kn=FP*up[1]+FQ*uq[1]
    km=np.hypot(ke,kn); bearing=np.degrees(np.arctan2(ke,kn))%180
    target=unit(FROZEN_BEARING)
    hemi=ke*target[0]+kn*target[1]>0
    mask=hemi&(km>=1/180)&(km<=1/70)&(np.abs(((bearing-FROZEN_BEARING+90)%180)-90)<=35)
    masked=np.where(mask,power,-np.inf); iy,ix=np.unravel_index(np.argmax(masked),masked.shape)
    kp=float(km[iy,ix]); angle=float(bearing[iy,ix]); peak=float(power[iy,ix])
    # Radial half-power width along the selected geographic ray.
    radial=np.linspace(1/220,1/55,1200)
    ae=math.sin(math.radians(angle)); an=math.cos(math.radians(angle))
    # Convert EN frequencies back to the p/q axes and interpolate by nearest bin.
    rp=radial*(ae*up[0]+an*up[1]); rq=radial*(ae*uq[0]+an*uq[1])
    jj=np.clip(np.rint((rp-fp[0])/(fp[1]-fp[0])).astype(int),0,px-1)
    ii=np.clip(np.rint((rq-fq[0])/(fq[1]-fq[0])).astype(int),0,py-1)
    line=power[ii,jj]; center=int(np.argmin(abs(radial-kp))); half=peak/2
    left=center
    while left>0 and line[left]>=half: left-=1
    right=center
    while right+1<line.size and line[right]>=half: right+=1
    fwhm=float(radial[right]-radial[left])
    return {"k_peak_cycles_per_m":kp,"wavelength_m":1/kp,"bearing_deg_mod_180":angle,
            "difference_from_frozen_bearing_deg":axial_diff(angle,FROZEN_BEARING),
            "radial_fwhm_cycles_per_m":fwhm,"radial_fwhm_fraction_of_k":fwhm/kp,
            "native_delta_f_parallel_cycles_per_m":1/(nx*dp),"zero_padding_factor":pad_factor,
            "peak_power_arbitrary":peak}


def resample_rotated(source: np.ndarray, center_en: np.ndarray, lp: int, lt: int, manifest: dict, dp=1.0,dq=1.0):
    p=(np.arange(lp)-(lp-1)/2)*dp; q=(np.arange(lt)-(lt-1)/2)*dq
    pp,qq=np.meshgrid(p,q); up=unit(FROZEN_BEARING); uq=unit(FROZEN_BEARING+90)
    east=center_en[0]+up[0]*pp+uq[0]*qq; north=center_en[1]+up[1]*pp+uq[1]*qq
    rc=ORIGINAL_RC[:,None]+np.linalg.solve(JAC,np.vstack(((east-ORIGINAL_EN[0]).ravel(),(north-ORIGINAL_EN[1]).ravel())))
    row0,_,col0,_=manifest["post_doppler_crop_sicd_bounds"]
    rf=manifest["row_block_factor"]; cf=manifest["col_block_factor"]
    coords=np.vstack(((rc[0]-row0)/rf-.5,(rc[1]-col0)/cf-.5))
    return map_coordinates(source,coords,order=1,mode="nearest").reshape(lt,lp).astype(np.float32)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    support=json.loads((OUT/"BLOCK7_ROI_SUPPORT_PLAN.json").read_text())
    manifest=json.loads((FORMED/"BLOCK7_ENLARGED_NOMINAL_MANIFEST.json").read_text())
    center=np.array(support["common_center_utm_e_n_m"]); max_lp=int(support["candidate_rois"][-1]["L_parallel_m"])
    sources=[np.load(FORMED/f"look{i}_intensity_bavg.npy",mmap_mode="r") for i in range(1,4)]
    rotated=[resample_rotated(src,center,max_lp,650,manifest) for src in sources]
    methods=["mean_hann","plane_tukey10","quadratic_tukey25"]
    rows=[]
    for roi in support["candidate_rois"]:
        lp=int(roi["L_parallel_m"]); x0=(max_lp-lp)//2; x1=x0+lp
        for look_index,array in enumerate(rotated,1):
            patch=array[:,x0:x1]
            for method in methods:
                record=measure(patch,1,1,method)
                record.update({"roi":roi["name"],"L_parallel_m":lp,"L_perpendicular_m":650,
                               "look_index":look_index,"method":method,"spatial_support":"nested_common_center"})
                rows.append(record)
            anchored=array[:,max_lp-lp:max_lp]
            for method in methods:
                record=measure(anchored,1,1,method)
                record.update({"roi":f"nearshore_anchored_{lp:04d}x0650","L_parallel_m":lp,"L_perpendicular_m":650,
                               "look_index":look_index,"method":method,"spatial_support":"nearshore_edge_anchored"})
                rows.append(record)
    # Re-measure a geometrically comparable original-centred rotated support.
    original_manifest={"post_doppler_crop_sicd_bounds":[9400,10600,78000,87600],"row_block_factor":2,"col_block_factor":20}
    originals=[]
    for look_index in range(1,4):
        complex_source=np.load(VANDENBERG/"results"/"sublooks_complex"/f"nearshore_look{look_index}_complex64.npy",mmap_mode="r")
        intensity=np.asarray(complex_source.real*complex_source.real+complex_source.imag*complex_source.imag,dtype=np.float32)
        coarse=intensity.reshape(600,2,480,20).mean(axis=(1,3),dtype=np.float32)
        originals.append(resample_rotated(coarse,ORIGINAL_EN,540,540,original_manifest))
    for look_index,array in enumerate(originals,1):
        for method in methods:
            record=measure(array,1,1,method); record.update({"roi":"original_center_rot_0540x0540","L_parallel_m":540,
                "L_perpendicular_m":540,"look_index":look_index,"method":method,"spatial_support":"original_center"}); rows.append(record)

    # Homogeneity: three cross-shore and three alongshore overlapping sub-ROIs.
    hom=[]
    mean_image=np.mean(np.stack(rotated),axis=0)
    for label,axis,centers,size in [
        ("cross_shore_along_k","p",[-max_lp/3,0,max_lp/3],(max_lp//3,650)),
        ("alongshore_perpendicular_k","q",[-162,0,162],(max_lp,325)),
    ]:
        for position in centers:
            lp,lt=size
            if axis=="p": x0=int(max_lp/2+position-lp/2); y0=int((650-lt)/2)
            else: x0=int((max_lp-lp)/2); y0=int(325+position-lt/2)
            patch=mean_image[y0:y0+lt,x0:x0+lp]
            rec=measure(patch,1,1,"plane_tukey10")
            rec.update({"transect":label,"coordinate_axis":axis,"center_coordinate_m":position,"L_parallel_m":lp,"L_perpendicular_m":lt})
            hom.append(rec)

    fieldnames=list(rows[0])
    with (OUT/"BLOCK7_SPATIAL_CONVERGENCE.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fieldnames);w.writeheader();w.writerows(rows)
    with (OUT/"BLOCK7_HOMOGENEITY.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(hom[0]));w.writeheader();w.writerows(hom)

    def summarize(selection):
        result=[]
        for lp in sorted(set(r["L_parallel_m"] for r in selection)):
            group=[r for r in selection if r["L_parallel_m"]==lp]
            lam=np.array([r["wavelength_m"] for r in group]);ang=np.array([r["bearing_deg_mod_180"] for r in group]);aang=FROZEN_BEARING+np.array([((a-FROZEN_BEARING+90)%180)-90 for a in ang])
            result.append({"L_parallel_m":lp,"L_perpendicular_m":650,"n_estimates":len(group),"lambda_median_m":float(np.median(lam)),"lambda_p10_p90_m":np.percentile(lam,[10,90]).tolist(),
                "theta_median_deg_mod_180":float(np.median(aang)%180),"theta_p10_p90_deg":np.percentile(aang,[10,90]).tolist(),"median_native_delta_f_cycles_per_m":float(np.median([r["native_delta_f_parallel_cycles_per_m"] for r in group])),"median_radial_fwhm_cycles_per_m":float(np.median([r["radial_fwhm_cycles_per_m"] for r in group]))})
        return result
    nested=[r for r in rows if r["spatial_support"]=="nested_common_center"];anchored=[r for r in rows if r["spatial_support"]=="nearshore_edge_anchored"]
    summary=summarize(nested);summary_anchored=summarize(anchored)
    last=summary_anchored[-3:]; last_lam=np.array([x["lambda_median_m"] for x in last]); last_ang=np.array([x["theta_median_deg_mod_180"] for x in last])
    cross=[r for r in hom if r["transect"]=="cross_shore_along_k"]; along=[r for r in hom if r["transect"]=="alongshore_perpendicular_k"]
    diagnostics={
        "generated_utc":datetime.now(timezone.utc).isoformat(),"frozen_original_lambda_m":FROZEN_LAMBDA,"frozen_bearing_deg":FROZEN_BEARING,
        "methods":methods,"zero_padding":"factor 2 interpolation only; native resolution is 1/L_parallel cycles/m",
        "summary_by_size":summary,"summary_nearshore_anchored_by_size":summary_anchored,
        "large_roi_convergence": {"last_three_lambda_range_m":float(np.ptp(last_lam)),"last_three_lambda_relative_range":float(np.ptp(last_lam)/np.mean(last_lam)),"last_three_theta_range_deg":float(np.ptp(last_ang))},
        "homogeneity": {"cross_shore_lambda_m":[r["wavelength_m"] for r in cross],"cross_shore_theta_deg":[r["bearing_deg_mod_180"] for r in cross],
            "alongshore_lambda_m":[r["wavelength_m"] for r in along],"alongshore_theta_deg":[r["bearing_deg_mod_180"] for r in along],
            "cross_shore_lambda_cv":float(np.std([r["wavelength_m"] for r in cross],ddof=1)/np.mean([r["wavelength_m"] for r in cross])),
            "alongshore_lambda_cv":float(np.std([r["wavelength_m"] for r in along],ddof=1)/np.mean([r["wavelength_m"] for r in along]))},
    }
    (OUT/"BLOCK7_SPATIAL_CONVERGENCE.json").write_text(json.dumps(diagnostics,indent=2),encoding="utf-8")

    fig,axes=plt.subplots(2,2,figsize=(12,9),constrained_layout=True)
    for seq,label,color in [(summary,"common-centred","tab:blue"),(summary_anchored,"nearshore-anchored","tab:red")]:
        x=np.array([s["L_parallel_m"] for s in seq]);lm=np.array([s["lambda_median_m"] for s in seq]);lo=np.array([s["lambda_p10_p90_m"] for s in seq]);axes[0,0].fill_between(x,lo[:,0],lo[:,1],alpha=.10,color=color);axes[0,0].plot(x,lm,"o-",label=label,color=color)
        th=np.array([s["theta_median_deg_mod_180"] for s in seq]);thi=np.array([s["theta_p10_p90_deg"] for s in seq]);axes[0,1].fill_between(x,thi[:,0],thi[:,1],alpha=.10,color=color);axes[0,1].plot(x,th,"o-",label=label,color=color)
    axes[0,0].axhline(130.6,color="k",ls="--",label="frozen 130.6 m");axes[0,0].axhspan(95,105,color="tab:orange",alpha=.15,label="95–105 m");axes[0,0].set(xlabel="L_parallel (m)",ylabel="peak wavelength (m)");axes[0,0].legend(fontsize=8)
    axes[0,1].axhline(FROZEN_BEARING,color="k",ls="--");axes[0,1].set(xlabel="L_parallel (m)",ylabel="wavevector bearing (deg mod 180)");axes[0,1].legend(fontsize=8)
    for group,color in [(cross,"tab:blue"),(along,"tab:green")]: axes[1,0].plot([r["center_coordinate_m"] for r in group],[r["wavelength_m"] for r in group],"o-",color=color,label=group[0]["transect"])
    axes[1,0].set(xlabel="sub-ROI center coordinate (m)",ylabel="peak wavelength (m)");axes[1,0].legend(fontsize=8)
    largest=mean_image; axes[1,1].imshow(10*np.log10(np.maximum(largest,np.finfo(float).tiny)),cmap="gray",origin="lower",extent=[-max_lp/2,max_lp/2,-325,325],aspect="equal",vmin=np.percentile(10*np.log10(largest),2),vmax=np.percentile(10*np.log10(largest),99.7));axes[1,1].set(xlabel="parallel to k (m)",ylabel="perpendicular to k (m)",title=f"{max_lp} x 650 m mean sublook intensity")
    fig.suptitle("Block 7: spatial peak convergence and homogeneity")
    fig.savefig(OUT/"BLOCK7_SPATIAL_CONVERGENCE.png",dpi=180);plt.close(fig)
    print(json.dumps({"largest":summary[-1],"nearshore_anchored":summary_anchored,"convergence":diagnostics["large_roi_convergence"],"homogeneity":diagnostics["homogeneity"]},indent=2))


if __name__=="__main__": main()

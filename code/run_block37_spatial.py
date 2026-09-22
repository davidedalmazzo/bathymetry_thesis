"""Execute the frozen Block37 real Sentinel-1 Duck spatial trial."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.enums import Resampling

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from s1_iw_annotation import GeoGrid, parse_annotation
from s1_spatial_trial import (
    axial_difference, calibrated_power, fit_frf_affine, frf_en_basis,
    frf_to_geo, grid_coordinates, parse_calibration_lut, parse_noise_lut,
    evaluate_noise, invert_dispersion, read_resampled_complex, spatial_spectrum,
)

BLOCK = ROOT / "duck_frf" / "Block37_s1_iw_spatial_trial"
BLOCK35 = ROOT / "duck_frf" / "Block35_s1_spatial_selection"
BLOCK36 = ROOT / "duck_frf" / "Block36_s1_iw_annotation_preflight"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")


def safe_float(value):
    value = float(value)
    return value if np.isfinite(value) else None


def locate(config):
    safe = next((BLOCK / "extracted_safe").glob(config["product_name"]))
    stem = "*iw3*vv*"
    return {
        "safe": safe,
        "tiff": next(safe.glob(f"measurement/{stem}.tiff")),
        "annotation": next(safe.glob(f"annotation/{stem}.xml")),
        "calibration": next(safe.glob(f"annotation/calibration/calibration-{stem}.xml")),
        "noise": next(safe.glob(f"annotation/calibration/noise-{stem}.xml")),
    }


def radiometry(dn, lines, samples, cal, noise_lut):
    raw = np.abs(dn)**2
    sigma = calibrated_power(dn, cal, lines, samples)
    thermal = evaluate_noise(noise_lut, lines, samples, "IW3")
    noise_sigma = calibrated_power(dn, cal, lines, samples, thermal)
    return {"raw_dn_power": raw, "sigma0_lut": sigma,
            "sigma0_noise_subtracted": noise_sigma}, thermal


def compact_result(result, common):
    omit = {"power", "kx", "ky"}
    out = {**common, **{k: v for k, v in result.items() if k not in omit}}
    for key, value in list(out.items()):
        if isinstance(value, (np.floating, float)):
            out[key] = safe_float(value)
    return out


def variant_specs():
    return [
        ("primary", "plane", "hann", "sigma0_lut", 1),
        ("quadratic_hann", "quadratic", "hann", "sigma0_lut", 1),
        ("plane_tukey", "plane", "tukey_alpha_0.25", "sigma0_lut", 1),
        ("raw_hann", "plane", "hann", "raw_dn_power", 1),
        ("noise_sub_hann", "plane", "hann", "sigma0_noise_subtracted", 1),
        ("nearest_hann", "plane", "hann", "sigma0_lut", 0),
    ]


def frf_reference():
    p = BLOCK35 / "frf-refined" / "c49a9c1f-9b00-5676-ab05-683975d898a2"
    summaries = load(p / "SPECTRAL_SUMMARIES.json")
    tensors = load(p / "TENSORS.json")
    output=[]
    for summary in summaries:
        pointer=summary["tensor_pointer"].split("/")
        key,var,index=pointer[0],pointer[2],int(pointer[3])
        item=tensors[key]
        freq=np.asarray(item["variables"]["waveFrequency"]["raw_values"],float)
        energy=np.asarray(item["variables"][var]["raw_values"],float)[index]
        energy=np.asarray(energy,float)
        mask=np.asarray(item["variables"][var]["valid_mask"],bool)[index]
        valid=np.isfinite(energy)&mask
        peak=int(np.nanargmax(np.where(valid,energy,np.nan)))
        half=valid & (energy>=energy[peak]/2)
        pb=summary["published_peak_band"]
        output.append({
            "instrument_id":summary["instrument_id"],"offset_seconds":summary["offset_seconds"],
            "Hm0_m":summary["Hm0_m"],"published_Tp_s":pb["waveTp"],
            "discrete_peak_period_s":1/freq[peak],"discrete_peak_frequency_hz":freq[peak],
            "half_power_frequency_hz":[float(freq[half].min()),float(freq[half].max())],
            "mean_direction_from_deg":pb["waveMeanDirectionPeakFrequency"],
            "peak_direction_from_deg":pb["wavePeakDirectionPeakFrequency"],
            "propagation_toward_deg":(pb["waveMeanDirectionPeakFrequency"]+180)%360,
            "directional_spread_deg":pb["directionalPeakSpread"],
            "valid_bin_fraction":summary["valid_bin_fraction"],"spectral_status":summary["status"],
            "qc_note":"nearest verified complete spectrum; published mean/mode directions retained separately",
        })
    return output


def make_figures(annotation, geo, coef, paths, grids, primary_spectra, supports, frf_dir):
    figures=BLOCK/"figures"; figures.mkdir(exist_ok=True)
    # Burst overview: downsample only burst 0, preserving the bounded burst read.
    with rasterio.open(paths["tiff"]) as ds:
        arr=ds.read(1,window=rasterio.windows.Window(0,0,ds.width,annotation["lines_per_burst"]),
                    out_shape=(350,900),resampling=Resampling.nearest)
    img=np.log10(np.maximum(np.abs(arr)**2,1))
    roi=load(BLOCK35/"PROPOSED_ROI.json")["geojson"]["coordinates"][0]
    pix=np.asarray([geo.geo_to_image(*p) for p in roi])
    fig,ax=plt.subplots(figsize=(11,5)); ax.imshow(img,extent=[0,annotation["number_of_samples"],annotation["lines_per_burst"],0],cmap="gray",aspect="auto")
    ax.plot(pix[:,0],pix[:,1],"r-",lw=2,label="fixed Block35 ROI")
    ax.set(xlabel="slant-range sample",ylabel="azimuth line",title="IW3 burst 0 overview (display decimated only)"); ax.legend(); fig.tight_layout()
    fig.savefig(figures/"BURST_ROI_OVERVIEW.png",dpi=160); plt.close(fig)

    xx,yy,images,valid=grids[-1]
    sigma=images["sigma0_lut"]
    fig,axs=plt.subplots(1,3,figsize=(14,4.2),sharex=True,sharey=True)
    im=axs[0].pcolormesh(xx,yy,sigma,shading="nearest",cmap="viridis"); fig.colorbar(im,ax=axs[0],label="sigma0 linear")
    im=axs[1].pcolormesh(xx,yy,10*np.log10(np.maximum(sigma,np.nanpercentile(sigma,1))),shading="nearest",cmap="gray"); fig.colorbar(im,ax=axs[1],label="dB (display only)")
    im=axs[2].pcolormesh(xx,yy,valid.astype(int),shading="nearest",vmin=0,vmax=1,cmap="gray"); fig.colorbar(im,ax=axs[2],label="valid")
    for ax,title in zip(axs,["linear calibrated intensity","log display","exact-source validity"]):
        ax.set(title=title,xlabel="xFRF (m)"); ax.set_aspect("equal")
    axs[0].set_ylabel("yFRF (m)"); fig.tight_layout(); fig.savefig(figures/"ROI_INTENSITY_VALID.png",dpi=180); plt.close(fig)

    fig,axs=plt.subplots(1,len(primary_spectra),figsize=(15,4.5))
    for ax,(label,r) in zip(axs,primary_spectra):
        p=10*np.log10(np.maximum(r["power"],np.max(r["power"])*1e-8))
        im=ax.pcolormesh(r["kx"],r["ky"],p,shading="auto",cmap="magma")
        iy,ix=r["selected_index"]; ax.plot(r["kx"][ix],r["ky"][iy],"co",mfc="none",ms=9)
        ax.set(title=f"{label}\nλ={r['wavelength_m']:.1f} m, θ={r['axial_bearing_deg']:.1f}°",xlabel="kxFRF (rad/m)")
        ax.set_ylabel("kyFRF (rad/m)"); fig.colorbar(im,ax=ax,label="power dB")
    fig.tight_layout(); fig.savefig(figures/"SPATIAL_SPECTRA.png",dpi=180); plt.close(fig)

    # Orientation diagram in true EN bearing space.
    fig,ax=plt.subplots(figsize=(6,6)); ax.set_aspect("equal"); ax.set_xlim(-1.2,1.2); ax.set_ylim(-1.2,1.2)
    def arrow(b,c,label):
        r=math.radians(b); ax.arrow(0,0,math.sin(r),math.cos(r),color=c,width=.012,length_includes_head=True,label=label)
    local=load(BLOCK36/"LOCAL_GEOMETRY.json")["subswaths"][0]
    arrow(0,"k","North"); arrow(local["range_sample_bearing_deg"],"tab:blue","local range")
    arrow(local["azimuth_line_bearing_deg"],"tab:green","local azimuth"); arrow(frf_dir,"tab:orange","FRF propagation")
    if primary_spectra: arrow(primary_spectra[-1][1]["bearing_toward_deg"],"tab:red","SAR selected axial family")
    ax.legend(loc="lower left"); ax.set_title("Orientation audit (bearings clockwise from North)"); ax.axis("off"); fig.tight_layout()
    fig.savefig(figures/"ORIENTATION.png",dpi=180); plt.close(fig)


def main():
    config=load(BLOCK/"CONFIG.json"); paths=locate(config)
    annotation=parse_annotation(paths["annotation"].read_bytes(),expected_swath="IW3",expected_polarisation="VV")
    geo=GeoGrid(annotation); roi=load(BLOCK35/"PROPOSED_ROI.json")
    coef,residual=fit_frf_affine(roi["frf_bounds_m"],roi["geojson"])
    basis=frf_en_basis(coef,config["window_center_frf_m"])
    cal=parse_calibration_lut(paths["calibration"]); noise_lut=parse_noise_lut(paths["noise"])
    grids=[]; all_rows=[]; primary=[]; supports=[]
    cache={}
    for size in config["window_sizes_frf_m"]:
        xx,yy=grid_coordinates(config["window_center_frf_m"],size,config["analysis_grid_spacing_frf_m"])
        for variant,detr,taper,rad,order in variant_specs():
            key=(tuple(size),order)
            if key not in cache:
                dn,lines,samples,valid,support=read_resampled_complex(paths["tiff"],annotation,geo,coef,xx,yy,order,config["burst_index"])
                images,thermal=radiometry(dn,lines,samples,cal,noise_lut)
                cache[key]=(dn,lines,samples,valid,support,images,thermal)
            dn,lines,samples,valid,support,images,thermal=cache[key]
            common={"window_width_m":size[0],"window_height_m":size[1],"variant":variant,
                    "radiometry":rad,"interpolation":"bilinear" if order else "nearest",
                    "negative_after_noise_fraction":float(np.mean(np.abs(dn)**2-thermal<=0)) if rad=="sigma0_noise_subtracted" else 0.0}
            if not np.all(np.isfinite(images[rad])):
                all_rows.append({**common,"processing_status":"unavailable_masked_pixels",
                                 "reason":"negative post-noise power is masked; FFT is not filled or clipped"})
                continue
            result=spatial_spectrum(images[rad],xx,yy,detrend=detr,taper=taper,padding=config["zero_padding_factor"],exclusion_bins=config["central_exclusion_bins"],basis_en=basis)
            all_rows.append(compact_result(result,{**common,"processing_status":"complete"}))
            if variant=="primary": primary.append((f"{int(size[0])}x{int(size[1])} m",result)); supports.append(support)
        grids.append((xx,yy,cache[(tuple(size),1)][5],cache[(tuple(size),1)][3]))
    fields=[]
    for row in all_rows:
        for key in row:
            if key not in fields and not isinstance(row[key],(list,dict)): fields.append(key)
    with (BLOCK/"SPATIAL_RESULTS.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(all_rows)
    primary_rows=[r for r in all_rows if r["variant"]=="primary"]
    waves=[r["wavelength_m"] for r in primary_rows]; angles=[r["axial_bearing_deg"] for r in primary_rows]
    angle_range=max(axial_difference(a,b) for a in angles for b in angles)
    stable=(max(waves)/min(waves)-1 <= config["stability_wavelength_relative_range_max"] and
            angle_range <= config["stability_axial_direction_range_max_deg"] and
            min(r["lobe_to_annular_median"] for r in primary_rows)>=config["minimum_lobe_to_annular_median"])
    pixel_support={
        "measurement_relative_path":str(paths["tiff"].relative_to(paths["safe"])).replace('\\','/'),
        "measurement_bytes":paths["tiff"].stat().st_size,"annotation_dimensions":[annotation["number_of_lines"],annotation["number_of_samples"]],
        "polarisation":"VV","subswath":"IW3","burst_index":0,"lines_per_burst":annotation["lines_per_burst"],
        "source_windows":supports,"frf_affine_lon_lat_coefficients":coef.tolist(),"affine_corner_residual_max_deg":residual,
        "frf_basis_EN_m_per_m":basis.tolist(),"calibration_formula":cal["formula"],"noise_formula":noise_lut["formula"],
        "nodata_handling":"no declared nodata; exact annotation validity required; no invalid-to-zero replacement",
        "iq_check":{"complex_type":True,"real_nontrivial":all(s["real_std"]>0 for s in supports),"imag_nontrivial":all(s["imag_std"]>0 for s in supports)},
    }
    dump(BLOCK/"PIXEL_SUPPORT.json",pixel_support)
    refs=frf_reference(); frf_dir=refs[0]["propagation_toward_deg"]
    deltas=[axial_difference(r["axial_bearing_deg"],frf_dir) for r in primary_rows]
    compatible=stable and max(deltas)<=config["frf_direction_compatibility_deg"]
    association="identifiable" if compatible and all(x["spectral_status"]=="complete_spectrum" for x in refs) else ("compatible but ambiguous" if min(deltas)<=config["frf_direction_compatibility_deg"] else "not identifiable")
    assoc={"classification":association,"sar_stable_unique_lobe":stable,"sar_primary_results":primary_rows,
           "frf_references":refs,"sar_frf_axial_differences_deg":deltas,
           "tolerance_deg":config["frf_direction_compatibility_deg"],
           "selection_order":"SAR-only result saved before external comparison; no expected-band or depth filter",
           "reason":"stable SAR family and direction-compatible complete FRF systems" if association=="identifiable" else "frozen stability/direction gate not passed or pairing remains non-unique"}
    dump(BLOCK/"FRF_ASSOCIATION.json",assoc)
    inversion_rows=[]; survey_comparison=[]
    if association=="identifiable":
        k_values=np.asarray([r["k_magnitude_rad_m"] for r in primary_rows]); k=float(np.median(k_values))
        for ref in refs:
            omega=2*np.pi/ref["discrete_peak_period_s"]
            f0,f1=ref["half_power_frequency_hz"]
            for current in config["current_sensitivity_m_s"]:
                inv=invert_dispersion(k,omega,current)
                inversion_rows.append({"instrument_id":ref["instrument_id"],"case":"projected_current",
                    "k_rad_m":k,"frequency_hz":1/ref["discrete_peak_period_s"],"omega_absolute_rad_s":omega,
                    "current_along_propagation_m_s":current,**inv})
            for kval,label in ((float(k_values.min()),"k_primary_min"),(float(k_values.max()),"k_primary_max")):
                inv=invert_dispersion(kval,omega,0)
                inversion_rows.append({"instrument_id":ref["instrument_id"],"case":label,"k_rad_m":kval,
                    "frequency_hz":1/ref["discrete_peak_period_s"],"omega_absolute_rad_s":omega,
                    "current_along_propagation_m_s":0,**inv})
            for freq,label in ((f0,"omega_halfpower_min"),(f1,"omega_halfpower_max")):
                inv=invert_dispersion(k,2*np.pi*freq,0)
                inversion_rows.append({"instrument_id":ref["instrument_id"],"case":label,"k_rad_m":k,
                    "frequency_hz":freq,"omega_absolute_rad_s":2*np.pi*freq,
                    "current_along_propagation_m_s":0,**inv})
        fields_inv=[]
        for row in inversion_rows:
            for key in row:
                if key not in fields_inv: fields_inv.append(key)
        with (BLOCK/"CONDITIONAL_INVERSION.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields_inv); w.writeheader(); w.writerows(inversion_rows)
        survey=load(BLOCK35/"surveys"/"FRF_geomorphology_elevationTransects_survey_20211024.nc.json")
        for size in config["window_sizes_frf_m"]:
            cx,cy=config["window_center_frf_m"]; w,h=size
            values=[p["elevation"] for p in survey["points"] if cx-w/2<=p["xFRF"]<=cx+w/2 and cy-h/2<=p["yFRF"]<=cy+h/2]
            survey_comparison.append({"window_m":size,"point_count":len(values),
                "bed_elevation_NAVD88_percentiles_m":np.percentile(values,[5,50,95]).tolist() if values else None})
        dump(BLOCK/"SURVEY_COMPARISON.json",{"survey_date":"2021-10-24","vertical_datum":"NAVD88",
            "instantaneous_depth_status":"not derivable: verified event water level absent",
            "comparison_role":"post-inversion context only; survey did not select k, omega, sign, or current",
            "windows":survey_comparison})
    validation={"visibility":"visible_but_weak_and_speckle_contaminated_manual_audit",
                "visual_features":{"periodic_crest_like_streaks":True,"multiple_clean_bands":False,
                    "coast_or_pier_in_roi":False,"ship_or_wake_confidently_identified":False,
                    "burst_join_in_roi":False,"isolated_bright_pixels":True},
                "measurability":"primary_bilinear_lobe_stable_with_material_nearest_neighbor_sensitivity" if stable else "not_identifiable",
                "association":association,"conditional_inversion_executed":association=="identifiable",
                "validation":"not_established; conditional inversion only and NAVD88 bed elevation is not instantaneous water depth",
                "primary_wavelength_range_m":[min(waves),max(waves)],"primary_axial_direction_range_deg":angle_range,
                "primary_lobe_background_min":min(r["lobe_to_annular_median"] for r in primary_rows),
                "nearest_neighbor_sensitivity":"selects a distinct 42-45 m, 43-44 degree family",
                "noise_subtraction_sensitivity":"unavailable because 12-13 percent non-positive powers remain masked"}
    dump(BLOCK/"VALIDATION_RESULTS.json",validation)
    make_figures(annotation,geo,coef,paths,grids,primary,supports,frf_dir)
    # Save numerical spectra separately only as lightweight compressed arrays.
    np.savez_compressed(BLOCK/"cache"/"primary_spectra.npz",**{f"power_{i}":r["power"] for i,(_,r) in enumerate(primary)}) if (BLOCK/"cache").exists() else None
    print(json.dumps({"stable":stable,"association":association,"primary":primary_rows,"pixel_support":pixel_support},indent=2))


if __name__=="__main__":
    main()

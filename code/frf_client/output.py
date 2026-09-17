"""Readable dossiers, long tables, JSON tensor equivalents, maps and provenance."""
import csv
import json
import math
import re
import sys
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from . import __version__
from .data import associate, qc_pass, utc, spectral_summary
from .client import qc_variable, historical_position, finite_list, ALIASES
from .geometry import polygon, distances, inverse
from .transport import save_json, digest


def table(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row)) or ["status"]
    with Path(path).open("w",newline="",encoding="utf-8") as f:
        writer = csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def iso(epoch):
    return datetime.fromtimestamp(float(epoch),timezone.utc).isoformat()


def temporal_metadata(family, attrs, arrays, index):
    """Never assume that the timestamp denotes a burst center or endpoint."""
    glob = attrs.get("NC_GLOBAL",{})
    summary = glob.get("summary","")
    duration = None
    if family == "wind":
        duration = 600 if "10 minute" in summary or "10-min" in summary else None
    elif family == "waves" and ("30 minutes" in summary or "30 minute" in summary):
        duration = 1800
    elif family == "currents" and "aveTime" in arrays:
        units = attrs.get("aveTime",{}).get("units","")
        value = float(np.asarray(arrays["aveTime"])[index])
        if math.isfinite(value) and value > 0 and units in ("s","seconds","sec"):
            duration = value
    return {"duration_seconds_from_source":duration,
            "interval_start_utc":None,"interval_end_utc":None,
            "timestamp_anchor":"not verified; burst boundaries not invented",
            "measurement_kind":"averaged_spectrum_or_burst" if family in ("waves","currents") else "averaged_wind" if family=="wind" else "observed_level",
            "interval_distance_seconds":None}


def dossier(acquisition, products, inventory, errors, config, output, transport):
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", acquisition["acquisition_id"])
    base = output/safe_id
    base.mkdir(parents=True,exist_ok=True)
    fp, roi = polygon(acquisition.get("footprint")), polygon(acquisition.get("roi"))
    target = utc(acquisition["timestamp_utc"]).timestamp()
    rows, spatial, tensors, associations, summaries, completeness, warnings = [], [], {}, [], [], [], []
    for p in products:
        loaded = p["loaded"]
        family, instrument = p["family"],p["instrument"]
        arrays, masks, times = loaded["arrays"],loaded["masks"],loaded["times"]
        attrs = loaded["metadata"]["attributes"]
        if family=="currents" and "awac5m" in attrs.get("NC_GLOBAL",{}).get("id","").lower() and instrument=="awac-11m":
            warnings.append({"instrument":instrument,"family":family,"status":"supplier_identifier_conflict",
                             "detail":"URL/title identify 11m AWAC but NC_GLOBAL.id identifies awac5m; both original fields retained, stable logical site ID uses discovered path"})
        if family=="currents" and attrs.get("aveTime",{}).get("units")=="index":
            warnings.append({"instrument":instrument,"family":family,"status":"averaging_time_metadata_conflict",
                             "detail":"aveTime long_name says seconds, units says index; raw 900 retained, interval duration/anchor not automatically inferred"})
        nearest_raw = int(np.argmin(abs(times-target)))
        defaults={"waves":["waveHs","waveTp","waveMeanDirectionPeakFrequency"],
                  "wind":["windSpeed","windDirection"],"currents":["currentEast","currentNorth"],"water_level":["waterLevel"]}
        requested=config.get("required_variables",{}).get(family,defaults[family])
        fractions={v:float(np.mean(masks[v][nearest_raw] if np.asarray(arrays[v]).ndim and np.asarray(arrays[v]).shape[0]==len(times) else masks[v])) if v in masks else None for v in requested}
        completeness.append({"instrument_id":"FRF:"+instrument,"family":family,"required_variables":requested,
                             "valid_fractions":fractions,"joint_all_requested_valid":all(x==1. for x in fractions.values()),
                             "only_requested_variables_counted":True,"qc_policy_applied_separately":True})
        historical = historical_position(attrs,arrays,nearest_raw,family)
        fpdist, roidist = distances(historical["lon_lat"],fp), distances(historical["lon_lat"],roi)
        if historical["position_uncertain"]:
            for d in (fpdist,roidist):
                if d["status"] != "not_evaluable":
                    d["status"] += "_position_uncertain"
        spatial.append({"instrument_id":"FRF:"+instrument,"family":family,
                        "position_status":historical["status"], "lon_lat_json":json.dumps(historical["lon_lat"]),
                        "position_uncertain":historical["position_uncertain"],"position_discrepancy_m":historical["position_discrepancy_m"],
                        **{"footprint_"+k:v for k,v in fpdist.items()}, **{"roi_"+k:v for k,v in roidist.items()}})
        name = family+"__"+instrument
        tensors[name] = {"format":"FRF tensor JSON v1; shape + raw_values + mask per variable; None encodes nonfinite",
                         "source":loaded["metadata"]["source"],"coverage":loaded["coverage"],
                         "historical_position":historical,
                         "variables":{v:{"shape":list(np.asarray(a).shape),"raw_values":finite_list(a),
                                          "valid_mask":masks[v].tolist(),"attributes":attrs.get(v,{})} for v,a in arrays.items()},
                         "metadata":loaded["metadata"], "aliases":ALIASES.get(instrument,[]),
                         "stable_identity":"FRF:"+instrument,"operator":attrs.get("NC_GLOBAL",{}).get("creator_name"),
                         "platform":attrs.get("NC_GLOBAL",{}).get("platform"),
                         "sensor":attrs.get("NC_GLOBAL",{}).get("instrument",attrs.get("NC_GLOBAL",{}).get("sensor_type"))}
        for variable, arr in arrays.items():
            shape = np.asarray(arr).shape
            if not shape or shape[0] != len(times) or variable in ("time","waveFrequency","waveDirectionBins","depth") or variable.lower().startswith("qc"):
                continue
            validity = masks[variable].reshape(len(times),-1)
            present = np.any(validity,axis=1)
            qcname = qc_variable(family,variable,arrays)
            if qcname:
                qcmask = qc_pass(arrays[qcname],attrs.get(qcname,{}),config["accepted_qc_flags"])
                qcmask = np.all(qcmask.reshape(len(times),-1),axis=1)
                qcstatus = "source_flag_checked"
            else:
                qcmask = np.full(len(times),config["accept_unknown_qc"],bool)
                qcstatus = "unknown_source_qc_not_assumed_pass"
            association = associate(times,target,present&qcmask,config["time_tolerance_seconds"][family],loaded.get("intervals"))
            association.update(instrument_id="FRF:"+instrument,family=family,variable=variable,qc_variable=qcname,qc_status=qcstatus,
                               nearest_raw_utc=iso(times[nearest_raw]),nearest_raw_offset_seconds=float(times[nearest_raw]-target))
            associations.append(association)
            choices = {"nearest_context":nearest_raw, "previous_qc":association["previous"],
                       "next_qc":association["next"], "nearest_qc":association["nearest"]}
            for role,j in choices.items():
                if j is None:
                    continue
                dt = float(times[j]-target)
                valid = bool(present[j])
                passes = bool(qcmask[j])
                current = abs(dt) <= config["time_tolerance_seconds"][family]
                status = "missing" if not valid else "qc_failed" if qcname and not passes else "qc_unknown" if not qcname and not passes else "outside_tolerance" if not current else "retrieved"
                value = np.asarray(arr[j])
                scalar = value.ndim == 0
                temporal = temporal_metadata(family,attrs,arrays,j)
                if loaded.get("intervals") is not None:
                    lo,hi=loaded["intervals"][j]
                    temporal.update(interval_start_utc=iso(lo),interval_end_utc=iso(hi),
                                    interval_distance_seconds=max(lo-target,target-hi,0.),
                                    timestamp_anchor="explicit source time bounds")
                rows.append({"acquisition_id":acquisition["acquisition_id"],"instrument_id":"FRF:"+instrument,
                             "family":family,"product":p["source"],"variable":variable,"role":role,
                             "sensor_time_utc":iso(times[j]), "timestamp_original":float(arrays["time"][j]),
                             "timestamp_original_units":attrs["time"]["units"],"offset_seconds":dt,
                             "interval_distance_seconds":temporal["interval_distance_seconds"],
                             "observation_duration_seconds":temporal["duration_seconds_from_source"],
                             "interval_start_utc":temporal["interval_start_utc"],"interval_end_utc":temporal["interval_end_utc"],
                             "units":attrs.get(variable,{}).get("units"),
                             "value":float(value) if scalar and valid else None,
                             "tensor_pointer":name+"/variables/"+variable+"/"+str(j),
                             "status":status,"within_tolerance":current,
                             "representative_eligible":valid and passes and current,
                             "qc_flag":float(np.asarray(arrays[qcname])[j]) if qcname and np.asarray(arrays[qcname])[j].ndim==0 else None,
                             "valid_fraction":float(np.mean(validity[j])),
                             "interpretation":attrs.get(variable,{}).get("description",attrs.get(variable,{}).get("long_name"))})
        if "waveEnergyDensity" in arrays and "waveFrequency" in arrays:
            arr = arrays["waveEnergyDensity"]
            if arr.ndim==2 and arr.shape[1]==len(arrays["waveFrequency"]):
                widths=arrays.get("waveFrequencyBandwidth")
                if widths is not None and np.asarray(widths).shape != np.asarray(arrays["waveFrequency"]).shape:
                    widths=None
                summary = spectral_summary(arrays["waveFrequency"],arr[nearest_raw],masks["waveEnergyDensity"][nearest_raw],widths)
                summary.update(instrument_id="FRF:"+instrument,offset_seconds=float(times[nearest_raw]-target),
                               integral_qc="see_variable_qc_association; spectrum summary is diagnostic, not representative by default")
                published = float(arrays["waveHs"][nearest_raw]) if "waveHs" in arrays and masks["waveHs"][nearest_raw] else None
                summary["published_Hs_m"] = published
                summary["Hm0_minus_published_Hs_m"] = summary["Hm0_m"]-published if published is not None else None
                summary["published_peak_band"] = {v:float(arrays[v][nearest_raw]) if v in arrays and masks[v][nearest_raw] else None
                                                   for v in ("waveTp","waveMeanDirectionPeakFrequency","wavePeakDirectionPeakFrequency","directionalPeakSpread")}
                summary["peak_band_caveat"] = "Published peak-frequency mean/mode and spread retained separately; all-frequency mean direction NOT assigned to Tp"
                peak = summary["peak_bin"]
                if peak is not None and "waveA1Value" in arrays and "waveB1Value" in arrays:
                    a1,b1 = arrays["waveA1Value"][nearest_raw,peak],arrays["waveB1Value"][nearest_raw,peak]
                    summary["peak_bin_directional_moments"]={"a1":float(a1) if np.isfinite(a1) else None,"b1":float(b1) if np.isfinite(b1) else None,
                                                               "direction_reconstructed":"not performed: moment-axis convention/estimator not inferred"}
                summaries.append(summary)
        _plots_product(base,name,family,loaded,target,nearest_raw)
    table(base/"OBSERVATIONS.csv",rows)
    table(base/"DISTANCES.csv",spatial)
    save_json(base/"TENSORS.json",tensors)
    save_json(base/"ASSOCIATIONS.json",associations)
    save_json(base/"SPECTRAL_SUMMARIES.json",summaries)
    save_json(base/"COMPLETENESS.json",completeness)
    save_json(base/"PROVENANCE_WARNINGS.json",warnings)
    save_json(base/"INVENTORY.json",inventory)
    save_json(base/"ACQUISITION.json",acquisition)
    save_json(base/"CONFIG.json",config)
    _map(base,fp,roi,spatial)
    selected = [r for r in rows if r["role"]=="nearest_qc" and r["representative_eligible"] and r["value"] is not None]
    contextual = [r for r in rows if r["role"]=="nearest_context" and r["variable"] in ("waveHs","waveTp","waveMeanDirection","windSpeed","waterLevel","currentSpeed")]
    lines = ["# FRF observational dossier: "+acquisition["acquisition_id"],"",
             "Timestamp: "+acquisition["timestamp_utc"]+"; semantics: "+acquisition["timestamp_semantics"],"",
             "Catalogue footprint only; valid SAR support NOT VERIFIED. No SAR data read.","",
             "## A. Original measurements (independent per product/instrument)","",
             "| instrument | variable | value | units | offset s | status |", "|---|---|---:|---|---:|---|"]
    for r in contextual:
        lines.append(f"|{r['instrument_id']}|{r['variable']}|{r['value']}|{r['units']}|{r['offset_seconds']:.3f}|{r['status']}|")
    lines += ["","Only rows with representative_eligible=True pass the configured QC and time policy; context never fills another instrument.","",
              "## B. Calculated quantities","","WGS84 distances in DISTANCES.csv, signed offsets and previous/next/nearest QC association in ASSOCIATIONS.json. Spectral integrals are diagnostic, with missing-bin coverage and published-Hs difference. No directional reconstruction or SAR inversion.","",
              "## C. Assumptions","","Configured temporal tolerances are operational, not universal physical limits. Historical nominal coordinates are conditioned on the dated source; conflicting deployment text remains in metadata. No interpolation, wave refraction or wind-height conversion. Depth datum is preserved, not assumed instantaneous water depth.","",
              "## D. Missing/conditional information","","No joint state of the tile is asserted. Position is not automatically a measured GPS location. Unverified burst anchoring leaves interval bounds/distance unknown. Unflagged products are QC-unknown under the default strict policy. Survey point/line coverage is not inferred from a bounding box. Unsupported/unfetched families and network limits are listed below:","",
              "```json",json.dumps(errors,indent=2),"```", "",
              "Source metadata warnings: "+json.dumps(warnings),"",
              "Profiles/2D spectra, when present, are preserved in TENSORS.json with source definitions and masks. Ancillary meteorology/temperature only from selected products. NDBC/CDIP alias republication is not counted independently."]
    (base/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    manifest = {"client_version":__version__,"python":sys.version,"configuration":config,
                "numpy_version":np.__version__,"matplotlib_version":matplotlib.__version__,
                "acquisition":acquisition,"network_tranche":transport.state,
                "cache_payloads":[],"artifacts":[],"code_sources":[]}
    for p in sorted(transport.directory.glob("*.json")):
        obj = json.loads(p.read_text())
        if obj.get("status")=="ok":
            manifest["cache_payloads"].append({"url":obj["url"],"sha256":obj["sha256"],"bytes":obj["bytes"]})
    for p in sorted(base.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.json":
            manifest["artifacts"].append({"path":str(p),"bytes":p.stat().st_size,"sha256":digest(p.read_bytes())})
    for p in sorted(Path("code/frf_client").glob("*.py")) + [Path("code/run_block32_frf_client.py"),Path("code/run_block30_frf_conditions.py")]:
        manifest["code_sources"].append({"path":str(p),"sha256":digest(p.read_bytes())})
    save_json(base/"MANIFEST.json",manifest)


def _plots_product(base,name,family,loaded,target,index):
    arrays,masks,times = loaded["arrays"],loaded["masks"],loaded["times"]
    variable = {"waves":"waveHs","wind":"windSpeed","currents":"currentSpeed","water_level":"waterLevel"}[family]
    if variable in arrays:
        fig,ax=plt.subplots(figsize=(7,3))
        values = np.where(masks[variable],arrays[variable],np.nan)
        ax.plot((times-target)/60,values,".-")
        ax.axvline(0,color="red",label="SAR catalogue timestamp")
        ax.set(xlabel="sensor time minus SAR timestamp (min)",ylabel=variable,title=name+"; no interpolation")
        ax.legend();fig.tight_layout();fig.savefig(base/(name+"_time.png"),dpi=130);plt.close(fig)
    if family=="waves" and "waveEnergyDensity" in arrays and "waveFrequency" in arrays:
        fig,ax=plt.subplots(figsize=(6,3))
        ax.plot(arrays["waveFrequency"],np.where(masks["waveEnergyDensity"][index],arrays["waveEnergyDensity"][index],np.nan))
        ax.set(xlabel="frequency (Hz)",ylabel="spectral density (source units)",title=name+"; nearest context, QC separate")
        fig.tight_layout();fig.savefig(base/(name+"_spectrum.png"),dpi=130);plt.close(fig)
        if "directionalWaveEnergyDensity" in arrays and "waveDirectionBins" in arrays:
            fig,ax=plt.subplots(figsize=(6,3))
            array=np.where(masks["directionalWaveEnergyDensity"][index],arrays["directionalWaveEnergyDensity"][index],np.nan)
            ax.pcolormesh(arrays["waveDirectionBins"],arrays["waveFrequency"],array,shading="auto")
            ax.set(xlabel="direction bins (source convention)",ylabel="Hz",title="Provided directional spectrum; no reconstruction")
            fig.tight_layout();fig.savefig(base/(name+"_directional_spectrum.png"),dpi=130);plt.close(fig)
    if family=="currents" and "currentEast" in arrays and "depth" in arrays:
        fig,ax=plt.subplots(figsize=(4,5))
        for var in ("currentEast","currentNorth"):
            if var in arrays:
                ax.plot(np.where(masks[var][index],arrays[var][index],np.nan),arrays["depth"],".-",label=var)
        ax.set(xlabel="velocity (source units)",ylabel="depth/elevation (source datum)",title="AWAC profile, not assumed surface current")
        ax.legend();fig.tight_layout();fig.savefig(base/(name+"_profile.png"),dpi=130);plt.close(fig)


def _map(base,fp,roi,spatial):
    fig,ax=plt.subplots(figsize=(7,6))
    for geo,color,label in [(fp,"black","catalogue footprint; SAR valid support unverified"),(roi,"blue","ROI")]:
        if geo is None:
            continue
        polygons=[geo] if geo.geom_type=="Polygon" else list(geo.geoms)
        for j,poly in enumerate(polygons):
            x,y=poly.exterior.xy
            ax.plot(x,y,color=color,label=label if j==0 else None)
    positions={r["instrument_id"]:json.loads(r["lon_lat_json"]) for r in spatial if r["lon_lat_json"] != "null"}
    for name,position in positions.items():
        ax.plot(*position,"o",label=name)
    ax.set(xlabel="longitude (WGS84)",ylabel="latitude (WGS84)",title="Historical source positions; proximity is not representativity")
    if positions or fp is not None:
        x0,x1=ax.get_xlim();y0,y1=ax.get_ylim()
        mid=(y0+y1)/2
        ax.set_aspect(1/max(math.cos(math.radians(mid)),.01))
        ax.annotate("N",xy=(.92,.93),xytext=(.92,.80),xycoords="axes fraction",arrowprops={"arrowstyle":"->"},ha="center")
        lon=x0+.05*(x1-x0);lat=y0+.05*(y1-y0)
        dl=(x1-x0)*.2
        length=inverse(lon,lat,lon+dl,lat)[0]
        ax.plot([lon,lon+dl],[lat,lat],"k-",lw=3)
        ax.text(lon,lat,f" {length/1000:.2f} km",va="bottom",fontsize=8)
    else:
        ax.text(.5,.5,"No geographic inputs/verified sensor positions; distances not evaluable",ha="center",transform=ax.transAxes,wrap=True)
    handles,labels=ax.get_legend_handles_labels()
    if handles: ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(base/"MAP.png",dpi=130);plt.close(fig)

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
from .data import associate, qc_pass, utc, spectral_summary,mask_values
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


def dossier(acquisition, products, inventory, errors, config, output, transport, search_coverage=None):
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
        if not len(times):continue
        nearest_raw = int(np.argmin(abs(times-target)))
        defaults={"waves":["waveHs","waveTp","waveMeanDirectionPeakFrequency"],
                  "wind":["windSpeed","windDirection"],"currents":["currentEast","currentNorth"],"water_level":["waterLevel"]}
        requested=config.get("required_variables",{}).get(family,defaults[family])
        fractions={v:float(np.mean(masks[v][nearest_raw] if np.asarray(arrays[v]).ndim and np.asarray(arrays[v]).shape[0]==len(times) else masks[v])) if v in masks else None for v in requested}
        completeness.append({"instrument_id":"FRF:"+instrument,"family":family,"required_variables":requested,
                             "product":p["source"],"offset_seconds":float(times[nearest_raw]-target),
                             "scope":"nearest raw context diagnostic, NOT representative event state",
                             "valid_fractions":fractions,"joint_all_requested_valid":all(x==1. for x in fractions.values()),
                             "only_requested_variables_counted":True,"qc_policy_applied_separately":True})
        indices=loaded.get("original_indices",np.arange(len(times)))
        positions={}
        def sample_position(j):
            if j in positions:return positions[j]
            historical=historical_position(attrs,arrays,j,family)
            fpdist,roidist=distances(historical["lon_lat"],fp),distances(historical["lon_lat"],roi)
            if historical["position_uncertain"]:
                for d in (fpdist,roidist):
                    if d["status"]!="not_evaluable":d["status"]+="_position_uncertain"
            key="position_"+digest((p["source"]+"|"+str(int(indices[j]))+"|"+str(float(times[j]))).encode())[:24]
            spatial.append({"position_id":key,"instrument_id":"FRF:"+instrument,"family":family,"product":p["source"],
                            "sensor_time_utc":iso(times[j]),"original_sample_index":int(indices[j]),
                            "effective_sensor_id":historical["sensor_id"],"deployment_status":historical["deployment_status"],
                            "deployment_start":historical["deployment_start"],"deployment_end":historical["deployment_end"],
                            "position_status":historical["status"],"lon_lat_json":json.dumps(historical["lon_lat"]),
                            "position_uncertain":historical["position_uncertain"],"position_discrepancy_m":historical["position_discrepancy_m"],
                            **{"footprint_"+k:v for k,v in fpdist.items()},**{"roi_"+k:v for k,v in roidist.items()}})
            positions[j]=key
            return key
        sample_position(nearest_raw)
        historical=historical_position(attrs,arrays,nearest_raw,family)
        name = family+"__"+instrument+"__"+digest(p["source"].encode())[:12]
        tensors[name] = {"format":"FRF tensor JSON v1; shape + raw_values + mask per variable; None encodes nonfinite",
                         "source":loaded["metadata"]["source"],"coverage":loaded["coverage"],
                         "historical_position":historical,
                         "original_sample_indices":np.asarray(indices).tolist(),
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
                qcknown=np.all(mask_values(arrays[qcname],attrs.get(qcname,{})).reshape(len(times),-1),axis=1)
            else:
                qcmask = np.full(len(times),config["accept_unknown_qc"],bool)
                qcstatus = "unknown_source_qc_not_assumed_pass"
                qcknown=np.zeros(len(times),bool)
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
                status = "missing" if not valid else "qc_unknown" if not qcknown[j] and not passes else "qc_failed" if qcname and not passes else "outside_tolerance" if not current else "retrieved"
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
                             "original_sample_index":int(indices[j]),"position_id":sample_position(j),
                             "sensor_vertical_context":json.dumps({v:{'value':finite_list(np.asarray(arrays[v])[j] if np.asarray(arrays[v]).ndim and np.asarray(arrays[v]).shape[0]==len(times) and v!='depth' else arrays[v]),'attributes':attrs.get(v,{})} for v in ('gaugeElevation','nominalDepth','gaugeDepth','depth') if v in arrays},allow_nan=False),
                             "status":status,"within_tolerance":current,
                             "representative_eligible":valid and passes and current,
                             "qc_flag":float(np.asarray(arrays[qcname])[j]) if qcname and qcknown[j] and np.asarray(arrays[qcname])[j].ndim==0 else None,
                             "valid_fraction":float(np.mean(validity[j])),
                             "interpretation":attrs.get(variable,{}).get("description",attrs.get(variable,{}).get("long_name"))})
        if "waveEnergyDensity" in arrays and "waveFrequency" in arrays:
            arr = arrays["waveEnergyDensity"]
            if arr.ndim==2 and arr.shape[1]==len(arrays["waveFrequency"]):
                widths=arrays.get("waveFrequencyBandwidth")
                if widths is not None and np.asarray(widths).shape != np.asarray(arrays["waveFrequency"]).shape:
                    widths=None
                summary = _spectral_state(arrays["waveFrequency"],arr[nearest_raw],masks["waveEnergyDensity"][nearest_raw],widths)
                summary.update(instrument_id="FRF:"+instrument,offset_seconds=float(times[nearest_raw]-target),
                               product=p["source"],tensor_pointer=name+"/variables/waveEnergyDensity/"+str(nearest_raw),
                               integral_qc="see_variable_qc_association; spectrum summary is diagnostic, not representative by default")
                published = float(arrays["waveHs"][nearest_raw]) if "waveHs" in arrays and masks["waveHs"][nearest_raw] else None
                summary["published_Hs_m"] = published
                summary["Hm0_minus_published_Hs_m"] = summary["Hm0_m"]-published if published is not None and summary["Hm0_m"] is not None else None
                summary["published_peak_band"] = {v:float(arrays[v][nearest_raw]) if v in arrays and masks[v][nearest_raw] else None
                                                   for v in ("waveTp","waveMeanDirectionPeakFrequency","wavePeakDirectionPeakFrequency","directionalPeakSpread")}
                summary["peak_band_caveat"] = "Published peak-frequency mean/mode and spread retained separately; all-frequency mean direction NOT assigned to Tp"
                peak = summary["peak_bin"]
                if peak is not None and "waveA1Value" in arrays and "waveB1Value" in arrays:
                    a1,b1 = arrays["waveA1Value"][nearest_raw,peak],arrays["waveB1Value"][nearest_raw,peak]
                    summary["peak_bin_directional_moments"]={"a1":float(a1) if np.isfinite(a1) else None,"b1":float(b1) if np.isfinite(b1) else None,
                                                               "direction_reconstructed":"not performed: moment-axis convention/estimator not inferred"}
                summaries.append(summary)
        _plots_product(base,name,family,loaded,target,nearest_raw,config.get('accepted_qc_flags',[1]))
    rows,associations,duplicates=_across_segments(rows,tensors,target,search_coverage or [])
    for row in rows:
        if row["variable"]=="waveEnergyDensity":
            tensor=tensors[row["tensor_pointer"].split('/')[0]]
            variables=tensor["variables"]
            j=int(row["tensor_pointer"].split('/')[-1])
            result=_spectral_state(variables["waveFrequency"]["raw_values"],variables["waveEnergyDensity"]["raw_values"][j],variables["waveEnergyDensity"]["valid_mask"][j],variables.get("waveFrequencyBandwidth",{}).get("raw_values"))
            row["spectral_status"]=result["status"]
            row["spectral_valid_bin_fraction"]=result.get("valid_bin_fraction")
    table(base/"OBSERVATIONS.csv",rows)
    table(base/"DISTANCES.csv",spatial)
    save_json(base/"TENSORS.json",tensors)
    save_json(base/"ASSOCIATIONS.json",associations)
    save_json(base/"SPECTRAL_SUMMARIES.json",summaries)
    table(base/"SPECTRAL_SUMMARIES.csv",[{k:v for k,v in s.items() if not isinstance(v,(dict,list))} for s in summaries])
    save_json(base/"DUPLICATE_SAMPLES.json",duplicates)
    save_json(base/"SEARCH_COVERAGE.json",search_coverage or [{"status":"search_coverage_not_provided","nearest_claim":"available samples only"}])
    save_json(base/"COMPLETENESS.json",completeness)
    save_json(base/"PROVENANCE_WARNINGS.json",warnings)
    save_json(base/"INVENTORY.json",inventory)
    save_json(base/"ACQUISITION.json",acquisition)
    save_json(base/"CONFIG.json",config)
    selected_positions={row["position_id"] for row in rows}
    _map(base,fp,roi,[row for row in spatial if row["position_id"] in selected_positions])
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
              "Search coverage: "+json.dumps(search_coverage or "not verified; available samples only"),"",
              "Spectral states (missing is not calm): "+json.dumps([{k:s.get(k) for k in ("instrument_id","product","status","Hm0_m","valid_bin_fraction")} for s in summaries]),"",
              "Duplicate timestamp diagnostics: "+json.dumps(duplicates),"",
              "Profiles/2D spectra, when present, are preserved in TENSORS.json with source definitions and masks. Ancillary meteorology/temperature only from selected products. NDBC/CDIP alias republication is not counted independently."]
    lines+=_operational_report(rows,spatial,summaries,inventory)
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
            manifest["artifacts"].append({"path":p.resolve().relative_to(Path.cwd().resolve()).as_posix(),"bytes":p.stat().st_size,"sha256":digest(p.read_bytes())})
    for p in sorted(Path("code/frf_client").glob("*.py")) + [Path("code/run_block32_frf_client.py"),Path("code/run_block30_frf_conditions.py"),Path("code/repository_paths.py"),Path("repository_paths.json")]:
        manifest["code_sources"].append({"path":str(p),"sha256":digest(p.read_bytes())})
    save_json(base/"MANIFEST.json",manifest)


def _operational_report(rows,spatial,summaries,inventory):
    positions={r['position_id']:r for r in spatial}
    names={'waveHs','waveTp','waveTm','waveTm1','waveTm2','waveMeanDirection','waveMeanDirectionPeakFrequency','wavePeakDirectionPeakFrequency','directionalPeakSpread','windSpeed','windDirection','windGust','currentSpeed','currentEast','currentNorth','currentUp','waterLevel','predictedWaterLevel','residualWaterLevel','gapGauge'}
    lines=['','## Operational reading guide','',
        '`representative_eligible` is ONLY implemented availability/QC/time eligibility, NOT proof of physical representativity of footprint or ROI.','',
        '### Original measurements and per-sample distances','',
        '| instrument | parameter | original value/profile | units | UTC | offset s | QC/status | footprint min m | ROI min m |',
        '|---|---|---|---|---|---:|---|---:|---:|']
    for r in rows:
        if r['role']!='nearest_context' or r['variable'] not in names:continue
        pos=positions[r['position_id']]
        value=r['value'] if r['value'] is not None else 'missing or profile: '+r['tensor_pointer']
        lines.append(f"|{r['instrument_id']}|{r['variable']}|{value}|{r['units']}|{r['sensor_time_utc']}|{r['offset_seconds']:.3f}|{r['qc_flag']}: {r['status']}|{pos['footprint_minimum_m']}|{pos['roi_minimum_m']}|")
    lines+=['','Nearest QC-eligible can be a different sample/gauge: OBSERVATIONS.csv references its own position_id in DISTANCES.csv. Previous/next/nearest selection remains in ASSOCIATIONS.json.','',
        '### Original height/depth/interval definitions','']
    seen=set()
    for r in rows:
        if r['role']!='nearest_context':continue
        key=(r['family'],r['instrument_id'],r['sensor_vertical_context'])
        if key in seen:continue
        seen.add(key)
        lines.append(f"- {r['instrument_id']} / {r['family']}: original vertical context {r['sensor_vertical_context']}; duration hint {r['observation_duration_seconds']} s; anchored interval {r['interval_start_utc']} to {r['interval_end_utc']}.")
    lines+=['','Sensor elevation is not automatically wind height above instantaneous water. Profile depth/elevation and depth-integrated currents are distinct; no surface/effective-wave-current substitution.','',
        '### Derived diagnostic spectral quantities','']
    for s in summaries:lines.append(f"- {s['instrument_id']}: {s['status']}; Hm0={s.get('Hm0_m')} m; Tp discrete-bin={s.get('Tp_bin_s')} s; Tm01={s.get('Tm01_s')} s; Tm02={s.get('Tm02_s')} s; bin widths={s.get('bin_width_origin')}; these do not replace published parameters.")
    surveys=[e for e in inventory if e.get('family')=='bathymetry']
    lines+=['','### Bathymetric references','',json.dumps(surveys,indent=2),'',
        'Filename dates/nominal bounding boxes do not prove measured survey coverage. Datum/method/unsupported layouts remain explicit. No depth inversion.']
    return lines


def _spectral_state(f,energy,valid,widths=None):
    try:return spectral_summary(f,energy,valid,widths)
    except ValueError:
        return {"status":"invalid_spectral_grid_or_widths","m0_m2":None,"Hm0_m":None,"Tm01_s":None,"Tm02_s":None,"Tp_bin_s":None,"peak_bin":None,"valid_mask":list(valid),"partial_integral":True}


def _across_segments(rows,tensors,target,coverage):
    """Choose across files without concatenating spectra or averaging duplicates."""
    grouped={}
    for row in rows:grouped.setdefault((row["family"],row["instrument_id"],row["variable"]),[]).append(row)
    result,associations,duplicates=[],[],[]
    # Examine ALL retrieved samples, including duplicate alternatives a local argmin did not select.
    sample_groups={}
    for name,tensor in tensors.items():
        variables=tensor["variables"];time=variables["time"]
        from .data import cf_times
        times=cf_times(time["raw_values"],time["attributes"]["units"])
        family=name.split('__')[0]
        for variable,v in variables.items():
            if not v["shape"] or v["shape"][0]!=len(times) or variable in ("time","waveFrequency","waveDirectionBins","depth") or variable.lower().startswith("qc"):continue
            for j,t in enumerate(times):
                key=(family,tensor["stable_identity"],variable,float(t))
                qcname=qc_variable(family,variable,variables)
                sample_groups.setdefault(key,[]).append({"product":tensor["source"],"original_sample_index":tensor["original_sample_indices"][j],"tensor_pointer":name+"/variables/"+variable+"/"+str(j),"value":v["raw_values"][j],"valid_mask":v["valid_mask"][j],"units":v["attributes"].get("units"),
                    "qc_flag":variables[qcname]["raw_values"][j] if qcname else None,
                    "sensor_id":variables['id']['raw_values'][j] if 'id' in variables and variables['id']['shape']==[len(times)] else None,
                    "spectral_frequency_grid":variables.get('waveFrequency',{}).get('raw_values') if variable in ('waveEnergyDensity','directionalWaveEnergyDensity','waveA1Value','waveB1Value','waveA2Value','waveB2Value') else None})
    conflict_keys=set()
    for key,samples in sample_groups.items():
        if len(samples)<2:continue
        # Masks/units are part of equality. QC flags are retained separately in tensors.
        same=len({json.dumps([s["value"],s["valid_mask"],s["units"],s['qc_flag'],s['sensor_id'],s['spectral_frequency_grid']],sort_keys=True) for s in samples})==1
        duplicates.append({"family":key[0],"instrument_id":key[1],"variable":key[2],"sensor_time_utc":iso(key[3]),"status":"consistent_duplicate" if same else "conflicting_duplicate","samples":samples,"policy":"no averaging; deterministic source/index tie-break; conflicts not representative"})
        if not same:conflict_keys.add(key)
    for key,group in grouped.items():
        chosen={}
        for role in ("nearest_context","previous_qc","next_qc","nearest_qc"):
            eligible=[r for r in group if r["role"]==role]
            if not eligible:continue
            metric=(lambda r: -utc(r["sensor_time_utc"]).timestamp()) if role=="previous_qc" else (lambda r:utc(r["sensor_time_utc"]).timestamp()) if role=="next_qc" else (lambda r:abs(r["offset_seconds"]))
            row=min(eligible,key=lambda r:(metric(r),r["product"],r["original_sample_index"]))
            if (*key,utc(row["sensor_time_utc"]).timestamp()) in conflict_keys:
                row["duplicate_status"]="conflicting_duplicate";row["representative_eligible"]=False
            else:row["duplicate_status"]="consistent_duplicate" if len(sample_groups.get((*key,utc(row["sensor_time_utc"]).timestamp()),[]))>1 else "unique"
            chosen[role]={"product":row["product"],"original_sample_index":row["original_sample_index"],"tensor_pointer":row["tensor_pointer"],"position_id":row["position_id"],"sensor_time_utc":row["sensor_time_utc"],"offset_seconds":row["offset_seconds"],"duplicate_status":row["duplicate_status"]}
            result.append(row)
        search=next((s for s in coverage if (s["family"],s["instrument_id"])==key[:2]),{"status":"search_coverage_not_provided"})
        associations.append({"family":key[0],"instrument_id":key[1],"variable":key[2],"selection":chosen,"search_coverage":search,"interpolation":"none","nearest_claim":"nearest within retrieved search segments, not absolute"})
    return result,associations,duplicates


def _plots_product(base,name,family,loaded,target,index,accepted_qc_flags=(1,)):
    arrays,masks,times = loaded["arrays"],loaded["masks"],loaded["times"]
    variable = {"waves":"waveHs","wind":"windSpeed","currents":"currentSpeed","water_level":"waterLevel"}[family]
    if variable in arrays:
        fig,ax=plt.subplots(figsize=(7,3))
        values = np.where(masks[variable],arrays[variable],np.nan)
        qcname=qc_variable(family,variable,arrays)
        quality=np.asarray(arrays[qcname]) if qcname else None
        good=qc_pass(quality,loaded['metadata']['attributes'].get(qcname,{}),accepted_qc_flags) if qcname else np.zeros(len(times),bool)
        if good.ndim>1:good=np.all(good.reshape(len(times),-1),axis=1)
        # Scatter only: no apparent continuity across long/unknown gaps.
        if qcname:
            known=mask_values(quality,loaded['metadata']['attributes'].get(qcname,{}))
            if known.ndim>1:known=np.all(known.reshape(len(times),-1),axis=1)
            ax.scatter((times[good]-target)/60,values[good],label='source QC accepted',s=18)
            failed=known&~good;unknown=~known
            ax.scatter((times[failed]-target)/60,values[failed],label='source QC not accepted',marker='x',s=20)
            ax.scatter((times[unknown]-target)/60,values[unknown],label='source QC unknown',marker='s',s=16)
        else:ax.scatter((times-target)/60,values,label='source QC unknown',marker='s',s=16)
        ax.axvline(0,color="red",label="SAR catalogue timestamp")
        ax.set(xlabel="sensor time minus SAR timestamp (min)",ylabel=variable,title=name+"; no interpolation")
        ax.legend();fig.tight_layout();fig.savefig(base/(name+"_time.png"),dpi=130);plt.close(fig)
    if family=="waves" and "waveEnergyDensity" in arrays and "waveFrequency" in arrays:
        fig,ax=plt.subplots(figsize=(6,3))
        ax.plot(arrays["waveFrequency"],np.where(masks["waveEnergyDensity"][index],arrays["waveEnergyDensity"][index],np.nan))
        state=_spectral_state(arrays["waveFrequency"],arrays["waveEnergyDensity"][index],masks["waveEnergyDensity"][index],arrays.get("waveFrequencyBandwidth"))
        ax.set(xlabel="frequency (Hz)",ylabel="spectral density (source units)",title=state["status"]+"; nearest context, QC separate")
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
        ax.set(xlabel="velocity (source units)",ylabel="depth/elevation (source datum)",title="AWAC profile\nnot assumed surface current")
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
    positions={}
    for r in spatial:
        point=json.loads(r['lon_lat_json'])
        if point is None:continue
        key=(r['instrument_id'],r.get('effective_sensor_id'),tuple(point))
        fpdist=r.get('footprint_minimum_m');roidist=r.get('roi_minimum_m')
        label=f"{r['instrument_id']} sensor={r.get('effective_sensor_id')} tile min={fpdist:.0f}m" if fpdist is not None else r['instrument_id']+' tile N/A'
        label+=f' ROI min={roidist:.0f}m' if roidist is not None else ' ROI N/A'
        positions[key]=(label,point)
    for name,position in positions.values():
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

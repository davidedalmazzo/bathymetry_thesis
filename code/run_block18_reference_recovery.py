"""Execute the strictly bounded Block18 NDBC per-bin recovery."""
from __future__ import annotations
from repository_paths import resolve_historical

import csv, hashlib, json, platform, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from umbra_sar.reference_recovery import (HTTPBudget, VARIABLES, fetch_limited,
    nearest_time_index, normalize_payload, parse_ascii_vector, parse_dds_dimensions, spectrum_metrics)

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'umbra/selezione_scene/Block18_reference_recovery'; B16=ROOT/'umbra/selezione_scene/Block16_scene_selection'
RAW=OUT/"payloads_raw"; NORM=OUT/"normalized"; RAW.mkdir(exist_ok=True); NORM.mkdir(exist_ok=True)

def dump(path,obj): path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def safe(x):
    if isinstance(x,(np.bool_,)): return bool(x)
    if isinstance(x,(np.integer,)): return int(x)
    if isinstance(x,(np.floating,)): return float(x)
    raise TypeError(type(x).__name__)
def write_csv(path,rows):
    if not rows: path.write_text("",encoding="utf-8"); return
    with path.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    cfg=json.loads((OUT/"BLOCK18_CONFIG.json").read_text())
    h=cfg["http_budget"]; budget=HTTPBudget(h["maximum_transactions_including_redirects_retries"],h["maximum_total_bytes"],h["maximum_response_bytes"],h["timeout_s"],h["maximum_retries"],h["chunk_bytes"])
    measured={r["acquisition_key"]:r for r in csv.DictReader((B16/"BLOCK16A_MEASURED_SPECTRA.csv").open(encoding="utf-8-sig"))}
    allrows={r["acquisition_key"]:r for r in csv.DictReader((B16/"BLOCK16A_ALL_CANDIDATES.csv").open(encoding="utf-8-sig")) if r["acquisition_key"] in measured}
    assert set(measured)=={a["acquisition_key"] for a in cfg["acquisitions"]} and len(measured)==4
    # Resolve historical payloads from the prior manifest by hash before network.
    prior_manifest=json.loads((B16/"BLOCK16A_DELIVERY_MANIFEST.json").read_text())
    wanted={a["historical_payload_sha256"] for a in cfg["acquisitions"]}; local_by_hash={}
    for rel,digest in prior_manifest.get("frozen_artifact_hashes",{}).items():
        path=resolve_historical(rel, ROOT)
        if digest in wanted and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest:
            local_by_hash[digest]=path
    base=cfg["sources"]["ndbc_aggregate"]
    recovered=[]; validations=[]; comparisons=[]; gates=[]; norm_rows=[]
    try:
        dds=fetch_limited(base+".dds",budget,purpose="aggregate_dimensions")
        das=fetch_limited(base+".das",budget,purpose="aggregate_attributes")
        times_raw=fetch_limited(base+".ascii?time",budget,purpose="aggregate_time_coordinate")
        (RAW/"42084w9999.dds").write_bytes(dds); (RAW/"42084w9999.das").write_bytes(das); (RAW/"42084w9999_time.ascii").write_bytes(times_raw)
        dims=parse_dds_dimensions(dds.decode("utf-8",errors="replace")); nfreq=dims["frequency"]
        epochs=parse_ascii_vector(times_raw.decode("utf-8",errors="replace"),"time")
        if len(epochs)!=dims["time"]: raise ValueError("time coordinate length differs from DDS")
        das_text=das.decode("utf-8",errors="replace")
        for target in cfg["acquisitions"]:
            key=target["acquisition_key"]; acquisition=datetime.fromisoformat(target["acquisition_utc"].replace("Z","+00:00")); epoch=acquisition.timestamp()
            index,observation_epoch=nearest_time_index(epochs,epoch); observation=datetime.fromtimestamp(observation_epoch,timezone.utc); offset=(observation-acquisition).total_seconds()
            clauses=["frequency"]+[f"{v}[{index}:1:{index}][0:1:{nfreq-1}][0:1:0][0:1:0]" for v in VARIABLES]
            url=base+".ascii?"+",".join(clauses)
            remote_payload=fetch_limited(url,budget,purpose="per_bin_spectrum_identity_check",acquisition_key=key)
            local_path=local_by_hash.get(target["historical_payload_sha256"])
            payload=local_path.read_bytes() if local_path else remote_payload
            stem=key.split(":",1)[1]; rawpath=RAW/f"{stem}_spectrum.ascii"; rawpath.write_bytes(payload)
            phash=hashlib.sha256(payload).hexdigest(); historical_hash=target["historical_payload_sha256"]
            remote_hash=hashlib.sha256(remote_payload).hexdigest()
            if local_path and phash==historical_hash and remote_hash==historical_hash: equivalence="local_original_found_and_remote_hash_identical"
            elif phash==historical_hash: equivalence="payload_remote_hash_identical"
            elif index==target["historical_index"] and nfreq==98: equivalence="serialization_or_remote_version_different"
            else: equivalence="current_coordinate_selected_payload_not_exact_historical_index"
            normalized=normalize_payload(payload.decode("utf-8",errors="replace"),das_text,observation_epoch_s=epochs[index],joint_band=tuple(cfg["validity"]["joint_band_hz"]))
            metrics=spectrum_metrics(normalized,long_max_hz=cfg["validity"]["long_energy_max_hz"])
            meta={"acquisition_key":key,"dataset":base,"station_id":target["station_id"],"current_index":index,"historical_index":target["historical_index"],"dimensions":dims,"observation_utc":observation.isoformat(),"observation_offset_s":offset,"source_url":url,"local_original_path":str(local_path.relative_to(ROOT)) if local_path else None,"payload_sha256":phash,"remote_payload_sha256":remote_hash,"historical_payload_sha256":historical_hash,"equivalence":equivalence,"attributes":normalized["attrs"],"band_width_source":normalized["band_width_source"]}
            dump(NORM/f"{stem}_metadata.json",meta)
            for i,f in enumerate(normalized["frequency_hz"]):
                row={"acquisition_key":key,"bin_index":i,"frequency_hz":f,"band_width_hz":normalized["band_width_hz"][i]}
                for v in VARIABLES:
                    row[v]=normalized["arrays"][v][i]; row[f"valid_{v}"]=normalized["masks"][v][i]
                row["valid_joint"]=normalized["joint_mask"][i]; norm_rows.append(row)
            density_fraction=float(np.mean(normalized["masks"]["spectral_wave_density"]))
            temporal=abs(offset)<=cfg["validity"]["maximum_observation_offset_s"]
            spatial=target["station_distance_km"]<=cfg["validity"]["maximum_station_distance_km"]
            joint=normalized["joint_band_energy_coverage"]
            admissible=temporal and spatial and joint>=cfg["validity"]["minimum_joint_valid_energy_fraction"]
            recovered.append(key)
            validations.append({"acquisition_key":key,"station_id":target["station_id"],"recovery_succeeded":True,"observation_utc":observation.isoformat(),"observation_offset_s":offset,"temporally_valid":temporal,"station_distance_km":target["station_distance_km"],"station_association":"historical_Block16A_station_metadata","spatially_valid":spatial,"density_bin_coverage":density_fraction,"joint_directional_energy_coverage_band_0p04_0p25":joint,"usable_for_screening":bool(temporal and spatial and density_fraction>0),"admissible_measured_reference":admissible,"directional_moments_not_unique_spectrum":True,"equivalence":equivalence})
            old=measured[key]
            mapping={"measured_hm0_m":"hm0_m","measured_peak_period_s":"peak_period_s","peak_frequency_hz":"peak_frequency_hz","measured_long_energy_fraction_f_le_0p1":"long_energy_fraction_f_le_0p1","measured_peak_direction_from_deg":"peak_alpha1_from_deg","measured_peak_alpha2_deg":"peak_alpha2_deg","measured_peak_r1":"peak_r1","measured_peak_r2":"peak_r2"}
            for oldname,newname in mapping.items():
                oval=float(old[oldname]) if old.get(oldname) not in (None,"") else None; nval=metrics[newname]
                comparisons.append({"acquisition_key":key,"metric":newname,"block16a_value":oval,"block18_value":nval,"difference":None if oval is None or nval is None else nval-oval,"cause":"band_width_sum_replaces_trapezoid" if newname in {"hm0_m","long_energy_fraction_f_le_0p1"} else "same_peak_parser_and_current_payload","payload_equivalence":equivalence})
            hist=allrows[key]; oldcat=hist["category"]; failures=json.loads(hist.get("gate_failures_json") or "[]")
            newcat=oldcat
            if not admissible and oldcat!="D": newcat="C"
            # A complete reference removes only a reference failure; every other frozen gate remains.
            nonreference=[x for x in failures if x not in {"reference_incomplete","reference_missing"}]
            if admissible and oldcat in {"C","E"} and not nonreference:
                newcat="A"
            gates.append({"acquisition_key":key,"historical_category":oldcat,"block17_status":"joint_per_bin_not_reproducible","block18_category":newcat,"category_changed":newcat!=oldcat,"reference_admissible":admissible,"historical_gate_failures":";".join(failures),"remaining_nonreference_failures":";".join(nonreference),"cphd_tx_time_span_s":hist.get("cphd_tx_time_span_s"),"sicd_processed_aperture_s":hist.get("sicd_processed_aperture_s"),"catalog_duration_s":hist.get("catalog_duration_s"),"nominal_observable_cycles":hist.get("observable_cycles"),"geometry_axial_difference_deg":hist.get("wave_range_axial_difference_deg"),"ocean_fraction":hist.get("ocean_fraction"),"roi_proxy_limit":"Natural_Earth_preliminary_not_SAR_verified","missing_sar_verifications":"delta_eff;interior_clearance_at_SAR_scale;lobe_separability;usable_intensity_ROI;SNR_coherence;full_Doppler_slow_time_mapping"})
            dump(NORM/f"{stem}_metrics.json",metrics)
    finally:
        write_csv(OUT/"BLOCK18_REQUEST_LOG.csv",budget.log)
    write_csv(OUT/"BLOCK18_NORMALIZED_BINS.csv",norm_rows); write_csv(OUT/"BLOCK18_REFERENCE_VALIDATION.csv",validations); write_csv(OUT/"BLOCK18_METRIC_COMPARISON.csv",comparisons); write_csv(OUT/"BLOCK18_CANDIDATE_GATE_COMPARISON.csv",gates)
    summary={"block":"18","status":"CHECKPOINT_18","targets":4,"references_recovered":len(recovered),"references_admissible":sum(x["admissible_measured_reference"] for x in validations),"payload_equivalence_counts":dict(__import__('collections').Counter(x["equivalence"] for x in validations)),"category_changes":sum(x["category_changed"] for x in gates),"categories":{x["acquisition_key"]:x["block18_category"] for x in gates},"budget":{"transactions":budget.transactions,"bytes":budget.total_bytes,"maximum_transactions":budget.max_transactions,"maximum_bytes":budget.max_total_bytes},"python":sys.version,"platform":platform.platform(),"limitations":["directional moments do not uniquely reconstruct a directional spectrum","space-time proximity does not prove local hydrodynamic representativeness","band widths reconstructed from frequency centres because no explicit bounds variable is exposed","no SAR verification performed"]}
    dump(OUT/"BLOCK18_SUMMARY.json",summary); print(json.dumps(summary,indent=2,default=safe))

if __name__=="__main__": main()

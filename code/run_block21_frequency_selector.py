"""Block21 offline-first Umbra selector for phase-evolution frequency validation.

No SAR object is downloaded or read.  The remote phase is deliberately separate
and consumes only the immutable queue emitted by the offline phase.
"""
from __future__ import annotations

import argparse, csv, hashlib, io, json, math, os, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PlotPolygon
import numpy as np
from shapely import STRtree
from shapely.geometry import Point, Polygon, box, shape
from shapely.ops import transform, unary_union

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"code"))
from run_block16a_scene_selection import read_esri_polygon_shapefile
from umbra_sar.frequency_validation_selector import as_bool, classify_candidate, pareto_front, temporal_scenarios
from umbra_sar.scene_selection import haversine_km
from umbra_sar.frequency_validation_selector import dominant_half_power_band
from umbra_sar.reference_recovery import (HTTPBudget, VARIABLES, fetch_limited,
    nearest_time_index, normalize_payload, parse_ascii_vector, parse_dds_dimensions)
from umbra_sar.selector_consolidation import ndbc_archive_plan

BASE=ROOT/'umbra/selezione_scene/Block21_frequency_validation_selector'
SNAP=ROOT/'umbra/selezione_scene/Block16_scene_selection/catalog_snapshots/20260913T231747Z/normalized_acquisitions.csv'
ENRICHED=ROOT/'umbra/selezione_scene/Block16_scene_selection/BLOCK16A_ALL_CANDIDATES.csv'
LAND=ROOT/'umbra/validazione/Block8_validation/catalog_raw/ne_10m_land/ne_10m_land.shp'
STATIONS=ROOT/'umbra/selezione_scene/Block16_scene_selection/cache/ndbc_stationmetadata.xml'
CONFIG=BASE/"BLOCK21_CONFIG.json"; CONFIG_HASH=BASE/"BLOCK21_CONFIG.sha256"
VANDENBERG="9d8283d8-550d-4435-899f-5483d2c1abcc"
R=6371008.8

def read_csv(path):
    with path.open(encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))
def atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name(path.name+f".tmp-{os.getpid()}")
    tmp.write_bytes(payload); os.replace(tmp,path)
def write_csv(path,rows,fields=None):
    rows=list(rows); fields=fields or list(dict.fromkeys(k for r in rows for k in r)) or ["status"]
    s=io.StringIO(newline=""); w=csv.DictWriter(s,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    atomic(path,s.getvalue().encode())
def write_json(path,value): atomic(path,(json.dumps(value,indent=2,sort_keys=True)+"\n").encode())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def number(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None
def load_config():
    expected=CONFIG_HASH.read_text().split()[0].lower(); actual=sha(CONFIG)
    if actual!=expected: raise RuntimeError(f"config hash mismatch {actual} != {expected}")
    return json.loads(CONFIG.read_text()),actual

def local_functions(lon0,lat0):
    c=max(math.cos(math.radians(lat0)),1e-6)
    def forward(x,y,z=None): return (R*c*math.radians(x-lon0),R*math.radians(y-lat0))
    def inverse(x,y,z=None): return (lon0+math.degrees(x/(R*c)),lat0+math.degrees(y/R))
    return forward,inverse

def repair_geometry(text):
    try:
        g=shape(json.loads(text)); g=transform(lambda x,y,z=None:(x,y),g)
        if not g.is_valid: g=g.buffer(0)
        return g if not g.is_empty else None
    except Exception: return None

def internal_roi(footprint,land_tree,land_shapes,cfg):
    p=footprint.representative_point(); lon0,lat0=p.x,p.y; fwd,inv=local_functions(lon0,lat0)
    fp=transform(fwd,footprint)
    indices=land_tree.query(footprint)
    local=[transform(fwd,land_shapes[int(i)].intersection(footprint)) for i in indices
           if land_shapes[int(i)].intersects(footprint)]
    land=unary_union(local) if local else Polygon()
    water=fp.difference(land); area=fp.area; ocean_fraction=water.area/area if area else 0
    if water.is_empty or not all(math.isfinite(v) for v in water.bounds):
        return {"ocean_fraction":ocean_fraction,"footprint_area_km2":area/1e6,
                "coast_distance_status":"empty_or_nonfinite_water_geometry"}
    minx,miny,maxx,maxy=water.bounds; n=int(cfg["roi"]["grid_points_per_axis"])
    points=[]
    for x in np.linspace(minx,maxx,n):
        for y in np.linspace(miny,maxy,n): points.append(Point(float(x),float(y)))
    points.append(water.representative_point())
    best=None
    for size in cfg["roi"]["square_sizes_m"]:
        candidates=[]
        for q in points:
            sq=box(q.x-size/2,q.y-size/2,q.x+size/2,q.y+size/2)
            if water.covers(sq):
                coast=q.distance(land.boundary) if not land.is_empty else None
                edge=q.distance(fp.boundary)
                candidates.append((min(coast if coast is not None else math.inf,edge),edge,coast,q,sq))
        if candidates:
            _,edge,coast,q,sq=max(candidates,key=lambda x:(x[0],x[1],-abs(x[3].x),-abs(x[3].y)))
            ll=transform(inv,q); poly=transform(inv,sq)
            best={"roi_center_lon":ll.x,"roi_center_lat":ll.y,"roi_square_size_m":size,
                  "roi_area_km2":size*size/1e6,"footprint_edge_distance_m":edge,
                  "coast_distance_m":coast,"coast_distance_status":"local_exact" if coast is not None else "lower_bound_beyond_footprint",
                  "roi_polygon_json":json.dumps(poly.__geo_interface__,separators=(",",":")),
                  "ocean_fraction":ocean_fraction,"footprint_area_km2":area/1e6}
            break
    return best or {"ocean_fraction":ocean_fraction,"footprint_area_km2":area/1e6,
                    "coast_distance_status":"no_fully_water_square_250m"}

def parse_stations(path):
    root=ET.parse(path).getroot(); out=[]
    for s in root.iter("station"):
        for h in s.findall("history"):
            lat=number(h.attrib.get("lat")); lon=number(h.attrib.get("lng"))
            if lat is None or lon is None: continue
            out.append({"station_id":s.attrib.get("id",""),"station_name":s.attrib.get("name",""),
                        "station_owner":s.attrib.get("owner",""),"station_program":s.attrib.get("pgm",""),
                        "station_lat":lat,"station_lon":lon,"active_start":h.attrib.get("start",""),
                        "active_stop":h.attrib.get("stop","")})
    return out

def nearest_stations(lon,lat,stations,limit=50,date_utc=""):
    rows=[]
    for s in stations:
        day=str(date_utc)[:10]
        if day and ((s["active_start"] and day<s["active_start"]) or (s["active_stop"] and day>s["active_stop"])): continue
        d=haversine_km(lat,lon,s["station_lat"],s["station_lon"])
        if d<=limit: rows.append({**s,"station_distance_km":d})
    return sorted(rows,key=lambda x:(x["station_distance_km"],x["station_id"]))

def offline():
    cfg,cfg_hash=load_config(); BASE.mkdir(exist_ok=True); (BASE/"figures").mkdir(exist_ok=True)
    source=read_csv(SNAP); enriched={r["acquisition_key"]:r for r in read_csv(ENRICHED)}
    land_shapes=read_esri_polygon_shapefile(LAND); tree=STRtree(land_shapes); stations=parse_stations(STATIONS)
    all_rows=[]; rois=[]; refs=[]; temporal=[]
    for i,row in enumerate(source):
        geom=repair_geometry(row.get("geometry_json","")); roi={}
        if geom is not None: roi=internal_roi(geom,tree,land_shapes,cfg)
        has_complex=as_bool(row.get("has_sicd")) or as_bool(row.get("has_cphd"))
        fatal=(row.get("collect_id")==VANDENBERG or row.get("instrument_mode")!="SPOTLIGHT" or
               (number(row.get("platform_count")) or 1)>1 or as_bool(row.get("is_multistatic")))
        near=nearest_stations(roi.get("roi_center_lon"),roi.get("roi_center_lat"),stations,date_utc=row.get("datetime_utc","")) if roi.get("roi_center_lon") is not None else []
        # NDBC five-digit station identifiers are the deterministic preliminary
        # wave-product queue. Availability is still verified remotely; this is
        # not a claim that every such station exposes directional spectra.
        wave_near=[s for s in near if re.fullmatch(r"\d{5}",s["station_id"])]
        old=enriched.get(row["acquisition_key"],{}); measured=as_bool(old.get("spectral_density_available")) and number(old.get("observation_offset_s")) is not None and abs(number(old.get("observation_offset_s")))<=cfg["reference"]["maximum_offset_s"]
        model=number(old.get("model_peak_period_s")) is not None
        label=classify_candidate(fatal=fatal,geometry_known=geom is not None,internal_roi="roi_square_size_m" in roi,
                                 has_complex=has_complex,measured_admissible=measured,
                                 station_query_possible=bool(wave_near),model_available=model)
        reasons=[]
        if row.get("collect_id")==VANDENBERG: reasons.append("development_scene_excluded")
        if not has_complex: reasons.append("no_SICD_or_CPHD")
        if geom is None: reasons.append("geometry_unknown")
        if geom is not None and "roi_square_size_m" not in roi: reasons.append("no_250m_fully_water_square")
        n=wave_near[0] if wave_near else {}
        merged={**row,**roi,"has_complex_path":has_complex,"nearest_station_id":n.get("station_id",""),
                "nearest_station_distance_km":n.get("station_distance_km",""),"stations_within_50km_count":len(wave_near),
                "stations_within_50km_json":json.dumps(wave_near,separators=(",",":")),
                "measured_reference_reused":measured,"model_reference_available":model,
                "primary_classification":label,"exclusion_reasons_json":json.dumps(reasons),
                "selector_order":"reference>roi_geometry>complex_path>joint_feasibility>access_cost",
                "duration_is_gate":False,"period_is_gate":False,"minimum_ocean_fraction_gate":False}
        all_rows.append(merged); rois.append({k:merged.get(k,"") for k in ("acquisition_key","collect_id","datetime_utc","geometry_valid","ocean_fraction","footprint_area_km2","roi_center_lon","roi_center_lat","roi_square_size_m","roi_area_km2","footprint_edge_distance_m","coast_distance_m","coast_distance_status","roi_polygon_json")})
        refs.append({"acquisition_key":row["acquisition_key"],"status":"reused_Block18" if measured else ("not_queried" if near else "no_station_within_50km"),
                     "station_id":old.get("station_id") if measured else n.get("station_id",""),"station_distance_km":old.get("station_distance_km") if measured else n.get("station_distance_km",""),
                     "observation_offset_s":old.get("observation_offset_s","") if measured else "","spectral_density_available":old.get("spectral_density_available","") if measured else "",
                     "alpha1_available":old.get("alpha1_available","") if measured else "","payload_sha256":old.get("payload_sha256","") if measured else "","source_url":old.get("source_url","") if measured else ""})
        period=number(old.get("measured_peak_period_s")) or number(old.get("model_peak_period_s"))
        for scenario in temporal_scenarios(row.get("catalog_duration_s"),cfg["look_durations_s"],cfg["sliding_step_s"],period):
            temporal.append({"acquisition_key":row["acquisition_key"],"duration_source":"catalog_start_end","catalog_duration_s":row.get("catalog_duration_s"),"period_source":"measured" if number(old.get("measured_peak_period_s")) else ("model" if period else "unknown"),**scenario})
        if (i+1)%1000==0: print(f"geometry {i+1}/{len(source)}",flush=True)
    # Pareto descriptors do not collapse into an opaque score.
    eligible=[r for r in all_rows if r["primary_classification"] not in {"EXCLUDED","NOT_EVALUABLE"}]
    for r,p in zip(eligible,pareto_front(eligible,("roi_square_size_m","stations_within_50km_count"))): r["pareto_front"]=p
    # Freeze diversified remote queue before any network request.
    pool=[r for r in all_rows if r["primary_classification"]=="CONDITIONAL_REFERENCE_CHECK"]
    pool.sort(key=lambda r:(number(r.get("nearest_station_distance_km")) or math.inf,-(number(r.get("roi_square_size_m")) or 0),
                            0 if as_bool(r.get("has_sicd")) and as_bool(r.get("has_cphd")) else 1,
                            (number(r.get("sicd_size_bytes")) or math.inf)+(number(r.get("cphd_size_bytes")) or math.inf),r["acquisition_key"]))
    queue=[]; per={}
    for r in pool:
        sid=r["nearest_station_id"]
        if per.get(sid,0)>=cfg["reference"]["maximum_per_station"]: continue
        queue.append({"queue_rank":len(queue)+1,"acquisition_key":r["acquisition_key"],"collect_id":r["collect_id"],"datetime_utc":r["datetime_utc"],"station_id":sid,"station_distance_km":r["nearest_station_distance_km"],"status":"pending","attempts":0})
        per[sid]=per.get(sid,0)+1
        if len(queue)>=cfg["reference"]["maximum_remote_queue"]: break
    write_csv(BASE/"BLOCK21_ALL_CANDIDATES.csv",all_rows); write_csv(BASE/"BLOCK21_ROI_METRICS.csv",rois)
    write_csv(BASE/"BLOCK21_REFERENCE_AVAILABILITY.csv",refs); write_csv(BASE/"BLOCK21_TEMPORAL_SCENARIOS.csv",temporal)
    write_csv(BASE/"BLOCK21_REMOTE_QUEUE.csv",queue); atomic(BASE/"BLOCK21_REMOTE_QUEUE.sha256",(sha(BASE/"BLOCK21_REMOTE_QUEUE.csv")+"  BLOCK21_REMOTE_QUEUE.csv\n").encode())
    variants=ROOT/'umbra/selezione_scene/Block16_scene_selection/BLOCK16A_PROCESSING_VARIANTS.csv'
    historical=[{"selector":"Block8","role":"historical_not_input","primary_bias":"long_dwell/coastal validation shortlist"},{"selector":"Block16A","role":"metadata_enrichment_reused","primary_bias":"dwell/cycles/sea/long-energy gates removed in Block21"},{"selector":"Block17","role":"historical_not_input","primary_bias":"nearshore/bathymetry"},{"selector":"Block18","role":"four measured payloads reused","primary_bias":"per-bin recovery"},{"selector":"Block19","role":"excluded_as_input","primary_bias":"manual exploratory bathymetry screen"},{"selector":"Block20","role":"not_audited_not_input","primary_bias":"explicitly outside task"}]
    write_csv(BASE/"BLOCK21_HISTORICAL_COMPARISON.csv",historical)
    write_json(BASE/"BLOCK21_INPUT_INVENTORY.json",{"config_sha256":cfg_hash,"snapshot":{"path":str(SNAP.relative_to(ROOT)),"sha256":sha(SNAP),"rows":len(source)},"enrichment":{"path":str(ENRICHED.relative_to(ROOT)),"sha256":sha(ENRICHED)},"processing_variants":{"path":str(variants.relative_to(ROOT)),"sha256":sha(variants)},"land_mask":{"path":str(LAND.relative_to(ROOT)),"sha256":sha(LAND),"role":"preliminary coarse land mask"},"station_metadata":{"path":str(STATIONS.relative_to(ROOT)),"sha256":sha(STATIONS)},"Block19_used":False,"Block20_audited_or_used":False})
    summary={x:sum(r["primary_classification"]==x for r in all_rows) for x in ("MEASURED_PRODUCT_CHECK","CONDITIONAL_REFERENCE_CHECK","MODEL_EXPLORATORY","EXCLUDED","NOT_EVALUABLE")}
    print(json.dumps({"rows":len(all_rows),"roi_rows":sum("roi_square_size_m" in r for r in all_rows),"temporal_scenarios":len(temporal),"queue":len(queue),"classes":summary},indent=2))

def remote():
    cfg,_=load_config(); queue_path=BASE/"BLOCK21_REMOTE_QUEUE.csv"
    frozen=(BASE/"BLOCK21_REMOTE_QUEUE.sha256").read_text().split()[0]
    if sha(queue_path)!=frozen: raise RuntimeError("remote queue hash mismatch")
    queue=read_csv(queue_path); refs={r["acquisition_key"]:r for r in read_csv(BASE/"BLOCK21_REFERENCE_AVAILABILITY.csv")}
    h=cfg["remote_budget"]; budget=HTTPBudget(h["maximum_transactions"],h["maximum_total_bytes"],h["maximum_response_bytes"],h["timeout_s"],h["maximum_retries"],h["chunk_bytes"])
    raw=BASE/"reference_payloads_raw"; normdir=BASE/"reference_normalized"; raw.mkdir(exist_ok=True); normdir.mkdir(exist_ok=True)
    metadata_cache={}; bins=[]
    for q in queue:
        key=q["acquisition_key"]; station=q["station_id"]; year=int(q["datetime_utc"][:4]); target=datetime.fromisoformat(q["datetime_utc"].replace("Z","+00:00")).timestamp()
        q["attempts"]=0; selected=None; errors=[]
        for base in ndbc_archive_plan(station,year)["candidates"]:
            q["attempts"]=int(q["attempts"])+1
            try:
                if base not in metadata_cache:
                    dds=fetch_limited(base+".dds",budget,purpose="dimensions",acquisition_key=key)
                    das=fetch_limited(base+".das",budget,purpose="attributes",acquisition_key=key)
                    traw=fetch_limited(base+".ascii?time",budget,purpose="time_coordinate",acquisition_key=key)
                    dims=parse_dds_dimensions(dds.decode(errors="replace")); epochs=parse_ascii_vector(traw.decode(errors="replace"),"time")
                    metadata_cache[base]=(dims,epochs,das)
                    stem=f"{station}_{'9999' if '9999.nc' in base else year}"
                    atomic(raw/(stem+".dds"),dds); atomic(raw/(stem+".das"),das); atomic(raw/(stem+"_time.ascii"),traw)
                dims,epochs,das=metadata_cache[base]; idx,obs=nearest_time_index(epochs,target)
                clauses=["frequency"]+[f"{v}[{idx}:1:{idx}][0:1:{dims['frequency']-1}][0:1:0][0:1:0]" for v in VARIABLES]
                url=base+".ascii?"+",".join(clauses); payload=fetch_limited(url,budget,purpose="per_bin_spectrum",acquisition_key=key)
                normalized=normalize_payload(payload.decode(errors="replace"),das.decode(errors="replace"),observation_epoch_s=obs,joint_band=tuple(cfg["reference"]["joint_band_hz"]))
                metrics=dominant_half_power_band(normalized["frequency_hz"],normalized["arrays"]["spectral_wave_density"],normalized["arrays"]["mean_wave_dir"],normalized["arrays"]["wave_spectrum_r1"],normalized["joint_mask"])
                offset=obs-target; admissible=abs(offset)<=cfg["reference"]["maximum_offset_s"] and normalized["joint_band_energy_coverage"]>=cfg["reference"]["minimum_joint_energy_coverage"]
                stem=key.split(":",1)[1]; atomic(raw/(stem+"_spectrum.ascii"),payload)
                write_json(normdir/(stem+"_metrics.json"),{**metrics,"dataset":base,"station_id":station,"observation_epoch_s":obs,"observation_offset_s":offset,"joint_energy_coverage":normalized["joint_band_energy_coverage"],"admissible":admissible,"payload_sha256":hashlib.sha256(payload).hexdigest()})
                for j,f in enumerate(normalized["frequency_hz"]):
                    bins.append({"acquisition_key":key,"station_id":station,"bin_index":j,"frequency_hz":f,"band_width_hz":normalized["band_width_hz"][j],**{v:normalized["arrays"][v][j] for v in VARIABLES},"valid_joint":normalized["joint_mask"][j]})
                selected={"status":"recovered_admissible" if admissible else "recovered_not_admissible","station_id":station,"station_distance_km":q["station_distance_km"],"observation_offset_s":offset,"spectral_density_available":True,"alpha1_available":True,"joint_energy_coverage":normalized["joint_band_energy_coverage"],"source_url":url,"payload_sha256":hashlib.sha256(payload).hexdigest(),**metrics}
                break
            except Exception as exc: errors.append(f"{base}: {exc!r}")
        if selected: refs[key]={"acquisition_key":key,**selected}; q["status"]=selected["status"]
        else: refs[key]={"acquisition_key":key,"status":"archive_no_data_or_retrieval_failure","station_id":station,"station_distance_km":q["station_distance_km"],"errors_json":json.dumps(errors)}; q["status"]="failed"
        print(f"remote {q['queue_rank']}/{len(queue)} {station} {q['status']}",flush=True)
    write_csv(BASE/"BLOCK21_REFERENCE_AVAILABILITY.csv",refs.values()); write_csv(BASE/"BLOCK21_REFERENCE_BINS.csv",bins)
    write_csv(BASE/"BLOCK21_REQUEST_LOG.csv",budget.log); write_csv(BASE/"BLOCK21_REMOTE_QUEUE_STATUS.csv",queue)
    write_json(BASE/"BLOCK21_REMOTE_SUMMARY.json",{"transactions":budget.transactions,"bytes":budget.total_bytes,"maximum_transactions":budget.max_transactions,"maximum_bytes":budget.max_total_bytes,"recovered":sum(q["status"].startswith("recovered") for q in queue),"admissible":sum(q["status"]=="recovered_admissible" for q in queue),"failed":sum(q["status"]=="failed" for q in queue),"queue_sha256":frozen})

def finalize():
    cfg,cfg_hash=load_config(); candidates=read_csv(BASE/"BLOCK21_ALL_CANDIDATES.csv")
    refs={r["acquisition_key"]:r for r in read_csv(BASE/"BLOCK21_REFERENCE_AVAILABILITY.csv")}
    old={r["acquisition_key"]:r for r in read_csv(ENRICHED)}; scenarios=read_csv(BASE/"BLOCK21_TEMPORAL_SCENARIOS.csv")
    byscenario={}
    for s in scenarios: byscenario.setdefault(s["acquisition_key"],[]).append(s)
    updated=[]
    for r in candidates:
        ref=refs.get(r["acquisition_key"],{}); prior=old.get(r["acquisition_key"],{})
        admissible=ref.get("status") in {"reused_Block18","recovered_admissible"}
        if admissible and r["primary_classification"] not in {"EXCLUDED","NOT_EVALUABLE"}: r["primary_classification"]="MEASURED_PRODUCT_CHECK"
        period=number(ref.get("peak_period_s")) or number(prior.get("measured_peak_period_s"))
        direction=number(ref.get("propagation_to_deg")) or number(prior.get("measured_peak_propagation_to_deg"))
        ss=byscenario.get(r["acquisition_key"],[]); maxcent=max([int(x["sliding_center_count"]) for x in ss],default=0)
        r.update(reference_status=ref.get("status","not_queried"),reference_station_id=ref.get("station_id",""),
                 reference_peak_period_s=period or "",reference_propagation_to_deg=direction if direction is not None else "",
                 maximum_sliding_center_count=maxcent,
                 frequency_validation_readiness=("READY_FOR_SAR_METADATA_PREFLIGHT" if admissible and maxcent>=2 else ("LIMITED_TEMPORAL_SUPPORT" if admissible else "NO_ADMISSIBLE_MEASURED_REFERENCE")),
                 bathymetry_readiness="DESCRIPTIVE_ONLY_NOT_RANKED")
        updated.append(r)
    write_csv(BASE/"BLOCK21_ALL_CANDIDATES.csv",updated)
    measured=[r for r in updated if r["primary_classification"]=="MEASURED_PRODUCT_CHECK"]
    measured.sort(key=lambda r:(0 if r["frequency_validation_readiness"].startswith("READY") else 1,
                                number(refs[r["acquisition_key"]].get("station_distance_km")) or math.inf,
                                -(number(r.get("roi_square_size_m")) or 0),
                                -(number(r.get("maximum_sliding_center_count")) or 0),
                                0 if as_bool(r.get("has_sicd")) and as_bool(r.get("has_cphd")) else 1,
                                (number(r.get("sicd_size_bytes")) or math.inf)+(number(r.get("cphd_size_bytes")) or math.inf),r["acquisition_key"]))
    shortlist=[]
    for rank,r in enumerate(measured[:5],1):
        ref=refs[r["acquisition_key"]]; row={"rank":rank,"acquisition_key":r["acquisition_key"],"collect_id":r["collect_id"],"collect_name":r["collect_name"],"datetime_utc":r["datetime_utc"],"catalog_duration_s":r["catalog_duration_s"],"has_sicd":r["has_sicd"],"has_cphd":r["has_cphd"],"sicd_size_bytes":r["sicd_size_bytes"],"cphd_size_bytes":r["cphd_size_bytes"],"roi_square_size_m":r.get("roi_square_size_m",""),"footprint_edge_distance_m":r.get("footprint_edge_distance_m",""),"coast_distance_m":r.get("coast_distance_m",""),"coast_distance_status":r.get("coast_distance_status",""),"station_id":ref.get("station_id",""),"station_distance_km":ref.get("station_distance_km",""),"reference_status":ref.get("status",""),"observation_offset_s":ref.get("observation_offset_s",""),"peak_period_s":r.get("reference_peak_period_s",""),"propagation_to_deg":r.get("reference_propagation_to_deg",""),"joint_energy_coverage":ref.get("joint_energy_coverage",prior.get("joint_directional_energy_coverage_band_0p04_0p25","")),"maximum_sliding_center_count":r["maximum_sliding_center_count"],"frequency_validation_readiness":r["frequency_validation_readiness"],"ordering_basis":"measured reference; internal ROI; temporal descriptor; dual complex path; access cost","bathymetry_role":"descriptive only"}
        shortlist.append(row)
        # Candidate map: footprint, deterministic internal square, reference station.
        geom=repair_geometry(r["geometry_json"]); rp=shape(json.loads(r["roi_polygon_json"])); stations=json.loads(r.get("stations_within_50km_json") or "[]"); st=next((x for x in stations if x["station_id"]==ref.get("station_id")),None)
        fig,ax=plt.subplots(figsize=(6,5));
        for poly in ([geom] if geom.geom_type=="Polygon" else geom.geoms): ax.add_patch(PlotPolygon(np.asarray(poly.exterior.coords)[:,:2],fill=False,color="navy",label="SAR footprint" if not ax.patches else None))
        ax.add_patch(PlotPolygon(np.asarray(rp.exterior.coords)[:,:2],facecolor="cyan",alpha=.35,edgecolor="teal",label="deterministic water ROI"))
        if st: ax.scatter(st["station_lon"],st["station_lat"],marker="*",s=130,color="crimson",label=f"NDBC {st['station_id']}")
        ax.set_aspect("equal",adjustable="datalim"); ax.grid(alpha=.25); ax.legend(loc="best"); ax.set_xlabel("longitude [deg]"); ax.set_ylabel("latitude [deg]"); ax.set_title(f"Block21 candidate {rank}: {r['collect_name']}")
        fig.tight_layout(); fig.savefig(BASE/"figures"/f"candidate_{rank}_{r['collect_id']}.png",dpi=160); plt.close(fig)
        card=f"# Candidate {rank} — {r['collect_name']}\n\n- Collect: `{r['collect_id']}` at {r['datetime_utc']}\n- Complex path: SICD={r['has_sicd']}, CPHD={r['has_cphd']}; catalog duration {r['catalog_duration_s']} s (descriptor, not gate).\n- Internal-water ROI: {r.get('roi_square_size_m')} m square; edge clearance {float(r.get('footprint_edge_distance_m') or 0):.1f} m; coast status `{r.get('coast_distance_status')}`.\n- Measured reference: NDBC `{ref.get('station_id')}`, {float(ref.get('station_distance_km') or 0):.2f} km, offset {float(ref.get('observation_offset_s') or 0):.0f} s.\n- Dominant same-band period: {float(r.get('reference_peak_period_s') or 0):.2f} s; propagation-to direction: {r.get('reference_propagation_to_deg') or 'unknown'} deg.\n- Frequency readiness: **{r['frequency_validation_readiness']}**. Bathymetry is not a selection gate.\n\n![map](figures/candidate_{rank}_{r['collect_id']}.png)\n"
        atomic(BASE/f"BLOCK21_CANDIDATE_{rank}.md",card.encode())
    write_csv(BASE/"BLOCK21_SHORTLIST.csv",shortlist)
    source_variants=ROOT/'umbra/selezione_scene/Block16_scene_selection/BLOCK16A_PROCESSING_VARIANTS.csv'
    keys={r["acquisition_key"] for r in shortlist}; vr=[x for x in read_csv(source_variants) if x.get("acquisition_key") in keys]
    write_csv(BASE/"BLOCK21_PROCESSING_VARIANTS.csv",vr)
    counts={label:sum(r["primary_classification"]==label for r in updated) for label in cfg["labels"]}
    write_json(BASE/"BLOCK21_SUMMARY.json",{"block":21,"status":"CHECKPOINT_21","catalog_rows":len(updated),"internal_water_rois":sum(bool(r.get("roi_square_size_m")) for r in updated),"classifications":counts,"measured_references":len(measured),"shortlist_count":len(shortlist),"top_candidate":shortlist[0] if shortlist else None,"config_sha256":cfg_hash,"remote_summary":json.loads((BASE/"BLOCK21_REMOTE_SUMMARY.json").read_text()),"prohibitions_observed":{"sar_downloaded_or_read":False,"Block19_used_as_input":False,"Block20_audited_or_used":False,"dwell_or_period_hard_gate":False,"bathymetry_gate":False}})
    artifacts=[]
    for path in sorted(p for p in BASE.rglob("*") if p.is_file() and p.name!="BLOCK21_DELIVERY_MANIFEST.json"):
        artifacts.append({"path":str(path.relative_to(ROOT)).replace("\\","/"),"bytes":path.stat().st_size,"sha256":sha(path)})
    write_json(BASE/"BLOCK21_DELIVERY_MANIFEST.json",{"block":21,"created_utc":datetime.now(timezone.utc).isoformat(),"artifacts":artifacts,"artifact_count":len(artifacts),"config_sha256":cfg_hash,"remote_queue_sha256":sha(BASE/"BLOCK21_REMOTE_QUEUE.csv")})
    print(json.dumps({"measured":len(measured),"shortlist":[(x["rank"],x["collect_name"],x["station_id"],x["peak_period_s"]) for x in shortlist],"counts":counts},indent=2))

def main():
    p=argparse.ArgumentParser(); p.add_argument("--phase",choices=["offline","remote","finalize"],default="offline"); args=p.parse_args(); {"offline":offline,"remote":remote,"finalize":finalize}[args.phase]()
if __name__=="__main__": main()

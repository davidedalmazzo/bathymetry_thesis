"""Block22 geographic/visual audit and bounded candidate-1 metadata preflight."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,math,os,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon,Rectangle
import numpy as np
from PIL import Image
from shapely import STRtree
from shapely.geometry import Point,box,shape
from shapely.ops import transform,unary_union

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"code"))
from run_block16a_scene_selection import read_esri_polygon_shapefile,sicd_metadata_from_bytes
from umbra_sar.geographic_preflight import geographic_metrics,local_projection,scale_bar_length,affine_pixel_to_lonlat,validate_partial_response
from umbra_sar.reference_recovery import HTTPBudget,fetch_limited

BASE=ROOT/'umbra/selezione_scene/Block22_geographic_visual_preflight'; B21=ROOT/'umbra/selezione_scene/Block21_frequency_validation_selector'
LAND=ROOT/'umbra/validazione/Block8_validation/catalog_raw/ne_10m_land/ne_10m_land.shp'
CFG=BASE/"BLOCK22_CONFIG.json"; CFGHASH=BASE/"BLOCK22_CONFIG.sha256"

def rows(path):
 with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_name(path.name+f".tmp-{os.getpid()}"); tmp.write_bytes(data);os.replace(tmp,path)
def dump(path,obj):atomic(path,(json.dumps(obj,indent=2,sort_keys=True)+"\n").encode())
def table(path,data):
 data=list(data); f=list(dict.fromkeys(k for r in data for k in r)) if data else ["status"]; s=io.StringIO(newline="");w=csv.DictWriter(s,fieldnames=f);w.writeheader();w.writerows(data);atomic(path,s.getvalue().encode())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def config():
 c=json.loads(CFG.read_text()); assert digest(CFG)==CFGHASH.read_text().split()[0]; return c

def land_context(geom,tree,lands):
 # Original polygons are queried in an expanded neighborhood and never clipped
 # before their genuine boundaries are extracted.
 q=geom.buffer(3.0); idx=tree.query(q); selected=[lands[int(i)] for i in idx if lands[int(i)].intersects(q)]
 return unary_union(selected),unary_union([x.boundary for x in selected])

def plot_scene(rank,r,roi,fp,land,coast,station,metrics,detail=False,alternatives=()):
 c=roi.centroid; fwd,_=local_projection(c.x,c.y); fp=transform(fwd,fp);rp=transform(fwd,roi);la=transform(fwd,land);co=transform(fwd,coast);bp=transform(fwd,Point(station["station_lon"],station["station_lat"]))
 fig,ax=plt.subplots(figsize=(8,7));
 for p in ([la] if la.geom_type=="Polygon" else getattr(la,"geoms",[])):
  if p.geom_type=="Polygon": ax.add_patch(MplPolygon(np.asarray(p.exterior.coords),facecolor="0.85",edgecolor="0.25",lw=.7))
 for p in ([fp] if fp.geom_type=="Polygon" else fp.geoms):ax.add_patch(MplPolygon(np.asarray(p.exterior.coords),fill=False,edgecolor="navy",lw=1.5,label="SAR footprint"))
 ax.add_patch(MplPolygon(np.asarray(rp.exterior.coords),facecolor="cyan",alpha=.35,edgecolor="teal",lw=1.5,label="Block21 ROI"))
 for j,a in enumerate(alternatives):
  ap=transform(fwd,a);ax.add_patch(MplPolygon(np.asarray(ap.exterior.coords),fill=False,ls="--",lw=1,label=f"alternative A{j+1}"))
 ax.scatter(bp.x,bp.y,marker="*",s=130,color="crimson",label=f"NDBC {station['station_id']}");ax.plot([bp.x,rp.centroid.x],[bp.y,rp.centroid.y],":",color="crimson")
 if detail:
  pad=max(1000,float(r["roi_square_size_m"])); minx,miny,maxx,maxy=rp.bounds;ax.set_xlim(minx-pad,maxx+pad);ax.set_ylim(miny-pad,maxy+pad)
 else:
  geoms=[fp,rp,bp];minx=min(g.bounds[0] for g in geoms);miny=min(g.bounds[1] for g in geoms);maxx=max(g.bounds[2] for g in geoms);maxy=max(g.bounds[3] for g in geoms);pad=.15*max(maxx-minx,maxy-miny);ax.set_xlim(minx-pad,maxx+pad);ax.set_ylim(miny-pad,maxy+pad)
 extent=ax.get_xlim()[1]-ax.get_xlim()[0];bar=scale_bar_length(extent);x0=ax.get_xlim()[0]+.08*extent;y0=ax.get_ylim()[0]+.07*(ax.get_ylim()[1]-ax.get_ylim()[0]);ax.plot([x0,x0+bar],[y0,y0],"k",lw=3);ax.text(x0+bar/2,y0,f" {bar/1000:g} km" if bar>=1000 else f" {bar:g} m",ha="center",va="bottom");ax.annotate("N",xy=(.94,.94),xytext=(.94,.82),xycoords="axes fraction",arrowprops=dict(arrowstyle="-|>"),ha="center")
 ax.set_aspect("equal");ax.grid(alpha=.25);ax.set_xlabel("local east [m]");ax.set_ylabel("local north [m]");ax.set_title(f"Block22 {'detail' if detail else 'regional'} — finalist {rank}\n{r['datetime_utc']}, reference offset {r['observation_offset_s']} s");ax.legend(fontsize=8);fig.tight_layout();fig.savefig(BASE/"maps"/f"finalist_{rank}_{'detail' if detail else 'regional'}.png",dpi=160);plt.close(fig)

def alternatives(fp,land,roi,limit=3):
 c=roi.centroid;fwd,inv=local_projection(c.x,c.y);water=transform(fwd,fp).difference(transform(fwd,land));base=transform(fwd,roi);size=max(base.bounds[2]-base.bounds[0],base.bounds[3]-base.bounds[1]);out=[]
 minx,miny,maxx,maxy=water.bounds
 candidates=[]
 for x in np.linspace(minx+size/2,maxx-size/2,9):
  for y in np.linspace(miny+size/2,maxy-size/2,9):
   p=box(x-size/2,y-size/2,x+size/2,y+size/2)
   if water.covers(p) and p.centroid.distance(base.centroid)>size*.5:candidates.append((p.distance(water.boundary),p))
 for _,p in sorted(candidates,key=lambda z:-z[0]):
  if all(p.centroid.distance(q.centroid)>size*.5 for q in out):out.append(p)
  if len(out)>=limit:break
 return [transform(inv,p) for p in out]

def offline():
 cfg=config();BASE.mkdir(exist_ok=True);(BASE/"maps").mkdir(exist_ok=True)
 shortlist=rows(B21/"BLOCK21_SHORTLIST.csv"); allr={r["acquisition_key"]:r for r in rows(B21/"BLOCK21_ALL_CANDIDATES.csv")};refs={r["acquisition_key"]:r for r in rows(B21/"BLOCK21_REFERENCE_AVAILABILITY.csv")}
 lands=read_esri_polygon_shapefile(LAND);tree=STRtree(lands);dist=[];altrows=[]
 for s in shortlist:
  r=allr[s["acquisition_key"]];fp=shape(json.loads(r["geometry_json"]));roi=shape(json.loads(r["roi_polygon_json"]));land,coast=land_context(fp,tree,lands);sts=json.loads(r["stations_within_50km_json"]);st=next(x for x in sts if x["station_id"]==s["station_id"])
  m=geographic_metrics(fp,roi,coast,st["station_lon"],st["station_lat"]); water=fp.difference(land);m["roi_fully_in_mask_water"]=water.covers(roi);m.update(rank=s["rank"],acquisition_key=s["acquisition_key"],collect_id=s["collect_id"],station_id=s["station_id"],coast_source="Natural Earth 1:10m original boundary",coast_accuracy_status="mask_exact_not_real_coast_certification")
  dist.append(m);alts=alternatives(fp,land,roi) if s["rank"]=="1" else []
  for j,a in enumerate(alts,1):
   am=geographic_metrics(fp,a,coast,st["station_lon"],st["station_lat"]);altrows.append({"roi_id":f"A{j}","role":"neutral_geometric_alternative","polygon_json":json.dumps(a.__geo_interface__,separators=(",",":")),**am,"visual_status":"pending_preview_or_complex_data"})
  plot_scene(s["rank"],s,roi,fp,land,coast,st,m,False,alts);plot_scene(s["rank"],s,roi,fp,land,coast,st,m,True,alts)
 table(BASE/"BLOCK22_DISTANCES.csv",dist);table(BASE/"BLOCK22_ROI_ALTERNATIVES.csv",altrows)
 # Vandenberg: use its verified GEC affine, original ROI footprints and archived buoy.
 gr=json.loads((ROOT/'umbra/Vandenberg/results/diagnostics/GEC_georeference.json').read_text());rois=json.loads((ROOT/'umbra/Vandenberg/roi/ROIS.json').read_text());mat=gr["model_transformation_tag_34264"]
 img=np.asarray(Image.open(ROOT/'umbra/Vandenberg/results/diagnostics/GEC_overview_grid.png'));fig,ax=plt.subplots(figsize=(8,8));ax.imshow(img)
 colors={"nearshore":"cyan","offshore":"lime","land_control":"orange"}
 for name,x in rois["rois"].items():
  corners=np.array(x["corner_gec_col_row"])/10;ax.add_patch(MplPolygon(corners,fill=False,edgecolor=colors[name],lw=2,label=name))
 ax.add_patch(Rectangle((200,1400),700,200,fill=False,edgecolor="magenta",lw=2,ls="--",label="visual seed c2000–9000,r14000–16000"));ax.legend();ax.set_title("Vandenberg GEC overview — archived ROIs and visual seed");fig.tight_layout();fig.savefig(BASE/"maps/vandenberg_gec_roi_support_audit.png",dpi=160);plt.close(fig)
 scene_center=gr["corners_lonlat"]["center"];buoy=(-120.76899719238281,34.45100021362305);fwd,_=local_projection(scene_center[0],scene_center[1]);sc=transform(fwd,Point(*scene_center));bp=transform(fwd,Point(*buoy));fig,ax=plt.subplots(figsize=(7,6));ax.scatter(sc.x,sc.y,label="Vandenberg scene",s=80);ax.scatter(bp.x,bp.y,marker="*",s=140,label="NDBC 46218");ax.plot([sc.x,bp.x],[sc.y,bp.y],":");ax.set_aspect("equal");ax.grid();ax.legend();ax.set_xlabel("local east [m]");ax.set_ylabel("local north [m]");ax.set_title("Vandenberg scene–buoy regional relation");fig.tight_layout();fig.savefig(BASE/"maps/vandenberg_scene_buoy_regional.png",dpi=160);plt.close(fig)
 dump(BASE/"BLOCK22_VANDENBERG_AUDIT.json",{"georeference_source":str(Path(gr["source"]).name),"overview_scale_source_pixels_per_pixel":10,"initial_rois_overlaid":list(rois["rois"]),"later_support":"Block7/Block15K 1440x650 m rotated common ground ROI; exact GEC polygon provenance not archived, therefore not drawn as exact polygon","visual_seed_source_box_col_row":[2000,14000,9000,16000],"visual_seed_lonlat_corners":[affine_pixel_to_lonlat(mat,2000,14000),affine_pixel_to_lonlat(mat,9000,16000)],"classification_unchanged":"development stress test; physical frequency not identifiable","new_SAR_extraction":False})
 inv={"block21_manifest_sha256":digest(B21/"BLOCK21_DELIVERY_MANIFEST.json"),"block21_config_sha256":digest(B21/"BLOCK21_CONFIG.json"),"natural_earth_shp_sha256":digest(LAND),"local_images":[{"path":str(p.relative_to(ROOT)),"bytes":p.stat().st_size} for p in (ROOT/'umbra/Vandenberg').rglob("*") if p.is_file() and p.suffix.lower() in {".png",".tif"}],"start_commit":"a9dc43da5995b26007bf8b0e146876fc469ecf2b","preexisting_untracked":['scripts/legacy_git/COMMIT_MSG_BLOCK17_18.txt','scripts/legacy_git/PUSH_BLOCK17_18.bat',"five Block15 B/C/D result files"]}
 dump(BASE/"BLOCK22_INPUT_INVENTORY.json",inv);dump(BASE/"BLOCK22_OFFLINE_SUMMARY.json",{"finalists":5,"distance_rows":len(dist),"all_rois_fully_in_mask_water":all(x["roi_fully_in_mask_water"] for x in dist),"candidate1_alternatives":len(altrows),"visual_status_other_finalists":"no local official raster; structure not inspected","Block21_modified":False,"Block20_audited":False})

def remote():
 cfg=config();h=cfg["remote_budget"];budget=HTTPBudget(h["maximum_transactions"],h["maximum_total_bytes"],h["maximum_response_bytes"],h["timeout_s"],h["maximum_retries"],h["chunk_bytes"])
 key="sar-data/task-data/e0e5b2f2-250f-4394-af51-905e50da4178/2025-11-15-18-57-16_UMBRA-09/";root="https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/"+key
 urls={"stac":root+"2025-11-15-18-57-16_UMBRA-09.stac.v2.json","sicd_xml":root+"2025-11-15-18-57-13_UMBRA-09_SICD_MM.xml"}
 raw=BASE/"remote_raw";raw.mkdir(exist_ok=True);results={};xml=None
 for name,url in urls.items():
  try:
   data=fetch_limited(url,budget,purpose=name,acquisition_key="collect:e6b4c32d-bda9-4f75-a9a4-8dcfe0291a4f");atomic(raw/("candidate1."+("json" if name=="stac" else "xml")),data);results[name]={"status":"recovered","bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"url":url};xml=data if name=="sicd_xml" else xml
  except Exception as e:results[name]={"status":"failed","error":repr(e),"url":url}
 if xml is None:
  nitf=root+"2025-11-15-18-57-16_UMBRA-09_SICD.nitf"; total=13799853988; start=total-2*1024*1024; end=total-1
  try:
   budget.reserve_transaction(); req=Request(nitf,headers={"Range":f"bytes={start}-{end}","User-Agent":"UmbraThesis-Block22/1.0"})
   with urlopen(req,timeout=h["timeout_s"]) as resp:
    data=resp.read(h["maximum_response_bytes"]+1);status=getattr(resp,"status",None);cr=resp.headers.get("Content-Range")
   validate_partial_response(status,cr,start,end,len(data));budget.accept_chunk(0,len(data));atomic(raw/"candidate1_sicd_tail_2MiB.bin",data)
   p=data.find(b"<SICD");q=data.find(b"</SICD>",p)
   if p>=0 and q>p:xml=data[p:q+7];atomic(raw/"candidate1.xml",xml);results["sicd_tail_range"]={"status":"recovered_xml","range":[start,end],"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
   else:results["sicd_tail_range"]={"status":"range_recovered_xml_not_found","range":[start,end],"bytes":len(data)}
   budget.log.append({"timestamp_utc":datetime.now(timezone.utc).isoformat(),"acquisition_key":"collect:e6b4c32d-bda9-4f75-a9a4-8dcfe0291a4f","purpose":"sicd_tail_exact_range","url":nitf,"final_url":nitf,"retry":0,"http_status":status,"bytes":len(data),"outcome":results["sicd_tail_range"]["status"],"error":"","sha256":hashlib.sha256(data).hexdigest()})
  except Exception as e:results["sicd_tail_range"]={"status":"failed","error":repr(e)}
 meta={"identity":{"expected_collect_id":"e6b4c32d-bda9-4f75-a9a4-8dcfe0291a4f"},"retrieval":results}
 if xml:
  from sarpy.io.complex.sicd_elements.SICD import SICDType
  path=raw/"candidate1.xml";sicd=SICDType.from_xml_file(str(path));d=sicd.to_dict()
  ipps=d.get("Timeline",{}).get("IPP",[]);starts=[];ends=[]
  if isinstance(ipps,dict):ipps=[ipps]
  for x in ipps:
   starts.append(x.get("TStart"));ends.append(x.get("TEnd"))
  duration=(max(x for x in ends if x is not None)-min(x for x in starts if x is not None)) if starts and ends else None
  corners=d.get("GeoData",{}).get("ImageCorners",{})
  meta.update({"identity":{"collector":d.get("CollectionInfo",{}).get("CollectorName"),"core_name":d.get("CollectionInfo",{}).get("CoreName"),"radar_mode":d.get("CollectionInfo",{}).get("RadarMode",{}).get("ModeType"),"expected_collect_id":"e6b4c32d-bda9-4f75-a9a4-8dcfe0291a4f"},"polarization":d.get("ImageFormation",{}).get("TxRcvPolarizationProc"),"image_data":d.get("ImageData"),"grid":d.get("Grid"),"timeline":d.get("Timeline"),"processed_aperture_s_from_ipp":duration,"catalog_duration_s":7.6,"catalog_equals_processed_aperture":None if duration is None else abs(duration-7.6)<1e-6,"scpc oa":d.get("SCPCOA"),"image_corners":corners,"doppler_time_mapping_available":{"TimeCOAPoly":bool(d.get("Grid",{}).get("TimeCOAPoly")),"RMA":bool(d.get("RMA")),"PFA":bool(d.get("PFA"))}})
  verified=sicd_metadata_from_bytes(xml);meta["verified_compact_metadata"]=verified
  cpoints=[(float(x["Lon"]),float(x["Lat"])) for x in corners];sicdfp=shape({"type":"Polygon","coordinates":[cpoints+[cpoints[0]]]})
  b21=next(r for r in rows(B21/"BLOCK21_ALL_CANDIDATES.csv") if r["collect_id"]==cfg["candidate_collect_id"]);roi=shape(json.loads(b21["roi_polygon_json"]));meta["block21_roi_within_sicd_image_corners"]=sicdfp.covers(roi)
  meta["sampling_vs_resolution"]={"row_sample_spacing_m":verified["grid_row_ss_m"],"col_sample_spacing_m":verified["grid_col_ss_m"],"row_resolution_approx_m":1/verified["grid_row_imp_resp_bw"],"col_resolution_approx_m":1/verified["grid_col_imp_resp_bw"],"note":"sample spacing and impulse-response resolution are distinct"}
 dump(BASE/"BLOCK22_CANDIDATE1_SICD_METADATA.json",meta);table(BASE/"BLOCK22_REQUEST_LOG.csv",budget.log);dump(BASE/"BLOCK22_REMOTE_SUMMARY.json",{"transactions":budget.transactions,"bytes":budget.total_bytes,"maximum_transactions":budget.max_transactions,"maximum_bytes":budget.max_total_bytes,"sidecar_xml":results.get("sicd_xml",{}).get("status"),"preview":"not recovered; no small official browse asset advertised by STAC inventory","signal_array_read":False})

def reparse():
 path=BASE/"remote_raw/candidate1.xml";xml=path.read_bytes();meta=json.loads((BASE/"BLOCK22_CANDIDATE1_SICD_METADATA.json").read_text());verified=sicd_metadata_from_bytes(xml);meta["verified_compact_metadata"]=verified
 corners=meta["image_corners"];cpoints=[(float(x["Lon"]),float(x["Lat"])) for x in corners];sicdfp=shape({"type":"Polygon","coordinates":[cpoints+[cpoints[0]]]});cfg=config();b21=next(r for r in rows(B21/"BLOCK21_ALL_CANDIDATES.csv") if r["collect_id"]==cfg["candidate_collect_id"]);roi=shape(json.loads(b21["roi_polygon_json"]));meta["block21_roi_within_sicd_image_corners"]=sicdfp.covers(roi);meta["sampling_vs_resolution"]={"row_sample_spacing_m":verified["grid_row_ss_m"],"col_sample_spacing_m":verified["grid_col_ss_m"],"row_resolution_approx_m":1/verified["grid_row_imp_resp_bw"],"col_resolution_approx_m":1/verified["grid_col_imp_resp_bw"],"note":"sample spacing and impulse-response resolution are distinct"};dump(BASE/"BLOCK22_CANDIDATE1_SICD_METADATA.json",meta)

def finalize():
 cfg=config();meta=json.loads((BASE/"BLOCK22_CANDIDATE1_SICD_METADATA.json").read_text());v=meta["verified_compact_metadata"];diff=abs(((24.0-v["grid_row_ground_bearing_deg"]+90)%180)-90)
 dump(BASE/"BLOCK22_REQUEST_AUDIT.json",{"all_executions":{"transactions":5,"bytes":2110160},"retained_final_log":{"transactions":3,"bytes":2103656},"preliminary_sidecar_run":{"transactions":2,"bytes":6504,"note":"STAC recovered; standalone XML 404"},"limits":cfg["remote_budget"]})
 summary={"block":22,"status":"CHECKPOINT_22","finalists_audited":5,"geographic_corrections":["unclipped original coast boundaries","center versus polygon clearance","coast versus footprint edge","buoy center versus polygon distance","full polygon containment"],"candidate1":{"processed_aperture_s":v["sicd_processed_aperture_s"],"timeline_ipp_span_s":meta["processed_aperture_s_from_ipp"],"catalog_duration_s":7.6,"range_axis_unoriented_deg":v["grid_row_ground_bearing_deg"]%180,"buoy_propagation_to_deg":24.0,"axial_difference_deg":diff,"roi_inside_sicd_corners":meta["block21_roi_within_sicd_image_corners"],"preview_status":"not_evaluable_no_small_official_preview","download_recommendation":"NO_for_frequency_validation_due_to_67deg_range_mismatch"},"vandenberg":"geographic_visual_only; Block15K unchanged","remote":{"transactions":5,"bytes":2110160},"prohibitions":{"signal_pixels_read":False,"full_sar_download":False,"formation":False,"frequency_estimation":False,"Block20_audit":False,"commit":False,"push":False}}
 dump(BASE/"BLOCK22_SUMMARY.json",summary)
 artifacts=[]
 for p in sorted(x for x in BASE.rglob("*") if x.is_file() and x.name!="BLOCK22_DELIVERY_MANIFEST.json"):
  artifacts.append({"path":str(p.relative_to(ROOT)).replace("\\","/"),"bytes":p.stat().st_size,"sha256":digest(p)})
 dump(BASE/"BLOCK22_DELIVERY_MANIFEST.json",{"block":22,"created_utc":datetime.now(timezone.utc).isoformat(),"config_sha256":digest(CFG),"artifacts":artifacts,"artifact_count":len(artifacts)})

def main():
 p=argparse.ArgumentParser();p.add_argument("--phase",choices=["offline","remote","reparse","finalize"],default="offline");a=p.parse_args();{"offline":offline,"remote":remote,"reparse":reparse,"finalize":finalize}[a.phase]()
if __name__=="__main__":main()

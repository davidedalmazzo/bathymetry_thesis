"""Bounded metadata-only preflight for Block21 finalist 2."""
from __future__ import annotations
import csv,hashlib,io,json,math,os,struct,sys,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import numpy as np
from shapely.geometry import Point,Polygon,shape
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"code"))
from run_block16a_scene_selection import parse_kv_header,xml_nodes,xml_text,sicd_metadata_from_bytes
from umbra_sar.frequency_validation_selector import temporal_scenarios
from umbra_sar.geographic_preflight import local_projection,scale_bar_length

BASE=ROOT/'umbra/selezione_scene/Block23_candidate2_metadata_preflight';B21=ROOT/'umbra/selezione_scene/Block21_frequency_validation_selector';B22=ROOT/'umbra/selezione_scene/Block22_geographic_visual_preflight'
CFG=BASE/"BLOCK23_CONFIG.json";CFGH=BASE/"BLOCK23_CONFIG.sha256";ENDPOINT="https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/"

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+f".tmp-{os.getpid()}");t.write_bytes((json.dumps(x,indent=2,sort_keys=True)+"\n").encode());os.replace(t,p)
def table(p,rs):
 rs=list(rs);s=io.StringIO(newline="");w=csv.DictWriter(s,fieldnames=list(dict.fromkeys(k for r in rs for k in r)));w.writeheader();w.writerows(rs);Path(p).write_text(s.getvalue(),encoding="utf-8")
def rows(p):
 with open(p,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def cfg():
 x=json.loads(CFG.read_text());assert digest(CFG)==CFGH.read_text().split()[0];return x

class Client:
 def __init__(self,c):self.c=c;self.transactions=0;self.bytes=0;self.log=[]
 def request(self,url,purpose,method="GET",span=None):
  last=None
  for attempt in range(self.c["maximum_retries"]+1):
   if self.transactions>=self.c["maximum_transactions"]:raise RuntimeError("transaction budget")
   self.transactions+=1;headers={"User-Agent":"UmbraThesis-Block23/1.0"}
   if span:headers["Range"]=f"bytes={span[0]}-{span[1]}"
   started=datetime.now(timezone.utc).isoformat();n=0
   try:
    with urlopen(Request(url,headers=headers,method=method),timeout=self.c["timeout_s"]) as r:
     status=r.status;cr=r.headers.get("Content-Range");cl=r.headers.get("Content-Length");chunks=[]
     if method!="HEAD":
      while True:
       b=r.read(min(self.c["chunk_bytes"],self.c["maximum_response_bytes"]+1-n))
       if not b:break
       n+=len(b)
       if n>self.c["maximum_response_bytes"] or self.bytes+n>self.c["maximum_total_bytes"]:raise RuntimeError("byte budget")
       chunks.append(b)
    data=b"".join(chunks)
    if span:
     expected=span[1]-span[0]+1
     if status!=206 or cr is None or not cr.startswith(f"bytes {span[0]}-{span[1]}/") or n!=expected:raise RuntimeError("range not honored exactly")
    self.bytes+=n;self.log.append({"timestamp_utc":started,"purpose":purpose,"method":method,"url":url,"range_start":span[0] if span else "","range_end":span[1] if span else "","attempt":attempt,"http_status":status,"content_range":cr or "","content_length":cl or "","bytes":n,"outcome":"recovered","sha256":hashlib.sha256(data).hexdigest()});return data,{"status":status,"content_range":cr,"content_length":cl}
   except Exception as e:
    last=e;self.log.append({"timestamp_utc":started,"purpose":purpose,"method":method,"url":url,"range_start":span[0] if span else "","range_end":span[1] if span else "","attempt":attempt,"http_status":getattr(e,"code",""),"content_range":"","content_length":"","bytes":n,"outcome":"failed","error":repr(e)})
    if isinstance(e,HTTPError) and 400<=e.code<500:break
  raise RuntimeError(f"request failed {purpose}: {last!r}")

def axial(a,b):return abs(((a-b+90)%180)-90)
def full(a,b):return abs(((a-b+180)%360)-180)

def availability_only():
 c=cfg();client=Client(c["remote_budget"]);raw=BASE/"remote_raw";raw.mkdir(exist_ok=True);prefix="sar-data/tasks/ad hoc/Los_Angeles_CA_Wildfires/95266076-7d2d-4ef3-8653-263f8051ef66/2025-01-09-06-35-11_UMBRA-10/";url=lambda n:ENDPOINT+quote(prefix+n,safe="/")
 names=[("stac","2025-01-09-06-35-11_UMBRA-10.stac.v2.json","GET"),("metadata","2025-01-09-06-35-11_UMBRA-10_METADATA.json","GET"),("sicd_declared","2025-01-09-06-35-11_UMBRA-10_SICD_MM.nitf","HEAD"),("sicd_alias","2025-01-09-06-35-11_UMBRA-10_SICD.nitf","HEAD"),("cphd_declared","2025-01-09-06-35-11_UMBRA-10_MM.cphd","HEAD"),("cphd_alias","2025-01-09-06-35-11_UMBRA-10_CPHD.cphd","HEAD")];availability=[]
 for label,name,method in names:
  try:
   data,h=client.request(url(name),label,method=method);availability.append({"asset":label,"declared_name":name,"status":"publicly_available","size_bytes":h["content_length"] or len(data),"url":url(name)})
   if data:(raw/f"candidate2_{label}.json").write_bytes(data)
  except Exception as e:availability.append({"asset":label,"declared_name":name,"status":"not_publicly_retrievable","size_bytes":"","url":url(name),"error":repr(e)})
 table(BASE/"BLOCK23_ASSET_AVAILABILITY.csv",availability);table(BASE/"BLOCK23_REQUEST_LOG.csv",client.log);dump(BASE/"BLOCK23_REMOTE_SUMMARY.json",{"transactions":client.transactions,"bytes":client.bytes,"limits":c["remote_budget"],"sicd_public":False,"cphd_public":False,"interpretation":"STAC declarations are not equivalent to public object availability"})
 block21=next(r for r in rows(B21/"BLOCK21_ALL_CANDIDATES.csv") if r["collect_id"]==c["collect_id"]);block22=next(r for r in rows(B22/"BLOCK22_DISTANCES.csv") if r["rank"]=="2");meta=json.loads((raw/"candidate2_metadata.json").read_text())
 dump(BASE/"BLOCK23_IDENTITY.json",{"collect_id":c["collect_id"],"Block21":{"collect_name":block21["collect_name"],"platform":block21["platform"],"datetime_utc":block21["datetime_utc"],"catalog_duration_s":block21["catalog_duration_s"],"processing_version":block21["processing_version"],"processing_created_utc":block21["processing_created_utc"],"stac_declares_sicd":block21["has_sicd"],"stac_declares_cphd":block21["has_cphd"]},"official_metadata_json":meta,"availability_conclusion":"identity metadata available; complex product objects absent from frozen public listing and return 404"})
 unknown={"status":"NOT_VERIFIABLE_NO_PUBLIC_OBJECT","reason":"declared by STAC but absent from public listing and all scoped object names return 404","signal_or_pixels_read":False};dump(BASE/"BLOCK23_SICD_SUMMARY.json",unknown);dump(BASE/"BLOCK23_CPHD_SUMMARY.json",unknown)
 dump(BASE/"BLOCK23_WAVE_RANGE_GEOMETRY.json",{"wave_band_hz":c["frozen_wave_band_hz"],"wave_period_s":c["frozen_peak_period_s"],"wave_propagation_to_deg":c["frozen_propagation_to_deg"],"direction_resultant":0.9970494255000656,"range_axis":"unknown_without_SICD_or_CPHD_metadata","axial_difference_deg":None,"directed_difference_deg":None,"candidate1_Block22_axial_difference_deg":67.17,"band_reselected":False})
 dump(BASE/"BLOCK23_ROI_AUDIT.json",{"corrected_Block22_distances":block22,"original_roi_unchanged":True,"SICD_valid_support":"not verifiable","minimum_STAC_footprint_edge_clearance_m":float(block22["roi_polygon_to_footprint_edge_m"]),"minimum_mask_coast_clearance_m":float(block22["roi_polygon_to_coast_m"]),"alternatives_proposed":0,"reason":"cannot optimize before verifying complex support"})
 ts=[]
 for x in temporal_scenarios(15.0,c["look_durations_s"],c["sliding_step_s"],c["frozen_peak_period_s"]):ts.append({"path":"catalog_descriptor_only","duration_s":15.0,"look_to_period_ratio":x["look_duration_s"]/c["frozen_peak_period_s"],**x})
 table(BASE/"BLOCK23_TEMPORAL_SCENARIOS.csv",ts)
 fp=shape(json.loads(block21["geometry_json"]));roi=shape(json.loads(block21["roi_polygon_json"]));st=next(x for x in json.loads(block21["stations_within_50km_json"]) if x["station_id"]=="46268");cen=roi.centroid;fwd,_=local_projection(cen.x,cen.y);from shapely.ops import transform;fpp=transform(fwd,fp);rp=transform(fwd,roi);bp=transform(fwd,Point(st["station_lon"],st["station_lat"]));fig,ax=plt.subplots(figsize=(7,7));ax.add_patch(MplPolygon(np.asarray(fpp.exterior.coords),fill=False,edgecolor="navy",label="STAC footprint"));ax.add_patch(MplPolygon(np.asarray(rp.exterior.coords),facecolor="cyan",alpha=.4,edgecolor="teal",label="Block21 ROI"));ax.scatter(bp.x,bp.y,marker="*",s=140,color="crimson",label="NDBC 46268");ax.set_aspect("equal");ax.grid(alpha=.3);ax.legend();ax.set_xlabel("local east [m]");ax.set_ylabel("local north [m]");ax.set_title("Block23 candidate 2 — STAC geometry; complex assets unavailable");fig.tight_layout();fig.savefig(BASE/"BLOCK23_SCENE_ROI_BUOY_MAP.png",dpi=160);plt.close(fig)

def main():
 c=cfg();client=Client(c["remote_budget"]);raw=BASE/"remote_raw";raw.mkdir(exist_ok=True)
 allr={r["collect_id"]:r for r in rows(B21/"BLOCK21_ALL_CANDIDATES.csv")};r=allr[c["collect_id"]];assets=json.loads(r["assets_json"]);prefix="sar-data/tasks/ad hoc/Los_Angeles_CA_Wildfires/95266076-7d2d-4ef3-8653-263f8051ef66/2025-01-09-06-35-11_UMBRA-10/"
 url=lambda name:ENDPOINT+quote(prefix+name,safe="/")
 urls={"stac":url("2025-01-09-06-35-11_UMBRA-10.stac.v2.json"),"sicd":url("2025-01-09-06-35-11_UMBRA-10_SICD.nitf"),"cphd":url("2025-01-09-06-35-11_UMBRA-10_CPHD.cphd")}
 try:
  stac,_=client.request(urls["stac"],"stac");(raw/"candidate2.stac.json").write_bytes(stac);stacj=json.loads(stac)
  sizes={}
  for kind in ("sicd","cphd"):
   _,h=client.request(urls[kind],f"{kind}_head",method="HEAD");sizes[kind]=int(h["content_length"])
  # SICD DES is near EOF; exact 2 MiB range, no image samples.
  ss=sizes["sicd"];tail,_=client.request(urls["sicd"],"sicd_tail_xml",span=(ss-2*1024**2,ss-1));(raw/"candidate2_sicd_tail_2MiB.bin").write_bytes(tail);a=tail.find(b"<SICD");b=tail.find(b"</SICD>",a);assert a>=0 and b>a;sxml=tail[a:b+7];(raw/"candidate2_sicd.xml").write_bytes(sxml)
  from sarpy.io.complex.sicd_elements.SICD import SICDType
  sicd=SICDType.from_xml_string(sxml);sm=sicd_metadata_from_bytes(sxml);sd=sicd.to_dict();sm.update({"object_size_bytes":ss,"timeline":sd.get("Timeline"),"image_data":sd.get("ImageData"),"image_corners":sd.get("GeoData",{}).get("ImageCorners"),"grid_full":sd.get("Grid"),"PFA_present":sd.get("PFA") is not None,"TimeCOAPoly_present":sd.get("Grid",{}).get("TimeCOAPoly") is not None,"timeline_ipp_span_s":max(x["TEnd"] for x in sd["Timeline"]["IPP"])-min(x["TStart"] for x in sd["Timeline"]["IPP"])})
  # Project every frozen ROI corner to image coordinates and test ValidData polygon.
  roi=shape(json.loads(r["roi_polygon_json"]));valid=sd["ImageData"].get("ValidData",[]);vp=Polygon([(x["Col"],x["Row"]) for x in valid]);proj=[]
  for lon,lat in list(roi.exterior.coords)[:-1]:
   pix,res,it=sicd.project_ground_to_image_geo(np.array([lat,lon,0.0]),projection_type="HAE");p=Point(float(pix[1]),float(pix[0]));proj.append({"lon":lon,"lat":lat,"row":float(pix[0]),"col":float(pix[1]),"projection_residual":float(res),"iterations":int(it),"inside_valid_data":vp.covers(p),"distance_to_valid_edge_pixels":p.distance(vp.boundary)})
  sm["block21_roi_projection"]=proj;sm["roi_all_corners_inside_valid_data"]=all(x["inside_valid_data"] for x in proj);sm["roi_min_valid_edge_distance_pixels"]=min(x["distance_to_valid_edge_pixels"] for x in proj)
  dump(BASE/"BLOCK23_SICD_SUMMARY.json",sm)
  # CPHD header/XML and five fixed PVP TxTime values.
  chead,_=client.request(urls["cphd"],"cphd_header",span=(0,4095));parsed=parse_kv_header(chead);xo=int(parsed["XML_BLOCK_BYTE_OFFSET"]);xn=int(parsed["XML_BLOCK_SIZE"]);cxml,_=client.request(urls["cphd"],"cphd_xml",span=(xo,xo+xn-1));(raw/"candidate2_cphd_header.bin").write_bytes(chead);(raw/"candidate2_cphd.xml").write_bytes(cxml)
  import xml.etree.ElementTree as ET
  root=ET.fromstring(cxml);chs=[]
  for node in xml_nodes(root,("Data","Channel")):
   local=lambda n:next((x.text.strip() for x in node if x.tag.rsplit('}',1)[-1]==n),None);chs.append({x:local(x) for x in ("Identifier","NumVectors","NumSamples","SignalArrayByteOffset","PVPArrayByteOffset")})
  psize=int(xml_text(root,("Data","NumBytesPVP")));toff=int(xml_text(root,("PVP","TxTime","Offset")));pbase=int(parsed["PVP_BLOCK_BYTE_OFFSET"]);count=int(chs[0]["NumVectors"]);coff=int(chs[0]["PVPArrayByteOffset"]);samples=[]
  for frac in c["fixed_pvp_sample_fractions"]:
   ix=round(frac*(count-1));off=pbase+coff+ix*psize+toff*8;val,_=client.request(urls["cphd"],f"pvp_TxTime_{frac:g}",span=(off,off+7));samples.append({"fraction":frac,"vector_index":ix,"byte_offset":off,"tx_time_s":struct.unpack(">d",val)[0]})
  cm={"object_size_bytes":sizes["cphd"],"file_format":parsed.get("format"),"collection_start":xml_text(root,("Global","Timeline","CollectionStart")),"collector":xml_text(root,("CollectionID","CollectorName")),"core_name":xml_text(root,("CollectionID","CoreName")),"radar_mode":xml_text(root,("CollectionID","RadarMode","ModeType")),"channels":chs,"channel_count":len(chs),"num_bytes_pvp":psize,"tx_time_offset_words":toff,"pvp_block_byte_offset":pbase,"signal_block_byte_offset":int(parsed["SIGNAL_BLOCK_BYTE_OFFSET"]),"signal_block_size_bytes":int(parsed["SIGNAL_BLOCK_SIZE"]),"sampled_TxTime":samples,"sampled_span_s":samples[-1]["tx_time_s"]-samples[0]["tx_time_s"],"sampled_monotonic":all(y["tx_time_s"]>x["tx_time_s"] for x,y in zip(samples,samples[1:])),"full_sequence_continuity_demonstrated":False,"signal_array_read":False,"xml_sha256":hashlib.sha256(cxml).hexdigest()};dump(BASE/"BLOCK23_CPHD_SUMMARY.json",cm)
  # Same-band direction only; no band reselection.
  wave=37.31836855246769;geo={"range_oriented_deg":sm["grid_row_ground_bearing_deg"],"range_axis_mod180_deg":sm["grid_row_ground_bearing_deg"]%180,"incidence_deg":sm["incidence_deg"],"wave_propagation_to_deg":wave,"wave_band_hz":c["frozen_wave_band_hz"],"wave_direction_resultant":0.9970494255000656,"axial_difference_deg":axial(wave,sm["grid_row_ground_bearing_deg"]),"directed_difference_deg":full(wave,sm["grid_row_ground_bearing_deg"]),"roi_variation_status":"Grid Row UVect is constant in SICD; per-point range variation is not supplied, so only SCP axis is verified","candidate1_Block22_axial_difference_deg":67.17,"buoy_direction_is_local_roi_measurement":False};dump(BASE/"BLOCK23_WAVE_RANGE_GEOMETRY.json",geo)
  # Separate temporal scenarios, never independent for sliding looks.
  ts=[]
  for path,duration in (("SICD_processed",sm["sicd_processed_aperture_s"]),("CPHD_sampled_TxTime",cm["sampled_span_s"])):
   for x in temporal_scenarios(duration,c["look_durations_s"],c["sliding_step_s"],c["frozen_peak_period_s"]):ts.append({"path":path,"duration_s":duration,"look_to_period_ratio":x["look_duration_s"]/c["frozen_peak_period_s"],**x})
  table(BASE/"BLOCK23_TEMPORAL_SCENARIOS.csv",ts)
  d=next(x for x in rows(B22/"BLOCK22_DISTANCES.csv") if x["rank"]=="2");dump(BASE/"BLOCK23_ROI_AUDIT.json",{"block22_distances":d,"sicd_valid_data_projection":proj,"original_roi_unchanged":True,"preprocessing_margin_status":"insufficient: only 90.1 m to STAC footprint edge and metadata-only valid-data margin must be interpreted in ground geometry before full-azimuth decomposition","alternatives_proposed":0})
  # Metric map reuses verified footprint/ROI/buoy.
  fp=shape(json.loads(r["geometry_json"]));st=next(x for x in json.loads(r["stations_within_50km_json"]) if x["station_id"]=="46268");cen=roi.centroid;fwd,_=local_projection(cen.x,cen.y);fpp=__import__('shapely').ops.transform(fwd,fp);rp=__import__('shapely').ops.transform(fwd,roi);bp=__import__('shapely').ops.transform(fwd,Point(st["station_lon"],st["station_lat"]));fig,ax=plt.subplots(figsize=(7,7));ax.add_patch(MplPolygon(np.asarray(fpp.exterior.coords),fill=False,edgecolor="navy",label="STAC footprint"));ax.add_patch(MplPolygon(np.asarray(rp.exterior.coords),facecolor="cyan",alpha=.4,edgecolor="teal",label="Block21 ROI"));ax.scatter(bp.x,bp.y,marker="*",s=140,color="crimson",label="NDBC 46268");ax.set_aspect("equal");ax.grid(alpha=.3);ax.legend();ax.set_xlabel("local east [m]");ax.set_ylabel("local north [m]");ax.set_title("Block23 candidate 2 — verified identity / frozen ROI and buoy");fig.tight_layout();fig.savefig(BASE/"BLOCK23_SCENE_ROI_BUOY_MAP.png",dpi=160);plt.close(fig)
  dump(BASE/"BLOCK23_IDENTITY.json",{"expected_collect_id":c["collect_id"],"block21":{"collect_name":r["collect_name"],"platform":r["platform"],"datetime_utc":r["datetime_utc"],"processing_version":r["processing_version"]},"stac":{"id":stacj.get("id"),"properties":stacj.get("properties"),"sha256":hashlib.sha256(stac).hexdigest()},"sicd":{"collector":sm["collector"],"core_name":sm["core_name"],"size_bytes":ss,"url":urls["sicd"]},"cphd":{"collector":cm["collector"],"core_name":cm["core_name"],"size_bytes":sizes["cphd"],"url":urls["cphd"]},"association_status":"same collector, acquisition family and remote STAC; metadata collection starts compared in report"})
 finally:
  table(BASE/"BLOCK23_REQUEST_LOG.csv",client.log);dump(BASE/"BLOCK23_REMOTE_SUMMARY.json",{"transactions":client.transactions,"bytes":client.bytes,"limits":c["remote_budget"]})

def manifest_only():
 artifacts=[]
 for p in sorted(x for x in BASE.rglob("*") if x.is_file() and x.name!="BLOCK23_DELIVERY_MANIFEST.json"):
  artifacts.append({"path":str(p.relative_to(ROOT)).replace("\\","/"),"bytes":p.stat().st_size,"sha256":digest(p)})
 dump(BASE/"BLOCK23_DELIVERY_MANIFEST.json",{"block":23,"created_utc":datetime.now(timezone.utc).isoformat(),"config_sha256":digest(CFG),"artifact_count":len(artifacts),"artifacts":artifacts})

if __name__=="__main__":
 manifest_only() if "--manifest-only" in sys.argv else (availability_only() if "--availability-only" in sys.argv else main())

"""Bounded Samoa SICD metadata preflight: exact headers/DES, never image bytes."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,os,sys,gzip,struct
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import quote,urlparse
from urllib.error import HTTPError,URLError
import numpy as np
from shapely.geometry import shape,Polygon,Point,LineString
from shapely.ops import transform
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
from run_block22_geographic_preflight import atomic,dump,table
from run_block16a_scene_selection import sicd_metadata_from_bytes,parse_kv_header,xml_text,xml_nodes
from umbra_sar.geographic_preflight import local_projection,validate_partial_response
BASE=ROOT/'Block28_Samoa_metadata_preflight';ID='1424a3c8-7285-4210-b965-069514c13a2a'
ENDPOINT='https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/'
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def axial(a,b):return abs((a-b+90)%180-90)
def initialize():
    if (BASE/'STATE.json').exists():return
    BASE.mkdir(parents=True,exist_ok=True)
    a=next(r for r in read(ROOT/'Block21_frequency_validation_selector/BLOCK21_ALL_CANDIDATES.csv') if r['collect_id']==ID)
    r=next(r for r in read(ROOT/'Block27_frequency_query/representativity_v2/ACQUISITION_AUDIT.csv') if r['collect_id']==ID)
    dump(BASE/'LOCAL_INPUTS.json',{'catalog':a,'reference_and_roi':r})
    sources=[ROOT/'Block21_frequency_validation_selector/BLOCK21_ALL_CANDIDATES.csv',
        ROOT/'Block27_frequency_query/representativity_v2/ACQUISITION_AUDIT.csv',ROOT/r['payload_path'],
        ROOT/f'Block27_frequency_query/representativity_v2/normalized/{ID}.json']
    dump(BASE/'INPUT_PROVENANCE.json',[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sources])
    dump(BASE/'STATE.json',{'tranche':'Samoa_complex_metadata_only','transactions':0,'total_bytes':0,
        'max_transactions':20,'max_total_bytes':20*1024**2,'max_response_bytes':5*1024**2,
        'stage':'initialized_before_network','historical_budgets':'separate, unchanged','image_pixels_read':False,'signal_array_read':False})
    dump(BASE/'REQUEST_LOG.json',[])
    atomic(BASE/'PROTOCOL.md',b'Samoa only. Independent 20 transactions / 20 MiB total / 5 MiB each, redirects included, no automatic retry. Pertinent HEAD connectivity probe first, stop on blocked transport before further endpoints. Public S3 assets only; sidecar or exact NITF main header and DES metadata. Reject ignored byte-range BEFORE reading body; no image segment reads. Frozen buoy half-power band unchanged; direction measured at buoy, not certified in ROI. No complete SAR, formation, real frequency, inversion, AIS, Block20 or Vandenberg.\n')

class Client:
    def __init__(self):
        self.state=json.loads((BASE/'STATE.json').read_text());self.log=json.loads((BASE/'REQUEST_LOG.json').read_text())
    def save(self):dump(BASE/'STATE.json',self.state);dump(BASE/'REQUEST_LOG.json',self.log)
    def reserve(self,url,purpose,method,span,kind='request'):
        if self.state['transactions']>=20:raise RuntimeError('transaction_budget_exhausted')
        if urlparse(url).hostname!=urlparse(ENDPOINT).hostname:raise RuntimeError('redirect_outside_authorized_public_host')
        self.state['transactions']+=1
        e={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'url':url,'purpose':purpose,'method':method,
           'range':span,'kind':kind,'outcome':'pending','bytes':0}
        self.log.append(e);self.save();return e
    def request(self,url,purpose,method='GET',span=None):
        e=self.reserve(url,purpose,method,span);client=self
        class Redirect(HTTPRedirectHandler):
            def redirect_request(self,req,fp,code,msg,headers,newurl):
                entry=client.reserve(newurl,purpose,method,span,'redirect');entry.update(http_status=code,outcome='redirect');client.save()
                return super().redirect_request(req,fp,code,msg,headers,newurl)
        h={'User-Agent':'UmbraThesis-Samoa-Preflight/1.0'}
        if span:h['Range']=f'bytes={span[0]}-{span[1]}'
        try:
            with build_opener(Redirect()).open(Request(url,headers=h,method=method),timeout=20) as r:
                status=r.status;cr=r.headers.get('Content-Range');cl=r.headers.get('Content-Length')
                e.update(http_status=status,content_range=cr,content_length=cl)
                if span:
                    # Critical safety: reject before reading any body/pixel bytes.
                    validate_partial_response(status,cr,*span,span[1]-span[0]+1)
                    if cl and int(cl)!=span[1]-span[0]+1:raise RuntimeError('range_content_length_mismatch')
                if method!='HEAD' and cl and int(cl)>5*1024**2:raise RuntimeError('declared_response_too_large')
                chunks=[]
                if method!='HEAD':
                    remaining=(span[1]-span[0]+1) if span else 5*1024**2
                    while remaining>0:
                        n=min(65536,remaining,20*1024**2-self.state['total_bytes'])
                        if n<=0:raise RuntimeError('total_byte_budget_exhausted')
                        b=r.read(n)
                        if not b:break
                        chunks.append(b);remaining-=len(b);e['bytes']+=len(b);self.state['total_bytes']+=len(b);self.save()
                    if span:validate_partial_response(status,cr,*span,e['bytes'])
                    elif remaining==0 and not cl:raise RuntimeError('response_at_limit_without_declared_eof')
                data=b''.join(chunks)
            e.update(outcome='recovered',sha256=hashlib.sha256(data).hexdigest());self.save()
            return data,{'content_length':cl,'content_range':cr,'http_status':status}
        except Exception as exc:
            e.update(outcome='failed',http_status=getattr(exc,'code',e.get('http_status')),error=repr(exc));self.save();raise

def inputs():return json.loads((BASE/'LOCAL_INPUTS.json').read_text())
def asset(kind):return next((a for a in json.loads(inputs()['catalog']['assets_json']) if a['kind']==kind),None)
def url(key):return ENDPOINT+quote(key,safe='/')
def probe():
    c=Client();a=asset('SICD')
    try:
        _,h=c.request(url(a['public_key']),'pertinent_connectivity_and_sicd_size',method='HEAD')
        dump(BASE/'SICD_PUBLIC_HEAD.json',{'url':url(a['public_key']),'size_bytes':int(h['content_length']),
            'catalog_size_bytes':a['size_bytes'],'size_matches_catalog':int(h['content_length'])==a['size_bytes']})
        c.state['stage']='connectivity_verified';c.save()
    except Exception as exc:
        c.state.update(stage='transport_or_access_blocked',diagnostic=repr(exc));c.save()
        raise RuntimeError('Connectivity probe failed; do not query other endpoints until diagnosed.') from exc

def nitf_segments(data,total):
    from sarpy.io.general.nitf_elements.nitf_head import NITFHeader
    if data[:9]!=b'NITF02.10':raise ValueError('unsupported NITF version')
    header=NITFHeader.from_bytes(data,0)
    if header.FL!=total or header.HL!=len(data):raise ValueError('NITF size/header mismatch')
    offset=header.HL;segments=[]
    for kind in ['ImageSegments','GraphicsSegments','TextSegments','DataExtensions','ReservedExtensions']:
        arr=getattr(header,kind)
        for sh,sz in zip(arr.subhead_sizes,arr.item_sizes):
            sh=int(sh);sz=int(sz);segments.append({'kind':kind,'offset':offset,'subheader_size':sh,'data_offset':offset+sh,'data_size':sz});offset+=sh+sz
    if offset!=total:raise ValueError('unaccounted NITF segments')
    return segments

def remote():
    c=Client()
    if c.state['stage'] not in ['connectivity_verified','metadata_recovered']:raise RuntimeError('probe not verified')
    a=inputs()['catalog'];prefix=a['stac_s3_key'].rsplit('/',1)[0]+'/'
    for name,key in [('official_stac',a['stac_s3_key']),('vendor_metadata',prefix+a['collect_name']+'_METADATA.json')]:
        path=BASE/'raw'/f'{name}.json'
        if path.exists():continue
        if any(e['url']==url(key) and e.get('http_status') in [403,404] for e in c.log):continue
        try:data,_=c.request(url(key),name);atomic(path,data)
        except HTTPError as exc:
            if exc.code not in [403,404]:raise
    # Standalone XML has no verified public listing size: one precise advertised sidecar attempt.
    xmlpath=BASE/'raw/sicd.xml'
    if not xmlpath.exists():
        side=asset('SICD_XML')
        if side:
            try:data,_=c.request(url(side['public_key']),'advertised_sicd_xml');atomic(xmlpath,data)
            except HTTPError as exc:
                if exc.code not in [403,404]:raise
        if not xmlpath.exists():
            head=json.loads((BASE/'SICD_PUBLIC_HEAD.json').read_text());total=head['size_bytes'];u=head['url']
            fixed,_=c.request(u,'NITF_fixed_main_header',span=(0,359));atomic(BASE/'raw/nitf_fixed_header.bin',fixed)
            if fixed[:9]!=b'NITF02.10':raise ValueError('unsupported NITF format')
            hl=int(fixed[354:360]);full,_=c.request(u,'NITF_complete_main_header',span=(0,hl-1));atomic(BASE/'raw/nitf_main_header.bin',full)
            segments=nitf_segments(full,total);dump(BASE/'NITF_SEGMENT_LAYOUT.json',segments)
            for i,s in enumerate(segments):
                if s['kind']!='DataExtensions':continue
                # Exact DES subheader and payload only; never preceding image bytes.
                sh,_=c.request(u,f'DES_{i}_subheader',span=(s['offset'],s['data_offset']-1));atomic(BASE/'raw'/f'des_{i}_subheader.bin',sh)
                if b'XML_DATA_CONTENT' not in sh and b'SICD' not in sh:continue
                if s['data_size']>5*1024**2:raise RuntimeError('DES_over_response_budget')
                data,_=c.request(u,f'DES_{i}_XML_only',span=(s['data_offset'],s['data_offset']+s['data_size']-1))
                atomic(BASE/'raw'/f'des_{i}_xml.bin',data)
                start=data.find(b'<SICD');stop=data.find(b'</SICD>',start)
                if start>=0 and stop>start:atomic(xmlpath,data[start:stop+7]);break
    if not xmlpath.exists():raise RuntimeError('No SICD XML recovered')
    listing=ROOT/'Block16_scene_selection/catalog_snapshots/20260913T231747Z/listing_s3.csv.gz'
    with gzip.open(listing,'rt') as f:public=[r for r in csv.DictReader(f) if r['key'].startswith(prefix)]
    dump(BASE/'PUBLIC_LISTING_INVENTORY.json',{'source':str(listing.relative_to(ROOT)),'sha256':sha(listing),'assets':public,
        'normalization_discrepancy':'CPHD exists in public listing but is omitted from normalized STAC asset inventory' if any(r['key'].endswith('.cphd') for r in public) and asset('CPHD') is None else None})
    cp=next((r for r in public if r['key'].endswith('.cphd')),None)
    if cp and not (BASE/'CPHD_METADATA.json').exists():
        u=url(cp['key']);_,h=c.request(u,'public_CPHD_head',method='HEAD');size=int(h['content_length'])
        header,_=c.request(u,'CPHD_ASCII_header_only',span=(0,511));atomic(BASE/'raw/cphd_header.bin',header);kv=parse_kv_header(header)
        xo=int(kv['XML_BLOCK_BYTE_OFFSET']);xn=int(kv['XML_BLOCK_SIZE'])
        xml,_=c.request(u,'CPHD_XML_only',span=(xo,xo+xn-1));atomic(BASE/'raw/cphd.xml',xml)
        import xml.etree.ElementTree as ET
        root=ET.fromstring(xml);channels=[]
        for ch in xml_nodes(root,('Data','Channel')):
            def value(name):return next((x.text.strip() for x in ch if x.tag.rsplit('}',1)[-1]==name),None)
            channels.append({k:value(k) for k in ['Identifier','NumVectors','NumSamples','PVPArrayByteOffset','SignalArrayByteOffset']})
        pvp_size=int(xml_text(root,('Data','NumBytesPVP')));toff=int(xml_text(root,('PVP','TxTime','Offset')))
        base=int(kv['PVP_BLOCK_BYTE_OFFSET']);samples=[]
        ch=channels[0];n=int(ch['NumVectors'])
        for frac in [0,.5,1]:
            ix=round(frac*(n-1));off=base+int(ch['PVPArrayByteOffset'])+ix*pvp_size+toff*8
            data,_=c.request(u,f'CPHD_PVP_TxTime_{frac}',span=(off,off+7));atomic(BASE/'raw'/f'txtime_{ix}.bin',data)
            samples.append({'vector_index':ix,'byte_offset':off,'tx_time_s':struct.unpack('>d',data)[0]})
        dump(BASE/'CPHD_METADATA.json',{'url':u,'size_bytes':size,'size_matches_listing':size==int(cp['size_bytes']),
            'collector':xml_text(root,('CollectionID','CollectorName')),'core_name':xml_text(root,('CollectionID','CoreName')),
            'collection_start':xml_text(root,('Global','Timeline','CollectionStart')),'channels':channels,
            'num_bytes_pvp':pvp_size,'PVP_fields':[x.tag.rsplit('}',1)[-1] for x in xml_nodes(root,('PVP',))[0]],
            'sampled_TxTime':samples,'first_last_TxTime_span_s':samples[-1]['tx_time_s']-samples[0]['tx_time_s'],
            'full_PVP_time_sequence_validated':False,'signal_array_read':False,
            'signal_block_byte_offset':int(kv['SIGNAL_BLOCK_BYTE_OFFSET']),'header_fields':kv})
    c.state['stage']='metadata_recovered';c.save()

def projected_axes(sicd,pixel,hae,step=10.):
    """Push-forward image coordinate axes to a stated WGS84 HAE surface."""
    from run_block27_representativity import bearing
    pixel=np.asarray(pixel,float);out={}
    for axis,name in [(0,'row'),(1,'col')]:
        pp=np.tile(pixel,(2,1));pp[0,axis]-=step;pp[1,axis]+=step
        llh=sicd.project_image_to_ground_geo(pp,projection_type='HAE',hae0=hae)
        a,b=Point(llh[0,1],llh[0,0]),Point(llh[1,1],llh[1,0]);fwd,_=local_projection((a.x+b.x)/2,(a.y+b.y)/2)
        out[name+'_surface_bearing_deg']=bearing(a,b)
        out[name+'_ground_m_per_pixel']=transform(fwd,a).distance(transform(fwd,b))/(2*step)
    return out

def roi_projection(sicd,roi,hae,samples=33):
    valid=sicd.ImageData.ValidData
    vp=Polygon([(v.Col,v.Row) for v in valid])
    coords=list(roi.exterior.coords);ll=[]
    for a,b in zip(coords[:-1],coords[1:]):
        for f in np.linspace(0,1,samples,endpoint=False):ll.append([a[1]+f*(b[1]-a[1]),a[0]+f*(b[0]-a[0]),hae])
    pixels,res,it=sicd.project_ground_to_image_geo(np.asarray(ll))
    polygon=Polygon(pixels[:,::-1]);ssr=float(sicd.Grid.Row.SS);ssc=float(sicd.Grid.Col.SS)
    scaled=lambda x,y,z=None:(x*ssc,y*ssr)
    sroi=transform(scaled,polygon);svalid=transform(scaled,vp)
    centers=[Point(*xy) for xy in pixels[:,::-1]]
    slices=[]
    for row in np.linspace(pixels[:,0].min(),pixels[:,0].max(),17):
        interval=vp.intersection(LineString([(-1,float(row)),(sicd.ImageData.NumCols,float(row))]))
        slices.append({'row':float(row),'valid_azimuth_extent_pixels':interval.length,
            'col_min':interval.bounds[0],'col_max':interval.bounds[2]})
    return {'hae_m':hae,'samples_per_edge':samples,'whole_sampled_roi_within_ValidData':vp.covers(polygon),
        'minimum_valid_edge_margin_pixels_euclidean':polygon.distance(vp.boundary),
        'minimum_valid_edge_margin_image_plane_m':sroi.distance(svalid.boundary),
        'projection_residual_max_m':float(np.max(res)),'projection_iterations_max':int(np.max(it)),
        'roi_image_bounds_col_row':list(polygon.bounds),'valid_azimuth_slices':slices,
        'common_valid_col_interval_over_range_strip':[max(s['col_min'] for s in slices),min(s['col_max'] for s in slices)],
        'boundary_pixels_row_col':pixels.tolist(),'valid_polygon_col_row':list(vp.exterior.coords)}

def analyze():
    from dataclasses import asdict
    from sarpy.io.complex.sicd_elements.SICD import SICDType
    from umbra_sar.subaperture import SicdSubapertureContext,ProcessedSupport,plan_tiled_bands
    xml=BASE/'raw/sicd.xml';s=SICDType.from_xml_file(str(xml));d=s.to_dict();compact=sicd_metadata_from_bytes(xml.read_bytes())
    i=inputs();r=i['reference_and_roi'];roi=shape(json.loads(r['roi_polygon_json']));fp=shape(json.loads(i['catalog']['geometry_json']))
    cp=json.loads((BASE/'CPHD_METADATA.json').read_text());stac=json.loads((BASE/'raw/official_stac.json').read_text())
    identity={'collect_id_catalog':ID,'collect_id_sicd':d['CollectionInfo']['Parameters']['collect_id'],
        'collect_id_stac':stac['properties']['umbra:collect_id'],'collector_sicd':compact['collector'],
        'collector_cphd':cp['collector'],'core_name_sicd':compact['core_name'],'core_name_cphd':cp['core_name'],
        'collection_start_sicd':compact['collect_start'],'collection_start_cphd':cp['collection_start'],
        'catalog_center_time':i['catalog']['datetime_utc'],'stac_processing_version':stac['properties']['processing:version'],
        'sicd_processing_software':compact['processing_software']}
    identity['association_verified']=identity['collect_id_sicd']==ID==identity['collect_id_stac'] and compact['core_name']==cp['core_name'] and compact['collect_start']==cp['collection_start'] and compact['collector']==cp['collector']
    if not identity['association_verified']:raise ValueError('Metadata identity mismatch')
    dump(BASE/'IDENTITY.json',identity)
    hae=float(s.GeoData.SCP.LLH.HAE);scp=s.ImageData.SCPPixel.get_array()
    rc=np.array([roi.centroid.y,roi.centroid.x,hae]);center,res,it=s.project_ground_to_image_geo(rc)
    axes_scp=projected_axes(s,scp,hae);axes_roi=projected_axes(s,center,hae)
    g=[roi_projection(s,roi,h,n) for h,n in [(hae,9),(hae,33),(0.,33)]]
    corners=Polygon([(v.Lon,v.Lat) for v in s.GeoData.ImageCorners]);valid_geo=Polygon([(v.Lon,v.Lat) for v in s.GeoData.ValidData]);fwd,_=local_projection(roi.centroid.x,roi.centroid.y)
    rp=transform(fwd,roi);vg=transform(fwd,valid_geo);full=transform(fwd,corners)
    roi_audit={'original_roi_unchanged':True,'roi_polygon_geojson':json.loads(r['roi_polygon_json']),
        'catalog_footprint_contains_roi':fp.covers(roi),'sicd_image_corners_contain_roi':corners.covers(roi),
        'sicd_geo_ValidData_contains_roi':valid_geo.covers(roi),'sicd_geo_valid_edge_margin_m':rp.distance(vg.boundary),
        'sicd_image_corner_edge_margin_m':rp.distance(full.boundary),'projections':g,
        'surface_assumption':'WGS84 constant HAE at SCP; HAE=0 sensitivity is NOT an asserted sea-level/tidal datum',
        'preexisting_mask_coast_margin_evidence':{'source':r['coastline_source'],'roi_land_overlap_m2':r['roi_land_overlap_m2'],
            'queue_coast_center_distance_m':r['coast_distance_m'],'mask_does_not_certify_current_coast_or_cleanliness':True}}
    dump(BASE/'ROI_VALID_SUPPORT.json',roi_audit)
    # Actual surface range LOS differs from the coordinate push-forward in squint geometry.
    arp=s.Position.ARPPoly(float(s.SCPCOA.SCPTime))
    from sarpy.geometry.geocoords import geodetic_to_ecf
    def local_los(lat,lon):
        ll=np.array([lat,lon,hae]);v=arp-geodetic_to_ecf(ll);la,lo=math.radians(lat),math.radians(lon)
        east=np.array([-math.sin(lo),math.cos(lo),0]);north=np.array([-math.sin(la)*math.cos(lo),-math.sin(la)*math.sin(lo),math.cos(la)])
        up=np.array([math.cos(la)*math.cos(lo),math.cos(la)*math.sin(lo),math.sin(la)])
        return {'LOS_towards_sensor_bearing_deg':math.degrees(math.atan2(v@east,v@north))%360,
            'incidence_deg':math.degrees(math.acos(float(v@up/np.linalg.norm(v))))}
    los_roi=local_los(roi.centroid.y,roi.centroid.x);wave=float(r['band_propagation_to_deg'])
    geo={'scpc oa_azimuth_LOS_deg':compact['azimuth_deg'],'scpc oa_incidence_deg':compact['incidence_deg'],
        'grid_Row_UVect_horizontal_projection_bearing_deg':compact['grid_row_ground_bearing_deg'],
        'grid_Col_UVect_horizontal_projection_bearing_deg':compact['grid_col_ground_bearing_deg'],
        'SCP_image_coordinate_pushforward':axes_scp,'ROI_image_coordinate_pushforward':axes_roi,
        'ROI_surface_LOS':los_roi,'surface_HAE_m':hae,
        'vendor_axial_difference_deg':float(r['preliminary_axial_difference_deg']),
        'sicd_GridRow_horizontal_axial_difference_deg':axial(wave,compact['grid_row_ground_bearing_deg']),
        'sicd_surface_LOS_axial_difference_at_ROI_deg':axial(wave,los_roi['LOS_towards_sensor_bearing_deg']),
        'sicd_image_Row_surface_pushforward_axial_difference_at_ROI_deg':axial(wave,axes_roi['row_surface_bearing_deg']),
        'buoy_band_hz':[float(r['band_low_hz']),float(r['band_high_hz'])],'buoy_propagation_to_deg':wave,
        'buoy_direction_is_local_roi_measurement':False,'band_reselected':False,'Snell_applied':False,
        'interpretation':'Horizontal UVect projection is a vector in the local tangent plane, not the same as push-forward of a row-coordinate displacement at constant image Col. For range-aligned scattering use local LOS; for spatial FFT map BOTH coordinate axes/Jacobian, not a rotation alone.'}
    dump(BASE/'GEOMETRY.json',geo)
    context=SicdSubapertureContext.from_sicd(s,cphd_slow_time_dwell_s=cp['first_last_TxTime_span_s']);support=ProcessedSupport.from_axis_metadata(int(s.ImageData.NumCols),context.axis)
    plans=[]
    for label,width,overlap in [('two_nonoverlap',1.4,0.),('three_nonoverlap',.95,0.),('two_overlapping',1.8,.5)]:
        bands=plan_tiled_bands(context,support,width,overlap_fraction=overlap)
        bwp=width/context.durations.processed_aperture_duration_s
        plans.append({'label':label,'nominal_look_s':width,'overlap_fraction':overlap,'look_count':len(bands),
            'bands':[asdict(b) for b in bands],'col_resolution_scale_approx':1/bwp,
            'col_impulse_width_image_plane_m_approx':float(s.Grid.Col.ImpRespWid)/bwp,
            'col_impulse_width_surface_m_approx':float(s.Grid.Col.ImpRespWid)/bwp*axes_roi['col_ground_m_per_pixel']/float(s.Grid.Col.SS),
            'timing_model':'nominal_linear_bandwidth_to_processed_time; not PVP validated',
            'statistically_independent':False,'disjoint_Doppler_support':overlap==0,
            'resolution_caveat':'Uniform native weighting; estimates scale full impulse width by reciprocal retained fraction; smooth windows further broaden. Not a measured sublook PSF.'})
    dump(BASE/'SUBAPERTURE_METADATA_AND_PLANS.json',{'context':asdict(context),'support':asdict(support),'plans':plans,
        'PFA':d['PFA'],'Grid':d['Grid'],'Timeline':d['Timeline'],'ImageFormation':d['ImageFormation'],
        'nominal_timing_not_exact':True,'numerical_sign_tests_required_and_reused':True,
        'future_physical_mapping':'Use CPHD/PVP TxTime, Tx/RcvPos/Vel, SRPPos and aFDOP over processed support; PFA PolarAngPoly provides geometric check. Three TxTime samples do not validate full mapping.',
        'full_azimuth_requirement':'Read full Col extent per range chunk before Doppler decomposition; preserve and propagate oblique ValidData mask. Quantify edge/invalid-data leakage before phase interpretation; do not pre-cut the 1500m ROI.'})
    dump(BASE/'SICD_METADATA.json',{'compact':compact,'full_metadata':d})
    listing=json.loads((BASE/'PUBLIC_LISTING_INVENTORY.json').read_text())
    dump(BASE/'PREVIEW_ASSESSMENT.json',{'official_small_preview_advertised':False,
        'source':'recovered official STAC plus complete cached public-prefix listing',
        'large_GEC_size_bytes':next(int(x['size_bytes']) for x in listing['assets'] if x['key'].endswith('_GEC.tif')),
        'large_SIDD_size_bytes':next(int(x['size_bytes']) for x in listing['assets'] if x['key'].endswith('_SIDD.nitf')),
        'private_COG_overview_not_verified_as_small_public_asset':True,'wave_structure_status':'not_evaluable_no_small_official_preview','preview_downloaded':False})
    state=json.loads((BASE/'STATE.json').read_text());state['stage']='CHECKPOINT_28';dump(BASE/'STATE.json',state)
    summary={'status':'CHECKPOINT_28','decision':'B','decision_reason':'Metadata pathway feasible, but validate squinted PFA Doppler–PVP timing and oblique valid-support leakage before interpreting phase; buoy-to-ROI exposure remains conditional.',
        'SICD_size_bytes':2551099862,'CPHD_size_bytes':cp['size_bytes'],'catalog_duration_s':float(i['catalog']['catalog_duration_s']),
        'SICD_processed_aperture_s':compact['sicd_processed_aperture_s'],'SICD_timeline_collect_duration_s':float(s.Timeline.CollectDuration),
        'SICD_IPP_span_s':max(v.TEnd for v in s.Timeline.IPP)-min(v.TStart for v in s.Timeline.IPP),
        'CPHD_first_last_TxTime_span_s':cp['first_last_TxTime_span_s'],'roi_valid_at_stated_HAE':g[1]['whole_sampled_roi_within_ValidData'],
        'transactions':state['transactions'],'total_bytes':state['total_bytes'],'wave_period_is_observational_not_SAR_estimate':True,
        'no_scientific_validation_claim':True,'automatic_download':False}
    dump(BASE/'SUMMARY.json',summary)
    report=f'''# Samoa — CHECKPOINT_28: preflight complesso

**B. Condizionato alla verifica del mapping Doppler–PVP nel PFA squintato e della leakage del supporto valido obliquo.** I metadati giustificano il percorso tecnico di una prima prova controllata, non una misura fisica già validata né un download automatico. Nessun confronto definitivo con altre zone.

## Identità, asset e durate

Collect `{ID}`, `{i['catalog']['collect_name']}`, Umbra-09, spotlight monostatico right-looking, **H:H**. UUID SICD/STAC, core name SICD/CPHD e CollectStart coincidono; processing Umbra SAR Processor 5.0.20. Catalog datetime è il centro 21:51:37.8Z, non CollectStart 21:51:36Z. Il secondo differente nel basename non indica un'altra acquisizione.

| Quantità | Valore |
|---|---:|
| SICD pubblico, HEAD e FL NITF concordanti | 2.551.099.862 byte |
| CPHD pubblico, HEAD e listing concordanti | {cp['size_bytes']:,} byte |
| Durata catalogo | 3,6 s |
| SICD processed aperture, TEndProc−TStartProc | {compact['sicd_processed_aperture_s']:.9f} s |
| SICD Timeline.CollectDuration | {float(s.Timeline.CollectDuration):.9f} s |
| SICD IPP span | {summary['SICD_IPP_span_s']:.9f} s |
| CPHD TxTime primo–ultimo | {cp['first_last_TxTime_span_s']:.9f} s |

Il CPHD era omesso dall'inventario normalizzato STAC ma presente nel listing pubblico congelato; la discrepanza è documentata, senza modificare il catalogo congelato. Tre campioni TxTime non provano continuità dell'intera serie. NITF: soli header e DES XML esatti; nessun byte di image segment. CPHD: header/XML e tre TxTime da 8 byte; nessun support/signal array.

## Geometria: tre oggetti diversi

Incidenza SCP **{compact['incidence_deg']:.5f}°**, ROI **{los_roi['incidence_deg']:.5f}°** sulla superficie WGS84 HAE dichiarata.

| Asse/direzione | Bearing orientato | Scarto assiale rispetto alla banda boa |
|---|---:|---:|
| Vendor range proxy (away from sensor) | {float(r['local_range_axis_deg']):.5f}° | {geo['vendor_axial_difference_deg']:.5f}° |
| Grid.Row UVect, componente orizzontale ENU allo SCP | {compact['grid_row_ground_bearing_deg']:.5f}° | {geo['sicd_GridRow_horizontal_axial_difference_deg']:.5f}° |
| LOS locale sulla superficie ROI, verso sensore | {los_roi['LOS_towards_sensor_bearing_deg']:.5f}° | {geo['sicd_surface_LOS_axial_difference_at_ROI_deg']:.5f}° |
| Incremento Row a Col costante, push-forward sulla superficie ROI | {axes_roi['row_surface_bearing_deg']:.5f}° | {geo['sicd_image_Row_surface_pushforward_axial_difference_at_ROI_deg']:.5f}° |

SCPCOA.AzimAng={compact['azimuth_deg']:.5f}° è verso sensore; Grid.Row orizzontale punta in senso opposto, dunque stesso asse modulo180. Il push-forward di coordinate immagine non è quella semplice proiezione ENU: in squint/PFA varia anche la geolocalizzazione trasversale. Per trasformare un vettore d'onda della FFT immagine occorre il Jacobiano completo e la sua trasformazione covariante/inversa trasposta, non una sola rotazione. L'allineamento fisico range per lo scattering va distinto dalla direzione di una linea a Col costante. Non si usa il valore più favorevole per scegliere una banda.

## ROI e supporto valido

ROI congelata 1500×1500 m, centro ({r['roi_lat']}, {r['roi_lon']}); contenuta nei corner SICD e nel GeoData.ValidData. Proiezione dell'intero bordo (33 campioni/lato) nel poligono ImageData.ValidData: **{g[1]['whole_sampled_roi_within_ValidData']}**. Margine GeoData valido **{roi_audit['sicd_geo_valid_edge_margin_m']:.2f} m**, margine footprint SICD **{roi_audit['sicd_image_corner_edge_margin_m']:.2f} m**; margine nel piano immagine **{g[1]['minimum_valid_edge_margin_image_plane_m']:.2f} m**, non confuso con distanza al suolo. Residuo massimo proiezione **{g[1]['projection_residual_max_m']:.6f} m**. Convergenza 9/33 campioni e sensibilità HAE=0 salvate.

Superficie nominale: HAE SCP={hae:.5f} m, WGS84 ellissoidale; HAE=0 è solo sensibilità geometrica, **non** quota marina o tidal datum accertati. Maschera costiera Natural Earth 1:10m resta preliminare. ValidData è fortemente obliquo: contenimento della ROI non garantisce uno strip rettangolare interamente valido su tutte le Col. Mantenere intera estensione azimutale prima della FFT e controllare esplicitamente leakage/guard regions e maschera. Nessun crop azimutale preventivo piccolo.

## Riferimento osservativo e anteprima

51209: coordinate storiche riusate ({r['station_lat']}, {r['station_lon']}), osservazione {r['observation_utc']}, offset {float(r['observation_offset_s']):+.1f} s; distanza boa–ROI **{float(r['buoy_roi_distance_m'])/1000:.3f} km**. Banda invariata **{r['band_low_hz']}–{r['band_high_hz']} Hz**, Tp={float(r['peak_period_s']):.5f} s, propagazione **{wave:.5f}°** alla boa. Payload/hash, frequenze, larghezze, momenti e maschere riusati integralmente. Questa non è una misura della direzione nella ROI; nessuna Snell o reselezione.

Nessuna piccola anteprima ufficiale pubblica nel listing/STAC. GEC (~682 MB) e SIDD (~512 MB) non scaricati; overview di TIFF privato non dimostrata asset pubblico piccolo. **Struttura ondosa non valutabile**; nessun prodotto completo per supplire.

## Sottoaperture: poche opzioni, nominali

RGAZIM/SLANT, NumRows={compact['num_rows']}, NumCols={compact['num_cols']}, RE32F_IM32F; Row range axis0, Col Doppler axis1, Col.Sgn=−1: FFT forward/IFFT inverse. DeltaKCOAPoly costante zero, supporto Col {support.start}:{support.stop}, {support.size} bin; weighting UNIFORM, nessuna deweighting SVA da trasferire da Vandenberg. Grid.TimeCOAPoly costante non assegna da sola tempi fisici alle bande; PFA e PVP disponibili per verifica rigorosa successiva.

| Piano | Look nominali | Overlap | Risoluzione Col al suolo approssimata |
|---|---|---|---|
'''
    for p in plans:report+=f"| {p['label']} | {p['look_count']} × {p['nominal_look_s']} s | {p['overlap_fraction']:.0%} | {p['col_impulse_width_surface_m_approx']:.3f} m |\n"
    report+=f'''
Sono piani prodotti dal codice esistente, non look formati. La PSF è stimata scalando la larghezza full-band per frazione conservata e Jacobiano locale; finestre smooth la allargano ancora. La risoluzione resta dell'ordine di 1–2 m rispetto alla ROI di 1500 m, ma questa non è una misura della visibilità delle onde. Nessun gate su un ciclo, dwell minimo o 45° di fase. Bande disgiunte non sono automaticamente repliche statisticamente indipendenti; look sovrapposti sono correlati. Tempi bandwidth/processed-aperture **nominali**, non PVP-validated; non stimata frequenza SAR.

## Budget, limiti e arresto

Nuova tranche distinta: **{state['transactions']}/20 transazioni, {state['total_bytes']}/20971520 byte**, massimo per risposta 5 MiB. Primo probe sandbox fallito e diagnosticato (proxy locale porta9); rete pubblica usata soltanto dopo approvazione del meccanismo di esecuzione autorizzato. Una richiesta METADATA JSON 404 è stata involontariamente ripetuta al resume tecnico per discovery CPHD: entrambi i tentativi sono conservati e conteggiati; il runner ora riusa anche i fallimenti 403/404. Range ignorati respinti prima della lettura del corpo.

Decisione **B**, non validazione: prima di interpretare fase servono mapping Doppler–PVP/PFA e controllo del supporto azimutale obliquo; esposizione/direzione boa–ROI e struttura ondosa rimangono condizionate. I metadati non motivano inversione o nuova frequenza reale. Nessun nuovo SAR completo, formazione, AIS, Block20, Vandenberg, commit o push. Nessun download automatico.
'''
    atomic(BASE/'SAMOA_CARD.md',report.encode('utf-8'))
    manifest()

def manifest():
    artifacts=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(BASE.rglob('*')) if p.is_file() and p.name!='DELIVERY_MANIFEST.json']
    sources=[ROOT/'code/run_block28_samoa_preflight.py',ROOT/'code/umbra_sar/subaperture.py',ROOT/'code/umbra_sar/geographic_preflight.py',ROOT/'code/run_block16a_scene_selection.py',ROOT/'tests/test_block28_samoa_preflight.py']
    dump(BASE/'DELIVERY_MANIFEST.json',{'block':28,'artifacts':artifacts,'code_sources':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in sources]})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['init','probe','remote','analyze','manifest']);args=p.parse_args();initialize()
    if args.stage=='probe':probe()
    elif args.stage=='remote':remote()
    elif args.stage=='analyze':analyze()
    elif args.stage=='manifest':manifest()

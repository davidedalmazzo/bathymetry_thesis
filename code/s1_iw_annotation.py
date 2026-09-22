"""Sentinel-1 IW annotation geometry/support utilities; no raster reads."""
from __future__ import annotations
from datetime import datetime,timezone
import math
import re
import numpy as np
from lxml import etree
from scipy.interpolate import LinearNDInterpolator
from shapely.geometry import Polygon,MultiPolygon,box,mapping,shape
from shapely.ops import unary_union
from frf_client.geometry import inverse


def _nodes(root,name):return root.xpath('.//*[local-name()=$n]',n=name)
def _one(root,name,required=True):
    found=_nodes(root,name)
    if not found:
        if required:raise ValueError('Missing XML field: '+name)
        return None
    text=found[0].text
    if text is None and required:raise ValueError('Empty XML field: '+name)
    return text.strip() if text is not None else None
def _number(root,name,cast=float,required=True):
    value=_one(root,name,required)
    return cast(value) if value is not None else None
def _utc(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    # Sentinel-1 SAFE annotations encode UTC fields without a trailing Z.
    # The field semantics, not the lexical representation, define UTC.
    if result.tzinfo is None:result=result.replace(tzinfo=timezone.utc)
    return result.isoformat()


def parse_int_vector(text,expected):
    values=[int(v) for v in text.split()]
    if len(values)!=expected:raise ValueError(f'Valid-sample vector length {len(values)} != linesPerBurst {expected}')
    return values


def parse_annotation(raw, *, expected_swath=None, expected_polarisation='VV', max_bytes=10*1024**2):
    if not isinstance(raw,(bytes,bytearray)) or not raw or len(raw)>max_bytes:raise ValueError('Unexpected or oversized annotation body')
    parser=etree.XMLParser(resolve_entities=False,no_network=True,remove_comments=False,huge_tree=False)
    try:root=etree.fromstring(raw,parser)
    except etree.XMLSyntaxError as exc:raise ValueError('Malformed annotation XML') from exc
    if etree.QName(root).localname!='product':raise ValueError('Unexpected annotation XML root')
    swath=_one(root,'swath').upper();polarisation=_one(root,'polarisation').upper()
    if expected_swath and swath!=expected_swath.upper():raise ValueError('Subswath identity mismatch')
    if expected_polarisation and polarisation!=expected_polarisation.upper():raise ValueError('Polarisation identity mismatch')
    lines_per=_number(root,'linesPerBurst',int);samples_per=_number(root,'samplesPerBurst',int)
    burst_nodes=_nodes(root,'burst')
    bursts=[]
    for i,node in enumerate(burst_nodes):
        first=parse_int_vector(_one(node,'firstValidSample'),lines_per)
        last=parse_int_vector(_one(node,'lastValidSample'),lines_per)
        valid=[]
        for j,(a,b) in enumerate(zip(first,last)):
            if a==-1 and b==-1:continue
            if not (0<=a<=b<samples_per):raise ValueError('Invalid first/last valid sample interval')
            valid.append([j,a,b])
        bursts.append({'index':i,'line_start':i*lines_per,'line_stop_exclusive':(i+1)*lines_per,
            'azimuth_time':_utc(_one(node,'azimuthTime')),'sensing_time':_utc(_one(node,'sensingTime',False)) if _one(node,'sensingTime',False) else None,
            'byte_offset':_number(node,'byteOffset',int,False),'first_valid_sample':first,'last_valid_sample':last,
            'valid_line_count':len(valid),'valid_intervals':valid})
    if not bursts:raise ValueError('No bursts in annotation')
    points=[]
    for node in _nodes(root,'geolocationGridPoint'):
        point={n:_number(node,n,int if n in ('line','pixel') else float) for n in ('line','pixel','latitude','longitude','height','incidenceAngle','elevationAngle','slantRangeTime')}
        point['azimuthTime']=_utc(_one(node,'azimuthTime'));points.append(point)
    if len(points)<4:raise ValueError('Insufficient geolocation grid')
    output={'mission':_one(root,'missionId',False) or _one(root,'missionDataTakeId',False),
        'product_type':_one(root,'productType',False),'mode':_one(root,'mode'),'swath':swath,'polarisation':polarisation,
        'start_time':_utc(_one(root,'startTime')),'stop_time':_utc(_one(root,'stopTime')),
        'absolute_orbit_number':_number(root,'absoluteOrbitNumber',int,False),
        'mission_data_take_id':_one(root,'missionDataTakeId',False),
        'number_of_lines':_number(root,'numberOfLines',int),'number_of_samples':_number(root,'numberOfSamples',int),
        'range_pixel_spacing_m':_number(root,'rangePixelSpacing'),'azimuth_pixel_spacing_m':_number(root,'azimuthPixelSpacing'),
        'azimuth_time_interval_s':_number(root,'azimuthTimeInterval'),'slant_range_time_s':_number(root,'slantRangeTime'),
        'range_sampling_rate_hz':_number(root,'rangeSamplingRate',float,False),
        'lines_per_burst':lines_per,'samples_per_burst':samples_per,'bursts':bursts,'geolocation_grid':points,
        'axis_order':['azimuth_line','slant_range_sample'],
        'pixel_spacing_scope':'annotation sampling; not effective resolution or geolocated ground spacing'}
    if output['number_of_lines'] < bursts[-1]['line_stop_exclusive']:raise ValueError('Burst lines exceed image dimensions')
    return output


def valid_support(annotation):
    """Exact union of valid per-line pixel cells, grouped without filling gaps."""
    pieces=[];by_burst=[]
    for burst in annotation['bursts']:
        current=[];segments=[]
        for local,a,b in burst['valid_intervals']:
            line=burst['line_start']+local
            cell=box(a-.5,line-.5,b+.5,line+.5);current.append(cell)
            if segments and segments[-1][1]==line and segments[-1][2:]==[a,b]:segments[-1][1]=line+1
            else:segments.append([line,line+1,a,b])
        geometry=unary_union(current) if current else Polygon()
        by_burst.append({'index':burst['index'],'geometry':geometry,'segments':segments,'valid_area_pixels':geometry.area})
        if not geometry.is_empty:pieces.append(geometry)
    return unary_union(pieces) if pieces else Polygon(),by_burst


def burst_support_geojson(annotation,index):
    """Project one burst's exact valid-cell outline through the SAFE GeoGrid."""
    _,items=valid_support(annotation);matches=[x for x in items if x['index']==index]
    if len(matches)!=1 or matches[0]['geometry'].is_empty:raise ValueError('Requested burst has no valid support')
    grid=GeoGrid(annotation);ns=annotation['number_of_samples'];nl=annotation['number_of_lines']
    def ring(coords):
        result=[]
        for sample,line in coords:
            point=grid.image_to_geo(min(max(sample,0),ns-1),min(max(line,0),nl-1))
            if not np.isfinite(sum(point)):raise ValueError('Burst support outside geolocation interpolation')
            result.append(point)
        return result
    geom=matches[0]['geometry'];polygons=[geom] if isinstance(geom,Polygon) else list(geom.geoms) if isinstance(geom,MultiPolygon) else []
    if not polygons:raise ValueError('Unsupported burst support geometry')
    projected=[Polygon(ring(p.exterior.coords),[ring(x.coords) for x in p.interiors]) for p in polygons]
    output=projected[0] if len(projected)==1 else MultiPolygon(projected)
    return mapping(output)


class GeoGrid:
    """DEPRECATED for IW SLC (kept only to reproduce frozen Blocks 36-37).

    Interpolates the geolocation grid in *line number*; IW grid rows sit at burst
    starts and bursts overlap in time, so azimuth time is compressed by ~12 % and
    pixels are misplaced by up to ~1.5 km.  Use s1_iw_geometry.SwathGeometry.
    See docs/NOTE_S1_GEOLOCATION_BURST_TIME.md."""
    def __init__(self,annotation):
        import warnings
        warnings.warn("s1_iw_annotation.GeoGrid interpolates IW geolocation in line number and is wrong for "
                      "multi-burst SLC; use s1_iw_geometry.SwathGeometry (Block38 geolocation fix)",
                      DeprecationWarning,stacklevel=2)
        p=annotation['geolocation_grid'];image=np.array([[x['pixel'],x['line']] for x in p],float)
        geo=np.array([[x['longitude'],x['latitude']] for x in p],float)
        self.forward_lon=LinearNDInterpolator(image,geo[:,0]);self.forward_lat=LinearNDInterpolator(image,geo[:,1])
        self.inverse_sample=LinearNDInterpolator(geo,image[:,0]);self.inverse_line=LinearNDInterpolator(geo,image[:,1])
        self.incidence=LinearNDInterpolator(image,np.array([x['incidenceAngle'] for x in p]))
    def image_to_geo(self,sample,line):return float(self.forward_lon(sample,line)),float(self.forward_lat(sample,line))
    def geo_to_image(self,lon,lat):return float(self.inverse_sample(lon,lat)),float(self.inverse_line(lon,lat))


def densify_polygon(geometry,n=16):
    coords=list(geometry.exterior.coords);points=[]
    for a,b in zip(coords[:-1],coords[1:]):
        points.extend([(a[0]+(b[0]-a[0])*t/n,a[1]+(b[1]-a[1])*t/n) for t in range(n)])
    return points


def roi_support(annotation,roi_geojson,edge_samples=16):
    roi=shape(roi_geojson);grid=GeoGrid(annotation)
    image=[]
    for lon,lat in densify_polygon(roi,edge_samples):
        sample,line=grid.geo_to_image(lon,lat)
        if not np.isfinite(sample+line):return {'subswath':annotation['swath'],'inside_geolocation_support':False,'valid_fraction':0.,'status':'roi_outside_geolocation_grid'}
        image.append((sample,line))
    roi_image=Polygon(image)
    if not roi_image.is_valid or roi_image.area<=0:raise ValueError('ROI inverse mapping is invalid')
    support,burst_support=valid_support(annotation)
    intersections=[]
    for item in burst_support:
        area=roi_image.intersection(item['geometry']).area
        if area>0:intersections.append({'burst_index':item['index'],'intersection_area_image_pixels':area,
                                        'fraction_of_roi_image_area':area/roi_image.area})
    valid=roi_image.intersection(support).area/roi_image.area
    return {'subswath':annotation['swath'],'inside_geolocation_support':True,'roi_image_polygon':mapping(roi_image),
        'roi_image_area_pixels':roi_image.area,'valid_fraction':valid,'burst_intersections':intersections,
        'fully_valid':valid>=1-1e-9,'single_valid_burst':valid>=1-1e-9 and len(intersections)==1,
        'crosses_burst_join':len(intersections)>1,
        'join_treatment':'none' if valid>=1-1e-9 and len(intersections)==1 else 'do not duplicate overlap; split/window only on each valid support and compare, or declare unavailable'}


def _local_en(origin,point):
    distance,bearing=inverse(*origin,*point);r=math.radians(bearing)
    return np.array([distance*math.sin(r),distance*math.cos(r)])


def local_geometry(annotation,roi_geojson,delta=1.):
    roi=shape(roi_geojson);center=(roi.centroid.x,roi.centroid.y);grid=GeoGrid(annotation)
    sample,line=grid.geo_to_image(*center)
    if not np.isfinite(sample+line):raise ValueError('ROI center outside geolocation grid')
    c=np.array(grid.image_to_geo(sample,line));sp=np.array(grid.image_to_geo(sample+delta,line));sm=np.array(grid.image_to_geo(sample-delta,line))
    lp=np.array(grid.image_to_geo(sample,line+delta));lm=np.array(grid.image_to_geo(sample,line-delta))
    j=np.column_stack(((_local_en(c,sp)-_local_en(c,sm))/(2*delta),(_local_en(c,lp)-_local_en(c,lm))/(2*delta)))
    if abs(np.linalg.det(j))<1e-9:raise ValueError('Singular local image-ground Jacobian')
    incidence=float(grid.incidence(sample,line));inc_boundary=[]
    for lon,lat in densify_polygon(roi,8):
        s,l=grid.geo_to_image(lon,lat)
        if np.isfinite(s+l):inc_boundary.append(float(grid.incidence(s,l)))
    bearings=[]
    for vector in j.T:
        bearing=math.degrees(math.atan2(vector[0],vector[1]))%360
        bearings.append(0. if math.isclose(bearing,360.,abs_tol=1e-9) else bearing)
    return {'evaluation_lon_lat':list(center),'evaluation_sample_line':[sample,line],
        'axis_order':['slant_range_sample','azimuth_line'],'jacobian_EN_m_per_pixel':j.tolist(),
        'determinant_m2_per_pixel2':float(np.linalg.det(j)),'ground_spacing_sample_line_m':[float(np.linalg.norm(j[:,0])),float(np.linalg.norm(j[:,1]))],
        'range_sample_bearing_deg':bearings[0],'azimuth_line_bearing_deg':bearings[1],
        'incidence_center_deg':incidence,'incidence_boundary_min_max_deg':[min(inc_boundary),max(inc_boundary)],
        'slant_range_pixel_spacing_m':annotation['range_pixel_spacing_m'],'azimuth_pixel_spacing_m':annotation['azimuth_pixel_spacing_m'],
        'effective_resolution':'not equated to pixel spacing; requires verified processing resolution metadata/response',
        'wavenumber_transform':'[k_east,k_north] = inverse(J).T @ [q_sample,q_line], q in rad/pixel',
        'fft_convention':'numpy fft2 forward negative exponent; fftshift(fftfreq); cycles/pixel times 2*pi',
        'direction_convention':'bearing clockwise from true north; axial comparisons modulo 180'}


def transform_k(q_sample,q_line,jacobian):
    j=np.asarray(jacobian,float)
    if j.shape!=(2,2) or abs(np.linalg.det(j))<1e-12:raise ValueError('Invertible 2x2 Jacobian required')
    k=np.linalg.solve(j.T,np.array([q_sample,q_line],float))
    bearing=math.degrees(math.atan2(k[0],k[1]))%360
    return {'k_east_rad_m':float(k[0]),'k_north_rad_m':float(k[1]),'magnitude_rad_m':float(np.linalg.norm(k)),
            'bearing_toward_deg':bearing,'axial_bearing_deg':bearing%180}


def axial_difference(a,b):return abs((a-b+90)%180-90)


def validate_xml_payload(raw,expected_name,declared_length,max_bytes=10*1024**2):
    if not expected_name.lower().endswith('.xml') and expected_name!='manifest.safe':raise ValueError('Only manifest/XML metadata content allowed')
    if not isinstance(declared_length,int) or declared_length<=0 or declared_length>max_bytes:raise ValueError('Unexpected or excessive declared metadata length')
    if len(raw)!=declared_length or len(raw)>max_bytes:raise ValueError('Metadata body length mismatch or excessive response')
    stripped=raw.lstrip()
    if not stripped.startswith(b'<'):raise ValueError('Unexpected non-XML body')
    return True


def validate_manifest(raw,expected_annotation_names):
    parser=etree.XMLParser(resolve_entities=False,no_network=True,huge_tree=False)
    try:root=etree.fromstring(raw,parser)
    except etree.XMLSyntaxError as exc:raise ValueError('Malformed manifest XML') from exc
    if etree.QName(root).localname.lower()!='xfdu':raise ValueError('Unexpected manifest root')
    hrefs={node.get('href','').replace('\\','/').removeprefix('./') for node in root.xpath('.//*[local-name()="fileLocation"]')}
    missing=[name for name in expected_annotation_names if 'annotation/'+name not in hrefs]
    if missing:raise ValueError('Manifest does not reference expected annotations: '+','.join(missing))
    return {'root':etree.QName(root).localname,'referenced_files':sorted(hrefs),'expected_annotations_present':True}

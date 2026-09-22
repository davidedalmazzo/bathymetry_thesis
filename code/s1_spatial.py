"""Pure metadata and analytic diagnostics; no SAR pixel reader or inversion."""
from datetime import datetime
from urllib.parse import urlsplit
import re
import numpy as np
from shapely.geometry import shape, mapping
from shapely import wkt
from shapely.ops import transform
from frf_client.geometry import inverse


def utc(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timezone required')
    return dt


def next_page(page):
    url = next((v for k,v in page.items() if k.lower() == '@odata.nextlink'), None)
    if url:
        p = urlsplit(url)
        if p.scheme != 'https' or p.hostname != 'catalogue.dataspace.copernicus.eu' or p.path != '/odata/v1/Products':
            raise ValueError('Unexpected pagination endpoint')
    return url


def catalogue_pages(transport, url):
    seen=set()
    while url:
        if url in seen:raise ValueError('Pagination cycle')
        seen.add(url)
        import json
        page=json.loads(transport.get(url))
        if not isinstance(page.get('value'),list):raise ValueError('Missing catalogue value list')
        yield {'url':url,'payload':page}
        url=next_page(page)


def deduplicate_entries(entries):
    unique={}; duplicates=[]
    for entry in entries:
        key=entry['Id']
        if key in unique:
            if unique[key]!=entry:raise ValueError('Conflicting catalogue UUID duplicate')
            duplicates.append(key)
        else:unique[key]=entry
    return list(unique.values()), duplicates


def axial_difference(a, b):
    return abs((a-b+90) % 180-90)


def quicklook_url(asset):
    expected='https://catalogue.dataspace.copernicus.eu/odata/v1/Assets('+str(asset.get('Id'))+')/$value'
    if asset.get('Type')!='QUICKLOOK' or asset.get('DownloadLink')!=expected:
        raise ValueError('Only the documented official quicklook Asset endpoint is allowed')
    return expected


def normalize(entry, marine):
    attrs = {a['Name']:a.get('Value') for a in entry.get('Attributes', [])}
    geo = entry.get('GeoFootprint')
    if geo:
        footprint = shape(geo)
    elif entry.get('Footprint'):
        text = re.sub(r"^geography'SRID=4326;", '', entry['Footprint']).rstrip("'")
        footprint = wkt.loads(text)
        geo = mapping(footprint)
    else:
        footprint = None
    if footprint is not None and (footprint.geom_type not in ('Polygon','MultiPolygon') or not footprint.is_valid):
        raise ValueError('Invalid catalogue footprint')
    date = entry.get('ContentDate', {})
    start, end = date.get('Start'), date.get('End')
    if start:utc(start)
    if end:utc(end)
    coverage, proxy = None, None
    if footprint is not None:
        # Local cylindrical equal-area screening, not a SAR geolocation model.
        lat0 = shape(marine).centroid.y
        def projector(x,y,z=None):
            return (6371008.8*np.radians(x)*np.cos(np.radians(lat0)),
                    6371008.8*np.sin(np.radians(y))/np.cos(np.radians(lat0)))
        area = transform(projector, shape(marine))
        coverage = transform(projector, footprint).intersection(area).area/area.area
        polys = [footprint] if footprint.geom_type == 'Polygon' else list(footprint.geoms)
        edges = []
        for poly in polys:
            coords = list(poly.exterior.coords)
            for a,b in zip(coords[:-1],coords[1:]):
                length, bearing = inverse(*a,*b)
                edges.append((length, bearing % 180))
        if edges:proxy = max(edges)[1]
    name = entry.get('Name','')
    match = re.search(r'(S1[ABCD])_IW_SLC__\w+_(\d{8}T\d{6})_(\d{8}T\d{6})_(\d+)_(\w+)_', name)
    key = '|'.join((match[1],match[4],match[5])) if match else entry['Id']
    slice_key = '|'.join(match.groups()) if match else entry['Id']
    return {'uuid':entry['Id'], 'name':name, 'acquisition_key':key, 'slice_key':slice_key,
        'platform':str(attrs.get('platformShortName',''))+'-'+str(attrs.get('platformSerialIdentifier','')),
        'mode':attrs.get('operationalMode'), 'product_type':attrs.get('productType'),
        'polarisation':attrs.get('polarisationChannels'), 'start_utc':start, 'end_utc':end,
        'timestamp_semantics':'catalogue ContentDate start/end; not local ROI sensing time',
        'relative_orbit':attrs.get('relativeOrbitNumber'), 'absolute_orbit':attrs.get('orbitNumber'),
        'orbit_direction':attrs.get('orbitDirection'), 'slice_number':attrs.get('sliceNumber'),
        'bytes':entry.get('ContentLength'), 'online':entry.get('Online'),
        'processing_version':attrs.get('processingVersion'), 'modification_utc':entry.get('ModificationDate'),
        'publication_utc':entry.get('PublicationDate'), 'origin_utc':entry.get('OriginDate'),
        'footprint':geo, 'marine_screening_fraction':coverage,
        'range_edge_proxy_axial_deg':proxy,
        'range_proxy_status':'longest footprint edge only; NOT local projected SAR range',
        'local_range_deg':None, 'local_incidence_deg':None, 'checksums_vendor':entry.get('Checksum'),
        'assets':entry.get('Assets'), 's3_path':entry.get('S3Path')}


def representatives(rows):
    versions={}
    for row in rows:versions.setdefault(row.get('slice_key',row['acquisition_key']), []).append(row)
    latest=[max(group,key=lambda r:(r['online'] is True,r['modification_utc'] or '',r['uuid'])) for group in versions.values()]
    passes={}
    for row in latest:passes.setdefault(row['acquisition_key'], []).append(row)
    return [max(group,key=lambda r:(r['online'] is True,r['marine_screening_fraction'] or 0,
                                   r['modification_utc'] or '',r['uuid'])) for group in passes.values()]


def dispersion_sensitivity(k, h, g=9.80665):
    if k <= 0 or h <= 0:raise ValueError('Positive k and h required')
    u = k*h
    omega = np.sqrt(g*k*np.tanh(u))
    cg = g*(np.tanh(u)+u/np.cosh(u)**2)/(2*omega)
    return {'omega_rad_s':float(omega), 'group_velocity_m_s':float(cg),
        'dh_dk_fixed_omega_m2':float(-(np.sinh(2*u)/2+u)/k**2),
        'dh_domega_fixed_k_m_s':float(2*omega*np.cosh(u)**2/(g*k**2))}

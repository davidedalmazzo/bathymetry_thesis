"""WGS84 ellipsoidal distances without optional global geospatial packages."""
import math
from scipy.optimize import minimize_scalar
from shapely.geometry import Point, shape, mapping


def inverse(lon1, lat1, lon2, lat2):
    """Vincenty WGS84 inverse; refuse nonconvergence instead of spherical fallback."""
    a, flattening = 6378137., 1/298.257223563
    b = a * (1-flattening)
    u1, u2 = math.atan((1-flattening)*math.tan(math.radians(lat1))), math.atan((1-flattening)*math.tan(math.radians(lat2)))
    su1, cu1, su2, cu2 = math.sin(u1),math.cos(u1),math.sin(u2),math.cos(u2)
    delta = math.radians(lon2-lon1)
    lam = delta
    for _ in range(200):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.hypot(cu2*sl, cu1*su2-su1*cu2*cl)
        if ss == 0:
            return 0., None
        cs = su1*su2+cu1*cu2*cl
        sigma = math.atan2(ss,cs)
        sa = cu1*cu2*sl/ss
        ca2 = 1-sa*sa
        c2sm = cs-2*su1*su2/ca2 if ca2 > 1e-16 else 0.
        c = flattening/16*ca2*(4+flattening*(4-3*ca2))
        old = lam
        lam = delta+(1-c)*flattening*sa*(sigma+c*ss*(c2sm+c*cs*(-1+2*c2sm*c2sm)))
        if abs(lam-old) < 1e-12:
            break
    else:
        raise ValueError("WGS84 inverse did not converge")
    usq = ca2*(a*a-b*b)/(b*b)
    aa = 1+usq/16384*(4096+usq*(-768+usq*(320-175*usq)))
    bb = usq/1024*(256+usq*(-128+usq*(74-47*usq)))
    ds = bb*ss*(c2sm+bb/4*(cs*(-1+2*c2sm*c2sm)-bb/6*c2sm*(-3+4*ss*ss)*(-3+4*c2sm*c2sm)))
    bearing = math.degrees(math.atan2(cu2*math.sin(lam),cu1*su2-su1*cu2*math.cos(lam))) % 360
    return b*aa*(sigma-ds), bearing


def polygon(value):
    if value is None:
        return None
    if value.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("WGS84 Polygon/MultiPolygon required")
    if "crs" in value:
        raise ValueError("GeoJSON uses WGS84 lon/lat; custom CRS not supported")
    geo = shape(value)
    if geo.is_empty or not geo.is_valid:
        raise ValueError("Empty or invalid polygon")
    if not (-180 <= geo.bounds[0] <= geo.bounds[2] <= 180 and -90 <= geo.bounds[1] <= geo.bounds[3] <= 90):
        raise ValueError("Coordinates must be longitude, latitude in WGS84")
    if geo.bounds[2]-geo.bounds[0] > 180:
        raise ValueError("Antimeridian polygons require explicit split")
    return geo


def distances(position, geo):
    if position is None or geo is None:
        return {"status": "not_evaluable", "center_m": None, "minimum_m": None, "inside": None, "bearing_deg": None}
    lon, lat = position
    center = geo.centroid
    center_m, bearing = inverse(lon,lat,center.x,center.y)
    inside = geo.covers(Point(lon,lat))
    minimum = 0.
    if not inside:
        candidates = []
        polys = [geo] if geo.geom_type == "Polygon" else list(geo.geoms)
        for poly in polys:
            for ring in [poly.exterior] + list(poly.interiors):
                coords = list(ring.coords)
                for p, q in zip(coords[:-1],coords[1:]):
                    fn = lambda t: inverse(lon,lat,p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1]))[0]
                    fit = minimize_scalar(fn, bounds=(0,1), method="bounded", options={"xatol": 1e-10})
                    candidates.extend([fn(0),fn(1),fit.fun])
        minimum = min(candidates)
    return {"status": "computed_conditioned_on_historical_position", "center_m": center_m,
            "minimum_m": minimum, "inside": inside, "bearing_deg": bearing,
            "method": "WGS84 Vincenty inverse; closest point on GeoJSON linear lon/lat boundary",
            "center_definition": "geometric lon/lat polygon centroid, not SAR aperture center"}

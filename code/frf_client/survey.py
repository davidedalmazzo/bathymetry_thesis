"""Bounded optional survey adapter; never equate bounding boxes with measured seabed."""
import re
from datetime import datetime
import numpy as np
from shapely.geometry import Point
from .catalog import catalog, metadata
from .data import ascii_arrays, mask_values, cf_times
from .geometry import polygon, distances
from .transport import FetchError


def inventory(transport, survey_catalog_url, timestamp):
    parent=catalog(transport,survey_catalog_url)
    data=next((r for r in parent["references"] if r["name"]=="data"),None)
    if data is None:
        return {"status":"unsupported_survey_catalog_layout","products":parent["products"],"survey_coverage":"not verified"}
    listed=catalog(transport,data["url"])
    year=next((r for r in listed["references"] if r["name"]==timestamp[:4]),None)
    if year:
        listed=catalog(transport,year["url"])
    entries=[]
    for p in listed["products"]:
        match=re.search(r"(?<!\d)(20\d{6})(?!\d)",p["name"] or "")
        date=datetime.strptime(match[1],"%Y%m%d").date().isoformat() if match else None
        entries.append({**p,"candidate_date_from_filename":date,"date_status":"not verified against survey metadata",
                        "measured_coverage":None,"survey_method":None,"resolution":None,"uncertainty":None,
                        "horizontal_datum":None,"vertical_datum":None})
    return {"status":"catalog_inventory_only","products":entries,
            "survey_coverage":"no line/point coverage asserted; no bounding-box substitution"}


def fetch_points(transport, product, selection, region):
    """Opt-in point-vector subset with caller-declared bounded index range.

    Refuse unknown layouts, no spatial selector, full products or >5000 points.
    Returned coverage is measured points only; does not invent connecting lines.
    """
    geo=polygon(region)
    if geo is None:
        raise ValueError("ROI/footprint required for survey download")
    lo,hi=selection
    if not isinstance(lo,int) or not isinstance(hi,int) or lo<0 or hi<lo or hi-lo+1>5000:
        raise ValueError("Explicit verified point-index range, maximum 5000 points")
    meta=metadata(transport,product)
    attrs,shapes=meta["attributes"],meta["shapes"]
    names={role:next((name for name in shapes if name.lower() in choices),None) for role,choices in {
        "latitude":("latitude","lat"),"longitude":("longitude","lon"),"elevation":("elevation","z","depth")}.items()}
    if any(v is None for v in names.values()):
        raise FetchError("unsupported_survey_coordinates")
    dimensions=[shapes[name] for name in names.values()]
    if not all(len(d)==1 and d==dimensions[0] and hi<d[0] for d in dimensions):
        raise FetchError("unsupported_survey_point_dimensions")
    query=",".join(f"{name}[{lo}:1:{hi}]" for name in names.values())
    arrays=ascii_arrays(transport.get(meta["source"]+".ascii?"+query).decode())
    valid=np.ones(hi-lo+1,bool)
    for name in names.values(): valid &= mask_values(arrays[name],attrs.get(name,{}))
    points=[]
    for j in np.flatnonzero(valid):
        lon,lat=float(arrays[names["longitude"]][j]),float(arrays[names["latitude"]][j])
        if not (-180<=lon<=180 and -90<=lat<=90):
            continue
        if geo.covers(Point(lon,lat)):
            points.append({"source_index":lo+int(j),"lon":lon,"lat":lat,"elevation_original":float(arrays[names["elevation"]][j])})
    return {"metadata":meta,"points":points,"selection":selection,"download_scope":"bounded declared point indices; points outside polygon excluded, not interpreted",
            "actual_point_count_inside":len(points),"footprint_intersection":bool(points),
            "coverage":"measured points only; lines and continuous seabed coverage not inferred",
            "horizontal_datum":"source coordinate metadata, unconverted",
            "vertical_datum":meta["attributes"].get("NC_GLOBAL",{}).get("geospatial_vertical_origin")}

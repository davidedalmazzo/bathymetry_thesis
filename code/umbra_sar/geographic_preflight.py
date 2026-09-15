"""Geometry and bounded-I/O primitives for Block22."""
from __future__ import annotations
import math
from dataclasses import dataclass
from urllib.request import Request, build_opener, HTTPRedirectHandler
from shapely.geometry import Point
from shapely.ops import transform

R=6371008.8

def local_projection(lon0,lat0):
    c=max(math.cos(math.radians(lat0)),1e-8)
    def forward(x,y,z=None): return R*c*math.radians(x-lon0),R*math.radians(y-lat0)
    def inverse(x,y,z=None): return lon0+math.degrees(x/(R*c)),lat0+math.degrees(y/R)
    return forward,inverse

def geographic_metrics(footprint,roi,coastlines,buoy_lon,buoy_lat):
    """Distances in a common local metric plane; coastlines must be un-clipped."""
    center=roi.centroid; fwd,_=local_projection(center.x,center.y)
    fp=transform(fwd,footprint); rp=transform(fwd,roi)
    coast=transform(fwd,coastlines); buoy=transform(fwd,Point(buoy_lon,buoy_lat)); rc=rp.centroid
    return {
      "roi_center_to_coast_m":rc.distance(coast),
      "roi_polygon_to_coast_m":rp.distance(coast),
      "roi_center_to_footprint_edge_m":rc.distance(fp.boundary),
      "roi_polygon_to_footprint_edge_m":rp.distance(fp.boundary),
      "buoy_to_roi_center_m":buoy.distance(rc),
      "buoy_to_roi_polygon_m":buoy.distance(rp),
      "roi_within_footprint":fp.covers(rp),
      "roi_disjoint_from_land_boundary":rp.disjoint(coast),
    }

def affine_pixel_to_lonlat(matrix,col,row):
    if len(matrix)!=16: raise ValueError("4x4 model transformation required")
    return matrix[0]*col+matrix[1]*row+matrix[3], matrix[4]*col+matrix[5]*row+matrix[7]

def scale_bar_length(extent_m):
    target=max(extent_m/5,1); power=10**math.floor(math.log10(target))
    return max(x*power for x in (1,2,5,10) if x*power<=target)

@dataclass
class RangeBudget:
    max_transactions:int=60; max_total_bytes:int=50*1024**2; max_response_bytes:int=10*1024**2
    transactions:int=0; total_bytes:int=0
    def reserve(self,n):
        if self.transactions>=self.max_transactions: raise RuntimeError("transaction budget exceeded")
        self.transactions+=1
        if n>self.max_response_bytes or self.total_bytes+n>self.max_total_bytes: raise RuntimeError("byte budget exceeded")
        self.total_bytes+=n

def validate_partial_response(status,content_range,requested_start,requested_end,received):
    expected=requested_end-requested_start+1
    if status!=206 or not content_range or not content_range.startswith(f"bytes {requested_start}-{requested_end}/"):
        raise RuntimeError("server did not honor exact byte range")
    if received!=expected: raise RuntimeError("partial response length mismatch")
    return True

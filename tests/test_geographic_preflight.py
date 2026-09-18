import numpy as np
import pytest
from shapely.geometry import box,LineString
from umbra_sar.geographic_preflight import geographic_metrics,affine_pixel_to_lonlat,scale_bar_length,RangeBudget,validate_partial_response

def test_unclipped_coast_external_to_footprint_is_measured():
 fp=box(-.01,-.01,.01,.01);roi=box(-.002,-.002,.002,.002);coast=LineString([(.02,-.1),(.02,.1)])
 m=geographic_metrics(fp,roi,coast,0,0);assert m["roi_center_to_coast_m"]>m["roi_polygon_to_coast_m"]>0

def test_center_distance_differs_from_polygon_clearance():
 m=geographic_metrics(box(-1,-1,1,1),box(-.01,-.01,.01,.01),LineString([(.1,-1),(.1,1)]),0,0)
 assert m["roi_center_to_coast_m"]>m["roi_polygon_to_coast_m"]

def test_polygon_containment_not_just_center():
 m=geographic_metrics(box(-.01,-.01,.01,.01),box(-.005,-.005,.02,.005),LineString([(.1,-1),(.1,1)]),0,0)
 assert not m["roi_within_footprint"]

def test_footprint_edge_separate_from_coast():
 m=geographic_metrics(box(-.01,-.01,.01,.01),box(-.002,-.002,.002,.002),LineString([(.1,-1),(.1,1)]),0,0)
 assert m["roi_polygon_to_footprint_edge_m"]!=m["roi_polygon_to_coast_m"]

def test_gec_affine_known_origin_and_step():
 m=[2,3,0,10,4,5,0,20,0,0,0,0,0,0,0,1]
 assert affine_pixel_to_lonlat(m,2,1)==(17,33)

def test_scale_bar_is_metric_nice_number():
 assert scale_bar_length(12000)==2000

def test_budget_and_exact_range_enforced():
 b=RangeBudget(max_transactions=1,max_total_bytes=10,max_response_bytes=8);b.reserve(8)
 with pytest.raises(RuntimeError):b.reserve(1)
 assert validate_partial_response(206,"bytes 10-19/100",10,19,10)
 with pytest.raises(RuntimeError):validate_partial_response(200,None,10,19,10)

def test_finalists_keep_actual_reference_ids():
 import csv,pathlib
 root=pathlib.Path(__file__).resolve().parents[1]
 with (root/'umbra/selezione_scene/Block21_frequency_validation_selector/BLOCK21_SHORTLIST.csv').open() as f:r=list(csv.DictReader(f))
 assert [x["station_id"] for x in r]==["46268","46268","46256","44087","46256"]

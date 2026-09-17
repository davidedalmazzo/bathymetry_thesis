import io
import json
import math
import urllib.error
from pathlib import Path
import numpy as np
import pytest
from frf_client.data import utc, cf_times, ascii_arrays, das_attributes, mask_values, qc_pass, associate, toward, circular_mean, spectral_summary
from frf_client.geometry import polygon, distances, inverse
from frf_client.inputs import validate, read_acquisitions, adapt_eoweb
from frf_client.client import historical_position, qc_variable
from frf_client.transport import Transport, FetchError, safe_url, digest


def test_explicit_timezone_and_signed_offset():
    assert utc("2021-10-14T01:00:15.669+02:00").isoformat()=="2021-10-13T23:00:15.669000+00:00"
    with pytest.raises(ValueError): utc("2021-10-13T23:00:00")
    t=utc("2021-10-13T23:00:15.669Z").timestamp()
    assert associate([t-15.669,t+1800],t,[True,True],3600)["offset_seconds"] == pytest.approx(-15.669,abs=1e-6)
    assert cf_times([60],"seconds since 1970-01-01 00:00:00")[0] == 60


def test_previous_next_interval_and_qc():
    result=associate([0,10,20],12,[True,False,True],5,[[0,4],[8,12],[18,22]])
    assert result["previous"]==0 and result["next"]==2 and result["nearest"]==2
    assert not result["within_tolerance"] and result["interval_distance_seconds"]==6
    assert associate([10],12,[True],5,[[8,14]])["interval_distance_seconds"]==0


def test_direction_no_empirical_correction():
    assert toward(59.25528,"from_true_north")==pytest.approx(239.25528)
    assert toward(239.25528,"toward_true_north")==pytest.approx(239.25528)
    assert min(circular_mean([359,1]),360-circular_mean([359,1]))<1e-10
    assert circular_mean([90,270]) is None
    with pytest.raises(ValueError): toward(70,"local_undefined")


def test_missing_and_qc_are_variable_specific():
    assert mask_values([1,-999,np.nan],{"_FillValue":-999}).tolist()==[True,False,False]
    assert mask_values([-999,-999.99],{"_FillValue":-999.99}).tolist()==[True,False]
    assert qc_pass([1,3,4,-99],{"_FillValue":-99}).tolist()==[True,False,False,False]
    assert qc_variable("waves","waveHs",{"qcFlagE":1,"qcFlagD":1})=="qcFlagE"
    assert qc_variable("waves","waveMeanDirection",{"qcFlagE":1,"qcFlagD":1})=="qcFlagD"


def test_dap_grid_indices_scalars_and_maps():
    text="Dataset {};\n--------------------\ntime[2]\n1, 2\n\nlatitude, 36.2\nlongitude, -75.7\n\nE.E[2][3]\n[0], 1, 2, 3\n[1], 4, NaN, -999\n\nE.time[2]\n1, 2\n"
    arrays=ascii_arrays(text)
    assert arrays["E"].shape==(2,3) and arrays["E"][1,0]==4
    assert arrays["latitude"]==36.2 and arrays["longitude"]==-75.7
    assert np.isnan(arrays["E"][1,1])
    with pytest.raises(ValueError): ascii_arrays(text.replace("[1], 4, NaN, -999","[1], 4, NaN"))
    with pytest.raises(ValueError): ascii_arrays(text.replace("E.time[2]\n1, 2","E.time[2]\n1, 3"))
    attrs=das_attributes('Attributes { E { Float32 _FillValue NaN; String units "m2 s"; } }')
    assert attrs["E"]["_FillValue"]=="nan"
    json.dumps(attrs,allow_nan=False)


@pytest.mark.parametrize("f",[[.04,.05,.07],[.04,.055,.08,.10]])
def test_variable_grid_missing_not_bridged(f):
    energy=np.ones(len(f));valid=np.ones(len(f),bool);valid[1]=False
    summary=spectral_summary(f,energy,valid)
    assert summary["partial_integral"] and summary["missing_bin_indices"]==[1]
    expected=sum(w for j,w in enumerate(summary["widths_hz"]) if j!=1)
    assert summary["m0_m2"]==pytest.approx(expected)
    assert summary["Hm0_m"]==pytest.approx(4*math.sqrt(expected))


def rectangle(x=-75.75,y=36.18):
    return {"type":"Polygon","coordinates":[[[x,y],[x+.01,y],[x+.01,y+.01],[x,y+.01],[x,y]]]}


def test_polygon_inside_center_and_hole():
    geo=polygon(rectangle())
    d=distances([-75.749,36.181],geo)
    assert d["inside"] and d["minimum_m"]==0 and d["center_m"]>0
    outer=rectangle();outer["coordinates"].append([[-75.747,36.183],[-75.743,36.183],[-75.743,36.187],[-75.747,36.187],[-75.747,36.183]])
    assert distances([-75.745,36.185],polygon(outer))["minimum_m"]>0
    assert distances([-75.76,36.185],geo)["minimum_m"]>800
    assert distances([-75.75,36.18],None)["status"]=="not_evaluable"
    assert inverse(0,0,1,0)[0]==pytest.approx(111319.490793,abs=.01)


def test_order_multipolygon_and_timestamp_inputs(tmp_path):
    invalid=rectangle(36,-175)
    with pytest.raises(ValueError): polygon(invalid)
    mp={"type":"MultiPolygon","coordinates":[rectangle()["coordinates"]]}
    assert polygon(mp).geom_type=="MultiPolygon"
    row={"acquisition_id":"sensor_agnostic","timestamp_utc":"2021-10-13T23:00:15.669Z","footprint":mp}
    file=tmp_path/"inputs.geojson"
    file.write_text(json.dumps({"type":"Feature","geometry":mp,"properties":{k:v for k,v in row.items() if k!="footprint"}}))
    assert read_acquisitions(file)[0]["acquisition_id"]=="sensor_agnostic"
    assert validate({"acquisition_id":"time_only","timestamp_utc":row["timestamp_utc"]}).get("footprint") is None


def test_historical_position_not_current_default():
    attrs={"NC_GLOBAL":{"geospatial_lat_min":36.2,"geospatial_lon_min":-75.7,"deployment_start":"2014-11-04T00:00:00Z"}}
    position=historical_position(attrs,{"latitude":np.asarray(36.21),"longitude":np.asarray(-75.71)})
    assert position["lon_lat"]==[-75.71,36.21] and position["position_uncertain"]
    assert position["position_discrepancy_m"]>1000
    assert historical_position({},{} )["lon_lat"] is None


@pytest.mark.parametrize("timestamp,dt",[("2021-06-29T22:56:51Z",189),("2021-06-30T10:54:50Z",310)])
def test_stale_waverider_does_not_fill_awac(timestamp,dt):
    target=utc(timestamp).timestamp()
    stale=associate([target-20*86400],target,[True],3600)
    current=associate([target+dt],target,[True],3600)
    assert not stale["within_tolerance"] and current["within_tolerance"]
    assert current["offset_seconds"]==dt


class Response(io.BytesIO):
    def __init__(self,body=b"ok",status=200,headers=None):
        super().__init__(body)
        self.status,self.headers=status,headers or {"Content-Length":str(len(body))}


class Opener:
    def __init__(self,responses): self.responses=list(responses);self.calls=0
    def open(self,*args,**kwargs):
        self.calls+=1
        response=self.responses.pop(0)
        if isinstance(response,Exception): raise response
        return response


URL="https://chldata.erdc.dren.mil/thredds/test"


def test_persistent_budget_cache_and_corruption(tmp_path):
    opener=Opener([Response()])
    client=Transport(tmp_path,opener=opener,max_requests=1,max_bytes=10,rate_seconds=0,retries=0)
    assert client.state_path.exists() and client.get(URL)==b"ok"
    assert client.get(URL)==b"ok" and opener.calls==1
    resumed=Transport(tmp_path,opener=Opener([]),max_requests=1,max_bytes=10)
    assert resumed.get(URL)==b"ok"
    with pytest.raises(FetchError,match="incomplete_budget"): resumed.get(URL+"2")
    client._paths(URL)[0].write_bytes(b"corrupt")
    with pytest.raises(FetchError,match="cache_hash_mismatch"): client.get(URL)


def test_redirect_retry_failure_and_byte_accounting(tmp_path):
    opener=Opener([Response(b"",302,{"Location":URL+"2","Content-Length":"0"}),Response(b"busy",503,{"Retry-After":"0","Content-Length":"4"}),Response(b"ok")])
    client=Transport(tmp_path,opener=opener,max_requests=3,max_bytes=10,rate_seconds=0)
    assert client.get(URL)==b"ok" and client.state["transactions"]==3 and client.state["bytes"]==6
    off=Transport(tmp_path,offline=True,max_requests=3,max_bytes=10)
    assert off.get(URL)==b"ok"
    with pytest.raises(FetchError,match="offline_cache_miss"): off.get(URL+"missing")


def test_failure_cache_404_not_global_absence(tmp_path):
    opener=Opener([Response(b"no",404)])
    client=Transport(tmp_path,opener=opener,rate_seconds=0)
    for _ in range(2):
        with pytest.raises(FetchError,match="path_not_found"): client.get(URL)
    assert opener.calls==1 and client.state["transactions"]==1


def test_secrets_and_unverified_auth_never_logged(tmp_path):
    assert "TOPSECRET" not in safe_url(URL+"?token=TOPSECRET")
    client=Transport(tmp_path,opener=Opener([]))
    with pytest.raises(FetchError): client.get(URL+"?token=TOPSECRET")
    with pytest.raises(FetchError): client.get("https://user:TOPSECRET@chldata.erdc.dren.mil/test")
    assert all("TOPSECRET" not in p.read_text() for p in tmp_path.glob("*.json*"))
    assert safe_url(URL+".ascii?time[1:1:3],waveHs")==URL+".ascii?time[1:1:3],waveHs"


def test_response_limit_rejected_before_body(tmp_path):
    response=Response(b"a"*20)
    client=Transport(tmp_path,opener=Opener([response]),max_response=10,rate_seconds=0)
    with pytest.raises(FetchError,match="response_too_large"): client.get(URL)
    assert client.state["bytes"]==0 and client.state["transactions"]==1


def test_verified_legacy_reuse(tmp_path):
    legacy=tmp_path/"legacy";legacy.mkdir()
    raw=b"sample\n"
    (legacy/(digest(URL.encode())+".txt")).write_bytes(raw)
    (legacy/"requests.jsonl").write_text(json.dumps({"url":URL,"sha256":digest(raw)})+"\n")
    client=Transport(tmp_path/"new",offline=True)
    assert client.import_legacy(legacy)[0]["status"]=="verified_legacy_reused"
    assert client.get(URL)==raw and client.state["transactions"]==0


def test_csv_blank_geometries_and_eoweb_fraction(tmp_path):
    file=tmp_path/"input.csv"
    file.write_text("acquisition_id,timestamp_utc,footprint_geojson,roi_geojson\nid,2021-10-13T23:00:15.669Z,,\n")
    assert read_acquisitions(file)[0]["footprint"] is None
    path=tmp_path/"eoweb.csv"
    path.write_text("recordNum;platformSerialIdentifier;startdate;enddate;footprint\n11;TDX-1;2021-10-13T23:00:15.669Z;2021-10-13T23:00:16.101Z;-75.75,36.18 -75.74,36.18 -75.74,36.19 -75.75,36.18\nfooter\n")
    record=adapt_eoweb(path,[11])[0]
    assert record["timestamp_utc"].endswith("15.669000+00:00")
    assert "catalogue" in record["timestamp_semantics"]


def test_failure_expiry_timeout_and_unknown_length_cap(tmp_path):
    import time
    opener=Opener([Response(b"no",404),Response(b"ok")])
    client=Transport(tmp_path/"expiry",opener=opener,failure_ttl=0,rate_seconds=0)
    with pytest.raises(FetchError): client.get(URL)
    assert client.get(URL)==b"ok" and client.state["transactions"]==2
    opener=Opener([TimeoutError(),Response()])
    retry=Transport(tmp_path/"timeout",opener=opener,rate_seconds=0)
    assert retry.get(URL)==b"ok" and retry.state["transactions"]==2
    response=Response(b"abcdefghijklmnop",headers={"X":"no-length"})
    capped=Transport(tmp_path/"stream",opener=Opener([response]),max_response=10,rate_seconds=0)
    with pytest.raises(FetchError,match="limit"): capped.get(URL)
    assert capped.state["bytes"]==10


def test_catalog_discovery_and_survey_not_bbox(tmp_path):
    from frf_client.catalog import catalog, discover_month
    from frf_client.survey import fetch_points
    xml=b'<catalog xmlns="http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0" xmlns:xlink="http://www.w3.org/1999/xlink"><service serviceType="OpenDAP" base="/thredds/dodsC/"/><dataset name="x"><catalogRef name="2021" xlink:href="2021/catalog.xml"/><dataset name="different_prefix_202110.nc" urlPath="frf/real_file.nc"/></dataset></catalog>'
    transport=Transport(tmp_path,opener=Opener([Response(xml),Response(xml)]),rate_seconds=0)
    products,state=discover_month(transport,URL,"202110")
    assert products[0]["services"]["OpenDAP"].endswith("frf/real_file.nc")
    assert products[0]["name"]=="different_prefix_202110.nc"
    with pytest.raises(ValueError): fetch_points(transport,products[0],[0,6000],rectangle())
    with pytest.raises(ValueError): fetch_points(transport,products[0],[0,5],None)


def test_deployment_contradiction_no_historical_distance():
    attrs={"NC_GLOBAL":{"geospatial_lat_min":36.2,"geospatial_lon_min":-75.7,"deployment_start":"2025-01-01T00:00:00Z"},
           "time":{"units":"seconds since 1970-01-01 00:00:00"}}
    pos=historical_position(attrs,{"time":np.array([utc("2021-10-13T23:00:00Z").timestamp()])},0)
    assert pos["deployment_conflict"] and pos["lon_lat"] is None
    json.dumps(pos,allow_nan=False)


def test_dossier_offline_fixture_masks_qc_roi_and_manifest(tmp_path):
    import csv
    from frf_client.output import dossier
    target=utc("2021-10-13T23:00:00Z").timestamp()
    arrays={"time":np.array([target-1800,target,target+1800]),"waveHs":np.array([1.,1.2,-999]),
            "waveTp":np.array([8.,9.,10.]),"waveMeanDirectionPeakFrequency":np.array([359.,1.,5.]),
            "qcFlagE":np.array([1,1,4]),"qcFlagD":np.array([1,4,1]),
            "waveFrequency":np.array([.05,.10,.15]),"waveEnergyDensity":np.array([[1,2,1],[2,np.nan,1],[1,1,1]]),
            "latitude":np.asarray(36.185),"longitude":np.asarray(-75.745)}
    attrs={name:{"units":"source_units","_FillValue":-999} for name in arrays}
    attrs["time"]={"units":"seconds since 1970-01-01 00:00:00"}
    attrs["NC_GLOBAL"]={"platform":"fixture","instrument":"fixture","summary":"30 minute records"}
    loaded={"metadata":{"attributes":attrs,"source":URL},"arrays":arrays,
            "masks":{v:mask_values(a,attrs[v]) for v,a in arrays.items()},"times":arrays["time"],"coverage":{"fixture":True},"intervals":None}
    acquisition=validate({"acquisition_id":"fixture_COSMO_TDX_equivalent","timestamp_utc":"2021-10-13T23:00:00Z","footprint":rectangle(),"roi":rectangle()})
    config={"accepted_qc_flags":[1],"accept_unknown_qc":False,"time_tolerance_seconds":{"waves":3600}}
    transport=Transport(tmp_path/"cache",offline=True)
    dossier(acquisition,[{"source":URL,"family":"waves","instrument":"waverider-17m","loaded":loaded}],[],[],config,tmp_path,transport)
    base=tmp_path/acquisition["acquisition_id"]
    rows=list(csv.DictReader((base/"OBSERVATIONS.csv").open()))
    assert any(r["variable"]=="waveHs" and r["role"]=="nearest_qc" and r["representative_eligible"]=="True" for r in rows)
    assert any(r["variable"]=="waveMeanDirectionPeakFrequency" and r["role"]=="nearest_context" and r["status"]=="qc_failed" for r in rows)
    summary=json.loads((base/"SPECTRAL_SUMMARIES.json").read_text())[0]
    assert summary["missing_bin_indices"]==[1]
    distances_rows=list(csv.DictReader((base/"DISTANCES.csv").open()))
    assert distances_rows[0]["roi_inside"]=="True" and float(distances_rows[0]["roi_minimum_m"])==0
    manifest=json.loads((base/"MANIFEST.json").read_text())
    assert all(digest(Path(e["path"]).read_bytes())==e["sha256"] for e in manifest["artifacts"])
    assert transport.state["transactions"]==0


def test_auth_required_cross_host_redirect_and_retry_after(tmp_path):
    auth=Transport(tmp_path/"auth",opener=Opener([Response(b"login",401)]),rate_seconds=0)
    with pytest.raises(FetchError,match="authentication_required"): auth.get(URL)
    redirect=Transport(tmp_path/"redirect",opener=Opener([Response(b"",302,{"Location":"https://unapproved.example/","Content-Length":"0"})]),rate_seconds=0)
    with pytest.raises(FetchError,match="unauthorized_endpoint"): redirect.get(URL)
    assert redirect.state["transactions"]==1
    deferred=Transport(tmp_path/"deferred",opener=Opener([Response(b"",429,{"Retry-After":"120","Content-Length":"0"})]),rate_seconds=0)
    with pytest.raises(FetchError,match="retry_after_deferred"): deferred.get(URL)
    assert deferred.state["transactions"]==1

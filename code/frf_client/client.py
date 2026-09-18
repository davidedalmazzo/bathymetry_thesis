"""Conservative family-aware FRF event client; missing information stays missing."""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
from .catalog import ROOT, catalog, discover_month, metadata
from .data import ascii_arrays, das_attributes, dds_shapes, cf_times, utc, mask_values, qc_pass, associate, spectral_summary
from .geometry import polygon, distances, inverse
from .transport import FetchError, save_json, digest
from .temporal import months_needed, event_windows

LEGACY_SCALARS = ["waveHs", "waveTp", "waveTm", "waveMeanDirection", "wavePeakDirectionPeakFrequency", "directionalPeakSpread"]
ALIASES = {"waverider-17m": ["FRF630","NDBC44056","CDIP433"],
           "waverider-26m": ["NDBC44100","CDIP430"], "eopNoaaTide": ["NOAA8651370"]}
VARIABLES = {
    "waves": LEGACY_SCALARS + ["waveTm1","waveTm2","waveMeanDirectionPeakFrequency","waveFrequency", "waveDirectionBins", "waveEnergyDensity", "directionalWaveEnergyDensity", "waveA1Value", "waveB1Value", "waveA2Value", "waveB2Value", "waveFrequencyBandwidth", "frequencyBounds", "qcFlagE", "qcFlagD", "waveDirectionEstimator", "nominalDepth", "gaugeDepth"],
    "wind": ["windSpeed","vectorSpeed","sustWindSpeed","windGust","windDirection","maxWindSpeed","minWindSpeed","stdWindSpeed","gaugeElevation","qcFlagS","qcFlagD","id","airTemperature","airPressure"],
    "currents": ["depth","cellSize","blankDist","maxCell","aveTime","meanPressure","aveE","aveN","currentSpeed","currentDirection","currentEast","currentNorth","currentUp","qcFlag"],
    "water_level": ["waterLevel","predictedWaterLevel","residualWaterLevel","gapGauge","qcFlag","temperature","airPressure"]}


def finite_list(arr):
    arr = np.asarray(arr)
    return np.where(np.isfinite(arr), arr, None).tolist()


def qc_variable(family, variable, available):
    if family == "waves":
        directional = any(w in variable.lower() for w in ("direction", "spread", "a1", "a2", "b1", "b2"))
        name = "qcFlagD" if directional else "qcFlagE"
    elif family == "wind":
        name = "qcFlagD" if "direction" in variable.lower() else "qcFlagS"
    else:
        name = "qcFlag"
    return name if name in available else None


def historical_position(attrs, arrays, index=None, family=None):
    """Only dated-product coordinates; nominal unless source establishes measured position."""
    global_attrs = attrs.get("NC_GLOBAL", {})
    position, source = None, "missing"
    if "latitude" in arrays and "longitude" in arrays:
        lat = np.asarray(arrays["latitude"]).reshape(-1)
        lon = np.asarray(arrays["longitude"]).reshape(-1)
        j = index if index is not None else 0
        jl,jo = j if len(lat)>1 else 0,j if len(lon)>1 else 0
        if jl < len(lat) and jo < len(lon) and mask_values(lat,attrs.get("latitude",{}))[jl] and mask_values(lon,attrs.get("longitude",{}))[jo] and -90 <= lat[jl] <= 90 and -180 <= lon[jo] <= 180:
            position, source = [float(lon[jo]),float(lat[jl])], "dated_product_coordinates_nominal_not_proven_measured"
    if position is None and not ("latitude" in arrays or "longitude" in arrays) and "geospatial_lat_min" in global_attrs and "geospatial_lon_min" in global_attrs:
        position = [float(global_attrs["geospatial_lon_min"]),float(global_attrs["geospatial_lat_min"])]
        source = "dated_product_global_nominal_metadata"
    # Derived wind is a gauge switcher: resolve the actual selected instrument in the supplied historical table.
    if family == "wind" and "id" in arrays and index is not None:
        ids=np.asarray(arrays["id"]).reshape(-1)
        selected = int(ids[index]) if index<len(ids) and np.isfinite(ids[index]) and mask_values(ids,attrs.get("id",{}))[index] else -1
        matches = re.findall(r"(\d+)\s*=\s*(\d+)\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s+([^\n]+)", global_attrs.get("summary", ""))
        match = next((x for x in matches if int(x[0]) == selected or int(x[1]) == selected), None)
        if match:
            position = [float(match[3]),float(match[2])]
            source = "dated_product_gauge_id_and_historical_nominal_table"
        else:
            position = None
            source = "selected_wind_gauge_position_unresolved"
    nominal_global = [float(global_attrs["geospatial_lon_min"]),float(global_attrs["geospatial_lat_min"])] if "geospatial_lat_min" in global_attrs and "geospatial_lon_min" in global_attrs else None
    discrepancy = inverse(*position,*nominal_global)[0] if position and nominal_global else None
    conflict = discrepancy is not None and discrepancy > 5
    dated_candidate=position.copy() if position else None
    # Technical plausibility guard, not a geolocation correction: conflicting
    # nominal sources separated by >1000 km cannot define one FRF site safely.
    gross_conflict=discrepancy is not None and discrepancy>1000000
    if gross_conflict:
        position=None;source='gross_nominal_coordinate_conflict_position_unresolved'
    deployment_conflict=False
    deployment_status="not_verified"
    if (global_attrs.get("deployment_start") or global_attrs.get("deployment_end")) and "time" in arrays:
        try:
            observed=cf_times(arrays["time"],attrs["time"]["units"]).reshape(-1)[index if index is not None else 0]
            start=utc(global_attrs["deployment_start"]).timestamp() if global_attrs.get("deployment_start") else None
            end=utc(global_attrs["deployment_end"]).timestamp() if global_attrs.get("deployment_end") else None
            deployment_conflict=bool((start is not None and observed<start) or (end is not None and observed>end))
            deployment_status="outside_supplied_deployment" if deployment_conflict else "within_supplied_bounds_not_complete_history"
        except (ValueError,KeyError):
            pass
    if deployment_conflict:
        position=None
        source="outside_deployment_position_unresolved"
    return {"lon_lat": position, "status": source + ("; conflicting_nominal_metadata" if conflict else ""),
            "global_nominal_lon_lat":nominal_global,"position_discrepancy_m":discrepancy,
            "dated_coordinate_candidate_lon_lat":dated_candidate,"gross_coordinate_conflict":gross_conflict,
            "position_uncertain":conflict or position is None,"deployment_conflict":deployment_conflict,
            "deployment_status":deployment_status,"sensor_id":str(selected) if family=="wind" and "id" in arrays and index is not None else global_attrs.get("instrument",global_attrs.get("sensor_type")),
            "deployment_start":global_attrs.get("deployment_start"),
            "deployment_end":global_attrs.get("deployment_end"),
            "caveat": "Dated file is not proof of complete deployment history; conflicting summary positions are retained in inventory"}


class Client:
    def __init__(self, transport, config):
        self.transport, self.config = transport, config
        if config.get("interpolation"):
            raise ValueError("Interpolation adapter not enabled; no silent interpolation")
        self.inventory, self.errors, self.loaded = [], [], {}
        self.pending_surveys=[]

    def _legacy_products(self):
        found = []
        for p in self.transport.directory.glob("*.json"):
            try:
                entry = json.loads(p.read_text())
            except (ValueError, OSError):
                continue
            if entry.get("status") == "ok" and entry.get("legacy_source") and entry.get("url", "").endswith(".das"):
                if not entry.get("verified"):
                    continue
                try:
                    self.transport.cached(entry["url"])
                except FetchError:
                    continue
                url = entry["url"][:-4]
                m = re.search(r"/waves/([^/]+)/\d{4}/.*?(\d{6})\.nc$", url)
                if m:
                    found.append({"family":"waves","instrument":m[1],"month":m[2], "source":url,
                                  "services":{"OpenDAP":url}, "discovery":"verified_Block30_response_provenance"})
        return found

    def _load_legacy(self, product):
        url = product["source"]
        attrs = das_attributes(self.transport.get(url+".das").decode())
        text = self.transport.get(url+".ascii?time,"+",".join(LEGACY_SCALARS)).decode()
        arrays = ascii_arrays(text)
        shapes = dds_shapes(text)
        return {"attributes":attrs,"shapes":shapes,"source":url,"available_services":product["services"]}, arrays

    def discover(self, acquisitions):
        root = catalog(self.transport, ROOT)
        sub = {r["name"]:r["url"] for r in root["references"]}
        paths={}
        for parent,families in (("oceanography",("waves","currents","water_level")),("meteorology",("wind",)),("geomorphology",("bathymetry",))):
            if not any(f in self.config["families"] for f in families):continue
            try:
                if parent not in sub:raise FetchError("family_parent_not_listed")
                paths.update({r["name"]:r["url"] for r in catalog(self.transport,sub[parent])["references"]})
            except (FetchError,ValueError) as exc:
                self.errors.append({"family_parent":parent,"status":getattr(exc,"status","malformed_catalog")})
        defaults = {"currents":"awac-11m","wind":"derived","water_level":"eopNoaaTide","bathymetry":"survey"}
        defaults.update(self.config.get("preferred_instruments",{}))
        choices = {"currents":(defaults["currents"],paths.get("currents")),
                   "wind":(defaults["wind"],paths.get("wind")), "water_level":(defaults["water_level"],paths.get("waterlevel")),
                   "bathymetry":(defaults["bathymetry"],paths.get("elevationTransects"))}
        months = months_needed(acquisitions,self.config,"waves")
        discovered = self._legacy_products()
        missing = [(instrument,month) for instrument in self.config["wave_instruments"] for month in months
                   if not any(p["instrument"]==instrument and p["month"]==month for p in discovered)]
        if missing and "waves" in self.config["families"]:
            try:
                if "waves" not in paths:raise FetchError("waves_catalog_not_listed")
                wave_catalog=catalog(self.transport,paths["waves"])
                self.inventory.append({"family":"waves","source":paths["waves"],"discovered_instruments":wave_catalog["references"]})
                for instrument,month in missing:
                    ref=next((r for r in wave_catalog["references"] if r["name"]==instrument),None)
                    if ref is None:
                        self.inventory.append({"family":"waves","instrument":instrument,"status":"not_in_inspected_catalog_not_global_absence"})
                        continue
                    try:
                        wave_products,state=discover_month(self.transport,ref["url"],month)
                    except (FetchError,ValueError) as exc:
                        self.errors.append({"family":"waves","instrument":instrument,"month":month,"status":getattr(exc,"status","malformed_catalog")})
                        continue
                    self.inventory.append({"family":"waves","instrument":instrument,"month":month,**state})
                    discovered.extend({**p,"family":"waves","instrument":instrument,"month":month,
                                       "source":p["services"].get("OpenDAP")} for p in wave_products)
            except FetchError as exc:
                self.errors.append({"family":"waves","status":exc.status,"code":exc.code})
        # Real-time new discovery is family-limited, not an unrestricted crawler.
        for family,(preferred,url) in choices.items():
            if family not in self.config["families"]:
                continue
            try:
                if url is None:raise FetchError("family_catalog_not_listed")
                family_listing = catalog(self.transport,url)
                self.inventory.append({"family":family,"discovered_instruments":family_listing["references"],
                                       "source":url,"status":"catalog_verified","independence":"aliases are not independent observations"})
                ref = next((r for r in family_listing["references"] if r["name"] == preferred),None)
                if ref is None:
                    continue
                if family == "bathymetry":
                    listing = catalog(self.transport,ref["url"])
                    self.inventory.append({"family":family,"instrument":preferred,"catalog":listing,
                                           "status":"inventory_only_no_survey_points_downloaded",
                                           "coverage": "not verified; catalog/bounding box is NOT surveyed seabed"})
                    self.pending_surveys.append(ref['url'])
                    continue
                for month in months_needed(acquisitions,self.config,family):
                    # Verification prioritizes October; later months still attempted only if budget permits.
                    try:
                        products, state = discover_month(self.transport,ref["url"],month)
                    except (FetchError,ValueError) as exc:
                        self.errors.append({"family":family,"instrument":preferred,"month":month,"status":getattr(exc,"status","malformed_catalog")})
                        continue
                    self.inventory.append({"family":family,"instrument":preferred,"month":month,**state})
                    for product in products:
                        discovered.append({**product,"source":product["services"].get("OpenDAP"),
                                           "instrument":preferred,"family":family,"month":month})
            except FetchError as exc:
                self.errors.append({"family":family,"status":exc.status,"code":exc.code})
        return list({(p["family"],p["instrument"],p["month"],p.get("source")):p for p in discovered}.values())

    def load(self, product, acquisitions, *, extended=True):
        family, url = product["family"], product["source"]
        key = (url,extended,tuple(tuple(w) for w in event_windows(acquisitions,self.config,family)))
        if key in self.loaded:
            return self.loaded[key]
        legacy = family == "waves" and product.get("discovery") == "verified_Block30_response_provenance"
        if legacy:
            meta, original = self._load_legacy(product)
            times = cf_times(original["time"],meta["attributes"]["time"]["units"])
        else:
            meta = metadata(self.transport,product)
            original = ascii_arrays(self.transport.get(url+".ascii?time").decode())
            times = cf_times(original["time"],meta["attributes"]["time"]["units"])
        # Always retain all original cached times for stale-reference diagnostics.
        initial_times = times.copy()
        initial_original = original.copy()
        original_indices=np.arange(len(times))
        if extended:
            if legacy:
                shapes = dds_shapes(self.transport.get(url+".dds").decode())
                meta["shapes"] = shapes
            else:
                shapes = meta["shapes"]
            if not shapes.get("time") or shapes["time"] != [len(times)]:
                raise FetchError("unsupported_time_dimensions")
            windows=event_windows(acquisitions,self.config,family)
            valid_times = mask_values(original["time"], meta["attributes"]["time"])
            pieces, kept, data_urls = [], [], []
            for window_lo,window_hi in windows:
                indices=np.flatnonzero(valid_times & (times>=window_lo) & (times<=window_hi))
                if not len(indices):continue
                lo,hi=int(indices.min()),int(indices.max())
                if hi-lo+1 > self.config.get("max_event_samples",2000):
                    raise FetchError("single_event_window_too_broad")
                selections = []
                bounds_name=meta["attributes"].get("time",{}).get("bounds")
                requested=["time","latitude","longitude"]+VARIABLES[family]+([bounds_name] if bounds_name else [])
                for name in requested:
                    if name not in shapes:
                        continue
                    dims = shapes[name]
                    if dims and dims[0] == len(times) and name not in ("waveFrequency","waveDirectionBins","depth"):
                        selector = f"{name}[{lo}:1:{hi}]" + "".join(f"[0:1:{n-1}]" for n in dims[1:])
                    else:
                        selector = name
                    selections.append(selector)
                data_url = url+".ascii?"+",".join(selections)
                piece=self._verified_subset(url,data_url,times[lo:hi+1],selections,shapes,len(initial_times))
                if np.asarray(piece["time"]).shape!=(hi-lo+1,):raise FetchError("subset_time_shape_mismatch")
                pieces.append(piece);kept.extend(range(lo,hi+1));data_urls.append(self._subset_source)
            if pieces:
                # Monthly segments share their own grid; different monthly grids remain separate tensors.
                original={}
                for name in pieces[0]:
                    dims=shapes[name]
                    dynamic=bool(dims and dims[0]==len(initial_times) and name not in ("waveFrequency","waveDirectionBins","depth"))
                    if dynamic:original[name]=np.concatenate([p[name] for p in pieces],axis=0)
                    else:
                        if not all(np.array_equal(p[name],pieces[0][name],equal_nan=True) for p in pieces):raise FetchError("within_product_coordinate_conflict")
                        original[name]=pieces[0][name]
                times=cf_times(original["time"],meta["attributes"]["time"]["units"])
                original_indices=np.asarray(kept)
                meta["event_subset_source"]=data_urls[0] if len(data_urls)==1 else data_urls
            else:
                meta["subset_status"] = "no_samples_in_event_context; cached stale context retained"
        masks = {name: mask_values(array,meta["attributes"].get(name,{})) for name,array in original.items()}
        bounds_name=meta["attributes"].get("time",{}).get("bounds")
        intervals=cf_times(original[bounds_name],meta["attributes"]["time"]["units"]) if bounds_name in original and np.asarray(original[bounds_name]).shape==(len(times),2) else None
        result = {"metadata":meta,"arrays":original,"masks":masks,"times":times,"intervals":intervals,
                  "initial_times":initial_times,"initial_arrays":initial_original,"original_indices":original_indices,
                  "coverage":{"actual_time_min":float(initial_times.min()),"actual_time_max":float(initial_times.max()),
                              "search_windows_utc_seconds":event_windows(acquisitions,self.config,family),
                              "monthly_time_vector_verified":True,"observations_in_context_retrieved":bool(extended and meta.get("event_subset_source")),
                              "scope":"verified monthly time vector; gaps not filled; QC search limited to fetched event context"}}
        self.loaded[key] = result
        return result

    def _verified_subset(self,url,data_url,requested_times,selections,shapes,monthly_length):
        """Reuse verified superset event payloads before any new bounded request."""
        self._subset_source=data_url
        if hasattr(self.transport,"cached"):
            try:return ascii_arrays(self.transport.cached(data_url).decode())
            except FetchError as exc:
                if exc.status not in ("offline_cache_miss",):raise
            for path in sorted(self.transport.directory.glob("*.json")):
                entry=json.loads(path.read_text())
                source=entry.get("url","")
                if entry.get("status")!="ok" or not source.startswith(url+".ascii?") or source==data_url:continue
                arrays=ascii_arrays(self.transport.cached(source).decode())
                needed=[s.split('[')[0] for s in selections]
                if "time" not in arrays or not all(n in arrays for n in needed):continue
                # Epoch units are identical within one product: compare original CF values.
                attrs=das_attributes(self.transport.cached(url+".das").decode())
                times=cf_times(arrays["time"],attrs["time"]["units"])
                matching=[];previous=-1
                for t in requested_times:
                    candidates=np.flatnonzero((times==t)&(np.arange(len(times))>previous))
                    if not len(candidates):break
                    previous=int(candidates[0]);matching.append(previous)
                if len(matching)!=len(requested_times):continue
                piece={}
                for name in needed:
                    dims=shapes[name]
                    dynamic=bool(dims and dims[0]==monthly_length and name not in ("waveFrequency","waveDirectionBins","depth"))
                    piece[name]=arrays[name][matching] if dynamic else arrays[name]
                self._subset_source=source
                return piece
        return ascii_arrays(self.transport.get(data_url).decode())

    def run(self, acquisitions, output, mode="offline"):
        from .output import dossier
        if mode=="offline" and not self.transport.offline:
            raise ValueError("Offline mode requires an offline Transport")
        self._inventory_only=mode=="inventory"
        output.mkdir(parents=True,exist_ok=True)
        ids=[re.sub(r"[^A-Za-z0-9_.-]","_",a["acquisition_id"]) for a in acquisitions]
        if len(ids)!=len(set(ids)):
            raise ValueError("Acquisition IDs collide after filename sanitization")
        try:
            products = self.discover(acquisitions)
        except (FetchError,ValueError,KeyError,SyntaxError) as exc:
            self.errors.append({'stage':'discovery','status':getattr(exc,'status','unsupported_or_malformed_catalog'),'detail':type(exc).__name__})
            products=[]
        selected = [p for p in products if p["family"] in self.config["families"] and (p["family"] != "waves" or p["instrument"] in self.config["wave_instruments"])]
        # Fetch primary event wave systems before ancillary products; October before June.
        selected.sort(key=lambda p:(p["family"] != "waves", -int(p["month"]), p["instrument"] != "waverider-17m"))
        for product in selected:
            relevant = [a for a in acquisitions if product["month"] in months_needed([a],self.config,product["family"])]
            if not relevant:
                continue
            try:
                if mode == "inventory":
                    meta = metadata(self.transport,product)
                    self.inventory.append({**product,"metadata":meta,"status":"metadata_verified_not_observations_fetched"})
                    continue
                extended = not product.get("discovery") or product["family"] != "waves" or product["instrument"] in self.config.get("spectral_instruments",["waverider-17m","awac-11m"])
                loaded = self.load(product,acquisitions,extended=extended)
                product["loaded"] = loaded
                self.inventory.append({k:v for k,v in product.items() if k != "loaded"} | {"metadata":loaded["metadata"],"coverage":loaded["coverage"],"status":"retrieved"})
            except (FetchError, ValueError, RuntimeError,KeyError,IndexError) as exc:
                self.errors.append({"source":product["source"],"family":product["family"],"instrument":product["instrument"],
                                    "month":product["month"],"status":("incomplete_budget_cache_not_available" if isinstance(exc,FetchError) and exc.status=="offline_cache_miss" and self.transport.state["transactions"]>=self.transport.state["max_transactions"] else exc.status) if isinstance(exc,FetchError) else "unsupported_or_malformed_payload", "detail":type(exc).__name__})
                if mode != "inventory" and product.get("discovery") == "verified_Block30_response_provenance":
                    # A failed spectral expansion must not discard verified local contemporaneous bulk context.
                    try:
                        loaded=self.load(product,acquisitions,extended=False)
                        loaded["metadata"]["extended_status"]="unavailable; cached bulk context only; QC not inferred"
                        product["loaded"]=loaded
                        self.inventory.append({k:v for k,v in product.items() if k!="loaded"} | {"metadata":loaded["metadata"],"coverage":loaded["coverage"],"status":"verified_cached_bulk_context_only"})
                    except (FetchError,ValueError) as fallback:
                        self.errors.append({"source":product["source"],"status":getattr(fallback,"status","malformed_cached_bulk")})
        self._survey_context(acquisitions,mode)
        for acquisition in acquisitions:
            relevant = [p for p in selected if p.get("loaded") and p["month"] in months_needed([acquisition],self.config,p["family"])]
            search=[]
            for family in self.config["families"]:
                if family=="bathymetry":continue
                instruments=self.config["wave_instruments"] if family=="waves" else [self.config.get("preferred_instruments",{}).get(family,{"currents":"awac-11m","wind":"derived","water_level":"eopNoaaTide"}[family])]
                for instrument in instruments:
                    expected=months_needed([acquisition],self.config,family)
                    present={p["month"] for p in relevant if p["family"]==family and p["instrument"]==instrument and p["loaded"]["coverage"].get("observations_in_context_retrieved")}
                    search.append({"family":family,"instrument_id":"FRF:"+instrument,"required_months":expected,"missing_or_unverified_months":sorted(set(expected)-present),
                                   "status":"verified_configured_context" if set(expected)<=present else "incomplete_search", "nearest_claim":"nearest within available segments, not absolute deployment nearest"})
            dossier(acquisition,relevant,self.inventory,self.errors,self.config,output,self.transport,search_coverage=search)
        save_json(output/"INVENTORY.json",self.inventory)
        save_json(output/"STATUS.json", {"errors":self.errors,"network":self.transport.state,
                                        "no_radar_access":True,"mode":mode,"event_representative_state":"not mixed across instruments"})

    def _survey_context(self,acquisitions,mode):
        """Ancillary survey work follows wave/current/wind/level retrieval."""
        from .survey import inventory as survey_inventory,fetch_points
        inspected=set()
        for url in self.pending_surveys:
            for acquisition in acquisitions:
                try:
                    surveys=survey_inventory(self.transport,url,acquisition['timestamp_utc'])
                    self.inventory.append({'family':'bathymetry','acquisition_id':acquisition['acquisition_id'],**surveys})
                    target=utc(acquisition['timestamp_utc']).timestamp()
                    candidates=[]
                    for product in surveys['products']:
                        date=product.get('candidate_date_from_filename')
                        if date:
                            offset=abs(utc(date+'T00:00:00Z').timestamp()-target)
                            if offset<=self.config['time_tolerance_seconds'].get('bathymetry',2592000):candidates.append((offset,product))
                    for _,product in sorted(candidates,key=lambda item:item[0])[:self.config.get('max_survey_metadata_products',3)]:
                        key=product['services'].get('OpenDAP')
                        if key in inspected:continue
                        inspected.add(key)
                        try:
                            meta=metadata(self.transport,product)
                            entry={'family':'bathymetry','survey_reference':product,'metadata':meta,
                                   'status':'nearby_candidate_metadata_verified','measured_coverage':'not verified by bounding box','filename_date_not_verified':True}
                            if mode!='inventory' and self.config.get('bathymetry_download') and key in self.config.get('survey_selections',{}):
                                entry['survey_subset']=fetch_points(self.transport,product,self.config['survey_selections'][key],acquisition.get('roi') or acquisition.get('footprint'))
                            self.inventory.append(entry)
                        except (FetchError,ValueError) as exc:
                            self.inventory.append({'family':'bathymetry','survey_reference':product,'status':getattr(exc,'status','unsupported_survey_metadata')})
                except (FetchError,ValueError) as exc:
                    self.inventory.append({'family':'bathymetry','acquisition_id':acquisition['acquisition_id'],'status':getattr(exc,'status','unsupported_survey_catalog'),'date_method_datum_coverage':'not verified; no source-product download'})

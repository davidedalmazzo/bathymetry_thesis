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
        j = index if index is not None and len(lat) > 1 else 0
        if j < len(lat) and j < len(lon) and -90 <= lat[j] <= 90 and -180 <= lon[j] <= 180:
            position, source = [float(lon[j]),float(lat[j])], "dated_product_coordinates_nominal_not_proven_measured"
    if position is None and "geospatial_lat_min" in global_attrs and "geospatial_lon_min" in global_attrs:
        position = [float(global_attrs["geospatial_lon_min"]),float(global_attrs["geospatial_lat_min"])]
        source = "dated_product_global_nominal_metadata"
    # Derived wind is a gauge switcher: resolve the actual selected instrument in the supplied historical table.
    if family == "wind" and "id" in arrays and index is not None:
        selected = int(np.asarray(arrays["id"])[index]) if np.isfinite(np.asarray(arrays["id"])[index]) else -1
        matches = re.findall(r"(\d+)\s*=\s*(\d+)\s+([+-]?\d+\.\d+)\s+([+-]?\d+\.\d+)\s+([+-]?\d+\.\d+)\s+([^\n]+)", global_attrs.get("summary", ""))
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
    deployment_conflict=False
    if global_attrs.get("deployment_start") and "time" in arrays:
        try:
            observed=cf_times(arrays["time"],attrs["time"]["units"]).reshape(-1)[index if index is not None else 0]
            deployment_conflict=bool(utc(global_attrs["deployment_start"]).timestamp()>observed)
        except (ValueError,KeyError):
            pass
    if deployment_conflict:
        position=None
        source="deployment_after_observation_position_unresolved"
    return {"lon_lat": position, "status": source + ("; conflicting_nominal_metadata" if conflict else ""),
            "global_nominal_lon_lat":nominal_global,"position_discrepancy_m":discrepancy,
            "position_uncertain":conflict or position is None,"deployment_conflict":deployment_conflict,
            "deployment_start":global_attrs.get("deployment_start"),
            "deployment_end":global_attrs.get("deployment_end"),
            "caveat": "Dated file is not proof of complete deployment history; conflicting summary positions are retained in inventory"}


class Client:
    def __init__(self, transport, config):
        self.transport, self.config = transport, config
        if config.get("interpolation"):
            raise ValueError("Interpolation adapter not enabled; no silent interpolation")
        self.inventory, self.errors, self.loaded = [], [], {}

    def _legacy_products(self):
        found = []
        for p in self.transport.directory.glob("*.json"):
            try:
                entry = json.loads(p.read_text())
            except (ValueError, OSError):
                continue
            if entry.get("status") == "ok" and entry.get("legacy_source") and entry.get("url", "").endswith(".das"):
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
        ocean = catalog(self.transport, sub["oceanography"])
        met = catalog(self.transport, sub["meteorology"])
        geom = catalog(self.transport, sub["geomorphology"])
        paths = {r["name"]:r["url"] for r in ocean["references"]}
        wind_url = next(r["url"] for r in met["references"] if r["name"] == "wind")
        survey_url = next(r["url"] for r in geom["references"] if r["name"] == "elevationTransects")
        defaults = {"currents":"awac-11m","wind":"derived","water_level":"eopNoaaTide","bathymetry":"survey"}
        defaults.update(self.config.get("preferred_instruments",{}))
        choices = {"currents":(defaults["currents"],paths["currents"]),
                   "wind":(defaults["wind"],wind_url), "water_level":(defaults["water_level"],paths["waterlevel"]),
                   "bathymetry":(defaults["bathymetry"],survey_url)}
        months = sorted({utc(r["timestamp_utc"]).strftime("%Y%m") for r in acquisitions}, reverse=True)
        discovered = self._legacy_products()
        missing = [(instrument,month) for instrument in self.config["wave_instruments"] for month in months
                   if not any(p["instrument"]==instrument and p["month"]==month for p in discovered)]
        if missing and "waves" in self.config["families"]:
            try:
                wave_catalog=catalog(self.transport,paths["waves"])
                self.inventory.append({"family":"waves","source":paths["waves"],"discovered_instruments":wave_catalog["references"]})
                for instrument,month in missing:
                    ref=next((r for r in wave_catalog["references"] if r["name"]==instrument),None)
                    if ref is None:
                        self.inventory.append({"family":"waves","instrument":instrument,"status":"not_in_inspected_catalog_not_global_absence"})
                        continue
                    wave_products,state=discover_month(self.transport,ref["url"],month)
                    self.inventory.append({"family":"waves","instrument":instrument,"month":month,**state})
                    discovered.extend({**p,"family":"waves","instrument":instrument,"month":month,
                                       "source":p["services"].get("OpenDAP")} for p in wave_products[:1])
            except FetchError as exc:
                self.errors.append({"family":"waves","status":exc.status,"code":exc.code})
        # Real-time new discovery is family-limited, not an unrestricted crawler.
        for family,(preferred,url) in choices.items():
            if family not in self.config["families"]:
                continue
            try:
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
                    from .survey import inventory as survey_inventory, fetch_points
                    for acquisition in acquisitions:
                        try:
                            surveys=survey_inventory(self.transport,ref["url"],acquisition["timestamp_utc"])
                            self.inventory.append({"family":family,"acquisition_id":acquisition["acquisition_id"],**surveys})
                            if self.config.get("bathymetry_download"):
                                selections=self.config.get("survey_selections",{})
                                for product in surveys["products"]:
                                    key=product["services"].get("OpenDAP")
                                    if key in selections:
                                        result=fetch_points(self.transport,product,selections[key],acquisition.get("roi") or acquisition.get("footprint"))
                                        self.inventory.append({"family":family,"acquisition_id":acquisition["acquisition_id"],"survey_subset":result})
                        except FetchError as exc:
                            self.inventory.append({"family":family,"acquisition_id":acquisition["acquisition_id"],
                                                   "status":"incomplete_budget" if self.transport.state["transactions"]>=self.transport.state["max_transactions"] else exc.status,
                                                   "date_method_datum_coverage":"not verified; no download"})
                    continue
                for month in months:
                    # Verification prioritizes October; later months still attempted only if budget permits.
                    products, state = discover_month(self.transport,ref["url"],month)
                    self.inventory.append({"family":family,"instrument":preferred,"month":month,**state})
                    for product in products[:1]:
                        discovered.append({**product,"source":product["services"].get("OpenDAP"),
                                           "instrument":preferred,"family":family,"month":month})
            except FetchError as exc:
                self.errors.append({"family":family,"status":exc.status,"code":exc.code})
        return discovered

    def load(self, product, acquisitions, *, extended=True):
        family, url = product["family"], product["source"]
        key = url
        if key in self.loaded:
            return self.loaded[key]
        legacy = family == "waves" and product.get("discovery")
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
        if extended:
            if legacy:
                shapes = dds_shapes(self.transport.get(url+".dds").decode())
                meta["shapes"] = shapes
            else:
                shapes = meta["shapes"]
            if not shapes.get("time") or shapes["time"] != [len(times)]:
                raise FetchError("unsupported_time_dimensions")
            targets = [utc(a["timestamp_utc"]).timestamp() for a in acquisitions if utc(a["timestamp_utc"]).strftime("%Y%m") == product["month"]]
            context = self.config["event_context_seconds"]
            valid_times = mask_values(original["time"], meta["attributes"]["time"])
            indices = np.flatnonzero(valid_times & (times >= min(targets)-context) & (times <= max(targets)+context))
            if len(indices):
                lo, hi = int(indices.min()), int(indices.max())
                if hi-lo > self.config.get("max_event_samples",2000):
                    raise FetchError("event_window_too_broad_split_manifest")
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
                original = ascii_arrays(self.transport.get(data_url).decode())
                times = cf_times(original["time"],meta["attributes"]["time"]["units"])
                meta["event_subset_source"] = data_url
            else:
                meta["subset_status"] = "no_samples_in_event_context; cached stale context retained"
        masks = {name: mask_values(array,meta["attributes"].get(name,{})) for name,array in original.items()}
        bounds_name=meta["attributes"].get("time",{}).get("bounds")
        intervals=cf_times(original[bounds_name],meta["attributes"]["time"]["units"]) if bounds_name in original and np.asarray(original[bounds_name]).shape==(len(times),2) else None
        result = {"metadata":meta,"arrays":original,"masks":masks,"times":times,"intervals":intervals,
                  "initial_times":initial_times,"initial_arrays":initial_original,
                  "coverage":{"actual_time_min":float(initial_times.min()),"actual_time_max":float(initial_times.max()),
                              "scope":"verified monthly time vector; gaps not filled; QC search limited to fetched event context"}}
        self.loaded[key] = result
        return result

    def run(self, acquisitions, output, mode="offline"):
        from .output import dossier
        if mode=="offline" and not self.transport.offline:
            raise ValueError("Offline mode requires an offline Transport")
        output.mkdir(parents=True,exist_ok=True)
        ids=[re.sub(r"[^A-Za-z0-9_.-]","_",a["acquisition_id"]) for a in acquisitions]
        if len(ids)!=len(set(ids)):
            raise ValueError("Acquisition IDs collide after filename sanitization")
        products = self.discover(acquisitions)
        selected = [p for p in products if p["family"] in self.config["families"] and (p["family"] != "waves" or p["instrument"] in self.config["wave_instruments"])]
        # Fetch primary event wave systems before ancillary products; October before June.
        selected.sort(key=lambda p:(p["family"] != "waves", -int(p["month"]), p["instrument"] != "waverider-17m"))
        for product in selected:
            relevant = [a for a in acquisitions if utc(a["timestamp_utc"]).strftime("%Y%m") == product["month"]]
            if not relevant:
                continue
            try:
                if mode == "inventory":
                    meta = metadata(self.transport,product) if product["family"] != "waves" else self._load_legacy(product)[0]
                    self.inventory.append({**product,"metadata":meta,"status":"metadata_verified_not_observations_fetched"})
                    continue
                extended = not product.get("discovery") or product["family"] != "waves" or product["instrument"] in self.config.get("spectral_instruments",["waverider-17m","awac-11m"])
                loaded = self.load(product,acquisitions,extended=extended)
                product["loaded"] = loaded
                self.inventory.append({k:v for k,v in product.items() if k != "loaded"} | {"metadata":loaded["metadata"],"coverage":loaded["coverage"],"status":"retrieved"})
            except (FetchError, ValueError, RuntimeError) as exc:
                self.errors.append({"source":product["source"],"family":product["family"],"instrument":product["instrument"],
                                    "month":product["month"],"status":("incomplete_budget_cache_not_available" if isinstance(exc,FetchError) and exc.status=="offline_cache_miss" and self.transport.state["transactions"]>=self.transport.state["max_transactions"] else exc.status) if isinstance(exc,FetchError) else "unsupported_or_malformed_payload", "detail":type(exc).__name__})
                if product.get("discovery") == "verified_Block30_response_provenance":
                    # A failed spectral expansion must not discard verified local contemporaneous bulk context.
                    loaded=self.load(product,acquisitions,extended=False)
                    loaded["metadata"]["extended_status"]="unavailable; cached bulk context only; QC not inferred"
                    product["loaded"]=loaded
                    self.inventory.append({k:v for k,v in product.items() if k!="loaded"} | {"metadata":loaded["metadata"],"coverage":loaded["coverage"],"status":"verified_cached_bulk_context_only"})
        for acquisition in acquisitions:
            relevant = [p for p in selected if p.get("loaded") and utc(acquisition["timestamp_utc"]).strftime("%Y%m") == p["month"]]
            dossier(acquisition,relevant,self.inventory,self.errors,self.config,output,self.transport)
        save_json(output/"INVENTORY.json",self.inventory)
        save_json(output/"STATUS.json", {"errors":self.errors,"network":self.transport.state,
                                        "no_radar_access":True,"mode":mode,"event_representative_state":"not mixed across instruments"})

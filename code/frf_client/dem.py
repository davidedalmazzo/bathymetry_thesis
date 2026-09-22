"""FRF gridded survey DEM (THREDDS geomorphology/DEMs/surveyDEM) nearest to an epoch.

Uses the budgeted/cached Transport and the THREDDS catalog walker of the FRF
client; never guesses filenames.  Elevations are NAVD88 bed elevations.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
import numpy as np
from .catalog import catalog
from .data import ascii_arrays, mask_values, das_attributes

SURVEY_DEM = "https://chldata.erdc.dren.mil/thredds/catalog/frf/geomorphology/DEMs/surveyDEM/data/catalog.xml"


def list_survey_dems(transport, url=SURVEY_DEM):
    out = []
    for p in catalog(transport, url)["products"]:
        m = re.search(r"(20\d{6}|19\d{6})", p["name"] or "")
        if m:
            d = datetime.strptime(m[1], "%Y%m%d").replace(tzinfo=timezone.utc)
            out.append({**p, "date_from_filename": d.date().isoformat(), "epoch": d.timestamp()})
    return sorted(out, key=lambda p: p["epoch"])


def nearest_survey_dem(transport, epoch, max_days=45.0, prefer_before=False):
    items = list_survey_dems(transport)
    if prefer_before:
        items = [p for p in items if p["epoch"] <= epoch] or items
    if not items:
        return None
    best = min(items, key=lambda p: abs(p["epoch"] - epoch))
    if abs(best["epoch"] - epoch) > max_days * 86400:
        return None
    best["offset_days"] = (best["epoch"] - epoch) / 86400
    return best


def fetch_survey_dem(transport, product):
    odap = product["services"].get("OPENDAP") or product["services"].get("OpenDAP")
    if not odap:
        raise ValueError("survey DEM product lacks an OPeNDAP service")
    das = das_attributes(transport.get(odap + ".das").decode())
    arr = ascii_arrays(transport.get(odap + ".ascii?xFRF,yFRF,elevation,latitude,longitude,time").decode())
    raw = np.asarray(arr["elevation"], float)[0]
    elev = np.where(mask_values(raw, das.get("elevation", {})), raw, np.nan)   # mask_values returns the validity mask
    t = float(np.ravel(arr["time"])[0])
    return {"xFRF": np.asarray(arr["xFRF"]), "yFRF": np.asarray(arr["yFRF"]), "elevation_navd88": np.asarray(elev, float),
            "latitude": np.asarray(arr["latitude"]), "longitude": np.asarray(arr["longitude"]),
            "survey_time_utc": datetime.fromtimestamp(t, timezone.utc).isoformat(), "source": odap,
            "vertical_datum": "NAVD88", "note": "gridded from FRF monthly survey lines; interpolated between lines"}

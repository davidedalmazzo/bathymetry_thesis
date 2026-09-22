"""NOAA NCEI CUDEM (Continuously Updated DEM) topobathy retrieval for a lon/lat bbox.

Generic for US coasts covered by CUDEM 1/9 arc-second tiles (NAVD88, EPSG:4269).
Tiles are selected from the official url list by the corner encoded in the
filename; only the bbox window is read over HTTP range (GDAL /vsicurl), so a
260 MB tile is never downloaded whole.  The clipped raster and its provenance
are written locally.
"""
from __future__ import annotations
import json, math, re, urllib.request
from pathlib import Path
import numpy as np

URLLIST = "https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/NCEI_ninth_Topobathy_2014_8483/urllist8483.txt"
TILE_RE = re.compile(r"ncei19_n(\d+)x(\d+)_w(\d+)x(\d+)_(\d{4})v(\d+)\.tif$")


def _tile_bounds(name):
    m = TILE_RE.search(name)
    if not m:
        return None
    north = int(m[1]) + int(m[2]) / 100; west = -(int(m[3]) + int(m[4]) / 100)
    return west, north - 0.25, west + 0.25, north, int(m[5]), int(m[6])


def tiles_for_bbox(bbox, cache_dir):
    cache = Path(cache_dir); cache.mkdir(parents=True, exist_ok=True)
    f = cache / "urllist8483.txt"
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(URLLIST, timeout=60).read())
    lon0, lat0, lon1, lat1 = bbox; best = {}
    for url in f.read_text().split():
        b = _tile_bounds(url)
        if b and b[0] < lon1 and b[2] > lon0 and b[1] < lat1 and b[3] > lat0:
            key = b[:4]
            if key not in best or b[4:] > best[key][1]:        # newest year/version for a tile
                best[key] = (url, b[4:])
    return [u for u, _ in best.values()]


def read_cudem(bbox, out_tif, cache_dir):
    import rasterio
    from rasterio.merge import merge
    urls = tiles_for_bbox(bbox, cache_dir)
    if not urls:
        return None
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        srcs = [rasterio.open("/vsicurl/" + u) for u in urls]
        tags = [dict(s.tags()) for s in srcs]
        arr, transform = merge(srcs, bounds=tuple(bbox), nodata=-9999.0)
        crs = srcs[0].crs
        for s in srcs:
            s.close()
    a = arr[0].astype("float32"); a[a <= -9998] = np.nan
    out = Path(out_tif); out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out, "w", driver="GTiff", height=a.shape[0], width=a.shape[1], count=1, dtype="float32",
                       crs=crs, transform=transform, nodata=np.nan, compress="deflate") as ds:
        ds.write(a, 1); ds.update_tags(vertical_datum="NAVD88", source="NOAA NCEI CUDEM 1/9 arc-second", tiles=",".join(urls))
    prov = {"product": "NOAA NCEI CUDEM 1/9 arc-second topobathy (dataset 8483)", "tiles": urls,
            "tile_tags": tags, "vertical_datum": "NAVD88 (tile description)", "horizontal_crs": str(crs),
            "valid_fraction": float(np.isfinite(a).mean()), "min_max_m": [float(np.nanmin(a)), float(np.nanmax(a))],
            "caveat": "mosaic of multi-year sources (see CUDEM metadata); nearshore bars change seasonally"}
    Path(str(out) + ".provenance.json").write_text(json.dumps(prov, indent=2))
    return prov


# ---------------------------------------------------------------- NOAA BlueTopo
BLUETOPO_BUCKET = "https://noaa-ocs-nationalbathymetry-pds.s3.amazonaws.com"


def _bluetopo_scheme(cache_dir):
    """Newest BlueTopo tile-scheme GeoPackage (cached)."""
    import xml.etree.ElementTree as ET
    cache = Path(cache_dir); cache.mkdir(parents=True, exist_ok=True)
    listing = urllib.request.urlopen(f"{BLUETOPO_BUCKET}/?list-type=2&prefix=BlueTopo/_BlueTopo_Tile_Scheme/", timeout=60).read()
    ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
    keys = sorted(k.text for k in ET.fromstring(listing).findall(".//s:Key", ns) if k.text.endswith(".gpkg"))
    if not keys:
        raise RuntimeError("BlueTopo tile scheme not found")
    f = cache / Path(keys[-1]).name
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(f"{BLUETOPO_BUCKET}/{keys[-1]}", timeout=120).read())
    return f


def bluetopo_tiles_for_bbox(bbox, cache_dir):
    import sqlite3
    import shapely.wkb
    from shapely.geometry import box
    f = _bluetopo_scheme(cache_dir)
    con = sqlite3.connect(f)
    table = con.execute("select table_name from gpkg_contents").fetchone()[0]
    cols = [r[1] for r in con.execute(f"pragma table_info('{table}')")]
    gcol = next(c for c in cols if c.lower() in ("geom", "geometry", "shape"))
    bb = box(*bbox); out = []
    for row in con.execute(f"select * from '{table}'"):
        rec = dict(zip(cols, row)); b = rec[gcol]
        env = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(b[3] >> 1) & 7]
        if rec.get("GeoTIFF_Link") and shapely.wkb.loads(bytes(b[8 + env:])).intersects(bb):
            out.append({k: v for k, v in rec.items() if k != gcol})
    return out, f.name


def _bluetopo_rat(url):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(urllib.request.urlopen(url, timeout=60).read())
    rat = root.find(".//GDALRasterAttributeTable")
    names = [f.find("Name").text for f in rat.findall("FieldDefn")]
    return {int(float(r.findall("F")[0].text)): dict(zip(names, [f.text for f in r.findall("F")])) for r in rat.findall("Row")}


def read_bluetopo(bbox, out_tif, cache_dir):
    """Elevation (NAVD88), vertical uncertainty and contributor bands for the bbox,
    plus the contributor table (survey id, institution, dates, uncertainty model)."""
    import rasterio
    from rasterio.merge import merge
    from rasterio.warp import transform_bounds
    tiles, scheme = bluetopo_tiles_for_bbox(bbox, cache_dir)
    if not tiles:
        return None
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tiff"):
        srcs = [rasterio.open("/vsicurl/" + t["GeoTIFF_Link"]) for t in tiles]
        crs = srcs[0].crs
        if any(s.crs != crs for s in srcs):
            raise RuntimeError("BlueTopo tiles in different UTM zones; split the bbox")
        b = transform_bounds(4326, crs, *bbox)
        arr, transform = merge(srcs, bounds=b, nodata=srcs[0].nodata, method="first")
        nodata = srcs[0].nodata
        for s in srcs:
            s.close()
    arr = arr.astype("float32")
    for i in range(arr.shape[0]):
        arr[i][arr[0] == nodata] = np.nan
    out = Path(out_tif); out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out, "w", driver="GTiff", height=arr.shape[1], width=arr.shape[2], count=3, dtype="float32",
                       crs=crs, transform=transform, nodata=np.nan, compress="deflate") as ds:
        ds.write(arr); ds.descriptions = ("Elevation NAVD88", "Vertical uncertainty", "Contributor")
    contrib = {}
    used = set(int(v) for v in np.unique(arr[2][np.isfinite(arr[2])]))
    for t in tiles:
        for k, v in _bluetopo_rat(t["RAT_Link"]).items():
            if k in used and k not in contrib:
                contrib[k] = {x: v.get(x) for x in ("source_survey_id", "source_institution", "survey_date_start", "survey_date_end",
                                                    "vertical_uncert_fixed", "vertical_uncert_var", "horizontal_uncert_fixed",
                                                    "horizontal_uncert_var", "coverage", "bathy_coverage")}
    cnt = {int(k): int(n) for k, n in zip(*np.unique(arr[2][np.isfinite(arr[2])], return_counts=True))}
    for k in contrib:
        contrib[k]["cells_in_bbox"] = cnt.get(k, 0)
    prov = {"product": "NOAA Office of Coast Survey BlueTopo (National Bathymetric Source)", "tile_scheme": scheme,
            "tiles": [{k: t[k] for k in ("tile", "GeoTIFF_Link", "Delivered_Date", "Resolution", "GeoTIFF_SHA256_Checksum")} for t in tiles],
            "vertical_datum": "NAVD88 (VERTICALDATUMWKT)", "horizontal_crs": str(crs),
            "contributors": {str(k): v for k, v in sorted(contrib.items(), key=lambda kv: -kv[1]["cells_in_bbox"])}}
    Path(str(out) + ".provenance.json").write_text(json.dumps(prov, indent=2))
    return prov


# ---------------------------------------------------------------- legacy grids
def legacy_spec(text, cache_dir):
    """'PATH|URL.zip,OFFSET,LABEL,YEAR' -> dict; zip URLs are cached and unpacked."""
    import zipfile
    parts = [p.strip() for p in text.split(",")]
    src, off = parts[0], float(parts[1]) if len(parts) > 1 else 0.0
    label = parts[2] if len(parts) > 2 else Path(src).stem
    year = float(parts[3]) if len(parts) > 3 else float("nan")
    if src.startswith("http"):
        cache = Path(cache_dir); cache.mkdir(parents=True, exist_ok=True)
        f = cache / Path(src).name
        if not f.exists():
            req = urllib.request.Request(src, headers={"User-Agent": "thesis-ground-truth/1.0"})
            f.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        dest = cache / f.stem
        if not dest.exists():
            with zipfile.ZipFile(f) as z:
                for m in z.namelist():
                    if not (dest / m).resolve().is_relative_to(dest.resolve()):
                        raise RuntimeError("unsafe path in zip")
                z.extractall(dest)
        hdr = sorted(dest.rglob("hdr.adf")) + sorted(dest.rglob("*.tif"))
        if not hdr:
            raise RuntimeError(f"no raster in {src}")
        src = str(hdr[0].parent if hdr[0].name == "hdr.adf" else hdr[0])
    return {"path": src, "datum_offset_to_navd88_m": off, "label": label, "year": year}

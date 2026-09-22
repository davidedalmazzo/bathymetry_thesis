"""Ground-truth retrieval helpers: CUDEM tile selection, FRF survey DEM masking."""
import numpy as np
import pytest

import coastal_dem
from frf_client import dem as frf_dem


def test_cudem_tile_bounds_from_name():
    b = coastal_dem._tile_bounds(".../NC/ncei19_n36x25_w075x75_2019v2.tif")
    assert b[:4] == pytest.approx((-75.75, 36.0, -75.5, 36.25)) and b[4:] == (2019, 2)


def test_cudem_tiles_for_bbox_picks_intersecting_newest(tmp_path):
    (tmp_path / "urllist8483.txt").write_text("\n".join([
        "https://x/NC/ncei19_n36x25_w075x75_2018v1.tif",
        "https://x/NC/ncei19_n36x25_w075x75_2019v2.tif",
        "https://x/NC/ncei19_n36x25_w076x00_2019v2.tif",
        "https://x/NC/ncei19_n35x00_w076x00_2019v2.tif"]))
    urls = sorted(coastal_dem.tiles_for_bbox((-75.79, 36.15, -75.70, 36.22), tmp_path))
    assert urls == ["https://x/NC/ncei19_n36x25_w075x75_2019v2.tif", "https://x/NC/ncei19_n36x25_w076x00_2019v2.tif"]


class FakeTransport:
    def __init__(self, das, ascii_):
        self.das, self.ascii_ = das, ascii_
    def get(self, url):
        return (self.das if url.endswith(".das") else self.ascii_).encode()


def test_survey_dem_values_not_replaced_by_validity_mask():
    das = 'Attributes {\n elevation {\n Float64 _FillValue -999.0;\n String units "m";\n }\n}\n'
    ascii_ = ("Dataset {} x;\n---------------------------------------------\n"
              "elevation.elevation[1][2][2]\n[0][0], -3.5, -999.0\n[0][1], -6.25, 1.5\n\n"
              "xFRF[2]\n50.0, 62.0\n\nyFRF[2]\n0.0, 24.0\n\n"
              "latitude.latitude[2][2]\n[0], 36.1, 36.1\n[1], 36.2, 36.2\n\n"
              "longitude.longitude[2][2]\n[0], -75.7, -75.6\n[1], -75.7, -75.6\n\ntime[1]\n1.6347744E9\n")
    out = frf_dem.fetch_survey_dem(FakeTransport(das, ascii_), {"services": {"OPENDAP": "https://h/x.nc"}})
    e = out["elevation_navd88"]
    assert e[0, 0] == pytest.approx(-3.5) and np.isnan(e[0, 1]) and e[1, 1] == pytest.approx(1.5)


def test_merge_corrects_legacy_bias_against_modern(tmp_path):
    """A legacy grid offset by +0.7 m is shifted back using its overlap with a modern
    (non-interpolated, recent) BlueTopo contributor deeper than legacy_min_depth."""
    import rasterio
    from rasterio.transform import from_origin
    import frf_ground_truth as g
    bbox = (-75.79, 36.15, -75.70, 36.22)
    x0, y1 = 425000.0, 4008000.0
    import pyproj
    tr = pyproj.Transformer.from_crs(4326, 32618, always_xy=True)
    xs, ys = tr.transform([bbox[0], bbox[2]], [bbox[1], bbox[3]])
    T = from_origin(min(xs) - 500, max(ys) + 500, 20, 20)
    ny, nx = int((max(ys) - min(ys) + 1000) / 20), int((max(xs) - min(xs) + 1000) / 20)
    truth = -(5 + 15 * np.linspace(0, 1, nx))[None, :].repeat(ny, 0).astype("float32")
    bt = np.stack([truth, np.full_like(truth, 1.0), np.full_like(truth, 7.0)])
    bt[:, :, nx // 2:] = np.nan                      # modern data only on the inshore half
    with rasterio.open(tmp_path / "bt.tif", "w", driver="GTiff", height=ny, width=nx, count=3, dtype="float32",
                       crs="EPSG:32618", transform=T, nodata=np.nan) as ds:
        ds.write(bt)
    with rasterio.open(tmp_path / "leg.tif", "w", driver="GTiff", height=ny, width=nx, count=1, dtype="float32",
                       crs="EPSG:32618", transform=T, nodata=np.nan) as ds:
        ds.write((truth + 0.7)[None])
    prov = {"contributors": {"7": {"source_survey_id": "lidar", "survey_date_start": "2019-06-01"}}}
    r = g.merged_bathymetry(bbox, None, 20.0, tmp_path / "m.tif", 0.0, bluetopo_tif=tmp_path / "bt.tif",
                            bluetopo_prov=prov, legacy=[{"path": str(tmp_path / "leg.tif"), "datum_offset_to_navd88_m": 0.0,
                                                         "label": "leg", "year": 2001}], min_overlap_cells=50)
    assert r["legacy"][0]["bias_vs_modern_m"] == pytest.approx(0.7, abs=0.02)
    with rasterio.open(tmp_path / "m.tif") as ds:
        z, src = ds.read(1), ds.read(2)
    assert np.any(src == 4) and np.any(src == 3)
    ref = np.full(z.shape, np.nan, "float32")
    from rasterio.warp import reproject, Resampling
    reproject(truth, ref, src_transform=T, src_crs="EPSG:32618", dst_transform=ds.transform, dst_crs=ds.crs,
              resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
    k = (src == 4) & np.isfinite(ref)
    assert np.nanmedian(np.abs(z[k] - ref[k])) < 0.05

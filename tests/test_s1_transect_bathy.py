"""Generic S1 transect tool: burst-time geolocation, spectra, coastline/transects."""
from datetime import datetime, timedelta, timezone
import math

import numpy as np
import pytest

import s1_paper_peak as pp
import s1_transect_bathy as tb
from s1_iw_geometry import SwathGeometry, window_inside_single_burst


def synthetic_annotation(lpb=100, nb=3, ati=0.002, overlap_lines=10, ns=50):
    """Grid rows at burst starts; bursts overlap by `overlap_lines` in time.
    Ground truth: lon = 0.001*sample, lat = 1e-3 * (time/ati) (one 'unit' per azimuth sample of time)."""
    t0 = datetime(2021, 1, 1, tzinfo=timezone.utc)
    step = (lpb - overlap_lines) * ati
    bursts, pts = [], []
    for b in range(nb):
        tb_ = t0 + timedelta(seconds=b * step)
        bursts.append({"azimuth_time": tb_.isoformat(), "first_valid_sample": [0] * lpb, "last_valid_sample": [ns - 1] * lpb,
                       "line_start": b * lpb})
    for b in range(nb + 1):
        t = b * step if b < nb else (nb - 1) * step + lpb * ati
        line = b * lpb if b < nb else nb * lpb - 1
        for s in (0, 25, 49):
            pts.append({"azimuthTime": (t0 + timedelta(seconds=t)).isoformat(), "pixel": s, "line": line,
                        "longitude": 0.001 * s, "latitude": 1e-3 * t / ati, "incidenceAngle": 40.0})
    return {"swath": "IW1", "lines_per_burst": lpb, "azimuth_time_interval_s": ati, "number_of_samples": ns,
            "number_of_lines": nb * lpb, "geolocation_grid": pts, "bursts": bursts}


def test_burst_time_geolocation_not_line_interpolation():
    ann = synthetic_annotation()
    g = SwathGeometry(ann)
    # line 80 of burst 0 is at time 80*ati -> latitude 0.080 (a line-number model would give 80/100*90*1e-3=0.072)
    lon, lat = g.forward(10.0, 80.0)
    assert lat == pytest.approx(0.080, abs=1e-6)
    lon, lat = g.forward(10.0, 105.0)          # burst 1, 5 lines in: t = 90*ati + 5*ati
    assert lat == pytest.approx(0.095, abs=1e-6)


def test_inverse_returns_both_bursts_in_overlap():
    g = SwathGeometry(synthetic_annotation())
    cands = g.candidates(0.010, 0.095)          # time 95*ati: burst0 line 95 and burst1 line 5
    lines = sorted(round(c["line"], 3) for c in cands)
    assert lines == [95.0, 105.0]
    assert cands[0]["line_margin"] >= cands[-1]["line_margin"]


def test_window_inside_single_burst():
    ann = synthetic_annotation()
    assert window_inside_single_burst(ann, 0, 5, 10, 40, 60)
    assert not window_inside_single_burst(ann, 0, 5, 90, 40, 110)   # crosses into next burst


def test_affine_dtft_equals_exact_nudft():
    rng = np.random.default_rng(2)
    z = rng.normal(size=(20, 60))
    J = np.array([[3.3, -2.0], [0.5, 13.9]])
    L, S = np.mgrid[0:20, 0:60].astype(float)
    Sc, Lc = S - S.mean(), L - L.mean()
    E = J[0, 0] * Sc + J[0, 1] * Lc; N = J[1, 0] * Sc + J[1, 1] * Lc
    k = np.linspace(-0.2, 0.2, 21)
    a = tb.dtft_affine(z, J, k)
    b = pp.nudft_magnitude(z, E, N, k, k)
    assert np.allclose(a, b, rtol=1e-9, atol=1e-9)


def test_otsu_separates_two_modes():
    rng = np.random.default_rng(0)
    v = np.concatenate((rng.normal(-20, 1, 5000), rng.normal(-5, 1, 5000)))
    assert -18 < tb.otsu(v) < -7          # anywhere inside the empty gap between modes


def test_coastline_and_transects_point_to_sea():
    sea = np.zeros((60, 80), bool); sea[:, 40:] = True        # sea to the east
    smap = {"sigma0": np.ones(sea.shape), "count": np.ones(sea.shape), "e0": 0.0, "n0": 0.0, "res": 50.0}
    coast, raw = tb.coastline(sea, smap, smooth_m=200.0)
    assert np.allclose(coast[:, 0], 2000.0, atol=30)
    trs = tb.transects(coast, sea, smap, spacing=250.0, smooth_m=200.0, test_d=300.0)
    assert trs and all(t["normal_E"] > 0.99 for t in trs)
    assert all(abs(t["seaward_bearing_deg"] - 90) < 1 for t in trs)


def test_grd_geometry_roundtrip():
    from s1_iw_geometry import GrdGeometry
    pts = [{"line": l, "pixel": p, "longitude": -75 + 1e-4 * p, "latitude": 36 + 1e-4 * l, "incidenceAngle": 40.0}
           for l in (0, 100, 200, 300, 400) for p in (0, 100, 200, 300, 400)]
    ann = {"swath": "IW", "number_of_lines": 401, "number_of_samples": 401, "geolocation_grid": pts,
           "bursts": [{"first_valid_sample": [0] * 401, "last_valid_sample": [400] * 401}], "lines_per_burst": 401}
    g = GrdGeometry(ann)
    lon, lat = g.forward(123.4, 234.5)
    c = g.candidates(lon, lat)
    assert len(c) == 1 and c[0]["sample"] == pytest.approx(123.4, abs=1e-6) and c[0]["line"] == pytest.approx(234.5, abs=1e-6)


def _smap(sig):
    return {"sigma0": sig, "e0": 0.0, "n0": 0.0, "res": 10.0}


def test_sea_side_picks_component_touching_that_side_not_padding_artifact():
    # land (bright) on the west 30 columns, sea (dark) on the east 50: both touch N and S borders.
    rng = np.random.default_rng(0)
    sig = np.where(np.arange(80)[None, :] < 30, 1.0, 0.01) * rng.uniform(0.8, 1.2, (60, 80))
    sea, info = tb.sea_mask_from_sar(_smap(sig), "E")
    assert info["sea_class"] == "dark"
    assert sea[:, 40:].all() and not sea[:, :25].any()
    assert info["sea_side_contact_fraction"] == pytest.approx(1.0)
    # the west side must select the land class: with border_value=1 padding both classes touched every side
    land, info_w = tb.sea_mask_from_sar(_smap(sig), "W")
    assert info_w["sea_class"] == "bright"


def test_sea_side_tie_raises():
    # diagonal-free split along N/S: both classes touch side E with equal length
    sig = np.where(np.arange(60)[:, None] < 30, 1.0, 0.01) * np.ones((60, 80))
    with pytest.raises(SystemExit):
        tb.sea_mask_from_sar(_smap(sig), "E")

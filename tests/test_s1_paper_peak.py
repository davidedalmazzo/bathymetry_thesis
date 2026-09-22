"""Paper-inspired (Mudiyanselage et al. 2024) contour-blob peak identification."""
import inspect
import math

import numpy as np
import pytest

import s1_paper_peak as pp


def native_grid(ns=153, nl=41, rot_deg=9.0, ds=3.35, dl=12.37):
    th = math.radians(rot_deg)
    r = np.array([math.cos(th), math.sin(th)]); a = np.array([-math.sin(th), math.cos(th)])
    S, L = np.meshgrid(np.arange(ns) - ns/2, np.arange(nl) - nl/2)
    return S*ds*r[0] + L*dl*a[0], S*ds*r[1] + L*dl*a[1], a


def spectrum(lam, deg, mod, seed, window=512.0, padding=1):
    x, y, a = native_grid()
    rng = np.random.default_rng(seed); k0 = 2*np.pi/lam
    img = (1 + mod*np.cos(k0*math.cos(math.radians(deg))*x + k0*math.sin(math.radians(deg))*y)) * rng.exponential(1, x.shape)
    z = pp.plane_detrend(img, x, y) * pp.hann2(img.shape)
    k, dk = pp.k_grid(window, padding, 0.30)
    mask = pp.search_mask(k, k, 2*2*np.pi/window, [(a[0], a[1], 0.8*np.pi/12.37)])
    return pp.nudft_magnitude(z, x, y, k, k), k, mask


def test_nudft_matches_fft_on_regular_grid():
    rng = np.random.default_rng(0); n = 16; d = 5.0
    z = rng.normal(size=(n, n)); x, y = np.meshgrid(np.arange(n)*d, np.arange(n)*d)
    k = 2*np.pi*np.fft.fftshift(np.fft.fftfreq(n, d))
    ref = np.abs(np.fft.fftshift(np.fft.fft2(z)))
    assert np.allclose(pp.nudft_magnitude(z, x, y, k, k), ref, atol=1e-9)


def test_nudft_magnitude_is_conjugate_symmetric():
    mag, k, _ = spectrum(80, 10, .3, 1)
    assert np.allclose(mag, mag[::-1, ::-1], rtol=1e-10, atol=1e-10)


@pytest.mark.parametrize("lam,deg", [(80, 10), (120, -20), (50, 30)])
def test_contour_peak_recovers_known_sinusoid_on_rotated_anisotropic_grid(lam, deg):
    errs, angs = [], []
    for seed in range(6):
        mag, k, mask = spectrum(lam, deg, .3, seed)
        res = pp.paper_peak(mag, k, k, mask)
        assert res["status"] in ("identified", "ambiguous_multiple_blobs")
        errs.append(res["wavelength_m"]/lam - 1)
        angs.append(pp.axial_difference(math.degrees(math.atan2(res["ky"], res["kx"])), deg))
    assert abs(np.median(errs)) < 0.06
    assert np.median(angs) < 8


def test_levels_are_twenty_interior_and_threshold_is_top():
    lev = pp.matlab_like_levels(0.0, 21.0, 20)
    assert len(lev) == 20 and lev[0] == pytest.approx(1.0) and lev[-1] == pytest.approx(20.0)


def test_selection_prefers_largest_then_closest_blob():
    k = np.arange(-20, 21) * 0.01
    mag = np.ones((k.size, k.size))
    c = 20
    mag[c+0:c+1, c+6:c+9] = 100.0      # 3-pixel blob, |k|~0.07
    mag[c+0, c+4] = 100.0              # 1-pixel blob closer to origin
    mag = np.maximum(mag, mag[::-1, ::-1])
    mask = np.hypot(*np.meshgrid(k, k)) >= 0.02
    res = pp.paper_peak(mag, k, k, mask, scale="linear")
    assert res["selected"]["area_px"] == 3
    assert res["kx"] == pytest.approx(0.07)
    assert res["symmetric_partner_found"]
    assert res["wavelength_m"] == pytest.approx(2*np.pi/0.07)


def test_equal_area_tie_goes_to_closest_to_origin():
    k = np.arange(-20, 21) * 0.01; c = 20
    mag = np.ones((k.size, k.size)); mag[c, c+5] = 50; mag[c, c+12] = 50
    mag = np.maximum(mag, mag[::-1, ::-1])
    res = pp.paper_peak(mag, k, k, np.hypot(*np.meshgrid(k, k)) >= 0.02, scale="linear")
    assert res["kx"] == pytest.approx(0.05)
    assert res["status"] == "ambiguous_multiple_blobs"


def test_fastpeakfind_port_median_removes_single_pixel_blob():
    d = np.zeros((21, 21)); d[10, 10] = 10.0
    assert pp.fastpeakfind_centroids(d, 1.0) == []
    d[8:13, 8:13] = 10.0
    blobs = pp.fastpeakfind_centroids(d, 1.0)
    assert len(blobs) == 1 and blobs[0]["centroid_row"] == pytest.approx(10.0) and blobs[0]["centroid_col"] == pytest.approx(10.0)


def test_sar_peak_functions_have_no_bathymetry_or_period_inputs():
    for fn in (pp.paper_peak, pp.argmax_peak, pp.search_mask, pp.nudft_magnitude, pp.contour_blobs):
        names = set(inspect.signature(fn).parameters)
        assert not names & {"depth", "h", "bathymetry", "omega", "period", "survey", "T", "expected_wavelength"}


def test_frf_affine_roundtrip_and_bearings():
    rng = np.random.default_rng(3)
    x = rng.uniform(0, 1000, 50); y = rng.uniform(-100, 1300, 50)
    lon = -75.75 + 1e-5*x - 3e-6*y; lat = 36.18 + 3e-6*x + 8e-6*y
    coef, fit = pp.fit_frf_geo_affine(x, y, lon, lat)
    xb, yb = pp.geo_to_frf(coef, lon, lat)
    assert np.allclose(xb, x) and np.allclose(yb, y) and fit["residual_max_m"] < 1e-6


def test_moving_mean_uses_only_valid_points():
    v = [1, 2, 100, 4, 5, 6]; ok = [1, 1, 0, 1, 1, 1]
    mm = pp.moving_mean(v, ok, 5, 3)
    assert np.isnan(mm[2]) and np.isnan(mm[0]) and mm[1] == pytest.approx(7/3) and mm[5] == pytest.approx(5)


def test_eq5_depth_and_eq6_tmin():
    lam, T = 77.0, 11.765
    h = pp.depth_from_wavelength_period(lam, T)
    k = 2*np.pi/lam
    assert (2*np.pi/T)**2 == pytest.approx(9.80665*k*np.tanh(k*h))
    assert math.isnan(pp.depth_from_wavelength_period(300, 10))
    assert pp.minimum_period(216.0) == pytest.approx(math.sqrt(2*np.pi*216/9.80665))


def test_window_inside_burst_rejects_invalid_lines_and_samples():
    ann = {"bursts": [{"line_start": 0, "first_valid_sample": [-1] + [10]*9, "last_valid_sample": [-1] + [90]*9}]}
    assert pp.window_inside_burst(ann, 0, 20, 2, 50, 8)[0]
    assert not pp.window_inside_burst(ann, 0, 20, 0, 50, 8)[0]
    assert not pp.window_inside_burst(ann, 0, 5, 2, 50, 8)[0]
    assert not pp.window_inside_burst(ann, 0, 20, 2, 95, 8)[0]

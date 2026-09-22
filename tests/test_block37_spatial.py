from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

from s1_spatial_trial import (
    calibrated_power, conjugate_average, fit_frf_affine, frf_to_geo,
    grid_coordinates, parse_calibration_lut, read_resampled_complex,
    spatial_spectrum,
)


def test_calibration_uses_power_divided_by_lut_squared(tmp_path):
    xml = b"""<calibration><calibrationVectorList>
      <calibrationVector><line>0</line><pixel count="2">0 9</pixel><sigmaNought count="2">2 2</sigmaNought></calibrationVector>
      <calibrationVector><line>9</line><pixel count="2">0 9</pixel><sigmaNought count="2">2 2</sigmaNought></calibrationVector>
    </calibrationVectorList></calibration>"""
    path = tmp_path / "cal.xml"; path.write_bytes(xml)
    lut = parse_calibration_lut(path)
    dn = np.asarray([[3+4j]])
    got = calibrated_power(dn, lut, np.asarray([[4.]]), np.asarray([[5.]]))
    assert got[0, 0] == 6.25


def test_frf_affine_reconstructs_frozen_rectangle():
    bounds = [0, 10, 0, 20]
    geo = {"coordinates": [[[1, 2], [3, 2], [3, 6], [1, 6], [1, 2]]]}
    coef, residual = fit_frf_affine(bounds, geo)
    lon, lat = frf_to_geo(coef, 5, 10)
    assert residual < 1e-12
    assert np.allclose([lon, lat], [2, 4])


def test_complex_iq_window_read_and_exact_support(tmp_path):
    path = tmp_path / "complex.tif"
    source = (np.arange(100).reshape(10, 10) + 1j*np.arange(100, 200).reshape(10, 10)).astype("complex64")
    with rasterio.open(path, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype="complex64", transform=Affine.identity()) as ds:
        ds.write(source, 1)
    annotation = {"number_of_samples": 10, "number_of_lines": 10,
                  "bursts": [{"line_start": 0, "first_valid_sample": [0]*10,
                              "last_valid_sample": [9]*10}]}
    class Grid:
        @staticmethod
        def geo_to_image(lon, lat): return lon, lat
    coef = np.asarray([[0, 0], [1, 0], [0, 1]], float)
    xx, yy = np.meshgrid(np.arange(2, 6), np.arange(3, 7))
    got, lines, samples, valid, support = read_resampled_complex(
        path, annotation, Grid(), coef, xx, yy, order=0, burst_index=0)
    assert np.iscomplexobj(got) and np.all(got.real == source[3:7, 2:6].real)
    assert np.all(got.imag == source[3:7, 2:6].imag)
    assert valid.all() and support["all_contributing_samples_valid"]


def test_conjugate_average_is_centrosymmetric():
    rng = np.random.default_rng(4)
    p = rng.random((10, 12))
    kx = 2*np.pi*np.fft.fftshift(np.fft.fftfreq(12))
    ky = 2*np.pi*np.fft.fftshift(np.fft.fftfreq(10))
    q = conjugate_average(p, kx, ky)
    ix = (2*(len(kx)//2)-np.arange(len(kx))) % len(kx)
    iy = (2*(len(ky)//2)-np.arange(len(ky))) % len(ky)
    assert np.allclose(q, q[np.ix_(iy, ix)])


def test_known_sinusoid_recovers_axes_k_wavelength_and_conjugates():
    xx, yy = grid_coordinates((0, 0), (512, 512), (4, 4))
    kx = 2*np.pi*8/512
    ky = 2*np.pi*5/512
    image = 2 + .2*xx/np.ptp(xx) + np.cos(kx*xx + ky*yy + .31)
    result = spatial_spectrum(image, xx, yy, detrend="plane", taper="hann",
                              padding=2, exclusion_bins=2, basis_en=np.eye(2))
    expected = np.hypot(kx, ky)
    assert abs(result["k_magnitude_rad_m"]-expected) < .003
    assert abs(result["wavelength_m"]-2*np.pi/expected) < 2
    assert result["conjugate_closure_relative"] < 1e-12


def test_sar_peak_api_has_no_bathymetry_or_expected_wave_input():
    names = set(inspect.signature(spatial_spectrum).parameters)
    assert names.isdisjoint({"depth", "bathymetry", "expected_k", "expected_wavelength", "frf_peak"})

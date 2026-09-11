from __future__ import annotations

import math

import numpy as np
import pytest

from umbra_sar.physical_identification import (
    axial_difference_deg,
    directional_difference_deg,
    frequency_bin_edges,
    ndbc_directional_distribution,
    propagation_to_deg,
    quasi_linear_cross_spectrum,
    quasi_linear_zero_lag_phase_slope,
    required_depth_for_period_wavelength,
)


def test_dispersion_required_depth_for_frozen_wavelength_and_periods() -> None:
    wavelength = 130.6028192373831
    depth_sar = required_depth_for_period_wavelength(17.902230457045317, wavelength)
    depth_buoy = required_depth_for_period_wavelength(13.33, wavelength)
    assert depth_sar == pytest.approx(5.55575545882108, abs=1e-12)
    assert depth_buoy == pytest.approx(10.627048720023646, abs=1e-12)
    with pytest.raises(ValueError, match="No positive finite-depth solution"):
        required_depth_for_period_wavelength(5.0, wavelength)


def test_osw_quasi_linear_directional_phase_sign_and_balance() -> None:
    omega = 0.47
    lag = np.linspace(0.0, 2.0, 9)
    forward = quasi_linear_cross_spectrum(1.0, 0.0, omega, lag)
    reverse = quasi_linear_cross_spectrum(0.0, 1.0, omega, lag)
    balanced = quasi_linear_cross_spectrum(1.0, 1.0, omega, lag)
    assert np.allclose(np.unwrap(np.angle(forward)), -omega * lag)
    assert np.allclose(np.unwrap(np.angle(reverse)), +omega * lag)
    assert np.max(np.abs(balanced.imag)) < 1e-15
    assert quasi_linear_zero_lag_phase_slope(1.0, 0.0, omega) == -omega
    assert quasi_linear_zero_lag_phase_slope(1.0, 1.0, omega) == 0.0
    assert quasi_linear_zero_lag_phase_slope(0.0, 1.0, omega) == omega


def test_osw_analytic_zero_lag_slope_matches_finite_difference() -> None:
    omega = 2.0 * math.pi / 13.33
    forward, reverse = 1.0, 0.1463946183201245
    epsilon = 1e-7
    values = quasi_linear_cross_spectrum(
        forward, reverse, omega, np.array([-epsilon, epsilon])
    )
    finite_difference = np.angle(values[1] / values[0]) / (2.0 * epsilon)
    analytic = quasi_linear_zero_lag_phase_slope(forward, reverse, omega)
    assert finite_difference == pytest.approx(analytic, rel=1e-9)


def test_ndbc_directional_distribution_normalization() -> None:
    azimuth_deg = np.linspace(0.0, 360.0, 36001)
    distribution = ndbc_directional_distribution(
        azimuth_deg, 252.0, 252.0, 0.89, 0.74
    )
    integral = np.trapezoid(distribution, np.deg2rad(azimuth_deg))
    assert integral == pytest.approx(1.0, abs=1e-12)
    # The truncated Fourier representation is allowed to be locally negative.
    assert np.min(distribution) < 0


def test_frequency_bin_edges_and_direction_conventions() -> None:
    frequency = np.array([0.05, 0.055, 0.060, 0.065])
    edges = frequency_bin_edges(frequency)
    assert np.allclose(edges, [0.0475, 0.0525, 0.0575, 0.0625, 0.0675])
    assert propagation_to_deg(260.0) == 80.0
    assert axial_difference_deg(80.0, 79.83572372864876) == pytest.approx(
        0.16427627135124112
    )
    assert directional_difference_deg(359.0, 1.0) == 2.0

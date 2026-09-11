"""Physical-identification primitives used by Block 5."""

from __future__ import annotations

import math

import numpy as np


def directional_difference_deg(first: float, second: float) -> float:
    """Return the smallest directed-bearing difference in degrees."""

    return abs(((float(first) - float(second) + 180.0) % 360.0) - 180.0)


def axial_difference_deg(first: float, second: float) -> float:
    """Return the smallest difference after a 180-degree ambiguity."""

    return abs(((float(first) - float(second) + 90.0) % 180.0) - 90.0)


def propagation_to_deg(direction_from_deg: float) -> float:
    """Convert the NDBC direction waves come from to propagation-to bearing."""

    return (float(direction_from_deg) + 180.0) % 360.0


def frequency_bin_edges(frequency_hz: np.ndarray) -> np.ndarray:
    """Construct midpoint bin edges for a strictly increasing frequency grid."""

    frequency = np.asarray(frequency_hz, dtype=np.float64)
    if frequency.ndim != 1 or frequency.size < 2:
        raise ValueError("frequency_hz must be a one-dimensional array with >=2 bins")
    if not np.all(np.isfinite(frequency)) or not np.all(np.diff(frequency) > 0):
        raise ValueError("frequency_hz must be finite and strictly increasing")
    return np.concatenate(
        (
            [frequency[0] - 0.5 * (frequency[1] - frequency[0])],
            0.5 * (frequency[:-1] + frequency[1:]),
            [frequency[-1] + 0.5 * (frequency[-1] - frequency[-2])],
        )
    )


def required_depth_for_period_wavelength(
    period_s: float, wavelength_m: float, *, gravity_m_per_s2: float = 9.80665
) -> float:
    """Solve omega^2=g*k*tanh(k*h) for h at fixed period and wavelength.

    This is a forward compatibility diagnostic, not a bathymetric inversion.
    """

    period = float(period_s)
    wavelength = float(wavelength_m)
    gravity = float(gravity_m_per_s2)
    if period <= 0 or wavelength <= 0 or gravity <= 0:
        raise ValueError("period, wavelength, and gravity must be positive")
    wavenumber = 2.0 * math.pi / wavelength
    ratio = (2.0 * math.pi / period) ** 2 / (gravity * wavenumber)
    if not 0.0 < ratio < 1.0:
        raise ValueError(
            "No positive finite-depth solution: requested frequency exceeds "
            "the deep-water frequency for this wavelength"
        )
    return math.atanh(ratio) / wavenumber


def quasi_linear_cross_spectrum(
    forward_weight: float,
    reverse_weight: float,
    omega_rad_per_s: float,
    lag_s: np.ndarray | float,
    *,
    stationary_transfer: complex = 1.0 + 0.0j,
) -> np.ndarray:
    """Evaluate the two-direction temporal factor in OSW ATBD Eq. (34).

    ``forward_weight`` represents ``|T(k)|^2 S(k)`` and multiplies
    ``exp(-i*omega*t)``. ``reverse_weight`` represents
    ``|T(-k)|^2 S(-k)`` and multiplies ``exp(+i*omega*t)``.
    """

    forward = float(forward_weight)
    reverse = float(reverse_weight)
    omega = float(omega_rad_per_s)
    lag = np.asarray(lag_s, dtype=np.float64)
    if forward < 0 or reverse < 0 or forward + reverse <= 0:
        raise ValueError("directional weights must be nonnegative with positive sum")
    return complex(stationary_transfer) * (
        forward * np.exp(-1j * omega * lag)
        + reverse * np.exp(+1j * omega * lag)
    )


def quasi_linear_zero_lag_phase_slope(
    forward_weight: float, reverse_weight: float, omega_rad_per_s: float
) -> float:
    """Analytic d(arg(P))/dt at zero lag for the Eq. (34) directional pair."""

    forward = float(forward_weight)
    reverse = float(reverse_weight)
    if forward < 0 or reverse < 0 or forward + reverse <= 0:
        raise ValueError("directional weights must be nonnegative with positive sum")
    return (reverse - forward) / (forward + reverse) * float(omega_rad_per_s)


def ndbc_directional_distribution(
    azimuth_from_deg: np.ndarray,
    alpha1_from_deg: float,
    alpha2_from_deg: float,
    r1: float,
    r2: float,
) -> np.ndarray:
    """NDBC truncated directional distribution D(f,A), per radian."""

    azimuth = np.deg2rad(np.asarray(azimuth_from_deg, dtype=np.float64))
    alpha1 = math.radians(float(alpha1_from_deg))
    alpha2 = math.radians(float(alpha2_from_deg))
    return (
        0.5
        + float(r1) * np.cos(azimuth - alpha1)
        + float(r2) * np.cos(2.0 * (azimuth - alpha2))
    ) / math.pi

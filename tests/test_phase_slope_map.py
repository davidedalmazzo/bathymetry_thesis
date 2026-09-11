from __future__ import annotations

import numpy as np

from umbra_sar.wave_analysis import local_coherent_phase_slope_map


def test_local_map_recovers_cross_spectrum_sign_and_rate() -> None:
    time = np.linspace(0.0, 10.0, 11)
    slope = -0.37
    row, col = np.mgrid[:17, :17]
    amplitude = 1.0 + 0.02 * row + 0.01 * col
    spectra = np.asarray(
        [amplitude * np.exp(1j * slope * current) for current in time]
    )
    weights = np.array(
        [[1.0, 2.0, 1.0], [2.0, 4.0, 2.0], [1.0, 2.0, 1.0]]
    )
    result = local_coherent_phase_slope_map(
        spectra,
        time,
        weights,
        hac_lag=2,
        adjacent_coherence_threshold=0.9,
        independent_indices=(0, 5, 10),
        independent_coherence_threshold=0.9,
    )
    center = (8, 8)
    assert result["coherence_and_unwrap_valid"][center]
    assert np.isclose(result["slope_rad_per_s"][center], slope, atol=1e-13)
    # F_secondary * conj(F_reference) preserves the imposed chronological sign.
    assert np.isclose(
        result["wrapped_phase_relative_reference_rad"][1][center], slope, atol=1e-13
    )
    assert result["r_squared"][center] > 1.0 - 1e-13


def test_hermitian_pair_has_opposite_phase_slope() -> None:
    time = np.linspace(0.0, 10.0, 11)
    omega = 0.41
    spectra = np.zeros((11, 17, 17), dtype=np.complex128)
    positive = (6, 7)
    negative = (10, 9)
    for index, current in enumerate(time):
        spectra[index, positive[0] - 1 : positive[0] + 2, positive[1] - 1 : positive[1] + 2] = np.exp(
            -1j * omega * current
        )
        spectra[index, negative[0] - 1 : negative[0] + 2, negative[1] - 1 : negative[1] + 2] = np.exp(
            +1j * omega * current
        )
    result = local_coherent_phase_slope_map(
        spectra,
        time,
        np.ones((3, 3)),
        independent_indices=(0, 5, 10),
    )
    assert np.isclose(result["slope_rad_per_s"][positive], -omega, atol=1e-13)
    assert np.isclose(result["slope_rad_per_s"][negative], +omega, atol=1e-13)
    assert np.isclose(
        result["slope_rad_per_s"][positive]
        + result["slope_rad_per_s"][negative],
        0.0,
        atol=1e-13,
    )


def test_independent_anchor_coherence_rejects_patch_decorrelation() -> None:
    rng = np.random.default_rng(91023)
    time = np.arange(11, dtype=np.float64)
    spectra = np.ones((11, 15, 15), dtype=np.complex128)
    patch = (slice(5, 10), slice(5, 10))
    spectra[5][patch] = np.exp(1j * rng.uniform(-np.pi, np.pi, (5, 5)))
    spectra[10][patch] = np.exp(1j * rng.uniform(-np.pi, np.pi, (5, 5)))
    result = local_coherent_phase_slope_map(
        spectra,
        time,
        np.ones((5, 5)),
        independent_indices=(0, 5, 10),
        independent_coherence_threshold=0.25,
    )
    assert result["minimum_independent_magnitude_squared_coherence"][7, 7] < 0.25
    assert not result["coherence_and_unwrap_valid"][7, 7]


def test_quasi_linear_two_direction_phase_derivative_formula() -> None:
    omega = 0.47
    amplitude_forward = 1.0
    amplitude_reverse = 0.31
    time = 1.7
    step = 1e-6

    def coefficient(current: float) -> complex:
        return amplitude_forward * np.exp(-1j * omega * current) + amplitude_reverse * np.exp(
            1j * omega * current
        )

    numerical = np.angle(coefficient(time + step) / coefficient(time - step)) / (2.0 * step)
    analytic = omega * (amplitude_reverse**2 - amplitude_forward**2) / (
        amplitude_forward**2
        + amplitude_reverse**2
        + 2.0
        * amplitude_forward
        * amplitude_reverse
        * np.cos(2.0 * omega * time)
    )
    assert np.isclose(numerical, analytic, rtol=1e-8, atol=1e-9)
    assert not np.isclose(analytic, -omega)


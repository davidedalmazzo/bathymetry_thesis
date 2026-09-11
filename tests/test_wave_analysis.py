from __future__ import annotations

import numpy as np

from umbra_sar.wave_analysis import (
    coherent_patch_cross,
    find_peak_candidates,
    intensity_spectrum_crop,
    linear_phase_fit,
    match_stable_peak,
    phase_correlation_shift,
    physical_frequency_grid,
    wrap_phase,
)


def test_wavevector_wavelength_and_three_look_stability() -> None:
    shape = (256, 2048)
    jacobian = np.array([[0.44, 0.0], [0.0, 0.055]])
    row = np.arange(shape[0])[:, None]
    col = np.arange(shape[1])[None, :]
    intensity = (2.0 + np.cos(2 * np.pi * (7 * row / shape[0] + 7 * col / shape[1]))).astype(
        np.float32
    )
    spectrum, indices = intensity_spectrum_crop(intensity, half_width=32)
    k_east, k_north, _, _ = physical_frequency_grid(shape, indices, jacobian)
    candidates = find_peak_candidates(
        np.abs(spectrum) ** 2,
        k_east,
        k_north,
        minimum_wavelength_m=5,
        maximum_wavelength_m=100,
    )
    expected_k = 7 / (shape[0] * 0.44)
    expected_wavelength = 1 / np.hypot(expected_k, expected_k)
    assert abs(candidates[0]["wavelength_m"] - expected_wavelength) < 1e-3
    stability = match_stable_peak([candidates, candidates, candidates])
    assert stability["robust"]
    assert stability["orientation_span_deg"] == 0


def test_phase_correlation_sign_ramp_and_shift_closure() -> None:
    rng = np.random.default_rng(17)
    reference = rng.normal(size=(128, 128)).astype(np.float32)
    secondary = np.roll(np.roll(reference, 3, axis=0), -4, axis=1)
    result = phase_correlation_shift(reference, secondary)
    measured = np.asarray(
        result["subpixel_displacement_secondary_relative_to_reference_row_col"]
    )
    assert np.max(np.abs(measured - [3, -4])) < 0.01
    assert result["phase_ramp_removed_residual_resultant"] > 0.99
    assert abs(wrap_phase(np.pi + np.pi)) < 1e-12


def test_fixed_patch_temporal_phase_sign_unwrap_and_rate() -> None:
    time = np.linspace(2.0, 14.0, 11)
    omega = -0.71
    row, col = np.mgrid[-2:3, -2:3]
    base = (2.0 + 0.1 * row + 0.2j * col) * np.exp(0.3j * row - 0.2j * col)
    spectra = [base * np.exp(1j * omega * value) for value in time]
    weights = np.exp(-(row**2 + col**2) / 2.0)
    reference = spectra[0]
    wrapped = np.array(
        [coherent_patch_cross(reference, item, weights)["phase_rad"] for item in spectra]
    )
    unwrapped = np.unwrap(wrapped)
    fit = linear_phase_fit(time, unwrapped, hac_lag=3)
    assert abs(fit["slope_rad_per_s"] - omega) < 1e-12
    assert fit["residual_rmse_rad"] < 1e-12
    adjacent = [
        coherent_patch_cross(first, second, weights)
        for first, second in zip(spectra[:-1], spectra[1:])
    ]
    assert max(abs(item["phase_rad"] - omega * (time[1] - time[0])) for item in adjacent) < 1e-12
    assert min(item["magnitude_squared_coherence"] for item in adjacent) > 1 - 1e-12

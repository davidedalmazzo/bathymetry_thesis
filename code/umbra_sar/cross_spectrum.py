"""Cross-spectrum primitives with an explicit, tested phase convention."""

from __future__ import annotations

from typing import Iterable

import numpy as np
from scipy import fft as scipy_fft


CROSS_SPECTRUM_CONVENTION = (
    "C_secondary,reference(k) = F_secondary(k) * conj(F_reference(k)); "
    "a +phi Fourier phase advance in secondary is recovered as +phi at the "
    "positive-frequency peak"
)


def intensity(complex_image: np.ndarray) -> np.ndarray:
    """Return floating-point intensity while preserving input precision."""

    data = np.asarray(complex_image)
    return np.real(data * np.conjugate(data))


def spatial_cross_spectrum(
    reference: np.ndarray,
    secondary: np.ndarray,
    *,
    axes: Iterable[int] = (-2, -1),
    remove_mean: bool = True,
    spatial_window: np.ndarray | None = None,
    workers: int | None = None,
) -> np.ndarray:
    """Return shifted ``F_secondary * conj(F_reference)``.

    The function is appropriate for synthetic validation with real intensity
    images and is also defined for complex inputs.  It does not decide whether a
    scientific retrieval should use complex or intensity cross-spectra.
    """

    first = np.asarray(reference)
    second = np.asarray(secondary)
    if first.shape != second.shape:
        raise ValueError("reference and secondary must have identical shapes")
    resolved_axes = tuple(int(axis) for axis in axes)
    if remove_mean:
        first = first - np.mean(first, axis=resolved_axes, keepdims=True)
        second = second - np.mean(second, axis=resolved_axes, keepdims=True)
    if spatial_window is not None:
        window = np.asarray(spatial_window)
        if window.shape != first.shape:
            raise ValueError("spatial_window must have the same shape as the images")
        first = first * window
        second = second * window
    first_spectrum = scipy_fft.fftn(first, axes=resolved_axes, workers=workers)
    second_spectrum = scipy_fft.fftn(second, axes=resolved_axes, workers=workers)
    cross = second_spectrum * np.conjugate(first_spectrum)
    return scipy_fft.fftshift(cross, axes=resolved_axes)


def wrapped_phase_error(measured_rad: float, expected_rad: float) -> float:
    """Return measured-minus-expected wrapped to [-pi, pi)."""

    return float(np.angle(np.exp(1j * (measured_rad - expected_rad))))


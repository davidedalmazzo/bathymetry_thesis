"""Small, explicit primitives for Block-3 intensity-spectrum diagnostics."""

from __future__ import annotations

import itertools
import math
from typing import Any

import numpy as np
from scipy import fft as scipy_fft
from scipy.ndimage import convolve, gaussian_filter, maximum_filter
from scipy.signal.windows import tukey


def wrap_phase(value: float) -> float:
    return float(np.angle(np.exp(1j * value)))


def coherent_patch_cross(
    reference: np.ndarray,
    secondary: np.ndarray,
    weights: np.ndarray | None = None,
) -> dict[str, Any]:
    """Locally smooth ``F_secondary * conj(F_reference)`` over one fixed patch."""

    first = np.asarray(reference, dtype=np.complex128)
    second = np.asarray(secondary, dtype=np.complex128)
    if first.shape != second.shape:
        raise ValueError("reference and secondary patches must have the same shape")
    if weights is None:
        weight = np.ones(first.shape, dtype=np.float64)
    else:
        weight = np.asarray(weights, dtype=np.float64)
        if weight.shape != first.shape:
            raise ValueError("weights must have the patch shape")
    if np.any(weight < 0) or not np.any(weight > 0):
        raise ValueError("weights must be nonnegative with positive sum")
    weight = weight / np.sum(weight)
    coefficient = np.sum(weight * second * np.conjugate(first))
    denominator = float(
        np.sum(weight * np.abs(first) ** 2)
        * np.sum(weight * np.abs(second) ** 2)
    )
    coherence = float(abs(coefficient) ** 2 / denominator) if denominator > 0 else 0.0
    return {
        "coefficient": complex(coefficient),
        "phase_rad": float(np.angle(coefficient)),
        "magnitude_squared_coherence": coherence,
    }


def local_coherent_phase_slope_map(
    spectra: np.ndarray,
    time_s: np.ndarray,
    weights: np.ndarray,
    *,
    hac_lag: int = 0,
    adjacent_coherence_threshold: float = 0.7,
    independent_indices: tuple[int, int, int] = (0, 5, 10),
    independent_coherence_threshold: float = 0.25,
    maximum_phase_step_rad: float = np.pi / 2.0,
    maximum_step_consistency_error_rad: float = 0.25,
) -> dict[str, np.ndarray]:
    """Fit local cross-spectral phase rate at every 2-D spectral bin.

    The local complex coefficient always follows the chronological convention
    ``F_secondary * conj(F_reference)``.  A weighted patch is evaluated around
    every output bin.  The returned validity mask requires both adjacent-look
    coherence and coherence among the three independent look anchors, so
    overlap alone cannot make a bin valid.
    """

    values = np.asarray(spectra, dtype=np.complex128)
    time = np.asarray(time_s, dtype=np.float64)
    weight = np.asarray(weights, dtype=np.float64)
    if values.ndim != 3 or values.shape[0] < 3:
        raise ValueError("spectra must have shape (time, row, col) with >=3 looks")
    if time.ndim != 1 or time.size != values.shape[0]:
        raise ValueError("time_s must match the leading spectra dimension")
    if not np.all(np.diff(time) > 0) or not np.all(np.isfinite(time)):
        raise ValueError("time_s must be finite and strictly increasing")
    if weight.ndim != 2 or any(size % 2 != 1 for size in weight.shape):
        raise ValueError("weights must be a 2-D odd-sized patch")
    if np.any(weight < 0) or not np.any(weight > 0):
        raise ValueError("weights must be nonnegative with positive sum")
    if not 0 <= hac_lag < time.size:
        raise ValueError("hac_lag must lie in [0, sample_count)")
    if any(index < 0 or index >= time.size for index in independent_indices):
        raise ValueError("independent_indices must refer to available looks")
    if tuple(sorted(independent_indices)) != independent_indices:
        raise ValueError("independent_indices must be chronological")
    weight = weight / np.sum(weight)

    def smooth(source: np.ndarray) -> np.ndarray:
        return convolve(source, weight, mode="constant", cval=0.0)

    def local_cross(first: np.ndarray, second: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        coefficient = smooth(second * np.conjugate(first))
        denominator = smooth(np.abs(first) ** 2) * smooth(np.abs(second) ** 2)
        coherence = np.zeros(denominator.shape, dtype=np.float64)
        positive = denominator > 0
        coherence[positive] = np.abs(coefficient[positive]) ** 2 / denominator[positive]
        return coefficient, np.clip(coherence, 0.0, 1.0)

    reference = values[0]
    direct_coefficients = []
    direct_coherences = []
    for secondary in values:
        coefficient, coherence = local_cross(reference, secondary)
        direct_coefficients.append(coefficient)
        direct_coherences.append(coherence)
    direct_coefficient = np.asarray(direct_coefficients)
    direct_coherence = np.asarray(direct_coherences)

    adjacent_coefficients = []
    adjacent_coherences = []
    for first, second in zip(values[:-1], values[1:]):
        coefficient, coherence = local_cross(first, second)
        adjacent_coefficients.append(coefficient)
        adjacent_coherences.append(coherence)
    adjacent_coefficient = np.asarray(adjacent_coefficients)
    adjacent_coherence = np.asarray(adjacent_coherences)

    independent_coherences = []
    for first_index, second_index in zip(
        independent_indices[:-1], independent_indices[1:]
    ):
        _, coherence = local_cross(values[first_index], values[second_index])
        independent_coherences.append(coherence)
    _, end_to_end_coherence = local_cross(
        values[independent_indices[0]], values[independent_indices[-1]]
    )
    independent_coherences.append(end_to_end_coherence)
    independent_coherence = np.asarray(independent_coherences)

    wrapped_phase = np.angle(direct_coefficient)
    direct_step = np.angle(np.exp(1j * np.diff(wrapped_phase, axis=0)))
    adjacent_phase = np.angle(adjacent_coefficient)
    step_consistency = np.angle(np.exp(1j * (direct_step - adjacent_phase)))
    unwrapped_phase = np.unwrap(wrapped_phase, axis=0)

    design = np.column_stack((np.ones(time.size), time))
    inverse_normal = np.linalg.inv(design.T @ design)
    flat_phase = unwrapped_phase.reshape(time.size, -1)
    beta = inverse_normal @ design.T @ flat_phase
    predicted = design @ beta
    residual = flat_phase - predicted
    degrees_of_freedom = time.size - 2
    residual_sum_squares = np.sum(residual**2, axis=0)
    residual_variance = residual_sum_squares / degrees_of_freedom
    total_sum_squares = np.sum(
        (flat_phase - np.mean(flat_phase, axis=0, keepdims=True)) ** 2,
        axis=0,
    )
    r_squared = np.ones_like(total_sum_squares)
    varying = total_sum_squares > 0
    r_squared[varying] = (
        1.0 - residual_sum_squares[varying] / total_sum_squares[varying]
    )
    ols_slope_error = np.sqrt(
        np.maximum(0.0, residual_variance * inverse_normal[1, 1])
    )

    score = design[:, :, None] * residual[:, None, :]
    meat = np.einsum("tap,tbp->pab", score, score)
    for lag in range(1, int(hac_lag) + 1):
        bartlett = 1.0 - lag / (hac_lag + 1.0)
        cross = np.einsum("tap,tbp->pab", score[lag:], score[:-lag])
        meat += bartlett * (cross + np.swapaxes(cross, 1, 2))
    hac_covariance = (
        time.size
        / degrees_of_freedom
        * np.einsum("ab,pbc,cd->pad", inverse_normal, meat, inverse_normal)
    )
    hac_slope_error = np.sqrt(np.maximum(0.0, hac_covariance[:, 1, 1]))

    shape = values.shape[1:]
    minimum_adjacent_coherence = np.min(adjacent_coherence, axis=0)
    minimum_independent_coherence = np.min(independent_coherence, axis=0)
    maximum_direct_step = np.max(np.abs(direct_step), axis=0)
    maximum_adjacent_step = np.max(np.abs(adjacent_phase), axis=0)
    maximum_consistency_error = np.max(np.abs(step_consistency), axis=0)
    valid = (
        (minimum_adjacent_coherence >= adjacent_coherence_threshold)
        & (minimum_independent_coherence >= independent_coherence_threshold)
        & (maximum_direct_step < maximum_phase_step_rad)
        & (maximum_adjacent_step < maximum_phase_step_rad)
        & (maximum_consistency_error <= maximum_step_consistency_error_rad)
    )
    row_margin = weight.shape[0] // 2
    col_margin = weight.shape[1] // 2
    if row_margin:
        valid[:row_margin, :] = False
        valid[-row_margin:, :] = False
    if col_margin:
        valid[:, :col_margin] = False
        valid[:, -col_margin:] = False

    mean_local_power = np.mean(
        np.asarray([smooth(np.abs(item) ** 2) for item in values]), axis=0
    )
    return {
        "slope_rad_per_s": beta[1].reshape(shape),
        "intercept_rad": beta[0].reshape(shape),
        "residual_rmse_rad": np.sqrt(
            residual_sum_squares / time.size
        ).reshape(shape),
        "r_squared": r_squared.reshape(shape),
        "ols_slope_standard_error_rad_per_s": ols_slope_error.reshape(shape),
        "hac_slope_standard_error_rad_per_s": hac_slope_error.reshape(shape),
        "selected_slope_standard_error_rad_per_s": np.maximum(
            ols_slope_error, hac_slope_error
        ).reshape(shape),
        "wrapped_phase_relative_reference_rad": wrapped_phase,
        "unwrapped_phase_relative_reference_rad": unwrapped_phase,
        "direct_magnitude_squared_coherence": direct_coherence,
        "adjacent_magnitude_squared_coherence": adjacent_coherence,
        "independent_magnitude_squared_coherence": independent_coherence,
        "minimum_adjacent_magnitude_squared_coherence": minimum_adjacent_coherence,
        "minimum_independent_magnitude_squared_coherence": minimum_independent_coherence,
        "maximum_abs_direct_step_rad": maximum_direct_step,
        "maximum_abs_adjacent_phase_rad": maximum_adjacent_step,
        "maximum_abs_step_consistency_error_rad": maximum_consistency_error,
        "mean_local_power": mean_local_power,
        "coherence_and_unwrap_valid": valid,
    }


def linear_phase_fit(
    time_s: np.ndarray, phase_unwrapped_rad: np.ndarray, *, hac_lag: int = 0
) -> dict[str, Any]:
    """Fit phase = intercept + slope*time with OLS and Newey-West uncertainty."""

    time = np.asarray(time_s, dtype=np.float64)
    phase = np.asarray(phase_unwrapped_rad, dtype=np.float64)
    if time.ndim != 1 or phase.shape != time.shape or time.size < 3:
        raise ValueError("time and phase must be equal 1-D arrays with >=3 samples")
    if not np.all(np.diff(time) > 0):
        raise ValueError("time must be strictly increasing")
    if not np.all(np.isfinite(time)) or not np.all(np.isfinite(phase)):
        raise ValueError("time and phase must be finite")
    lag = int(hac_lag)
    if lag < 0 or lag >= time.size:
        raise ValueError("hac_lag must lie in [0, sample_count)")

    design = np.column_stack((np.ones(time.size), time))
    inverse_normal = np.linalg.inv(design.T @ design)
    beta = inverse_normal @ design.T @ phase
    predicted = design @ beta
    residual = phase - predicted
    degrees_of_freedom = time.size - 2
    residual_variance = float(np.sum(residual**2) / degrees_of_freedom)
    ols_covariance = residual_variance * inverse_normal

    score = design * residual[:, None]
    meat = score.T @ score
    for current_lag in range(1, lag + 1):
        bartlett = 1.0 - current_lag / (lag + 1.0)
        cross = score[current_lag:].T @ score[:-current_lag]
        meat += bartlett * (cross + cross.T)
    hac_covariance = (
        time.size / degrees_of_freedom * inverse_normal @ meat @ inverse_normal
    )
    total = float(np.sum((phase - np.mean(phase)) ** 2))
    r_squared = 1.0 - float(np.sum(residual**2)) / total if total > 0 else 1.0
    return {
        "intercept_rad": float(beta[0]),
        "slope_rad_per_s": float(beta[1]),
        "predicted_phase_rad": predicted.tolist(),
        "residual_phase_rad": residual.tolist(),
        "residual_rmse_rad": float(np.sqrt(np.mean(residual**2))),
        "residual_max_abs_rad": float(np.max(np.abs(residual))),
        "r_squared": r_squared,
        "degrees_of_freedom": degrees_of_freedom,
        "ols_intercept_standard_error_rad": float(np.sqrt(max(0.0, ols_covariance[0, 0]))),
        "ols_slope_standard_error_rad_per_s": float(
            np.sqrt(max(0.0, ols_covariance[1, 1]))
        ),
        "newey_west_hac_lag": lag,
        "hac_intercept_standard_error_rad": float(
            np.sqrt(max(0.0, hac_covariance[0, 0]))
        ),
        "hac_slope_standard_error_rad_per_s": float(
            np.sqrt(max(0.0, hac_covariance[1, 1]))
        ),
    }


def axial_difference_deg(first: float, second: float) -> float:
    """Smallest difference between undirected orientations in degrees."""

    return abs(((float(first) - float(second) + 90.0) % 180.0) - 90.0)


def detrend_and_window_intensity(intensity: np.ndarray) -> np.ndarray:
    """Remove one global plane and apply an energy-normalized 2-D Tukey window."""

    work = np.asarray(intensity, dtype=np.float32).copy()
    rows, cols = work.shape
    row_coordinate = np.linspace(-1.0, 1.0, rows, dtype=np.float64)
    col_coordinate = np.linspace(-1.0, 1.0, cols, dtype=np.float64)
    mean = float(np.mean(work, dtype=np.float64))
    row_sums = np.sum(work, axis=1, dtype=np.float64)
    col_sums = np.sum(work, axis=0, dtype=np.float64)
    row_slope = float(
        np.dot(row_coordinate, row_sums) / (cols * np.dot(row_coordinate, row_coordinate))
    )
    col_slope = float(
        np.dot(col_coordinate, col_sums) / (rows * np.dot(col_coordinate, col_coordinate))
    )
    work -= np.float32(mean)
    work -= (row_slope * row_coordinate).astype(np.float32)[:, None]
    work -= (col_slope * col_coordinate).astype(np.float32)[None, :]
    row_window = tukey(rows, alpha=0.1, sym=True).astype(np.float32)
    col_window = tukey(cols, alpha=0.1, sym=True).astype(np.float32)
    raw_energy = float(np.sum(row_window**2) * np.sum(col_window**2))
    energy_scale = math.sqrt((rows * cols) / raw_energy)
    work *= row_window[:, None]
    work *= col_window[None, :]
    work *= np.float32(energy_scale)
    return work


def intensity_spectrum_crop(
    intensity: np.ndarray,
    *,
    half_width: int = 64,
    workers: int | None = None,
) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray]]:
    """Return a complex, fftshifted central crop and its global FFT indices."""

    work = detrend_and_window_intensity(intensity)
    spectrum = scipy_fft.fftshift(
        scipy_fft.fft2(work, workers=workers), axes=(0, 1)
    )
    center_row = spectrum.shape[0] // 2
    center_col = spectrum.shape[1] // 2
    row_indices = np.arange(
        center_row - half_width, center_row + half_width + 1, dtype=np.int64
    )
    col_indices = np.arange(
        center_col - half_width, center_col + half_width + 1, dtype=np.int64
    )
    crop = np.asarray(spectrum[np.ix_(row_indices, col_indices)], dtype=np.complex64)
    return crop, (row_indices, col_indices)


def physical_frequency_grid(
    shape: tuple[int, int],
    indices: tuple[np.ndarray, np.ndarray],
    ground_jacobian_en_m_per_pixel: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Convert shifted FFT-bin frequencies to local east/north cycles per metre."""

    row_all = np.fft.fftshift(np.fft.fftfreq(shape[0], d=1.0))
    col_all = np.fft.fftshift(np.fft.fftfreq(shape[1], d=1.0))
    row_frequency = row_all[indices[0]][:, None]
    col_frequency = col_all[indices[1]][None, :]
    inverse_transpose = np.linalg.inv(
        np.asarray(ground_jacobian_en_m_per_pixel, dtype=np.float64).T
    )
    k_east = (
        inverse_transpose[0, 0] * row_frequency
        + inverse_transpose[0, 1] * col_frequency
    )
    k_north = (
        inverse_transpose[1, 0] * row_frequency
        + inverse_transpose[1, 1] * col_frequency
    )
    return k_east, k_north, row_frequency, col_frequency


def _candidate_from_index(
    index: tuple[int, int],
    power: np.ndarray,
    smoothed: np.ndarray,
    k_east: np.ndarray,
    k_north: np.ndarray,
    center: tuple[int, int],
) -> dict[str, Any]:
    row, col = index
    log_power = np.log(np.maximum(smoothed, np.finfo(float).tiny))

    def parabolic_offset(axis: int) -> float:
        if axis == 0:
            before, center_value, after = (
                log_power[row - 1, col],
                log_power[row, col],
                log_power[row + 1, col],
            )
        else:
            before, center_value, after = (
                log_power[row, col - 1],
                log_power[row, col],
                log_power[row, col + 1],
            )
        denominator = before - 2.0 * center_value + after
        if denominator == 0:
            return 0.0
        return float(np.clip(0.5 * (before - after) / denominator, -0.5, 0.5))

    delta_row = parabolic_offset(0)
    delta_col = parabolic_offset(1)
    east = float(
        k_east[row, col]
        + delta_row * (k_east[row + 1, col] - k_east[row, col])
        + delta_col * (k_east[row, col + 1] - k_east[row, col])
    )
    north = float(
        k_north[row, col]
        + delta_row * (k_north[row + 1, col] - k_north[row, col])
        + delta_col * (k_north[row, col + 1] - k_north[row, col])
    )
    magnitude = math.hypot(east, north)
    wavelength = 1.0 / magnitude
    wavevector_bearing = math.degrees(math.atan2(east, north)) % 180.0
    radial = np.hypot(k_east, k_north)
    annulus = (radial >= 0.82 * magnitude) & (radial <= 1.18 * magnitude)
    annulus[row, col] = False
    background = (
        max(float(np.median(smoothed[annulus])), np.finfo(float).tiny)
        if np.any(annulus)
        else np.nan
    )
    prominence_db = float(
        10.0 * np.log10(max(float(smoothed[row, col]), np.finfo(float).tiny) / background)
    )
    return {
        "crop_index_row_col": [int(row), int(col)],
        "fft_bin_offset_row_col": [int(row - center[0]), int(col - center[1])],
        "subbin_parabolic_offset_row_col": [delta_row, delta_col],
        "fft_bin_offset_subpixel_row_col": [
            float(row - center[0] + delta_row),
            float(col - center[1] + delta_col),
        ],
        "k_east_cycles_per_m": east,
        "k_north_cycles_per_m": north,
        "wavenumber_magnitude_cycles_per_m": magnitude,
        "wavelength_m": wavelength,
        "wavevector_bearing_deg_mod_180": wavevector_bearing,
        "crest_orientation_deg_mod_180": (wavevector_bearing + 90.0) % 180.0,
        "power": float(power[row, col]),
        "smoothed_power": float(smoothed[row, col]),
        "annular_prominence_db": prominence_db,
    }


def find_peak_candidates(
    power: np.ndarray,
    k_east: np.ndarray,
    k_north: np.ndarray,
    *,
    minimum_wavelength_m: float = 40.0,
    maximum_wavelength_m: float = 500.0,
    count: int = 8,
) -> list[dict[str, Any]]:
    """Find unique undirected local maxima in a physical wavelength band."""

    source = np.asarray(power, dtype=np.float64)
    symmetric = 0.5 * (source + source[::-1, ::-1])
    smoothed = gaussian_filter(symmetric, sigma=0.8, mode="nearest")
    radial = np.hypot(k_east, k_north)
    mask = (radial >= 1.0 / maximum_wavelength_m) & (
        radial <= 1.0 / minimum_wavelength_m
    )
    # Keep one representative of each conjugate +/-k pair.
    tolerance = 10 * np.finfo(float).eps
    half_plane = (k_north > tolerance) | (
        (np.abs(k_north) <= tolerance) & (k_east >= 0)
    )
    local_maximum = smoothed == maximum_filter(smoothed, size=3, mode="nearest")
    candidate_indices = np.argwhere(mask & half_plane & local_maximum)
    if candidate_indices.size == 0:
        return []
    values = smoothed[candidate_indices[:, 0], candidate_indices[:, 1]]
    order = np.argsort(values)[::-1]
    center = (source.shape[0] // 2, source.shape[1] // 2)
    output: list[dict[str, Any]] = []
    for candidate_index in candidate_indices[order]:
        index = (int(candidate_index[0]), int(candidate_index[1]))
        candidate = _candidate_from_index(
            index, source, smoothed, k_east, k_north, center
        )
        # Suppress maxima within two FFT bins of an already retained peak.
        offset = np.asarray(candidate["fft_bin_offset_row_col"], dtype=float)
        if any(
            np.linalg.norm(
                offset - np.asarray(existing["fft_bin_offset_row_col"], dtype=float)
            )
            < 2.5
            for existing in output
        ):
            continue
        output.append(candidate)
        if len(output) >= count:
            break
    return output


def match_stable_peak(
    candidates_by_look: list[list[dict[str, Any]]],
    *,
    maximum_relative_wavelength_span: float = 0.20,
    maximum_orientation_span_deg: float = 12.0,
    minimum_prominence_db: float = 3.0,
) -> dict[str, Any]:
    """Select the strongest three-look-consistent undirected spectral peak."""

    if len(candidates_by_look) != 3 or any(not values for values in candidates_by_look):
        return {
            "robust": False,
            "reason": "At least one look has no peak candidate in the configured wavelength band.",
            "matched_candidates": [],
        }
    possibilities = []
    for triplet in itertools.product(*candidates_by_look):
        wavelengths = np.array([item["wavelength_m"] for item in triplet])
        orientations = np.array(
            [item["wavevector_bearing_deg_mod_180"] for item in triplet]
        )
        relative_span = float((wavelengths.max() - wavelengths.min()) / np.median(wavelengths))
        orientation_span = float(
            max(
                axial_difference_deg(a, b)
                for a, b in itertools.combinations(orientations, 2)
            )
        )
        prominence = np.array([item["annular_prominence_db"] for item in triplet])
        consistency_penalty = 15.0 * relative_span + 0.15 * orientation_span
        score = float(prominence.mean() - consistency_penalty)
        possibilities.append(
            (score, relative_span, orientation_span, float(prominence.min()), triplet)
        )
    passing = [
        item
        for item in possibilities
        if item[1] <= maximum_relative_wavelength_span
        and item[2] <= maximum_orientation_span_deg
        and item[3] >= minimum_prominence_db
    ]
    score, relative_span, orientation_span, minimum_prominence, triplet = max(
        passing if passing else possibilities, key=lambda item: item[0]
    )
    robust = bool(passing)
    wavelengths = np.array([item["wavelength_m"] for item in triplet])
    orientations = np.deg2rad(
        2.0 * np.array([item["wavevector_bearing_deg_mod_180"] for item in triplet])
    )
    mean_orientation = (
        0.5 * math.degrees(
            math.atan2(np.mean(np.sin(orientations)), np.mean(np.cos(orientations)))
        )
    ) % 180.0
    return {
        "robust": robust,
        "reason": (
            "All three thresholds passed."
            if robust
            else "Best triplet did not pass all wavelength/orientation/prominence thresholds."
        ),
        "thresholds": {
            "maximum_relative_wavelength_span": maximum_relative_wavelength_span,
            "maximum_orientation_span_deg": maximum_orientation_span_deg,
            "minimum_annular_prominence_db_each_look": minimum_prominence_db,
        },
        "score": score,
        "relative_wavelength_span": relative_span,
        "orientation_span_deg": orientation_span,
        "minimum_prominence_db": minimum_prominence,
        "mean_wavelength_m": float(wavelengths.mean()),
        "wavelength_standard_deviation_m": float(wavelengths.std()),
        "mean_wavevector_bearing_deg_mod_180": mean_orientation,
        "mean_crest_orientation_deg_mod_180": (mean_orientation + 90.0) % 180.0,
        "matched_candidates": list(triplet),
    }


def phase_correlation_shift(
    reference: np.ndarray, secondary: np.ndarray
) -> dict[str, Any]:
    """Estimate the feature displacement in secondary relative to reference."""

    first = detrend_and_window_intensity(reference)
    second = detrend_and_window_intensity(secondary)
    first_spectrum = scipy_fft.fft2(first)
    second_spectrum = scipy_fft.fft2(second)
    cross = second_spectrum * np.conjugate(first_spectrum)
    magnitude = np.abs(cross)
    normalized = cross / np.maximum(magnitude, np.finfo(np.float32).tiny)
    correlation = np.abs(scipy_fft.ifft2(normalized))
    peak = np.unravel_index(int(np.argmax(correlation)), correlation.shape)
    integer_shift = np.array(peak, dtype=np.float64)
    for axis, size in enumerate(correlation.shape):
        if integer_shift[axis] > size // 2:
            integer_shift[axis] -= size

    subpixel = integer_shift.copy()
    for axis in (0, 1):
        before_index = list(peak)
        after_index = list(peak)
        before_index[axis] = (before_index[axis] - 1) % correlation.shape[axis]
        after_index[axis] = (after_index[axis] + 1) % correlation.shape[axis]
        before = float(correlation[tuple(before_index)])
        center = float(correlation[peak])
        after = float(correlation[tuple(after_index)])
        denominator = before - 2.0 * center + after
        if denominator != 0:
            subpixel[axis] += 0.5 * (before - after) / denominator

    row_frequency = np.fft.fftfreq(correlation.shape[0])[:, None]
    col_frequency = np.fft.fftfreq(correlation.shape[1])[None, :]
    predicted_ramp = np.exp(
        -2j
        * np.pi
        * (row_frequency * subpixel[0] + col_frequency * subpixel[1])
    )
    residual_unit = normalized * np.conjugate(predicted_ramp)
    signal_mask = magnitude >= np.percentile(magnitude, 75.0)
    residual_mean = np.mean(residual_unit[signal_mask])
    return {
        "integer_displacement_secondary_relative_to_reference_row_col": integer_shift.tolist(),
        "subpixel_displacement_secondary_relative_to_reference_row_col": subpixel.tolist(),
        "correlation_peak": float(correlation[peak]),
        "correlation_peak_to_median_ratio": float(
            correlation[peak] / np.median(correlation)
        ),
        "phase_ramp_model": "-2*pi*(f_row*d_row + f_col*d_col) for F_secondary*conj(F_reference)",
        "phase_ramp_removed_residual_resultant": float(abs(residual_mean)),
        "phase_ramp_removed_residual_mean_phase_rad": float(np.angle(residual_mean)),
    }

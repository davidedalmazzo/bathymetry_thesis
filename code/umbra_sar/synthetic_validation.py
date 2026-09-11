"""Deterministic primitives for Block-9 phase-to-frequency validation.

The module deliberately contains no Vandenberg-specific constants.  It builds
synthetic truth first, then exercises the same cross-spectrum convention and
local phase-slope estimator used by the real-data pipeline.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

import numpy as np
from scipy import fft as scipy_fft
from scipy.ndimage import gaussian_filter

from .subaperture import (
    SubapertureBand,
    image_to_shifted_spectrum,
    make_window,
    sublook_from_spectrum,
    shifted_spectrum_to_image,
)
from .wave_analysis import (
    intensity_spectrum_crop,
    linear_phase_fit,
    local_coherent_phase_slope_map,
)


G_M_PER_S2 = 9.80665
SYNTHETIC_DEPTH_M = 10.0
RANGE_SAMPLE_COUNT = 1024
AZIMUTH_SAMPLE_COUNT = 600
RANGE_PIXEL_SPACING_M = 8.0
SPATIAL_HALF_WIDTH = 128
DOPPLER_TIME_STEP_S = 0.03
LOOK_WIDTH_BINS = 200
LOOK_STEP_BINS = 40
LOOK_COUNT = 11


@dataclass(frozen=True)
class SyntheticComponent:
    """One frozen, grid-resolved synthetic wave component."""

    component_id: str
    range_fft_mode: int
    azimuth_fft_mode: int
    wavelength_m: float
    k_rad_per_m: float
    omega_rad_per_s: float
    period_s: float
    propagation_angle_deg_from_positive_range: float
    amplitude: float
    phase_rad: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def finite_depth_omega(k_rad_per_m: np.ndarray | float, depth_m: float) -> np.ndarray:
    """Linear gravity-wave angular frequency at finite depth."""

    k = np.asarray(k_rad_per_m, dtype=np.float64)
    if np.any(k < 0) or depth_m <= 0:
        raise ValueError("wavenumber must be nonnegative and depth positive")
    return np.sqrt(G_M_PER_S2 * k * np.tanh(k * float(depth_m)))


def finite_depth_group_velocity(
    k_rad_per_m: np.ndarray | float, depth_m: float
) -> np.ndarray:
    """Analytic derivative d omega / d k for finite-depth gravity waves."""

    k = np.asarray(k_rad_per_m, dtype=np.float64)
    omega = finite_depth_omega(k, depth_m)
    kh = k * float(depth_m)
    numerator = G_M_PER_S2 * (
        np.tanh(kh) + kh / np.cosh(kh) ** 2
    )
    return numerator / (2.0 * omega)


def frozen_truth_components() -> list[SyntheticComponent]:
    """Return six grid-exact modes spanning roughly 80--190 m at h=10 m.

    The integer modes form a difference-free set for the listed modes.  Thus
    quadratic sideband/sideband intensity products cannot land on another
    injected truth bin in the full complex surrogate.
    """

    modes = (43, 51, 60, 70, 82, 99)
    # The gate case starts with equal amplitudes.  Unequal amplitudes are
    # introduced later as one isolated progressive-realism perturbation.
    amplitudes = (1.00, 1.00, 1.00, 1.00, 1.00, 1.00)
    phases = (0.17, -0.83, 1.21, -1.74, 2.13, -2.51)
    length_m = RANGE_SAMPLE_COUNT * RANGE_PIXEL_SPACING_M
    output: list[SyntheticComponent] = []
    for index, (mode, amplitude, phase) in enumerate(
        zip(modes, amplitudes, phases), start=1
    ):
        wavelength = length_m / mode
        k = 2.0 * np.pi / wavelength
        omega = float(finite_depth_omega(k, SYNTHETIC_DEPTH_M))
        output.append(
            SyntheticComponent(
                component_id=f"K{index}",
                range_fft_mode=mode,
                azimuth_fft_mode=0,
                wavelength_m=wavelength,
                k_rad_per_m=k,
                omega_rad_per_s=omega,
                period_s=2.0 * np.pi / omega,
                propagation_angle_deg_from_positive_range=0.0,
                amplitude=amplitude,
                phase_rad=phase,
            )
        )
    return output


def gaussian_patch_weights(radius: int = 2, sigma: float = 1.0) -> np.ndarray:
    if radius < 0:
        raise ValueError("radius must be nonnegative")
    row, col = np.mgrid[-radius : radius + 1, -radius : radius + 1]
    weights = np.exp(-(row**2 + col**2) / (2.0 * sigma**2))
    return weights / np.sum(weights)


def component_crop_centers(
    components: Sequence[SyntheticComponent], half_width: int = SPATIAL_HALF_WIDTH
) -> list[tuple[int, int]]:
    return [
        (
            half_width + item.range_fft_mode,
            half_width + item.azimuth_fft_mode,
        )
        for item in components
    ]


def phase_slope_from_complex_series(
    coefficients: Sequence[complex], time_s: Sequence[float], *, hac_lag: int = 0
) -> dict[str, Any]:
    """Fit the chronological phase of C(t)=F(t) conj(F(t0))."""

    values = np.asarray(coefficients, dtype=np.complex128)
    time = np.asarray(time_s, dtype=np.float64)
    if values.ndim != 1 or values.shape != time.shape:
        raise ValueError("coefficients and time must be equal 1-D arrays")
    cross = values * np.conjugate(values[0])
    wrapped = np.angle(cross)
    unwrapped = np.unwrap(wrapped)
    fit = linear_phase_fit(time, unwrapped, hac_lag=hac_lag)
    fit.update(
        {
            "cross_convention": "F_secondary * conj(F_reference)",
            "wrapped_phase_rad": wrapped.tolist(),
            "unwrapped_phase_rad": unwrapped.tolist(),
        }
    )
    return fit


def _raw_centered_spectrum_crop(
    intensity: np.ndarray, half_width: int = SPATIAL_HALF_WIDTH
) -> np.ndarray:
    spectrum = scipy_fft.fftshift(scipy_fft.fft2(intensity), axes=(0, 1))
    center = (spectrum.shape[0] // 2, spectrum.shape[1] // 2)
    rows = slice(center[0] - half_width, center[0] + half_width + 1)
    cols = slice(center[1] - half_width, center[1] + half_width + 1)
    return np.asarray(spectrum[rows, cols], dtype=np.complex128)


def generate_oracle_intensities(
    components: Sequence[SyntheticComponent],
    time_s: Sequence[float],
    omega_rad_per_s: Sequence[float],
    *,
    equal_amplitudes: bool = False,
    white_noise_std: float = 0.0,
    fixed_speckle_std: float = 0.0,
    decorrelating_speckle_std: float = 0.0,
    finite_peak_half_width_bins: int = 0,
    seed: int = 90210,
) -> np.ndarray:
    """Generate real oracle intensity snapshots with optional isolated effects."""

    time = np.asarray(time_s, dtype=np.float64)
    omega = np.asarray(omega_rad_per_s, dtype=np.float64)
    if omega.shape != (len(components),):
        raise ValueError("one omega is required per component")
    if min(white_noise_std, fixed_speckle_std, decorrelating_speckle_std) < 0:
        raise ValueError("noise levels must be nonnegative")
    if finite_peak_half_width_bins < 0:
        raise ValueError("finite peak half-width must be nonnegative")

    rng = np.random.default_rng(seed)
    row = np.arange(RANGE_SAMPLE_COUNT, dtype=np.float64)[:, None]
    fixed = rng.standard_normal((RANGE_SAMPLE_COUNT, AZIMUTH_SAMPLE_COUNT))
    fixed = gaussian_filter(fixed, sigma=(3.0, 3.0), mode="wrap")
    fixed /= max(float(np.std(fixed)), np.finfo(float).tiny)
    output = np.empty(
        (time.size, RANGE_SAMPLE_COUNT, AZIMUTH_SAMPLE_COUNT), dtype=np.float32
    )
    for time_index, current_time in enumerate(time):
        image = np.full(
            (RANGE_SAMPLE_COUNT, AZIMUTH_SAMPLE_COUNT), 10.0, dtype=np.float64
        )
        for component_index, item in enumerate(components):
            amplitude = 1.0 if equal_amplitudes else item.amplitude
            if finite_peak_half_width_bins:
                offsets = np.arange(
                    -finite_peak_half_width_bins,
                    finite_peak_half_width_bins + 1,
                    dtype=int,
                )
                spread = max(1.0, finite_peak_half_width_bins / 1.5)
                weights = np.exp(-0.5 * (offsets / spread) ** 2)
                weights /= np.sum(weights)
            else:
                offsets = np.array([0], dtype=int)
                weights = np.array([1.0])
            temporal_phase = -omega[component_index] * current_time + item.phase_rad
            for offset, weight in zip(offsets, weights):
                spatial_phase = (
                    2.0
                    * np.pi
                    * (item.range_fft_mode + int(offset))
                    * row
                    / RANGE_SAMPLE_COUNT
                )
                image += amplitude * float(weight) * np.cos(spatial_phase + temporal_phase)
        if fixed_speckle_std:
            image += fixed_speckle_std * fixed
        if decorrelating_speckle_std:
            current = rng.standard_normal(image.shape)
            current = gaussian_filter(current, sigma=(3.0, 3.0), mode="wrap")
            current /= max(float(np.std(current)), np.finfo(float).tiny)
            image += decorrelating_speckle_std * current
        if white_noise_std:
            image += white_noise_std * rng.standard_normal(image.shape)
        output[time_index] = image.astype(np.float32)
    return output


def spectra_from_intensities(
    intensities: np.ndarray,
    *,
    standard_window: bool,
    half_width: int = SPATIAL_HALF_WIDTH,
) -> np.ndarray:
    """Convert intensity snapshots to cropped complex spatial spectra."""

    output = []
    for image in np.asarray(intensities):
        if standard_window:
            spectrum, _ = intensity_spectrum_crop(
                image, half_width=half_width, workers=1
            )
        else:
            spectrum = _raw_centered_spectrum_crop(image, half_width=half_width)
        output.append(spectrum)
    return np.asarray(output, dtype=np.complex128)


def estimate_component_slopes(
    spectra: np.ndarray,
    time_s: Sequence[float],
    components: Sequence[SyntheticComponent],
    *,
    patch_radius: int = 2,
    hac_lag: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    """Run the real local cross-spectrum estimator at fixed truth bins."""

    mapped = local_coherent_phase_slope_map(
        spectra,
        np.asarray(time_s, dtype=np.float64),
        gaussian_patch_weights(patch_radius),
        hac_lag=hac_lag,
        adjacent_coherence_threshold=0.50,
        independent_indices=(0, 5, 10),
        independent_coherence_threshold=0.20,
        maximum_phase_step_rad=np.pi / 2.0,
        maximum_step_consistency_error_rad=0.25,
    )
    records = []
    for item, center in zip(components, component_crop_centers(components)):
        slope = float(mapped["slope_rad_per_s"][center])
        records.append(
            {
                "component_id": item.component_id,
                "crop_center_row_col": list(center),
                "signed_slope_rad_per_s": slope,
                "aligned_omega_rad_per_s": -slope,
                "absolute_omega_rad_per_s": abs(slope),
                "fit_standard_error_rad_per_s": float(
                    mapped["selected_slope_standard_error_rad_per_s"][center]
                ),
                "fit_r_squared": float(mapped["r_squared"][center]),
                "minimum_adjacent_coherence": float(
                    mapped["minimum_adjacent_magnitude_squared_coherence"][center]
                ),
                "minimum_independent_coherence": float(
                    mapped["minimum_independent_magnitude_squared_coherence"][center]
                ),
                "valid": bool(mapped["coherence_and_unwrap_valid"][center]),
            }
        )
    return records, mapped


def run_oracle_case(
    components: Sequence[SyntheticComponent],
    time_s: Sequence[float],
    omega_rad_per_s: Sequence[float],
    *,
    case_name: str,
    standard_window: bool = True,
    generator_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the complete downstream intensity-to-phase pipeline."""

    options = {} if generator_options is None else dict(generator_options)
    images = generate_oracle_intensities(
        components, time_s, omega_rad_per_s, **options
    )
    raw_spectra = spectra_from_intensities(images, standard_window=False)
    standard_spectra = spectra_from_intensities(
        images, standard_window=standard_window
    )
    raw_slopes = []
    spatial_fft_slopes = []
    centers = component_crop_centers(components)
    for center in centers:
        raw_slopes.append(
            phase_slope_from_complex_series(
                raw_spectra[:, center[0], center[1]], time_s, hac_lag=4
            )
        )
        spatial_fft_slopes.append(
            phase_slope_from_complex_series(
                standard_spectra[:, center[0], center[1]], time_s, hac_lag=4
            )
        )
    smoothed, mapped = estimate_component_slopes(
        standard_spectra, time_s, components
    )
    truth = np.asarray(omega_rad_per_s, dtype=np.float64)
    recovered = np.asarray(
        [record["aligned_omega_rad_per_s"] for record in smoothed],
        dtype=np.float64,
    )
    stages = []
    for index, item in enumerate(components):
        stages.append(
            {
                "component_id": item.component_id,
                "omega_truth_rad_per_s": float(truth[index]),
                "omega_after_intensity_generation_rad_per_s": float(
                    -raw_slopes[index]["slope_rad_per_s"]
                ),
                "omega_after_sublook_formation_rad_per_s": None,
                "omega_after_spatial_fft_rad_per_s": float(
                    -spatial_fft_slopes[index]["slope_rad_per_s"]
                ),
                "omega_after_smoothing_rad_per_s": float(
                    -smoothed[index]["signed_slope_rad_per_s"]
                ),
                "omega_after_sign_alignment_rad_per_s": float(recovered[index]),
                "omega_final_rad_per_s": float(recovered[index]),
                "final_error_rad_per_s": float(recovered[index] - truth[index]),
            }
        )
    del images, raw_spectra, standard_spectra, mapped
    return {
        "case": case_name,
        "time_s": np.asarray(time_s, dtype=np.float64).tolist(),
        "standard_real_data_window_used": bool(standard_window),
        "generator_options": options,
        "stage_tracking": stages,
        "max_abs_error_rad_per_s": float(np.max(np.abs(recovered - truth))),
        "rmse_rad_per_s": float(np.sqrt(np.mean((recovered - truth) ** 2))),
        "all_bins_valid": bool(all(record["valid"] for record in smoothed)),
        "component_diagnostics": smoothed,
    }


def canonical_half_plane_mask(
    row_offset: np.ndarray, col_offset: np.ndarray
) -> np.ndarray:
    """Canonical half-plane used for independent real-intensity statistics."""

    row = np.asarray(row_offset)
    col = np.asarray(col_offset)
    if row.shape != col.shape:
        raise ValueError("row and column offsets must have equal shape")
    return (row > 0) | ((row == 0) & (col >= 0))


def deduplicate_conjugate_offsets(
    offsets: Iterable[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Return one canonical representative of every +/- FFT-bin pair."""

    result: set[tuple[int, int]] = set()
    for row, col in offsets:
        key = (int(row), int(col))
        opposite = (-key[0], -key[1])
        if canonical_half_plane_mask(np.asarray(key[0]), np.asarray(key[1])):
            result.add(key)
        else:
            result.add(opposite)
    return sorted(result)


def synthetic_look_bands() -> tuple[list[SubapertureBand], np.ndarray, np.ndarray]:
    """Create an exact 6-s/80%-overlap Doppler-to-time mapping."""

    slice_time = (np.arange(AZIMUTH_SAMPLE_COUNT) + 0.5) * DOPPLER_TIME_STEP_S
    window, _ = make_window(
        LOOK_WIDTH_BINS, "tukey", tukey_alpha=0.25, normalization="energy"
    )
    bands = []
    effective_times = []
    for index in range(LOOK_COUNT):
        start = index * LOOK_STEP_BINS
        stop = start + LOOK_WIDTH_BINS
        effective = float(
            np.sum(window**2 * slice_time[start:stop]) / np.sum(window**2)
        )
        effective_times.append(effective)
        bands.append(
            SubapertureBand(
                start=start,
                stop=stop,
                support_start=0,
                support_stop=AZIMUTH_SAMPLE_COUNT,
                requested_nominal_duration_s=6.0,
                requested_bandwidth_fraction=LOOK_WIDTH_BINS
                / AZIMUTH_SAMPLE_COUNT,
                realized_bandwidth_fraction=LOOK_WIDTH_BINS
                / AZIMUTH_SAMPLE_COUNT,
                realized_nominal_duration_s=6.0,
                center_fraction_in_support=(0.5 * (start + stop))
                / AZIMUTH_SAMPLE_COUNT,
                nominal_center_time_from_collect_start_s=effective,
                timing_model="synthetic_exact_linear_Doppler_to_slow_time",
            )
        )
    return bands, slice_time, np.asarray(effective_times)


def run_full_subaperture_surrogate(
    components: Sequence[SyntheticComponent],
    *,
    sideband_scale: float = 0.08,
) -> dict[str, Any]:
    """Run complex-input -> Doppler sublooks -> intensity -> phase slopes.

    Construction
    ------------
    In shifted azimuth-Doppler coordinates ``f`` and range coordinate ``x``:

    ``Z(x,f)=R(f)[1+sum eps*A_j exp(i*k_j*x-i*omega_j*t(f)+i*phi_j)]``.

    For a symmetric Doppler window centered at ``t_i``, the range-frequency
    coefficient of ``|z_i|^2`` is proportional to the weighted average of
    ``exp(-i*omega_j*t(f))``.  Its phase is therefore ``-omega_j*t_i`` while
    the finite window changes only its real amplitude.  This explicitly puts
    physical evolution in Doppler/slow-time rather than inserting a static
    sinusoid into one SLC.
    """

    if sideband_scale <= 0:
        raise ValueError("sideband_scale must be positive")
    bands, slice_time, look_time = synthetic_look_bands()
    row = np.arange(RANGE_SAMPLE_COUNT, dtype=np.float64)[:, None]
    # A deterministic unit-modulus carrier distributes energy across azimuth
    # image samples (a constant Doppler phase would collapse to one azimuth
    # impulse and would make the later spatial taper an artificial dominant
    # effect).  Unit modulus keeps the analytic unwindowed Parseval result
    # exact while resembling a fixed coherent speckle carrier.
    rng = np.random.default_rng(9247001)
    carrier = np.exp(
        1j
        * rng.uniform(
            -np.pi,
            np.pi,
            (RANGE_SAMPLE_COUNT, AZIMUTH_SAMPLE_COUNT),
        )
    )
    modulation = np.ones(
        (RANGE_SAMPLE_COUNT, AZIMUTH_SAMPLE_COUNT), dtype=np.complex128
    )
    for item in components:
        spatial = np.exp(
            2j * np.pi * item.range_fft_mode * row / RANGE_SAMPLE_COUNT
        )
        temporal = np.exp(
            -1j * item.omega_rad_per_s * slice_time + 1j * item.phase_rad
        )[None, :]
        modulation += sideband_scale * item.amplitude * spatial * temporal
    shifted_doppler = carrier * modulation

    complex_input = shifted_spectrum_to_image(
        shifted_doppler, axis=1, sgn=-1, workers=1
    )
    recovered_doppler = image_to_shifted_spectrum(
        complex_input, axis=1, sgn=-1, workers=1
    )
    roundtrip_relative_error = float(
        np.max(np.abs(recovered_doppler - shifted_doppler))
        / np.max(np.abs(shifted_doppler))
    )
    window, metrics = make_window(
        LOOK_WIDTH_BINS, "tukey", tukey_alpha=0.25, normalization="energy"
    )

    raw_spectra = []
    standard_spectra = []
    analytic_coefficients: list[list[complex]] = [
        [] for _ in range(len(components))
    ]
    for band in bands:
        look = sublook_from_spectrum(
            recovered_doppler,
            band,
            axis=1,
            sgn=-1,
            window=window,
            workers=1,
        )
        intensity = np.abs(look) ** 2
        raw_spectra.append(_raw_centered_spectrum_crop(intensity))
        standard, _ = intensity_spectrum_crop(
            intensity.astype(np.float32), half_width=SPATIAL_HALF_WIDTH, workers=1
        )
        standard_spectra.append(standard)
        support_time = slice_time[band.start : band.stop]
        for component_index, item in enumerate(components):
            analytic_coefficients[component_index].append(
                complex(
                    np.sum(window**2 * np.exp(-1j * item.omega_rad_per_s * support_time))
                    / np.sum(window**2)
                )
            )
        del look, intensity

    raw_spectra_array = np.asarray(raw_spectra, dtype=np.complex128)
    standard_spectra_array = np.asarray(standard_spectra, dtype=np.complex128)
    centers = component_crop_centers(components)
    analytic_fits = [
        phase_slope_from_complex_series(values, look_time, hac_lag=4)
        for values in analytic_coefficients
    ]
    sublook_fits = [
        phase_slope_from_complex_series(
            raw_spectra_array[:, center[0], center[1]], look_time, hac_lag=4
        )
        for center in centers
    ]
    spatial_fits = [
        phase_slope_from_complex_series(
            standard_spectra_array[:, center[0], center[1]], look_time, hac_lag=4
        )
        for center in centers
    ]
    smoothed, mapped = estimate_component_slopes(
        standard_spectra_array, look_time, components
    )

    stages = []
    for index, item in enumerate(components):
        final = -float(smoothed[index]["signed_slope_rad_per_s"])
        stages.append(
            {
                "component_id": item.component_id,
                "omega_truth_rad_per_s": item.omega_rad_per_s,
                "omega_after_intensity_generation_rad_per_s": float(
                    -analytic_fits[index]["slope_rad_per_s"]
                ),
                "omega_after_sublook_formation_rad_per_s": float(
                    -sublook_fits[index]["slope_rad_per_s"]
                ),
                "omega_after_spatial_fft_rad_per_s": float(
                    -spatial_fits[index]["slope_rad_per_s"]
                ),
                "omega_after_smoothing_rad_per_s": final,
                "omega_after_sign_alignment_rad_per_s": final,
                "omega_final_rad_per_s": final,
                "final_error_rad_per_s": final - item.omega_rad_per_s,
            }
        )
    errors = np.asarray([item["final_error_rad_per_s"] for item in stages])
    del carrier, modulation, shifted_doppler, complex_input, recovered_doppler
    del raw_spectra_array, standard_spectra_array, mapped
    return {
        "construction_equation": (
            "Z(x,f)=R(f)[1+sum_j epsilon*A_j*exp(i*k_j*x-i*omega_j*t(f)+i*phi_j)]"
        ),
        "cross_convention": "F_secondary * conj(F_reference)",
        "sicd_sign_surrogate": -1,
        "image_to_Doppler_transform": "fft",
        "Doppler_to_image_transform": "ifft",
        "Doppler_slice_time_mapping": {
            "formula": "t(f_bin)=(bin+0.5)*0.03 s",
            "slice_time_step_s": DOPPLER_TIME_STEP_S,
            "slice_count": AZIMUTH_SAMPLE_COUNT,
            "look_width_s": LOOK_WIDTH_BINS * DOPPLER_TIME_STEP_S,
            "look_step_s": LOOK_STEP_BINS * DOPPLER_TIME_STEP_S,
            "overlap_fraction": 1.0 - LOOK_STEP_BINS / LOOK_WIDTH_BINS,
            "effective_look_centers_s": look_time.tolist(),
        },
        "window": asdict(metrics),
        "roundtrip_relative_max_error": roundtrip_relative_error,
        "stage_tracking": stages,
        "max_abs_error_rad_per_s": float(np.max(np.abs(errors))),
        "rmse_rad_per_s": float(np.sqrt(np.mean(errors**2))),
        "all_bins_valid": bool(all(item["valid"] for item in smoothed)),
        "component_diagnostics": smoothed,
    }


def fit_linear_law(k_rad_per_m: Sequence[float], omega: Sequence[float]) -> dict[str, float]:
    k = np.asarray(k_rad_per_m, dtype=np.float64)
    values = np.asarray(omega, dtype=np.float64)
    design = np.column_stack((np.ones(k.size), k))
    beta = np.linalg.lstsq(design, values, rcond=None)[0]
    residual = values - design @ beta
    return {
        "intercept_rad_per_s": float(beta[0]),
        "slope_m_per_s": float(beta[1]),
        "rmse_rad_per_s": float(np.sqrt(np.mean(residual**2))),
    }

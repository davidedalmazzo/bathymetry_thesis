"""Minimal physical ocean-surface to SAR-intensity forward model for Block 10.

This is deliberately not a raw-SAR simulator.  It isolates linear-wave orbital
velocity, geometric tilt/RAR modulation, azimuth displacement, and conservative
density/Jacobian effects before applying the already validated intensity
cross-spectrum phase estimator.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

import numpy as np
from scipy.ndimage import map_coordinates

from .synthetic_validation import finite_depth_omega, gaussian_patch_weights
from .wave_analysis import intensity_spectrum_crop, local_coherent_phase_slope_map


G_M_PER_S2 = 9.80665
N_RANGE = 768
N_AZIMUTH = 512
PIXEL_SPACING_RANGE_M = 8.0
PIXEL_SPACING_AZIMUTH_M = 8.0
SPATIAL_HALF_WIDTH = 96
PATCH_RADIUS = 2


@dataclass(frozen=True)
class RadarGeometry:
    incidence_angle_deg: float = 21.842925232944808
    slant_range_m: float = 610403.7510692304
    platform_speed_m_per_s: float = 7657.75057715643
    range_bearing_toward_sensor_deg: float = 101.91931056749142
    grid_row_positive_bearing_deg: float = 281.9193113543813
    azimuth_positive_bearing_deg: float = 191.18580265546754
    los_radial_velocity_positive: str = "toward_sensor"
    azimuth_mapping_sign: int = 1

    @property
    def range_over_velocity_s(self) -> float:
        return self.slant_range_m / self.platform_speed_m_per_s

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["range_over_velocity_s"] = self.range_over_velocity_s
        result["mapping_equation"] = (
            "y_SAR = y + (R/V) u_LOS for u_LOS positive toward sensor"
        )
        result["sign_derivation"] = (
            "Positive velocity toward the sensor is negative range-rate; zero-Doppler "
            "location shifts in positive along-track image coordinate by +(R/V)u_LOS."
        )
        return result


@dataclass(frozen=True)
class OceanComponent:
    component_id: str
    range_fft_mode: int
    azimuth_fft_mode: int
    k_range_rad_per_m: float
    k_azimuth_rad_per_m: float
    k_rad_per_m: float
    wavelength_m: float
    omega_rad_per_s: float
    period_s: float
    angle_from_range_deg: float
    amplitude_m: float
    steepness_ka: float
    phase_rad: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def physical_components(angle_case: str, *, depth_m: float = 10.0) -> list[OceanComponent]:
    """Return six grid-exact finite-depth components for one angle geometry."""

    if angle_case == "range_0deg":
        mode_pairs = ((32, 0), (38, 0), (46, 0), (55, 0), (65, 0), (76, 0))
    elif angle_case == "vandenberg_like_22deg":
        mode_pairs = ((30, 8), (36, 10), (43, 12), (52, 14), (61, 17), (71, 20))
    else:
        raise ValueError(f"unknown angle case {angle_case!r}")
    phases = (0.17, -0.83, 1.21, -1.74, 2.13, -2.51)
    length_range = N_RANGE * PIXEL_SPACING_RANGE_M
    length_azimuth = N_AZIMUTH * PIXEL_SPACING_AZIMUTH_M
    output = []
    for index, ((range_mode, azimuth_mode), phase) in enumerate(
        zip(mode_pairs, phases), start=1
    ):
        k_range = 2.0 * np.pi * range_mode / length_range
        k_azimuth = 2.0 * np.pi * azimuth_mode / length_azimuth
        k = float(np.hypot(k_range, k_azimuth))
        omega = float(finite_depth_omega(k, depth_m))
        steepness = 0.012
        amplitude = steepness / k
        output.append(
            OceanComponent(
                component_id=f"K{index}",
                range_fft_mode=range_mode,
                azimuth_fft_mode=azimuth_mode,
                k_range_rad_per_m=k_range,
                k_azimuth_rad_per_m=k_azimuth,
                k_rad_per_m=k,
                wavelength_m=2.0 * np.pi / k,
                omega_rad_per_s=omega,
                period_s=2.0 * np.pi / omega,
                angle_from_range_deg=float(np.degrees(np.arctan2(k_azimuth, k_range))),
                amplitude_m=amplitude,
                steepness_ka=steepness,
                phase_rad=phase,
            )
        )
    return output


class LinearWaveSurface:
    """Precomputed grid-exact wave surface and linear orbital velocities."""

    def __init__(
        self,
        components: Sequence[OceanComponent],
        radar: RadarGeometry,
        *,
        depth_m: float = 10.0,
    ) -> None:
        self.components = list(components)
        self.radar = radar
        self.depth_m = float(depth_m)
        row = np.arange(N_RANGE, dtype=np.float64)[:, None] * PIXEL_SPACING_RANGE_M
        col = np.arange(N_AZIMUTH, dtype=np.float64)[None, :] * PIXEL_SPACING_AZIMUTH_M
        base = np.asarray(
            [
                item.k_range_rad_per_m * row
                + item.k_azimuth_rad_per_m * col
                + item.phase_rad
                for item in self.components
            ],
            dtype=np.float32,
        )
        self.cos_base = np.cos(base).astype(np.float32)
        self.sin_base = np.sin(base).astype(np.float32)
        self.omega = np.asarray(
            [item.omega_rad_per_s for item in self.components], dtype=np.float64
        )
        self.amplitude = np.asarray(
            [item.amplitude_m for item in self.components], dtype=np.float64
        )
        self.k_range = np.asarray(
            [item.k_range_rad_per_m for item in self.components], dtype=np.float64
        )
        self.k_azimuth = np.asarray(
            [item.k_azimuth_rad_per_m for item in self.components], dtype=np.float64
        )
        self.k = np.asarray(
            [item.k_rad_per_m for item in self.components], dtype=np.float64
        )
        self.cos_direction = self.k_range / self.k
        self.sin_direction = self.k_azimuth / self.k
        incidence = np.deg2rad(radar.incidence_angle_deg)
        horizontal_orbital_amplitude = (
            self.amplitude * self.omega / np.tanh(self.k * self.depth_m)
        )
        vertical_orbital_amplitude = self.amplitude * self.omega
        self.weights = {
            "eta_cos": self.amplitude,
            "eta_range_sin": -self.amplitude * self.k_range,
            "eta_azimuth_sin": -self.amplitude * self.k_azimuth,
            "u_range_cos": horizontal_orbital_amplitude * self.cos_direction,
            "u_azimuth_cos": horizontal_orbital_amplitude * self.sin_direction,
            "w_vertical_sin": vertical_orbital_amplitude,
            "u_los_cos": np.sin(incidence)
            * horizontal_orbital_amplitude
            * self.cos_direction,
            "u_los_sin": np.cos(incidence) * vertical_orbital_amplitude,
            "du_los_dy_sin": -np.sin(incidence)
            * horizontal_orbital_amplitude
            * self.cos_direction
            * self.k_azimuth,
            "du_los_dy_cos": np.cos(incidence)
            * vertical_orbital_amplitude
            * self.k_azimuth,
        }
        self._row_grid = np.broadcast_to(
            np.arange(N_RANGE, dtype=np.float64)[:, None],
            (N_RANGE, N_AZIMUTH),
        )
        self._col_grid = np.broadcast_to(
            np.arange(N_AZIMUTH, dtype=np.float64)[None, :],
            (N_RANGE, N_AZIMUTH),
        )
        self._flat_row_base = (
            np.arange(N_RANGE, dtype=np.int64)[:, None] * N_AZIMUTH
        )

    def _quadratures(self, time_s: float) -> tuple[np.ndarray, np.ndarray]:
        current = self.omega * float(time_s)
        cos_time = np.cos(current)[:, None, None]
        sin_time = np.sin(current)[:, None, None]
        cos_phase = self.cos_base * cos_time + self.sin_base * sin_time
        sin_phase = self.sin_base * cos_time - self.cos_base * sin_time
        return cos_phase, sin_phase

    @staticmethod
    def _sum(weights: np.ndarray, values: np.ndarray) -> np.ndarray:
        return np.einsum("j,jrc->rc", weights, values, optimize=True)

    def fields(self, time_s: float) -> dict[str, np.ndarray]:
        cos_phase, sin_phase = self._quadratures(time_s)
        result = {
            "eta_m": self._sum(self.weights["eta_cos"], cos_phase),
            "eta_range_slope": self._sum(
                self.weights["eta_range_sin"], sin_phase
            ),
            "eta_azimuth_slope": self._sum(
                self.weights["eta_azimuth_sin"], sin_phase
            ),
            "u_range_m_per_s": self._sum(
                self.weights["u_range_cos"], cos_phase
            ),
            "u_azimuth_m_per_s": self._sum(
                self.weights["u_azimuth_cos"], cos_phase
            ),
            "w_vertical_m_per_s": self._sum(
                self.weights["w_vertical_sin"], sin_phase
            ),
            "u_los_m_per_s": self._sum(self.weights["u_los_cos"], cos_phase)
            + self._sum(self.weights["u_los_sin"], sin_phase),
            "du_los_dy_per_s": self._sum(
                self.weights["du_los_dy_sin"], sin_phase
            )
            + self._sum(self.weights["du_los_dy_cos"], cos_phase),
        }
        return {name: np.asarray(value, dtype=np.float32) for name, value in result.items()}

    def rar_brightness(self, fields: dict[str, np.ndarray]) -> np.ndarray:
        """Parameter-free geometric tilt proxy: (n dot LOS / cos incidence)^2."""

        incidence = np.deg2rad(self.radar.incidence_angle_deg)
        range_slope = fields["eta_range_slope"]
        azimuth_slope = fields["eta_azimuth_slope"]
        normalizer = np.sqrt(1.0 + range_slope**2 + azimuth_slope**2)
        mu = (
            np.cos(incidence) - np.sin(incidence) * range_slope
        ) / normalizer
        return np.asarray(
            10.0 * (np.maximum(mu, 0.0) / np.cos(incidence)) ** 2,
            dtype=np.float32,
        )

    def inverse_displacement(
        self, source: np.ndarray, displacement_m: np.ndarray
    ) -> np.ndarray:
        """Brightness-preserving inverse warp, without density/Jacobian gain."""

        source_col = self._col_grid.copy()
        displacement_pixels = displacement_m / PIXEL_SPACING_AZIMUTH_M
        for _ in range(3):
            sampled_displacement = map_coordinates(
                displacement_pixels,
                [self._row_grid, source_col],
                order=1,
                mode="wrap",
                prefilter=False,
            )
            source_col = self._col_grid - sampled_displacement
        return np.asarray(
            map_coordinates(
                source,
                [self._row_grid, source_col],
                order=1,
                mode="wrap",
                prefilter=False,
            ),
            dtype=np.float32,
        )

    def conservative_displacement(
        self, source: np.ndarray, displacement_m: np.ndarray
    ) -> np.ndarray:
        """Forward conservative splat including density/Jacobian and folds."""

        target = (
            self._col_grid + displacement_m / PIXEL_SPACING_AZIMUTH_M
        ) % N_AZIMUTH
        lower = np.floor(target).astype(np.int64)
        fraction = target - lower
        upper = (lower + 1) % N_AZIMUTH
        lower_flat = (self._flat_row_base + lower).ravel()
        upper_flat = (self._flat_row_base + upper).ravel()
        values = np.asarray(source, dtype=np.float64)
        output = np.bincount(
            lower_flat,
            weights=(values * (1.0 - fraction)).ravel(),
            minlength=N_RANGE * N_AZIMUTH,
        )
        output += np.bincount(
            upper_flat,
            weights=(values * fraction).ravel(),
            minlength=N_RANGE * N_AZIMUTH,
        )
        return np.asarray(output.reshape(N_RANGE, N_AZIMUTH), dtype=np.float32)

    def instantaneous_models(
        self,
        time_s: float,
        *,
        beta_scale: float = 1.0,
        model_names: Iterable[str] = ("M0", "M1", "M2", "M3", "M4"),
    ) -> tuple[dict[str, np.ndarray], dict[str, float]]:
        requested = set(model_names)
        unknown = requested.difference({"M0", "M1", "M2", "M3", "M4"})
        if unknown:
            raise ValueError(f"unknown model names: {sorted(unknown)}")
        fields = self.fields(time_s)
        m0 = np.asarray(10.0 + fields["eta_m"], dtype=np.float32)
        rar = self.rar_brightness(fields)
        beta = (
            float(beta_scale)
            * self.radar.azimuth_mapping_sign
            * self.radar.range_over_velocity_s
        )
        displacement = np.asarray(beta * fields["u_los_m_per_s"], dtype=np.float32)
        jacobian = 1.0 + beta * fields["du_los_dy_per_s"]
        result: dict[str, np.ndarray] = {}
        if "M0" in requested:
            result["M0"] = m0
        if "M1" in requested:
            result["M1"] = rar
        if "M2" in requested:
            result["M2"] = self.inverse_displacement(m0, displacement)
        if "M3" in requested:
            result["M3"] = self.conservative_displacement(m0, displacement)
        if "M4" in requested:
            result["M4"] = self.conservative_displacement(rar, displacement)
        diagnostics = {
            "beta_scale": float(beta_scale),
            "beta_s": float(beta),
            "maximum_abs_u_los_m_per_s": float(
                np.max(np.abs(fields["u_los_m_per_s"]))
            ),
            "rms_u_los_m_per_s": float(
                np.sqrt(np.mean(fields["u_los_m_per_s"] ** 2))
            ),
            "maximum_abs_azimuth_displacement_m": float(
                np.max(np.abs(displacement))
            ),
            "minimum_mapping_jacobian": float(np.min(jacobian)),
            "maximum_mapping_jacobian": float(np.max(jacobian)),
            "fold_fraction_jacobian_le_zero": float(np.mean(jacobian <= 0.0)),
            "near_caustic_fraction_abs_jacobian_lt_0p1": float(
                np.mean(np.abs(jacobian) < 0.1)
            ),
        }
        return result, diagnostics


def temporally_averaged_sequences(
    surface: LinearWaveSurface,
    center_times_s: Sequence[float],
    *,
    look_width_s: float,
    beta_scale: float,
    model_names: Iterable[str],
    quadrature_order: int = 9,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Average instantaneous model brightness over a rectangular look time."""

    if look_width_s <= 0 or quadrature_order < 1:
        raise ValueError("look width and quadrature order must be positive")
    names = tuple(model_names)
    nodes, weights = np.polynomial.legendre.leggauss(quadrature_order)
    weights = weights / 2.0
    centers = np.asarray(center_times_s, dtype=np.float64)
    sequences = {
        name: np.empty((centers.size, N_RANGE, N_AZIMUTH), dtype=np.float32)
        for name in names
    }
    diagnostics = []
    for center_index, center in enumerate(centers):
        accumulators = {
            name: np.zeros((N_RANGE, N_AZIMUTH), dtype=np.float64)
            for name in names
        }
        local_diagnostics = []
        for node, weight in zip(nodes, weights):
            current_time = center + 0.5 * look_width_s * node
            images, current_diagnostic = surface.instantaneous_models(
                current_time, beta_scale=beta_scale, model_names=names
            )
            for name in names:
                accumulators[name] += float(weight) * images[name]
            local_diagnostics.append(current_diagnostic)
        for name in names:
            sequences[name][center_index] = accumulators[name].astype(np.float32)
        diagnostics.append(
            {
                "center_time_s": float(center),
                "maximum_abs_u_los_m_per_s": max(
                    item["maximum_abs_u_los_m_per_s"] for item in local_diagnostics
                ),
                "maximum_abs_azimuth_displacement_m": max(
                    item["maximum_abs_azimuth_displacement_m"]
                    for item in local_diagnostics
                ),
                "minimum_mapping_jacobian": min(
                    item["minimum_mapping_jacobian"] for item in local_diagnostics
                ),
                "maximum_fold_fraction": max(
                    item["fold_fraction_jacobian_le_zero"]
                    for item in local_diagnostics
                ),
                "maximum_near_caustic_fraction": max(
                    item["near_caustic_fraction_abs_jacobian_lt_0p1"]
                    for item in local_diagnostics
                ),
            }
        )
    return sequences, {
        "look_width_s": float(look_width_s),
        "temporal_average": "9-point Gauss-Legendre quadrature of a rectangular look",
        "quadrature_order": int(quadrature_order),
        "beta_scale": float(beta_scale),
        "per_look": diagnostics,
    }


def component_crop_centers(
    components: Sequence[OceanComponent], *, half_width: int = SPATIAL_HALF_WIDTH
) -> list[tuple[int, int]]:
    return [
        (
            half_width + item.range_fft_mode,
            half_width + item.azimuth_fft_mode,
        )
        for item in components
    ]


def recover_phase_frequencies(
    intensity_sequence: np.ndarray,
    time_s: Sequence[float],
    components: Sequence[OceanComponent],
    *,
    hac_lag: int = 4,
) -> dict[str, Any]:
    """Apply the Block-9-validated intensity FFT -> local phase-rate path."""

    spectra = []
    for image in np.asarray(intensity_sequence):
        spectrum, _ = intensity_spectrum_crop(
            image, half_width=SPATIAL_HALF_WIDTH, workers=1
        )
        spectra.append(spectrum)
    spectra_array = np.asarray(spectra, dtype=np.complex128)
    mapped = local_coherent_phase_slope_map(
        spectra_array,
        np.asarray(time_s, dtype=np.float64),
        gaussian_patch_weights(PATCH_RADIUS),
        hac_lag=hac_lag,
        adjacent_coherence_threshold=0.70,
        independent_indices=(0, 5, 10),
        independent_coherence_threshold=0.25,
        maximum_phase_step_rad=np.pi / 2.0,
        maximum_step_consistency_error_rad=0.25,
    )
    rows = []
    for component, center in zip(components, component_crop_centers(components)):
        slope = float(mapped["slope_rad_per_s"][center])
        rows.append(
            {
                "component_id": component.component_id,
                "crop_center_row_col": list(center),
                "k_rad_per_m": component.k_rad_per_m,
                "wavelength_m": component.wavelength_m,
                "angle_from_range_deg": component.angle_from_range_deg,
                "omega_truth_rad_per_s": component.omega_rad_per_s,
                "signed_phase_slope_rad_per_s": slope,
                "omega_hat_aligned_rad_per_s": -slope,
                "omega_hat_absolute_rad_per_s": abs(slope),
                "bias_aligned_rad_per_s": -slope - component.omega_rad_per_s,
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
    k = np.asarray([item.k_rad_per_m for item in components])
    truth = np.asarray([item.omega_rad_per_s for item in components])
    recovered = np.asarray([row["omega_hat_aligned_rad_per_s"] for row in rows])
    design = np.column_stack((np.ones(k.size), k))
    truth_beta = np.linalg.lstsq(design, truth, rcond=None)[0]
    recovered_beta = np.linalg.lstsq(design, recovered, rcond=None)[0]
    truth_std = float(np.std(truth, ddof=1))
    recovered_std = float(np.std(recovered, ddof=1))
    return {
        "cross_convention": "F_secondary * conj(F_reference)",
        "half_plane": "injected +k only; conjugate -k excluded from statistics",
        "components": rows,
        "all_components_valid": bool(all(row["valid"] for row in rows)),
        "valid_component_count": int(sum(row["valid"] for row in rows)),
        "bias_mean_rad_per_s": float(np.mean(recovered - truth)),
        "bias_max_abs_rad_per_s": float(np.max(np.abs(recovered - truth))),
        "rmse_rad_per_s": float(np.sqrt(np.mean((recovered - truth) ** 2))),
        "truth_linear_fit": {
            "intercept_rad_per_s": float(truth_beta[0]),
            "domega_dk_m_per_s": float(truth_beta[1]),
        },
        "recovered_linear_fit": {
            "intercept_rad_per_s": float(recovered_beta[0]),
            "domega_hat_dk_m_per_s": float(recovered_beta[1]),
        },
        "constantness_ratio_std_hat_over_std_truth": recovered_std / truth_std,
        "quasi_constant_predeclared_criterion": (
            "std(omega_hat)/std(omega_truth)<0.25 and |domega_hat/dk|<0.25|domega_truth/dk|"
        ),
        "quasi_constant": bool(
            recovered_std / truth_std < 0.25
            and abs(recovered_beta[1]) < 0.25 * abs(truth_beta[1])
        ),
        "spatial_spectral_resolution": {
            "delta_k_range_rad_per_m": 2.0
            * np.pi
            / (N_RANGE * PIXEL_SPACING_RANGE_M),
            "delta_k_azimuth_rad_per_m": 2.0
            * np.pi
            / (N_AZIMUTH * PIXEL_SPACING_AZIMUTH_M),
            "patch_radius_bins": PATCH_RADIUS,
        },
    }

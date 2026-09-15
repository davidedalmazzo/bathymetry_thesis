"""Auditable primitives introduced by Block 17.

The routines are deliberately independent of network and SAR readers.  They
make missingness, temporal admissibility, and estimator assumptions explicit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np


ARCHIVE_OUTCOMES = {
    "recovered", "not_found", "network_error", "parse_error",
    "temporal_mismatch", "joint_directional_incomplete", "screening_only",
}


def bin_widths(frequency_hz: Sequence[float]) -> np.ndarray:
    """Voronoi-like widths for ordered spectral bin centres."""
    f = np.asarray(frequency_hz, dtype=float)
    if f.ndim != 1 or f.size < 2 or not np.all(np.diff(f) > 0):
        raise ValueError("frequency centres must be a strictly increasing vector")
    edges = np.r_[f[0] - (f[1] - f[0]) / 2,
                  (f[:-1] + f[1:]) / 2,
                  f[-1] + (f[-1] - f[-2]) / 2]
    return np.diff(edges)


def integrate_density(frequency_hz, density, *, widths_hz=None):
    """Integrate valid bins without bridging gaps caused by missing values."""
    f = np.asarray(frequency_hz, float)
    e = np.asarray(density, float)
    w = bin_widths(f) if widths_hz is None else np.asarray(widths_hz, float)
    if f.shape != e.shape or f.shape != w.shape:
        raise ValueError("frequency, density and widths must have equal shape")
    valid = np.isfinite(f) & np.isfinite(e) & np.isfinite(w) & (w > 0) & (e >= 0)
    return {"energy": float(np.sum(e[valid] * w[valid])),
            "valid_bin_count": int(valid.sum()),
            "method": "explicit_bin_width_sum" if widths_hz is not None else "derived_bin_width_sum_no_gap_interpolation"}


def joint_directional_validity(frequency_hz, density, alpha1, alpha2, r1, r2,
                               *, band=(0.04, 0.25), widths_hz=None,
                               minimum_energy_coverage=0.9):
    """Require all five directional products to be valid in the same bins."""
    f, e, a1, a2, q1, q2 = map(lambda x: np.asarray(x, float),
                               (frequency_hz, density, alpha1, alpha2, r1, r2))
    if len({x.shape for x in (f, e, a1, a2, q1, q2)}) != 1:
        raise ValueError("all arrays must have equal shape")
    w = bin_widths(f) if widths_hz is None else np.asarray(widths_hz, float)
    in_band = (f >= band[0]) & (f <= band[1]) & np.isfinite(e) & (e >= 0)
    joint = in_band & np.isfinite(a1) & np.isfinite(a2) & np.isfinite(q1) & np.isfinite(q2)
    joint &= (q1 >= 0) & (q1 <= 1) & (q2 >= 0) & (q2 <= 1)
    denominator = np.sum(e[in_band] * w[in_band])
    coverage = float(np.sum(e[joint] * w[joint]) / denominator) if denominator > 0 else 0.0
    return {"joint_mask": joint, "in_band_mask": in_band,
            "joint_bin_count": int(joint.sum()), "band_bin_count": int(in_band.sum()),
            "energy_coverage": coverage,
            "admissible": bool(joint.any() and coverage >= minimum_energy_coverage)}


def select_reference(attempts: Iterable[Mapping], *, model=None, max_distance_km=50.0,
                     max_offset_s=3600.0, minimum_energy_coverage=0.9):
    """Choose nearest *admissible* reference, never first HTTP success."""
    audit = []
    for raw in sorted(attempts, key=lambda a: (float(a.get("distance_km", np.inf)), str(a.get("station_id", "")))):
        a = dict(raw)
        if a.get("outcome") not in ARCHIVE_OUTCOMES:
            raise ValueError("unknown archive outcome")
        if float(a.get("distance_km", np.inf)) > max_distance_km:
            a["decision"] = "outside_distance"
        elif a["outcome"] != "recovered":
            a["decision"] = a["outcome"]
        elif abs(float(a.get("offset_s", np.inf))) > max_offset_s:
            a["decision"] = "temporal_mismatch"
        elif float(a.get("joint_energy_coverage", 0.0)) < minimum_energy_coverage:
            a["decision"] = "joint_directional_incomplete"
        else:
            a["decision"] = "selected"
            audit.append(a)
            return {"selected": a, "attempts": audit, "status": "independent_directional_reference"}
        audit.append(a)
    return {"selected": None, "screening_fallback": model, "attempts": audit,
            "status": "model_screening_only" if model is not None else "no_admissible_reference"}


def ndbc_archive_plan(station_id: str, year: int, product="swden"):
    """Ordered aggregate/annual candidates; dimensions must be discovered, never fixed."""
    stem = f"{station_id}w"
    base = f"https://dods.ndbc.noaa.gov/thredds/dodsC/data/{product}/{station_id}"
    return {"candidates": [f"{base}/{stem}9999.nc", f"{base}/{stem}{year}.nc"],
            "dimension_policy": "query metadata coordinates and shapes before slicing",
            "initial_status": "archive_not_queried"}


def cdip_reference_admissible(station_match, deployment_match, acquisition_covered):
    """CDIP is an alternative only with all three provenance links verified."""
    return bool(station_match and deployment_match and acquisition_covered)


def temporal_budgets(cphd_duration_s, sicd_aperture_s, look_duration_s):
    """Keep phase-history dwell and processed SICD aperture as separate paths."""
    def one(name, duration):
        if duration is None or not np.isfinite(duration) or duration <= 0:
            return {"path": name, "duration_s": None, "nominal_nonoverlapping_aperture_count": None}
        return {"path": name, "duration_s": float(duration),
                "nominal_nonoverlapping_aperture_count": int(np.floor(duration / look_duration_s)),
                "statistical_independence_demonstrated": False}
    return {"cphd_phase_history": one("cphd_phase_history", cphd_duration_s),
            "sicd_processed_image": one("sicd_processed_image", sicd_aperture_s)}


def roi_proxy_semantics(clearance_m):
    return {"representative_ocean_point_clearance_m": float(clearance_m),
            "centered_clearance_diameter_m": 2.0 * float(clearance_m),
            "boundary_role": "minimum_distance_to_ocean_piece_boundary; may be coastline or footprint edge",
            "is_maximum_ocean_roi_diameter": False}


def synthesize_band(times_s, f0_hz, epsilon, n_components, rng, *, legacy=False):
    """Generate a target Gaussian *energy* band or reproduce the legacy double weighting."""
    t = np.asarray(times_s, float)
    sigma = epsilon * f0_hz
    if sigma == 0:
        f = np.full(n_components, f0_hz)
    else:
        f = rng.normal(f0_hz, sigma, n_components)
        # Truncated physical support, with deterministic resampling from the same RNG.
        bad = f <= 0
        while bad.any():
            f[bad] = rng.normal(f0_hz, sigma, int(bad.sum()))
            bad = f <= 0
    phase = rng.uniform(-np.pi, np.pi, n_components)
    if legacy and sigma > 0:
        energy_weight = np.exp(-0.5 * ((f - f0_hz) / sigma) ** 2)
    else:
        energy_weight = np.ones(n_components)
    amp = np.sqrt(energy_weight)
    z = np.sum(amp[:, None] * np.exp(1j * (2 * np.pi * f[:, None] * t + phase[:, None])), axis=0)
    p = amp ** 2
    mean = float(np.sum(p * f) / np.sum(p))
    std = float(np.sqrt(np.sum(p * (f - mean) ** 2) / np.sum(p)))
    return {"signal": z, "frequencies_hz": f, "amplitudes": amp,
            "realized_energy_mean_hz": mean, "realized_energy_std_hz": std,
            "definition": "legacy_sample_then_reweight" if legacy else "gaussian_energy_distribution_equal_component_power"}


def estimate_tone_frequency(times_s, signal, search_band_hz, grid_size=20001):
    """Continuous-grid coherent estimator; FFT bins are only display samples."""
    t = np.asarray(times_s, float); z = np.asarray(signal, complex)
    grid = np.linspace(search_band_hz[0], search_band_hz[1], grid_size)
    score = np.abs(np.exp(-2j * np.pi * grid[:, None] * t[None, :]) @ z)
    return float(grid[int(np.argmax(score))])


def dispersion_omega(k, h, g=9.80665):
    return np.sqrt(g * np.asarray(k) * np.tanh(np.asarray(k) * h))


def dispersion_derivatives(k, h, g=9.80665):
    k = float(k); h = float(h); omega = float(dispersion_omega(k, h, g))
    sech2 = 1.0 / np.cosh(k * h) ** 2
    fk = -g * (np.tanh(k * h) + k * h * sech2)
    fh = -g * k * k * sech2
    fw = 2 * omega
    return {"omega": omega, "group_velocity": -fk / fw,
            "dh_dk": -fk / fh, "dh_domega": -fw / fh}


def depth_variance(k, h, var_k, var_omega, cov_k_omega, g=9.80665):
    d = dispersion_derivatives(k, h, g)
    variance = d["dh_dk"] ** 2 * var_k + d["dh_domega"] ** 2 * var_omega + 2 * d["dh_dk"] * d["dh_domega"] * cov_k_omega
    return {**d, "variance_h": float(variance)}

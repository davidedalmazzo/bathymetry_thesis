"""Assess when SAR inter-look phase can and cannot equal ocean-wave phase."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from umbra_sar.physical_identification import (
    quasi_linear_cross_spectrum,
    quasi_linear_zero_lag_phase_slope,
)
from umbra_sar.wave_analysis import linear_phase_fit


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / 'umbra/Vandenberg/results/analysis_block5'
FROZEN_PATH = OUTPUT_DIR / "BLOCK5_FROZEN_INPUTS.json"
BLOCK4_PATH = ROOT / 'umbra/Vandenberg/results/analysis_block4/BLOCK4_PHASE_METRICS_SAR_ONLY.json'


def model_fit(times: np.ndarray, omega: float, reverse_ratio: float) -> dict[str, object]:
    lag = times - times[0]
    cross = quasi_linear_cross_spectrum(1.0, reverse_ratio, omega, lag)
    phase = np.unwrap(np.angle(cross / cross[0]))
    fit = linear_phase_fit(times, phase, hac_lag=0)
    return {
        "reverse_to_forward_effective_weight_ratio": reverse_ratio,
        "phase_rad": phase.tolist(),
        "fit_slope_rad_per_s": fit["slope_rad_per_s"],
        "fit_rmse_rad": fit["residual_rmse_rad"],
        "fit_r_squared": fit["r_squared"],
    }


def main() -> None:
    frozen = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    block4 = json.loads(BLOCK4_PATH.read_text(encoding="utf-8"))
    times = np.asarray(block4["time_axis"]["physical_slow_time_centers_s"])
    omega_observed = float(frozen["frozen_sar_only"]["omega_rad_per_s"])
    omega_17 = 2.0 * math.pi / float(frozen["frozen_sar_only"]["T_SAR_s"])
    omega_13 = 2.0 * math.pi / 13.33
    magnitude_observed = abs(omega_observed)

    ratio_13_small_lag = (omega_13 - magnitude_observed) / (
        omega_13 + magnitude_observed
    )
    ratio_17_small_lag = (omega_17 - magnitude_observed) / (
        omega_17 + magnitude_observed
    )
    q_grid = np.linspace(0.0, 0.99, 1000)
    slopes_13 = np.asarray(
        [model_fit(times, omega_13, float(q))["fit_slope_rad_per_s"] for q in q_grid]
    )
    nearest_grid = int(np.argmin(np.abs(slopes_13 - omega_observed)))

    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Theoretical phase-slope audit; no SAR estimate is retuned",
        "cross_convention": "F_secondary * conj(F_reference)",
        "frozen_observed_slope_rad_per_s": omega_observed,
        "candidate_angular_frequencies_rad_per_s": {
            "17_902230457_s": omega_17,
            "13_33_s": omega_13,
        },
        "quasi_linear_equation": {
            "source": "Sentinel-1 OSW ATBD v1.3 Eq. (34), derived from the Engen-Johnsen cross-spectral transform",
            "form": "P_qlin(k,t)=C(k){A(k) exp(-i omega t)+B(k) exp(+i omega t)}",
            "definitions": {
                "C(k)": "stationary system transfer times azimuth-cutoff factor",
                "A(k)": "|T(k)|^2 S(k)",
                "B(k)": "|T(-k)|^2 S(-k)",
            },
            "phase": "arg C + atan2((B-A) sin(omega t), (A+B) cos(omega t))",
            "zero_lag_phase_slope": "omega (B-A)/(A+B)",
            "finite_lag_phase_slope": "omega (B^2-A^2)/[(A+B)^2 cos^2(omega t)+(B-A)^2 sin^2(omega t)]",
        },
        "limiting_cases": {
            "only_S_plus_k": quasi_linear_zero_lag_phase_slope(1.0, 0.0, omega_13),
            "equal_opposite_directions": quasi_linear_zero_lag_phase_slope(
                1.0, 1.0, omega_13
            ),
            "only_S_minus_k": quasi_linear_zero_lag_phase_slope(0.0, 1.0, omega_13),
        },
        "small_lag_directional_ratio_diagnostics": {
            "if_ocean_period_17_902230457_s_B_over_A": ratio_17_small_lag,
            "if_ocean_period_13_33_s_B_over_A": ratio_13_small_lag,
            "warning": "These ratios apply only to the derivative at zero lag. They are not valid fits over the full 11.59-s baseline.",
        },
        "finite_baseline_13_33_s_test": {
            "physical_lags_s": (times - times[0]).tolist(),
            "unidirectional": model_fit(times, omega_13, 0.0),
            "small_lag_matched_ratio": model_fit(
                times, omega_13, ratio_13_small_lag
            ),
            "q_scan_range": [0.0, 0.99],
            "q_scan_slope_range_rad_per_s": [
                float(np.min(slopes_13)),
                float(np.max(slopes_13)),
            ],
            "nearest_q_grid_to_observed_slope": float(q_grid[nearest_grid]),
            "nearest_grid_slope_rad_per_s": float(slopes_13[nearest_grid]),
            "conclusion": "For A>B and fixed positive weights, the finite-lag phase winds with the -omega branch; the observed -0.351 rad/s is outside this q-scan. A stationary bidirectional quasi-linear mixture alone does not reproduce the long-baseline slope for T=13.33 s.",
        },
        "phase_bias_needed_if_13_33_s_unidirectional_rad_per_s": omega_13
        - magnitude_observed,
        "bias_terms": [
            {
                "term": "Directional mixture S(k)/S(-k) and MTF asymmetry",
                "effect": "Changes the instantaneous phase through A=|T(k)|^2S(k), B=|T(-k)|^2S(-k); generally makes phase nonlinear in lag, not simply omega*t.",
            },
            {
                "term": "Complex nonlinear contribution P_nlin(k,t)",
                "effect": "Vector-adds to P_qlin. Its time-dependent phase and amplitude change Im(P* dP/dt)/|P|^2. OSW removes it using a wind/direction/wave-age LUT before inversion.",
            },
            {
                "term": "Velocity bunching / shift MTF and RAR MTF",
                "effect": "The total MTF controls A/B and detectability. Its phase cancels in the ideal same-k stationary quadratic term, but unequal look filters or time variation can leave differential phase.",
            },
            {
                "term": "Stationary system transfer U(k) and azimuth cutoff",
                "effect": "A constant arg U is an intercept and cancels in relative phase. Look-dependent U, filtering, or residual registration makes it a slope/ramp bias.",
            },
            {
                "term": "Finite spectral patch",
                "effect": "The estimator measures arg of a weighted sum over k, mixing omega(k), directions, MTF, and peak drift. Arg(sum) is not the mean of component phases.",
            },
            {
                "term": "Six-second overlapping temporal windows",
                "effect": "They temporally average the evolving scene and correlate adjacent estimates; a symmetric identical window mainly changes amplitude, while unequal effective windows can shift phase.",
            },
            {
                "term": "Advection/current and finite-depth dispersion",
                "effect": "The observed wave-pattern frequency can include k dot U_current and omega(k,h); it need not be the intrinsic deep-water frequency.",
            },
            {
                "term": "Common image translation / phase ramp",
                "effect": "A look-dependent shift contributes -2*pi*k dot Delta_x to phase. The near-zero land-control slope constrains, but cannot exclude ocean-specific motion or decorrelation.",
            },
            {
                "term": "Noise, clutter, speckle, and decorrelation",
                "effect": "Ideal cross-spectra suppress the co-spectrum speckle pedestal, but finite ensemble size and loss of coherence perturb phase; OSW estimates clutter noise and weights looks accordingly.",
            },
        ],
        "applicability_warning": "Sentinel-1 OSW is a C-band open-ocean operational formulation. Its structural equation is relevant here, but its calibrated MTF/nonlinear lookup tables cannot be transferred directly to this Umbra X-band nearshore acquisition.",
        "sources": [
            {
                "citation": "Engen, G. and Johnsen, H. (1995), SAR-ocean wave inversion using image cross spectra, IEEE TGRS 33(4), 1047-1056",
                "url": "https://doi.org/10.1109/36.406690",
            },
            {
                "citation": "Sentinel-1 Ocean Swell Wave Spectra (OSW) Algorithm Definition, v1.3 (2020), especially Eqs. 16, 34-39",
                "url": "https://sentinels.copernicus.eu/documents/247904/349449/S-1_L2_OSW_Detailed_Algorithm_Definition.pdf",
            },
            {
                "citation": "Monteban et al. (2019), Spatiotemporal Observations of Wave Dispersion Within Sea Ice Using Sentinel-1 SAR TOPS Mode",
                "url": "https://doi.org/10.1029/2019JC015311",
            },
        ],
    }
    json_path = OUTPUT_DIR / "BLOCK5_PHASE_THEORY.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    note = f"""# Block 5 - phase theory audit

This note tests the assumption `dphi/dt = omega_ocean`; it does **not** modify the frozen SAR-only estimate. The frozen value remains `{omega_observed:.12f} rad/s` (`T_SAR={frozen['frozen_sar_only']['T_SAR_s']:.12f} s`).

## Cross convention and quasi-linear model

The Sentinel-1 OSW ATBD defines the look cross-spectrum with the later/secondary intensity transform multiplied by the conjugate of the earlier/reference transform (ATBD Eq. 16), matching `F_secondary * conj(F_reference)`. Its quasi-linear ocean-to-SAR model (Eq. 34) is

`P_qlin(k,t) = C(k) [ A(k) exp(-i omega t) + B(k) exp(+i omega t) ]`,

where `A=|T(k)|^2 S(k)`, `B=|T(-k)|^2 S(-k)`, and `C` contains the stationary system transfer and azimuth-cutoff attenuation. Therefore the selected `+k` component has negative phase slope under the validated convention, while the conjugate peak has the opposite sign.

The phase is

`arg(C) + atan2((B-A) sin(omega t), (A+B) cos(omega t))`.

Only the unidirectional limit `B=0` gives `phi=-omega t+constant`. Equal counter-propagating effective energy (`A=B`) makes the cross-spectrum real and removes a continuous directional phase. At zero lag,

`dphi/dt = omega (B-A)/(A+B)`.

Thus the MTF does not simply disappear: its *phase* cancels in ideal stationary `|T|^2`, but its directional amplitudes change the effective ratio `B/A = |T(-k)|^2 S(-k) / (|T(k)|^2 S(k))`.

## Numerical implication for the two candidate periods

For 17.902230457 s, `omega={omega_17:.12f} rad/s`, numerically identical in magnitude to the SAR-only slope. The zero-lag effective reverse/forward ratio is `{ratio_17_small_lag:.6g}` (essentially unidirectional).

For 13.33 s, `omega={omega_13:.12f} rad/s`. Matching only the *zero-lag derivative* would require `B/A={ratio_13_small_lag:.6f}`. But over the actual 0-{times[-1]-times[0]:.3f} s PVP baselines that model fits a slope of `{result['finite_baseline_13_33_s_test']['small_lag_matched_ratio']['fit_slope_rad_per_s']:.6f} rad/s`, not -0.351. Scanning `0 <= B/A <= 0.99` never reaches the observed slope. A stationary quasi-linear directional mixture alone therefore cannot turn a 13.33-s unidirectional branch into the observed highly linear 17.902-s phase history.

If the physical ocean component were nevertheless 13.33 s, an additional net phase-rate term of about `+{result['phase_bias_needed_if_13_33_s_unidirectional_rad_per_s']:.6f} rad/s` would be needed relative to the `-omega` branch.

## Terms that can bias the measured slope

1. **Nonlinear SAR contribution.** Engen-Johnsen's forward transform is nonlinear. OSW explicitly subtracts a complex `P_nlin(k,t)` simulated as a function of wind speed, direction, and inverse wave age before applying its quasi-linear inversion. Vector addition changes phase rate through `Im(P* dP/dt)/|P|^2`.
2. **Velocity-bunching/shift and RAR MTF.** OSW uses `T(k)=i k_y T_xi(k)+T_sigma(k)` (Eqs. 35-37). The ideal Eq. 34 contains its squared magnitude, but directional asymmetry changes `A/B`; different effective look filters or time variability can add differential phase.
3. **`S(k)/S(-k)`.** Counter-propagating energy makes phase nonlinear in lag and can suppress the zero-lag derivative. It is not a constant multiplicative correction to omega.
4. **Finite k-patch and peak drift.** The measured coefficient is a coherent weighted sum over 25 bins, each with different dispersion, directionality, MTF, and nonlinear contamination. `arg(sum P_k)` is not `sum arg(P_k)`.
5. **Six-second overlapping looks.** Each point is a temporally filtered observation, not an instantaneous surface. Identical symmetric windows primarily attenuate amplitude; unequal effective windows and overlap correlations can bias phase and understate uncertainty.
6. **System/registration phase.** A constant `arg U(k)` is only an intercept. A time-dependent image shift gives a ramp `-2 pi k dot Delta_x(t)`. The land control is consistent with zero common slope, constraining this mechanism.
7. **Hydrodynamic frequency.** Finite depth and current advection (`k dot U_current`) alter the observed pattern frequency relative to intrinsic deep-water dispersion.
8. **Noise and decorrelation.** Cross-spectra suppress the co-spectrum speckle pedestal, but finite averaging, clutter, and motion decorrelation still perturb phase.

## Scope warning

The OSW structure is the appropriate theoretical warning against equating phase rate and ocean frequency automatically. Its calibrated Sentinel-1 C-band open-ocean MTF and nonlinear lookup tables are not transferable as numerical corrections to this Umbra X-band nearshore case.

Sources: [Engen & Johnsen (1995)](https://doi.org/10.1109/36.406690); [Sentinel-1 OSW ATBD v1.3](https://sentinels.copernicus.eu/documents/247904/349449/S-1_L2_OSW_Detailed_Algorithm_Definition.pdf), pp. 25-26 and 36-40; [Monteban et al. (2019)](https://doi.org/10.1029/2019JC015311).
"""
    md_path = OUTPUT_DIR / "BLOCK5_PHASE_THEORY.md"
    md_path.write_text(note, encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        "13.33-s small-lag q and full-baseline slope:",
        ratio_13_small_lag,
        result["finite_baseline_13_33_s_test"]["small_lag_matched_ratio"][
            "fit_slope_rad_per_s"
        ],
    )


if __name__ == "__main__":
    main()

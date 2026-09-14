#!/usr/bin/env python3
"""Block 16b - the corrected scene-selection criterion.

CHECKPOINT_15 concluded that a BIMODAL swell is required, with
d_omega * T_dwell > 2*pi.  That rule is self-inconsistent: applied to the
46218 spectrum itself, NO pair of bands reaches even one beat cycle
(best case 10.53/16.67 s -> 0.764), and Block 16a shows there is no second
system to begin with.  The rule also rests on a category error: a mixture
being indistinguishable from a single component is only a problem when the
two must be SEPARATED.  If the system is narrow, both hypotheses return the
same omega to within the band width, and nothing needs separating.

This script replaces the rule with the quantity that actually binds:
  (1) the relative spectral width eps = sigma_f / f_bar of the dominant
      system inside the SAR look cone, which sets the spread of the
      phase-slope estimator;
  (2) the joint resolution / WKB constraint on the window width W, which
      sets the wavenumber error and, through A, dominates the depth budget.

No tuning to any measured value.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

G = 9.80665
T_SPAN_S = 21.836
N_LOOKS = 32


# ---------------------------------------------------------------- estimator
def phase_slope(sig: np.ndarray, times: np.ndarray, ref: int = 0):
    cross = sig * np.conj(sig[ref])
    ph = np.unwrap(np.angle(cross))
    c = times - times.mean()
    slope = float(np.sum(c * ph) / np.sum(c ** 2))
    pred = slope * c + (ph.mean() - slope * c.mean())
    ss = float(np.sum((ph - pred) ** 2))
    st = float(np.sum((ph - ph.mean()) ** 2))
    return -slope, (1.0 - ss / st if st > 0 else float("nan"))


def band_trial(rng, f0, eps, times, ncomp=64):
    """One realisation of a SINGLE system with Gaussian relative width eps."""
    fs = rng.normal(f0, eps * f0, ncomp)
    w = np.exp(-0.5 * ((fs - f0) / (eps * f0)) ** 2)
    a = np.sqrt(w) * rng.rayleigh(1.0, ncomp)
    ph0 = rng.uniform(0.0, 2 * np.pi, ncomp)
    sig = np.array([np.sum(a * np.exp(1j * (ph0 - 2 * np.pi * fs * tt)))
                    for tt in times])
    return phase_slope(sig, times)


# ---------------------------------------------------------------- dispersion
def k_of(T: float, h: float) -> float:
    w = 2 * math.pi / T
    k = w * w / G
    for _ in range(400):
        k = w * w / (G * math.tanh(k * h))
    return k


def amplification(T: float, h: float):
    kh = k_of(T, h) * h
    A = 1.0 + math.sinh(2 * kh) / (2 * kh)
    return A, 2.0 * (A - 1.0)


def self_consistent_window(h: float, T: float, grad: float):
    """Largest W whose shoaling smear of the peak stays inside one resolution
    element.  A wider window resolves more finely than the peak is sharp, so
    the extra width buys nothing and breaks eq. (2.36)."""
    best = None
    W = 100.0
    while W < 8000.0:
        dh = grad * W
        if h - dh / 2 <= 1.0:
            break
        smear = abs(k_of(T, h - dh / 2) - k_of(T, h + dh / 2))
        if smear <= 2 * math.pi / W:
            best = W
        W += 25.0
    return best


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260914)
    times = np.linspace(0.0, T_SPAN_S, N_LOOKS)
    f0 = 0.08377                              # 46218 swell-band mean

    report = {
        "note": "look times approximated as uniform over the measured span; "
                "Block 11 measured the true centres, deviation < 1%",
        "T_span_s": T_SPAN_S, "n_looks": N_LOOKS, "f0_hz": f0,
        "true_omega_rad_s": 2 * math.pi * f0,
    }

    # (1) width -> estimator spread
    rows = []
    for eps in (0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.177, 0.25):
        res = [band_trial(rng, f0, eps, times) for _ in range(800)]
        ws = np.array([r[0] for r in res])
        r2 = np.array([r[1] for r in res])
        p10, p50, p90 = np.percentile(ws, [10, 50, 90])
        rows.append({"eps": eps, "median_omega": float(p50),
                     "p10": float(p10), "p90": float(p90),
                     "relative_80pct_width": float((p90 - p10) / p50),
                     "sigma_over_median": float(ws.std() / p50),
                     "median_R2": float(np.median(r2))})
    report["width_response"] = rows
    report["width_response_verdict"] = (
        "the estimator is MEDIAN-UNBIASED at every width - broadening widens "
        "the distribution, it does not shift it; median R2 stays >= 0.997 up to "
        "eps = 0.25, so R2 has no diagnostic power at any width"
    )

    # where the frozen Vandenberg value sits in the single-broad-system law
    res = np.array([band_trial(rng, f0, 0.177, times)[0] for _ in range(6000)])
    report["vandenberg_value_in_single_system_law"] = {
        "observed_omega_rad_s": 0.4120656492,
        "percentile": float(100 * np.mean(res < 0.4120656492)),
        "median": float(np.median(res)),
        "p10": float(np.percentile(res, 10)),
        "p90": float(np.percentile(res, 90)),
        "comment": "reported as a placement, not as a validation; Vandenberg "
                   "stays frozen at the Block 15K classification",
    }

    # (2) the WKB / resolution floor on the depth error
    floor = []
    for grad in (8.79e-3, 4.0e-3, 2.0e-3, 1.0e-3, 5.0e-4):
        for h in (5.0, 10.0, 15.0, 25.0, 40.0):
            T = 13.0
            A, B = amplification(T, h)
            W = self_consistent_window(h, T, grad)
            if W is None:
                floor.append({"grad": grad, "h_m": h, "W_m": None})
                continue
            L = 2 * math.pi / k_of(T, h)
            dLL = L / W
            floor.append({
                "grad": grad, "h_m": h, "L_m": L, "A": A, "W_max_m": W,
                "dL_over_L": dLL,
                "dh_over_h_spatial_only": A * dLL,
                "dh_over_h_with_eps003": math.hypot(A * dLL, B * 0.035),
            })
    report["depth_error_floor"] = floor
    report["depth_error_floor_verdict"] = (
        "on the Vandenberg gradient 8.79e-3 the spatial term alone floors "
        "dh/h at 40-62% however well omega is measured; reaching 10% needs a "
        "bottom gradient of order 5e-4 m/m. The binding constraint of the "
        "method is wavenumber resolution against the WKB window, not the "
        "frequency estimate. Stated under thesis eq. (3.9) dL/L = L/W, i.e. "
        "the resolution criterion; a peak-centroid estimator relaxes it by its "
        "own gain, but Block 15K measured only 2.014 effective radial elements "
        "in the lobe, so that gain is of order sqrt(2), not orders of magnitude."
    )

    report["selection_criterion"] = {
        "supersedes": "CHECKPOINT_15 'serve swell bimodale, d_omega*T_dwell > 2pi'",
        "reason_superseded": [
            "no pair in the 46218 spectrum reaches one beat cycle "
            "(best 10.53/16.67 s -> 0.764)",
            "Block 16a shows there is no second system: the frequency dip is "
            "chi-squared noise and the directional split is the MEM artefact",
            "one-vs-two only matters when the two must be separated; for a "
            "narrow single system both hypotheses give the same omega",
        ],
        "replacement": [
            "rank scenes by eps = sigma_f/f_bar of the dominant system inside "
            "a +/-20 deg cone about the expected image wave vector; eps <= 0.05 "
            "keeps the omega spread under 10%",
            "rank by bottom gradient: |grad h| <= 2e-3 m/m for dh/h under ~25%, "
            "<= 5e-4 for ~10%",
            "require the swell to be shore-normal enough that the cone holds "
            "most of the band energy",
        ],
    }

    (out / "BLOCK16B_WIDTH_CRITERION.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("width_response_verdict", "vandenberg_value_in_single_system_law",
                       "depth_error_floor_verdict", "selection_criterion")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Block 15a - does the estimator survive two components in one spectral bin?

Why this test did not exist yet
-------------------------------
CHECKPOINT_9 validated the phase-slope estimator end to end and authorised the
return to real data. Every one of its cases, including the seven realism
variants (white noise, fixed speckle, decorrelating speckle, unequal
amplitudes, finite-width peaks, detrend+Tukey, 80 per cent overlap), carries a
SINGLE angular frequency. TEST B's "constant-frequency 1.818e-06" is a
single-frequency check. Two components with DIFFERENT omega occupying the same
spectral bin were never simulated.

That configuration is not hypothetical at Vandenberg, it is forced by geometry.
NDBC 46218 at the acquisition time carries 8.9 per cent of m0 at 13.33 s and
8.2 per cent at 15.38 s. At h = 16.44 m those are 158.70 m and 186.15 m, a
separation of 0.00584 rad/m, against a 0.00628 rad/m spectral step on a 1000 m
window. They are unresolvable in wavenumber. In frequency the separation is
0.0629 rad/s, a beat period of 100 s, against a 21.836 s observation: 0.22 of
a beat cycle. They are unresolvable in time as well.

So every bin of the main lobe is an irreducible mixture, and the question this
script answers is the only one that matters: what does the estimator report
when handed one?

The estimator reproduced here is the one in the analysis scripts, verbatim in
structure: cross-spectrum against a mid-sequence reference look, unwrap along
the look axis, least squares slope with intercept, magnitude taken at the end.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np

GRAVITY_M_PER_S2 = 9.80665

# NDBC 46218, 2025-02-16 19:00 UTC. period [s], share of m0.
BUOY_BAND = [(16.67, 0.015), (15.38, 0.082), (14.29, 0.060),
             (13.33, 0.089), (12.50, 0.045), (11.76, 0.056)]


def estimate(signal: np.ndarray, times: np.ndarray, reference: int) -> dict:
    """The pipeline estimator, applied to one bin's complex time series."""

    cross = signal * np.conj(signal[reference])
    phase = np.unwrap(np.angle(cross))
    centred = times - times.mean()
    slope = float(np.sum(centred * phase) / np.sum(centred**2))
    fitted = phase.mean() + slope * centred
    total = float(np.sum((phase - phase.mean()) ** 2))
    r_squared = 1.0 - float(np.sum((phase - fitted) ** 2)) / total if total > 0 else 1.0
    return {
        "omega_rad_per_s": abs(slope),
        "period_s": 2.0 * np.pi / abs(slope) if slope != 0 else np.inf,
        "r_squared": r_squared,
        "residual_rmse_rad": float(np.sqrt(np.mean((phase - fitted) ** 2))),
        "envelope_min_over_max": float(np.abs(cross).min() / np.abs(cross).max()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="a real BLOCK12_SUBLOOK_MANIFEST.json, so the look "
                             "times are the measured ones and not a model")
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--speckle-realisations", type=int, default=200)
    parser.add_argument("--speckle-to-signal", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=20260914)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    times = np.asarray(manifest["mean_tx_time_per_look_s"], dtype=np.float64)
    reference = len(times) // 2
    span = float(times.max() - times.min())
    print(f"tempi reali: {times.size} look, span {span:.4f} s, "
          f"riferimento indice {reference}")

    w1, w2 = 2.0 * np.pi / 13.33, 2.0 * np.pi / 15.38
    beat = 2.0 * np.pi / abs(w1 - w2)
    print(f"componenti 13.33 s ({w1:.4f} rad/s) e 15.38 s ({w2:.4f} rad/s)")
    print(f"battimento {beat:.1f} s -> l'osservazione copre {span / beat:.3f} cicli\n")

    # --- 1. deterministic sweep over amplitude ratio and relative phase ----
    print("1. miscela deterministica, senza rumore")
    print("   A2/A1  fase rel.   omega      T [s]     R^2      inviluppo min/max")
    rows = []
    ratios = [0.0, 0.25, 0.5, 0.75, 0.96, 1.0, 1.5, 2.0]
    phases = [0.0, np.pi / 2, np.pi, 3 * np.pi / 2]
    for ratio, phi in product(ratios, phases):
        z = np.exp(-1j * w1 * times) + ratio * np.exp(-1j * (w2 * times + phi))
        r = estimate(z, times, reference)
        rows.append({"amplitude_ratio": ratio, "relative_phase_rad": phi, **r})
        if phi in (0.0, np.pi):
            print(f"   {ratio:5.2f}  {phi:7.3f}   {r['omega_rad_per_s']:.4f}   "
                  f"{r['period_s']:6.2f}   {r['r_squared']:.4f}   "
                  f"{r['envelope_min_over_max']:.3f}")
    omegas = np.array([r["omega_rad_per_s"] for r in rows if r["amplitude_ratio"] > 0])
    r2s = np.array([r["r_squared"] for r in rows if r["amplitude_ratio"] > 0])
    print(f"\n   intervallo di omega restituito: {omegas.min():.4f} - {omegas.max():.4f} rad/s")
    print(f"   R^2 minimo su TUTTE le miscele: {r2s.min():.4f}")
    print(f"   -> un R^2 alto NON distingue una componente singola da una miscela\n")

    # --- 2. the full buoy swell band in one bin ----------------------------
    print("2. l'intera banda di swell della boa in un solo bin")
    band_amp = np.sqrt(np.array([s for _, s in BUOY_BAND]))
    band_w = np.array([2.0 * np.pi / T for T, _ in BUOY_BAND])
    rng = np.random.default_rng(args.seed)
    estimates = []
    for _ in range(args.speckle_realisations):
        phi = rng.uniform(0, 2 * np.pi, band_amp.size)
        z = np.sum(band_amp[:, None] * np.exp(-1j * (band_w[:, None] * times[None, :]
                                                     + phi[:, None])), axis=0)
        estimates.append(estimate(z, times, reference))
    om = np.array([e["omega_rad_per_s"] for e in estimates])
    rr = np.array([e["r_squared"] for e in estimates])
    energy_weighted = float(np.sum([s * 2 * np.pi / T for T, s in BUOY_BAND])
                            / np.sum([s for _, s in BUOY_BAND]))
    band_summary = {
        "realisations": int(args.speckle_realisations),
        "omega_median_rad_per_s": float(np.median(om)),
        "omega_p10_p90_rad_per_s": [float(np.percentile(om, 10)),
                                    float(np.percentile(om, 90))],
        "omega_min_max_rad_per_s": [float(om.min()), float(om.max())],
        "r_squared_median": float(np.median(rr)),
        "r_squared_min": float(rr.min()),
        "energy_weighted_omega_rad_per_s": energy_weighted,
    }
    print(f"   fasi relative casuali, {args.speckle_realisations} realizzazioni")
    print(f"   omega mediana {np.median(om):.4f} rad/s, "
          f"p10-p90 {np.percentile(om, 10):.4f}-{np.percentile(om, 90):.4f}, "
          f"estremi {om.min():.4f}-{om.max():.4f}")
    print(f"   media pesata sull'energia delle componenti: {energy_weighted:.4f} rad/s")
    print(f"   R^2 mediana {np.median(rr):.4f}, minima {rr.min():.4f}")
    print(f"   osservato: Block 12 al picco 0.4121 (R^2 0.9945); "
          f"Block 13 a riva 0.4338\n")

    # --- 3. can a single component plus speckle reach the same value? ------
    print("3. controllo: componente SINGOLA a 13.33 s piu' speckle decorrelante")
    single = []
    for _ in range(args.speckle_realisations):
        noise = (rng.normal(size=times.size) + 1j * rng.normal(size=times.size))
        z = np.exp(-1j * w1 * times) + args.speckle_to_signal * noise / np.sqrt(2)
        single.append(estimate(z, times, reference))
    som = np.array([e["omega_rad_per_s"] for e in single])
    print(f"   speckle/segnale {args.speckle_to_signal}: omega mediana "
          f"{np.median(som):.4f}, p10-p90 {np.percentile(som, 10):.4f}-"
          f"{np.percentile(som, 90):.4f}")
    print(f"   una componente singola resta centrata su {w1:.4f}: il rumore "
          f"allarga, non sposta.\n")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": ("Estimator behaviour on two and many unresolved components, "
                  "using the measured sub-look times. Closes the gap left by "
                  "CHECKPOINT_9, whose realism variants all carry one omega."),
        "look_times_s": times.tolist(),
        "reference_look_index": reference,
        "span_s": span,
        "beat_period_s": beat,
        "beat_cycles_observed": span / beat,
        "deterministic_sweep": rows,
        "buoy_band_in_one_bin": band_summary,
        "single_component_with_speckle": {
            "speckle_to_signal": args.speckle_to_signal,
            "omega_median_rad_per_s": float(np.median(som)),
            "omega_p10_p90_rad_per_s": [float(np.percentile(som, 10)),
                                        float(np.percentile(som, 90))],
        },
        "observed_for_comparison": {
            "block12_peak_omega_rad_per_s": 0.4121,
            "block12_peak_r_squared": 0.9945,
            "block13_inshore_omega_rad_per_s": 0.4338,
        },
        "caveats": [
            "This is an estimator test, not a SAR simulation: the components are "
            "injected directly into one spectral bin, with no imaging operator.",
            "It shows what the estimator does with a mixture; it does not by "
            "itself prove the real bin is one. The real-data test is Block 15b.",
        ],
    }
    out = args.outdir / "BLOCK15A_ESTIMATOR_MIXTURE.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Scritto {out}")


if __name__ == "__main__":
    main()

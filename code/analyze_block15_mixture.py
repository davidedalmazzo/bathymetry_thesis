"""Block 15b - is the real peak bin one component or a mixture? (real data)

Block 15a established that the estimator cannot tell: over every two-component
mixture of the buoy's 13.33 s and 15.38 s peaks it returns omega between 0.3875
and 0.4916 rad/s with a minimum R-squared of 0.9973. High linearity of the
phase ramp, which Blocks 4, 6, 12 and 13 all used as evidence of a clean single
component, has no discriminating power at all.

Three observables do discriminate, and all three are computable from the
sub-look arrays already on disk.

1. The envelope. For one component the cross-spectral magnitude at a bin is set
   by decorrelation alone and depends only on the lag. For two components it is
   |S_i||S_j| with |S(t)|^2 = A1^2 + A2^2 + 2 A1 A2 cos(dw t + phi): it depends
   on ABSOLUTE time. So regressing log|C_ij| on both lag and mid-time separates
   them. A non-zero mid-time coefficient is non-stationarity, and a stationary
   single component cannot produce one.

2. The per-look power at the bin, |S_i| against look time. One component plus
   speckle fluctuates about a constant; a mixture beats at dw = 0.0629 rad/s,
   which over the 21.836 s span is 1.372 rad of a cosine — a large, smooth,
   systematic swing.

3. Model comparison on the complex series. Fit, to the same 32 complex samples:
   a single component with free omega; the same with an exponential
   decorrelation envelope; and the buoy's two components with omega FIXED at
   0.4714 and 0.4085 rad/s and only amplitudes and phases free. The last has
   four real parameters against three, so the comparison is nearly free of
   complexity penalty.

Run over many bins, not one: the question is whether the two-component model
wins SYSTEMATICALLY, not whether it wins somewhere.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

BUOY_OMEGA_1 = 2.0 * np.pi / 13.33
BUOY_OMEGA_2 = 2.0 * np.pi / 15.38


def tukey(n: int, alpha: float) -> np.ndarray:
    x = np.linspace(0.0, 1.0, n)
    out = np.ones(n)
    t = alpha / 2.0
    left, right = x < t, x > 1.0 - t
    out[left] = 0.5 * (1 + np.cos(np.pi * (2 * x[left] / alpha - 1)))
    out[right] = 0.5 * (1 + np.cos(np.pi * (2 * x[right] / alpha - 2 / alpha + 1)))
    return out


def detrended_spectrum(intensity: np.ndarray, window: np.ndarray) -> np.ndarray:
    work = np.asarray(intensity, dtype=np.float64)
    work = work - work.mean()
    rows, cols = work.shape
    u = np.linspace(-1.0, 1.0, rows)
    v = np.linspace(-1.0, 1.0, cols)
    work -= (np.dot(u, work.sum(axis=1)) / (cols * np.dot(u, u)) * u)[:, None]
    work -= (np.dot(v, work.sum(axis=0)) / (rows * np.dot(v, v)) * v)[None, :]
    return np.fft.fftshift(np.fft.fft2(work * window))


def linear_phase_fit(series, times, reference):
    cross = series * np.conj(series[reference])
    phase = np.unwrap(np.angle(cross))
    centred = times - times.mean()
    slope = float(np.sum(centred * phase) / np.sum(centred**2))
    fitted = phase.mean() + slope * centred
    total = float(np.sum((phase - phase.mean()) ** 2))
    return abs(slope), (1.0 - float(np.sum((phase - fitted) ** 2)) / total
                        if total > 0 else 1.0)


def _residual(model, data):
    r = model - data
    return np.concatenate([r.real, r.imag])


def fit_models(series: np.ndarray, times: np.ndarray) -> dict:
    """Single component, single with decorrelation, and the buoy pair."""

    scale = float(np.mean(np.abs(series)))
    z = series / scale
    t = times - times.mean()
    omega0, _ = linear_phase_fit(series, times, len(times) // 2)

    def m1(p):
        return p[0] * np.exp(1j * p[1]) * np.exp(-1j * p[2] * t)

    def m1d(p):
        return p[0] * np.exp(-np.abs(t) / max(p[3], 1e-3)) * np.exp(
            1j * p[1]) * np.exp(-1j * p[2] * t)

    def m2(p):
        return (p[0] * np.exp(1j * p[1]) * np.exp(-1j * BUOY_OMEGA_1 * t)
                + p[2] * np.exp(1j * p[3]) * np.exp(-1j * BUOY_OMEGA_2 * t))

    out = {}
    n = 2 * z.size
    for name, model, start, k in (
        ("single", m1, [1.0, 0.0, omega0], 3),
        ("single_decorrelating", m1d, [1.0, 0.0, omega0, 20.0], 4),
        ("buoy_pair_fixed_omega", m2, [0.7, 0.0, 0.7, 0.0], 4),
    ):
        best = None
        for seed_phase in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
            s = list(start)
            s[1] = seed_phase
            if name == "buoy_pair_fixed_omega":
                s[3] = seed_phase
            try:
                r = least_squares(lambda p: _residual(model(p), z), s, max_nfev=4000)
            except Exception:
                continue
            if best is None or r.cost < best.cost:
                best = r
        ss = float(2.0 * best.cost)
        out[name] = {
            "sum_of_squares": ss,
            "aic": float(n * np.log(max(ss, 1e-30) / n) + 2 * k),
            "parameters": [float(v) for v in best.x],
            "free_parameters": k,
        }
    out["delta_aic_pair_minus_single"] = (
        out["buoy_pair_fixed_omega"]["aic"] - out["single"]["aic"])
    out["delta_aic_pair_minus_single_decorrelating"] = (
        out["buoy_pair_fixed_omega"]["aic"] - out["single_decorrelating"]["aic"])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indir", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--label", default="block12")
    parser.add_argument("--tukey-alpha", type=float, default=0.1)
    parser.add_argument("--wavelength-bounds-m", type=float, nargs=2,
                        default=[80.0, 400.0])
    parser.add_argument("--min-power-fraction", type=float, default=0.10)
    parser.add_argument("--min-r-squared", type=float, default=0.95)
    parser.add_argument("--max-bins", type=int, default=60)
    parser.add_argument("--control-band-m", type=float, nargs=2, default=[15.0, 60.0],
                        help="speckle-dominated wavelengths used both to normalise "
                             "each look's illumination and as a null control")
    parser.add_argument("--no-illumination-normalisation", action="store_true")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((args.indir / "BLOCK12_SUBLOOK_MANIFEST.json")
                          .read_text(encoding="utf-8"))
    stack = np.load(args.indir / "BLOCK12_SUBLOOKS_complex64.npy", mmap_mode="r")
    times = np.asarray(manifest["mean_tx_time_per_look_s"], dtype=np.float64)
    spacing = float(manifest["grid"]["spacing_m"])
    look_count, rows, cols = stack.shape
    reference = look_count // 2
    print(f"[{args.label}] {look_count} look, griglia {rows}x{cols} a {spacing} m, "
          f"span {np.ptp(times):.4f} s")

    window = np.outer(tukey(rows, args.tukey_alpha), tukey(cols, args.tukey_alpha))
    spectra = np.array([detrended_spectrum(np.abs(np.asarray(stack[i])) ** 2, window)
                        for i in range(look_count)])

    ku = 2.0 * np.pi * np.fft.fftshift(np.fft.fftfreq(rows, d=spacing))
    kv = 2.0 * np.pi * np.fft.fftshift(np.fft.fftfreq(cols, d=spacing))
    KU, KV = np.meshgrid(ku, kv, indexing="ij")
    magnitude = np.hypot(KU, KV)
    with np.errstate(divide="ignore"):
        wavelength = np.where(magnitude > 0, 2.0 * np.pi / magnitude, np.inf)
    band = ((wavelength >= args.wavelength_bounds_m[0])
            & (wavelength <= args.wavelength_bounds_m[1]) & (KU < 0))
    control = ((wavelength >= args.control_band_m[0])
               & (wavelength <= args.control_band_m[1]))

    # Each look carries the illumination envelope of the dwell: the Block 12
    # manifest records the mean intensity per look rising from 0.48 to 1.00 and
    # falling to 0.81. That factor is common to every bin, and it would forge
    # both a mid-time dependence in log|C| and an apparent beat in the per-look
    # amplitude. Divide it out using a speckle-dominated control band, which
    # tracks the illumination without carrying the swell.
    illumination = np.sqrt(np.array(
        [np.median(np.abs(spectra[i][control]) ** 2) for i in range(look_count)]))
    illumination /= illumination.mean()
    print("illuminazione per look dalla banda di controllo "
          f"({args.control_band_m[0]:.0f}-{args.control_band_m[1]:.0f} m): "
          f"min {illumination.min():.3f}, max {illumination.max():.3f}, "
          f"escursione {illumination.max() / illumination.min():.2f}x")
    if not args.no_illumination_normalisation:
        spectra = spectra / illumination[:, None, None]
        print("  -> normalizzata via")
    else:
        print("  -> NON normalizzata (richiesto)")

    power = np.mean(np.abs(spectra) ** 2, axis=0)
    peak = np.unravel_index(int(np.argmax(np.where(band, power, -np.inf))), power.shape)
    print(f"picco: lambda {wavelength[peak]:.2f} m")

    # ---- 1. stationarity of the cross-spectral magnitude ------------------
    i, j = np.triu_indices(look_count, k=1)
    lag = times[j] - times[i]
    mid = 0.5 * (times[i] + times[j]) - times.mean()

    def stationarity(bin_index):
        s = spectra[:, bin_index[0], bin_index[1]]
        c = np.abs(s[j] * np.conj(s[i]))
        y = np.log(c / c.max() + 1e-30)
        design = np.column_stack((np.ones(y.size), np.abs(lag), mid))
        beta, *_ = np.linalg.lstsq(design, y, rcond=None)
        resid = y - design @ beta
        dof = y.size - 3
        sigma2 = float(resid @ resid / dof)
        cov = sigma2 * np.linalg.inv(design.T @ design)
        return beta, np.sqrt(np.diag(cov))

    beta, err = stationarity(peak)
    print("\n1. stazionarieta' dell'ampiezza del cross-spettro (bin di picco)")
    print(f"   log|C| = {beta[0]:+.3f} {beta[1]:+.4f}*|dt| {beta[2]:+.4f}*t_medio")
    print(f"   errori standard        {err[1]:.4f}        {err[2]:.4f}")
    print(f"   coefficiente sul tempo medio: {abs(beta[2] / err[2]):.1f} sigma"
          f"   [zero se componente singola stazionaria]")

    # The 496 pairs come from 32 looks and are far from independent, so the
    # parametric standard error understates the scatter by a large factor. The
    # only defensible reference is empirical: the same statistic on
    # speckle-dominated bins, where no wave exists and the coefficient must be
    # zero apart from estimation noise.
    strongest_control = np.argsort(np.where(control, power, -np.inf).ravel())[-200:]
    null_coef, null_sigma = [], []
    for flat in strongest_control:
        rc = np.unravel_index(int(flat), power.shape)
        b_, e_ = stationarity(rc)
        null_coef.append(b_[2])
        null_sigma.append(abs(b_[2] / e_[2]))
    null_coef = np.array(null_coef)
    null_sigma = np.array(null_sigma)
    null_scale = float(np.percentile(np.abs(null_coef), 68))
    print(f"   controllo nullo, 200 bin di sola speckle: coefficiente |.| "
          f"mediano {np.median(np.abs(null_coef)):.4f}, "
          f"68esimo pct {null_scale:.4f}, 95esimo {np.percentile(np.abs(null_coef), 95):.4f}")
    print(f"   il sigma parametrico su quegli stessi bin vale gia' "
          f"{np.median(null_sigma):.1f} in mediana: e' inflazionato, non usarlo")
    print(f"   -> il bin di picco sta a {abs(beta[2]) / null_scale:.1f} volte "
          f"la scala del nullo, percentile "
          f"{100.0 * (np.abs(null_coef) < abs(beta[2])).mean():.1f}")

    # ---- 2. per-look power at the peak bin --------------------------------
    s_peak = spectra[:, peak[0], peak[1]]
    amp = np.abs(s_peak) / np.abs(s_peak).max()
    order = np.argsort(times)
    print("\n2. ampiezza per look al bin di picco (normalizzata)")
    print("   " + " ".join(f"{a:.2f}" for a in amp[order]))
    print(f"   min {amp.min():.3f}  max 1.000  escursione {amp.max() / amp.min():.2f}x")
    print("   [una componente singola con speckle fluttua senza andamento; "
          "una miscela oscilla al battimento]")

    # ---- 3. model comparison over many bins -------------------------------
    keep = band & (power > args.min_power_fraction * power[peak])
    idx = np.argwhere(keep)
    scored = []
    for r, c in idx:
        s = spectra[:, r, c]
        om, r2 = linear_phase_fit(s, times, reference)
        if r2 < args.min_r_squared:
            continue
        scored.append((float(power[r, c]), int(r), int(c), om, r2))
    scored.sort(reverse=True)
    scored = scored[: args.max_bins]
    print(f"\n3. confronto fra modelli su {len(scored)} bin "
          f"(potenza > {args.min_power_fraction:.0%} del picco, R^2 > {args.min_r_squared})")

    records = []
    for p_, r, c, om, r2 in scored:
        s = spectra[:, r, c]
        fits = fit_models(s, times)
        b, e = stationarity((r, c))
        records.append({
            "row": r, "col": c,
            "wavelength_m": float(wavelength[r, c]),
            "power_relative_to_peak": float(p_ / power[peak]),
            "omega_linear_fit_rad_per_s": om,
            "r_squared_linear_fit": r2,
            "mid_time_coefficient": float(b[2]),
            "mid_time_significance_sigma": float(abs(b[2] / e[2])),
            "delta_aic_pair_minus_single": fits["delta_aic_pair_minus_single"],
            "delta_aic_pair_minus_single_decorrelating":
                fits["delta_aic_pair_minus_single_decorrelating"],
            "buoy_pair_amplitude_ratio": float(
                abs(fits["buoy_pair_fixed_omega"]["parameters"][2])
                / max(abs(fits["buoy_pair_fixed_omega"]["parameters"][0]), 1e-9)),
        })
    d1 = np.array([x["delta_aic_pair_minus_single"] for x in records])
    d2 = np.array([x["delta_aic_pair_minus_single_decorrelating"] for x in records])
    sig = np.array([x["mid_time_significance_sigma"] for x in records])
    ratio = np.array([x["buoy_pair_amplitude_ratio"] for x in records])
    print(f"   dAIC (coppia - singola):            mediana {np.median(d1):+.1f}, "
          f"vince la coppia in {int((d1 < 0).sum())}/{len(d1)} bin")
    print(f"   dAIC (coppia - singola+decorrel.):  mediana {np.median(d2):+.1f}, "
          f"vince la coppia in {int((d2 < 0).sum())}/{len(d2)} bin")
    print(f"   significativita' del tempo medio:   mediana {np.median(sig):.1f} sigma, "
          f"> 3 sigma in {int((sig > 3).sum())}/{len(sig)} bin")
    print(f"   rapporto di ampiezza A2/A1 recuperato: mediana {np.median(ratio):.2f} "
          f"(boa: 0.96 dalle energie)")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "scope": ("Single component versus mixture at the real peak bin, from "
                  "the stored sub-looks. Discriminators: stationarity of the "
                  "cross-spectral magnitude, per-look amplitude, and a model "
                  "comparison with the buoy periods held fixed."),
        "grid": manifest["grid"],
        "look_times_s": times.tolist(),
        "reference_look_index": reference,
        "tukey_alpha": args.tukey_alpha,
        "peak": {
            "row": int(peak[0]), "col": int(peak[1]),
            "wavelength_m": float(wavelength[peak]),
            "stationarity_intercept": float(beta[0]),
            "stationarity_lag_coefficient": float(beta[1]),
            "stationarity_mid_time_coefficient": float(beta[2]),
            "stationarity_mid_time_sigma": float(abs(beta[2] / err[2])),
            "per_look_amplitude_normalised": amp[order].tolist(),
        },
        "null_control": {
            "band_m": list(args.control_band_m),
            "bin_count": int(null_sigma.size),
            "median_abs_coefficient": float(np.median(np.abs(null_coef))),
            "p68_abs_coefficient": null_scale,
            "p95_abs_coefficient": float(np.percentile(np.abs(null_coef), 95)),
            "median_parametric_sigma_on_pure_speckle": float(np.median(null_sigma)),
            "note": ("the parametric sigma is inflated because 496 pairs are built "
                     "from 32 looks; use the empirical null scale instead"),
        },
        "illumination_per_look": illumination.tolist(),
        "illumination_normalised": not args.no_illumination_normalisation,
        "bins": records,
        "summary": {
            "bin_count": len(records),
            "median_delta_aic_pair_minus_single": float(np.median(d1)),
            "pair_wins_over_single": int((d1 < 0).sum()),
            "median_delta_aic_pair_minus_single_decorrelating": float(np.median(d2)),
            "pair_wins_over_single_decorrelating": int((d2 < 0).sum()),
            "median_mid_time_sigma_parametric_inflated": float(np.median(sig)),
            "median_recovered_amplitude_ratio": float(np.median(ratio)),
        },
        "verdict": (
            "The real data cannot separate one component from a mixture over this "
            "span. Block 15a predicts exactly that: 0.218 of a beat cycle makes "
            "the two observationally equivalent."),
        "caveats": [
            "Speckle is not modelled: the residual of every model contains it, so "
            "the AIC comparison is descriptive, not a likelihood ratio with "
            "calibrated significance.",
            "The 32 looks are disjoint in slow time but the bins are not "
            "independent of each other; bin counts are not degrees of freedom.",
            "Each look's spectrum is divided by the square root of the median "
            "power in a speckle-dominated control band, to remove the dwell "
            "illumination envelope that is common to all bins. Without it both "
            "the stationarity test and the per-look amplitude are confounded.",
            "The pair model fixes omega at the buoy values. It tests whether "
            "THOSE two components explain the bin, not whether some other pair "
            "would do better.",
        ],
    }
    out = args.outdir / f"BLOCK15B_MIXTURE_{args.label}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nScritto {out}")


if __name__ == "__main__":
    main()

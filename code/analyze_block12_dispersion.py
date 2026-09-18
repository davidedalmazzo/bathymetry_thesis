"""Block 12c - dispersion inversion on the backprojected, resolved lobe.

Block 6 could not attempt this. Its 540 m window left the primary lobe
answering with one number at every wave number: a weighted fit of the observed
against the dispersion frequency gave a response of 0.19 with a +0.269 rad/s
intercept, the signature of an unresolved train leaking across its own skirt.

On the 1440 m backprojected support the lobe is resolved and omega does vary
across it, so a dispersion relation can be fitted rather than asserted.

Also fixes a defect in analyze_block12_phase_slope.py: the coherence there is
computed from single spectral realisations, |a conj(b)| / sqrt(|a|^2 |b|^2),
which is identically one. It gated nothing. Coherence needs an ensemble, so it
is estimated here by smoothing the cross- and auto-spectra over a small
neighbourhood in k before taking the ratio.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / 'umbra/Vandenberg'
GRAVITY_M_PER_S2 = 9.80665


def tukey(n: int, alpha: float = 0.1) -> np.ndarray:
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


def smooth(field: np.ndarray, half: int = 1) -> np.ndarray:
    """Boxcar over a (2*half+1)^2 neighbourhood, wrapping in k."""

    out = np.zeros_like(field)
    for dr in range(-half, half + 1):
        for dc in range(-half, half + 1):
            out += np.roll(np.roll(field, dr, axis=0), dc, axis=1)
    return out / (2 * half + 1) ** 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indir", type=Path,
                        default=VANDENBERG / "results" / "block12_backprojection")
    parser.add_argument("--outdir", type=Path,
                        default=VANDENBERG / "results" / "analysis_block12")
    parser.add_argument("--wavelength-bounds-m", type=float, nargs=2,
                        default=[60.0, 300.0])
    parser.add_argument("--min-power-fraction", type=float, default=0.15)
    parser.add_argument("--min-r-squared", type=float, default=0.97)
    parser.add_argument("--min-coherence", type=float, default=0.25,
                        help="on the extreme pair, 21.8 s apart, where the "
                             "surface has genuinely decorrelated: peak "
                             "coherence falls from 0.93 at 5.6 s to 0.65")
    parser.add_argument("--dem-depth-m", type=float, default=16.441)
    parser.add_argument("--dem-depth-p10-p90-m", type=float, nargs=2,
                        default=[11.76, 23.03])
    parser.add_argument("--buoy-period-s", type=float, default=13.33333280351429)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((args.indir / "BLOCK12_SUBLOOK_MANIFEST.json")
                          .read_text(encoding="utf-8"))
    stack = np.load(args.indir / "BLOCK12_SUBLOOKS_complex64.npy", mmap_mode="r")
    times = np.asarray(manifest["mean_tx_time_per_look_s"], dtype=np.float64)
    spacing = float(manifest["grid"]["spacing_m"])
    look_count, rows, cols = stack.shape

    window = np.outer(tukey(rows), tukey(cols))
    spectra = np.array([detrended_spectrum(np.abs(np.asarray(stack[i])) ** 2, window)
                        for i in range(look_count)])
    reference = look_count // 2
    cross = spectra * np.conj(spectra[reference])
    power = np.mean(np.abs(spectra) ** 2, axis=0)

    first, last = spectra[0], spectra[-1]
    coherence = np.abs(smooth(first * np.conj(last))) / np.sqrt(
        smooth(np.abs(first) ** 2) * smooth(np.abs(last) ** 2) + 1e-30)

    phase = np.unwrap(np.angle(cross), axis=0)
    centred = times - times.mean()
    slope = np.tensordot(centred, phase, axes=(0, 0)) / float(np.sum(centred**2))
    residual = phase - (phase.mean(axis=0)[None] + slope[None] * centred[:, None, None])
    total = np.sum((phase - phase.mean(axis=0)[None]) ** 2, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        r_squared = 1.0 - np.sum(residual**2, axis=0) / total

    kx = 2.0 * np.pi * np.fft.fftshift(np.fft.fftfreq(rows, d=spacing))
    ky = 2.0 * np.pi * np.fft.fftshift(np.fft.fftfreq(cols, d=spacing))
    KX, KY = np.meshgrid(kx, ky, indexing="ij")
    magnitude = np.hypot(KX, KY)
    with np.errstate(divide="ignore"):
        wavelength = np.where(magnitude > 0, 2.0 * np.pi / magnitude, np.inf)

    band = ((wavelength >= args.wavelength_bounds_m[0])
            & (wavelength <= args.wavelength_bounds_m[1]))
    peak = np.unravel_index(int(np.argmax(np.where(band, power, -np.inf))), power.shape)
    hemisphere = (KX * KX[peak] + KY * KY[peak]) > 0
    keep = (band & hemisphere & (power > args.min_power_fraction * power[peak])
            & (r_squared > args.min_r_squared) & (coherence > args.min_coherence)
            & np.isfinite(slope))

    k = magnitude[keep]
    observed = np.abs(slope[keep])
    weight = power[keep] / power[peak]
    cosine = (KX[keep] * KX[peak] + KY[keep] * KY[peak]) / (
        magnitude[peak] * k)
    print(f"{int(keep.sum())} bin selezionati, lambda "
          f"{wavelength[keep].min():.1f}-{wavelength[keep].max():.1f} m, "
          f"omega {observed.min():.4f}-{observed.max():.4f} rad/s")
    print(f"coerenza levigata sui bin scelti: "
          f"{coherence[keep].min():.3f}-{coherence[keep].max():.3f}")

    def dispersion(depth: float) -> np.ndarray:
        return np.sqrt(GRAVITY_M_PER_S2 * k * np.tanh(k * abs(depth)))

    def fit(model, start):
        from scipy.optimize import least_squares
        solution = least_squares(
            lambda p: np.sqrt(weight) * (model(p) - observed), start)
        error = model(solution.x) - observed
        return solution.x, float(np.sqrt(np.sum(weight * error**2) / np.sum(weight)))

    models = {
        "linear_dispersion_free_depth": (lambda p: dispersion(p[0]), [10.0],
                                         ["depth_m"]),
        "dispersion_at_dem_depth_plus_current": (
            lambda p: np.sqrt(GRAVITY_M_PER_S2 * k
                              * np.tanh(k * args.dem_depth_m)) + k * p[0] * cosine,
            [-1.0], ["current_along_k_m_per_s"]),
        "free_depth_plus_current": (
            lambda p: dispersion(p[0]) + k * p[1] * cosine, [16.0, -1.0],
            ["depth_m", "current_along_k_m_per_s"]),
        "pure_scale_at_dem_depth": (
            lambda p: p[0] * np.sqrt(GRAVITY_M_PER_S2 * k
                                     * np.tanh(k * args.dem_depth_m)), [0.7],
            ["scale"]),
    }
    fits = {}
    print("\nmodello                                  parametri            rms pesato")
    for name, (model, start, labels) in models.items():
        values, rms = fit(model, start)
        fits[name] = {"parameters": dict(zip(labels, [float(v) for v in values])),
                      "weighted_rms_rad_per_s": rms}
        pretty = ", ".join(f"{a}={b:.3f}" for a, b in zip(labels, values))
        print(f"  {name:38s} {pretty:28s} {rms:.4f}")

    per_bin = observed**2 / (GRAVITY_M_PER_S2 * k)
    depths = np.where(per_bin < 1.0, np.arctanh(np.clip(per_bin, 0, 0.999999)) / k,
                      np.nan)
    trend = np.polyfit(np.log(wavelength[keep]), depths, 1)
    print(f"\nprofondita' per bin: mediana {np.nanmedian(depths):.2f} m, "
          f"IQR {np.nanpercentile(depths, 25):.2f}-{np.nanpercentile(depths, 75):.2f} m")
    print(f"  tendenza h vs log(lambda): {trend[0]:+.2f} m per e-fold "
          f"(una scala pura su omega produrrebbe proprio questa deriva)")
    print(f"  DEM sul supporto: p10 {args.dem_depth_p10_p90_m[0]:.2f}, "
          f"mediana {args.dem_depth_m:.2f}, p90 {args.dem_depth_p10_p90_m[1]:.2f} m")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Dispersion inversion on the resolved lobe of the backprojected support",
        "grid": manifest["grid"],
        "selection": {
            "bin_count": int(keep.sum()),
            "wavelength_bounds_m": list(args.wavelength_bounds_m),
            "minimum_power_fraction": args.min_power_fraction,
            "minimum_r_squared": args.min_r_squared,
            "minimum_smoothed_coherence": args.min_coherence,
        },
        "peak": {
            "wavelength_m": float(wavelength[peak]),
            "omega_rad_per_s": float(abs(slope[peak])),
            "period_s": float(2.0 * np.pi / abs(slope[peak])),
            "r_squared": float(r_squared[peak]),
            "smoothed_coherence": float(coherence[peak]),
        },
        "models": fits,
        "per_bin_depth_m": {
            "median": float(np.nanmedian(depths)),
            "p25": float(np.nanpercentile(depths, 25)),
            "p75": float(np.nanpercentile(depths, 75)),
            "trend_vs_log_wavelength_m": float(trend[0]),
        },
        "dem_reference": {
            "median_depth_m": args.dem_depth_m,
            "p10_p90_m": list(args.dem_depth_p10_p90_m),
            "note": "depth is -elevation on NAVD88; no tidal reduction applied",
        },
        "buoy_omega_rad_per_s": 2.0 * np.pi / args.buoy_period_s,
        "caveats": [
            "Free depth, depth-plus-current and a pure scale on the DEM depth fit "
            "within a few per cent of each other; this selection cannot separate "
            "them.",
            "A pure scale on omega produces a drift of the per-bin depth with "
            "wavelength, which is present, so a single physical depth is not "
            "established.",
        ],
    }
    out = args.outdir / "BLOCK12_DISPERSION.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nScritto {out}")

    _plot(args.outdir / "BLOCK12_DISPERSION.png", k, observed, weight,
          wavelength[keep], fits, args, phase, times, peak, slope)
    print(f"Scritto {args.outdir / 'BLOCK12_DISPERSION.png'}")


def _plot(path, k, observed, weight, lam, fits, args, phase, times, peak, slope):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "serif", "font.size": 9,
                         "xtick.direction": "in", "ytick.direction": "in",
                         "xtick.top": True, "ytick.right": True})
    figure, axes = plt.subplots(1, 2, figsize=(9.2, 3.6))
    grid = np.linspace(k.min() * 0.92, k.max() * 1.08, 200)
    ax = axes[0]
    ax.scatter(k, observed, s=8 + 34 * weight, facecolors="none",
               edgecolors="#00204d", linewidths=0.9, label="bin misurati")
    for depth, colour, style, label in (
        (args.dem_depth_m, "#000000", "--", f"dispersione a h={args.dem_depth_m:.1f} m (DEM)"),
        (fits["linear_dispersion_free_depth"]["parameters"]["depth_m"], "#bb5566",
         "-", "dispersione, h libero = "
         f"{fits['linear_dispersion_free_depth']['parameters']['depth_m']:.2f} m"),
    ):
        ax.plot(grid, np.sqrt(9.80665 * grid * np.tanh(grid * abs(depth))),
                color=colour, linestyle=style, linewidth=1.4, label=label)
    scale = fits["pure_scale_at_dem_depth"]["parameters"]["scale"]
    ax.plot(grid, scale * np.sqrt(9.80665 * grid * np.tanh(grid * args.dem_depth_m)),
            color="#7f7f7f", linestyle="-.", linewidth=1.3,
            label=f"scala pura {scale:.3f} sul DEM")
    ax.set_xlabel(r"$k$ [rad m$^{-1}$]")
    ax.set_ylabel(r"$\omega$ [rad s$^{-1}$]")
    ax.set_title("(a) relazione di dispersione misurata")
    ax.legend(frameon=False, fontsize=7, loc="upper left")

    ax = axes[1]
    series = phase[:, peak[0], peak[1]]
    order = np.argsort(times)
    ax.plot(times[order], series[order] - series[order][0], linestyle="none",
            marker="o", markersize=3.2, color="#00204d", label="fase misurata")
    span = np.linspace(times.min(), times.max(), 64)
    for omega, colour, style, label in (
        (abs(slope[peak]), "#bb5566", "-", f"SAR: {abs(slope[peak]):.4f} rad/s"),
        (2 * np.pi / args.buoy_period_s, "#000000", "--",
         f"boa NDBC: {2 * np.pi / args.buoy_period_s:.4f} rad/s"),
    ):
        ax.plot(span, np.sign(slope[peak]) * omega * (span - times.min()),
                color=colour, linestyle=style, linewidth=1.3, label=label)
    ax.set_xlabel("slow time [s]")
    ax.set_ylabel("fase non avvolta [rad]")
    ax.set_title("(b) rampa di fase al picco")
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    figure.tight_layout()
    figure.savefig(path, dpi=200)
    plt.close(figure)


if __name__ == "__main__":
    main()

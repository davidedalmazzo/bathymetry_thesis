"""Block 13 - sliding-window shoaling test on the widened backprojected support.

Why a sliding window and not one transform
------------------------------------------
Equation (2.36) of the thesis requires L <~ W << L_b. On the 3 km support the
depth runs from about 10 m to about 36 m, so a single transform over the whole
thing violates the right-hand inequality outright: every wave component is
smeared across many image wavenumbers, because its local wavelength changes by
a factor of nearly two from one end to the other. That smearing is what breaks
the one-to-one map between an image wavenumber and a wave component, and it is
the most likely reason the 1440 m support reported a wavelength belonging to
one buoy component (131 m is the 13.33 s wave at the shallow edge) while its
phase slope reported another (0.4121 rad/s is the 15.38 s wave).

A sliding window restores the separation locally: each sub-window spans a
narrow depth range, so each component sits at one wavenumber inside it.

What the test decides
---------------------
Equation (2.33) says omega is the same everywhere in a steady field, while the
wavelength responds to the seabed. So across the support:

  * omega(x) must be flat. If it drifts, either the field is not steady or the
    estimator is picking up different components in different places.
  * lambda(x) must shoal. The predicted curve for the 15.38 s component runs
    from 261 m at 36.5 m depth to 149 m at 10.1 m; for the 13.33 s component,
    from 231 m to 128 m. Which curve the data follow identifies the component.
  * h(x) from the pair must track the DEM profile, offset at worst by the
    datum. If lambda shoals but h does not track, the pairing is wrong.

The buoy spectrum at the acquisition time
-----------------------------------------
NDBC 46218, 2025-02-16 19:00 UTC, Hs 1.99 m. The swell is a broad band, not a
peak: 15.38 s carries 8.2 per cent of the variance and 13.33 s carries 8.9,
with 11.8-16.7 s all comparably energetic and every component arriving from
252-284 deg, i.e. propagating within 10 deg of our wavevector. There is
therefore no single "buoy period" to compare against, which is exactly the
component mismatch of thesis section 3.3.2. Note also that the 17.90 s of
Block 6 carries 0.3 per cent: that value corresponded to no real component,
while the 15.25 s of Block 12 sits on an energetic one.
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

# NDBC 46218 at the acquisition time: period [s], share of m0, direction of travel
BUOY_COMPONENTS = [
    (16.67, 0.015, 88.0), (15.38, 0.082, 88.0), (14.29, 0.060, 96.0),
    (13.33, 0.089, 72.0), (12.50, 0.045, 80.0), (11.76, 0.056, 104.0),
    (11.11, 0.037, 88.0), (10.53, 0.053, 96.0), (9.90, 0.079, 92.0),
]


def tukey(n: int, alpha: float = 0.2) -> np.ndarray:
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


def wavelength_at(period_s: float, depth_m: float) -> float:
    omega = 2.0 * np.pi / period_s
    k = omega**2 / GRAVITY_M_PER_S2
    for _ in range(400):
        k = omega**2 / (GRAVITY_M_PER_S2 * np.tanh(k * depth_m))
    return float(2.0 * np.pi / k)


def depth_from(wavelength_m: float, omega: float) -> float | None:
    k = 2.0 * np.pi / wavelength_m
    ratio = omega**2 / (GRAVITY_M_PER_S2 * k)
    return float(np.arctanh(ratio) / k) if 0.0 < ratio < 1.0 else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indir", type=Path,
                        default=VANDENBERG / "results" / "block13_backprojection")
    parser.add_argument("--outdir", type=Path,
                        default=VANDENBERG / "results" / "analysis_block13")
    parser.add_argument("--window-m", type=float, default=1000.0,
                        help="sub-window length along k; 1000 m is 7.6 wavelengths "
                             "at 131 m, giving one-cell dL/L of 13 per cent, and "
                             "spans only 8.8 m of depth at the 1:114 slope")
    parser.add_argument("--step-m", type=float, default=250.0)
    parser.add_argument("--dem-shallow-edge-m", type=float, default=10.11)
    parser.add_argument("--dem-gradient-m-per-m", type=float, default=8.79e-3)
    parser.add_argument("--wavelength-bounds-m", type=float, nargs=2,
                        default=[80.0, 400.0])
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((args.indir / "BLOCK12_SUBLOOK_MANIFEST.json")
                          .read_text(encoding="utf-8"))
    stack = np.load(args.indir / "BLOCK12_SUBLOOKS_complex64.npy", mmap_mode="r")
    times = np.asarray(manifest["mean_tx_time_per_look_s"], dtype=np.float64)
    spacing = float(manifest["grid"]["spacing_m"])
    look_count, rows, cols = stack.shape
    length_parallel = float(manifest["grid"]["length_parallel_m"])
    print(f"{look_count} sub-look, griglia {rows}x{cols} a {spacing} m "
          f"({length_parallel:.0f} m lungo k), span {np.ptp(times):.3f} s")

    n_window = int(round(args.window_m / spacing))
    n_step = int(round(args.step_m / spacing))
    starts = list(range(0, rows - n_window + 1, n_step))
    window = np.outer(tukey(n_window), tukey(cols))
    centred = times - times.mean()
    print(f"finestra {n_window * spacing:.0f} m, passo {n_step * spacing:.0f} m, "
          f"{len(starts)} posizioni")

    ky = 2.0 * np.pi * np.fft.fftshift(np.fft.fftfreq(cols, d=spacing))
    kx = 2.0 * np.pi * np.fft.fftshift(np.fft.fftfreq(n_window, d=spacing))
    KX, KY = np.meshgrid(kx, ky, indexing="ij")
    magnitude = np.hypot(KX, KY)
    with np.errstate(divide="ignore"):
        wavelength = np.where(magnitude > 0, 2.0 * np.pi / magnitude, np.inf)
    band = ((wavelength >= args.wavelength_bounds_m[0])
            & (wavelength <= args.wavelength_bounds_m[1]) & (KX < 0))

    print("\n  centro    h DEM   lambda    omega      T      h da (l,w)   R^2")
    print("   [m]       [m]      [m]    [rad/s]     [s]        [m]")
    records = []
    for start in starts:
        spectra = np.array([
            detrended_spectrum(np.abs(np.asarray(stack[i, start:start + n_window])) ** 2,
                               window) for i in range(look_count)])
        reference = look_count // 2
        cross = spectra * np.conj(spectra[reference])
        power = np.mean(np.abs(spectra) ** 2, axis=0)
        phase = np.unwrap(np.angle(cross), axis=0)
        slope = np.tensordot(centred, phase, axes=(0, 0)) / float(np.sum(centred**2))
        residual = phase - (phase.mean(axis=0)[None] + slope[None] * centred[:, None, None])
        total = np.sum((phase - phase.mean(axis=0)[None]) ** 2, axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            r_squared = 1.0 - np.sum(residual**2, axis=0) / total
        peak = np.unravel_index(int(np.argmax(np.where(band, power, -np.inf))),
                                power.shape)

        centre_index = start + n_window / 2.0
        offset = (centre_index - rows / 2.0) * spacing      # + verso riva
        depth_dem = args.dem_shallow_edge_m + args.dem_gradient_m_per_m * (
            length_parallel / 2.0 - offset)
        lam = float(wavelength[peak])
        omega = abs(float(slope[peak]))
        h_pair = depth_from(lam, omega)
        records.append({
            "centre_offset_m": float(offset),
            "dem_depth_m": float(depth_dem),
            "wavelength_m": lam,
            "omega_rad_per_s": omega,
            "period_s": float(2.0 * np.pi / omega),
            "depth_from_pair_m": h_pair,
            "r_squared": float(r_squared[peak]),
            "expected_wavelength_by_component_m": {
                f"{T:g}s": wavelength_at(T, depth_dem) for T, _, _ in BUOY_COMPONENTS},
        })
        print("  %+7.0f   %5.1f   %6.1f   %.4f   %6.2f     %s   %.4f" % (
            offset, depth_dem, lam, omega, 2 * np.pi / omega,
            "  ---" if h_pair is None else "%5.2f" % h_pair, r_squared[peak]))

    omegas = np.array([r["omega_rad_per_s"] for r in records])
    lams = np.array([r["wavelength_m"] for r in records])
    dems = np.array([r["dem_depth_m"] for r in records])
    print(f"\nomega: mediana {np.median(omegas):.4f} rad/s, "
          f"cv {omegas.std() / omegas.mean() * 100:.1f}%   "
          f"[deve essere costante, eq. (2.33)]")
    print(f"lambda: da {lams.max():.1f} a {lams.min():.1f} m, "
          f"escursione {(lams.max() / lams.min() - 1) * 100:.0f}%   "
          f"[deve seguire lo shoaling]")
    for T, share, _ in BUOY_COMPONENTS:
        if share < 0.05:
            continue
        predicted = np.array([wavelength_at(T, d) for d in dems])
        print(f"   componente {T:5.2f} s ({share * 100:4.1f}% di m0): "
              f"rms lambda osservata-attesa = {np.sqrt(np.mean((lams - predicted) ** 2)):6.1f} m")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Sliding-window shoaling test on the widened backprojected support",
        "grid": manifest["grid"],
        "window_m": n_window * spacing,
        "step_m": n_step * spacing,
        "one_cell_wavelength_uncertainty": float(
            np.median(lams) / (n_window * spacing)),
        "buoy_components": [
            {"period_s": T, "share_of_m0": s, "travel_direction_deg": d}
            for T, s, d in BUOY_COMPONENTS],
        "records": records,
        "omega_median_rad_per_s": float(np.median(omegas)),
        "omega_coefficient_of_variation": float(omegas.std() / omegas.mean()),
    }
    out = args.outdir / "BLOCK13_SLIDING.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nScritto {out}")
    _plot(args.outdir / "BLOCK13_SLIDING.png", records, dems, BUOY_COMPONENTS)
    print(f"Scritto {args.outdir / 'BLOCK13_SLIDING.png'}")


def _plot(path, records, dems, components):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "serif", "font.size": 9,
                         "xtick.direction": "in", "ytick.direction": "in",
                         "xtick.top": True, "ytick.right": True})
    offsets = np.array([r["centre_offset_m"] for r in records])
    lams = np.array([r["wavelength_m"] for r in records])
    omegas = np.array([r["omega_rad_per_s"] for r in records])
    figure, axes = plt.subplots(1, 3, figsize=(11.4, 3.5))

    ax = axes[0]
    for (T, share, _), colour, style in zip(
            [c for c in components if c[1] >= 0.05],
            ["#000000", "#7f7f7f", "#4477aa", "#997700"],
            ["--", "-.", ":", (0, (3, 1, 1, 1))]):
        ax.plot(offsets, [wavelength_at(T, d) for d in dems], color=colour,
                linestyle=style, linewidth=1.2, label=f"{T:.2f} s ({share*100:.0f}%)")
    ax.plot(offsets, lams, color="#bb5566", marker="o", markersize=3.5,
            linewidth=1.6, label="misurata")
    ax.set_xlabel("posizione lungo $k$ [m]  (+ verso riva)")
    ax.set_ylabel(r"$\lambda$ [m]")
    ax.set_title("(a) shoaling: quale componente")
    ax.legend(frameon=False, fontsize=6.5, loc="best")

    ax = axes[1]
    ax.plot(offsets, omegas, color="#bb5566", marker="o", markersize=3.5, linewidth=1.6)
    ax.axhline(float(np.median(omegas)), color="#7f7f7f", linestyle=":", linewidth=1.0)
    for T, share, _ in components:
        if share >= 0.08:
            ax.axhline(2 * np.pi / T, color="#000000", linestyle="--", linewidth=0.9)
            ax.annotate(f"{T:.2f} s", (offsets[0], 2 * np.pi / T), fontsize=6.5,
                        va="bottom")
    ax.set_xlabel("posizione lungo $k$ [m]")
    ax.set_ylabel(r"$\omega$ [rad s$^{-1}$]")
    ax.set_title(r"(b) $\omega$ deve essere costante")

    ax = axes[2]
    paired = [r["depth_from_pair_m"] for r in records]
    ax.plot(offsets, dems, color="#000000", linestyle="--", linewidth=1.3, label="DEM")
    ax.plot(offsets, [np.nan if p is None else p for p in paired], color="#bb5566",
            marker="o", markersize=3.5, linewidth=1.6, label=r"da $(\lambda,\omega)$")
    ax.set_xlabel("posizione lungo $k$ [m]")
    ax.set_ylabel("profondita' [m]")
    ax.set_title("(c) profilo batimetrico")
    ax.legend(frameon=False, fontsize=7)
    figure.tight_layout()
    figure.savefig(path, dpi=200)
    plt.close(figure)


if __name__ == "__main__":
    main()

"""Block 14 - is the 26 per cent wavelength deficit a nonlinear imaging signature?

Block 13 established the problem cleanly. omega is right: it is constant within
each regime (cv 1.6 and 4.3 per cent) and both values land on real NDBC
components. What is wrong is lambda, short by a constant factor 0.738 +- 0.030
across nine positions, two wave systems and a factor two in depth.

A wavelength deficit that is uniform in space but produced by imaging has to
come from the imaging operator, and the operator has exactly one strongly
nonlinear ingredient: velocity bunching, which displaces scatterers in azimuth
by beta * u_r. Three consequences are testable here, all from the sub-looks
already on disk.

1. Azimuth cut-off. The bunching exponential attenuates the image spectrum as
   exp(-k_a^2 beta^2 sigma_ur^2). Fitting that anisotropy against an isotropic
   background gives beta*sigma_ur, hence lambda_c = 2 pi beta sigma_ur and
   sigma_ur itself. This is the number that says how nonlinear the acquisition
   actually was, instead of assuming it from a hindcast.

2. Harmonic structure. A nonlinear operator applied to a monochromatic pattern
   generates energy at 2k. A bound harmonic must carry phase rate 2 omega, so
   the phase slope identifies it unambiguously and separates it from an
   independent short wave that happens to sit at 2k.

3. Anisotropy of the deficit. Bunching acts only through the azimuth component
   of the wavenumber. If it shortens the imaged wavelength, the shortening must
   be strongest for bins near the azimuth direction and vanish in range. If the
   deficit is instead isotropic, bunching is not the mechanism and the whole
   velocity-bunching family is closed.

Point 3 is the decisive one, and it is a null test: bunching predicts a
dependence, and its absence would be conclusive.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

GRAVITY_M_PER_S2 = 9.80665
GRID_BEARING_DEG = 79.8357237          # the grid u axis
AZIMUTH_BEARING_DEG = 191.45798292805307
RANGE_BEARING_DEG = 281.17862730319644
BETA_S = 79.75                          # R/V measured from the PVP ephemeris


def tukey(n: int, alpha: float = 0.2) -> np.ndarray:
    x = np.linspace(0.0, 1.0, n)
    out = np.ones(n)
    t = alpha / 2.0
    left, right = x < t, x > 1.0 - t
    out[left] = 0.5 * (1 + np.cos(np.pi * (2 * x[left] / alpha - 1)))
    out[right] = 0.5 * (1 + np.cos(np.pi * (2 * x[right] / alpha - 2 / alpha + 1)))
    return out


def detrended_spectrum(intensity, window):
    work = np.asarray(intensity, dtype=np.float64)
    work = work - work.mean()
    rows, cols = work.shape
    u = np.linspace(-1.0, 1.0, rows)
    v = np.linspace(-1.0, 1.0, cols)
    work -= (np.dot(u, work.sum(axis=1)) / (cols * np.dot(u, u)) * u)[:, None]
    work -= (np.dot(v, work.sum(axis=0)) / (rows * np.dot(v, v)) * v)[None, :]
    return np.fft.fftshift(np.fft.fft2(work * window))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indir", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--window-m", type=float, default=1500.0)
    parser.add_argument("--cutoff-band-m", type=float, nargs=2, default=[15.0, 90.0],
                        help="wavelengths used for the cut-off fit; short enough "
                             "that the swell does not contribute")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((args.indir / "BLOCK12_SUBLOOK_MANIFEST.json")
                          .read_text(encoding="utf-8"))
    stack = np.load(args.indir / "BLOCK12_SUBLOOKS_complex64.npy", mmap_mode="r")
    times = np.asarray(manifest["mean_tx_time_per_look_s"], dtype=np.float64)
    spacing = float(manifest["grid"]["spacing_m"])
    look_count, rows, cols = stack.shape

    # inshore half of the transect, where Block 13 found the 14.5 s regime
    n_window = int(round(args.window_m / spacing))
    start = rows - n_window
    window = np.outer(tukey(n_window), tukey(cols))
    spectra = np.array([
        detrended_spectrum(np.abs(np.asarray(stack[i, start:start + n_window])) ** 2,
                           window) for i in range(look_count)])
    power = np.mean(np.abs(spectra) ** 2, axis=0)

    ku = 2.0 * np.pi * np.fft.fftshift(np.fft.fftfreq(n_window, d=spacing))
    kv = 2.0 * np.pi * np.fft.fftshift(np.fft.fftfreq(cols, d=spacing))
    KU, KV = np.meshgrid(ku, kv, indexing="ij")
    magnitude = np.hypot(KU, KV)
    with np.errstate(divide="ignore"):
        wavelength = np.where(magnitude > 0, 2.0 * np.pi / magnitude, np.inf)

    # project onto the radar axes
    phi_a = np.deg2rad(AZIMUTH_BEARING_DEG - GRID_BEARING_DEG)
    phi_r = np.deg2rad(RANGE_BEARING_DEG - GRID_BEARING_DEG)
    azimuth_unit = np.array([np.cos(phi_a), np.sin(phi_a)])
    range_unit = np.array([np.cos(phi_r), np.sin(phi_r)])
    print(f"asse azimut nel piano della griglia: ({azimuth_unit[0]:+.4f}, "
          f"{azimuth_unit[1]:+.4f}); ortogonalita' con range "
          f"{float(azimuth_unit @ range_unit):+.4f}")
    k_azimuth = KU * azimuth_unit[0] + KV * azimuth_unit[1]
    k_range = KU * range_unit[0] + KV * range_unit[1]

    # ---- 1. azimuth cut-off from the spectral anisotropy -------------------
    lo, hi = args.cutoff_band_m
    fit_mask = (wavelength >= lo) & (wavelength <= hi) & (power > 0)
    design = np.column_stack((
        np.ones(int(fit_mask.sum())),
        magnitude[fit_mask],
        k_azimuth[fit_mask] ** 2,
    ))
    coefficients, *_ = np.linalg.lstsq(design, np.log(power[fit_mask]), rcond=None)
    a_squared = -coefficients[2]
    cutoff = {
        "fit_bins": int(fit_mask.sum()),
        "wavelength_band_m": [lo, hi],
        "beta_sigma_ur_m": float(np.sqrt(a_squared)) if a_squared > 0 else None,
        "azimuth_cutoff_m": float(2 * np.pi * np.sqrt(a_squared)) if a_squared > 0 else None,
        "sigma_ur_m_per_s": float(np.sqrt(a_squared) / BETA_S) if a_squared > 0 else None,
        "isotropic_slope_per_rad_per_m": float(coefficients[1]),
    }
    print("\n=== 1. taglio azimutale dalla anisotropia spettrale ===")
    if a_squared > 0:
        print(f"  beta*sigma_ur = {cutoff['beta_sigma_ur_m']:.2f} m")
        print(f"  lambda_c      = {cutoff['azimuth_cutoff_m']:.1f} m")
        print(f"  sigma_ur      = {cutoff['sigma_ur_m_per_s']:.3f} m/s   "
              f"(stima a priori dallo stato di mare: 0.25-0.33 m/s)")
    else:
        print("  nessuna attenuazione anisotropa rilevata: coefficiente di segno "
              "sbagliato, il taglio non e' misurabile su questa banda")

    # ---- 2. phase slope map, then the harmonic test ------------------------
    reference = look_count // 2
    cross = spectra * np.conj(spectra[reference])
    phase = np.unwrap(np.angle(cross), axis=0)
    centred = times - times.mean()
    slope = np.tensordot(centred, phase, axes=(0, 0)) / float(np.sum(centred**2))
    residual = phase - (phase.mean(axis=0)[None] + slope[None] * centred[:, None, None])
    total = np.sum((phase - phase.mean(axis=0)[None]) ** 2, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        r_squared = 1.0 - np.sum(residual**2, axis=0) / total

    band = (wavelength >= 80.0) & (wavelength <= 400.0) & (KU < 0)
    peak = np.unravel_index(int(np.argmax(np.where(band, power, -np.inf))), power.shape)
    k_peak = np.array([KU[peak], KV[peak]])
    omega_peak = abs(float(slope[peak]))
    print(f"\n=== 2. struttura armonica ===")
    print(f"  fondamentale: lambda {wavelength[peak]:.1f} m, "
          f"omega {omega_peak:.4f} rad/s, R2 {r_squared[peak]:.4f}")
    harmonics = []
    for order in (2, 3):
        target = order * k_peak
        distance = np.hypot(KU - target[0], KV - target[1])
        near = distance <= 1.5 * max(ku[1] - ku[0], kv[1] - kv[0])
        if not np.any(near):
            continue
        index = np.unravel_index(int(np.argmax(np.where(near, power, -np.inf))),
                                 power.shape)
        harmonics.append({
            "order": order,
            "wavelength_m": float(wavelength[index]),
            "power_relative_to_fundamental": float(power[index] / power[peak]),
            "omega_rad_per_s": abs(float(slope[index])),
            "omega_over_order_times_fundamental": float(
                abs(slope[index]) / (order * omega_peak)),
            "r_squared": float(r_squared[index]),
        })
        print(f"  ordine {order}: lambda {wavelength[index]:6.1f} m, "
              f"potenza {power[index] / power[peak] * 100:5.2f}% del fondamentale, "
              f"omega {abs(slope[index]):.4f} rad/s "
              f"(atteso {order * omega_peak:.4f} se legata), "
              f"rapporto {abs(slope[index]) / (order * omega_peak):.3f}, "
              f"R2 {r_squared[index]:.3f}")

    # ---- 3. is the deficit anisotropic? ------------------------------------
    keep = (band & (power > 0.10 * power[peak]) & (r_squared > 0.95)
            & np.isfinite(slope) & (np.abs(slope) > 1e-6))
    k_here = magnitude[keep]
    omega_here = np.abs(slope[keep])
    ratio = omega_here**2 / (GRAVITY_M_PER_S2 * k_here)
    usable = ratio < 0.999
    depth = np.full(k_here.shape, np.nan)
    depth[usable] = np.arctanh(ratio[usable]) / k_here[usable]
    angle = np.degrees(np.arctan2(np.abs(k_azimuth[keep]), np.abs(k_range[keep])))
    weight = power[keep] / power[peak]
    good = np.isfinite(depth)
    print(f"\n=== 3. il deficit dipende dall'angolo rispetto all'azimut? ===")
    print(f"  {int(good.sum())} bin, angolo dall'asse di range "
          f"{angle[good].min():.0f}-{angle[good].max():.0f} deg")
    design = np.column_stack((np.ones(int(good.sum())), angle[good]))
    w = weight[good]
    beta_fit = np.linalg.solve(design.T @ (w[:, None] * design),
                               design.T @ (w * depth[good]))
    predicted = design @ beta_fit
    scatter = float(np.sqrt(np.sum(w * (depth[good] - predicted) ** 2) / np.sum(w)))
    standard_error = scatter / np.sqrt(np.sum(w * (angle[good] - np.average(
        angle[good], weights=w)) ** 2) / np.sum(w)) / np.sqrt(max(1, good.sum() - 2))
    print(f"  h implicita = {beta_fit[0]:.2f} {beta_fit[1]:+.4f} * angolo   "
          f"(errore standard sulla pendenza {standard_error:.4f} m/deg)")
    print(f"  dispersione pesata {scatter:.2f} m")
    verdict = ("isotropo: nessuna dipendenza dall'angolo, il velocity bunching "
               "non e' il meccanismo"
               if abs(beta_fit[1]) < 2.0 * standard_error else
               "anisotropo: la profondita' implicita dipende dall'angolo, "
               "compatibile con il velocity bunching")
    print(f"  verdetto: {verdict}")
    for lo_a, hi_a in ((0, 20), (20, 40), (40, 60), (60, 90)):
        sel = good & (angle >= lo_a) & (angle < hi_a)
        if sel.sum() < 2:
            continue
        print(f"    {lo_a:2d}-{hi_a:2d} deg dall'asse di range: {int(sel.sum()):3d} bin, "
              f"h mediana {np.median(depth[sel]):5.2f} m, "
              f"lambda mediana {np.median(2 * np.pi / k_here[sel]):6.1f} m")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Nonlinearity diagnostics on the backprojected sub-looks",
        "window_m": n_window * spacing,
        "azimuth_cutoff": cutoff,
        "fundamental": {
            "wavelength_m": float(wavelength[peak]),
            "omega_rad_per_s": omega_peak,
            "r_squared": float(r_squared[peak]),
        },
        "harmonics": harmonics,
        "anisotropy": {
            "bin_count": int(good.sum()),
            "intercept_m": float(beta_fit[0]),
            "slope_m_per_deg": float(beta_fit[1]),
            "slope_standard_error_m_per_deg": float(standard_error),
            "weighted_scatter_m": scatter,
            "verdict": verdict,
        },
    }
    out = args.outdir / "BLOCK14_NONLINEARITY.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nScritto {out}")


if __name__ == "__main__":
    main()

"""Block 12b - phase slope from backprojected sub-looks.

Same estimator as Block 6, on a support that finally resolves the wave and on
a time axis that needs no inversion: each look's slow time is the mean TxTime
of the pulses summed into it.

Two things Block 6 could not do:

  * 1440 m along k instead of 540 m. Block 6's primary lobe answered with a
    single number at every wave number (its response to dispersion was 19 per
    cent of nominal), the signature of an unresolved train leaking across its
    own skirt. At 1440 m the native radial bin is 2 pi / 1440 rather than
    2 pi / 540, so omega(k) can vary across the lobe if it physically does.
  * 32 strictly disjoint looks over the full 22.541 s dwell, giving pairwise
    baselines from 0.70 s to 21.8 s with no shared aperture at all.

Everything is computed on the ground grid, so k is already in ground metres
and no slant-plane Jacobian enters.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / 'umbra/Vandenberg'
GRAVITY_M_PER_S2 = 9.80665


def tukey2d(rows: int, cols: int, alpha: float = 0.1) -> np.ndarray:
    def w(n: int) -> np.ndarray:
        x = np.linspace(0.0, 1.0, n)
        out = np.ones(n)
        t = alpha / 2.0
        left, right = x < t, x > 1.0 - t
        out[left] = 0.5 * (1 + np.cos(np.pi * (2 * x[left] / alpha - 1)))
        out[right] = 0.5 * (1 + np.cos(np.pi * (2 * x[right] / alpha - 2 / alpha + 1)))
        return out
    return np.outer(w(rows), w(cols))


def detrended_spectrum(intensity: np.ndarray, window: np.ndarray) -> np.ndarray:
    """Remove one global plane, apply the window, transform."""

    work = np.asarray(intensity, dtype=np.float64)
    rows, cols = work.shape
    u = np.linspace(-1.0, 1.0, rows)
    v = np.linspace(-1.0, 1.0, cols)
    work = work - work.mean()
    work -= (np.dot(u, work.sum(axis=1)) / (cols * np.dot(u, u)) * u)[:, None]
    work -= (np.dot(v, work.sum(axis=0)) / (rows * np.dot(v, v)) * v)[None, :]
    return np.fft.fftshift(np.fft.fft2(work * window))


def depth_from_dispersion(wavelength_m: float, omega: float) -> float | None:
    k = 2.0 * np.pi / float(wavelength_m)
    if abs(omega) >= np.sqrt(GRAVITY_M_PER_S2 * k):
        return None
    target = omega**2 / (GRAVITY_M_PER_S2 * k)
    return float(np.arctanh(target) / k) if 0.0 < target < 1.0 else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indir", type=Path,
                        default=VANDENBERG / "results" / "block12_backprojection")
    parser.add_argument("--outdir", type=Path,
                        default=VANDENBERG / "results" / "analysis_block12")
    parser.add_argument("--buoy-period-s", type=float, default=13.33333280351429)
    parser.add_argument("--wavelength-bounds-m", type=float, nargs=2,
                        default=[40.0, 500.0])
    parser.add_argument("--reference-depths-m", type=float, nargs="*",
                        default=[11.003, 16.441])
    parser.add_argument("--min-coherence", type=float, default=0.3)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((args.indir / "BLOCK12_SUBLOOK_MANIFEST.json")
                          .read_text(encoding="utf-8"))
    stack = np.load(args.indir / "BLOCK12_SUBLOOKS_complex64.npy", mmap_mode="r")
    times = np.asarray(manifest["mean_tx_time_per_look_s"], dtype=np.float64)
    spacing = float(manifest["grid"]["spacing_m"])
    look_count, rows, cols = stack.shape
    print(f"{look_count} sub-look, griglia {rows}x{cols} a {spacing} m, "
          f"slow time {times.min():.4f}-{times.max():.4f} s "
          f"(span {times.max() - times.min():.4f} s)")

    window = tukey2d(rows, cols, 0.1)
    spectra = np.empty((look_count, rows, cols), dtype=np.complex128)
    for i in range(look_count):
        spectra[i] = detrended_spectrum(np.abs(np.asarray(stack[i])) ** 2, window)

    kx = 2.0 * np.pi * np.fft.fftshift(np.fft.fftfreq(rows, d=spacing))
    ky = 2.0 * np.pi * np.fft.fftshift(np.fft.fftfreq(cols, d=spacing))
    KX, KY = np.meshgrid(kx, ky, indexing="ij")
    magnitude = np.hypot(KX, KY)
    with np.errstate(divide="ignore"):
        wavelength = np.where(magnitude > 0, 2.0 * np.pi / magnitude, np.inf)
    band = ((wavelength >= args.wavelength_bounds_m[0])
            & (wavelength <= args.wavelength_bounds_m[1]))

    reference = look_count // 2
    cross = spectra * np.conj(spectra[reference])
    power = np.mean(np.abs(spectra) ** 2, axis=0)

    # coherence between the two extreme looks: the harshest available baseline
    a, b = spectra[0], spectra[-1]
    coherence = np.abs(a * np.conj(b)) / np.sqrt(
        np.abs(a) ** 2 * np.abs(b) ** 2 + 1e-30)

    phase = np.angle(cross)
    order = np.argsort(times)
    phase = np.unwrap(phase[order], axis=0)
    t = times[order]

    tc = t - t.mean()
    slope = np.tensordot(tc, phase, axes=(0, 0)) / float(np.sum(tc**2))
    fitted = phase.mean(axis=0)[None] + slope[None] * tc[:, None, None]
    residual = phase - fitted
    total = np.sum((phase - phase.mean(axis=0)[None]) ** 2, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        r_squared = 1.0 - np.sum(residual**2, axis=0) / total
    rmse = np.sqrt(np.mean(residual**2, axis=0))

    valid = band & (coherence >= args.min_coherence) & np.isfinite(slope)
    if not np.any(valid):
        raise SystemExit("Nessun bin supera i criteri; rivedere soglie o supporto.")
    masked_power = np.where(valid, power, -np.inf)
    peak = np.unravel_index(int(np.argmax(masked_power)), power.shape)
    omega = abs(float(slope[peak]))
    lam = float(wavelength[peak])
    omega_buoy = 2.0 * np.pi / float(args.buoy_period_s)

    print(f"\npicco: lambda = {lam:.2f} m, "
          f"angolo da k_parallelo = {np.degrees(np.arctan2(KY[peak], KX[peak])):.2f} deg")
    print(f"  omega = {omega:.4f} rad/s   T = {2 * np.pi / omega:.3f} s   "
          f"R^2 = {r_squared[peak]:.4f}   rmse = {rmse[peak]:.4f} rad")
    print(f"  boa  = {omega_buoy:.4f} rad/s   T = {args.buoy_period_s:.3f} s   "
          f"rapporto = {omega / omega_buoy:.4f}")
    depth = depth_from_dispersion(lam, omega)
    print(f"  h implicita = {'-' if depth is None else round(depth, 2)} m")
    for h in args.reference_depths_m:
        k = 2.0 * np.pi / lam
        w = np.sqrt(GRAVITY_M_PER_S2 * k * np.tanh(k * h))
        print(f"  dispersione a h={h:g} m: omega={w:.4f} rad/s, T={2 * np.pi / w:.3f} s")

    # dispersion response across the resolved lobe: Block 6 measured 0.19
    lobe = valid & (power > 0.05 * power[peak])
    responses = {}
    for h in args.reference_depths_m:
        k = magnitude[lobe]
        wd = np.sqrt(GRAVITY_M_PER_S2 * k * np.tanh(k * h))
        wo = np.abs(slope[lobe])
        design = np.column_stack((np.ones(wd.size), wd))
        beta = np.linalg.lstsq(design, wo, rcond=None)[0]
        responses[f"h_{h:g}_m"] = {
            "intercept_rad_per_s": float(beta[0]),
            "dispersion_response": float(beta[1]),
            "correlation": float(np.corrcoef(wd, wo)[0, 1]),
        }
        print(f"  risposta alla dispersione (h={h:g} m, {int(lobe.sum())} bin): "
              f"omega_obs = {beta[0]:+.4f} + {beta[1]:.4f}*omega_disp, "
              f"corr {np.corrcoef(wd, wo)[0, 1]:+.3f}   [Block 6 dava 0.19]")

    # pairwise omega against baseline, all disjoint by construction
    pairs = []
    for i in range(look_count):
        for j in range(i + 1, look_count):
            dt = float(t[j] - t[i])
            pairs.append({"i": i, "j": j, "delta_t_s": dt,
                          "omega_rad_per_s": abs(float(
                              (phase[j][peak] - phase[i][peak]) / dt))})
    dts = np.array([p["delta_t_s"] for p in pairs])
    oms = np.array([p["omega_rad_per_s"] for p in pairs])
    w = dts**2
    design = np.column_stack((np.ones(dts.size), dts))
    beta = np.linalg.solve(design.T @ (w[:, None] * design), design.T @ (w * oms))
    print(f"\ncoppie {len(pairs)} (tutte disgiunte), dt {dts.min():.2f}-{dts.max():.2f} s")
    print(f"  omega mediana {np.median(oms):.4f} rad/s, "
          f"pendenza vs dt {beta[1]:+.5f} rad/s per s")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Phase slope from backprojected disjoint sub-looks on a ground grid",
        "source_manifest": manifest,
        "grid": manifest["grid"],
        "look_times_s": t.tolist(),
        "reference_look_index": int(reference),
        "criteria": {
            "wavelength_bounds_m": list(args.wavelength_bounds_m),
            "minimum_end_to_end_coherence": float(args.min_coherence),
        },
        "peak": {
            "index": [int(peak[0]), int(peak[1])],
            "wavelength_m": lam,
            "k_parallel_rad_per_m": float(KX[peak]),
            "k_perpendicular_rad_per_m": float(KY[peak]),
            "omega_rad_per_s": omega,
            "period_s": 2.0 * np.pi / omega,
            "r_squared": float(r_squared[peak]),
            "residual_rmse_rad": float(rmse[peak]),
            "end_to_end_coherence": float(coherence[peak]),
            "depth_from_dispersion_m": depth,
            "omega_buoy_rad_per_s": omega_buoy,
            "ratio_to_buoy": omega / omega_buoy,
        },
        "dispersion_response": responses,
        "pairwise": {
            "count": len(pairs),
            "median_omega_rad_per_s": float(np.median(oms)),
            "slope_vs_delta_t_rad_per_s_per_s": float(beta[1]),
            "delta_t_range_s": [float(dts.min()), float(dts.max())],
        },
    }
    out = args.outdir / "BLOCK12_PHASE_SLOPE.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    np.savez_compressed(
        args.outdir / "BLOCK12_PHASE_SLOPE_MAP.npz",
        slope_rad_per_s=slope, r_squared=r_squared, residual_rmse_rad=rmse,
        wavelength_m=wavelength, k_parallel=KX, k_perpendicular=KY,
        mean_power=power, end_to_end_coherence=coherence, valid_mask=valid,
        unwrapped_phase_rad=phase, look_times_s=t,
    )
    print(f"\nScritto {out}")


if __name__ == "__main__":
    main()

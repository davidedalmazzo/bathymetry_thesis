"""Block 11b - is the phase rate independent of the baseline that measures it?

Block 11a measured the effective slow time of every sub-look from its own
azimuth power spectrum and found the geometric labels essentially right: the
lever arm shrinks by 1.7 percent, not the 25 percent the omega deficit needs.
The time axis is therefore not the explanation, and a different property of the
observable has to be tested.

The eleven Block 4 looks are 80 percent overlapped in Doppler.  Two overlapping
sub-looks share most of their illumination, so their cross-spectrum is

    <A_i A_j*> = double integral w_i(t) w_j(t') rho(t - t') exp(-i omega (t - t')) dt dt'

where rho is the scene coherence in slow time.  When rho is broad compared with
the look separation this factorises and the phase is exactly
-omega (t_i - t_j), the centroid rule Block 4 assumes.  When rho is narrow the
integrand concentrates on t = t', where the phase factor is unity, and the
measured phase is pulled toward zero: omega comes out *low*, and by an amount
that grows with the overlap.  The measured coherence does fall from 0.97 between
adjacent looks to 0.56 between the disjoint anchors, so this regime is not
hypothetical.

The test is free and it separates the two cases cleanly:

  * a genuine wave phase rate gives the same omega from every pair, disjoint or
    not, and no trend against the temporal baseline;
  * an overlap-borne contamination gives an omega that rises toward the truth as
    the shared aperture shrinks.

Everything here is recomputed from the stored Block 6 unwrapped phase stack.
No image is re-read.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"


def overlap_fraction(band_a: tuple[int, int], band_b: tuple[int, int]) -> float:
    lo = max(band_a[0], band_b[0])
    hi = min(band_a[1], band_b[1])
    shared = max(0, hi - lo)
    width = min(band_a[1] - band_a[0], band_b[1] - band_b[0])
    return shared / width


def weighted_line(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> dict[str, float]:
    """Weighted least squares y = a + b x with a naive standard error on b."""

    design = np.column_stack((np.ones(x.size), x))
    weights = np.diag(w)
    normal = design.T @ weights @ design
    beta = np.linalg.solve(normal, design.T @ weights @ y)
    residual = y - design @ beta
    dof = max(1, x.size - 2)
    scale = float(residual @ (weights @ residual) / dof)
    covariance = scale * np.linalg.inv(normal)
    return {
        "intercept": float(beta[0]),
        "slope": float(beta[1]),
        "slope_standard_error_naive": float(np.sqrt(max(0.0, covariance[1, 1]))),
        "residual_rms": float(np.sqrt(np.mean(residual**2))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--block6-npz", type=Path,
                        default=VANDENBERG / "results" / "analysis_block6"
                        / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.npz")
    parser.add_argument("--block6-summary", type=Path,
                        default=VANDENBERG / "results" / "analysis_block6"
                        / "BLOCK6_PHASE_SLOPE_SUMMARY.json")
    parser.add_argument("--manifest", type=Path,
                        default=VANDENBERG / "results" / "block4_sliding_complex"
                        / "BLOCK4_SLIDING_MANIFEST.json")
    parser.add_argument("--block11-json", type=Path,
                        default=VANDENBERG / "results" / "analysis_block11"
                        / "BLOCK11_ENERGY_CENTROID.json")
    parser.add_argument("--outdir", type=Path,
                        default=VANDENBERG / "results" / "analysis_block11")
    parser.add_argument("--roi", default="nearshore")
    parser.add_argument("--buoy-period-s", type=float, default=13.33333280351429)
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    summary6 = json.loads(args.block6_summary.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    block11 = json.loads(args.block11_json.read_text(encoding="utf-8"))

    entries = sorted(manifest["outputs"][args.roi],
                     key=lambda e: int(e["chronological_index"]))
    bands = [(int(e["band"]["start_inclusive"]), int(e["band"]["stop_exclusive"]))
             for e in entries]
    anchors = set(manifest["independent_nonoverlap_set"]["chronological_sliding_indices"])

    centroids = {c["chronological_index"]: c
                 for c in block11["rois"][args.roi]["sub_look_centroids"]}
    time_energy = np.array([centroids[i + 1]["t_energy_centroid_s"]
                            for i in range(len(entries))])

    with np.load(args.block6_npz, allow_pickle=True) as z:
        phase = z["unwrapped_phase_relative_reference_rad"]
        time_geometric = z["time_s"]
        wavelength = z["wavelength_m"]
        angle_from_range = z["angle_from_range_deg"]
        primary_lobe = z["primary_lobe_mask"]

    row, col = (int(v) for v in summary6["frozen_peak_reproduction"]["crop_index_row_col"])
    omega_buoy = 2.0 * np.pi / float(args.buoy_period_s)
    look_count = phase.shape[0]

    for label, times in (("geometrici", time_geometric), ("energetici", time_energy)):
        print(f"tempi {label}: span {times.max() - times.min():.4f} s")

    pairs: list[dict[str, Any]] = []
    series = phase[:, row, col]
    lobe_series = phase[:, primary_lobe]
    for i in range(look_count):
        for j in range(i + 1, look_count):
            dt_geometric = float(time_geometric[j] - time_geometric[i])
            dt_energy = float(time_energy[j] - time_energy[i])
            delta_phase = float(series[j] - series[i])
            lobe_delta = lobe_series[j] - lobe_series[i]
            pairs.append({
                "look_early": i + 1,
                "look_late": j + 1,
                "separation_index": j - i,
                "delta_t_geometric_s": dt_geometric,
                "delta_t_energy_s": dt_energy,
                "doppler_overlap_fraction": overlap_fraction(bands[i], bands[j]),
                "both_independent_anchors": bool({i + 1, j + 1} <= anchors),
                "delta_phase_rad": delta_phase,
                "omega_peak_rad_per_s": abs(delta_phase / dt_energy),
                "omega_lobe_median_rad_per_s": float(
                    np.median(np.abs(lobe_delta / dt_energy))
                ),
            })

    dt = np.array([p["delta_t_energy_s"] for p in pairs])
    overlap = np.array([p["doppler_overlap_fraction"] for p in pairs])
    omega = np.array([p["omega_peak_rad_per_s"] for p in pairs])
    # A pair's phase-difference noise scales like 1/dt, so weight by dt^2.
    weight = dt**2

    versus_dt = weighted_line(dt, omega, weight)
    versus_overlap = weighted_line(overlap, omega, weight)

    disjoint = overlap <= 0.0
    print(f"\ncoppie totali {len(pairs)}, disgiunte {int(np.count_nonzero(disjoint))}")
    print(f"omega su tutte le coppie   : mediana {np.median(omega):.4f} rad/s "
          f"[{omega.min():.4f}, {omega.max():.4f}]")
    if np.any(disjoint):
        print(f"omega sulle coppie disgiunte: mediana {np.median(omega[disjoint]):.4f} rad/s "
              f"[{omega[disjoint].min():.4f}, {omega[disjoint].max():.4f}]")
    print(f"omega dalla boa            : {omega_buoy:.4f} rad/s")
    print(f"\nregressione omega vs delta t : pendenza "
          f"{versus_dt['slope']:+.5f} +/- {versus_dt['slope_standard_error_naive']:.5f} "
          f"rad/s per s   (intercetta {versus_dt['intercept']:.4f})")
    print(f"regressione omega vs overlap : pendenza "
          f"{versus_overlap['slope']:+.5f} +/- "
          f"{versus_overlap['slope_standard_error_naive']:.5f} rad/s per unita "
          f"(intercetta a overlap zero {versus_overlap['intercept']:.4f})")

    by_separation = {}
    for step in range(1, look_count):
        sel = np.array([p["separation_index"] == step for p in pairs])
        by_separation[step] = {
            "pair_count": int(np.count_nonzero(sel)),
            "mean_delta_t_s": float(np.mean(dt[sel])),
            "mean_overlap_fraction": float(np.mean(overlap[sel])),
            "median_omega_peak_rad_per_s": float(np.median(omega[sel])),
            "median_omega_lobe_rad_per_s": float(np.median(
                [p["omega_lobe_median_rad_per_s"] for p, s in zip(pairs, sel) if s]
            )),
        }
    print("\n passo  coppie  dt medio [s]  overlap  omega picco  omega lobo")
    for step, item in by_separation.items():
        print(f"  {step:3d}   {item['pair_count']:5d}   {item['mean_delta_t_s']:10.4f}"
              f"   {item['mean_overlap_fraction']:6.3f}"
              f"   {item['median_omega_peak_rad_per_s']:10.4f}"
              f"   {item['median_omega_lobe_rad_per_s']:9.4f}")

    verdict = (
        "flat: omega does not depend on the baseline, so the deficit is a genuine "
        "phase rate and not an overlap artefact"
        if abs(versus_overlap["slope"]) < 3.0 * versus_overlap["slope_standard_error_naive"]
        else "trending: omega depends on the shared aperture, consistent with an "
             "overlap-borne contamination"
    )
    print(f"\nverdetto: {verdict}")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Pairwise phase rates recomputed from the stored Block 6 phase stack",
        "frozen_peak": {
            "crop_index_row_col": [row, col],
            "wavelength_m": float(wavelength[row, col]),
            "angle_from_range_deg": float(angle_from_range[row, col]),
        },
        "buoy_omega_rad_per_s": omega_buoy,
        "pairs": pairs,
        "by_separation_index": by_separation,
        "regression_omega_vs_delta_t": versus_dt,
        "regression_omega_vs_overlap_fraction": versus_overlap,
        "disjoint_pairs": {
            "count": int(np.count_nonzero(disjoint)),
            "median_omega_rad_per_s": (
                float(np.median(omega[disjoint])) if np.any(disjoint) else None
            ),
        },
        "verdict": verdict,
        "caveats": [
            "The 55 pairs are built from 11 heavily overlapping looks, so they are "
            "far from independent; the quoted standard errors are naive.",
            "Only three looks are strictly disjoint, giving three disjoint pairs.",
        ],
    }
    out = args.outdir / "BLOCK11_PAIRWISE_OMEGA.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nScritto {out}")

    if not args.no_plot:
        _plot(args.outdir / "BLOCK11_PAIRWISE_OMEGA.png", dt, overlap, omega,
              disjoint, omega_buoy, versus_overlap)
        print(f"Scritto {args.outdir / 'BLOCK11_PAIRWISE_OMEGA.png'}")


def _plot(path, dt, overlap, omega, disjoint, omega_buoy, fit) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif", "font.size": 9,
        "xtick.direction": "in", "ytick.direction": "in",
        "xtick.top": True, "ytick.right": True,
    })
    figure, axes = plt.subplots(1, 2, figsize=(8.2, 3.3))
    for ax, x, xlabel, title in (
        (axes[0], dt, r"baseline temporale $\Delta t$ [s]", "(a) rispetto al baseline"),
        (axes[1], overlap, "frazione di apertura condivisa", "(b) rispetto alla sovrapposizione"),
    ):
        ax.plot(x[~disjoint], omega[~disjoint], linestyle="none", marker="o",
                markersize=3.5, markerfacecolor="none", color="#00204d",
                label="coppie sovrapposte")
        ax.plot(x[disjoint], omega[disjoint], linestyle="none", marker="D",
                markersize=5.0, color="#bb5566", label="coppie disgiunte")
        ax.axhline(omega_buoy, color="#000000", linestyle="--", linewidth=1.0,
                   label=r"$\omega$ dalla boa NDBC")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(r"$\omega$ dalla coppia [rad s$^{-1}$]")
        ax.set_title(title)
    grid = np.linspace(overlap.min(), overlap.max(), 32)
    axes[1].plot(grid, fit["intercept"] + fit["slope"] * grid, color="#7f7f7f",
                 linestyle="-.", linewidth=1.2, label="regressione pesata")
    axes[0].legend(frameon=False, fontsize=7, loc="lower right")
    axes[1].legend(frameon=False, fontsize=7, loc="lower right")
    figure.tight_layout()
    figure.savefig(path, dpi=200)
    plt.close(figure)


if __name__ == "__main__":
    main()

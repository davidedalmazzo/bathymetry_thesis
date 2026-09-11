"""Block 11 - does the azimuth weighting shrink the sub-look time baseline?

Blocks 3/4 label every sub-look with the *geometric* centre of its Doppler
band, mapped to slow time through the CPHD PVP inversion.  That label is exact
only for a flat azimuth spectral density.  The SICD declares
``Grid.Col.WgtType = SVA`` without ``WgtFunct`` samples, the two-way antenna
pattern tapers the illumination, and Block 4 multiplies a Tukey(0.25) inside
each band.  Under any weighting peaked at the centre of the processed aperture
the power-weighted centroid of a band is pulled inward, the lever arm of the
phase-versus-time regression shrinks, and

    omega_estimated = omega_true * shrink,      shrink <= 1,

independently of wave number, because it is a rescaling of the time axis.

The sign is a prediction, not a fit: a centre-peaked weighting can only shrink
the baseline, so omega can only come out *low*.  Block 6 measures
``-0.35097 rad/s`` against ``-0.47136 rad/s`` from the NDBC 46218 dominant
period of 13.33 s, i.e. a required shrink of 0.7446.  Block 9's synthetic
surrogate could not have detected this: it builds the aperture from a
unit-modulus random carrier, so its azimuth spectrum is flat by construction
and its shrink is identically one.

This script measures the shrink from the stored sub-looks and refits Block 6.
It never re-reads the SICD image and never opens the CPHD signal block.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from umbra_sar.aperture_weighting import (  # noqa: E402
    SicdScalars,
    azimuth_power_profile,
    band_energy_centroid,
    deweighted_band_profile,
    energy_normalized,
    load_kcol_time_table,
    shrink_factor,
    tukey_window,
)

ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"
GRAVITY_M_PER_S2 = 9.80665


# --------------------------------------------------------------------------


def linear_dispersion_omega(wavelength_m: float, depth_m: float) -> float:
    k = 2.0 * np.pi / float(wavelength_m)
    return float(np.sqrt(GRAVITY_M_PER_S2 * k * np.tanh(k * float(depth_m))))


def depth_from_dispersion(wavelength_m: float, omega_rad_per_s: float) -> float | None:
    """Invert omega^2 = g k tanh(k h) for h; None when omega is unreachable."""

    k = 2.0 * np.pi / float(wavelength_m)
    omega = abs(float(omega_rad_per_s))
    deep_water_limit = np.sqrt(GRAVITY_M_PER_S2 * k)
    if omega >= deep_water_limit:
        return None
    target = omega**2 / (GRAVITY_M_PER_S2 * k)
    if not 0.0 < target < 1.0:
        return None
    return float(np.arctanh(target) / k)


def ols_slope_map(
    time_s: np.ndarray, phase_stack: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised OLS slope (with intercept) of phase against time, per bin."""

    t = np.asarray(time_s, dtype=np.float64)
    phase = np.asarray(phase_stack, dtype=np.float64)
    if phase.shape[0] != t.size:
        raise ValueError("phase stack and time axis disagree on look count")
    tc = t - t.mean()
    denominator = float(np.sum(tc**2))
    slope = np.tensordot(tc, phase, axes=(0, 0)) / denominator
    intercept = phase.mean(axis=0) - slope * t.mean()
    residual = phase - (intercept[None, :, :] + slope[None, :, :] * t[:, None, None])
    total = np.sum((phase - phase.mean(axis=0)[None]) ** 2, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        r_squared = 1.0 - np.sum(residual**2, axis=0) / total
    return slope, r_squared


# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=VANDENBERG / "results" / "block4_sliding_complex"
                        / "BLOCK4_SLIDING_MANIFEST.json")
    parser.add_argument("--sicd-json", type=Path,
                        default=VANDENBERG / "metadata" / "SICD_METADATA.json")
    parser.add_argument("--cphd", type=Path,
                        default=VANDENBERG / "2025-02-16-18-55-44_UMBRA-10_CPHD.cphd")
    parser.add_argument("--cphd-json", type=Path,
                        default=VANDENBERG / "metadata" / "CPHD_METADATA.json")
    parser.add_argument("--block6-npz", type=Path,
                        default=VANDENBERG / "results" / "analysis_block6"
                        / "BLOCK6_NEARSHORE_PHASE_SLOPE_MAP.npz")
    parser.add_argument("--block6-summary", type=Path,
                        default=VANDENBERG / "results" / "analysis_block6"
                        / "BLOCK6_PHASE_SLOPE_SUMMARY.json")
    parser.add_argument("--outdir", type=Path,
                        default=VANDENBERG / "results" / "analysis_block11")
    parser.add_argument("--roi", default="nearshore",
                        help="manifest ROI key to analyse")
    parser.add_argument("--control-roi", default="land_control",
                        help="second ROI measured as a scene-independence control")
    parser.add_argument("--window-alpha", type=float, default=0.25)
    parser.add_argument("--buoy-period-s", type=float, default=13.33333280351429,
                        help="NDBC 46218 dominant period; omega is depth invariant")
    parser.add_argument("--reference-depths-m", type=float, nargs="*",
                        default=[11.003, 13.1, 16.441],
                        help="Block 7 median depths: historic ROI, then all-water supports")
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    sicd = SicdScalars.from_json(args.sicd_json)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    summary6 = json.loads(args.block6_summary.read_text(encoding="utf-8"))

    print("Ricostruzione della mappatura k_col -> slow time dal blocco PVP del CPHD ...")
    table = load_kcol_time_table(args.cphd, args.cphd_json, sicd)
    checks = table.validate_against_sicd(sicd)
    print(f"  k_row(SCP) = {checks['interpolated_k_row_at_scp_time_per_m']:.11f} /m")
    print(f"  k_col(SCP) = {checks['interpolated_k_col_at_scp_time_per_m']:.3e} /m")

    full_k_axis = np.fft.fftshift(np.fft.fftfreq(sicd.num_cols, d=sicd.col_ss_m))

    results: dict[str, Any] = {}
    for roi in [args.roi, args.control_roi]:
        entries = manifest["outputs"].get(roi)
        if entries is None:
            print(f"ROI {roi!r} assente dal manifest; saltata.")
            continue
        print(f"\nROI {roi}: {len(entries)} sub-look")
        window = energy_normalized(tukey_window(int(entries[0]["band"]["width_bins"]),
                                                args.window_alpha))
        centroids: list[dict[str, Any]] = []
        deweighted_k: list[np.ndarray] = []
        deweighted_p: list[np.ndarray] = []
        for entry in entries:
            path = Path(str(entry["path"]).replace("\\", "/"))
            if not path.exists():
                path = _relocate(path, args.manifest)
            image = np.load(path, mmap_mode="r")
            k_axis, power = azimuth_power_profile(
                image, col_ss_m=sicd.col_ss_m, col_sgn=sicd.col_sgn
            )
            band = entry["band"]
            k_low = float(full_k_axis[int(band["start_inclusive"])])
            k_high = float(full_k_axis[int(band["stop_exclusive"]) - 1])
            k_bar, samples, leakage = band_energy_centroid(
                k_axis, power, k_low_per_m=k_low, k_high_per_m=k_high
            )
            k_geometric = 0.5 * (k_low + k_high)
            t_energy = float(table.time_for_k(k_bar)[0])
            t_geometric = float(entry["effective_early_center_late_s"][1])
            centroids.append({
                "chronological_index": int(entry["chronological_index"]),
                "band_start_bin": int(band["start_inclusive"]),
                "band_stop_bin": int(band["stop_exclusive"]),
                "k_low_per_m": k_low,
                "k_high_per_m": k_high,
                "k_geometric_center_per_m": k_geometric,
                "k_energy_centroid_per_m": k_bar,
                "k_centroid_minus_geometric_per_m": k_bar - k_geometric,
                "t_geometric_center_s": t_geometric,
                "t_energy_centroid_s": t_energy,
                "t_energy_minus_geometric_s": t_energy - t_geometric,
                "in_band_spectral_samples": samples,
                "power_fraction_outside_band": leakage,
                "source_path": str(path),
            })
            kd, pd_ = deweighted_band_profile(
                k_axis, power, k_low_per_m=k_low, k_high_per_m=k_high,
                band_window=window,
            )
            deweighted_k.append(kd)
            deweighted_p.append(pd_)
            print(f"  look {entry['chronological_index']:2d}  "
                  f"t_geom={t_geometric:7.4f} s  t_energia={t_energy:7.4f} s  "
                  f"delta={t_energy - t_geometric:+7.4f} s  "
                  f"fuori banda={leakage * 100:5.2f}%")

        t_geom = np.array([c["t_geometric_center_s"] for c in centroids])
        t_energy = np.array([c["t_energy_centroid_s"] for c in centroids])
        stats = shrink_factor(t_geom, t_energy)
        print(f"  shrink = {stats['shrink']:.4f}   "
              f"span {stats['geometric_span_s']:.4f} s -> {stats['energy_span_s']:.4f} s   "
              f"residuo rms {stats['residual_rms_s'] * 1e3:.2f} ms")

        weighting = _stitch_weighting(deweighted_k, deweighted_p, table)
        results[roi] = {
            "sub_look_centroids": centroids,
            "shrink_statistics": stats,
            "reconstructed_aperture_weighting": weighting,
        }

    primary = results[args.roi]
    shrink = float(primary["shrink_statistics"]["shrink"])

    # ---- Test B: refit Block 6 with the measured times --------------------
    print("\nRifit della mappa di pendenza di fase di Block 6 sui tempi energetici ...")
    with np.load(args.block6_npz, allow_pickle=True) as z:
        phase = z["unwrapped_phase_relative_reference_rad"]
        time_stored = z["time_s"]
        wavelength = z["wavelength_m"]
        angle_from_range = z["angle_from_range_deg"]
        slope_stored = z["slope_rad_per_s"]
        high_quality = z["high_quality_mask"]
        primary_lobe = z["primary_lobe_mask"]

    order = np.argsort([c["chronological_index"] for c in primary["sub_look_centroids"]])
    t_new = np.array([primary["sub_look_centroids"][i]["t_energy_centroid_s"] for i in order])
    t_old = np.array([primary["sub_look_centroids"][i]["t_geometric_center_s"] for i in order])
    if not np.allclose(t_old, time_stored, atol=1e-9):
        raise SystemExit(
            "I tempi del manifest non coincidono con time_s dell'npz di Block 6; "
            "il rifit sarebbe applicato a una serie diversa."
        )

    slope_refit, r2_refit = ols_slope_map(t_new, phase)
    slope_check, _ = ols_slope_map(t_old, phase)
    reproduction_error = float(np.nanmax(np.abs(slope_check - slope_stored)))
    print(f"  riproduzione della pendenza originale: max|delta| = {reproduction_error:.3e} rad/s")

    peak_row, peak_col = (int(v) for v in summary6["frozen_peak_reproduction"]["crop_index_row_col"])
    lam_peak = float(wavelength[peak_row, peak_col])
    omega_old = abs(float(slope_stored[peak_row, peak_col]))
    omega_new = abs(float(slope_refit[peak_row, peak_col]))
    omega_buoy = 2.0 * np.pi / float(args.buoy_period_s)

    targets = {
        "ndbc_46218_dominant_period": {
            "period_s": float(args.buoy_period_s),
            "omega_rad_per_s": omega_buoy,
            "required_shrink": omega_old / omega_buoy,
            "note": "omega is invariant under shoaling, so this target needs no depth",
        }
    }
    for depth in args.reference_depths_m:
        omega_h = linear_dispersion_omega(lam_peak, depth)
        targets[f"linear_dispersion_h_{depth:g}_m"] = {
            "depth_m": float(depth),
            "omega_rad_per_s": omega_h,
            "period_s": 2.0 * np.pi / omega_h,
            "required_shrink": omega_old / omega_h,
        }

    peak = {
        "crop_index_row_col": [peak_row, peak_col],
        "wavelength_m": lam_peak,
        "angle_from_range_deg": float(angle_from_range[peak_row, peak_col]),
        "omega_geometric_times_rad_per_s": omega_old,
        "period_geometric_times_s": 2.0 * np.pi / omega_old,
        "omega_energy_times_rad_per_s": omega_new,
        "period_energy_times_s": 2.0 * np.pi / omega_new,
        "r_squared_energy_times": float(r2_refit[peak_row, peak_col]),
        "depth_from_geometric_times_m": depth_from_dispersion(lam_peak, omega_old),
        "depth_from_energy_times_m": depth_from_dispersion(lam_peak, omega_new),
        "targets": targets,
    }

    lobe = primary_lobe & np.isfinite(slope_refit)
    lobe_stats = {
        "bin_count": int(np.count_nonzero(lobe)),
        "median_omega_geometric_rad_per_s": float(np.median(np.abs(slope_stored[lobe]))),
        "median_omega_energy_rad_per_s": float(np.median(np.abs(slope_refit[lobe]))),
        "median_period_energy_s": float(2.0 * np.pi / np.median(np.abs(slope_refit[lobe]))),
        "median_r_squared_energy": float(np.median(r2_refit[lobe])),
        "wavelength_range_m": [float(np.min(wavelength[lobe])), float(np.max(wavelength[lobe]))],
    }
    hq = high_quality & np.isfinite(slope_refit)
    ratio = np.abs(slope_refit[hq]) / np.abs(slope_stored[hq])
    scale_invariance = {
        "high_quality_bin_count": int(np.count_nonzero(hq)),
        "omega_ratio_min": float(np.min(ratio)),
        "omega_ratio_median": float(np.median(ratio)),
        "omega_ratio_max": float(np.max(ratio)),
        "note": (
            "A pure time-axis rescaling multiplies every bin by 1/shrink; a spread "
            "here would mean the refit is not a rescaling."
        ),
    }

    print(f"  picco congelato ({peak_row},{peak_col}), lambda = {lam_peak:.2f} m")
    print(f"    omega  {omega_old:.4f} -> {omega_new:.4f} rad/s")
    print(f"    T      {2 * np.pi / omega_old:.3f} -> {2 * np.pi / omega_new:.3f} s   "
          f"(boa {args.buoy_period_s:.2f} s)")
    print(f"    shrink misurato {shrink:.4f}   richiesto dalla boa "
          f"{targets['ndbc_46218_dominant_period']['required_shrink']:.4f}")
    dh_old = peak["depth_from_geometric_times_m"]
    dh_new = peak["depth_from_energy_times_m"]
    print(f"    h      {dh_old if dh_old is None else round(dh_old, 2)} -> "
          f"{dh_new if dh_new is None else round(dh_new, 2)} m")

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "Effective sub-look slow time from the measured azimuth power spectrum; "
            "SICD image not re-read, CPHD signal block not opened."
        ),
        "hypothesis": (
            "A centre-peaked azimuth weighting pulls each band's power centroid "
            "inward, shrinking the regression lever arm and biasing omega low by a "
            "wave-number independent factor."
        ),
        "sicd_scalars": sicd.to_dict(),
        "cphd_mapping_checks": checks,
        "window": {"kind": "tukey", "alpha": args.window_alpha, "normalization": "energy"},
        "rois": results,
        "block6_refit": {
            "geometric_times_s": t_old.tolist(),
            "energy_times_s": t_new.tolist(),
            "stored_slope_reproduction_max_abs_error_rad_per_s": reproduction_error,
            "frozen_peak": peak,
            "primary_lobe": lobe_stats,
            "scale_invariance": scale_invariance,
        },
        "caveats": [
            "The measured band power is (scene azimuth spectrum) x (aperture "
            "weighting); speckle makes the scene factor white in expectation, so "
            "the estimate is unbiased only to that approximation.",
            "The land control ROI is reported so a scene-dependent shrink can be "
            "distinguished from an instrument-borne one.",
            "This measures the shrink; it does not by itself prove the shrink is "
            "the whole of the omega deficit. The sub-look width sweep is the "
            "independent falsification test.",
        ],
    }
    out_json = args.outdir / "BLOCK11_ENERGY_CENTROID.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nScritto {out_json}")

    _write_csv(args.outdir / "BLOCK11_SUBLOOK_TIMES.csv", primary["sub_look_centroids"])
    if not args.no_plot:
        _plot(args.outdir / "BLOCK11_ENERGY_CENTROID.png", results, args.roi,
              t_old, t_new, phase, peak_row, peak_col, shrink, omega_buoy)
        print(f"Scritto {args.outdir / 'BLOCK11_ENERGY_CENTROID.png'}")


# --------------------------------------------------------------------------


def _relocate(path: Path, manifest_path: Path) -> Path:
    """Map a Windows path recorded in the manifest onto the current mount."""

    candidate = manifest_path.parent / path.name
    if candidate.exists():
        return candidate
    for parent in manifest_path.parents:
        guess = parent / "results" / path.parent.name / path.name
        if guess.exists():
            return guess
    raise FileNotFoundError(f"cannot locate stored sub-look {path}")


def _stitch_weighting(ks, ps, table) -> dict[str, Any]:
    """Combine the de-windowed bands into one aperture weighting versus time."""

    k = np.concatenate(ks)
    p = np.concatenate(ps)
    order = np.argsort(k)[::-1]          # k_col decreases with slow time
    k, p = k[order], p[order]
    edges = np.linspace(k.max(), k.min(), 257)
    index = np.clip(np.searchsorted(-edges, -k, side="right") - 1, 0, edges.size - 2)
    centres, values, counts = [], [], []
    for b in range(edges.size - 1):
        sel = index == b
        if np.count_nonzero(sel) < 4:
            continue
        centres.append(0.5 * (edges[b] + edges[b + 1]))
        values.append(float(np.median(p[sel])))
        counts.append(int(np.count_nonzero(sel)))
    centres = np.asarray(centres)
    values = np.asarray(values)
    values = values / values.max()
    times = table.time_for_k(centres)
    return {
        "k_col_per_m": centres.tolist(),
        "slow_time_s": times.tolist(),
        "normalized_power": values.tolist(),
        "samples_per_bin": counts,
        "edge_to_peak_power_ratio": float(min(values[0], values[-1])),
        "method": (
            "Each band's measured power is divided by its Tukey window power where "
            "that exceeds 0.2, then overlapping bands are combined by the median."
        ),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    fields = [k for k in rows[0] if k != "source_path"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _plot(path, results, roi, t_old, t_new, phase, row, col, shrink, omega_buoy) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 9,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.top": True,
        "ytick.right": True,
        "axes.grid": False,
    })
    figure, axes = plt.subplots(1, 3, figsize=(11.0, 3.4))

    weighting = results[roi]["reconstructed_aperture_weighting"]
    ax = axes[0]
    ax.plot(weighting["slow_time_s"], weighting["normalized_power"],
            color="#00204d", linewidth=1.4, label="pesatura ricostruita")
    for entry in results[roi]["sub_look_centroids"]:
        ax.axvline(entry["t_geometric_center_s"], color="#7f7f7f",
                   linewidth=0.6, linestyle=":")
        ax.axvline(entry["t_energy_centroid_s"], color="#bb5566",
                   linewidth=0.6, linestyle="-")
    ax.set_xlabel("slow time [s]")
    ax.set_ylabel("potenza azimutale normalizzata")
    ax.plot([], [], color="#7f7f7f", linewidth=0.8, linestyle=":",
            label="centri geometrici")
    ax.plot([], [], color="#bb5566", linewidth=0.8, linestyle="-",
            label="centroidi energetici")
    ax.set_ylim(0.0, 1.28)
    ax.set_title("(a) pesatura d'apertura misurata")
    ax.legend(frameon=False, loc="upper left", fontsize=6.5, ncol=1)

    ax = axes[1]
    ax.plot(t_old, t_old, color="#7f7f7f", linewidth=1.0, linestyle=":",
            label="identita (ipotesi geometrica)")
    ax.plot(t_old, t_new, color="#bb5566", linewidth=1.4, marker="o",
            markersize=3.5, label=f"centroide energetico (shrink {shrink:.3f})")
    ax.set_xlabel("centro geometrico di banda [s]")
    ax.set_ylabel("centroide energetico [s]")
    ax.set_title("(b) accorciamento del braccio")
    ax.legend(frameon=False, fontsize=7, loc="upper left")

    ax = axes[2]
    series = phase[:, row, col]
    for times, colour, style, marker, label in (
        (t_old, "#7f7f7f", ":", "s", "tempi geometrici"),
        (t_new, "#bb5566", "-", "o", "tempi energetici"),
    ):
        design = np.column_stack((np.ones(times.size), times))
        beta = np.linalg.lstsq(design, series, rcond=None)[0]
        grid = np.linspace(times.min(), times.max(), 64)
        ax.plot(times, series, linestyle="none", marker=marker, markersize=3.5,
                color=colour)
        ax.plot(grid, beta[0] + beta[1] * grid, color=colour, linestyle=style,
                linewidth=1.3, label=f"{label}: {abs(beta[1]):.4f} rad/s")
    reference = np.linspace(t_new.min(), t_new.max(), 64)
    ax.plot(reference, -omega_buoy * (reference - t_new.mean())
            + series.mean(), color="#000000", linestyle="--", linewidth=1.1,
            label=f"boa NDBC: {omega_buoy:.4f} rad/s")
    ax.set_xlabel("slow time [s]")
    ax.set_ylabel("fase non avvolta [rad]")
    ax.set_title(f"(c) picco congelato ({row},{col})")
    ax.legend(frameon=False, fontsize=7, loc="best")

    figure.tight_layout()
    figure.savefig(path, dpi=200)
    plt.close(figure)


if __name__ == "__main__":
    main()

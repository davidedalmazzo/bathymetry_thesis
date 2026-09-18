"""Block 12 - form sub-looks directly from CPHD phase history by backprojection.

Three modes:

  overview  coarse image over a wide area from a pulse subset. End-to-end check
            that the geometry is right: the coastline must appear where the DEM
            says it is, and the correct carrier sign must beat the wrong one by
            a large contrast margin.
  validate  fine image on a small patch, both carrier signs, focus metrics.
  form      the production run: disjoint sub-looks over the full CPHD dwell on
            the Block 7 all-water support.

See umbra_sar/backprojection.py for why the vendor SICD is not reused.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from umbra_sar.backprojection import (  # noqa: E402
    CphdChannel, backproject, build_ground_grid, disjoint_look_assignment,
)

ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / 'umbra/Vandenberg'
SUPPORT_CENTER_E_N = (715510.6102416331, 3827627.093742074)
SUPPORT_BEARING_DEG = 79.8357237
SEA_SURFACE_HAE_M = -36.376          # NOAA GEOID18 at the ROI; NAVD88 zero
UTM_ZONE = 10


def _progress(label: str):
    state = {"t": time.time()}

    def report(done: int, total: int) -> None:
        now = time.time()
        if now - state["t"] < 20.0 and done < total:
            return
        state["t"] = now
        print(f"  {label}: {done}/{total} impulsi ({100.0 * done / total:.1f}%)",
              flush=True)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["overview", "validate", "form"])
    parser.add_argument("--cphd", type=Path,
                        default=VANDENBERG / "2025-02-16-18-55-44_UMBRA-10_CPHD.cphd")
    parser.add_argument("--cphd-json", type=Path,
                        default=VANDENBERG / "metadata" / "CPHD_METADATA.json")
    parser.add_argument("--outdir", type=Path,
                        default=VANDENBERG / "results" / "block12_backprojection")
    parser.add_argument("--spacing-m", type=float, default=5.0)
    parser.add_argument("--length-parallel-m", type=float, default=1440.0)
    parser.add_argument("--length-perpendicular-m", type=float, default=650.0)
    parser.add_argument("--look-count", type=int, default=32)
    parser.add_argument("--fft-size", type=int, default=1 << 18)
    parser.add_argument("--pulse-block", type=int, default=256)
    parser.add_argument("--pulse-stride", type=int, default=1,
                        help="overview/validate only; production never decimates")
    parser.add_argument("--max-pulses", type=int, default=0)
    parser.add_argument("--center-easting-m", type=float,
                        default=SUPPORT_CENTER_E_N[0],
                        help="UTM 10N easting of the support centre. The Block 7 "
                             "default is the 1440 m all-water support; a longer "
                             "support must be re-centred seaward so its landward "
                             "edge stays put.")
    parser.add_argument("--center-northing-m", type=float,
                        default=SUPPORT_CENTER_E_N[1])
    parser.add_argument("--delay-window-m", type=float, default=900.0,
                        help="half-width of the retained range-compressed window; "
                             "must exceed the patch's differential-range span")
    parser.add_argument("--carrier-sign", type=int, default=1, choices=[1, -1],
                        help="confirmed +1 on the overview image: the coastline "
                             "lands where the DEM puts it and land sits on the "
                             "positive-parallel side, while -1 smears diagonal "
                             "ghosts. Contrast alone does not separate the two, "
                             "so the image is the evidence, not the metric.")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    channel = CphdChannel.open(args.cphd, args.cphd_json)
    print(f"CPHD: {channel.num_vectors} impulsi, {channel.num_samples} campioni, "
          f"SC0={channel.sc0_hz / 1e9:.6f} GHz, SCSS={channel.scss_hz:.3f} Hz, "
          f"Sgn={channel.global_sgn}")
    print(f"dwell TxTime {channel.tx_time_s[0]:.4f} - {channel.tx_time_s[-1]:.4f} s "
          f"({channel.tx_time_s[-1] - channel.tx_time_s[0]:.4f} s), "
          f"PRF media {channel.num_vectors / (channel.tx_time_s[-1] - channel.tx_time_s[0]):.1f} Hz")

    if args.mode in {"overview", "validate"}:
        _diagnose(channel, args)
        return
    _form(channel, args)


def _subset(channel: CphdChannel, args) -> np.ndarray:
    index = np.arange(0, channel.num_vectors, max(1, args.pulse_stride))
    if args.max_pulses:
        keep = np.linspace(0, index.size - 1, args.max_pulses).astype(np.int64)
        index = index[np.unique(keep)]
    return index


def _diagnose(channel: CphdChannel, args) -> None:
    if args.mode == "overview":
        spacing, length_parallel, length_perpendicular = 12.0, 2400.0, 2400.0
        pulses = args.max_pulses or 1500
    else:
        spacing, length_parallel, length_perpendicular = 0.5, 120.0, 120.0
        pulses = args.max_pulses or 20000

    grid = build_ground_grid(
        center_easting_m=SUPPORT_CENTER_E_N[0],
        center_northing_m=SUPPORT_CENTER_E_N[1],
        utm_zone=UTM_ZONE, bearing_deg=SUPPORT_BEARING_DEG,
        length_parallel_m=length_parallel,
        length_perpendicular_m=length_perpendicular,
        spacing_m=spacing, surface_hae_m=SEA_SURFACE_HAE_M,
    )
    # A contiguous run centred on the dwell: the mount serves sequential reads
    # an order of magnitude faster than scattered ones, and a 1500-pulse burst
    # still gives about 6 m azimuth resolution, ample for a geometry check.
    middle = channel.num_vectors // 2
    index = np.arange(middle - pulses // 2, middle + pulses - pulses // 2,
                      dtype=np.int64)
    look = np.full(channel.num_vectors, -1, dtype=np.int32)
    look[index] = 0
    print(f"\nmodo {args.mode}: griglia {grid.shape} a {spacing} m, "
          f"{index.size} impulsi")

    results = {}
    for sign in (+1, -1):
        t0 = time.time()
        images, diagnostics = backproject(
            channel, grid, look, look_count=1, fft_size=args.fft_size,
            pulse_block=64, carrier_sign=sign, pulse_indices=index,
            progress=_progress(f"segno {sign:+d}"),
        )
        power = np.abs(images[0].reshape(grid.shape)) ** 2
        contrast = float(power.std() / power.mean())
        peak_to_median = float(power.max() / np.median(power))
        results[sign] = {
            "contrast": contrast,
            "peak_to_median_db": 10.0 * np.log10(peak_to_median),
            "elapsed_s": time.time() - t0,
        }
        np.save(args.outdir / f"{args.mode}_sign{sign:+d}_complex64.npy",
                images[0].reshape(grid.shape).astype(np.complex64))
        print(f"  segno {sign:+d}: contrasto {contrast:.3f}, "
              f"picco/mediana {results[sign]['peak_to_median_db']:.1f} dB, "
              f"{results[sign]['elapsed_s']:.0f} s")

    best = max(results, key=lambda s: results[s]["contrast"])
    margin = results[best]["contrast"] / results[-best]["contrast"]
    print(f"\nsegno della portante che focalizza: {best:+d} "
          f"(contrasto {margin:.1f}x rispetto all'altro)")
    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "grid": grid.metadata(),
        "pulses_used": int(index.size),
        "carrier_sign_results": {str(k): v for k, v in results.items()},
        "focusing_carrier_sign": int(best),
        "contrast_margin": float(margin),
        "diagnostics": diagnostics,
    }
    (args.outdir / f"BLOCK12_{args.mode.upper()}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Scritto {args.outdir / f'BLOCK12_{args.mode.upper()}.json'}")


def _form(channel: CphdChannel, args) -> None:
    carrier_sign = int(args.carrier_sign)

    grid = build_ground_grid(
        center_easting_m=args.center_easting_m,
        center_northing_m=args.center_northing_m,
        utm_zone=UTM_ZONE, bearing_deg=SUPPORT_BEARING_DEG,
        length_parallel_m=args.length_parallel_m,
        length_perpendicular_m=args.length_perpendicular_m,
        spacing_m=args.spacing_m, surface_hae_m=SEA_SURFACE_HAE_M,
    )
    if args.max_pulses:
        # smoke test: a contiguous central run, looks split over its own span
        middle = channel.num_vectors // 2
        subset = np.arange(middle - args.max_pulses // 2,
                           middle + args.max_pulses - args.max_pulses // 2,
                           dtype=np.int64)
        look, edges = disjoint_look_assignment(
            channel.tx_time_s, args.look_count,
            start_s=float(channel.tx_time_s[subset[0]]),
            stop_s=float(channel.tx_time_s[subset[-1]]))
        mask = np.ones(channel.num_vectors, dtype=bool)
        mask[subset] = False
        look[mask] = -1
        print(f"  COLLAUDO: solo {subset.size} impulsi contigui, "
              f"{(edges[-1] - edges[0]):.4f} s di dwell")
    else:
        subset = None
        look, edges = disjoint_look_assignment(channel.tx_time_s, args.look_count)
    print(f"\nformazione: griglia {grid.shape} a {args.spacing_m} m "
          f"({grid.ecf_m.shape[0]} px), {args.look_count} sub-look disgiunti "
          f"di {(edges[1] - edges[0]):.4f} s, portante {carrier_sign:+d}")

    srp = channel.srp_position_ecf_m[0]
    probe = np.linspace(0, channel.num_vectors - 1, 32).astype(np.int64)
    span = 0.0
    for pulse in probe:
        antenna = channel.tx_position_ecf_m[pulse]
        delta = grid.ecf_m - antenna
        ranges = np.sqrt(np.einsum("ij,ij->i", delta, delta))
        differential = ranges - float(np.linalg.norm(srp - antenna))
        span = max(span, float(np.max(np.abs(differential))))
    print(f"  span di range differenziale sulla griglia: {span:.0f} m "
          f"(finestra ritardo {args.delay_window_m:.0f} m)")
    if span > 0.9 * args.delay_window_m:
        raise SystemExit(
            f"La finestra di ritardo ({args.delay_window_m:.0f} m) non copre lo "
            f"span della griglia ({span:.0f} m). Rilanciare con "
            f"--delay-window-m {int(np.ceil(span * 1.3 / 100) * 100)}.")

    t0 = time.time()
    images, diagnostics = backproject(
        channel, grid, look, look_count=args.look_count, fft_size=args.fft_size,
        delay_window_m=args.delay_window_m,
        pulse_block=args.pulse_block, carrier_sign=carrier_sign,
        pulse_indices=subset, progress=_progress("formazione"),
    )
    elapsed = time.time() - t0
    stack = images.reshape((args.look_count,) + grid.shape)
    np.save(args.outdir / "BLOCK12_SUBLOOKS_complex64.npy", stack)

    powers = [float(np.mean(np.abs(stack[i]) ** 2)) for i in range(args.look_count)]
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": ("Sub-looks formed by time-domain backprojection from CPHD phase "
                  "history; the vendor SICD is not used."),
        "why_not_the_sicd": (
            "The SICD declares SVA weighting on Grid.Row and Grid.Col without "
            "WgtFunct samples. SVA is a nonlinear, pixel-dependent apodization "
            "that does not commute with a Doppler sub-band split, so a sub-look "
            "masked out of an SVA image is not the image that band would form. "
            "Autofocus is declared off and TimeCOAPoly is constant."
        ),
        "source_cphd": str(args.cphd),
        "grid": grid.metadata(),
        "look_edges_tx_time_s": edges.tolist(),
        "look_duration_s": float(edges[1] - edges[0]),
        "mean_tx_time_per_look_s": diagnostics["mean_tx_time_per_look_s"],
        "pulses_per_look": diagnostics["pulses_per_look"],
        "mean_intensity_per_look": powers,
        "carrier_sign": carrier_sign,
        "kernel": diagnostics,
        "elapsed_s": elapsed,
        "advantages_over_block4": [
            "slow time of each look is the exact mean TxTime of its pulses",
            "full 22.541 s CPHD dwell instead of the 18.068 s SICD aperture",
            "strictly disjoint looks; no shared aperture",
            "uniform aperture weighting, chosen here",
            "ground grid at the sea-surface height; no slant-plane Jacobian",
        ],
    }
    (args.outdir / "BLOCK12_SUBLOOK_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nfatto in {elapsed / 60:.1f} min -> "
          f"{args.outdir / 'BLOCK12_SUBLOOKS_complex64.npy'}")


if __name__ == "__main__":
    main()

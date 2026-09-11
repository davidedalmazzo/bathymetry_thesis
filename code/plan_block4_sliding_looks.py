"""Plan fixed-width overlapping SICD Doppler looks with CPHD/PVP time centers."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.constants import speed_of_light
from sarpy.io.complex.sicd_elements.SICD import SICDType

from cphd_doppler_time_mapping import field, interp_decreasing
from umbra_sar.subaperture import make_window


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cphd",
        type=Path,
        default=VANDENBERG / "2025-02-16-18-55-44_UMBRA-10_CPHD.cphd",
    )
    parser.add_argument(
        "--cphd-json",
        type=Path,
        default=VANDENBERG / "metadata" / "CPHD_METADATA.json",
    )
    parser.add_argument(
        "--sicd-xml",
        type=Path,
        default=VANDENBERG / "metadata" / "SICD_METADATA.xml",
    )
    parser.add_argument(
        "--fixed-plan",
        type=Path,
        default=VANDENBERG / "metadata" / "SUBAPERTURE_PLAN_6S.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=VANDENBERG / "metadata" / "BLOCK4_SLIDING_LOOK_PLAN.json",
    )
    parser.add_argument(
        "--plot",
        type=Path,
        default=VANDENBERG / "results" / "diagnostics" / "BLOCK4_SLIDING_LOOK_PLAN.png",
    )
    parser.add_argument("--count", type=int, default=11)
    args = parser.parse_args()

    if args.count < 3 or args.count % 2 != 1:
        raise ValueError("look count must be an odd integer >= 3")
    cphd_meta = json.loads(args.cphd_json.read_text(encoding="utf-8"))
    fixed = json.loads(args.fixed_plan.read_text(encoding="utf-8"))
    sicd = SICDType.from_xml_file(str(args.sicd_xml))
    fixed_bands = [item["band"] for item in fixed["looks"]]
    widths = {int(item["stop"]) - int(item["start"]) for item in fixed_bands}
    if len(widths) != 1:
        raise ValueError("the fixed three-look plan does not use one common width")
    width = widths.pop()
    first_start = int(fixed_bands[0]["start"])
    last_start = int(fixed_bands[-1]["start"])
    starts_fft_order = np.rint(
        np.linspace(first_start, last_start, args.count)
    ).astype(np.int64)
    if len(np.unique(starts_fft_order)) != args.count:
        raise ValueError("sliding look starts are not unique")

    header = cphd_meta["file"]["header"]
    definitions = cphd_meta["pvp_fields"]
    num_vectors = int(cphd_meta["data"]["num_vectors"])
    record_bytes = int(cphd_meta["data"]["num_bytes_pvp"])
    records = np.memmap(
        args.cphd,
        dtype=">f8",
        mode="r",
        offset=int(header["PVP_BLOCK_BYTE_OFFSET"]),
        shape=(num_vectors, record_bytes // 8),
    )
    tx_time = field(records, definitions, "TxTime")[:, 0]
    tx_pos = field(records, definitions, "TxPos")
    srp_pos = field(records, definitions, "SRPPos")
    line_of_sight = srp_pos - tx_pos
    line_of_sight /= np.linalg.norm(line_of_sight, axis=1)[:, None]
    center_frequency = 0.5 * (
        float(sicd.ImageFormation.TxFrequencyProc.MinProc)
        + float(sicd.ImageFormation.TxFrequencyProc.MaxProc)
    )
    col_unit = np.asarray(sicd.Grid.Col.UVectECF.get_array(), dtype=np.float64)
    k_col = (2.0 * center_frequency / speed_of_light) * (line_of_sight @ col_unit)
    if not np.all(np.diff(k_col) < 0):
        raise ValueError("CPHD-derived k_col is not strictly decreasing")

    fft_size = int(fixed["support"]["fft_size"])
    fft_coordinates = np.fft.fftshift(
        np.fft.fftfreq(fft_size, d=float(sicd.Grid.Col.SS))
    )
    fixed_start_to_look = {
        int(item["band"]["start"]): int(item["look_index"])
        for item in fixed["looks"]
    }
    window, window_metrics = make_window(
        width, "tukey", tukey_alpha=0.25, normalization="energy"
    )
    del window

    # Ascending FFT index runs late -> early, so reverse for chronological output.
    looks: list[dict[str, object]] = []
    for chronological_index, start in enumerate(starts_fft_order[::-1], start=1):
        start = int(start)
        stop = start + width
        low_k = float(fft_coordinates[start])
        high_k = float(fft_coordinates[stop - 1])
        center_k = 0.5 * (low_k + high_k)
        mapped = interp_decreasing(
            k_col, tx_time, np.array([low_k, center_k, high_k])
        )
        reused_fixed_look = fixed_start_to_look.get(start)
        looks.append(
            {
                "chronological_index": chronological_index,
                "fft_order_index": int(
                    np.where(starts_fft_order == start)[0][0] + 1
                ),
                "band": {
                    "start_inclusive": start,
                    "stop_exclusive": stop,
                    "width_bins": width,
                },
                "k_col_low_center_high_per_m": [low_k, center_k, high_k],
                "effective_early_center_late_s": [
                    float(mapped[2]),
                    float(mapped[1]),
                    float(mapped[0]),
                ],
                "effective_span_s": float(mapped[0] - mapped[2]),
                "reuses_block3_nonoverlap_look": reused_fixed_look,
            }
        )

    centers = np.array(
        [item["effective_early_center_late_s"][1] for item in looks],
        dtype=np.float64,
    )
    steps = np.diff(centers)
    start_steps = np.abs(np.diff(starts_fft_order))
    overlap_fractions = 1.0 - start_steps / width
    middle = (args.count + 1) // 2
    nonoverlap = [1, middle, args.count]
    if [looks[index - 1]["reuses_block3_nonoverlap_look"] for index in nonoverlap] != [3, 2, 1]:
        raise ValueError("chronological endpoint/middle looks do not reproduce Block-3 bands")

    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Block 4 fixed ~6 s width sliding looks; no dwell sweep",
        "inputs": {
            "cphd": str(args.cphd.resolve()),
            "cphd_metadata": str(args.cphd_json.resolve()),
            "sicd_xml": str(args.sicd_xml.resolve()),
            "block3_fixed_plan": str(args.fixed_plan.resolve()),
        },
        "durations_kept_distinct": {
            "sicd_processed_aperture_duration_s": float(
                sicd.ImageFormation.TEndProc - sicd.ImageFormation.TStartProc
            ),
            "cphd_available_slow_time_dwell_s": float(
                cphd_meta["dwell"]["dwell_time_s"]
            ),
        },
        "transform_convention": {
            "sicd_col_sgn": int(sicd.Grid.Col.Sgn),
            "image_to_shifted_doppler": "fft",
            "shifted_doppler_to_image": "ifft",
            "fft_axis": 1,
        },
        "window": {
            "kind": "tukey",
            "alpha": 0.25,
            "normalization": "energy",
            "length_bins": width,
            "applied_scale": window_metrics.applied_scale,
            "enbw_bins": window_metrics.enbw_bins,
        },
        "sequence": {
            "count": args.count,
            "centers_order": "chronological early to late",
            "physical_center_time_source": "CPHD/PVP inversion of Doppler k_col",
            "center_step_s": {
                "values": steps.tolist(),
                "minimum": float(steps.min()),
                "maximum": float(steps.max()),
                "mean": float(steps.mean()),
            },
            "adjacent_doppler_overlap_fraction": {
                "values_fft_order": overlap_fractions.tolist(),
                "minimum": float(overlap_fractions.min()),
                "maximum": float(overlap_fractions.max()),
                "mean": float(overlap_fractions.mean()),
            },
        },
        "looks_chronological": looks,
        "independent_nonoverlap_set_retained": {
            "chronological_indices": nonoverlap,
            "corresponding_block3_look_indices": [3, 2, 1],
            "note": "These are the original three disjoint ~6 s Doppler bands and remain stored separately under results/sublooks_complex for future dispersion work.",
        },
        "guardrails": {
            "dwell_sweep_performed": False,
            "bathymetric_inversion_performed": False,
            "external_oceanography_used_for_phase_branch": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    args.plot.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(10, 5.5), constrained_layout=True)
    for item in looks:
        early, center, late = item["effective_early_center_late_s"]
        index = item["chronological_index"]
        color = "tab:orange" if index in nonoverlap else "tab:blue"
        axis.plot([early, late], [index, index], color=color, linewidth=5, alpha=0.75)
        axis.plot(center, index, "o", color="black", markersize=3)
    axis.set_xlabel("CPHD/PVP slow time from CollectionStart (s)")
    axis.set_ylabel("Sliding look (chronological)")
    axis.set_title("Block 4: overlapping fixed-width ~6 s looks")
    axis.grid(True, alpha=0.25)
    fig.savefig(args.plot, dpi=180)
    plt.close(fig)
    print(args.output)
    print(args.plot)


if __name__ == "__main__":
    main()

"""Map SICD azimuth spatial-frequency bands to CPHD PVP slow time.

Only the CPHD ASCII header, XML, and PVP blocks are accessed. The CPHD signal
block is never opened. For this monostatic collection the two-way spatial
frequency vector at the processed SICD center frequency is projected onto the
SICD Grid Row/Col unit vectors and inverted monotonically against TxTime.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.constants import speed_of_light
from sarpy.io.complex.sicd_elements.SICD import SICDType


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"


def field(records: np.ndarray, definitions: dict, name: str) -> np.ndarray:
    item = definitions[name]
    start = int(item["offset_words"])
    stop = start + int(item["size_words"])
    return np.asarray(records[:, start:stop], dtype=np.float64)


def interp_decreasing(x: np.ndarray, y: np.ndarray, targets: np.ndarray) -> np.ndarray:
    if not np.all(np.diff(x) < 0):
        raise ValueError("Expected a strictly decreasing spatial-frequency mapping")
    if np.any(targets < x[-1]) or np.any(targets > x[0]):
        raise ValueError("Requested spatial-frequency target is outside CPHD coverage")
    return np.interp(targets, x[::-1], y[::-1])


def mapping_stats(values: np.ndarray) -> dict[str, float | bool]:
    return {
        "first": float(values[0]),
        "last": float(values[-1]),
        "min": float(values.min()),
        "max": float(values.max()),
        "strictly_decreasing": bool(np.all(np.diff(values) < 0)),
    }


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
        "--plan",
        type=Path,
        default=VANDENBERG / "metadata" / "SUBAPERTURE_PLAN_6S.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=VANDENBERG / "metadata" / "CPHD_DOPPLER_TIME_MAPPING.json",
    )
    parser.add_argument(
        "--plot",
        type=Path,
        default=VANDENBERG / "results" / "diagnostics" / "CPHD_DOPPLER_TIME_MAPPING.png",
    )
    args = parser.parse_args()

    cphd_meta = json.loads(args.cphd_json.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    sicd = SICDType.from_xml_file(str(args.sicd_xml))
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

    processed_center_frequency_hz = 0.5 * (
        float(sicd.ImageFormation.TxFrequencyProc.MinProc)
        + float(sicd.ImageFormation.TxFrequencyProc.MaxProc)
    )
    wave_vector_ecf = (
        2.0 * processed_center_frequency_hz / speed_of_light
    ) * line_of_sight
    row_unit = np.asarray(sicd.Grid.Row.UVectECF.get_array(), dtype=np.float64)
    col_unit = np.asarray(sicd.Grid.Col.UVectECF.get_array(), dtype=np.float64)
    k_row = wave_vector_ecf @ row_unit
    k_col = wave_vector_ecf @ col_unit

    if not np.all(np.diff(tx_time) > 0):
        raise ValueError("CPHD TxTime is not strictly increasing")
    if not np.all(np.diff(k_col) < 0):
        raise ValueError("CPHD-derived SICD Col spatial frequency is not monotonic")

    scp_time = float(sicd.SCPCOA.SCPTime)
    k_col_at_scp = float(np.interp(scp_time, tx_time, k_col))
    k_row_at_scp = float(np.interp(scp_time, tx_time, k_row))

    # An independent consistency check: evaluate the SICD ARP polynomial at the
    # same PVP times and compare its projected k_col with the CPHD PVP geometry.
    processed_mask = (tx_time >= float(sicd.ImageFormation.TStartProc)) & (
        tx_time <= float(sicd.ImageFormation.TEndProc)
    )
    processed_times = tx_time[processed_mask]
    sicd_arp = np.asarray(sicd.Position.ARPPoly(processed_times), dtype=np.float64)
    sicd_los = np.asarray(sicd.GeoData.SCP.ECF.get_array()) - sicd_arp
    sicd_los /= np.linalg.norm(sicd_los, axis=1)[:, None]
    sicd_k_col = (
        2.0 * processed_center_frequency_hz / speed_of_light
    ) * (sicd_los @ col_unit)
    cphd_k_col_processed = k_col[processed_mask]
    k_col_residual = cphd_k_col_processed - sicd_k_col

    fft_size = int(plan["support"]["fft_size"])
    col_ss = float(sicd.Grid.Col.SS)
    fft_coordinates = np.fft.fftshift(np.fft.fftfreq(fft_size, d=col_ss))
    support_targets = np.array(
        [float(sicd.Grid.Col.DeltaK1), float(sicd.Grid.Col.DeltaK2)]
    )
    support_times = interp_decreasing(k_col, tx_time, support_targets)

    looks: list[dict[str, object]] = []
    for item in plan["looks"]:
        band = item["band"]
        start = int(band["start"])
        stop = int(band["stop"])
        low_k = float(fft_coordinates[start])
        high_k = float(fft_coordinates[stop - 1])
        center_k = 0.5 * (low_k + high_k)
        mapped = interp_decreasing(
            k_col, tx_time, np.array([low_k, center_k, high_k])
        )
        # Since k_col decreases with time, the high-k edge is earlier.
        early_time = float(mapped[2])
        center_time = float(mapped[1])
        late_time = float(mapped[0])
        looks.append(
            {
                "look_index": int(item["look_index"]),
                "fft_shifted_bin_start_inclusive": start,
                "fft_shifted_bin_stop_exclusive": stop,
                "k_col_low_center_high_per_m": [low_k, center_k, high_k],
                "slow_time_for_low_center_high_k_s": mapped.tolist(),
                "effective_early_center_late_s": [
                    early_time,
                    center_time,
                    late_time,
                ],
                "effective_edge_span_s": late_time - early_time,
                "nominal_metadata_only_center_s": float(
                    band["nominal_center_time_from_collect_start_s"]
                ),
                "ordering_note": "Because CPHD-derived k_col decreases with TxTime, ascending shifted-FFT band index runs from later to earlier slow time: look 1 is late, look 3 is early.",
            }
        )

    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "CPHD ASCII header/XML/PVP only; CPHD signal block not read",
        "signal_block_read": False,
        "method": {
            "collection_type": "MONOSTATIC",
            "formula": "k_ECF(t)=(2*f_proc_center/c)*unit(SRPPos(t)-TxPos(t)); k_col=dot(k_ECF, SICD.Grid.Col.UVectECF)",
            "time_coordinate": "CPHD PVP TxTime in seconds relative to the shared CollectionStart",
            "frequency_choice": "SICD processed TxFrequencyProc center, required to reproduce SICD Row.KCtr at SCPTime",
            "inversion": "piecewise-linear interpolation of strictly decreasing k_col(t) over all PVP vectors",
            "fft_coordinate": "fftshift(fftfreq(NumCols, d=Grid.Col.SS)); validated Col.Sgn=-1 image->spectrum transform is fft",
        },
        "durations_kept_distinct": {
            "sicd_processed_aperture_duration_s": float(
                sicd.ImageFormation.TEndProc - sicd.ImageFormation.TStartProc
            ),
            "cphd_available_slow_time_dwell_s": float(
                cphd_meta["dwell"]["dwell_time_s"]
            ),
        },
        "inputs": {
            "cphd": str(args.cphd.resolve()),
            "cphd_metadata": str(args.cphd_json.resolve()),
            "sicd_xml": str(args.sicd_xml.resolve()),
            "subaperture_plan": str(args.plan.resolve()),
        },
        "processed_center_frequency_hz": processed_center_frequency_hz,
        "pvp_tx_time_s": {
            "first": float(tx_time[0]),
            "last": float(tx_time[-1]),
            "span": float(tx_time[-1] - tx_time[0]),
            "strictly_increasing": bool(np.all(np.diff(tx_time) > 0)),
        },
        "pvp_projected_k_col_per_m": mapping_stats(k_col),
        "reference_checks": {
            "sicd_scp_time_s": scp_time,
            "interpolated_k_col_at_scp_time_per_m": k_col_at_scp,
            "interpolated_k_row_at_scp_time_per_m": k_row_at_scp,
            "sicd_grid_row_kctr_per_m": float(sicd.Grid.Row.KCtr),
            "row_kctr_absolute_error_per_m": abs(
                k_row_at_scp - float(sicd.Grid.Row.KCtr)
            ),
            "cphd_vs_sicd_arp_poly_k_col_residual_per_m": {
                "rms": float(np.sqrt(np.mean(k_col_residual**2))),
                "max_abs": float(np.max(np.abs(k_col_residual))),
                "samples": int(k_col_residual.size),
            },
        },
        "sicd_processed_support": {
            "k_col_delta_k1_delta_k2_per_m": support_targets.tolist(),
            "mapped_time_for_delta_k1_delta_k2_s": support_times.tolist(),
            "chronological_early_late_s": [
                float(support_times[1]),
                float(support_times[0]),
            ],
            "mapped_span_s": float(support_times[0] - support_times[1]),
            "image_formation_t_start_t_end_s": [
                float(sicd.ImageFormation.TStartProc),
                float(sicd.ImageFormation.TEndProc),
            ],
        },
        "looks": looks,
        "interpretation_guardrail": "This mapping supplies effective look times for later phase interpretation, but no cross-spectrum phase is converted to a period in Block 3.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    args.plot.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5.5), constrained_layout=True)
    ax.plot(tx_time, k_col, color="black", linewidth=1.2, label="CPHD PVP geometry")
    colors = ["tab:blue", "tab:orange", "tab:green"]
    for look, color in zip(looks, colors):
        k_low, k_center, k_high = look["k_col_low_center_high_per_m"]
        ax.axhspan(k_low, k_high, color=color, alpha=0.16)
        ax.scatter(
            [look["effective_early_center_late_s"][1]],
            [k_center],
            color=color,
            label=f"look {look['look_index']} center",
            zorder=3,
        )
    ax.axvline(scp_time, color="0.45", linestyle="--", label="SICD SCPTime")
    ax.set_xlabel("CPHD TxTime / slow time (s)")
    ax.set_ylabel("Projected SICD Col spatial frequency (cycles/m)")
    ax.set_title("PVP geometry mapping: Doppler/spatial-frequency band to slow time")
    ax.grid(True, alpha=0.25)
    ax.legend(ncol=2, fontsize=8)
    fig.savefig(args.plot, dpi=180)
    plt.close(fig)
    print(args.output)
    print(args.plot)
    print("CPHD signal block read: False")


if __name__ == "__main__":
    main()

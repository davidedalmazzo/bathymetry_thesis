"""Analyze the complete directional NDBC 46218 spectrum nearest the SICD."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.io import netcdf_file
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from umbra_sar.physical_identification import (
    axial_difference_deg,
    frequency_bin_edges,
    ndbc_directional_distribution,
    propagation_to_deg,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'umbra/Vandenberg/external/46218w9999.nc'
FROZEN = ROOT / 'umbra/Vandenberg/results/analysis_block5/BLOCK5_FROZEN_INPUTS.json'
OUTPUT_DIR = ROOT / 'umbra/Vandenberg/results/analysis_block5'
ACQUISITION = datetime(2025, 2, 16, 18, 55, 44, 274000, tzinfo=timezone.utc)
SOURCE_URL = (
    "https://dods.ndbc.noaa.gov/thredds/fileServer/data/swden/46218/"
    "46218w9999.nc"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def circular_energy_mean_deg(direction_deg: np.ndarray, weight: np.ndarray) -> float:
    vector = np.sum(weight * np.exp(1j * np.deg2rad(direction_deg)))
    return float(np.rad2deg(np.angle(vector)) % 360.0)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    theta_sar = frozen["frozen_sar_only"][
        "theta_SAR_wavevector_bearing_deg_mod_180"
    ]
    t_sar = frozen["frozen_sar_only"]["T_SAR_s"]
    requested_t_sar = frozen["frozen_sar_only"]["T_SAR_reported_s"]
    f1 = 1.0 / requested_t_sar
    f1_exact_frozen = 1.0 / t_sar
    f2 = 1.0 / 13.33

    with netcdf_file(SOURCE, "r", mmap=False) as dataset:
        time_epoch_s = dataset.variables["time"][:].astype(np.int64)
        frequency = dataset.variables["frequency"][:].astype(np.float64)
        target_epoch = ACQUISITION.timestamp()
        record_index = int(np.argmin(np.abs(time_epoch_s - target_epoch)))
        record_epoch = int(time_epoch_s[record_index])
        variables = {
            name: dataset.variables[name][record_index, :, 0, 0].astype(np.float64)
            for name in (
                "spectral_wave_density",
                "mean_wave_dir",
                "principal_wave_dir",
                "wave_spectrum_r1",
                "wave_spectrum_r2",
            )
        }
        latitude = float(dataset.variables["latitude"][0])
        longitude = float(dataset.variables["longitude"][0])
        global_attributes = {
            name: (
                value.decode("utf-8", errors="replace")
                if isinstance(value, bytes)
                else value
            )
            for name, value in dataset._attributes.items()
        }
        neighbor_indices = np.arange(record_index - 3, record_index + 4)
        neighbor_density = dataset.variables["spectral_wave_density"][
            neighbor_indices, :, 0, 0
        ].astype(np.float64)
        neighbor_alpha1 = dataset.variables["mean_wave_dir"][
            neighbor_indices, :, 0, 0
        ].astype(np.float64)

    density = variables["spectral_wave_density"]
    alpha1 = variables["mean_wave_dir"]
    alpha2 = variables["principal_wave_dir"]
    r1 = variables["wave_spectrum_r1"]
    r2 = variables["wave_spectrum_r2"]
    direction_to = (alpha1 + 180.0) % 360.0
    edges = frequency_bin_edges(frequency)
    bin_width = np.diff(edges)
    variance_per_bin = density * bin_width
    total_m0 = float(np.sum(variance_per_bin))

    def target_summary(target_frequency: float) -> dict[str, object]:
        nearest = int(np.argmin(np.abs(frequency - target_frequency)))
        insertion = int(np.searchsorted(frequency, target_frequency))
        bracketing = sorted(
            {max(0, insertion - 1), min(frequency.size - 1, insertion)}
        )
        return {
            "target_frequency_hz": target_frequency,
            "target_period_s": 1.0 / target_frequency,
            "nearest_bin_index": nearest,
            "nearest_bin": {
                "frequency_hz": float(frequency[nearest]),
                "period_s": float(1.0 / frequency[nearest]),
                "frequency_offset_hz": float(frequency[nearest] - target_frequency),
                "spectral_wave_density_m2_per_hz": float(density[nearest]),
                "variance_in_bin_m2": float(variance_per_bin[nearest]),
                "fraction_total_variance": float(variance_per_bin[nearest] / total_m0),
                "equivalent_single_bin_Hm0_m": float(
                    4.0 * math.sqrt(variance_per_bin[nearest])
                ),
                "alpha1_direction_from_deg": float(alpha1[nearest]),
                "alpha1_propagation_to_deg": float(direction_to[nearest]),
                "alpha2_principal_from_deg": float(alpha2[nearest]),
                "r1": float(r1[nearest]),
                "r2": float(r2[nearest]),
                "axial_direction_difference_from_SAR_deg": axial_difference_deg(
                    direction_to[nearest], theta_sar
                ),
            },
            "bracketing_bins": [
                {
                    "frequency_hz": float(frequency[index]),
                    "period_s": float(1.0 / frequency[index]),
                    "spectral_wave_density_m2_per_hz": float(density[index]),
                    "alpha1_direction_from_deg": float(alpha1[index]),
                    "alpha1_propagation_to_deg": float(direction_to[index]),
                    "r1": float(r1[index]),
                    "axial_direction_difference_from_SAR_deg": axial_difference_deg(
                        direction_to[index], theta_sar
                    ),
                }
                for index in bracketing
            ],
        }

    target_f1 = target_summary(f1)
    target_f2 = target_summary(f2)

    # Peak diagnostics are reported both raw and after a declared 0.75-bin
    # Gaussian smoothing. The latter prevents interpreting bin-to-bin estimator
    # jitter as multiple physical systems.
    raw_peaks, raw_props = find_peaks(density, prominence=0.15, distance=2)
    smooth_density = gaussian_filter1d(density, sigma=0.75)
    smooth_peaks, smooth_props = find_peaks(
        smooth_density, prominence=0.15, distance=2
    )

    def peaks_to_records(indices: np.ndarray, prominences: np.ndarray, field: np.ndarray):
        records = []
        for index, prominence in zip(indices, prominences):
            if frequency[index] > 0.30:
                continue
            records.append(
                {
                    "frequency_hz": float(frequency[index]),
                    "period_s": float(1.0 / frequency[index]),
                    "density_m2_per_hz": float(field[index]),
                    "prominence_m2_per_hz": float(prominence),
                    "alpha1_from_deg": float(alpha1[index]),
                    "propagation_to_deg": float(direction_to[index]),
                    "r1": float(r1[index]),
                }
            )
        return records

    partitions = []
    for name, lower, upper in (
        ("dominant_long_period_swell_band", 0.045, 0.135),
        ("shorter_period_secondary_band", 0.135, 0.250),
        ("high_frequency_tail", 0.250, math.inf),
    ):
        mask = (frequency >= lower) & (frequency < upper)
        weights = variance_per_bin[mask]
        partitions.append(
            {
                "name": name,
                "frequency_bounds_hz": [lower, None if math.isinf(upper) else upper],
                "variance_m2": float(np.sum(weights)),
                "fraction_total_variance": float(np.sum(weights) / total_m0),
                "equivalent_partition_Hm0_m": float(4.0 * math.sqrt(np.sum(weights))),
                "energy_weighted_alpha1_from_deg": circular_energy_mean_deg(
                    alpha1[mask], weights
                ),
                "energy_weighted_propagation_to_deg": circular_energy_mean_deg(
                    direction_to[mask], weights
                ),
            }
        )

    f1_index = int(target_f1["nearest_bin_index"])
    f2_index = int(target_f2["nearest_bin_index"])
    temporal_check = []
    for local, source_index in enumerate(neighbor_indices):
        temporal_check.append(
            {
                "utc": datetime.fromtimestamp(
                    int(time_epoch_s[source_index]), timezone.utc
                ).isoformat(),
                "f1_nearest_density_m2_per_hz": float(
                    neighbor_density[local, f1_index]
                ),
                "f1_nearest_propagation_to_deg": propagation_to_deg(
                    neighbor_alpha1[local, f1_index]
                ),
                "f2_nearest_density_m2_per_hz": float(
                    neighbor_density[local, f2_index]
                ),
                "f2_nearest_propagation_to_deg": propagation_to_deg(
                    neighbor_alpha1[local, f2_index]
                ),
            }
        )

    csv_path = OUTPUT_DIR / "NDBC_46218_20250216T1900_FULL_DIRECTIONAL_SPECTRUM.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "frequency_hz",
                "period_s",
                "spectral_wave_density_m2_per_hz",
                "bin_width_hz",
                "variance_in_bin_m2",
                "alpha1_direction_from_deg",
                "alpha1_propagation_to_deg",
                "alpha2_principal_from_deg",
                "r1",
                "r2",
            ]
        )
        for values in zip(
            frequency,
            1.0 / frequency,
            density,
            bin_width,
            variance_per_bin,
            alpha1,
            direction_to,
            alpha2,
            r1,
            r2,
        ):
            writer.writerow(values)

    azimuth = np.arange(0.0, 361.0, 2.0)
    directional = np.stack(
        [
            density[index]
            * ndbc_directional_distribution(
                azimuth, alpha1[index], alpha2[index], r1[index], r2[index]
            )
            for index in range(frequency.size)
        ]
    )
    fig, axes = plt.subplots(4, 1, figsize=(11, 13), constrained_layout=True)
    axes[0].plot(frequency, density, "k.-", label="C11 spectral density")
    axes[0].plot(frequency, smooth_density, color="tab:blue", label="Gaussian 0.75-bin")
    axes[0].axvline(f1, color="tab:green", linestyle="--", label=f"f1={f1:.5f} Hz")
    axes[0].axvline(f2, color="tab:red", linestyle="--", label=f"f2={f2:.5f} Hz")
    axes[0].set_xlim(0.025, 0.30)
    axes[0].set_ylabel("C11 [m²/Hz]")
    axes[0].grid(alpha=0.25)
    axes[0].legend(ncol=4, fontsize=8)

    energetic = density > 0
    axes[1].scatter(frequency[energetic], direction_to[energetic], c=r1[energetic], cmap="viridis", s=35)
    axes[1].axhline(theta_sar, color="tab:orange", linestyle="--", label="SAR 79.84° mod 180")
    axes[1].axhline(theta_sar + 180.0, color="tab:orange", linestyle="--")
    axes[1].set_xlim(0.025, 0.30)
    axes[1].set_ylim(0, 360)
    axes[1].set_ylabel("Propagation-to alpha1 [°]")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.25)

    axes[2].plot(frequency, r1, label="r1")
    axes[2].plot(frequency, r2, label="r2")
    axes[2].set_xlim(0.025, 0.30)
    axes[2].set_ylim(0, 1)
    axes[2].set_ylabel("Directional concentration")
    axes[2].grid(alpha=0.25)
    axes[2].legend()

    image = axes[3].pcolormesh(
        frequency,
        azimuth,
        directional.T,
        shading="nearest",
        cmap="RdBu_r",
    )
    axes[3].set_xlim(0.025, 0.30)
    axes[3].set_ylim(0, 360)
    axes[3].set_xlabel("Frequency [Hz]")
    axes[3].set_ylabel("Direction waves come from [°N]")
    axes[3].set_title("NDBC truncated Fourier directional density (signed)")
    fig.colorbar(image, ax=axes[3], label="C11 D(f,A) [m² Hz⁻¹ rad⁻¹]")
    plot_path = OUTPUT_DIR / "NDBC_46218_FULL_DIRECTIONAL_SPECTRUM.png"
    fig.savefig(plot_path, dpi=180)
    plt.close(fig)

    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Complete NDBC 46218 directional spectrum nearest SICD acquisition",
        "source": {
            "url": SOURCE_URL,
            "path": str(SOURCE),
            "bytes": SOURCE.stat().st_size,
            "sha256": sha256(SOURCE),
            "global_attributes": global_attributes,
            "station_latitude_deg": latitude,
            "station_longitude_deg": longitude,
            "record_count": int(time_epoch_s.size),
            "frequency_count": int(frequency.size),
            "variables_used": list(variables),
        },
        "timing": {
            "sicd_acquisition_utc": ACQUISITION.isoformat(),
            "nearest_spectral_record_index": record_index,
            "nearest_spectral_record_utc": datetime.fromtimestamp(
                record_epoch, timezone.utc
            ).isoformat(),
            "offset_record_minus_acquisition_s": record_epoch - ACQUISITION.timestamp(),
            "note": "The full spectral product is hourly; the separate standard-meteorological record at 18:56 UTC is not substituted for it.",
        },
        "frozen_sar": frozen["frozen_sar_only"],
        "requested_frequencies": {
            "f1_from_reported_17_902_s": f1,
            "f1_from_exact_frozen_T_SAR": f1_exact_frozen,
            "f2_from_13_33_s": f2,
        },
        "bulk_from_integrated_spectrum": {
            "m0_m2": total_m0,
            "Hm0_m": 4.0 * math.sqrt(total_m0),
        },
        "target_f1": target_f1,
        "target_f2": target_f2,
        "nearest_bin_energy_ratio_f1_over_f2": float(
            density[f1_index] / density[f2_index]
        ),
        "peak_detection": {
            "raw_method": "scipy.find_peaks prominence>=0.15 m2/Hz, distance>=2 bins, f<=0.30 Hz",
            "raw_peaks": peaks_to_records(
                raw_peaks, raw_props["prominences"], density
            ),
            "smoothed_method": "Gaussian sigma=0.75 frequency bin then same find_peaks thresholds",
            "smoothed_peaks": peaks_to_records(
                smooth_peaks, smooth_props["prominences"], smooth_density
            ),
            "interpretation_guardrail": "Raw adjacent subpeaks that merge under less-than-one-bin smoothing are not declared separate physical systems.",
        },
        "broad_energy_partitions": partitions,
        "plus_minus_3_hour_target_bin_check": temporal_check,
        "direction_convention": {
            "NDBC_alpha1": "Azimuth clockwise from true north toward direction waves come from",
            "comparison": "propagation-to=(alpha1+180) mod 360, then 180-degree axial difference to SAR wavevector",
            "r1_r2_note": "Normalized directional Fourier radii; low r1 means a weakly concentrated alpha1 direction.",
        },
        "artifacts": {
            "full_frequency_csv": str(csv_path),
            "diagnostic_plot": str(plot_path),
        },
    }
    json_path = OUTPUT_DIR / "BLOCK5_NDBC_FULL_SPECTRUM.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {plot_path}")
    print(
        "f1 nearest: ",
        target_f1["nearest_bin"],
        "\nf2 nearest: ",
        target_f2["nearest_bin"],
    )
    print(f"f1/f2 nearest-bin density ratio: {density[f1_index] / density[f2_index]:.5f}")


if __name__ == "__main__":
    main()

"""Compare frozen SAR-only Block-4 results with the nearest NDBC observation."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io import netcdf_file
from sarpy.io.complex.sicd_elements.SICD import SICDType

from umbra_sar.wave_analysis import axial_difference_deg


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def haversine_km(first_lat_lon: tuple[float, float], second_lat_lon: tuple[float, float]) -> float:
    first = np.deg2rad(first_lat_lon)
    second = np.deg2rad(second_lat_lon)
    delta = second - first
    value = (
        np.sin(delta[0] / 2.0) ** 2
        + np.cos(first[0]) * np.cos(second[0]) * np.sin(delta[1] / 2.0) ** 2
    )
    return float(2.0 * 6371.0088 * np.arcsin(np.sqrt(value)))


def main() -> None:
    sar_path = (
        VANDENBERG
        / "results"
        / "analysis_block4"
        / "BLOCK4_PHASE_METRICS_SAR_ONLY.json"
    )
    buoy_path = VANDENBERG / "external" / "46218h2025.nc"
    roi_path = VANDENBERG / "roi" / "ROIS.json"
    sicd_path = VANDENBERG / "metadata" / "SICD_METADATA.xml"
    sar = json.loads(sar_path.read_text(encoding="utf-8"))
    rois = json.loads(roi_path.read_text(encoding="utf-8"))["rois"]
    sicd = SICDType.from_xml_file(str(sicd_path))
    if sar["external_data_used_for_unwrapping_or_fit"] is not False:
        raise ValueError("SAR-only result does not preserve the external-data guardrail")

    collect_start = np.datetime64(sicd.Timeline.CollectStart, "ns")
    collect_duration = float(sicd.Timeline.CollectDuration)
    midpoint = collect_start + np.timedelta64(round(0.5 * collect_duration * 1e9), "ns")
    midpoint_epoch = float(
        (midpoint - np.datetime64("1970-01-01T00:00:00", "ns"))
        / np.timedelta64(1, "s")
    )
    with netcdf_file(buoy_path, "r", mmap=False) as dataset:
        time = np.asarray(dataset.variables["time"][:], dtype=np.int64)
        closest = int(np.argmin(np.abs(time - midpoint_epoch)))
        latitude = float(dataset.variables["latitude"][0])
        longitude = float(dataset.variables["longitude"][0])

        def value(name: str, index: int) -> float:
            return float(dataset.variables[name][index, 0, 0])

        record = {
            "index": closest,
            "time_utc": datetime.fromtimestamp(
                int(time[closest]), tz=timezone.utc
            ).isoformat(),
            "time_difference_from_sicd_midpoint_s": float(
                time[closest] - midpoint_epoch
            ),
            "significant_wave_height_m": value("wave_height", closest),
            "dominant_wave_period_s": value("dominant_wpd", closest),
            "average_wave_period_s": value("average_wpd", closest),
            "mean_wave_direction_from_deg_true": value("mean_wave_dir", closest),
        }
        neighborhood = []
        for index in range(max(0, closest - 4), min(time.size, closest + 5)):
            neighborhood.append(
                {
                    "time_utc": datetime.fromtimestamp(
                        int(time[index]), tz=timezone.utc
                    ).isoformat(),
                    "significant_wave_height_m": value("wave_height", index),
                    "dominant_wave_period_s": value("dominant_wpd", index),
                    "average_wave_period_s": value("average_wpd", index),
                    "mean_wave_direction_from_deg_true": value(
                        "mean_wave_dir", index
                    ),
                }
            )

    near = sar["results"]["nearshore"]
    fit = near["primary_fixed_patch_phase"]["fit_direct_reference_phase"]
    sar_period = float(fit["period_s"])
    sar_wavevector = float(
        json.loads(
            (
                VANDENBERG
                / "results"
                / "analysis_block3"
                / "BLOCK3_SPECTRAL_METRICS.json"
            ).read_text(encoding="utf-8")
        )["results"]["nearshore"]["three_look_peak_stability"]
        ["mean_wavevector_bearing_deg_mod_180"]
    )
    buoy_from = float(record["mean_wave_direction_from_deg_true"])
    buoy_propagation_to = (buoy_from + 180.0) % 360.0
    roi_lon, roi_lat = rois["nearshore"]["selected_center_lon_lat_deg"]
    dominant = float(record["dominant_wave_period_s"])
    average = float(record["average_wave_period_s"])

    comparison = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ordering_guardrail": {
            "sar_only_metrics_generated_utc": sar["generated_utc"],
            "sar_only_metrics_sha256": sha256_file(sar_path),
            "external_data_used_for_sar_phase_branch_or_fit": False,
            "statement": "The SAR-only JSON was finalized before this external file was inspected; this comparison does not modify its phases, unwrap, slope, or uncertainty.",
        },
        "source": {
            "provider": "NOAA National Data Buoy Center; station data submitted by Scripps CDIP",
            "station": "46218 Harvest, CA (CDIP 071)",
            "station_latitude_deg": latitude,
            "station_longitude_deg": longitude,
            "water_depth_m_from_station_page": 550.0,
            "local_file": str(buoy_path.resolve()),
            "local_file_size_bytes": buoy_path.stat().st_size,
            "local_file_sha256": sha256_file(buoy_path),
            "download_url": "https://dods.ndbc.noaa.gov/thredds/fileServer/data/stdmet/46218/46218h2025.nc",
            "station_history_url": "https://www.ndbc.noaa.gov/station_history.php?station=46218",
            "measurement_description_url": "https://www.ndbc.noaa.gov/obsdes.shtml",
            "distance_from_nearshore_roi_center_km": haversine_km(
                (roi_lat, roi_lon), (latitude, longitude)
            ),
        },
        "sicd_time": {
            "collect_start_utc": str(collect_start),
            "collect_duration_s": collect_duration,
            "collect_midpoint_utc": str(midpoint),
        },
        "nearest_buoy_record": record,
        "buoy_record_neighborhood": neighborhood,
        "comparison": {
            "sar_period_s": sar_period,
            "sar_period_fit_only_95_percent_ci_s": fit[
                "period_95_percent_ci_fit_only_s"
            ],
            "ndbc_dominant_period_s": dominant,
            "ndbc_average_period_s": average,
            "sar_minus_ndbc_dominant_period_s": sar_period - dominant,
            "sar_to_ndbc_dominant_period_ratio": sar_period / dominant,
            "sar_minus_ndbc_average_period_s": sar_period - average,
            "sar_to_ndbc_average_period_ratio": sar_period / average,
            "period_label_warning": "NDBC DPD is the period of maximum nondirectional spectral energy; APD is the average over all waves. Neither is automatically an isolated swell partition period.",
            "sar_wavevector_bearing_deg_mod_180": sar_wavevector,
            "ndbc_mean_wave_direction_from_deg_true": buoy_from,
            "ndbc_inferred_propagation_to_deg_true": buoy_propagation_to,
            "undirected_axis_difference_sar_vs_ndbc_deg": axial_difference_deg(
                sar_wavevector, buoy_propagation_to
            ),
            "direction_warning": "NDBC MWD is the direction waves come from at the dominant-period band; the SAR wavevector is undirected. Modulo 180 permits an axis comparison, not a signed propagation validation.",
        },
        "conclusion": "The frozen SAR period is substantially longer than both the coincident NDBC dominant and average periods, while the undirected propagation axes are close. No alternate SAR unwrap branch was selected to improve this agreement.",
        "guardrails": {
            "sar_unwrap_changed_after_external_comparison": False,
            "dwell_sweep_performed": False,
            "bathymetric_inversion_performed": False,
        },
    }
    output_path = (
        VANDENBERG
        / "results"
        / "analysis_block4"
        / "BLOCK4_EXTERNAL_NDBC_COMPARISON.json"
    )
    output_path.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()

"""Summarize the two verified short-dwell NDBC directional spectra."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'umbra/validazione/Block8_validation'
RESULTS = BASE / "results"
WAVES = RESULTS / "wave_model_screen.csv"
CASES = [
    {
        "station": "42084", "collect": "2025-12-02-16-00-55_UMBRA-07", "distance_km": 34.1639,
        "observation_utc": "2025-12-02T16:00:00Z", "time_offset_s": -55.5,
        "file": BASE / "buoy_data" / "42084_20251202T1600_spectrum.ascii",
    },
    {
        "station": "42084", "collect": "2025-12-23-02-59-26_UMBRA-07", "distance_km": 34.1639,
        "observation_utc": "2025-12-23T03:00:00Z", "time_offset_s": 33.4,
        "file": BASE / "buoy_data" / "42084_20251223T0300_spectrum.ascii",
    },
    {
        "station": "42084", "collect": "2026-02-18-04-59-34_UMBRA-09", "distance_km": 34.1639,
        "observation_utc": "2026-02-18T05:00:00Z", "time_offset_s": 25.9,
        "file": BASE / "buoy_data" / "42084_20260218T0500_spectrum.ascii",
    },
    {
        "station": "42084", "collect": "2026-03-14-04-37-20_UMBRA-09", "distance_km": 34.1639,
        "observation_utc": "2026-03-14T05:00:00Z", "time_offset_s": 1359.4,
        "file": BASE / "buoy_data" / "42084_20260314T0500_spectrum.ascii",
    },
    {
        "station": "46237", "collect": "2023-08-04-18-18-17_UMBRA-04", "distance_km": 19.0471,
        "observation_utc": "2023-08-04T18:00:00Z", "time_offset_s": -1097.5,
        "file": BASE / "buoy_data" / "46237_20230804T1800_spectrum.ascii",
    },
    {
        "station": "44087", "collect": "2023-07-13-15-18-26_UMBRA-04", "distance_km": 6.5311,
        "observation_utc": "2023-07-13T15:00:00Z", "time_offset_s": -1106.2,
        "file": BASE / "buoy_data" / "44087_20230713T1500_spectrum.ascii",
    },
]


def values_after_section(text, name):
    match = re.search(rf"(?m)^{re.escape(name)}\.{re.escape(name)}[^\n]*\n(.*?)(?:\n\s*\n|\Z)", text, re.S)
    if not match:
        raise ValueError(f"section {name!r} not found")
    return np.asarray([float(line.rsplit(",", 1)[-1].strip()) for line in match.group(1).splitlines() if line.strip()], dtype=float)


def frequency_values(text):
    match = re.search(r"(?m)^frequency\[\d+\]\s*\n([^\n]+)", text)
    if not match:
        raise ValueError("frequency vector not found")
    return np.asarray([float(v.strip()) for v in match.group(1).split(",")], dtype=float)


def axial_delta(direction, axis):
    return abs(((direction - axis + 90.0) % 180.0) - 90.0)


def local_peak_indices(spectrum):
    interior = [i for i in range(1, len(spectrum) - 1) if spectrum[i] >= spectrum[i - 1] and spectrum[i] > spectrum[i + 1]]
    return sorted(interior, key=lambda i: spectrum[i], reverse=True)


def main():
    with WAVES.open(newline="", encoding="utf-8") as handle:
        wave_by_collect = {row["collect_name"]: row for row in csv.DictReader(handle)}
    output = []
    for case in CASES:
        scene = wave_by_collect[case["collect"]]
        text = case["file"].read_text(encoding="utf-8")
        f = frequency_values(text)
        density = values_after_section(text, "spectral_wave_density")
        alpha1 = values_after_section(text, "mean_wave_dir")
        alpha2 = values_after_section(text, "principal_wave_dir")
        r1 = values_after_section(text, "wave_spectrum_r1")
        r2 = values_after_section(text, "wave_spectrum_r2")
        valid = np.isfinite(density) & (density < 900) & (density >= 0)
        f, density, alpha1, alpha2, r1, r2 = (array[valid] for array in (f, density, alpha1, alpha2, r1, r2))
        m0 = float(np.trapezoid(density, f))
        long = f <= 0.10
        long_m0 = float(np.trapezoid(density[long], f[long])) if np.count_nonzero(long) >= 2 else 0.0
        peaks = local_peak_indices(density)
        peak = peaks[0] if peaks else int(np.argmax(density))
        long_indices = np.where(long)[0]
        long_peak = int(long_indices[np.argmax(density[long])]) if len(long_indices) else None
        propagation = (alpha1[peak] + 180.0) % 360.0 if alpha1[peak] < 900 else None
        long_propagation = (alpha1[long_peak] + 180.0) % 360.0 if long_peak is not None and alpha1[long_peak] < 900 else None
        axis = float(scene["range_axis_deg_mod180"])
        top_peaks = []
        for idx in peaks[:5]:
            top_peaks.append({"frequency_hz": float(f[idx]), "period_s": float(1.0 / f[idx]), "density_m2_per_hz": float(density[idx]),
                              "alpha1_from_deg": float(alpha1[idx]), "propagation_to_deg": float((alpha1[idx] + 180.0) % 360.0),
                              "delta_to_range_axis_deg": float(axial_delta((alpha1[idx] + 180.0) % 360.0, axis))})
        output.append({
            "screen_band": scene["screen_band"], "collect_name": case["collect"], "station": case["station"],
            "buoy_distance_km": case["distance_km"], "scene_datetime_utc": scene["datetime_utc"],
            "buoy_observation_utc": case["observation_utc"], "buoy_minus_scene_s": case["time_offset_s"],
            "range_axis_deg_mod180": axis, "spectrum_frequency_bins": len(f),
            "spectral_hs_m": 4.0 * np.sqrt(max(m0, 0.0)), "spectral_peak_frequency_hz": float(f[peak]),
            "spectral_peak_period_s": float(1.0 / f[peak]), "spectral_peak_density_m2_per_hz": float(density[peak]),
            "peak_alpha1_direction_from_deg": float(alpha1[peak]), "peak_propagation_to_deg": propagation,
            "peak_delta_to_range_axis_deg": None if propagation is None else axial_delta(propagation, axis),
            "energy_fraction_f_le_0p1_hz": None if m0 <= 0 else long_m0 / m0,
            "hs_equivalent_f_le_0p1_hz_m": 4.0 * np.sqrt(max(long_m0, 0.0)),
            "long_band_peak_period_s": None if long_peak is None else float(1.0 / f[long_peak]),
            "long_band_peak_propagation_to_deg": long_propagation,
            "long_band_peak_delta_to_range_axis_deg": None if long_propagation is None else axial_delta(long_propagation, axis),
            "directional_fields": "spectral density + alpha1 + alpha2 + r1 + r2",
            "ndbc_direction_convention": "from_true_north_clockwise",
            "top_local_peaks_json": json.dumps(top_peaks, separators=(",", ":")),
            "raw_subset_file": str(case["file"].resolve()),
            "source_url": f"https://dods.ndbc.noaa.gov/thredds/catalog/data/swden/{case['station']}/catalog.html",
        })
    destination = RESULTS / "verified_ndbc_spectra.csv"
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0])); writer.writeheader(); writer.writerows(output)
    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "rows": len(output),
                "direction_reference": "https://www.ndbc.noaa.gov/faq/measdes.shtml",
                "output_csv": str(destination.resolve()), "output_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
    (RESULTS / "VERIFIED_NDBC_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

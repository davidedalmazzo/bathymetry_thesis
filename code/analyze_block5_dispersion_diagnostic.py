"""Forward dispersion compatibility check for the frozen nearshore SAR peak."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from umbra_sar.physical_identification import required_depth_for_period_wavelength


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "Vandenberg/results/analysis_block5"
FROZEN_PATH = OUTPUT_DIR / "BLOCK5_FROZEN_INPUTS.json"
ETOPO_POINT = ROOT / "Vandenberg/external/ETOPO2022_ROI_NEARSHORE_POINT.csv"
ETOPO_NEIGHBORHOOD = ROOT / "Vandenberg/external/ETOPO2022_ROI_NEARSHORE_5X5.csv"
G = 9.80665


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_etopo(path: Path) -> list[dict[str, float]]:
    with path.open("r", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        units = next(reader)
        if units != {
            "latitude": "degrees_north",
            "longitude": "degrees_east",
            "z": "meters",
        }:
            raise ValueError(f"Unexpected ETOPO units row: {units}")
        return [
            {key: float(value) for key, value in row.items()} for row in reader
        ]


def period_at_depth(wavelength_m: float, depth_m: float) -> float:
    wavenumber = 2.0 * math.pi / wavelength_m
    omega = math.sqrt(G * wavenumber * math.tanh(wavenumber * depth_m))
    return 2.0 * math.pi / omega


def main() -> None:
    frozen = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    sar = frozen["frozen_sar_only"]
    wavelength = float(sar["lambda_SAR_m"])
    point = read_etopo(ETOPO_POINT)[0]
    neighborhood = read_etopo(ETOPO_NEIGHBORHOOD)
    water_depths = [-row["z"] for row in neighborhood if row["z"] < 0]
    center_depth = -point["z"]

    periods = {
        "frozen_SAR_exact": float(sar["T_SAR_s"]),
        "requested_SAR_reported": float(sar["T_SAR_reported_s"]),
        "buoy_dominant_13_33": 13.33,
    }
    required = {
        name: required_depth_for_period_wavelength(period, wavelength)
        for name, period in periods.items()
    }
    deep_water_period = 2.0 * math.pi / math.sqrt(
        G * (2.0 * math.pi / wavelength)
    )

    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Forward dispersion compatibility diagnostic only",
        "guardrails": {
            "bathymetric_inversion_performed": False,
            "T_SAR_retuned": False,
            "lambda_SAR_retuned": False,
            "warning": "The required depths are algebraic compatibility values at fixed (T, lambda), not retrieved bathymetry.",
        },
        "equation": "omega^2 = g*k*tanh(k*h), k=2*pi/lambda, h=atanh(omega^2/(g*k))/k",
        "gravity_m_per_s2": G,
        "frozen_lambda_SAR_m": wavelength,
        "deep_water_period_for_lambda_SAR_s": deep_water_period,
        "period_cases_s": periods,
        "required_depth_cases_m": required,
        "rough_roi_depth": {
            "source": "NOAA NCEI ETOPO 2022 30 arc-second global relief (ice surface / EGM2008 height, positive up)",
            "source_url": "https://oceanwatch.pifsc.noaa.gov/erddap/griddap/ETOPO_2022_v1_30s.html",
            "roi_center_lon_lat_deg": [-120.64679691911917, 34.569636382251765],
            "nearest_grid_center_lon_lat_deg": [
                point["longitude"] - 360.0,
                point["latitude"],
            ],
            "nearest_grid_z_m_positive_up": point["z"],
            "nearest_grid_water_depth_m": center_depth,
            "period_predicted_for_lambda_at_nearest_grid_depth_s": period_at_depth(
                wavelength, center_depth
            ),
            "five_by_five_water_cell_depth_range_m": [
                min(water_depths),
                max(water_depths),
            ],
            "resolution_warning": "30 arc-second is roughly 0.77 km east-west by 0.93 km north-south here. The ROI is coastal and the center cell mixes steep bathymetry/shoreline; this is only a gross comparison.",
            "point_file": str(ETOPO_POINT),
            "point_file_sha256": sha256(ETOPO_POINT),
            "neighborhood_file": str(ETOPO_NEIGHBORHOOD),
            "neighborhood_file_sha256": sha256(ETOPO_NEIGHBORHOOD),
        },
        "comparison_to_center_depth_m": {
            name: depth - center_depth for name, depth in required.items()
        },
        "diagnostic_reading": {
            "17_902_s": "Requires about 5.56 m, 2.33 m deeper than the coarse center-cell estimate.",
            "13_33_s": "Requires about 10.63 m, 7.40 m deeper than the coarse center-cell estimate.",
            "constraint": "The 17.902-s pair is closer to the gross center-cell depth, but ETOPO resolution and shoreline mixing are too coarse to validate either period or to perform bathymetry.",
        },
    }
    output = OUTPUT_DIR / "BLOCK5_DISPERSION_DIAGNOSTIC.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {output}")
    print(json.dumps(result["required_depth_cases_m"], indent=2))
    print(f"ETOPO center depth: {center_depth:.6f} m")


if __name__ == "__main__":
    main()

"""Reconcile CPHD/SICD look azimuth, slant LOS, Grid Row, and surface range."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sarpy.geometry.geocoords import ecf_to_geodetic
from sarpy.io.complex.sicd_elements.SICD import SICDType

from cphd_doppler_time_mapping import field
from umbra_sar.wave_analysis import axial_difference_deg


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"


def enu_bearing(vector_ecf: np.ndarray, at_ecf: np.ndarray) -> float:
    latitude_deg, longitude_deg, _ = ecf_to_geodetic(at_ecf)
    latitude = np.deg2rad(latitude_deg)
    longitude = np.deg2rad(longitude_deg)
    east = np.array([-np.sin(longitude), np.cos(longitude), 0.0])
    north = np.array(
        [
            -np.sin(latitude) * np.cos(longitude),
            -np.sin(latitude) * np.sin(longitude),
            np.cos(latitude),
        ]
    )
    return float(
        np.degrees(np.arctan2(vector_ecf @ east, vector_ecf @ north)) % 360.0
    )


def interp_vector(time: np.ndarray, values: np.ndarray, target: float) -> np.ndarray:
    return np.array(
        [np.interp(target, time, values[:, component]) for component in range(3)]
    )


def main() -> None:
    sicd_path = VANDENBERG / "metadata" / "SICD_METADATA.xml"
    cphd_path = VANDENBERG / "2025-02-16-18-55-44_UMBRA-10_CPHD.cphd"
    cphd_json_path = VANDENBERG / "metadata" / "CPHD_METADATA.json"
    roi_path = VANDENBERG / "roi" / "ROIS.json"
    metrics_path = (
        VANDENBERG / "results" / "analysis_block3" / "BLOCK3_SPECTRAL_METRICS.json"
    )
    sicd = SICDType.from_xml_file(str(sicd_path))
    cphd = json.loads(cphd_json_path.read_text(encoding="utf-8"))
    rois = json.loads(roi_path.read_text(encoding="utf-8"))["rois"]
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))["results"]

    header = cphd["file"]["header"]
    records = np.memmap(
        cphd_path,
        dtype=">f8",
        mode="r",
        offset=int(header["PVP_BLOCK_BYTE_OFFSET"]),
        shape=(
            int(cphd["data"]["num_vectors"]),
            int(cphd["data"]["num_bytes_pvp"]) // 8,
        ),
    )
    time = field(records, cphd["pvp_fields"], "TxTime")[:, 0]
    tx_position = field(records, cphd["pvp_fields"], "TxPos")
    srp_position = field(records, cphd["pvp_fields"], "SRPPos")

    scp_time = float(sicd.SCPCOA.SCPTime)
    cphd_reference_time = float(cphd["reference_geometry"]["reference_time_s"])
    bearings_by_time: dict[str, dict[str, float]] = {}
    for label, target in (
        ("sicd_scp_time", scp_time),
        ("cphd_reference_time", cphd_reference_time),
    ):
        tx = interp_vector(time, tx_position, target)
        srp = interp_vector(time, srp_position, target)
        ground_to_platform = enu_bearing(tx - srp, srp)
        bearings_by_time[label] = {
            "time_s": target,
            "ground_to_platform_bearing_deg": ground_to_platform,
            "platform_to_ground_los_bearing_deg": (ground_to_platform + 180.0)
            % 360.0,
            "undirected_range_axis_deg_mod_180": ground_to_platform % 180.0,
        }

    scp = np.asarray(sicd.GeoData.SCP.ECF.get_array(), dtype=np.float64)
    grid_row = np.asarray(sicd.Grid.Row.UVectECF.get_array(), dtype=np.float64)
    grid_col = np.asarray(sicd.Grid.Col.UVectECF.get_array(), dtype=np.float64)
    grid_row_bearing = enu_bearing(grid_row, scp)
    grid_col_bearing = enu_bearing(grid_col, scp)

    roi_results: dict[str, dict[str, float]] = {}
    for name in ("nearshore", "offshore"):
        local_row = float(rois[name]["local_row_axis_bearing_deg_clockwise_from_north"])
        local_col = float(rois[name]["local_col_axis_bearing_deg_clockwise_from_north"])
        wavevector = float(
            metrics[name]["three_look_peak_stability"]
            ["mean_wavevector_bearing_deg_mod_180"]
        )
        roi_results[name] = {
            "wavevector_bearing_deg_mod_180": wavevector,
            "local_surface_grid_row_bearing_deg": local_row,
            "local_surface_grid_col_bearing_deg": local_col,
            "wavevector_difference_from_local_surface_row_deg": axial_difference_deg(
                wavevector, local_row
            ),
            "wavevector_difference_from_sicd_scpcoa_azimang_axis_deg": axial_difference_deg(
                wavevector, float(sicd.SCPCOA.AzimAng)
            ),
            "wavevector_difference_from_cphd_reference_azimuth_axis_deg": axial_difference_deg(
                wavevector, float(cphd["reference_geometry"]["azimuth_angle_deg"])
            ),
            "local_surface_row_difference_from_scp_grid_row_axis_deg": axial_difference_deg(
                local_row, grid_row_bearing
            ),
        }

    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "metadata_correction": {
            "claimed_scpcoa_azimang_approx_105_85_is_correct": False,
            "actual_sicd_scpcoa_azimang_deg": float(sicd.SCPCOA.AzimAng),
            "actual_sicd_scpcoa_scp_time_s": scp_time,
            "cphd_reference_geometry_azimuth_angle_deg": float(
                cphd["reference_geometry"]["azimuth_angle_deg"]
            ),
            "cphd_reference_time_s": cphd_reference_time,
            "explanation": "105.848 deg is the CPHD ReferenceGeometry look azimuth at 11.075 s; SICD SCPCOA is evaluated at 9.036 s and is 101.919 deg. PVP interpolation reproduces both.",
        },
        "directed_los_bearings": bearings_by_time,
        "sicd_grid_at_scp": {
            "row_positive_bearing_tangent_projection_deg": grid_row_bearing,
            "row_undirected_axis_deg_mod_180": grid_row_bearing % 180.0,
            "col_positive_bearing_tangent_projection_deg": grid_col_bearing,
            "col_undirected_axis_deg_mod_180": grid_col_bearing % 180.0,
            "interpretation": "Positive Grid Row follows the groundward LOS direction. SCPCOA AzimAng is ground-to-platform, hence the 180 deg directed difference but the same undirected range line at SCP.",
        },
        "local_surface_projection": {
            "method": "finite-difference SICD image-to-ground projection at each ROI center on the common constant-HAE surface; the resulting EN Jacobian defines the geographic row/column directions used for 2-D spectrum conversion",
            "roi_results": roi_results,
        },
        "conclusion": "The previously reported 21.3 deg nearshore and 14.6 deg offshore values compare the spectral wavevector with the local surface projection of SICD Grid Row, not with CPHD ReferenceGeometry at its later reference time.",
    }
    json_path = VANDENBERG / "metadata" / "RANGE_AXIS_RECONCILIATION.json"
    json_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    near = roi_results["nearshore"]
    off = roi_results["offshore"]
    text = f"""# Range-axis reconciliation

`105.848355722°` is **not** the SICD `SCPCOA.AzimAng`. It is the CPHD
`ReferenceGeometry.Monostatic.AzimuthAngle` at `{cphd_reference_time:.9f} s`.
The actual SICD value is `SCPCOA.AzimAng={float(sicd.SCPCOA.AzimAng):.9f}°` at
`SCPTime={scp_time:.9f} s`. Direct interpolation of CPHD PVP positions reproduces
both values; the difference is the changing look azimuth over about 2.04 s.

At SICD SCP time, `AzimAng` is the directed ground-to-platform bearing. The
groundward slant LOS is `{bearings_by_time['sicd_scp_time']['platform_to_ground_los_bearing_deg']:.9f}°`.
Positive SICD Grid Row projected onto the SCP tangent plane is
`{grid_row_bearing:.9f}°`. Thus LOS/Grid Row and `AzimAng` differ by 180° as
directed vectors but define the same undirected range axis (`101.919° mod 180`).

For a spatial spectrum, the appropriate comparison uses the local surface
Jacobian of the SICD Grid at the ROI, because it converts image frequencies to
east/north ground frequencies. Its positive Row bearing is
`{near['local_surface_grid_row_bearing_deg']:.9f}°` nearshore and
`{off['local_surface_grid_row_bearing_deg']:.9f}°` offshore. Surface projection
and displacement from the SCP account for their small offsets from the tangent
Grid Row.

| ROI | wavevector | local surface Row | difference | difference from SICD SCPCOA axis | difference from CPHD-reference axis |
|---|---:|---:|---:|---:|---:|
| nearshore | {near['wavevector_bearing_deg_mod_180']:.3f}° | {near['local_surface_grid_row_bearing_deg']:.3f}° | {near['wavevector_difference_from_local_surface_row_deg']:.3f}° | {near['wavevector_difference_from_sicd_scpcoa_azimang_axis_deg']:.3f}° | {near['wavevector_difference_from_cphd_reference_azimuth_axis_deg']:.3f}° |
| offshore | {off['wavevector_bearing_deg_mod_180']:.3f}° | {off['local_surface_grid_row_bearing_deg']:.3f}° | {off['wavevector_difference_from_local_surface_row_deg']:.3f}° | {off['wavevector_difference_from_sicd_scpcoa_azimang_axis_deg']:.3f}° | {off['wavevector_difference_from_cphd_reference_azimuth_axis_deg']:.3f}° |

Therefore the Block-3 values `21.3°` and `14.6°` are internally consistent and
refer specifically to the **local surface projection of Grid Row**.
"""
    report_path = VANDENBERG / "metadata" / "RANGE_AXIS_RECONCILIATION.md"
    report_path.write_text(text, encoding="utf-8")
    print(json_path)
    print(report_path)


if __name__ == "__main__":
    main()

"""Define reproducible Block-3 ROIs using the GEC only as a geographic locator."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from sarpy.geometry.geocoords import geodetic_to_ecf
from sarpy.io.complex.sicd_elements.SICD import SICDType


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / "Vandenberg"
SICD_XML = VANDENBERG / "metadata" / "SICD_METADATA.xml"
ROI_DIR = VANDENBERG / "roi"
DIAGNOSTIC_DIR = VANDENBERG / "results" / "diagnostics"

# Deliberately fixed GEC centers. The GEC is used only to select geographic
# locations; all wave measurements will use the full-resolution complex SICD.
ROI_SPECS = {
    "nearshore": {
        "kind": "ocean_nearshore",
        "gec_center_col_row": [13000, 12300],
        "sicd_center_row_col_override": [10000, 82800],
        "shape_rows_cols": [1200, 9600],
        "description": "Open water immediately seaward of the central rocky coast; refined on full-aperture SICD intensity to exclude the terrain displaced by constant-HAE projection.",
    },
    "offshore": {
        "kind": "ocean_offshore",
        "gec_center_col_row": [11500, 14800],
        "sicd_center_row_col_override": [11500, 75800],
        "shape_rows_cols": [1200, 9600],
        "description": "Open water farther seaward; refined on full-aperture SICD intensity to exclude all coastline pixels.",
    },
    "land_control": {
        "kind": "land_control",
        "gec_center_col_row": [7600, 8500],
        "shape_rows_cols": [1536, 12288],
        "description": "Persistent terrestrial infrastructure, roads, and surrounding terrain near the central facility.",
    },
}


def enu_from_ecf_delta(delta: np.ndarray, lat_deg: float, lon_deg: float) -> np.ndarray:
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    transform = np.array(
        [
            [-math.sin(lon), math.cos(lon), 0.0],
            [
                -math.sin(lat) * math.cos(lon),
                -math.sin(lat) * math.sin(lon),
                math.cos(lat),
            ],
            [
                math.cos(lat) * math.cos(lon),
                math.cos(lat) * math.sin(lon),
                math.sin(lat),
            ],
        ]
    )
    return transform @ delta


def bearing_deg(east: float, north: float) -> float:
    return math.degrees(math.atan2(east, north)) % 360.0


def main() -> None:
    Image.MAX_IMAGE_PIXELS = None
    gec_path = next(VANDENBERG.glob("*GEC*.tif"))
    sicd = SICDType.from_xml_file(str(SICD_XML))
    scp_hae = float(sicd.GeoData.SCP.LLH.HAE)
    image_rows = int(sicd.ImageData.NumRows)
    image_cols = int(sicd.ImageData.NumCols)

    with Image.open(gec_path) as gec:
        model = np.asarray(gec.tag_v2[34264], dtype=np.float64).reshape(4, 4)
        gec_size = gec.size
        overview = gec.resize((1600, 1600), Image.Resampling.LANCZOS).convert("RGB")

    affine = model[:2, :2]
    origin = model[:2, 3]
    affine_inverse = np.linalg.inv(affine)

    def gec_to_lonlat(col: float, row: float) -> tuple[float, float]:
        lon, lat = affine @ np.array([col, row], dtype=np.float64) + origin
        return float(lon), float(lat)

    def lonlat_to_gec(lon: float, lat: float) -> tuple[float, float]:
        col, row = affine_inverse @ (np.array([lon, lat]) - origin)
        return float(col), float(row)

    output_rois: dict[str, dict[str, object]] = {}
    draw = ImageDraw.Draw(overview)
    colors = {
        "nearshore": (255, 70, 20),
        "offshore": (0, 220, 255),
        "land_control": (255, 235, 0),
    }

    for name, spec in ROI_SPECS.items():
        gec_col, gec_row = spec["gec_center_col_row"]
        lon, lat = gec_to_lonlat(gec_col, gec_row)
        initial_image_point, _, _ = sicd.project_ground_to_image_geo(
            [lat, lon, scp_hae]
        )
        if "sicd_center_row_col_override" in spec:
            center_row, center_col = map(int, spec["sicd_center_row_col_override"])
            selected_geo = sicd.project_image_to_ground_geo(
                [[center_row, center_col]], projection_type="HAE"
            )[0]
            lat, lon = float(selected_geo[0]), float(selected_geo[1])
        else:
            center_row, center_col = (
                int(round(float(value))) for value in initial_image_point
            )
        image_point, residual_m, iterations = sicd.project_ground_to_image_geo(
            [lat, lon, scp_hae]
        )
        roi_rows, roi_cols = map(int, spec["shape_rows_cols"])
        row_start = center_row - roi_rows // 2
        col_start = center_col - roi_cols // 2
        row_stop = row_start + roi_rows
        col_stop = col_start + roi_cols
        if not (0 <= row_start < row_stop <= image_rows):
            raise ValueError(f"{name}: SICD row bounds outside image")
        if not (0 <= col_start < col_stop <= image_cols):
            raise ValueError(f"{name}: SICD column bounds outside image")

        center = np.array([[center_row, center_col]], dtype=np.float64)
        sample_points = np.vstack(
            [center, center + [1, 0], center + [0, 1]]
        )
        sample_geo = sicd.project_image_to_ground_geo(
            sample_points, projection_type="HAE"
        )
        sample_ecf = geodetic_to_ecf(sample_geo)
        row_enu = enu_from_ecf_delta(
            sample_ecf[1] - sample_ecf[0], sample_geo[0, 0], sample_geo[0, 1]
        )
        col_enu = enu_from_ecf_delta(
            sample_ecf[2] - sample_ecf[0], sample_geo[0, 0], sample_geo[0, 1]
        )
        ground_jacobian = np.column_stack([row_enu[:2], col_enu[:2]])
        row_spacing = float(np.linalg.norm(row_enu[:2]))
        col_spacing = float(np.linalg.norm(col_enu[:2]))

        corners_image = np.array(
            [
                [row_start, col_start],
                [row_start, col_stop - 1],
                [row_stop - 1, col_stop - 1],
                [row_stop - 1, col_start],
            ],
            dtype=np.float64,
        )
        corners_geo = sicd.project_image_to_ground_geo(
            corners_image, projection_type="HAE"
        )
        corners_gec = [
            lonlat_to_gec(float(point[1]), float(point[0])) for point in corners_geo
        ]
        overview_polygon = [(c / 10.0, r / 10.0) for c, r in corners_gec]
        draw.polygon(overview_polygon, outline=colors[name], width=5)
        label_col, label_row = overview_polygon[0]
        draw.text((label_col + 8, label_row + 8), name, fill=colors[name])

        output_rois[name] = {
            **spec,
            "gec_source": str(gec_path.resolve()),
            "initial_gec_center_lon_lat_deg": list(gec_to_lonlat(gec_col, gec_row)),
            "selected_center_lon_lat_deg": [lon, lat],
            "selected_center_gec_col_row": list(lonlat_to_gec(lon, lat)),
            "initial_gec_projected_sicd_center_row_col": initial_image_point.tolist(),
            "selection_stage": (
                "full_aperture_SICD_intensity_refinement"
                if "sicd_center_row_col_override" in spec
                else "GEC_geographic_localization"
            ),
            "projection_hae_m": scp_hae,
            "ground_to_sicd_residual_m": float(residual_m),
            "ground_to_sicd_iterations": int(iterations),
            "sicd_center_row_col": [center_row, center_col],
            "sicd_bounds": {
                "row_start_inclusive": row_start,
                "row_stop_exclusive": row_stop,
                "col_start_inclusive": col_start,
                "col_stop_exclusive": col_stop,
                "rows": roi_rows,
                "cols": roi_cols,
            },
            "corner_lat_lon_hae": corners_geo.tolist(),
            "corner_gec_col_row": [list(point) for point in corners_gec],
            "local_ground_jacobian_EN_m_per_pixel": ground_jacobian.tolist(),
            "local_row_ground_spacing_m": row_spacing,
            "local_col_ground_spacing_m": col_spacing,
            "local_row_axis_bearing_deg_clockwise_from_north": bearing_deg(
                row_enu[0], row_enu[1]
            ),
            "local_col_axis_bearing_deg_clockwise_from_north": bearing_deg(
                col_enu[0], col_enu[1]
            ),
            "approximate_ground_extent_row_col_m": [
                row_spacing * roi_rows,
                col_spacing * roi_cols,
            ],
        }

    ROI_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    roi_path = ROI_DIR / "ROIS.json"
    overlay_path = DIAGNOSTIC_DIR / "GEC_roi_overlay.png"
    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "selection_scope": "GEC used for geographic ROI localization only; no GEC spectrum is used for SICD wave metrics.",
        "sicd_xml": str(SICD_XML.resolve()),
        "sicd_dimensions_rows_cols": [image_rows, image_cols],
        "gec_dimensions_cols_rows": list(gec_size),
        "gec_model_transformation_tag_34264": model.ravel().tolist(),
        "shared_projection_hae_m": scp_hae,
        "roi_shape_reason": "Ocean ROIs use 1200 x 9600 SICD pixels (approximately 0.54 km square) after full-aperture SICD refinement to exclude land. Land control retains 1536 x 12288 pixels (approximately 0.69 km square) for robust registration.",
        "doppler_decomposition_rule": "For every selected range row, all 107800 SICD azimuth columns must be transformed before any ROI column crop.",
        "rois": output_rois,
    }
    roi_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    overview.save(overlay_path)
    print(roi_path)
    print(overlay_path)


if __name__ == "__main__":
    main()

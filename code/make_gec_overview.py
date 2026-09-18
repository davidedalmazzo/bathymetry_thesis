"""Create a lightweight GEC overview and record its affine lon/lat transform."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / 'umbra/Vandenberg'
OUT_DIR = VANDENBERG / "results" / "diagnostics"


def main() -> None:
    Image.MAX_IMAGE_PIXELS = None
    source = next(VANDENBERG.glob("*GEC*.tif"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        matrix = tuple(float(v) for v in image.tag_v2[34264])
        source_size = image.size
        overview = image.resize((1600, 1600), Image.Resampling.LANCZOS)
        detail_specs = {
            "GEC_detail_coast_ocean.png": (8000, 8000, 16001, 16001),
            "GEC_detail_land.png": (4500, 5500, 10500, 11500),
        }
        details = {
            name: image.crop(box).resize((1600, 1600), Image.Resampling.LANCZOS)
            for name, box in detail_specs.items()
        }

    overview = overview.convert("RGB")
    draw = ImageDraw.Draw(overview)
    for value in range(0, 1601, 200):
        draw.line((value, 0, value, 1600), fill=(255, 80, 40), width=1)
        draw.line((0, value, 1600, value), fill=(255, 80, 40), width=1)
        if value < 1600:
            draw.text((value + 4, 4), f"c={value * 10}", fill=(255, 80, 40))
            draw.text((4, value + 4), f"r={value * 10}", fill=(255, 80, 40))
    overview_path = OUT_DIR / "GEC_overview_grid.png"
    overview.save(overview_path)

    for name, detail in details.items():
        box = detail_specs[name]
        detail = detail.convert("RGB")
        detail_draw = ImageDraw.Draw(detail)
        scale_col = (box[2] - box[0]) / 1600
        scale_row = (box[3] - box[1]) / 1600
        for value in range(0, 1601, 200):
            detail_draw.line((value, 0, value, 1600), fill=(255, 80, 40), width=1)
            detail_draw.line((0, value, 1600, value), fill=(255, 80, 40), width=1)
            if value < 1600:
                source_col = round(box[0] + value * scale_col)
                source_row = round(box[1] + value * scale_row)
                detail_draw.text((value + 4, 4), f"c={source_col}", fill=(255, 80, 40))
                detail_draw.text((4, value + 4), f"r={source_row}", fill=(255, 80, 40))
        detail.save(OUT_DIR / name)

    def lonlat(col: float, row: float) -> tuple[float, float]:
        lon = matrix[0] * col + matrix[1] * row + matrix[3]
        lat = matrix[4] * col + matrix[5] * row + matrix[7]
        return lon, lat

    metadata = {
        "source": str(source.resolve()),
        "source_size_col_row": list(source_size),
        "overview": str(overview_path.resolve()),
        "detail_crops_source_boxes_col0_row0_col1_row1": {
            name: list(box) for name, box in detail_specs.items()
        },
        "overview_scale_source_pixels_per_pixel": 10.0,
        "model_transformation_tag_34264": list(matrix),
        "coordinate_reference_system": "EPSG:4326 (from GeoKeyDirectoryTag)",
        "pixel_to_lonlat": {
            "lon": "m00*col + m01*row + m03",
            "lat": "m10*col + m11*row + m13",
        },
        "corners_lonlat": {
            "upper_left": lonlat(0, 0),
            "upper_right": lonlat(source_size[0] - 1, 0),
            "lower_left": lonlat(0, source_size[1] - 1),
            "lower_right": lonlat(source_size[0] - 1, source_size[1] - 1),
            "center": lonlat((source_size[0] - 1) / 2, (source_size[1] - 1) / 2),
        },
    }
    metadata_path = OUT_DIR / "GEC_georeference.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(overview_path)
    print(metadata_path)


if __name__ == "__main__":
    main()

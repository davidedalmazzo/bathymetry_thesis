"""Plan nested, rotated, all-water Block-7 nearshore ROIs from the NOAA 1 m DEM.

The DEM is used only as an independent coastline/depth constraint.  Spectra use
rectangular support (no bathymetric mask), so the window leakage is explicit.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.merge import merge


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / 'umbra/Vandenberg'
OUT = VANDENBERG / "results" / "analysis_block7"
BATHY = VANDENBERG / "bathymetry"
FROZEN_BEARING_DEG = 79.8357237
ORIGINAL_UTM_EN = np.array([716210.6102416331, 3827777.0937420740])
ORIGINAL_SICD_RC = np.array([10000.0, 82800.0])
JAC_EN_PER_RC = np.array(
    [[-0.4428968144347891, -0.009929984691552818],
     [0.07684305729344487, -0.055618567392230034]], dtype=float
)
SICD_SHAPE = (13310, 107800)


def unit(bearing_deg: float) -> np.ndarray:
    angle = math.radians(bearing_deg)
    return np.array([math.sin(angle), math.cos(angle)])


def sample_nearest(z: np.ndarray, transform, east: np.ndarray, north: np.ndarray) -> np.ndarray:
    col = np.floor((east - transform.c) / transform.a).astype(int)
    row = np.floor((north - transform.f) / transform.e).astype(int)
    result = np.full(east.shape, np.nan, dtype=np.float32)
    good = (row >= 0) & (row < z.shape[0]) & (col >= 0) & (col < z.shape[1])
    result[good] = z[row[good], col[good]]
    return result


def rectangle_grid(center: np.ndarray, lp: float, lt: float, spacing: float = 10.0):
    up = unit(FROZEN_BEARING_DEG)
    ut = unit(FROZEN_BEARING_DEG + 90.0)
    p = np.linspace(-lp / 2, lp / 2, max(3, int(lp / spacing) + 1))
    q = np.linspace(-lt / 2, lt / 2, max(3, int(lt / spacing) + 1))
    pp, qq = np.meshgrid(p, q)
    en = center[:, None, None] + up[:, None, None] * pp + ut[:, None, None] * qq
    return en, up, ut


def sicd_bounds(en: np.ndarray) -> tuple[list[int], bool]:
    delta = en.reshape(2, -1) - ORIGINAL_UTM_EN[:, None]
    rc = ORIGINAL_SICD_RC[:, None] + np.linalg.solve(JAC_EN_PER_RC, delta)
    margin = np.array([8.0, 32.0])[:, None]
    lower = np.floor(np.min(rc, axis=1) - margin[:, 0]).astype(int)
    upper = np.ceil(np.max(rc, axis=1) + margin[:, 0]).astype(int)
    inside = bool(np.all(lower >= 0) and np.all(upper <= np.array(SICD_SHAPE)))
    lower = np.maximum(lower, 0)
    upper = np.minimum(upper, np.array(SICD_SHAPE))
    return [int(lower[0]), int(upper[0]), int(lower[1]), int(upper[1])], inside


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = sorted(BATHY.glob("10SGD*.tif"))
    datasets = [rasterio.open(path) for path in paths]
    try:
        merged, transform = merge(datasets, nodata=np.nan, dtype="float32")
    finally:
        for dataset in datasets:
            dataset.close()
    z = merged[0]

    # Search a common centre for a large rectangle.  The original centre must
    # remain inside it and displacement is penalised to preserve the same field.
    lt = 650.0
    candidates = []
    for lp_max in [1800.0, 1620.0, 1440.0, 1260.0, 1080.0, 900.0]:
        for de in np.arange(-900.0, 251.0, 25.0):
            for dn in np.arange(-650.0, 251.0, 25.0):
                center = ORIGINAL_UTM_EN + [de, dn]
                en, up, ut = rectangle_grid(center, lp_max, lt, spacing=10.0)
                values = sample_nearest(z, transform, en[0], en[1])
                original_local = np.array([np.dot(ORIGINAL_UTM_EN-center, up), np.dot(ORIGINAL_UTM_EN-center, ut)])
                contains_original = abs(original_local[0]) <= lp_max/2 and abs(original_local[1]) <= lt/2
                all_water = bool(np.all(np.isfinite(values)) and np.max(values) < -2.0)
                bounds, inside = sicd_bounds(en)
                if contains_original and all_water and inside:
                    # Prefer minimal displacement, then smaller depth spread.
                    score = float(np.hypot(de, dn) + 0.25 * (np.percentile(values, 95)-np.percentile(values, 5)))
                    candidates.append((score, center, values, bounds))
        if candidates:
            break
    if not candidates:
        raise RuntimeError("No >=900 x 650 m all-water rectangle containing the original ROI found")
    _, common_center, _, maximal_bounds = min(candidates, key=lambda item: item[0])

    records = []
    lengths = [value for value in [540.0, 720.0, 900.0, 1080.0, 1260.0, 1440.0, 1620.0, 1800.0] if value <= lp_max]
    for index, lp in enumerate(lengths, 1):
        en, up, ut = rectangle_grid(common_center, lp, lt, spacing=5.0)
        values = sample_nearest(z, transform, en[0], en[1])
        bounds, inside = sicd_bounds(en)
        records.append({
            "roi_index": index,
            "name": f"rot_k_{int(lp):04d}x{int(lt):04d}",
            "center_utm_e_n_m": common_center.tolist(),
            "L_parallel_m": lp,
            "L_perpendicular_m": lt,
            "orientation_wavevector_bearing_deg_mod_180": FROZEN_BEARING_DEG,
            "native_delta_k_parallel_rad_per_m": 2*math.pi/lp,
            "native_delta_f_parallel_cycles_per_m": 1/lp,
            "nominal_wavelengths_at_130_6": lp/130.6028192373831,
            "all_samples_finite": bool(np.all(np.isfinite(values))),
            "maximum_elevation_NAVD88_m": float(np.nanmax(values)),
            "minimum_depth_positive_down_NAVD88_m": float(-np.nanmax(values)),
            "depth_percentiles_positive_down_NAVD88_m": (-np.nanpercentile(values, [95, 75, 50, 25, 5])).tolist(),
            "sicd_bounding_rows_cols": bounds,
            "sicd_inside_image": inside,
        })

    # Original 540 m square is retained as a separate baseline.
    original_en, _, _ = rectangle_grid(ORIGINAL_UTM_EN, 540.0, 540.0, spacing=5.0)
    original_z = sample_nearest(z, transform, original_en[0], original_en[1])
    document = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Nested rotated rectangular spectral supports; DEM is not used as an irregular spectral mask.",
        "frozen_wavevector_bearing_deg_mod_180": FROZEN_BEARING_DEG,
        "geolocation_surface": {"projection_HAE_m": -36.376, "source": "NOAA GEOID18 at original ROI; HAE=N for NAVD88 zero", "geoid_model_error_m": 0.032,
            "warning": "This replaces the SCP-HAE (+101.525 m) locator used in earlier display-only ROI metadata."},
        "water_acceptance": "Every 5 m grid sample finite and DEM elevation < -2 m NAVD88; 10 m grid used in centre search.",
        "common_center_utm_e_n_m": common_center.tolist(),
        "common_center_shift_from_original_e_n_m": (common_center-ORIGINAL_UTM_EN).tolist(),
        "maximal_sicd_bounding_rows_cols": maximal_bounds,
        "original_baseline": {
            "center_utm_e_n_m": ORIGINAL_UTM_EN.tolist(), "L_parallel_m": 540.0,
            "L_perpendicular_m": 540.0, "maximum_elevation_NAVD88_m": float(np.nanmax(original_z)),
        },
        "candidate_rois": records,
        "zero_padding_policy": "Allowed only to interpolate a maximum; native radial resolution remains approximately 2*pi/L_parallel.",
        "bathymetry_tiles": [str(path.resolve()) for path in paths],
    }
    (OUT / "BLOCK7_ROI_SUPPORT_PLAN.json").write_text(json.dumps(document, indent=2), encoding="utf-8")

    # Context map with maximum and original supports.
    fig, ax = plt.subplots(figsize=(9, 8), constrained_layout=True)
    extent = [transform.c, transform.c+transform.a*z.shape[1], transform.f+transform.e*z.shape[0], transform.f]
    image = ax.imshow(z, extent=extent, origin="upper", cmap="terrain", vmin=-40, vmax=40)
    for center, lp, width, color, label in [
        (ORIGINAL_UTM_EN, 540, 540, "white", "original ~540 m"),
        (common_center, lp_max, lt, "magenta", f"maximum {int(lp_max)} x 650 m"),
    ]:
        up=unit(FROZEN_BEARING_DEG);ut=unit(FROZEN_BEARING_DEG+90)
        corners=np.column_stack([center+up*p+ut*q for p,q in [(-lp/2,-width/2),(lp/2,-width/2),(lp/2,width/2),(-lp/2,width/2),(-lp/2,-width/2)]])
        ax.plot(corners[0], corners[1], color=color, lw=2, label=label)
    ax.contour(np.linspace(extent[0],extent[1],z.shape[1]), np.linspace(extent[3],extent[2],z.shape[0]), z, levels=[-2,0], colors=["cyan","black"], linewidths=[1,1])
    ax.scatter(*ORIGINAL_UTM_EN, c="white", s=25)
    ax.set(xlabel="UTM 10N easting (m)", ylabel="UTM 10N northing (m)", title="Block 7 spectral supports on NOAA California Topobathy (m NAVD88)")
    ax.legend(loc="lower left")
    fig.colorbar(image, ax=ax, label="Elevation (m NAVD88)")
    fig.savefig(OUT / "BLOCK7_ROI_SUPPORT_BATHYMETRY.png", dpi=180)
    plt.close(fig)
    print(json.dumps({"common_center": common_center.tolist(), "bounds": maximal_bounds, "n_candidates": len(records)}, indent=2))


if __name__ == "__main__":
    main()

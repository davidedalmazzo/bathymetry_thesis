"""Recover the width-formation manifest after spectra completed successfully."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from umbra_sar.subaperture import make_window


ROOT = Path(__file__).resolve().parents[1]
V = ROOT / 'umbra/Vandenberg'
OUT = V / "results/analysis_block5"
NPZ = OUT / "BLOCK5_WIDTH_SENSITIVITY_SPECTRA.npz"
JSON_PATH = OUT / "BLOCK5_WIDTH_FORMATION.json"


def main() -> None:
    if JSON_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite {JSON_PATH}")
    archive = np.load(NPZ)
    spectra = archive["spectra"]
    if spectra.shape != (3, 9, 129, 129) or not np.all(np.isfinite(spectra)):
        raise ValueError("The completed spectrum archive failed integrity checks")
    plan = json.loads((V / "metadata/BLOCK4_SLIDING_LOOK_PLAN.json").read_text())
    fixed = json.loads((V / "metadata/SUBAPERTURE_PLAN_6S.json").read_text())
    look_plan = {int(item["chronological_index"]): item for item in plan["looks_chronological"]}
    support_size = int(fixed["support"]["size"])
    processed = float(plan["durations_kept_distinct"]["sicd_processed_aperture_duration_s"])
    records = []
    for width in archive["widths_s"]:
        width = float(width)
        width_bins = int(round(support_size * width / processed))
        if width_bins % 2:
            width_bins += 1
        _, metrics = make_window(
            width_bins, "tukey", tukey_alpha=0.25, normalization="energy"
        )
        bands = []
        for index in archive["chronological_indices"]:
            original = look_plan[int(index)]["band"]
            center = 0.5 * (int(original["start_inclusive"]) + int(original["stop_exclusive"]))
            start = int(round(center - 0.5 * width_bins))
            bands.append({"start_inclusive": start, "stop_exclusive": start + width_bins})
        records.append(
            {
                "width_s": width,
                "width_bins": width_bins,
                "realized_nominal_width_s": width_bins / support_size * processed,
                "bands": bands,
                "window": asdict(metrics),
                "source": (
                    "reused Block-4 complex looks"
                    if width == 6.0
                    else "new nearshore-only formation from full SICD azimuth extent"
                ),
                "azimuth_pre_crop_before_doppler_decomposition": False,
                "spectrum_shape": list(spectra[list(archive["widths_s"]).index(width)].shape),
            }
        )
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Moderate local look-width sensitivity, not a dwell sweep",
        "source_sicd": str((V / "2025-02-16-18-55-44_UMBRA-10_SICD.nitf").resolve()),
        "source_sicd_size_bytes": (V / "2025-02-16-18-55-44_UMBRA-10_SICD.nitf").stat().st_size,
        "widths_s": archive["widths_s"].tolist(),
        "common_chronological_indices": archive["chronological_indices"].tolist(),
        "physical_center_times_s": archive["physical_center_times_s"].tolist(),
        "edge_centers_excluded": [1, 11],
        "edge_exclusion_reason": "6.5-s support exceeds the processed SICD support at centers 1 and 11",
        "formation_records": records,
        "output_npz": str(NPZ.resolve()),
        "recovery_note": "The numerical formation and NPZ write completed; only JSON serialization of WindowMetrics failed. This manifest was reconstructed from the verified NPZ and immutable plans without repeating radar processing.",
        "temporary_work_directory_empty_after_success": not any((OUT / "_width_work").iterdir()),
        "guardrails": {
            "full_dwell_sweep_performed": False,
            "bathymetric_inversion_performed": False,
            "complex_sublook_files_persisted": False,
            "only_derived_spectrum_crops_persisted": True,
        },
    }
    JSON_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {JSON_PATH}")


if __name__ == "__main__":
    main()

"""Freeze the SAR-only Block-5 inputs before consulting buoy spectra."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLOCK4 = ROOT / "Vandenberg/results/analysis_block4/BLOCK4_PHASE_METRICS_SAR_ONLY.json"
BLOCK3 = ROOT / "Vandenberg/results/analysis_block3/BLOCK3_SPECTRAL_METRICS.json"
OUTPUT = ROOT / "Vandenberg/results/analysis_block5/BLOCK5_FROZEN_INPUTS.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    block4 = json.loads(BLOCK4.read_text(encoding="utf-8"))
    block3 = json.loads(BLOCK3.read_text(encoding="utf-8"))
    near4 = block4["results"]["nearshore"]
    primary = near4["primary_fixed_patch_phase"]["fit_direct_reference_phase"]
    near3 = block3["results"]["nearshore"]["three_look_peak_stability"]

    frozen = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Immutable SAR-only inputs for Block 5 physical identification",
        "source_files": {
            "block4_sar_only": str(BLOCK4),
            "block4_sar_only_sha256": sha256(BLOCK4),
            "block3_spectral_metrics": str(BLOCK3),
            "block3_spectral_metrics_sha256": sha256(BLOCK3),
        },
        "external_data_used_to_select_or_fit_these_values": False,
        "frozen_sar_only": {
            "omega_rad_per_s": primary["slope_rad_per_s"],
            "T_SAR_s": primary["period_s"],
            "T_SAR_reported_s": 17.902,
            "fit_only_period_95_percent_ci_s": primary[
                "period_95_percent_ci_fit_only_s"
            ],
            "lambda_SAR_m": near3["mean_wavelength_m"],
            "theta_SAR_wavevector_bearing_deg_mod_180": near3[
                "mean_wavevector_bearing_deg_mod_180"
            ],
            "cross_spectrum_convention": "F_secondary * conj(F_reference)",
        },
        "guardrails": {
            "T_SAR_must_not_be_retuned_to_external_data": True,
            "no_full_dwell_sweep": True,
            "no_bathymetric_inversion": True,
            "dispersion_depth_is_diagnostic_forward_compatibility_only": True,
            "sensitivity_look_widths_s": [5.5, 6.0, 6.5],
        },
    }
    if frozen["source_files"]["block4_sar_only_sha256"] != (
        "c399af008e2159ede9b6e27b8bf99dffdd17b7f808aa263ea569d20438df8fcd"
    ):
        raise RuntimeError("The Block-4 SAR-only artifact changed before the freeze")
    if abs(frozen["frozen_sar_only"]["T_SAR_s"] - 17.902230457045317) > 1e-12:
        raise RuntimeError("Unexpected Block-4 SAR-only period")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(frozen, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"Frozen Block-4 SHA256: {frozen['source_files']['block4_sar_only_sha256']}")
    print(f"Frozen T_SAR: {frozen['frozen_sar_only']['T_SAR_s']:.12f} s")


if __name__ == "__main__":
    main()

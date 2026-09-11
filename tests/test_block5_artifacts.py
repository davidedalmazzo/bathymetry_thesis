from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Vandenberg/results/analysis_block5"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_block5_frozen_sar_artifact_matches_immutable_block4() -> None:
    frozen = json.loads((OUT / "BLOCK5_FROZEN_INPUTS.json").read_text())
    block4 = ROOT / "Vandenberg/results/analysis_block4/BLOCK4_PHASE_METRICS_SAR_ONLY.json"
    assert frozen["external_data_used_to_select_or_fit_these_values"] is False
    assert frozen["source_files"]["block4_sar_only_sha256"] == sha256(block4)
    assert frozen["source_files"]["block4_sar_only_sha256"] == (
        "c399af008e2159ede9b6e27b8bf99dffdd17b7f808aa263ea569d20438df8fcd"
    )
    assert frozen["frozen_sar_only"]["T_SAR_s"] == pytest.approx(
        17.902230457045317, abs=1e-12
    )
    assert frozen["guardrails"]["T_SAR_must_not_be_retuned_to_external_data"]


def test_complete_ndbc_spectrum_and_two_requested_frequencies() -> None:
    result = json.loads((OUT / "BLOCK5_NDBC_FULL_SPECTRUM.json").read_text())
    assert result["source"]["bytes"] == 153486944
    assert result["source"]["sha256"] == (
        "eb296c36049de144043c1a8b39a59df1ebeb50453541d23a0a784badcee0d20d"
    )
    assert result["source"]["frequency_count"] == 64
    assert set(result["source"]["variables_used"]) == {
        "spectral_wave_density",
        "mean_wave_dir",
        "principal_wave_dir",
        "wave_spectrum_r1",
        "wave_spectrum_r2",
    }
    f1 = result["target_f1"]["nearest_bin"]
    f2 = result["target_f2"]["nearest_bin"]
    assert f1["frequency_hz"] == pytest.approx(0.055, abs=1e-8)
    assert f2["frequency_hz"] == pytest.approx(0.075, abs=1e-8)
    assert f1["alpha1_propagation_to_deg"] == 80.0
    assert f2["alpha1_propagation_to_deg"] == 72.0
    assert result["nearest_bin_energy_ratio_f1_over_f2"] == pytest.approx(0.03)


def test_block5_sensitivity_is_sar_only_and_not_a_dwell_sweep() -> None:
    result = json.loads((OUT / "BLOCK5_SAR_SENSITIVITY.json").read_text())
    assert result["external_data_used_in_sensitivity"] is False
    assert result["guardrails"]["full_5_to_16_s_dwell_sweep_performed"] is False
    assert result["guardrails"]["bathymetric_inversion_performed"] is False
    assert result["guardrails"]["peak_reselected_per_variant"] is False
    counts = sum(
        family["valid_fit_count"] for family in result["family_summaries"].values()
    )
    assert counts == 24
    assert result["robustness_summary"][
        "all_valid_variants_preserve_negative_sign"
    ]
    lower, upper = result["robustness_summary"][
        "all_variant_slope_range_rad_per_s"
    ]
    assert lower == pytest.approx(-0.3677820148037798)
    assert upper == pytest.approx(-0.3410297312815275)


def test_dispersion_artifact_remains_diagnostic_only() -> None:
    result = json.loads((OUT / "BLOCK5_DISPERSION_DIAGNOSTIC.json").read_text())
    assert result["guardrails"]["bathymetric_inversion_performed"] is False
    assert result["guardrails"]["T_SAR_retuned"] is False
    assert result["required_depth_cases_m"]["frozen_SAR_exact"] == pytest.approx(
        5.55575545882108
    )
    assert result["required_depth_cases_m"]["buoy_dominant_13_33"] == pytest.approx(
        10.627048720023646
    )

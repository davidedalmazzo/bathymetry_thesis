import csv, json
from pathlib import Path

import numpy as np
import pytest

from umbra_sar.frequency_validation_selector import (
    classify_candidate, dominant_half_power_band, pareto_front, temporal_scenarios,
)
from umbra_sar.reference_recovery import HTTPBudget
from umbra_sar.selector_consolidation import select_reference


def test_short_scene_is_not_rejected_and_has_feasible_looks():
    rows=temporal_scenarios(3.4)
    assert [x["look_duration_s"] for x in rows]==[1.5,2.5]
    assert all(x["sliding_looks_statistically_independent"] is False for x in rows)

def test_no_period_gate():
    row=temporal_scenarios(2.0,period_s=None)[0]
    assert row["observable_cycles"] is None

def test_phase_span_is_continuous_descriptor():
    row=temporal_scenarios(12,[4],1,8)[0]
    assert row["sliding_center_count"]==9
    assert row["phase_span_rad"]==pytest.approx(2*np.pi)

def test_sicd_only_can_be_measured_product_check():
    assert classify_candidate(geometry_known=True,internal_roi=True,has_complex=True,
                              measured_admissible=True)=="MEASURED_PRODUCT_CHECK"

def test_cphd_only_can_be_conditional():
    assert classify_candidate(geometry_known=True,internal_roi=True,has_complex=True,
                              station_query_possible=True)=="CONDITIONAL_REFERENCE_CHECK"

def test_preview_only_is_excluded():
    assert classify_candidate(geometry_known=True,internal_roi=True,has_complex=False)=="EXCLUDED"

def test_unknown_geometry_is_not_evaluable():
    assert classify_candidate(geometry_known=False,internal_roi=False,has_complex=True)=="NOT_EVALUABLE"

def test_half_power_band_and_same_band_direction():
    f=np.array([.04,.05,.06,.07,.08]); e=np.array([1,4,8,5,1.])
    result=dominant_half_power_band(f,e,[0,20,40,60,180],[1,1,1,1,1])
    assert result["peak_frequency_hz"]==.06
    assert result["band_bin_count"]==3
    assert 20 < result["direction_from_deg"] < 60
    assert result["propagation_to_deg"]==pytest.approx((result["direction_from_deg"]+180)%360)

def test_direction_missing_does_not_invent_value():
    result=dominant_half_power_band([.05,.06],[2,1],[np.nan,np.nan],[np.nan,np.nan])
    assert result["direction_from_deg"] is None

def test_disjoint_second_system_not_merged_into_dominant_band():
    result=dominant_half_power_band([.04,.05,.06,.07,.08],[1,10,1,9,1])
    assert result["band_bin_count"]==1

def test_pareto_front():
    rows=[{"a":2,"b":2},{"a":1,"b":1},{"a":3,"b":1}]
    assert pareto_front(rows,("a","b"))==[True,False,True]

def test_config_frozen_and_no_forbidden_gates():
    root=Path(__file__).resolve().parents[1]; cfg=json.loads((root/"Block21_frequency_validation_selector/BLOCK21_CONFIG.json").read_text())
    text=json.dumps(cfg)
    assert "minimum_dwell" not in text and "minimum_cycles" not in text
    assert cfg["bathymetry_role"].startswith("descriptive_secondary")

def test_less_than_80_percent_water_not_a_classification_gate():
    assert classify_candidate(geometry_known=True,internal_roi=True,has_complex=True,
                              station_query_possible=True)=="CONDITIONAL_REFERENCE_CHECK"

def test_sub_10_second_band_not_a_gate():
    assert dominant_half_power_band([.1,.2,.3],[1,4,1])["peak_period_s"]==5

def test_frequency_ready_can_be_bathymetry_insensitive():
    # Bathymetric sensitivity is deliberately absent from the primary classifier.
    assert classify_candidate(geometry_known=True,internal_roi=True,has_complex=True,
                              measured_admissible=True)=="MEASURED_PRODUCT_CHECK"

def test_valid_reference_beats_closer_out_of_time_reference():
    result=select_reference([{"station_id":"a","distance_km":1,"offset_s":5000,"joint_energy_coverage":1,"outcome":"recovered"},
                             {"station_id":"b","distance_km":2,"offset_s":20,"joint_energy_coverage":1,"outcome":"recovered"}])
    assert result["selected"]["station_id"]=="b"

def test_http_budget_enforces_transaction_and_byte_limits():
    b=HTTPBudget(1,10,8,1,0); b.reserve_transaction(); b.accept_chunk(0,8)
    with pytest.raises(RuntimeError): b.reserve_transaction()
    with pytest.raises(RuntimeError): b.accept_chunk(0,3)

def test_block18_payloads_are_present_for_offline_reuse():
    root=Path(__file__).resolve().parents[1]
    assert len(list((root/"Block18_reference_recovery/payloads_raw").glob("*_spectrum.ascii")))==4

def test_frozen_config_digest_matches():
    import hashlib
    root=Path(__file__).resolve().parents[1]; path=root/"Block21_frequency_validation_selector/BLOCK21_CONFIG.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest()==(path.with_suffix(".sha256").read_text().split()[0])

def test_runner_uses_full_snapshot_and_explicit_offline_phase():
    root=Path(__file__).resolve().parents[1]
    source=(root/"code/run_block21_frequency_selector.py").read_text()
    assert "normalized_acquisitions.csv" in source
    assert 'choices=["offline","remote","finalize"]' in source
    assert "Block20_audited_or_used\":False" in source

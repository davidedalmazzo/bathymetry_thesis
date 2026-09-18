from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import MultiPolygon, Polygon

from umbra_sar.scene_selection import (
    ByteRangeBudget,
    acquisition_key,
    anomaly_flags,
    axial_direction_difference_deg,
    canonical_json_bytes,
    classify_candidate,
    clean_spectral_arrays,
    cphd_sicd_association,
    crawl_status,
    deduplicate_processings,
    direction_from_to,
    full_direction_difference_deg,
    is_vandenberg,
    marine_geometry_metrics,
    normalize_stac_item,
    normalized_identifier,
    observation_offset_s,
    period_fields,
    rank_candidates,
    reference_classification,
    repaired_geometry,
    snapshot_identity,
    spectral_hm0_m,
    temporal_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'umbra/selezione_scene/Block16_scene_selection' / "BLOCK16A_CONFIG.json").read_text(encoding="utf-8"))
SNAPSHOT_TIME = datetime(2026, 9, 14, tzinfo=timezone.utc)


def item(*, collect_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", start="2025-01-01T00:00:00Z", end="2025-01-01T00:00:20Z", mode="SPOTLIGHT", geometry=None):
    geometry = geometry or {"type": "Polygon", "coordinates": [[[0, 0], [0.1, 0], [0.1, 0.1], [0, 0.1], [0, 0]]]}
    return {
        "id": "ITEM-A",
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "umbra:collect_id": collect_id,
            "umbra:task_id": "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
            "platform": "Umbra-01",
            "start_datetime": start,
            "end_datetime": end,
            "datetime": start,
            "sar:instrument_mode": mode,
            "view:incidence_angle": 25,
            "view:azimuth": 100,
            "processing:version": "1.2.3",
            "created": "2025-01-02T00:00:00Z",
        },
        "assets": {
            "scene_CPHD.cphd": {"title": "CPHD"},
            "scene_SICD.nitf": {"title": "SICD"},
        },
    }


def normalized(**kwargs):
    raw = item(**kwargs)
    objects = [
        {"key": "sar-data/task/scene/scene_CPHD.cphd", "size_bytes": "100", "etag": "a"},
        {"key": "sar-data/task/scene/scene_SICD.nitf", "size_bytes": "200", "etag": "b"},
    ]
    row = normalize_stac_item(raw, stac_key="sar-data/task/scene/scene.stac.v2.json", objects=objects)
    row["anomaly_flags_json"] = json.dumps(anomaly_flags(row, SNAPSHOT_TIME, CONFIG))
    return row


def eligible_record(**updates):
    row = normalized()
    row.update({
        "ocean_roi_available": True,
        "temporal_hard_gate": True,
        "wave_range_axial_difference_deg": 3.0,
        "metadata_association_verified": True,
        "preliminary_spatial_gate": True,
        "reference_class": "measured_complete",
        "observable_cycles": 2.1,
        "measured_hm0_m": 1.2,
        "measured_peak_r1": 0.8,
        "measured_long_energy_fraction_f_le_0p1": 0.8,
        "station_distance_km": 15,
    })
    row.update(updates)
    return row


def test_identifier_normalization():
    assert normalized_identifier(" AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA ") == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert normalized_identifier("  scene A ") == "scene A"
    assert normalized_identifier("null") is None


def test_collect_id_primary_and_fallback_stable():
    assert acquisition_key("AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA", platform="x", start=None, end=None, geometry=None).startswith("collect:aaaaaaaa")
    args = dict(collect_id=None, platform="x", start="2025-01-01Z", end="2025-01-02Z", geometry=item()["geometry"])
    assert acquisition_key(**args) == acquisition_key(**args)


def test_dedup_collect_id_preserves_variants_and_prefers_both_assets():
    first = normalized(); second = dict(first)
    second["processing_key"] = "processing:other"; second["has_sicd"] = False; second["processing_created_utc"] = "2026-01-01T00:00:00Z"
    acquisitions, variants = deduplicate_processings([second, first])
    assert len(acquisitions) == 1 and len(variants) == 2
    assert acquisitions[0]["has_cphd"] and acquisitions[0]["has_sicd"]
    assert sum(bool(x["preferred_processing"]) for x in variants) == 1


def test_missing_collect_ids_are_not_collapsed_when_geometry_differs():
    a = normalized(collect_id=None)
    b = normalized(collect_id=None, geometry={"type": "Polygon", "coordinates": [[[2, 0], [2.1, 0], [2.1, .1], [2, .1], [2, 0]]]})
    acquisitions, _ = deduplicate_processings([a, b])
    assert len(acquisitions) == 2


@pytest.mark.parametrize(("start", "end", "expected"), [
    ("2027-01-01T00:00:00Z", "2027-01-01T00:00:10Z", "date_in_future"),
    ("2025-01-01T00:00:10Z", "2025-01-01T00:00:00Z", "start_end_inverted"),
])
def test_date_anomalies(start, end, expected):
    row = normalized(start=start, end=end)
    assert expected in anomaly_flags(row, SNAPSHOT_TIME, CONFIG)


def test_negative_and_anomalous_dwell():
    inverted = normalized(start="2025-01-01T00:00:10Z", end="2025-01-01T00:00:00Z")
    assert "dwell_nonpositive" in anomaly_flags(inverted, SNAPSHOT_TIME, CONFIG)
    huge = normalized(start="2025-01-01T00:00:00Z", end="2025-01-01T01:00:00Z")
    assert "dwell_implausible" in anomaly_flags(huge, SNAPSHOT_TIME, CONFIG)


def test_incomplete_crawl_fails_closed():
    assert crawl_status(listed_sidecars=10, parsed_sidecars=10, errors=[]) == "complete"
    assert crawl_status(listed_sidecars=10, parsed_sidecars=9, errors=[]) == "incomplete"
    assert crawl_status(listed_sidecars=10, parsed_sidecars=10, errors=["x"]) == "incomplete"


def test_polygon_and_multipolygon_are_supported():
    polygon = Polygon([(0, 0), (.1, 0), (.1, .1), (0, .1)])
    multi = MultiPolygon([polygon, Polygon([(1, 0), (1.1, 0), (1.1, .1), (1, .1)])])
    assert repaired_geometry(polygon).geom_type == "Polygon"
    assert repaired_geometry(multi).geom_type == "MultiPolygon"
    assert marine_geometry_metrics(multi, Polygon()).get("footprint_area_km2", 0) > 0


def test_invalid_polygon_is_repaired():
    bowtie = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}
    fixed = repaired_geometry(bowtie)
    assert fixed.is_valid and not fixed.is_empty


def test_antimeridian_distance_and_geometry_are_finite():
    polygon = {"type": "Polygon", "coordinates": [[[179.8, 0], [-179.8, 0], [-179.8, .1], [179.8, .1], [179.8, 0]]]}
    metrics = marine_geometry_metrics(polygon, Polygon())
    assert np.isfinite(metrics["footprint_area_km2"])
    from umbra_sar.scene_selection import haversine_km
    assert haversine_km(0, 179.9, 0, -179.9) < 25


def test_marine_roi_and_land_control_are_separate():
    footprint = Polygon([(0, 0), (.1, 0), (.1, .1), (0, .1)])
    land = Polygon([(0, 0), (.02, 0), (.02, .1), (0, .1)])
    metrics = marine_geometry_metrics(footprint, land)
    assert metrics["ocean_roi_available"] is True
    assert metrics["land_control_available"] is True


def test_axial_and_full_direction_conventions():
    assert direction_from_to(350) == 170
    assert axial_direction_difference_deg(179, 1) == pytest.approx(2)
    assert full_direction_difference_deg(350, 10) == pytest.approx(-20)


def test_temporal_cycles_and_independent_looks():
    result = temporal_metrics(catalog_duration_s=24, period_s=9, nominal_look_duration_s=6)
    assert result["independent_look_count"] == 4
    assert result["usable_center_span_s"] == pytest.approx(18)
    assert result["observable_cycles"] == pytest.approx(2)
    assert result["temporal_hard_gate"] is True


def test_cphd_duration_precedes_sicd_and_catalog_but_remains_distinct():
    result = temporal_metrics(catalog_duration_s=18, sicd_processed_aperture_s=17, cphd_tx_time_span_s=22, period_s=10)
    assert result["duration_source"] == "cphd_tx_time_span_s"
    assert result["cphd_tx_time_span_s"] == 22 and result["sicd_processed_aperture_s"] == 17


def test_mean_and_peak_periods_never_conflated():
    result = period_fields(model_mean=12)
    assert result["model_peak_period_s"] is None
    assert result["period_proxy_source"] == "model_mean_period_proxy"
    result = period_fields(model_peak=10, model_mean=12, measured_peak=8)
    assert result["period_proxy_for_screening_s"] == 8


def test_ndbc_missing_values_and_nan_are_removed_or_marked():
    f, density, alpha = clean_spectral_arrays([.05, .06, .07, .08], [1, 999, np.nan, 2], [10, 20, 30, 999])
    assert f.tolist() == [.05, .08]
    assert density.tolist() == [1, 2]
    assert alpha[0] == 10 and np.isnan(alpha[1])


def test_nonordered_frequencies_rejected():
    with pytest.raises(ValueError, match="strictly increasing"):
        clean_spectral_arrays([.1, .08], [1, 2])


def test_hm0_integral():
    assert spectral_hm0_m([.05, .1, .15], [1, 1, 1]) == pytest.approx(4 * np.sqrt(.1))


def test_active_station_without_spectrum_is_not_measured_reference():
    value = reference_classification(station_active=True, spectrum_density=False, alpha1=False, alpha2=False, r1=False, r2=False, within_distance=True, within_time=True, model_available=True)
    assert value == "nearby_buoy_without_spectrum"


def test_active_station_outside_distance_is_not_called_nearby():
    value = reference_classification(station_active=True, spectrum_density=False, alpha1=False, alpha2=False, r1=False, r2=False, within_distance=False, within_time=True, model_available=True)
    assert value == "model_only"


def test_observation_offset_is_signed():
    assert observation_offset_s("2025-01-01T00:00:00Z", "2025-01-01T00:30:00Z") == 1800


def test_manual_verification_has_no_ranking_effect_and_order_is_stable():
    a = eligible_record(acquisition_key="collect:a", manually_verified=True)
    b = eligible_record(acquisition_key="collect:b", manually_verified=False)
    first = rank_candidates([a, b], CONFIG)
    second = rank_candidates([b, a], CONFIG)
    assert [(r["acquisition_key"], r["category"], r["score"]) for r in first] == [(r["acquisition_key"], r["category"], r["score"]) for r in second]
    assert first[0]["score"] == first[1]["score"]


def test_missing_gate_data_abstains_as_E():
    row = eligible_record(metadata_association_verified=None)
    assert classify_candidate(row, CONFIG)[0] == "E"


@pytest.mark.parametrize("identity", [
    {"collect_id": "9d8283d8-550d-4435-899f-5483d2c1abcc"},
    {"collect_name": "2025-02-16-18-55-44_UMBRA-10"},
])
def test_vandenberg_exclusion_is_invariant(identity):
    row = eligible_record(**identity)
    assert is_vandenberg(row)
    assert classify_candidate(row, CONFIG)[0] == "D"


def test_byte_range_budget():
    budget = ByteRangeBudget(100)
    budget.reserve(60)
    assert budget.remaining_bytes == 40
    with pytest.raises(RuntimeError, match="budget"):
        budget.reserve(41)


def test_cphd_sicd_association():
    assert cphd_sicd_association({"collect_id": "A"}, {"collect_id": "A"})
    assert not cphd_sicd_association({"collect_id": "A"}, {"collect_id": "B"})
    assert cphd_sicd_association({"platform": "U", "collect_start": "2025-01-01T00:00:00Z"}, {"platform": "U", "collect_start": "2025-01-01T00:00:00.5Z"})


def test_snapshot_hash_is_reproducible_and_order_independent():
    assert snapshot_identity({"b": 2, "a": 1}) == snapshot_identity({"a": 1, "b": 2})
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}\n'


def test_normalization_finds_assets_and_sizes():
    row = normalized()
    assert row["has_cphd"] and row["has_sicd"]
    assert row["cphd_size_bytes"] == 100 and row["sicd_size_bytes"] == 200


def test_public_asset_name_is_joined_by_kind_when_internal_name_differs():
    raw = item()
    raw["assets"] = {"internal_MM.cphd": {"title": "CPHD"}, "internal_SICD_MM.nitf": {"title": "SICD"}}
    objects = [{"key": "public/collect_CPHD.cphd", "size_bytes": "123"}, {"key": "public/collect_SICD.nitf", "size_bytes": "456"}]
    row = normalize_stac_item(raw, stac_key="public/collect.stac.v2.json", objects=objects)
    assert row["cphd_size_bytes"] == 123 and row["sicd_size_bytes"] == 456


def test_block8_paths_are_not_outputs_of_new_module():
    source = (ROOT / "code" / "umbra_sar" / "scene_selection.py").read_text(encoding="utf-8")
    assert 'umbra/validazione/Block8_validation' not in source


def test_regression_old_manual_list_membership_cannot_change_classification():
    first = eligible_record(acquisition_key="collect:a", old_block8_manual_case=True)
    second = eligible_record(acquisition_key="collect:b", old_block8_manual_case=False)
    ranked = rank_candidates([first, second], CONFIG)
    assert {row["category"] for row in ranked} == {"A"}
    assert len({row["score"] for row in ranked}) == 1

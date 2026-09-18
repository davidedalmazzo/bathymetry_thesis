import csv,json
from pathlib import Path
import pytest

def root(): return Path(__file__).resolve().parents[1]

def test_config_is_single_candidate_and_frozen_band():
 c=json.loads((root()/"Block23_candidate2_metadata_preflight/BLOCK23_CONFIG.json").read_text())
 assert c["collect_id"]=="f7ced35f-8a2c-45ef-a822-c442bb47662d"
 assert c["frozen_wave_band_hz"]==[.0575,.0775]

def test_declared_assets_do_not_equal_verified_availability():
 with (root()/"Block23_candidate2_metadata_preflight/BLOCK23_ASSET_AVAILABILITY.csv").open() as f:r={x["asset"]:x for x in csv.DictReader(f)}
 assert r["stac"]["status"]=="publicly_available"
 assert r["sicd_declared"]["status"]==r["cphd_declared"]["status"]=="not_publicly_retrievable"

def test_vendor_collect_identity_and_polarization():
 x=json.loads((root()/"Block23_candidate2_metadata_preflight/remote_raw/candidate2_metadata.json").read_text())["collects"][0]
 assert x["id"]=="f7ced35f-8a2c-45ef-a822-c442bb47662d" and x["polarizations"]==["VV"]
 assert x["endAtUTC"]>x["startAtUTC"]

def test_range_check_cannot_be_promoted_from_missing_sicd():
 x=json.loads((root()/"Block23_candidate2_metadata_preflight/BLOCK23_WAVE_RANGE_GEOMETRY.json").read_text())
 assert x["axial_difference_deg"] is None and not x["band_reselected"]


"""Offline tranche provenance and recovered-spectrum regressions."""
import json
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
import run_block27_representativity as m
OUT=ROOT/'Block27_frequency_query/representativity_v2'

def test_historical_budget_unknown_and_new_tranche_bounded():
    s=json.loads((OUT/'STATE.json').read_text())
    assert s['historical_transactions'] is None and s['historical_bytes'] is None
    assert s['historical_consumption']=='consumo storico non determinabile'
    assert s['old_cumulative_limit_certified'] is False
    assert 0<=s['transactions']<=30 and 0<=s['total_bytes']<=20*1024**2
    logs=json.loads((OUT/'REQUEST_LOG.json').read_text())
    assert sum(l['bytes'] for l in logs)==s['total_bytes']

def test_new_subset_timestamp_hash_masks_and_offline_reparse():
    r=next(r for r in m.read(OUT/'ACQUISITION_AUDIT.csv') if r['station_id']=='51209')
    assert r['reference_status']=='recovered'
    raw=ROOT/r['payload_path']; assert m.sha(raw)==r['payload_sha256']
    text=raw.read_text();obs=m.parse_ascii_vector(text,'time')
    assert len(obs)==1 and abs(float(obs[0])-m.epoch(r['observation_utc']))<.01
    ds=r['source_url'].split('.ascii?')[0]
    das=OUT/'raw'/(hashlib.sha256((ds+'.das').encode()).hexdigest()+'.txt')
    n=m.normalize_payload(text,das.read_text(),observation_epoch_s=float(obs[0]))
    saved=json.loads((OUT/'normalized'/f"{r['collect_id']}.json").read_text())
    assert m.serial(n)==saved
    assert len(n['frequency_hz'])==64 and set(n['masks'])==set(m.VARIABLES)

def test_local_42084_preserved_and_not_relabelled_42094():
    rr=m.read(OUT/'ACQUISITION_AUDIT.csv')
    old=[r for r in rr if r['reference_status']=='verified_local_Block18']
    assert len(old)==4
    assert all(r['reference_station_id']=='42084' and r['station_id']=='42094' for r in old)
    assert all(m.sha(ROOT/r['payload_path'])==r['payload_sha256'] for r in old)

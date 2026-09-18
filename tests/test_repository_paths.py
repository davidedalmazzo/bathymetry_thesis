"""Native layout and non-mutating legacy provenance resolution."""
import hashlib
import json
from pathlib import Path
import pytest
from repository_paths import ROOT, remap_relative, resolve_historical
from frf_client.provenance import audit


def test_native_and_legacy_paths_are_idempotent():
    mappings = json.loads((ROOT / 'repository_paths.json').read_text())['prefixes']
    for old, new in mappings.items():
        assert remap_relative(old) == new
        assert remap_relative(new) == new
        assert resolve_historical(old) == ROOT / new
        assert (ROOT / new).exists()
    assert remap_relative('CHECKPOINT_34.md') == 'docs/checkpoints/CHECKPOINT_34.md'
    assert remap_relative('https://example.com/Vandenberg/file') == 'https://example.com/Vandenberg/file'


def test_absolute_local_windows_and_foreign_paths():
    value = str(ROOT / 'Vandenberg/metadata').replace('/', '\\')
    assert resolve_historical(value) == ROOT / 'umbra/Vandenberg/metadata'
    for invalid in ('../outside', 'C:/old_project/file', 'https://example.com/file'):
        with pytest.raises(ValueError):
            resolve_historical(invalid)


def test_audit_keeps_original_and_four_statuses(tmp_path):
    path = tmp_path / 'umbra/Vandenberg/small'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'original')
    entries = [
        {'path': 'Vandenberg/small', 'sha256': hashlib.sha256(b'original').hexdigest()},
        {'path': 'Vandenberg/small', 'sha256': 'different'},
        {'path': 'Vandenberg/missing', 'sha256': 'missing'},
        {'path': 'C:/foreign/file', 'sha256': 'foreign'},
    ]
    before = json.dumps(entries)
    result = audit(entries, tmp_path)
    assert [r['status'] for r in result] == ['hash_verified', 'mismatch', 'file_unavailable', 'unresolved_path']
    assert result[0]['original_path'] == 'Vandenberg/small'
    assert result[0]['resolved_path'] == 'umbra/Vandenberg/small'
    assert json.dumps(entries) == before


def test_frozen_block34_baseline_after_migration():
    baseline = ROOT / 'duck_frf/Block34_frf_operational/FROZEN_BASELINE.json'
    records = json.loads(baseline.read_text())
    assert len(records) == 810
    # A public source clone intentionally excludes private payload caches.
    # Local migration audit separately requires all 810 to remain available.
    assert all(row['status'] in ('hash_verified', 'file_unavailable') for row in audit(records, ROOT))

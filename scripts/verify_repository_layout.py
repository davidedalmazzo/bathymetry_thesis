"""Read-only artifact migration audit plus optional ordinary/offline smoke tests."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code'))
from repository_paths import resolve_historical
from frf_client.provenance import audit

OUT = ROOT / 'docs/reorganization'


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def run(name, args):
    result = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    save(name, {'command': ['.venv-umbra-thesis/Scripts/python.exe', *args], 'exit_code': result.returncode,
                'stdout': result.stdout, 'stderr': result.stderr})
    print(result.stdout)
    return result.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tests', action='store_true')
    ap.add_argument('--delivery', action='store_true')
    args = ap.parse_args()
    if Path.cwd().resolve() != ROOT:
        raise ValueError('Run from repository root')
    os.environ.update(TEMP=str(ROOT / '_tmp'), TMP=str(ROOT / '_tmp'), MPLCONFIGDIR=str(ROOT / '_cache/matplotlib'))
    baseline = json.loads((ROOT / 'duck_frf/Block34_frf_operational/FROZEN_BASELINE.json').read_text())
    frozen = audit(baseline, ROOT)
    save('FROZEN_ARTIFACT_AUDIT.json', {'counts': dict(Counter(r['status'] for r in frozen)), 'entries': frozen})
    git = ['git', '-c', f'safe.directory={ROOT.as_posix()}']
    original_blobs = {}
    for line in subprocess.check_output(git + ['ls-tree', '-r', 'HEAD'], text=True).splitlines():
        metadata, name = line.split('\t', 1)
        original_blobs[name] = metadata.split()[2]
    moves = []
    for line in subprocess.check_output(git + ['diff', '--cached', '--name-status', '--find-renames=100%'], text=True).splitlines():
        if not line.startswith('R100\t'):
            continue
        _, old, new = line.split('\t')
        path = ROOT / new
        original = original_blobs[old]
        body = path.read_bytes()
        current = hashlib.sha1(f'blob {len(body)}\0'.encode() + body).hexdigest()
        normalized = body.replace(b'\r\n', b'\n')
        normalized_blob = hashlib.sha1(f'blob {len(normalized)}\0'.encode() + normalized).hexdigest()
        moves.append({'original_path': old, 'resolved_path': new, 'mapping_matches': resolve_historical(old) == path,
                      'git_original_blob': original, 'current_raw_blob': current,
                      'raw_bytes_status': 'hash_verified' if current == original else 'mismatch',
                      'difference_kind': 'none' if current == original else 'git_eol_normalization_only' if normalized_blob == original else 'content_changed'})
    save('STAGED_MOVE_AUDIT.json', {'entries': moves, 'counts': dict(Counter(r['raw_bytes_status'] for r in moves)),
                                 'note': 'Git blob comparison is distinct from historical SHA256; pre-existing EOL normalization may differ.'})
    states = {}
    for prefix in ('duck_frf/Block32_frf_client/cache/probe', 'duck_frf/Block34_frf_operational/cache/probe',
                   'duck_frf/Block34_frf_operational/network/probe', 'umbra/Vandenberg/results/block12_backprojection/probe',
                   'umbra/Vandenberg/original.cphd', '.venv-umbra-thesis/probe'):
        states[prefix] = subprocess.run(git + ['check-ignore', '--no-index', prefix], capture_output=True).returncode == 0
    save('IGNORE_SAFETY.json', states)
    historical = {}
    for name in ('duck_frf/Block32_frf_client/DELIVERY_MANIFEST.json', 'duck_frf/Block33_frf_offline_correction/MANIFEST.json', 'duck_frf/Block34_frf_operational/MANIFEST.json'):
        manifest = json.loads((ROOT / name).read_text())
        entries = audit(manifest['artifacts'], ROOT)
        historical[name] = {'counts': dict(Counter(r['status'] for r in entries)), 'entries': entries}
    save('HISTORICAL_MANIFEST_AUDIT.json', {'manifests': historical,
         'note': 'Current code/docs can differ from historical sources; frozen artifact mismatch is separately checked. Original manifests are never rewritten.'})
    rc = int(any(r['status'] != 'hash_verified' for r in frozen) or not all(states.values()))
    if args.tests:
        rc |= run('FULL_SUITE.json', ['-m', 'pytest', '-q', '--tb=short'])
    if args.delivery:
        from frf_client.delivery import verify_delivery
        base = OUT / 'frf_delivery'
        base.mkdir(parents=True, exist_ok=True)
        verify_delivery(ROOT, base)
        rc |= run('CLI_REAL_INPUT_OFFLINE.json', ['code/frf_client_cli.py', '--mode', 'offline', '--input',
                'duck_frf/Block34_frf_operational/ACQUISITIONS.json', '--config',
                'duck_frf/Block34_frf_operational/CLIENT_CONFIG.json', '--cache',
                '_cache/layout_frf', '--reuse-cache', 'duck_frf/Block34_frf_operational/cache',
                '--output', 'outputs/layout_frf_cached'])
    names = {'repository_paths.json', 'code/repository_paths.py', 'scripts/migrate_repository_paths.py',
             'scripts/verify_repository_layout.py', 'tests/test_repository_paths.py', 'README.md', 'AGENTS.md',
             'WORKLOG.md', '.gitignore', '.gitattributes', 'docs/REPOSITORY_LAYOUT.md', 'docs/FRF_QUICKSTART.md',
             'umbra/scripts/FORMA_BLOCK12.bat', 'umbra/scripts/FORMA_BLOCK13.bat', 'umbra/scripts/download_vandenberg_sicd.bat'}
    for name in ('MECHANICAL_REWRITE.json', 'DYNAMIC_REWRITE.json', 'DOC_REWRITE.json'):
        for entry in json.loads((OUT / name).read_text()):
            names.add(entry['path'] if isinstance(entry, dict) else entry)
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'code/frf_client').glob('*.py'))
    names.update(p.relative_to(ROOT).as_posix() for p in OUT.rglob('*') if p.is_file() and not any(part.startswith('delivery_copy') for part in p.parts) and p.name != 'MANIFEST.json')
    save('MANIFEST.json', {'root_relative_paths': True, 'no_commit_push': True,
          'artifacts': [{'path': name, 'bytes': (ROOT / name).stat().st_size,
                         'sha256': hashlib.sha256((ROOT / name).read_bytes()).hexdigest()} for name in sorted(names)]})
    return rc


if __name__ == '__main__':
    raise SystemExit(main())

"""Explicit compatibility for repository paths in immutable historical records."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_FILE = ROOT / 'repository_paths.json'


def remap_relative(value):
    """Map a root-relative legacy path; preserve unrelated identifiers and URLs."""
    value = str(value).replace('\\', '/')
    mappings = json.loads(MAP_FILE.read_text(encoding='utf-8'))['prefixes']
    for old, new in sorted(mappings.items(), key=lambda item: -len(item[0])):
        if value == old or value.startswith(old + '/'):
            return new + value[len(old):]
    if re.fullmatch(r'CHECKPOINT_\d+\.md', value):
        return 'docs/checkpoints/' + value
    return value


def resolve_historical(value, root=ROOT):
    """Resolve only local paths; absolute external paths need explicit remapping."""
    root = Path(root).resolve()
    value = str(value).replace('\\', '/')
    if '://' in value:
        raise ValueError('A URL is not a local historical path')
    if re.match(r'^[A-Za-z]:/', value):
        prefix = ROOT.as_posix().rstrip('/')
        if not value.lower().startswith(prefix.lower() + '/'):
            raise ValueError('External historical path requires an explicit remap')
        value = value[len(prefix) + 1:]
    elif value.startswith('/'):
        try:
            value = Path(value).resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError('External historical path requires an explicit remap') from exc
    path = (root / remap_relative(value)).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Historical path escapes repository')
    return path

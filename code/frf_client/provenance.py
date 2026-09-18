"""Explicit root-relative historical manifest audit; unavailable is not verified."""
import ntpath
from pathlib import Path
from .transport import digest
from repository_paths import resolve_historical


def audit(entries,root,remaps=None):
    root=Path(root).resolve();result=[]
    for entry in entries:
        original=entry["path"];path=None
        if ntpath.isabs(original):
            for prefix,destination in (remaps or {}).items():
                normalized=original.replace('\\','/');prefix=prefix.replace('\\','/').rstrip('/')
                if normalized.lower().startswith(prefix.lower()+'/'):
                    path=resolve_historical(destination, root)/normalized[len(prefix)+1:];break
        else:
            try:path=resolve_historical(original,root)
            except ValueError:path=None
        if path is not None and path.resolve().is_relative_to(root):
            path=resolve_historical(path.resolve().relative_to(root).as_posix(),root)
        status="unresolved_path" if path is None or not path.resolve().is_relative_to(root) else "file_unavailable" if not path.is_file() else "hash_verified" if digest(path.read_bytes())==entry["sha256"] else "mismatch"
        result.append({"original_path":original,"resolved_path":path.resolve().relative_to(root).as_posix() if path is not None and path.resolve().is_relative_to(root) else None,"status":status})
    return result

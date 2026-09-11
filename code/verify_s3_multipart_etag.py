"""Verify a large local object against an S3 multipart ETag without loading it in RAM."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected-size", type=int, required=True)
    parser.add_argument("--expected-etag", required=True)
    parser.add_argument("--part-size", type=int, default=50 * 1024 * 1024)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def new_md5() -> "hashlib._Hash":
    try:
        return hashlib.md5(usedforsecurity=False)
    except TypeError:
        return hashlib.md5()


def main() -> int:
    args = parse_args()
    actual_size = args.path.stat().st_size
    if actual_size != args.expected_size:
        raise SystemExit(
            f"size mismatch: expected {args.expected_size}, got {actual_size}"
        )

    part_digests: list[bytes] = []
    sha256 = hashlib.sha256()
    bytes_read = 0
    with args.path.open("rb", buffering=0) as stream:
        while True:
            block = stream.read(args.part_size)
            if not block:
                break
            digest = new_md5()
            digest.update(block)
            part_digests.append(digest.digest())
            sha256.update(block)
            bytes_read += len(block)
            if len(part_digests) % 10 == 0 or bytes_read == actual_size:
                print(
                    f"verified chunk {len(part_digests):03d}: "
                    f"{bytes_read}/{actual_size} bytes",
                    flush=True,
                )

    combined = new_md5()
    combined.update(b"".join(part_digests))
    computed_etag = f"{combined.hexdigest()}-{len(part_digests)}"
    expected_etag = args.expected_etag.strip('"')
    passed = computed_etag.lower() == expected_etag.lower()

    report = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "path": str(args.path.resolve()),
        "size_bytes": actual_size,
        "expected_size_bytes": args.expected_size,
        "part_size_bytes": args.part_size,
        "part_count": len(part_digests),
        "computed_multipart_etag": computed_etag,
        "expected_multipart_etag": expected_etag,
        "sha256": sha256.hexdigest(),
        "passed": passed,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not passed:
        raise SystemExit("multipart ETag mismatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Quarantine the hand-inserted sections of the Block 14 JSON.

Three sections in Vandenberg/results/analysis_block14/BLOCK14_NONLINEARITY.json
are produced by no script in the repository:

  azimuth_cutoff.interpretation
  anisotropy.controlled_for_wavelength
  model_comparison            (including the q = 0.789 result)

They were inserted by hand. Two problems follow. First, they cannot be
reproduced or audited. Second, `anisotropy.controlled_for_wavelength` directly
contradicts the sibling key `anisotropy.verdict`, which the script does write:
the script says "anisotropo ... compatibile con il velocity bunching", the
insert says "no evidence ... Velocity bunching is not implicated".

Deleting them would lose information that may well be correct. This script
moves them, unchanged, into a clearly labelled quarantine block so that the
file is honest about what is machine-generated and what is not, and so that
nothing downstream can read q = 0.789 as a script output.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

UNPROVENANCED = [
    ("azimuth_cutoff", "interpretation"),
    ("anisotropy", "controlled_for_wavelength"),
    ("model_comparison", None),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    document = json.loads(args.json.read_text(encoding="utf-8"))
    if "manual_annotations_unverified" in document:
        raise SystemExit("gia' messo in quarantena; nulla da fare")

    quarantine = {}
    for parent, child in UNPROVENANCED:
        if child is None:
            if parent in document:
                quarantine[parent] = document.pop(parent)
        elif parent in document and child in document[parent]:
            quarantine[f"{parent}.{child}"] = document[parent].pop(child)

    document["manual_annotations_unverified"] = {
        "quarantined_utc": datetime.now(timezone.utc).isoformat(),
        "reason": (
            "These sections are present in the delivered JSON but are written by "
            "no script in code/. They were inserted by hand and cannot be "
            "reproduced or audited. They are preserved verbatim and moved here so "
            "that no downstream analysis can mistake them for script output."),
        "known_conflict": (
            "'anisotropy.controlled_for_wavelength' contradicts the "
            "script-written 'anisotropy.verdict'. The script's own value is left "
            "in place; the contradiction is unresolved."),
        "must_be_regenerated_before_use": [
            "model_comparison (this is where q = 0.789 lives)"],
        "content": quarantine,
    }
    args.out.write_text(json.dumps(document, indent=2), encoding="utf-8")
    print(f"messe in quarantena {len(quarantine)} sezioni: {list(quarantine)}")
    print(f"scritto {args.out}")


if __name__ == "__main__":
    main()

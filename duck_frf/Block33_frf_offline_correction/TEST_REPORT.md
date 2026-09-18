# Executed test evidence

- Before correction: 11 failing assertions, REPRODUCTION.json (6.69 s).
- Complete ordinary thesis-interpreter suite: 310 passed, FULL_SUITE.json (40.52 s, final rerun).
- Isolated corrected-source snapshot: 68 passed, CLEAN_CLIENT_TESTS.json (23.58 s, final rerun).
- No failures/skips in the final successful runs; normal tests use no real HTTP.

41 new numerical/behavior tests plus the existing 24 client tests and unchanged
3 Block30 tests run in the isolated set. Earlier isolated verifier attempt
omitted pending temporal.py and failed import; explicit pending-file inventory
corrected the snapshot, final source paths/hashes are in CLEAN_TREE_INPUTS.json.
This is evidence of a corrected working-tree clone-shaped snapshot, not evidence
that uncommitted changes are already published or that a fresh dependency
installation was tested. No pip/network operations were performed.

Four cached dossier comparisons, frozen file audit and historical manifest
reference audit are separate from ordinary tests; inspect their JSON states,
not only output-file presence. Audit statuses distinguish hash_verified,
mismatch, file_unavailable, unresolved_path with explicit prefix remapping.

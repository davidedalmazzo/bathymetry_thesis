# Block32 verification

Final complete thesis-interpreter suite: **269 passed in 23.00 s**, no failures/skips.

24 new ordinary offline tests: UTC/numeric offsets and millisecond preservation;
previous/next/nearest-QC and known intervals; from/toward/circular mean;
per-variable missing/QC; ND DAP row indices, GRID coordinate canonicalization,
inline scalars and shape conflicts; supplier NaN and NumPy bool serialization;
variable spectral grid/missing-bin integration; WGS84 inverse and polygon
inside/hole/edge/ROI; MultiPolygon/coordinate order; historical/deployment
contradictions; stale Waverider versus independent AWAC context; JSON/GeoJSON/CSV
and EOWEB footer; offline dossier/masks/manifest; cache reuse/corruption/resume,
persistent budgets, redirects/retry/Retry-After/timeouts/failure TTL, body limits,
authentication states/secret protection, metadata-driven catalog filenames and
bounded survey opt-in.

Separate real endpoint execution: 40 transactions, 2,412,291 received payload
bytes including the incomplete transfer; later dossier/inventory/time-only
verification entirely offline/cached. Detailed endpoint evidence in
REAL_ENDPOINT_REPORT.json, ledger in cache/requests.jsonl and persistent state
in cache/NETWORK_STATE.json. No network performed by ordinary tests.

Frozen Block28–31/Block30 script regression audit: 163 files unchanged.
Block4 SAR-only metrics golden SHA256 unchanged. Delivery audit also checks
complete payload hashes, manifest artifact/source hashes and the file-size gate.

This does not certify unsupported survey/NCSS/HTTP fallback layouts or absent
June parameters and does not validate phase-to-frequency SAR physics.

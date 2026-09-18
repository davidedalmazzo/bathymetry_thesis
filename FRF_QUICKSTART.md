# Duck/FRF client — quickstart

Run from the thesis repository root. Local pending Block33/34 source files must
be versioned before these corrections exist on GitHub. No credentials needed
for verified public endpoints. No SAR data are used.

## Environment

```powershell
py -3.13 -m venv .venv-umbra-thesis
.\.venv-umbra-thesis\Scripts\python.exe -m pip install -r requirements-thesis.txt
$env:TEMP = "$PWD\_tmp"
$env:TMP = "$PWD\_tmp"
$env:MPLCONFIGDIR = "$PWD\_cache\matplotlib"
```

Installation requires network separately; no packages were installed in Block34.
Use the already-existing environment if available, never `sdb-iride`.
Example footprint/ROI files are synthetic illustrations, NOT real SAR support.
Supply your own valid WGS84 lon/lat GeoJSON geometry or single Feature.

## Minimal single acquisition (offline, correct partial dossier on cache miss)

```powershell
.\.venv-umbra-thesis\Scripts\python.exe code\frf_client_cli.py --acquisition-id my_scene --timestamp-utc 2021-10-12T11:07:16.616Z --footprint examples\frf\footprint.geojson --output outputs\my_scene --config examples\frf\client.json
Invoke-Item outputs\my_scene\SUMMARY.md
```

Add `--roi examples\frf\roi.geojson` to query an ROI. ROI outside footprint is
rejected unless `--roi-outside allow` explicitly requests an unclipped external
ROI. Omit `--footprint` for a time-only query: spatial distances are N/A, not zero.
Timestamps need timezone; catalogue timestamps are not physical aperture centers.

## Batch, dry-run and inventory

```powershell
.\.venv-umbra-thesis\Scripts\python.exe code\frf_client_cli.py --input examples\frf\acquisitions.json --output outputs\batch --config examples\frf\client.json
.\.venv-umbra-thesis\Scripts\python.exe code\frf_client_cli.py --input examples\frf\acquisitions.json --output outputs\plan --config examples\frf\client.json --dry-run
.\.venv-umbra-thesis\Scripts\python.exe code\frf_client_cli.py --input examples\frf\acquisitions.json --output outputs\inventory --config examples\frf\client.json --mode inventory --dry-run
```

Dry-run never uses HTTP. RECOVERY_PLAN lists verified payloads/missing known
requests, bounded event windows and a lower-bound transaction count. Unknown
sizes/catalog descendants/retries are explicit. Live inventory requires a named
authorized tranche just as fetch does; it reads metadata, not observed ASCII.

## Explicit new authorized tranche and resume

Budget limits live in a separate JSON, not reusable scientific/time config.
The example budget is a template, NOT new authorization. After authorization:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe code\frf_client_cli.py --mode fetch --input examples\frf\acquisitions.json --config examples\frf\client.json --output outputs\live --cache _cache\frf_client --tranche my_authorized_tranche --new-tranche --budget-config examples\frf\budget.json
.\.venv-umbra-thesis\Scripts\python.exe code\frf_client_cli.py --mode fetch --input examples\frf\acquisitions.json --config examples\frf\client.json --output outputs\live --cache _cache\frf_client --tranche my_authorized_tranche --budget-config examples\frf\budget.json
.\.venv-umbra-thesis\Scripts\python.exe code\frf_client_cli.py --mode offline --input examples\frf\acquisitions.json --config examples\frf\client.json --output outputs\cached --cache _cache\frf_client --tranche my_authorized_tranche --budget-config examples\frf\budget.json
```

Remove only `--new-tranche` on resume; repeated creation, altered limits or
unknown tranche without explicit creation fail. Payload cache is shared between
named tranche states; verified reuse is free of new HTTP-byte charges.
`--reuse-cache path` imports only SHA-verified payloads, never historical budgets.
`--tranche-root` selects state location separately from cache/output. Keep a
single writer; concurrent mutation of one cache/tranche is unsupported.
An exhausted tranche cannot be enlarged or implicitly reset.

## Results and states

Open SUMMARY.md, then per-acquisition REPORT.md. Original measurements/QC and
exact sample pointers are in OBSERVATIONS.csv; per-sample geography/deployment in
DISTANCES.csv; masks/native spectra/profiles in TENSORS.json; diagnostic derived
Hm0/moments in SPECTRAL_SUMMARIES. SEARCH_COVERAGE and STATUS retain missing,
incomplete and technical states. `representative_eligible` means ONLY implemented
availability/QC/time policy, not physical representativity. Unknown QC stays
unknown; no automatic instrument substitution/interpolation/direction correction.
Missing spectra are null, valid zero energy has no arbitrary Tp. Burst intervals
are shown only if explicitly known, not invented from supplier averages.
Scatter time plots do not bridge gaps. Profiles are not assumed surface currents;
wind elevation is not converted to neutral 10m; tide datum is original.

Verified adapter: numerical OPeNDAP DAP2 ASCII. NCSS/HTTP fallback, compressed DAP
parsing and unknown survey layouts remain unsupported. Catalogue footprints are
not verified valid SAR support. Historical-cache audits/regressions are optional
and distinct from ordinary offline tests. No definitive scene recommendation.

```powershell
.\.venv-umbra-thesis\Scripts\python.exe -m pytest -q
.\.venv-umbra-thesis\Scripts\python.exe -m pytest tests\test_frf_client.py tests\test_frf_block33.py tests\test_frf_operational.py tests\test_block30_frf_conditions.py -q
```

Block34 execution evidence and actual named budget are in CHECKPOINT_34 and
Block34_frf_operational; generic examples do not authorize another live run.

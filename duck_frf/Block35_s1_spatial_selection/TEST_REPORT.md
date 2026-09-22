# Block35 tests and real API verification

## Final offline suite

Thesis interpreter: `.venv-umbra-thesis/Scripts/python.exe`.
**343 passed, zero failed/skipped** (54.82 s); exact command, output, timestamp
and interpreter are preserved in `FULL_SUITE.json`.

Nineteen new test cases cover documented nextLinks and unsafe endpoints,
pagination/empty responses/cycles/conflicting UUID duplicates, fractional UTC,
query time boundaries and polygon AOI, holes/MultiPolygons/missing footprints,
version grouping, measured from-to-toward axial convention, analytic dispersion
sensitivities versus toy finite differences, integration with the existing FRF
monthly scalar loader and complete chunked survey adapter, Windows persistence
retry and quicklook endpoint safety (never a full SAR product link).
Existing FRF parser/transport/budget/resume/provenance/SarPy tests were included
in the full suite; these offline tests are not proof that an API is reachable.

## Diagnoses/corrections retained

- First full-suite attempt: 296 passed, 42 setup errors from pytest temporary
  directories outside the writable repository. Set TEMP/TMP/MPLCONFIGDIR
  locally and a fresh repository `_tmp` basetemp; no scientific regression was
  involved, no external directory was removed.
- A new integration fixture exposed an inline DAP scalar after a vector without
  a separating blank line. The **existing shared** ASCII parser now treats that
  scalar as a vector/GRID boundary and accepts scalar-only payloads. Shape
  checks remain strict. No second parser or source CSV change was introduced.
- Public CDSE combined expansion returned HTTP400. Corrected to single
  documented `Assets` expansion, successful for all five finalists; original
  five failed attempts are charged/retained.
- A Windows sharing violation denied atomic ledger replacement before HTTP
  dispatch. One attempt was conservatively charged from the pending file;
  local replacement retries are bounded, do not repeat HTTP. Ledger audit:
  72 dispatched attempts + one reserved charge = 73.
- WR17 3D directional and current-profile requests timed out. Failed URLs were
  not repeated. A new smaller wave projection recovered native E(f)/moments.
  Currents remain unavailable; Oct13 full survey-vector retrieval is incomplete.

## Separate live evidence

Actual public documented CDSE search completed in October: count=8, unique
UUIDs=8, physical passes=5, one complete page. FRF scalar/QC and spectrum
requests succeeded/reused verified caches with preserved actual sample IDs.
Four complete small survey-vector traversals succeeded, one timed out.
Assets/Nodes and two official quicklooks succeeded; annotation XML **401**,
no credentials configured. No protected retry/access bypass, SAR pixel read or
full download. See `CATALOGUE_STATUS.json`, `REFINED_REASON.json`, initial/live
FRF status, `SURVEY_STATUS.json`, `INSPECTION.json`, `NETWORK_AUDIT.json`.

## Frozen hashes and visual QA

`FROZEN_AUDIT.json`: **810 checked, zero mismatches** using the native historical
path resolver. No prior manifest/checksum/result/budget rewrite.

Visually inspected `figures/ROI_SURVEYS.png`, `figures/SPECTRA_FINALISTS.png`
and chosen official quicklook. Survey maps show actual points and the explicit
northern rectangle/pier-profile exclusion; incomplete spatial coverage is not
filled. All five spectra are readable, references labelled with sample offset;
numeric lobes are not physical-system partitions. The tiny quicklook shows
only broad scene structure; wave visibility/k is **not evaluable**.

`MANIFEST.json` lists artifact/source SHA256 and verified local cache payload
provenance. All prospective versioned files remain under GitHub's 100 MiB
per-file cap; radar/NetCDF source files, caches and environments stay excluded.
No Git commit or push was made.

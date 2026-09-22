# Sentinel-1 IW spatial screening at Duck

Stable entry points are `code/s1_duck_selection.py`, `code/s1_spatial_compare.py`
and `code/s1_spatial_delivery.py`. The historical `run_block33_*` names are
deprecated wrappers, not a second FRF client or an output directory. Block33
already belongs to the FRF offline correction; current outputs are native
`duck_frf/Block35_s1_spatial_selection/`.

This experiment screens **spatial k from future SAR intensity**, external
frequency from pertinent FRF observations, and eventual direct survey
comparison. No inversion or SAR formation is performed. It neither validates
temporal phase retrieval nor chooses/excludes a TOPS/spotlight temporal route.

## Reproduce

Run from the actual Git root, with the thesis interpreter:

```powershell
python code/s1_duck_selection.py catalogue --offline
python code/s1_spatial_compare.py --phase frf-a
python code/s1_duck_selection.py frf-refined --offline
python code/s1_spatial_delivery.py
```

Replace `python` with `.\.venv-umbra-thesis\Scripts\python.exe`. Verified cache
is local-only; cache misses stay missing in offline mode. Live phases omit
`--offline`, use the same named persistent tranche and require public network
access. `init` is explicitly rejected when the tranche already exists; budgets
cannot silently reset. Discovery is CDSE documented OData only, follows actual
nextLinks with host/path checks, detects cycles/conflicting UUID duplicates,
preserves UTC fractions/holes/MultiPolygons/missing values and counts slices,
versions and physical datatake passes separately. Latest online version per
slice is retained for comparisons, then the slice covering the marine area is
chosen per pass; every catalogue product remains in the complete table.

Pass A uses the existing FRF `Client` with an opt-in validated **scalar/QC wave
projection**, bounded monthly vectors, two instruments and all catalogue
products. Pass B fetches spectra and ancillary context for at most five passes.
`frf-refined` reduces the failed 3D directional projection to native E(f) and
four directional moments; failed URLs are not repeated. The measured published
peak-frequency mean and modal directions remain distinct; all-frequency mean
direction is not substituted. Shared source/sample IDs are not independent.

The survey adapter traverses every index of a small complete coordinate,
elevation, profile-ID and time vector in chunks <=5000 before geographic
filtering. It refuses unsupported layouts/overlarge vectors and preserves
datum and source masks. These are small ASCII geographic subsets, not source
NetCDF downloads. Survey catalogs in the new dossier are compacted by the
declared time context, not by first-N selection; verified full raw catalogs
remain locally cached. Measured points/profile IDs do not imply continuous
seabed coverage. Per-point dates take precedence over filename dates.

## Evidence and unresolved geometry

No weighted score/hard physical cutoff is used. The preregistered order is
technical coverage and available QC context, then smaller WR17 measured peak
spread, larger Hs descriptively, UTC. Five covered passes fit the five-finalist
cap. The footprint longest-edge bearing is a **proxy only**, not incidence,
heading-derived truth or local projected range. The buoy propagation direction
is `(measured_from+180)%360`; axial difference is modulo 180. No refraction,
Snell, direction or wind-height correction is applied. Missing data are not
unfavorable physical conditions. A numeric half-maximum lobe is descriptive,
not an identified independent physical wave system.

Public Assets and Nodes were verified. Quicklooks are auxiliary compressed
previews, not k measurements or a visibility test. Annotation XML content is
authenticated; a single 401 is retained and no access restriction is bypassed.
Without XML/manifest, subswath/burst support, seam margins, local incidence and
projected range remain conditions before SAR work. A complete SAFE download
is only prepared, never automatically executed.

## Analytic dispersion sensitivity

For `u=kh`, `omega=sqrt(g*k*tanh(u))`:

```text
domega/dk|h = g*(tanh(u)+u*sech(u)^2)/(2*omega)
dh/dk|omega = -(sinh(2*u)/2+u)/k^2
dh/domega|k = 2*omega*cosh(u)^2/(g*k^2)
```

`s1_spatial.dispersion_sensitivity` evaluates analytic diagnostics only. Tests
use a toy inverse solely for finite-difference validation; actual-scene
bathymetry is never inverted. No imposed SAR peak/dispersion fit center is
created. FFT spacing, lobe width, estimator uncertainty and physical spatial
variability differ. `delta_k/k ~ L/W` is not a universal estimator accuracy
bound or an RMSE prediction; no required 3-4 km ROI or Block17 floor is asserted.
External omega is not local truth. Bed NAVD88, tide reference and instantaneous
water depth are separate; absent representative currents remain uncertainty.

## Tests and provenance

Offline targeted tests cover UTC/geometry/directions/pagination/empty results/
duplicates/version grouping and finite-difference sensitivities, alongside
existing FRF transport/budget/resume/parser tests. Live API results are separate
evidence. Block35 exports a persistent network audit, payload checksums,
artifact/source manifest, complete table and frozen-hash audit. No old result
manifest or historical budget is rewritten. No commit/push in this task.

## Block36 annotation preflight

`run_block36_s1_iw_preflight.py` consumes only the fixed Block35 product and
ROI. `init` creates or resumes a persistent 40-request, 50 MiB metadata tranche;
`prepare --offline` emits a truthful blocked dossier without credentials;
`fetch` retrieves only manifest, VV IW1/IW2/IW3 annotations and the pertinent
calibration/noise XML. Measurement TIFF content is never on the allow-list.

Credentials normally come from `CDSE_USERNAME`/`CDSE_PASSWORD` in the
Git-ignored root `.env`; `CDSE_ACCESS_TOKEN` remains an alternative. The
tracked `.env.example` has empty values. `fetch` obtains and refreshes its
bearer in memory through the documented CDSE `cdse-public` password flow and
prompts locally once for MFA/TOTP if needed. Authentication consumes the same
persistent budget and neither credential forms nor token responses are logged
or cached. The parser
checks platform, mode, swath, polarization, orbit, time overlap and exact
manifest references. Per-line valid intervals exclude `-1`; ROI support is
computed in image coordinates through the annotation geolocation grid. Local
physical wavenumber follows `k_EN = J^-T q_image`, not a footprint bearing.
The completed artifact is `READY`: the fixed ROI is entirely valid in IW3
burst 0 without a seam. Local range is 80.571242 degrees and incidence is
44.163763 degrees at ROI center. This is technical readiness for the first
spatial-intensity trial, not a wave or bathymetry validation.

## Block37 real spatial trial

`download_block37_s1.py` performs the UUID/name/length/checksum-locked,
resumable full-product transfer; `prepare_block37_safe.py` validates and safely
extracts the SAFE. Raw archive and extraction directories are Git-ignored.
`run_block37_spatial.py` reads only bounded VV/IW3 windows, verifies exact burst
support, applies calibration/noise conventions, maps the fixed FRF grids, and
computes the preregistered intensity spectra without a bathymetry or expected-k
input. `s1_spatial_trial_validate.py` checks the frozen baseline and writes the
versionable artifact/source manifest. This intensity-only trial does not choose
between the project's temporal-method candidates.

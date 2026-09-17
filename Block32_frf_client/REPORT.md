# CHECKPOINT_32 — reusable Duck/FRF observational client

2026-09-17. **Client implemented and verified; remote verification is partial because the authorized 40-transaction tranche is exhausted.** No SAR processing/download, inversion, definitive selection, commit or push.

## Implementation

Mission-neutral `code/frf_client/` library and `code/run_block32_frf_client.py` CLI provide single-acquisition and multi-acquisition inputs, inventory/fetch/offline modes, official THREDDS discovery, metadata-driven OPeNDAP subsets, SHA256-verified legacy cache reuse, persistent budgets/failure TTL/retry/redirect accounting, signed temporal offsets and QC associations, WGS84 geometry, structured spectra/profiles and plots/manifests. Interfaces/examples and limitations: [README_FRF_CLIENT](../code/README_FRF_CLIENT.md).

The original Block30 scalar parser is reused without changing its script or frozen CSV/results. The extension was necessary for actual DAP2 responses: inline scalar coordinates, indexed ND rows and GRID names such as `waveEnergyDensity.waveEnergyDensity` with repeated coordinate maps. Grids/shapes are checked before canonicalization. A non-record EOWEB footer is ignored by the separate adapter; TDX milliseconds come from original record 11, not the rounded derivative CSV.

The first event run exhausted the tranche before a JSON serialization error involving supplier NaN metadata; this was corrected offline, along with NumPy boolean serialization. Early URL logging appended a spurious `=` to bare DAP constraints; cache-key SHA256 proved the original URLs, and own-cache provenance was repaired without changing payloads or Block30 files. Tests cover these cases. Final dossiers are fully regenerated offline; no scientific input was adjusted.

## A. Original observations and verified dates

October 2021: Waverider-17m and AWAC-11m complete 1D/2D wave spectra, moments, published bulk parameters and QC flags; AWAC current profiles; EOP derived wind; EOP NOAA tide. June 2021: verified cached bulk waves at all four selected stations and newly recovered AWAC current profiles. AWAC June spectrum/QC expansion failed partway through transport; only independently verified cached bulk context is used afterward.

| Acquisition | Reference | Tp published (s) | Hs published (m) | sensor−catalogue timestamp (s) | Quality/use |
|---|---|---:|---:|---:|---|
| COSMO 2098202, 2021-10-13T22:45:03Z | Waverider-17m 23:00 | 9.546539 | 1.1081544 | +897.000 | QC 1, within 3600 s policy |
| COSMO 2098202 | AWAC-11m waves 23:00:00.5 | 8.316009 | 1.1006101 | +897.500 | QC 1, within policy |
| TDX-1 record 11, 2021-10-13T23:00:15.669Z | same Waverider record | 9.546539 | 1.1081544 | −15.669 | same observation, NOT independent reference |
| TDX-1 record 11 | same AWAC wave record | 8.316009 | 1.1006101 | −15.169 | same observation, NOT independent reference |
| COSMO 1941935, 2021-06-29T22:56:51.912Z | AWAC-11m waves | 7.5901327 | 0.58215046 | +188.588 | contemporaneous cached bulk, QC not recovered |
| COSMO 1942455, 2021-06-30T10:54:50.308Z | AWAC-11m waves | 6.6445184 | source retained in dossier | +310.192 | contemporaneous cached bulk, QC not recovered |

The two June starts retain original catalogue fractions, unlike second-rounded Block30 CSV; differences in reported offsets reflect precision, not modified observations. Waverider nearest records for those cases have offsets **−1,744,011.912 s and −1,787,090.308 s** (about 20 days). They remain context only, never representative and never fill an AWAC row. All four stations' bulk parameters are compared separately in each readable dossier.

For COSMO 2098202: wind 6.364327 m/s at +297 s; AWAC depth-integrated speed 0.2435523 m/s at +3597 s; observed level 0.052 m NAVD88 at +177 s. For TDX: wind 6.3533335 m/s at −15.669 s; current +2684.331 s; level −0.017 m at −15.669 s. These are not one mixed tile state. NOAA source selector `gapGauge=2` denotes preliminary data: no passed NOAA QC is asserted. The current is not called surface/effective wave current. Wind sensor elevation stays original, not converted to neutral 10 m.

## B. Calculated quantities and geography

October spectra contain **62 frequency bins ×72 directional bins**, plus supplied a1/b1/a2/b2 moments. Reconstructed midpoint bin widths are explicitly identified. Waverider integrated Hm0=1.108154484 m differs from published Hs by 8.37e−8 m; AWAC Hm0=1.100610172 m differs by 7.19e−8 m. This validates decoding/integration numerically, not spatial representativity or SAR physics. The bin periods (9.3023/8.1633 s) remain distinct from supplier parabolic-fit Tp (9.5465/8.3160 s).

Waverider published mean direction at peak frequency is **64.93568° from true north**, versus all-spectrum mean 59.25528°; peak mode 65°, peak spread 25.0523°. AWAC corresponding peak-frequency mean 66.50954°, mode 70°, spread 28.057314°. No all-spectrum direction is automatically assigned to Tp; no directional reconstruction, Snell correction or fixed 250° direction.

With dated scalar nominal coordinates, TDX Waverider is **outside** its catalogue footprint: minimum edge distance **690.35 m**, centroid distance **3706.57 m**, sensor→centroid bearing 239.37°. AWAC is inside (minimum zero), centroid distance **1181.14 m**. For COSMO 2098202 Waverider is inside; all exact distances are in DISTANCES.csv. These footprints are catalogue geometry, not verified valid SAR support. No ROI was supplied for these regressions, so ROI distances are explicitly not evaluable; a separate single time-only CLI verification marks tile and ROI distances not evaluable.

Scalar coordinates differ from global nominal bounds by **24.46 m Waverider /46.11 m AWAC waves**. Both source representations are retained; conflicting positions flag spatial uncertainty. They are not claimed measured GPS/deployment-validated locations. Global AWAC current ID incorrectly says `awac5m` despite 11m URI/title; `aveTime=900` long_name says seconds while units says index. Supplier anomalies are documented, not silently repaired or used to invent burst timing.

## C. Assumptions and policy

Configured before remote event queries: waves/currents tolerance 3600 s; wind/level 1800 s; survey context 30 days; QC accepted flag 1; unknown QC not accepted; no interpolation or automatic survey download. Previous/next/nearest eligible references are retained per variable over fetched context. Known durations without verified anchoring do not invent start/end or interval distance. Ellipsoidal WGS84 distances are conditioned on nominal historical source positions, not proof of representativity. Catalogue timestamp is NOT declared aperture center, especially TDX record 11.

## D. Missing/conditional products

- June AWAC wave spectra/QC: failed transfer, no complete payload, verified cached bulk only.
- June EOP wind: DAS recovered, DDS/time/event values unfinished for budget.
- June NOAA level: discovered product, detailed retrieval unfinished for budget.
- 8m-array and Waverider-26m: cached contemporaneous bulk context; spectral/QC expansion not selected in this bounded verification.
- Surveys: official elevationTransects/survey catalog and aggregate service verified; detailed survey date/method/uncertainty/datum/point-line coverage inventory not retrieved for budget. No seabed coverage inferred from bounding boxes, no bathymetry download/GEBCO substitution. Optional reusable 1D geographic point subset adapter exists but real survey layouts/selector verification remain conditional.
- NCSS/HTTPServer are declared official services; automatic fallback adapters are not certified/enabled. Unsupported layouts and absent inspected products remain source-specific, not global absence.
- Anonymous public access verified. Authentication/signed URLs are refused rather than guessed; no secrets requested or stored, TLS remains active. Future authenticated support requires official mechanism verification.

## Network, tests and hashes

**40 transactions /2,412,291 bytes (2.30 MiB)**. 39 complete responses; one failed stream included **1,048,576 partial bytes** in the persistent streaming counter. Complete-response bodies sum 1,363,715 bytes. Earlier error logging omitted its per-error bytes; the ledger audit reconciles the difference with the persistent counter, and logging now preserves partial bytes explicitly. No failed payload is reused. Redirects/retries count separately; none are hidden in an OPeNDAP package. **86 unique legacy successful URL payloads verified/reused**, no legacy hash mismatch. Historical cumulative consumption from earlier tranches is **non determinabile**, not zero; this tranche is separate.

**269 full-suite tests passed**, including 24 new offline tests and existing SarPy/FFT/sign tests. Real endpoint verification is separate from ordinary tests. Frozen audit: **163 files, zero mismatches**; Block4 frozen SAR-only metrics SHA256 remains `c399af008e2159ede9b6e27b8bf99dffdd17b7f808aa263ea569d20438df8fcd`. Per-dossier and delivery manifests record config, sources, versions and SHA256. No file ≥100 MiB; caches Git-excluded. No staged commit/push.

Conclusion: **the client is usable with explicit coverage/QC limits; this is not a complete FRF survey inventory, a definitive scene selection or validation of the SAR method.** Stop at CHECKPOINT_32. State and unfinished recovery are saved; no further HTTP is authorized in this exhausted tranche.

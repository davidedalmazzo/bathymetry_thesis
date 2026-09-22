# CHECKPOINT_35 — Sentinel-1 IW spatial-validation selection, Duck

## Decision: first technical download, conditional

**S1A_IW_SLC__1SDV_20211028T230636_20211028T230703_040326_04C765_B6FA.SAFE**

- UUID: `c49a9c1f-9b00-5676-ab05-683975d898a2`.
- Catalogue sensing interval: **2021-10-28 23:06:36.323000–23:07:03.267000 UTC**.
  These are product boundaries, not the ROI's local sensing time/burst center.
- Sentinel-1A, IW SLC complex, VV & VH, ascending; relative orbit **4**,
  absolute orbit **40326**, slice 19. Public catalogue `Online=true`.
- Catalogue `ContentLength`: **7,799,368,890 bytes** (~7.26 GiB). This is the
  vendor product size, not a separately verified delivered ZIP size.
- Footprint, assets and node inventory are public. Actual XML content returned
  **401**, with no configured access token. No bypass or further protected
  content attempt was made. Download command is prepared, **not executed**.

This is a choice for a first **spatial** technical trial, not validation of
phase-to-frequency or a final choice between TOPS and spotlight approaches.
No SAR pixels, signal arrays, formation, frequency estimation, depth inversion
or dwell sweep were performed. Vandenberg and frozen shortlists were untouched.

## Complete initial search, actual live API verification

The public documented CDSE OData query uses the configured polygon covering
the marine FRF/instrumented area, **[2021-10-01, 2021-11-01)** in UTC.
The catalogue reports **8 products**, all returned in one page: **five physical
datatake passes**, three with adjacent slices. All UUIDs remain in inventory and
the complete comparison table; slices and reprocessing versions are not
independent passes. Three southern slices intersect the AOI but do not cover
the configured marine screening area. Five northern/covering slices are the
finalists. October therefore suffices; **no date extension or fallback API**.

API field names were observed, not inferred: `operationalMode=IW`,
`productType=IW_SLC__1S`, `polarisationChannels=VV&VH`, `GeoFootprint` is a
MultiPolygon. UTC fractions, vendor checksums, original footprint and missing
processing-version fields are retained. Pagination uses returned nextLinks,
not synthesized skips; offline tests exercise pagination/empty/duplicates.

| Pass UTC date | WR17 Hs m | WR17 published Tp s | AWAC published Tp s | WR17 peak spread deg | WR17 toward deg | axial delta to footprint proxy deg |
|---|---:|---:|---:|---:|---:|---:|
| 2021-10-28 | 1.710 | 11.396 | 10.870 | 23.25 | 246.34 | 14.53 |
| 2021-10-11 | 2.111 | 8.826 | 8.969 | 26.65 | 251.97 | 8.86 |
| 2021-10-04 | 0.602 | 10.471 | 10.959 | 27.81 | 266.03 | 5.16 |
| 2021-10-16 | 0.641 | 9.756 | 10.870 | 30.42 | 275.87 | 15.00 |
| 2021-10-23 | 0.515 | 14.388 | 13.423 | 31.14 | 253.37 | 7.45 |

These are original measured published peak-frequency **mean** directions and
spread, not all-frequency mean directions or assumed 250 degrees. Modal peak
directions and mean periods remain separate in the full table/dossiers.
Propagation is `from+180`; axial difference is modulo 180. No angle correction.
The ~80.87 degree footprint longest-edge bearing is **only a proxy**, never a
local projected range or heading-derived incidence. Its delta did not impose
a rejection threshold or dominate the selection.

The preregistered unweighted ordering uses technical coverage/QC context,
then smaller measured WR17 peak spread, larger Hs descriptively and UTC.
All five covered passes fit the cap, so this ordering did not suppress a
covered pass. Missing data remain unknown, not physically unfavorable.

## Observational reference and alternatives

Pass A uses the operational FRF client, with bounded monthly scalar/QC vectors
for WR17 and AWAC11 for **all eight products**. Pass B has at most five passes.
Complete native E(f), masks and directional information are retained; no
second parser or wind downloader was introduced. A timed-out 3D WR17 request
was replaced by a **different, smaller projection** preserving E(f), four
directional moments and published peak-band parameters. The failed attempt
and timeout of the AWAC current profile remain documented, not silently calm.

For the chosen scene, QC-eligible reference spectra are:

- WR17: 23:00:00 UTC, offset **−396.323 s**, Hm0 **1.710 m**, numeric E(f)
  maximum **0.085 Hz**; published fitted Tp **11.396 s**.
- AWAC11: 23:00:00.500 UTC, offset **−395.823 s**, Hm0 **1.717 m**, numeric
  maximum **0.0925 Hz**; published Tp **10.870 s**.
- Both spectra have complete valid-bin support. Numeric contiguous
  half-maximum widths are **0.030/0.0225 Hz**, containing **38.4/36.2%** of
  total variance. This descriptive lobe is **not** a physical wave-system
  partition; other numerical maxima are listed, not declared independent seas.
- Measured peak-frequency mean propagation **246.34/246.41 degrees**, spread
  **23.25/24.21 degrees**. Modal peak-frequency propagation is 250 degrees;
  it is retained separately and was not used to tune the alignment.
- WR17's nearest distance to the proposed ROI is **2.98 km**, center distance
  **3.27 km**. AWAC11 is **453 m** from its edge, **732 m** from its center.
  These are dated nominal instrument positions, not proof of instantaneous
  buoy GPS or automatic physical representativity of the whole ROI.
- QC-eligible derived wind: **8.970 m/s**, measured from **56.01 degrees**,
  offset **+203.677 s**, source 10-minute mean. Anemometer elevation is
  **19.64 m NAVD88**, not an assumed 10 m above water; no height conversion.
- Tide product global metadata explicitly names **NAVD88**. Its preliminary
  NOAA/substitute-gauge context lacks verified archive QA/source identity;
  context values are labelled as such, not eligible tide truth or automatically
  added to bed elevations. Representative effective currents are unavailable.
- No finalist's nearest raw wave record is >60 minutes away. Burst timestamp
  anchoring remains unverified; no invented interval/center. Shared observation
  source/sample IDs among adjacent products are reported as one record.

**Alternative: 2021-10-11**, UUID
`d982f98d-9739-5a03-aa42-27407da87d7e`. It has stronger wave energy and better
proxy alignment (WR17 8.86 degrees; AWAC11 2.01 degrees), but broader numerical
lobes (0.0975/0.075 Hz), 10-minute measured wind **11.879 m/s** and an incomplete
nearby survey retrieval. These are comparative diagnostics, not hard wind/Tp
cutoffs. The 28 October spectrum is narrower and has substantial energy in
both references. October 4/16/23 are useful retained alternatives, with lower
measured energy; their waves are not asserted absent/unrecoverable.

## Geography, preliminary ROI and measured bathymetric support

Proposed fixed native FRF rectangle: **x=300–850 m, y=700–1000 m** (550×300 m),
north of the pier profiles 514/520, minimum alongshore separation 180 m.
It was specified independently of predicted k or dispersion agreement.
Geographic corners/source-affine fit are in `PROPOSED_ROI.json`; source pair
fit p95 error ~0.010 m is an internal coordinate-fit residual, **not** absolute
SAR geolocation accuracy. The location and consistently negative measured
bed support a preliminary water ROI away from beach/pier; exact shoreline,
structures and valid complex pixels remain a preflight condition.

The ROI is inside the chosen **catalogue** footprint, with an approximate
local-projection boundary margin **18.7 km**. This is not a valid-pixel or burst
seam margin. Without authenticated VV annotations of all three subswaths and
manifest, do not assert ROI subswath, local range/incidence, burst support,
sampling/resolution or discontinuity-free support.

Complete small point/profile/time vectors were traversed before filtering for
the surveys named Oct 4,16,24,27; Oct 13 encountered a timeout and is explicitly
incomplete. This is not first-N coverage or a global bounding-box assumption.
The nominally nearest Oct 27 survey has **zero** points in this northern ROI.
Use actual **Oct 24** measurements here: **1199 points, six profile IDs**,
actual UTC **15:26:32–16:03:18**, about 4.3 days before the scene.
Elevation percentiles p5/median/p95 are **−8.114/−6.194/−3.744 m NAVD88**
(source geoid 2003), **not** inferred instantaneous water depth.
The survey's source geographic coordinates are NAD83 according to its method
text; source degrees were used without a NAD83-to-WGS84 epoch transformation.
The small datum/geolocation difference remains unresolved, despite the
precise internal affine fit. Points/lines are not continuous seabed coverage:
on a declared 23×13 ROI grid, nearest-point distance p50/p95/max is
**14.6/40.1/63.7 m**. Adjacent observed within-profile segments, consecutive
source indices and spacing 1–20 m only: median spacing **2.46 m**, median/p95
absolute slope **0.00957/0.01545**. No constant global gradient is asserted.

Other survey points expose time/space uncertainty. The file named Oct 16
contains ROI point times on **Oct 15**; older surveys have incomplete offshore
support in this rectangle. Bed change cannot be inferred from unlike spatial
support medians alone. No buoy depth is substituted for local bed measurements.

## Previews, sensitivity and unresolved work

Two official quicklooks were saved and visually checked. They resolve broad
land/water scene structure, **not** the wave lobe or ROI-scale k. Failure to see
waves in these tiny compressed previews does not mean waves are absent.

Analytic dispersion sensitivities are implemented and checked against finite
differences on explicit toy scenarios only; formulas/interpretation are in
`code/README_S1_SPATIAL.md`. No actual depth is inverted, no predicted k is
imposed on a future SAR fit. FFT step, lobe width, estimator uncertainty and
physical variability are distinct. No universal L/W bound, required kilometer
window, RMSE prediction or Block17 accuracy floor is used. External frequency
is uncertain/nonlocal; current neglect is **not** established.

To remove the decisive technical condition: configure a local excluded CDSE
access token and retrieve **manifest plus VV XML for IW1/IW2/IW3**, then map the
proposed ROI to actual burst valid support and derive local projected range,
incidence, resolution and seam margins. No credentials were supplied, and no
protected endpoint was bypassed. SAR wave visibility/spatial convergence can
only be assessed in a later explicitly authorized technical download/trial.

## Network/provenance/test boundary

New tranche only: **73/80 charged attempts**, **7,041,606/157,286,400 bytes**
(~6.716 MiB), per-response cap 15 MiB. This includes initial blocked-proxy
failure, redirects/errors/timeouts, five unsupported combined-expansion HTTP
400s (corrected to documented single `Assets` expansion) and a single XML 401.
There are **72 dispatched HTTP attempts plus one conservative reserved charge**
after a Windows atomic-replacement failure before dispatch; persistence now
has bounded local-only sharing-violation retries, never HTTP retries.
Historical consumption is not reconstructed; no old cumulative-budget claim.
Local payload hashes were verified/reused and historical ledgers unchanged.
Seven charged attempts remain; they cannot resolve authenticated XML without
credentials and are not consumed merely to fill the tranche.

`FROZEN_AUDIT.json`: **810 frozen file hashes unchanged**. Offline suite and
live API verification are separate. See `TEST_REPORT.md`, `NETWORK_AUDIT.json`
and `MANIFEST.json`. No commit/push. Stop at conditional first-product choice.

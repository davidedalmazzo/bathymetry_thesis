# Block36 — authenticated Sentinel-1 IW annotation preflight

## Outcome: READY

The fixed Block35 product passed the authenticated annotation-only preflight:
`S1A_IW_SLC__1SDV_20211028T230636_20211028T230703_040326_04C765_B6FA.SAFE`,
UUID `c49a9c1f-9b00-5676-ab05-683975d898a2`, catalogue size
7,799,368,890 bytes. The October 11 alternative was not queried and the ranking
was not reopened. `READY` authorizes only the first spatial intensity trial;
it is not wave, temporal-frequency or bathymetry validation.

## Authenticated assets and identity

The manifest and VV IW1/IW2/IW3 annotations match S1A, IW, VV, absolute orbit
40326 and the selected sensing interval. The manifest references all three
exact annotation paths. Original bodies, SHA-256 and source URLs are retained.
For the pertinent IW3 support, its matching calibration and noise XML were also
retrieved and verified. No measurement TIFF, full SAFE/ZIP or SAR pixel was
read.

The first real parse exposed that SAFE annotation timestamps omit a lexical
`Z`; their fields are defined as UTC. The parser now assigns UTC explicitly and
a regression test covers the vendor form. No timestamp value was altered.

## ROI and burst support

The primary Block35 ROI remains unchanged: native FRF x=300–850 m,
y=700–1000 m (550×300 m). Its authenticated support is:

- pertinent subswath: **IW3**; IW1 and IW2 are outside their geolocation support;
- burst: **index 0**, lines 0–1507;
- burst azimuth time: **2021-10-28 23:06:37.287243 UTC**;
- burst sensing time: **2021-10-28 23:06:38.401751 UTC**;
- ROI image envelope: approximately samples 14269.7–14445.7 and lines
  946.4–977.1;
- valid ROI fraction: **1.0** using exact per-line
  `firstValidSample/lastValidSample` cells;
- one valid burst only; **no burst join or overlap crossing**.

Thus no stitching is required. Invalid samples remain excluded rather than
being interpreted as zero-valued sea. `ROI_BURST_SUPPORT.geojson` contains the
projected valid burst outline and fixed ROI; the two-panel map separately shows
the full valid support and an ROI/survey/instrument zoom.

## Local geometry

At ROI centroid lon/lat −75.74655515°, 36.18649067°:

- local range-sample bearing: **80.571242°** clockwise from true north;
- local azimuth-line bearing: **350.453641°**;
- incidence: **44.163763°**, boundary range **44.148162–44.179404°**;
- slant-range annotation spacing: **2.329562 m**;
- azimuth annotation spacing: **13.905430 m**;
- geolocated ground spacing: **3.345897 m/sample**, **12.366025 m/line**;
- local Jacobian `[E,N]` m/pixel:
  `[[3.300694, -2.050851], [0.548129, 12.194777]]`;
- determinant: **41.375362 m²/pixel²**.

Effective resolution is not equated to pixel spacing. Image angular
wavenumber `[q_sample,q_line]` transforms as
`[k_east,k_north] = J^{-T}[q_sample,q_line]`. Bearings are oriented clockwise
from true north; wave-axis comparisons are modulo 180°. The footprint edge is
not used as local range.

The measured FRF peak propagation directions remain independent context:
246.34158° WR17 and 246.40836° AWAC11. Their axial differences from local range
are **14.22966°** and **14.16288°**. They are not imposed as a SAR correction or
used to select a peak.

## Spatial trial and independent context

The preregistered future trial uses valid IW3/VV burst-0 pixels only,
`abs(SLC)^2`, verified calibration/noise definitions, and fixed 300×300,
400×300 and 500×300 m candidates where supported. Plane detrending is primary;
quadratic is diagnostic. Hann/Tukey windows and a 2× zero-pad are fixed in
advance; padding is interpolation, not physical resolution. Discrete FFT step,
window response, lobe width and estimator error remain separate. Conjugate
peaks are retained and “association not identifiable” is an allowed result.

FRF values remain frozen from Block35: WR17/AWAC published Tp 11.396/10.870 s,
discrete maxima 0.085/0.0925 Hz, and observation offsets
−396.323/−395.823 s. The full bands, QC, distance, survey coverage, NAVD88 datum,
unknown instantaneous level/current and buoy–ROI representativeness remain
explicit. No inversion was run.

## Authentication, budget and provenance

Username/password authentication succeeded through the documented CDSE
`cdse-public` password grant. Tokens and responses stayed in memory and no
secret was logged. No MFA prompt was required. One sandbox transport failure is
retained in the ledger rather than hidden; the authorized direct retry then
succeeded. All earlier successful metadata payloads were reused from verified
cache instead of redownloaded.

Final tranche usage is **12/40 transactions and 3,819,945/52,428,800 bytes**.
Authentication,
failures and metadata requests all share the original 40-transaction,
52,428,800-byte budget and 10,485,760-byte response cap. Historical tranches
remain separate. `MANIFEST.json` hashes all deliverables, code sources and the
six original metadata bodies. The focused tests are 17 passed; the authoritative
full suite is **360 passed**, with 810 frozen hashes unchanged. The full product
download remains **NOT EXECUTED**.

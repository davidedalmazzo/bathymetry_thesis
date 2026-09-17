# Mission-neutral FRF observational client — Block32

No radar API access, pixel processing, wave-frequency SAR estimation, inversion,
selection or commits. Run only under the repository root using
`.venv-umbra-thesis/Scripts/python.exe`. No new dependencies.

## Entry points

```powershell
.\.venv-umbra-thesis\Scripts\python.exe code\run_block32_frf_client.py --mode inventory --input Block32_frf_client\REGRESSION_ACQUISITIONS.json
.\.venv-umbra-thesis\Scripts\python.exe code\run_block32_frf_client.py --mode fetch --input Block32_frf_client\REGRESSION_ACQUISITIONS.json
.\.venv-umbra-thesis\Scripts\python.exe code\run_block32_frf_client.py --mode offline --input Block32_frf_client\REGRESSION_ACQUISITIONS.json
.\.venv-umbra-thesis\Scripts\python.exe code\run_block32_frf_client.py --mode offline --acquisition-id example --timestamp-utc 2021-10-13T22:45:03Z --output Block32_frf_client\time_only
```

`--footprint geometry.geojson` and `--roi geometry.geojson` are optional for a
single acquisition. All paths must remain inside this repository. No footprint
means tile distances are not evaluable; no ROI means ROI distances are not
evaluable. Catalogue footprints are never called verified SAR ValidData.

Inventory discovers catalogs, instruments and product metadata, not event
samples. Fetch retrieves bounded event subsets; offline verifies/reprocesses
cached payloads and never calls HTTP. `Client.run(...,mode="offline")` also
requires an explicitly offline `Transport`, preventing accidental API networking.

Library: add `code` to the Python import path, then import `frf_client.Client`
from `frf_client.client`, `Transport` from `frf_client.transport`, and validated
records from `frf_client.inputs`. No mission names appear in the retrieval logic.

## Strict input formats

JSON manifest: `{"acquisitions": [{"acquisition_id": "id", "timestamp_utc":
"2021-10-13T23:00:15.669Z", "footprint": {"type":"Polygon",
"coordinates":[[[-75.76,36.18],[-75.74,36.18],[-75.74,36.20],[-75.76,36.20],[-75.76,36.18]]]},
"roi": null}]}`. Optional properties: `start_utc`, `end_utc`,
`timestamp_semantics`, `source`. Unsupported properties fail, including asset or
credential fields. GeoJSON Feature/FeatureCollection: same record properties,
geometry is the footprint. WGS84 GeoJSON coordinates are **longitude, latitude**;
custom CRS is refused, invalid geometry is refused, antimeridian polygons must
be explicitly split. A plausible but mistakenly swapped coordinate pair cannot
be inferred safely; the input contract, never automatic reordering, is decisive.

CSV: `acquisition_id,timestamp_utc,start_utc,end_utc,timestamp_semantics,footprint_geojson,roi_geojson,source`.
Use ordinary CSV quoting for the embedded GeoJSON. Blank optional fields are
accepted. Explicit timezone is mandatory; numeric offsets are converted to UTC.
Fractions of seconds are preserved. No UTC or latitude/longitude inference.

Legacy catalogue adapters are separate: `adapt_cleos` selects product IDs from
the original GeoJSON; `adapt_eoweb` selects `recordNum` from the semicolon export
and ignores its non-record footer. The Block31 derivative CSV truncated TDX
fractions: regression inputs instead use the original record 11 timestamp
**2021-10-13T23:00:15.669Z**. It is a catalogue timestamp, NOT an aperture center.
`--prepare-regressions` prepares four inputs; `--audit-frozen` records/verifies
frozen Block28–31 inputs/artifacts without radar source reads.

## Discovery and adapters

Official root: https://chldata.erdc.dren.mil/thredds/catalog/frf/catalog.xml.
Follow actual catalog references and declared service bases. New months do not
depend on Block30's guessed filename template. Verified cached response URLs
are also legitimate discovery evidence. Defaults select bounded instrument
priorities (`preferred_instruments` can override ancillary defaults), not every
FRF device. Additional wave gauges are configurable.

The production data adapter is **OPeNDAP DAP2 ASCII** with metadata-driven shapes
and constrained index ranges. Scalar vectors reuse the verified Block30 parser;
the extension handles inline scalars, indexed ND rows, `GRID.array` payloads,
coordinate maps and shape conflicts. Source masks, values and attributes remain
available. A DAP error page or malformed shape is not treated as observations.

NCSS and HTTPServer availability is recorded from the official catalog, but
these are not automatically used as unverified fallbacks. Unsupported layouts
remain explicitly unsupported. NDBC/CDIP aliases are documented, not expanded
by default and not counted as independent observations.

Survey inventory follows survey/data/declared-year catalogs when budget allows.
Filename dates are only candidate dates, not verified survey times. Datum,
method, uncertainty and actual point/line coverage remain unknown unless source
metadata/data verify them. Optional `bathymetry_download` requires explicit
bounded `survey_selections` keyed by the discovered OpenDAP URL. The reusable
`survey.fetch_points` supports verified 1-D geographic point-vector layouts,
maximum 5000 points in a caller-declared index block, retaining only points in
the ROI/footprint. Gridded/local-coordinate survey layouts require a verified
adapter and are refused, not replaced by GEBCO. Connecting lines/full seabed
coverage are never invented. The current verification did NOT download surveys.

## Temporal/quality policy

Config is persisted with every dossier. Operational tolerances: waves/currents
3600 s; wind/water level 1800 s; survey context 30 days. These are not physical
limits. Default accepts source QC flag 1; unflagged products are QC-unknown,
not automatically passed. Energy and direction flags are mapped separately.
No stale Waverider value can fill an AWAC row. Previous, next and nearest
QC-eligible samples are retained per variable; search completeness is explicitly
limited to the fetched event context, never claimed for an entire deployment.

Offsets are `sensor_time - acquisition_timestamp`. Explicit CF time bounds,
when supplied, are used for interval distance; otherwise duration hints are
retained while anchoring/start/end remain unknown. No assumption that an hourly
spectrum is instantaneous or timestamp denotes a burst center. Joint
completeness counts only `required_variables` (configurable per family), while
per-variable and spectral-bin masks are retained independently. No interpolation
by default; requesting interpolation is refused until its adapter is enabled.
The reusable circular-mean/from–toward helpers are tested but not empirical
direction corrections.

Spectral integrals use valid bins only: `mn=sum(E*df*f**n)`, `Hm0=4sqrt(m0)`,
`Tm01=m0/m1`, `Tm02=sqrt(m0/m2)`. Missing bins are excluded, not zero-filled or
bridged. Original bandwidths are used if available; otherwise midpoint widths
are explicitly reconstructed. Published peak-period/peak-frequency direction,
mean direction and spread remain distinct. No swell partition or unique
directional distribution is inferred from moments. Supplied 2D spectra are
stored as supplied.

Wind is the published height/gauge-specific measurement, not neutral 10 m.
Derived EOP wind switches gauges; its historical ID table is used for nominal
position, with unknown IDs left unresolved. NAVD88 sensor elevation is not
height above instantaneous sea level. AWAC vertical profiles and depth-integrated
velocity are distinct, neither is assumed the effective wave current. Published
water-level residual is kept separately; no new residual is formed without
compatible timestamps and datum. Source `gapGauge` must be interpreted; no
global NOAA-QC claim is made for preliminary/filled FRF products.

## Cache, budget and authentication

Persistent tranche in `cache/NETWORK_STATE.json` is created **before** HTTP and
cannot be reset on resume or silently enlarged. Defaults: 40 transactions,
100 MiB total, 8 MiB per response. Each redirect/retry counts; bytes are updated
while streaming, including error bodies. Known oversized responses are refused
before their body. Timeout, rate limit, one retry for transient HTTP/timeouts,
Retry-After (long waits deferred), manual bounded redirects and failure TTL are
implemented. Failed paths have source-specific states, not global absence.
Concurrent processes sharing one cache are NOT supported: use a single writer.

Payloads are SHA256-checked before reuse. Legacy Block30 files are reused only
when they reproduce successful logged SHA256 (including reversible Windows
newline conversion). Corrupt/unverified cache is not silently consumed. Logs
record transaction starts/results; earlier tranche consumption is not restated
as zero. `safe_url` redacts secret query values while preserving DAP constraints.

Official verified endpoints are anonymous; no credentials needed/requested.
TLS verification remains active. URL user-info/signed URL secrets are refused;
no environment contents or raw exceptions are logged. 401/403 stops with
`authentication_required`: **no guessed authentication protocol or automatic
interactive login**. A future authenticated adapter requires official mechanism
verification before enabling env/file credentials. `.env`/credential files are
already Git-excluded; the current anonymous adapter does not accept secrets.

## Output and limits

Per acquisition: REPORT.md, ACQUISITION/CONFIG/INVENTORY.json,
OBSERVATIONS.csv (long), DISTANCES.csv, ASSOCIATIONS.json, COMPLETENESS.json,
TENSORS.json, SPECTRAL_SUMMARIES.json, map/time/spectrum/profile plots and
MANIFEST.json. Tensor JSON v1 is the documented NetCDF equivalent: variables
carry shape, raw_values, valid_mask, source attributes/units and coordinates;
nonfinite raw values encode as null with false masks, finite fill sentinels are
preserved. Original byte payloads remain in the verified cache.

Distances: WGS84 ellipsoidal inverse to geometric footprint/ROI centroid and
minimum on GeoJSON linear lon/lat boundaries; polygon interiors/holes supported.
Internal point minimum is zero but centroid distance can be nonzero. Bearing is
sensor→centroid. Historical coordinates stay nominal unless proven measured;
conflicts between dated scalar coordinates/global bounds are explicitly flagged
and propagate to spatial uncertainty. Distance is not proof of representation.
Maps have north/scale and label catalogue versus unverified valid SAR support.

Ordinary tests use offline fixtures. Real endpoint checks use the separate
Block32 execution and persistent ledger. The current authorized tranche is
exhausted; do not start new verification downloads without new authorization.

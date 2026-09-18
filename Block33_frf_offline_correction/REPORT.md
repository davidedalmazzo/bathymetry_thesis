# CHECKPOINT_33 — offline FRF client correction

The reported behaviors are reproduced and corrected. Client supports new
dates/products with metadata-driven discovery and no mandatory legacy cache.
No real endpoints were tested: all new transport checks are simulated and all
historical dossier regeneration uses verified local payloads. Actual HTTP: **0**.

- Inventory: catalogs and DAS/DDS only, optional variables and independent errors.
- Time: per-family configured search months including year/leap transitions;
  separated far-event windows; cross-file previous/next/nearest association.
- Provenance: original indices, distinct monthly grids/tensors, duplicate conflict
  report and explicit incomplete search; no absolute-nearest claim.
- Spectra: missing/zero/partial/complete differentiated, valid-bin integration
  and width assumptions preserved, invalid coordinates rejected.
- Geography: selected-sample position keys, effective wind ID, time-variable
  coordinates, both deployment bounds, WGS84 footprint/ROI distances; nominal
  positions are not measured GPS.
- Transport: short Content-Length and interrupted stream refused/non-ok,
  received bytes counted, TTL/resume and unknown-length caps retained.
- Reproducibility: pinned installed dependencies match; isolated corrected-source
  snapshot runs without private cache, radar, credentials or downloads.

Tests: **310 passed** complete ordinary suite; **68 passed** isolated client plus
unchanged Block30 parser tests. See FULL_SUITE.json / CLEAN_CLIENT_TESTS.json.
Pre-correction 11 failures are retained in REPRODUCTION.json; 41 new behavior
tests cover the fixes. The isolated snapshot uses tracked working-tree sources
plus explicitly listed pending files, not the unchanged remote Git HEAD.

Four offline dossiers: 604 observation rows retain all compared measurements,
times, offsets, QC and original context distances; spectral values unchanged.
438 available Block32 artifact/cache files and 163 historical inputs retain
their SHA256. Historical source mismatches are expected for corrected code and
reported separately; unavailable/unresolved are not called verified.

Limits: no live certification for new dates/endpoints; OPeNDAP numeric supported
layouts only, not arbitrary NCSS/HTTP fallback or compressed DAP parsing. Exact
ties are deterministic without averaging; conflicting samples are not declared
representative. Survey layouts/vertical datum, June missing observations and
complete deployment histories remain conditional as in Block32. Offline cache
miss reports incompleteness, never fetches or infers another instrument's values.

Remaining delivery requirement: newly added source/test/fixture files must be
versioned in a separately authorized commit before the correction exists on
GitHub. All required client input fixtures are lightweight and listed; original
historical exports/private cache are not necessary for ordinary tests. Historical
commands cannot recreate absent originals; they report missing/unresolved.

No frozen dossier/config/manifest, budget, measured direction or SAR quantity
changed. No SAR read/formation, inversion, scene choice, download, commit/push.
Stop CHECKPOINT_33.

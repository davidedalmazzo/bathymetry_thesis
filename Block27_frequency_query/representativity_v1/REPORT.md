# Block27 — buoy–ROI representativity continuation v1

This is a provenance/recovery checkpoint, not completed physical validation.
Frozen queue/report retained without overwriting; four zones, 23 acquisitions.

## Input reconciliation

ROI polygons are reused verbatim from Block21, not reconstructed from rounded coordinates.
The Gulf centers are **not exactly identical**: near 29 N / 90 W because repeated acquisition footprints cover the same target and the deterministic square search selects near the central interior. No fallback coordinates are present in these queue entries; footprint centroid and ROI remain separate columns. Containment is checked against catalog polygons only, not SICD pixel support. See per-acquisition table.

The queue wave-station target 42094 does not replace the actual verified Block18 reference 42084. The nearest station of any instrument type is separately recomputed (GRBL1 in the Gulf); proximity alone does not establish spectral capability. Four Block18 raw hashes are checked before offline reparsing; their normalized individual masks and joint masks are retained. Block21 bins contain only newly recovered acquisitions; the separate availability table and Block18 bin archive are inventoried rather than interpreted as no-data evidence.

## Observations and decisions

Statuses: `{"archive_not_queried": 19, "verified_local_Block18": 4}`. Recovered spectra use dynamic DDS dimensions, variable-specific masks and midpoint reconstructed frequency widths. Direction is propagation=(from+180) mod360; period and direction refer to the same contiguous half-power lobe. No added energy/wavelength/kh/phase gate, no Snell correction, no tuning to Vandenberg.

References with usable payloads are **conditional**, not proof of common exposure. Failed source requests are not documented product absence. Unqueried dates retain frozen order. No candidate is promoted using unsupported clean-water/traffic/plume descriptions in the legacy report.

## Geography and models

Four maps show frozen ROI, catalog footprints, reference/target stations, north and metric scale. Bearings, distances and land intersection lengths are tabulated. Natural Earth 1:10m is a cartographic-scale preliminary land mask, not a high-resolution coastline certification for reef-scale Tobago exposure. Intersections indicate possible different exposure only; non-intersections do not establish identical sea state. GEBCO point depths in the input queue are not used for refraction or validation: exact source/datum has not been reconciled.

Existing Block8/16 wave-model caches are historical screening, not verified paired event predictions at native buoy/ROI cells. No model comparison or climatology substitute is claimed; native resolution, mask, event coverage, partitions, currents and assimilation remain to be documented before model retrieval.

## Budget / resumability

Recorded recovery spending: 0/30 transactions, 0/20971520 response bytes; retries disabled, redirects counted by Block18 budget. Existing Blocks25–27 contain no request ledger or recovery payloads, so unlogged prior spending cannot be reconstructed. State and raw URL-hash cache avoid repeated successful requests. This uncertainty prevents claiming a certified cumulative pre-existing budget.

No SAR, AIS, inversion or Vandenberg processing. No justified priority yet. Next single step: resolve the outstanding provenance/documentation gaps before any SAR preflight.

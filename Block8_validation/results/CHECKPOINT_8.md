# CHECKPOINT_8 — Umbra validation-scene screening

Generated: 2026-09-01T10:29:40.285520+00:00

## Scope and integrity

- Vandenberg was not processed or modified; it is excluded from ranking.
- Complete public catalog: 12,539/12,539 STAC v2 sidecars; 9,577 with CPHD.
- No CPHD or SICD payload was downloaded. Only catalog JSON, wave-model fields, buoy metadata, and six exact-time buoy spectral subsets were retrieved.
- Marine gate: 51 long-dwell scenes and 60 short controls have at least 80% ocean footprint by Natural Earth 1:10m intersection.

## Direction and period conventions

- Umbra `view:azimuth` is used as the range/view axis and treated as an undirected axis modulo 180°.
- MFWAM and NDBC directions are reported **from**; propagation is `(from + 180°) mod 360°` before computing axial delta.
- MFWAM `swell_wave_period` is a mean period. Its `swell_wave_peak_period` field was null for all 111 screened scenes, so no model mean is relabelled as T_p.
- True peak periods below come only from measured NDBC spectral density.

## Decision

### A — best available, conditional: `2025-12-02-16-00-55_UMBRA-07`

- Position/date: 29.00000°, -90.00000°; 2025-12-02T16:00:55.500000Z.
- Dwell 17.0 s; incidence 33.2°; ocean fraction 100.0%.
- NDBC 42084 at 34.2 km supplies density + α1 + α2 + r1 + r2 within 56 s.
- Measured dominant peak: T_p=4.255 s, Hs=1.009 m, propagation 140.0°, Δrange=2.33°.
- Gate: excellent geometry and independent spectrum, but **not a swell-period validation scene**: measured energy at f≤0.1 Hz is 0.00% and the dominant peak is short-period wind sea. Keep only as a conditional phase→period test if a 4.26 s component is acceptable.

### B — long-swell alternative, not validation-ready: `2025-04-26-14-43-09_UMBRA-08`

- Position/date: -72.30199°, -78.82000°; 2025-04-26T14:43:09Z.
- Dwell 16.0 s; incidence 38.1°; ocean fraction 100.0%.
- MFWAM: total Hs=3.14 m, swell Hs=2.52 m, mean swell period=15.25 s.
- Gate: strong, long, swell-dominant sea, but Δrange=20.08° and no verified directional buoy within 50 km. It cannot presently provide independent phase→T_p validation.

### C — 5–7 s control retained: `2023-07-13-15-18-26_UMBRA-04`

- Dwell 6.4 s; incidence 48.1°; NDBC 44087 at 6.5 km.
- Measured T_p=9.901 s and Δrange=2.37°, with complete directional coefficients.
- Gate: useful TerraSAR-X/CSG-like timing control, but Hs=0.278 m is low and incidence 48.1° is outside the preferred interval; retain as a weak-signal control, not the primary validation scene.

## Overall conclusion

The complete catalog contains **no scene that satisfies all ideal gates simultaneously**: long dwell, preferred incidence, strong narrow swell with T_p≥10 s, propagation within 10° of range, and a verified directional spectrum within 50 km. Candidate A is the best independently observed phase-period case but has T_p≈4.26 s; B has the desired long swell but lacks geometry/ground truth; C is a low-energy short-dwell control. Therefore no download >1 GB is authorized at CHECKPOINT_8.

## Artifacts

- `top16_candidates.csv`: requested 10–20 candidate table (15 long-dwell + one short control).
- `ranked_candidates_all.csv`: all 111 marine candidates and score decomposition.
- `verified_ndbc_spectra.csv`: six exact-time spectra and directional diagnostics.

## Sources

- Umbra open data: https://registry.opendata.aws/umbra-open-data/
- Umbra metadata fields: https://docs.canopy.umbra.space/docs/collect-metadata
- Open-Meteo marine fields/conventions: https://open-meteo.com/en/docs/marine-weather-api
- Natural Earth land: https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/
- NDBC spectral conventions: https://www.ndbc.noaa.gov/faq/measdes.shtml
- NDBC historical spectral data: https://www.ndbc.noaa.gov/data/historical/
- CDIP THREDDS data access: https://cdip.ucsd.edu/m/documents/data_access.html

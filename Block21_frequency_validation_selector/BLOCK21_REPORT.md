# Block21 — Umbra frequency-validation selector

## Outcome

The selector evaluated the complete frozen catalog snapshot (10,140 deduplicated acquisitions) and stopped at metadata/reference screening. It did not read or download SAR data, use Block19 as an input, or audit Block20.

The primary output is a five-scene shortlist for validating `arg C(kp, Δt) → ωp → Tp`. Bathymetric sensitivity is recorded only as descriptive future information and is not a ranking gate.

## Method

- A SICD **or** CPHD complex path is sufficient. GEC/preview alone is insufficient.
- Catalog dwell, observable cycles, period ≥10 s, 80% marine coverage, and long-wave energy are not hard gates.
- For every valid footprint, the Natural Earth 1:10m land mask was projected to a local equirectangular metric plane. A deterministic 7×7 search tested fully-water squares of 1500, 1000, 750, 500, and 250 m.
- `footprint_edge_distance_m` and `coast_distance_m` are separate. Where no coast occurs inside the footprint, coast distance is explicitly a lower-bound status rather than the footprint-edge distance.
- Temporal paths use 1.5, 2.5, 4, and 6 s looks at 1 s sliding steps. Counts, overlap, center span, cycles, and phase span are descriptors; sliding looks are never called statistically independent.
- The dominant measured wave band is the contiguous half-power lobe around the global valid density maximum. Period and circular-mean propagation direction are derived from that same band.
- Ordering is lexicographic and inspectable: admissible measured reference, reference proximity, internal ROI, temporal support, dual complex path, then access cost. No opaque total score is used.

## Offline screen

Of 10,140 acquisitions, 2,591 have a deterministic fully-water ROI of at least 250 m. The final classes are:

| Class | Count |
|---|---:|
| MEASURED_PRODUCT_CHECK | 9 |
| CONDITIONAL_REFERENCE_CHECK | 529 |
| MODEL_EXPLORATORY | 0 |
| EXCLUDED | 7,554 |
| NOT_EVALUABLE | 2,048 |

The four Block18 per-bin references were reused locally and remained complete. They were reconsidered under the frequency objective but were not promoted automatically; their dominant bands are short (4.26–7.14 s) and their station is about 34.2 km away.

## Bounded reference verification

The remote queue was frozen before access (`16bb92c…a7dc3c`) and contained 12 acquisitions, at most two per station. NDBC aggregate data were attempted before annual fallback. Five scenes yielded admissible density plus directional moments, seven archive attempts failed, and no failure was generalized to the rest of the catalog.

- HTTP transactions: 28 / 200
- Response bytes: 2,377,820 / 104,857,600
- Per-response cap: 10 MiB; retries: at most 2; timeout: 45 s
- Newly admissible references: 5
- Block18 references reused without HTTP: 4

The directional coefficients are spectral moments, not a unique reconstructed 2-D directional spectrum.

## Shortlist

| Rank | Collect | Duration (catalog) | Complex path | ROI | Buoy / distance | Dominant band | Offset |
|---:|---|---:|---|---:|---|---|---:|
| 1 | `2025-11-15-18-57-16_UMBRA-09` | 7.6 s | SICD | 1500 m | 46268 / 0.44 km | 15.38 s, propagation 24.0° | +163 s |
| 2 | `2025-01-09-06-35-11_UMBRA-10` | 15.0 s | SICD+CPHD | 1000 m | 46268 / 1.21 km | 15.38 s, propagation 37.32° | +1480 s |
| 3 | `2026-06-22-19-52-52_UMBRA-10` | 13.4 s | SICD | 1500 m | 46256 / 3.13 km | 13.33 s, propagation 23.76° | +427 s |
| 4 | `2023-07-05-15-30-48_UMBRA-04` | 2.80 s | SICD+CPHD | 1500 m | 44087 / 3.51 km | 4.76 s, propagation 295.55° | +1752 s |
| 5 | `2023-12-02-07-02-48_UMBRA-06` | 9.0 s | SICD | 1000 m | 46256 / 3.77 km | 14.29 s, propagation 32.0° | −168 s |

Rank 1 is the best reference/ROI match, but its SICD is 13.80 GB and its 7.6 s catalog duration supports only seven 1 s-spaced centers at the shortest look. Rank 2 has both complex products and longer temporal support but a smaller ROI and larger time/station offsets. Rank 3 has a strong long-period band and large ROI, but its SICD is 25.04 GB. None is called ideal before SICD metadata and SAR-domain coherence checks.

## Historical effects and limitations

Block8/16A/17 categories are retained only for comparison. Block21 scientifically removes dwell/cycle, ≥80% sea, long-period, long-energy, and bathymetry gates. Implementation corrections include recalculating all short-scene geometry, separating coast from footprint boundary, enforcing same-band period/direction, allowing either complex product, and distinguishing not queried from archive failure.

Natural Earth is a coarse preliminary mask; the candidate maps and ROI containment are not a high-resolution coastline certification. Catalog duration is not substituted for CPHD Tx-time span or SICD processed aperture. Local range geometry, Doppler/slow-time mapping, actual water texture, usable coherent ROI, and wave-vector/range alignment remain SAR metadata or data checks before any download decision.

## Decision

Candidate 1 is **recommendable for a metadata-only asset preflight, not yet for a 13.8 GB download**. The single next step is a bounded SICD-header/range audit for candidate 1 to verify processed aperture, grid/range direction, polarization and image support without downloading the image payload.


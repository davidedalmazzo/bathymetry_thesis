# Block42 — Block40 re-run with deterministic footprint depths

Directory: `duck_frf/Block42_block40_depth_all/`. Driver: `code/block42_rerun_block40.py`.
Block40 (`duck_frf/Block40_stratified_validation/`) stays as published.

**Why.** Block41 showed that the forward prediction of Block39/40 averaged λ over a
random 60-depth subsample of each footprint. The generator was shared by every window
of a process, so the result depended on how the runs were chunked. The published
Block40 numbers are one realization of that Monte Carlo. Since Block41,
`forward_lambda_check.py` defaults to `--depth-sampling all`, which uses every
footprint cell and is deterministic.

**What was re-run.**
- The forward passes with `all`: the Block40 configuration (66.34°, admissible set) and
  the Block39 fixed-72° fallback used by `block40_matched`.
- Then `block40_matched`, `block40_variance_ladder --finalize 24`,
  `block40_sensitivity`, `block40_figures`, `block40_summary` and `block40_manifest`,
  unchanged.

Protocol, sectors, seeds, blocks, admissibility and estimators are those of Block40.
Inputs that do not depend on depth sampling were copied from Block40: configuration,
source mask, inventory, audit, window provenance, and the SAR-only ladder partial
spectra.

**Checks.**
- `pytest tests/test_block41.py tests/test_block40.py`: 18 passed in
  `.venv-umbra-thesis`.
- The primary strata are identical to the `all` realization of Block41.
- Every changed numeric leaf is listed in `BLOCK42_COMPARISON.json`.

## Results (contour peak, WR17, 95 % CI from the spatial block bootstrap)

| stratum | n | Block40 | Block42 |
|---|---|---|---|
| C 20–30 m SLC | 404 | −7.76 % (−14.32 … −1.24) | −7.76 % (−14.19 … −1.24) |
| C 20–30 m GRD | 425 | +1.38 % (−5.44 … +7.89) | **−0.21 % (−5.27 … +6.98)** |
| B 12–20 m SLC | 22 | −2.36 % (−6.42 … +11.24) | −2.12 % (−8.14 … +13.14) |
| B 12–20 m GRD | 31 | −8.08 % (−21.17 … **−0.90**) | −7.30 % (−21.22 … **+8.92**) |

1. **Band C.**
   - SLC is unchanged and still significantly negative. GRD is compatible with zero.
   - The SLC − GRD gap between band medians goes from 9.1 to 7.5 points.
   - On the 119 paired windows (the same windows for both products; unchanged between
     the two blocks) SLC is −1.24 % (−7.8 … +2.0) and GRD +1.43 % (−5.1 … +9.0), with a
     median paired difference of +4.1 points. Most of the band-level gap therefore
     comes from the two products using different window sets (404 vs 425 windows), not
     from the product itself.
2. **Band B GRD is no longer significantly negative.**
   - In Block41 the upper CI bound ranges from −1.0 to +9.7 % across depth-sampling
     realizations (sd 3.2 points); the published −0.9 % was one of them.
   - With 22–31 windows band B is declared not interpretable. The SLC NMAD, for
     instance, moves from 8.1 to 17.7 %.
3. **Compensation between sources holds and is stronger.**
   - Positive strata in 0–12 m grow: GRD mixed +5.0 → +8.5 %, SLC mixed
     +11.5 → +13.8 %; temporally inadmissible +6.3 → +7.8 % (GRD) and
     +4.3 → +5.4 % (SLC).
   - Legacy strata become slightly more negative: SLC B −8.6 → −9.2 %, GRD C
     −2.6 → −2.8 %.
   - Band A is where depth sampling matters most. The inferred reason is the strong
     depth gradient inside the footprint combined with the nonlinearity of λ(h); this
     has not been verified separately.
4. **SLC ladder** (n = 607).
   - Medians: single look −10.5 → −9.0 %, N2 −14.2 % (unchanged), N4 −9.0 → −8.6 %,
     K4 −8.0 % (unchanged), GRD +1.4 % (unchanged).
   - Still not monotone. Single look and K4 now differ by 1 point, inside the CIs, so
     there is no evidence that variance reduction moves the median.
   - The robust signature is the short-wavelength tail: 30–39 % for the SLC variants
     against 4.5 % for GRD.
   - Several medians are identical to 1e-16 between the blocks, so these medians appear
     to move in discrete steps (inferred).
5. **Budget.**
   - The estimator term (centroid − contour +6.57/+6.80 %) and the 26 m reference term
     are unchanged.
   - Block39 headline with `all`: GRD −0.39 % (−3.79 … +2.58), SLC −4.69 %
     (−8.52 … −0.66); published values −0.77 % and −4.81 %.

## Corrections to Block40 statements

- "Band B GRD −8.1 %" must not be read as significant.
- "Band C GRD +1.4 %" becomes −0.2 %; the conclusion (compatible with zero) is the same.
- The quoted "Block39 aggregate −0.8 %" is −0.4 % with all footprint depths.
  `block40_summary.py` now reads it from Block41 instead of hard-coding it; Block42's
  `BLOCK40_SUMMARY.json` must be regenerated for the text to follow.

**Scope** as in Block40: spatial k/λ only. ω is not measured, no temporal phase is
validated, and bathymetric inversion is not validated.

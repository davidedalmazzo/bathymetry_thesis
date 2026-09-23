# CHECKPOINT 40 — Stratified validation by bathymetric source and SLC variance audit (Duck, S1 2021-10-28)

Block directory: `duck_frf/Block40_stratified_validation/`
Protocol frozen before the analysis: `BLOCK40_PROTOCOL.md`; configuration and seeds:
`BLOCK40_CONFIG.json`; hashes of inputs, code and outputs: `BLOCK40_MANIFEST.json`.
Full report: `BLOCK40_REPORT.md`. HEAD at the start of the block: `7b168a5`.
No download, no catalogue query, no new FRF request, no commit, no push.

**Scope.** Spatial `k` / `lambda` audit only. `omega` is not measured, no temporal or
cross-spectral phase is validated, and this is not a validation of bathymetric inversion.

## What was established

1. **Provenance.** Every ground-truth cell was resolved to an actual survey. The scene's
   deep half is not modern: 20.7 % of cells are interpolated 1868/1970 surveys or the NBS
   generalisation layer and 42.4 % are bias-corrected legacy grids, against 18.8 % direct
   H12859 multibeam (2016) and 6.3 % direct USACE 2019 lidar. The contributor with
   NMAD 0.73 m is the NOAA NGS 2019–2020 topobathy lidar, which spans the dune to 5.5 m
   of water.
2. **Admissible coverage.** With the frozen 90 % rule: band A (0–12 m) has **no**
   admissible window — the FRF survey of 2021-10-21 never covers more than 73 % of a
   512 m window; band B (12–20 m) has 26 (SLC) / 34 (GRD) windows on the 2019 lidar;
   band C (20–30 m) has 581 / 601 windows on H12859. About 8 % of the scene's windows
   are validatable, ~95 % of them on one 2016 survey.
3. **Stratified result** (contour peak, WR17, CI from a spatial block bootstrap):
   band C GRD **+1.4 % (−5.4 … +7.9)**, SLC **−7.8 % (−14.3 … −1.2)**; band B GRD
   −8.1 %, SLC −2.4 % on 31/22 windows. Non-primary strata: +4 … +6 % in 0–12 m,
   −1 … −3 % on legacy cells. **The Block39 aggregate −0.8 % mixes terms of opposite
   sign** and is not the accuracy on directly measured bathymetry.
4. **SLC variance ladder** (same windows, spatial averaging only): single look −10.5 %
   (tail below −25 %: 36.6 %), 2 incoherent looks −14.2 % (39.0 %), 2×2 looks −9.0 %
   (35.9 %), multitaper K=4 −8.0 % (29.8 %), paired GRD +1.4 % (4.5 %). ENL rises
   0.81 → 2.5; the convergence is **not monotone and does not reach the GRD**. The
   multitaper wins with the least resolution loss, so the gain follows variance
   reduction rather than lost resolution.
5. **Budget.** Reference spectrum −16 … +17 % (dominant), estimator +6.6/+6.8 %
   (centroid − contour), processing −14 … +1 %, source class up to ~10 points between
   strata, bathymetric vertical uncertainty 0.2–0.6 %, water level ≤ 0.8 %, current
   ~1 %. Survey age / morphological change is declared and **not** quantified.
   Hierarchical MC over declared scenarios: median −6.1 %, p05/p95 −17.1 … +15.4 %,
   excluding the spatial term.

## Frozen for later blocks

- Admissibility rules, the 90 % window rule, the WR17 reference, the contour-peak
  primary estimator, `kmin_factor = 4`, the sector at 66.34° ± 30°, blocks of
  9 transects × 1024 m and `seed = 0`.
- Corrected nhatt/VIMS are a sensitivity stratum, not independent truth; the legacy
  correction is declared not independently validatable in this scene.

## Open / not closed here

- The authoritative test suite (`.venv-umbra-thesis` on Windows) could **not** be run:
  the Windows interpreter cannot be executed in the Linux device shell. The Linux run
  gives 375 passed / 20 failed, all pre-existing environment failures (temporary
  directories outside the repository, file deletion not permitted). Block40 stays
  "not verified in the authoritative environment" until
  `.\.venv-umbra-thesis\Scripts\python.exe -m pytest -q` is run and its real outcome
  recorded.
- Band A remains unvalidatable without either a smaller window (which would change the
  frozen spectral protocol) or a contemporaneous survey with a wider footprint.

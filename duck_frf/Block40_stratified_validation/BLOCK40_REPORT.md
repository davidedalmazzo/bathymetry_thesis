# Block40 — Stratified spatial validation by bathymetric source, and controlled audit of SLC variance reduction

Duck (FRF), Sentinel-1 scene of 2021-10-28 23:06:36 UTC, IW3/VV.
Protocol frozen before the analysis in `BLOCK40_PROTOCOL.md`; configuration, thresholds
and seeds in `BLOCK40_CONFIG.json`; inputs, code and outputs hashed in
`BLOCK40_MANIFEST.json`. HEAD at the start of the block: `7b168a5` (Block39). No
download, no catalogue query, no new FRF request, no commit, no push.

**Scope.** This block concerns only the spatial quantities `k` and `lambda`. It does
not measure `omega`, does not validate any temporal or cross-spectral phase, and is not
a validation of SAR bathymetric inversion.

---

## 1. Ground-truth provenance audit

Every cell was resolved to an actual survey through the BlueTopo contributor table
(`source_survey_id`, institution, survey dates, `coverage`, `bathy_coverage`, declared
uncertainty) plus the FRF survey DEM and the legacy grids
(`BLOCK40_SOURCE_INVENTORY.csv`, `BLOCK40_SOURCE_MASK.tif`, figure 1).

| source (key) | survey | dates | age at acquisition | direct | depth range (BlueTopo cells) | empirical NMAD vs FRF |
|---|---|---|---|---|---|---|
| `frf_survey_dem_2021` | FRF geomorphology survey DEM | 2021-10-21 | **7.96 d** | yes | −1.5 … 8.8 m | reference |
| `bluetopo_74730` | USACE/JALBTCX 2019 topobathy NC | 2019-06-18 → 06-25 | 856 d | yes | 3.2 … 16.2 m | **0.15 m** |
| `bluetopo_74726` | NOAA NGS/RSD NC1902-TB-C ellipsoidal DEM | 2019-11-26 → 2020-06-22 | 494 d | yes | −7.3 … 5.5 m (mostly land/beach) | **0.73 m** |
| `bluetopo_74492`, `76731` | USACE/JALBTCX 2016 "TopoBathDEM Duck" | 2016-06-30 → 07-07 | 1940 d | yes | 12.4 … 23.0 m | no FRF overlap |
| `bluetopo_76675`, `105310`, `105309` | **NOAA H12859 multibeam** | 2016-02-23 → 03-23 | **2046 d** | yes | 18.5 … 29.0 m | no FRF overlap |
| `bluetopo_74161`, `103627`, `74176` | H00965 / H09171 *interpolated* | 1868, 1970 | 55–153 y | **no** (`coverage = 0`) | 14 … 27 m | — |
| `bluetopo_0` | "NBS Generalization" | — | — | **no** | 0.2 … 2.0 m | — |
| `legacy_usgs` (nhatt), `legacy_usgs/vims` | USGS OFR 2011-1015, USGS/VIMS LARC | 2001, 2002 | 20 y | yes, but **bias-calibrated** | 9 … 30 m | 0.30 / 0.32 m after bias removal |

Findings that change the reading of Block39:

1. The contributor that Block39 counted as "BlueTopo modern" with NMAD 0.73 m is the
   **NOAA NGS 2019–2020 topobathy lidar**, whose cells run from the dune (+7.3 m NAVD88) to only 5.5 m of water, with a
   median depth of 0.6 m. Excluding it from the primary therefore changes little offshore,
   but its 0.73 m NMAD was never an offshore bathymetric uncertainty in the first place.
2. The deep half of the scene is **not** modern BlueTopo: 20.7 % of the cells are
   interpolated 1868/1970 hydrographic surveys or the "NBS Generalization" layer, and
   42.4 % are the bias-corrected legacy grids. Only 18.8 % are direct H12859 multibeam
   and 6.3 % direct 2019 lidar.
3. `74492` / `76731` are labelled "USACE topobathy DEM" but carry cells down to 23 m,
   deeper than green-lidar penetration at this site: the survey id does not identify the
   measurement technique, so these cells are treated as direct-but-unverified and never
   enter the primary.
4. Declared uncertainty for H12859 in the RAT is `vertical_uncert_fixed = 0.5 m`,
   `vertical_uncert_var = 0.01`, **not** the 0.28 m quoted in the task: reported as
   found.

Declared per-cell uncertainty, empirical NMAD against a higher-ranked survey, survey age
and morphological change are kept as four distinct quantities; no vertical NMAD is
reinterpreted as a morphological-change estimate anywhere in this block.

## 2. Admissible masks and window classification

Frozen rules (section 3 of the protocol) applied per depth band, then the 90 % footprint
rule per window (`BLOCK40_WINDOW_PROVENANCE.csv`, figure 2).

Admissible **cells** as a fraction of the band: 0–12 m **2.4 %**, 12–20 m **4.5 %**,
20–30 m **32.2 %**.

Primary-admissible **windows** (90 % rule):

| run | windows | primary A (0–12) | primary B (12–20) | primary C (20–30) | at 75 % | at 100 % |
|---|---|---|---|---|---|---|
| slc_near | 5364 | 0 | 26 | 0 | 79 | 7 |
| grd_near | 5853 | 0 | 34 | 0 | 89 | 2 |
| slc_far | 2213 | 0 | 0 | 581 | 622 | 468 |
| grd_far | 2218 | 0 | 0 | 601 | 641 | 486 |

**Band A is not validatable with the primary ground truth.** The FRF survey of
2021-10-21 covers xFRF 50–950 m, and no 512 m SAR window has more than **73 %** of its
footprint inside that footprint (the pier also removes the windows closest to it through
the bright-target rejection). The band was not rescued by lowering the threshold or by
substituting the 2019 lidar: the 0–12 m windows are dominated by `74730` (2019, 856 days
old, where the bars move) and are labelled `temporally_inadmissible`.

Band B survives only through the 12–16 m sliver of the 2019 USACE lidar: 26 (SLC) and 34
(GRD) windows, in 3 spatial blocks. The direct sources that actually cover 12–20 m are
the 2016 products, which the frozen date window excludes from the primary.

## 3. Legacy sources

nhatt and VIMS keep a constant bias estimated against modern cells **in the same area
used for validation**, so they are used only as a sensitivity stratum, never as
independent truth. An out-of-sample split was examined and not performed: the modern
cells available for calibration (FRF + 2019 lidar) sit in 0–16 m while the legacy cells
to be verified sit in 9–30 m, so a spatially separated calibration/verification split
would compare different depth regimes rather than the same surface. **The legacy
correction is therefore declared not independently validatable in this scene.**

## 4. Paired SLC/GRD comparison, stratified

1052 pairs (median centre offset 20.5 m, p90 42.7 m, max 50.0 m); footprints are
physically equivalent, never pixel-identical. Frozen configuration: WR17, contour peak,
`kmin_factor` 4, sector fixed at the WR17 mean direction at the peak frequency
(66.34°, half-width 30°), no water level applied, `U = 0`.

Primary (contour peak, `lambda_SAR / lambda_pred − 1`, CI from a bootstrap over spatial
blocks):

| band | product | windows | blocks | median | CI 95 % | NMAD |
|---|---|---|---|---|---|---|
| B 12–20 m (2019 lidar) | SLC | 22 | 3 | −2.4 % | −6.4 … +11.2 % | 8.1 % |
| B 12–20 m (2019 lidar) | GRD | 31 | 3 | −8.1 % | −21.2 … −0.9 % | 10.3 % |
| C 20–30 m (H12859) | SLC | 404 | 19 | **−7.8 %** | −14.3 … −1.2 % | 24.2 % |
| C 20–30 m (H12859) | GRD | 425 | 19 | **+1.4 %** | −5.4 … +7.9 % | 18.9 % |

Inside the primary band C stratum the error is itself depth-dependent (figure 3):
binned every 2 m it runs from about -7 % at 13 m to +10 … +13 % at 23-25 m and back to
-4 … +3 % at 27 m, on both products. The single band-C median therefore summarises a
trend, not a constant offset, and the bins are not independent samples.

Non-primary strata, same estimator (figure 3):

| stratum | windows | median | CI 95 % |
|---|---|---|---|
| GRD, 0–12 m, temporally inadmissible (2019 lidar) | 486 | +6.3 % | −2.6 … +10.8 % |
| GRD, 12–20 m, legacy corrected | 2251 | −1.1 % | −4.7 … +2.6 % |
| GRD, 20–30 m, legacy corrected | 1199 | −2.6 % | −6.3 … +2.6 % |
| SLC, 0–12 m, temporally inadmissible | 433 | +4.3 % | −0.9 … +9.3 % |
| SLC, 12–20 m, legacy corrected | 2196 | −8.6 % | −12.7 … −4.7 % |
| SLC, 20–30 m, legacy corrected | 1153 | −4.7 % | −9.7 … +0.7 % |

**Compensation is present.** The strata do not share a sign: shallow windows are
positive (+4 … +6 %), legacy-dominated windows are slightly negative, and the primary
H12859 stratum is +1.4 % (GRD) / −7.8 % (SLC). The Block39 aggregate −0.8 % is therefore
a weighted mixture of terms of opposite sign, dominated by the legacy class (42 % of the
scene), and cannot be read as the accuracy on directly measured bathymetry.

Estimator: the radial centroid sits **+6.6 %** (GRD) and **+6.8 %** (SLC) above the
contour peak in median, with p10/p90 −9 … +31 % (GRD) and −10 … +65 % (SLC): the choice
of estimator is a systematic term of the same size as the effect being measured
(figure 8).

## 5. SLC variance-reduction ladder (spatial only)

Same 607 native SLC windows of the primary set, same footprint, detrending, k grid,
`kmin`, sector and peak algorithm; only the averaging domain changes. No temporal
sub-aperture is created and no physical time is attached to any look; averaged pixels,
tapers and sub-blocks are not independent acquisitions
(`BLOCK40_SLC_VARIANCE_LADDER.csv`, figures 4–6).

| variant | looks | ENL (annulus) | half-power lobe width (rad/m) | median | CI 95 % | tail < −25 % | λ shift vs single look |
|---|---|---|---|---|---|---|---|
| slc_single_look | 1 | 0.81 | 0.0123 | −10.5 % | −18.9 … −5.6 % | 36.6 % | — |
| slc_incoherent_N2 | 2 | 1.46 | 0.0153 | −14.2 % | −21.7 … −8.3 % | 39.0 % | +0.3 % |
| slc_incoherent_N4 | 4 | 2.48 | 0.0307 | −9.0 % | −16.6 … −4.3 % | 35.9 % | −0.9 % |
| slc_multitaper_K4 | 4 | 2.43 | 0.0230 | −8.0 % | −15.1 … −2.2 % | 29.8 % | +0.6 % |
| grd_esa (paired) | — | — | — | **+1.4 %** | −5.1 … +8.4 % | **4.5 %** | — |

Reading:

- variance reduction works as designed — the ENL diagnostic rises 0.81 → 2.5 — but the
  **median does not converge to the GRD** and the improvement is **not monotone**: two
  azimuth looks are worse than the single look, because halving the azimuth extent costs
  spectral resolution before it buys enough averaging;
- the negative tail is reduced but not removed: 36.6 % → 29.8 % of windows still fall
  below −25 %, against 4.5 % for the GRD;
- the **multitaper is the best variant**: the largest median improvement and the largest
  tail reduction with the smallest resolution loss (width ×1.9 against ×2.5 for the 2×2
  incoherent looks) and a lobe displacement of +0.6 % in λ, 0.0° in bearing;
- the lobe is conserved: median |Δλ| ≤ 0.9 % and median bearing shift ≤ 1.7° across
  variants, so the gain is not a displacement of the physical peak.

Because the multitaper improves most while degrading resolution least, the gain follows
**variance reduction**, not resolution loss; but four spatial looks inside one window are
not enough to reach the GRD, whose windows contain both a larger number of independent
resolution cells and ESA multilooking.

Two caveats on this table. First, the single-look reference here has **no alongshore
averaging**, unlike the Block39 SLC runs (which average 9 neighbouring spectra), so it is
deliberately harsher than the −4.8 % of Block39 and the two numbers are not
interchangeable. Second, the blob centroid of the paper estimator can fall **inside** the
low-k hole when the selected blob straddles the cut; those cases are flagged
(`peak_at_kmin_edge`, 1.5–4.4 % of windows) and left in, since removing them would be a
post-hoc threshold change.

## 6. Water level, reference period, current

Primary: still-water depth on NAVD88, `eopNoaaTide` not applied (`qc_unknown`, not
`representative_eligible`). Frozen scenarios (figure 7, `BLOCK40_REFERENCE_SENSITIVITY.csv`):

| scenario | shift of the median error |
|---|---|
| `eta = 0.000 m` | 0.00 % (baseline) |
| `eta = +0.235 m` (the rejected preliminary reading) | −0.46 % |
| `eta = −0.100 m` | +0.28 % |
| `eta = +0.435 m` (prudential upper bound with setup) | −0.76 % |
| WR17 published `waveTp` = 11.396 s instead of the E(k) centroid | −1.8 % |
| WR17 discrete spectral maximum (11.76 s), monochromatic | −5.5 % |
| WR17 dominant-lobe half-power edges (T = 10.0 s / 12.9 s) | +16.5 % / −15.7 % |
| AWAC-11m spectrum | +5.2 % |
| 8m-array spectrum | −7.2 % |
| waverider-26m spectrum | −6.1 % |
| AWAC current projected on k (U = −0.108 m/s), monochromatic | +0.97 % |

The water level is a **sub-percent** term over the whole declared interval, at the
depths where primary windows exist (11.8–27.3 m, median 26.3 m). The **reference spectrum dominates**: the
spread between the gauges is ±5–7 % and the width of the WR17 dominant lobe alone spans
−16 … +17 %. The broad, slightly bimodal E(f) is not collapsed into a single Gaussian on
Tp anywhere in this block. The current term is computed only as a diagnostic: the AWAC
value is a profile average at 11 m taken 38 min from the acquisition and is not the
surface current advecting the Bragg waves.

Bathymetric vertical uncertainty translates into λ as +0.19 % (FRF 0.15 m), +0.19 %
(2019 lidar 0.15 m), +0.63 % (H12859 0.5 m declared) and +0.39 % (legacy 0.31 m) at the
median primary depth: an order of magnitude below the reference term.

## 7. Error budget

`BLOCK40_UNCERTAINTY_BUDGET.json` keeps the terms separate and never sums dependent
terms in quadrature:

- **spatial/statistical**: block bootstrap over 19–23 blocks (9 transects × 1024 m),
  seed 0, 2000 resamples — CI half-widths of 5–8 % on the primary strata; this is
  *only* the variability between blocks, not a total uncertainty, and the windows inside
  a block overlap by 50–100 m steps and are not independent;
- **bathymetry (vertical)**: 0.2–0.6 % on λ;
- **survey age / morphological evolution**: **not quantified** — 2046 days for H12859,
  856 for the 2019 lidar, ~20 years for the legacy grids; this is a declared gap, not a
  number;
- **water level**: ≤ 0.8 %;
- **reference spectrum**: −16 … +17 % (dominant);
- **current**: ~1 % as a diagnostic;
- **estimator choice**: +6.6 / +6.8 % (centroid − contour);
- **variance reduction / resampling**: −14 … −8 % across the SLC ladder, +1.4 % for the GRD;
- **source/contributor effect**: the stratum-to-stratum spread of section 4, up to ~10
  percentage points between shallow 2019-lidar windows and the primary H12859 stratum.

The hierarchical Monte Carlo over the declared scenarios (4000 draws, seed 0; η uniform
on [−0.100, +0.435] m, reference spectrum uniform over the declared options, a
per-realisation bathymetric offset N(0, 0.33 m) common to the realisation) gives a median
of **−6.1 %** with a 5th–95th percentile range of **−17.1 … +15.4 %**. This is the
scenario spread of the *median* bias and excludes the spatial term, which is reported
separately.

## 8. Required conclusions

1. **Does the spatial wavelength recovery stay accurate on directly measured,
   temporally admissible bathymetry?** Only where such bathymetry exists. On the H12859
   multibeam at 20–30 m the GRD contour peak gives **+1.4 % (CI −5.4 … +7.9 %, 425
   windows, 19 blocks)** and the SLC **−7.8 % (CI −14.3 … −1.2 %)**. At 12–20 m the
   primary sample is 22–31 windows in 3 blocks and its CI spans 20 percentage points.
   At 0–12 m there is no admissible window at all.
2. **Is the near-zero GRD result present in each source, or partly compensation?**
   Partly compensation. Shallow windows on the 2019 lidar give +6.3 %, legacy-dominated
   windows −1.1 / −2.6 %, primary H12859 +1.4 %, primary band B −8.1 %. The aggregate
   −0.8 % of Block39 is a mixture of terms of opposite sign and must not be quoted as the
   absolute accuracy.
3. **How much does the result change across 0–12, 12–20 and 20–30 m?** 0–12 m: not
   validatable (no admissible window; the non-admissible stratum there reads +4 … +6 %).
   12–20 m: −8.1 % (GRD) / −2.4 % (SLC) on 31/22 windows, conditional. 20–30 m: +1.4 %
   (GRD) / −7.8 % (SLC) on ~400 windows.
4. **How much truly validatable coverage remains?** By cells: 2.4 % of band A, 4.5 % of
   band B, 32.2 % of band C. By windows: 0 / 26 / 581 (SLC) and 0 / 34 / 601 (GRD) out of
   7577 and 8071 windows — i.e. **about 8 % of the windows** of the scene, all of them at
   12–30 m, and ~95 % of those rest on a single 2016 multibeam survey.
5. **Does controlled SLC variance reduction remove the negative tail and converge to the
   GRD?** No. It improves the median from −10.5 % to −8.0 % and the tail from 36.6 % to
   29.8 % (multitaper), it is not monotone in the incoherent ladder, and it stays far
   from the GRD (+1.4 %, tail 4.5 %). Four spatial looks inside a window are not a
   substitute for the GRD's multilooking.
6. **Is the improvement due to less speckle or to lost resolution?** To variance
   reduction: the multitaper, which loses the least resolution (width ×1.9 vs ×2.5) and
   displaces the lobe the least (+0.6 % in λ, 0.0° in bearing), improves the most, while the two-look variant,
   which loses azimuth extent first, is the worst. Resolution loss alone would have
   favoured the 2×2 incoherent variant.
7. **How much do the estimator, bathymetry, water level, period and current weigh?**
   Reference spectrum −16 … +17 %; estimator +6.6 / +6.8 %; variance reduction /
   processing −14 … +1 %; source class up to ~10 points between strata; bathymetric
   vertical uncertainty 0.2–0.6 %; water level ≤ 0.8 %; current ~1 %. The reference and
   the estimator dominate everything that the bathymetry contributes.
8. **What is robust, conditional or not identifiable?** Robust: the GRD result on direct
   H12859 bathymetry at 20–30 m; the insensitivity to water level; the SLC short-λ tail
   and its partial reduction by multitapering. Conditional: band B (small sample, one
   contributor); every comparison with Block39 aggregates; the radial centroid.
   Not identifiable here: band A at the frozen threshold; the independence of the
   corrected legacy grids; morphological change since each survey; and anything about
   `omega`, temporal phase or a complete bathymetric inversion — none of which this block
   touches.

## 9. Tests and environment

`tests/test_block40.py` adds 16 targeted tests: contributor and date extraction,
`coverage` / `bathy_coverage` reading, direct / interpolated / generalised recognition,
pre-2010 exclusion, exclusion of the > 0.5 m contributor, H12859 recognition, source
fraction inside a rasterised footprint, mixed-window classification, the exact 90 %
threshold (0.8999 is rejected), geographic identity and single use in the pairing,
multilook normalisation and lobe conservation on a synthetic sinusoid with speckle,
variance reduction without a false resolution gain, dependence of overlapping looks,
multitaper reproducibility, water-level scenarios and the sign of the current term,
conjugate-lobe and axial-bearing handling, the `kmin` cut and its edge flag, and the
preservation of the frozen Block39 artefacts.

Suite executed in the Linux device shell (`python 3.10.12`, numpy 2.x, scipy, rasterio):
**375 passed, 7 failed** outside `test_frf_block33.py`, plus 13 failures in that file.
All 20 failures are the same pre-existing environment failures as before Block40: they
come from temporary directories created outside the repository root and from file
deletion not being permitted in this shell, not from Block40 code. **They are not
declared harmless**: the authoritative run in `.venv-umbra-thesis` on Windows could not
be performed from here — the Windows interpreter cannot be executed in this Linux shell
(`Exec format error`) — so Block40 is closed *pending* that run:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe -m pytest -q
```

Until its real outcome is recorded, the suite status of this block is "not verified in
the authoritative environment".

## 10. Deliverables

`BLOCK40_PROTOCOL.md`, `BLOCK40_CONFIG.json`, `BLOCK40_SOURCE_INVENTORY.csv`,
`BLOCK40_SOURCE_AUDIT.json`, `BLOCK40_SOURCE_MASK.tif`, `BLOCK40_WINDOW_PROVENANCE.csv`
(+ summary), `BLOCK40_WINDOW_RESULTS.csv`, `BLOCK40_MATCHED_RESULTS.csv`,
`BLOCK40_STRATIFIED.json`, `BLOCK40_SLC_VARIANCE_LADDER.csv`, `BLOCK40_LADDER_SUMMARY.json`,
`BLOCK40_REFERENCE_SENSITIVITY.csv`, `BLOCK40_UNCERTAINTY_BUDGET.json`,
`BLOCK40_SUMMARY.json`, `BLOCK40_MANIFEST.json`, `forward/<run>/` and `figures/fig1..fig8`.

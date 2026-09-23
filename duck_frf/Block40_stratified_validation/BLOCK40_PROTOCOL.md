# Block40 — Frozen protocol

Written and frozen **before** running any Block40 analysis. Thresholds, the primary
estimator, admissibility criteria, sensitivity scenarios and seeds below must not be
changed after seeing results; any deviation is recorded as a numbered amendment at the
end of this file, with its date and reason.

Repository root resolved with `git rev-parse --show-toplevel`; HEAD at freeze time is
`7b168a5` (Block39). Block35–39 artefacts are read-only inputs.

## 0. Scope

Block40 is a **spatial audit only**: it concerns the recovered wavenumber `k` and
wavelength `lambda`. It does not measure `omega`, does not validate any temporal or
cross-spectral phase, and is not a validation of SAR bathymetric inversion. No
download, catalogue query, new FRF request, Umbra/Vandenberg processing or AIS work is
performed. No commit or push.

## 1. Inputs (all local, frozen)

- Sentinel-1 IW SLC `S1A_IW_SLC__1SDV_20211028T230636_..._B6FA.SAFE` (VV, IW3).
- Sentinel-1 IW GRDH `S1A_IW_GRDH_1SDV_20211028T230637_..._8C9F.SAFE` (VV).
- Block39 window sets and stored spectra:
  `duck_frf/Block39_s1_paper_confirm/{slc,grd}/{near,far}` (partial spectra) and the
  `*_k4` finalisations (primary low-k factor).
- Ground truth `outputs/ground_truth_s1a_20211028_ext20`
  (`bathymetry_merged_utm.tif`, `bluetopo_bbox.tif` + `.provenance.json`,
  `cudem_bbox_navd88.tif`, `MERGE_REPORT.json`), FRF survey DEM cache
  `outputs/ground_truth_s1a_20211028/frf_survey_dem.npz`, FRF dossier
  `outputs/ground_truth_s1a_20211028/frf_observations/s1a_20211028_duck`.

If an input needed by a step is not available locally, that step is declared blocked
and documented; it is never replaced by a less suitable source.

## 2. Ground-truth provenance audit

Every ground-truth cell is resolved to an actual survey, not to a year alone:
BlueTopo contributor id, `source_survey_id`, `source_institution`,
`survey_date_start/end`, `coverage`, `bathy_coverage`, declared fixed/variable vertical
uncertainty, native resolution, datum, plus the empirical agreement with the FRF survey
DEM where the two overlap. Four quantities are kept distinct and never converted into
one another:

1. declared per-cell vertical uncertainty;
2. empirical agreement (NMAD) with a higher-ranked survey;
3. survey age at 2021-10-28;
4. morphological change since the survey (not estimated here; a vertical NMAD is
   never reinterpreted as a morphological-change estimate).

## 3. Primary admissibility by depth band

A cell is `direct` only if `coverage = 1`, `bathy_coverage = 1` and the
`source_survey_id` contains neither `interpolated` nor `Generalization`.

- **Band A, 0–12 m.** Admissible only inside the footprint of the FRF survey DEM
  `FRF_geomorphology_DEMs_surveyDEM_20211021.nc` (7.96 days before the acquisition).
  The FRF grid is never extrapolated beyond its own footprint.
- **Band B, 12–20 m.** Admissible only for direct surveys with
  `2019-01-01 <= survey_date_start <= 2020-12-31` **and** empirical NMAD vs the FRF
  survey DEM <= 0.50 m. A contributor whose empirical NMAD exceeds 0.50 m is excluded
  from the primary result even if direct and recent; a contributor with no FRF overlap
  cannot be certified and is likewise excluded from the primary. If no source passes,
  the band is declared **not validatable with the primary ground truth** — nhatt,
  VIMS, CUDEM or interpolated BlueTopo are not substituted.
- **Band C, 20–30 m.** Admissible for the direct NOAA H12859 (2016-02-23 →
  2016-03-23) contributors. Declared vertical uncertainty is taken from the BlueTopo
  RAT and reported as found; any other 2016 survey enters only as a separate,
  documented analysis.

## 4. Window classification

For every SAR window the fraction of its exact native footprint falling in each source
class is computed. The window class is:

- `primary_admissible` — >= 90 % of the footprint in a single class admissible for the
  window's depth band;
- `mixed_source` — no single class reaches the threshold;
- `direct_but_uncertain` — dominant class direct but failing the NMAD/date criteria
  (e.g. NOAA NGS 2019–2020 at NMAD ~0.73 m);
- `interpolated` — dominant class interpolated or generalised;
- `legacy_calibrated` — dominant class is a legacy grid whose bias was removed against
  modern data (nhatt, VIMS);
- `temporally_inadmissible` — dominant class direct but outside the band's date window;
- `provenance_unknown` — provenance not resolvable.

Primary threshold **90 %**, frozen. 75 % and 100 % are computed as descriptive
sensitivities only and never replace the primary.

## 5. Legacy sources

nhatt (2001) and VIMS (2002) carry a constant bias estimated against modern data in
the same area used for validation; they are therefore **not independent ground truth**
and appear only as sensitivity. If an out-of-sample test is attempted, the calibration
and verification regions are separated spatially, the bias is estimated on the
calibration region only and applied to the excluded region; if the coverage does not
allow a credible split, the correction is declared not independently validatable.

## 6. Paired SLC/GRD comparison — frozen configuration

- reference gauge: **FRF:waverider-17m**, predeclared;
- primary estimator: **contour peak** (20 levels, log10 scaling, largest blob nearest
  the origin), as frozen in Block39;
- `kmin_factor = 4` (`k >= 4*pi/window`);
- directional sector, frozen before results: axial bearing **66.34°**, the WR17
  `waveMeanDirectionPeakFrequency` at the acquisition (peak direction 70°, directional
  spread 23.2°), half-width **30°**;
- radial centroid kept as a **secondary** estimator; the contour–centroid difference is
  always reported, never suppressed;
- depths 7–27 m, further split by band A/B/C;
- no water level applied as truth (band 3 = still-water depth on NAVD88);
- `U = 0` in the primary;
- pairing: an SLC window and a GRD window are paired when their centres are within
  **25 m** (near, 512 m windows) or **50 m** (far, 1024 m windows), they fall in the
  same depth band and the same source class; the residual centre offset distribution is
  reported. Footprints are physically equivalent but not pixel-identical.

## 7. SLC variance-reduction ladder (spatial only)

Same native SLC windows, identical footprint, detrending, primary taper, k grid, kmin,
sector, peak algorithm and identifiability criteria. Only the averaging domain changes:

1. `slc_single_look` — one periodogram, no averaging (reference);
2. `slc_incoherent_N2` — incoherent average of 2x2-block sub-periodograms;
3. `slc_incoherent_N4` — incoherent average of 4x4-block sub-periodograms;
4. `slc_multitaper_K4` — 2-D Slepian (DPSS) multitaper, NW = 2.5, K = 4;
5. `grd_esa` — ESA-focused GRDH as the external reference.

No temporal sub-apertures are created and no physical time is attached to any look.
Averaged pixels, tapers and overlapping looks are **not** independent acquisitions and
are never treated as Monte-Carlo replicas. For each variant the report documents the
averaging domain, normalisation, effective resolution, spectral response, estimated
ENL, resolution loss, look correlation, lobe-position conservation and the effect on
the short-wavelength tail. No threshold is retuned to improve convergence.

## 8. Water level, period, current

- Primary: depth on NAVD88, no `eopNoaaTide` applied (`qc_unknown`, not
  `representative_eligible`).
- Frozen scenarios: `eta = 0.000 m`; `eta = +0.235 m` (the rejected preliminary
  reading, a sensitivity, not the event truth); prudential interval
  `eta in [-0.100, +0.435] m` = measured value ±0.10 m gauge/preliminary uncertainty
  plus 0…+0.20 m unmodelled wave setup, declared here before any result.
- Frequency scenarios: WR17 discrete spectral maximum (primary); WR17 published
  `waveTp` (parabolic fit) as an alternative; the dominant-lobe half-power interval of
  the WR17 E(f); the other gauges (AWAC-11m, 8m-array, WR26) as alternative references.
  A broad or multi-peaked spectrum is never collapsed into a single Gaussian sigma on
  Tp.
- Current: `U = 0` primary; AWAC-11m depth-profile average
  (E = +0.014, N = -0.302 m/s, 38 min offset) projected on the wave direction as a
  diagnostic only, with the explicit caveat that a profile-averaged current at 11 m is
  not the surface current advecting the Bragg waves.

## 9. Uncertainty budget

Terms are kept separate: algorithmic/statistical spatial term, dependence between
overlapping windows, bathymetric uncertainty, survey age and possible morphological
evolution, water level, reference period, current, estimator choice, variance
reduction, source/contributor effect. The block bootstrap quantifies **only** spatial
variability between blocks and is never called a total uncertainty. Blocks: 9
consecutive transects x 1024 m along-transect, 2000 resamples, `seed = 0`. Any
combined figure is built as declared scenarios or a hierarchical Monte Carlo, with
distributions documented and dependent terms not summed in quadrature.

## 10. Reporting rules

The report must not claim that temporal phase is validated, that `omega` is measured,
that full bathymetric inversion is validated, that source differences are certainly
caused by bar migration, that overlapping windows are independent observations, that
corrected nhatt/VIMS are independent truth, or that the aggregate -0.8 % of Block39 is
by itself the absolute accuracy. Insufficient primary coverage is documented as a
limit; thresholds are not relaxed and legacy sources are not reintroduced to obtain a
result.

## Amendments

- (none at freeze time)

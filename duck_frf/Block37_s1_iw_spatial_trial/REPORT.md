# Block37 — first real Sentinel-1 Duck spatial trial

## Decision

The fixed Duck IW3/VV intensity contains a reproducible spatial lobe under the
frozen primary estimator.  The three correlated, co-centred windows give
`k=0.08146–0.08200 rad/m`, wavelength **76.63–77.14 m**, and axial bearing
**85.36–85.88° true**.  The lobe/background ratio is 54.8–93.6.  This passes
the preregistered primary stability gate and its axial mismatch from the
measured FRF propagation direction is 19.0–19.5°, inside the frozen 25° gate.
The association is therefore classified **identifiable**, with an important
interpolation sensitivity described below.  This is not a validation of a
temporal SAR method or of bathymetric inversion.

## Download and integrity

The only downloaded radar product was the frozen UUID
`c49a9c1f-9b00-5676-ab05-683975d898a2`.  The retained ZIP is exactly
7,799,368,890 bytes; vendor MD5 `d1886a92315be184489eea0e072c0578` and local
SHA-256 `0b302e9ace9b3b1714a4beb40c57c30fb6a7cc3c00e1b9711f1dae6ef7275050`
both verify.  The archive has 46 safe members and 7,799,351,858 uncompressed
file bytes.  Authentication and the single continuous archive stream used two
HTTP transactions and 7,799,372,638 response bytes.  No secret was logged.

The preserved SAFE member used here is
`measurement/s1a-iw3-slc-vv-20211028t230637-20211028t230702-040326-04c765-006.tiff`
(1,341,901,640 bytes).  Rasterio identifies one 24,714 × 13,572
`complex_int16` band.  Both real and imaginary components are non-trivial;
there is no declared TIFF nodata value.  Invalid source samples are instead
controlled by the exact annotation intervals.

## Pixel support and radiometry

All bilinear contributors lie in IW3 burst 0.  Across increasing windows the
bounded source reads span samples 14,277.94–14,437.42 and lines
947.21–976.31; no seam, overlap duplication, or invalid-to-zero replacement is
used.  The complex raster is resampled to the frozen FRF grid (4 m × 12 m).
This sampling is not claimed as effective SAR resolution.

Primary power is `sigma0 = |DN|² / sigmaNought²`.  Raw DN and calibrated LUT
processing select the same lobe.  The prefixed thermal-noise sensitivity uses
`(|DN|² − noiseRangeLut·noiseAzimuthLut)/sigmaNought²`; 12.1–13.0% of its
samples are non-positive.  Those samples remain masked, so that sensitivity is
reported unavailable rather than filled, clipped, or Fourier transformed.

## Visual audit

The ROI is fully marine in the selected burst and does not include the coast or
FRF pier.  The calibrated intensity is speckled, with weak repeated,
approximately alongshore crest-like streaks and several isolated bright
pixels; the waves are **visible but not cleanly separable by visual inspection
alone**.  No ship or wake is confidently identifiable.  No burst join crosses
the ROI.  The burst overview shows large-scale radiometric/TOPS illumination
structure outside the ROI, while a plane is removed locally before the primary
FFT.  The spectral decision is numerical, not visual.

## Spatial spectrum

| FRF window | k (rad/m) | wavelength (m) | axial bearing | lobe/background | half-power radial width (rad/m) |
|---|---:|---:|---:|---:|---:|
| 300 × 300 m | 0.081997 | 76.627 | 85.882° | 54.83 | 0.01545 |
| 400 × 300 m | 0.081884 | 76.732 | 85.355° | 70.41 | 0.02050 |
| 500 × 300 m | 0.081456 | 77.136 | 85.372° | 93.63 | 0.01433 |

The estimator uses plane detrending, one separable Hann taper, NumPy's
negative-exponent FFT, conjugate averaging, and 2× padding.  Padding only
interpolates the spectrum.  Unpadded physical bin steps are 0.02094 rad/m in
both axes for 300 m, 0.01571/0.02094 for 400 × 300 m, and
0.01257/0.02094 for 500 × 300 m.  These steps, the interpolated maximum, and
the measured half-power widths are not interchangeable uncertainty measures.
Conjugate closure is exact after the explicitly tested discrete-index average;
the reported sign is one canonical member of an axial pair.

Quadratic detrending, Tukey taper, and raw-DN power retain 75.94–77.62 m and
85.35–86.93°.  Nearest-neighbour resampling instead selects 42.05–45.38 m at
43.16–43.92°.  This is a material gridding sensitivity, plausibly related to
nearest-neighbour repetition on the rotated, anisotropic source grid; it is not
hidden in the primary spread.  The primary gate remains passed because its
thresholds were frozen specifically across the three bilinear primary windows,
but the nearest result limits how strongly the lobe can be interpreted.

## FRF association

The SAR result was written before the external comparison.  WR17's complete
nearest spectrum is 396.323 s after the acquisition, `Hm0=1.710 m`, published
`Tp=11.396 s`, discrete maximum 0.085 Hz (11.765 s), and half-power band
0.0775–0.100 Hz.  AWAC is 395.823 s after, `Hm0=1.717 m`, published
`Tp=10.870 s`, discrete maximum 0.0925 Hz (10.811 s), and half-power band
0.085–0.100 Hz.  Their peak-frequency mean directions are respectively
66.342° and 66.408° **from**, hence 246.342°/246.408° propagation toward.
The axial SAR differences are 19.0–19.5°.  Mean and modal direction, spread
(23.2–24.2°), published Tp, discrete maximum, and half-power band remain
separate.  Both instruments support one broad compatible system rather than a
forced exact one-bin correspondence.

## Conditional dispersion inversion and survey context

Because the frozen association gate passes, a conditional inversion was run
with the median primary `k=0.081884 rad/m`; the discrete FRF maxima, not a
survey-tuned period, supply absolute frequency.

- WR17: nominal `h=4.535 m`; projected-current sensitivity `U=-0.5…+0.5 m/s`
  gives 5.346–3.818 m; primary-k spread alone gives 4.586–4.522 m; its
  half-power frequency band gives 3.717–6.573 m.
- AWAC: nominal `h=5.477 m`; the same current sensitivity gives
  6.419–4.651 m; primary-k spread alone gives 5.539–5.461 m; its half-power
  band gives 4.535–6.573 m.

No current was fitted to the survey.  The October 24 observations contain
713/949/1,136 points in the three windows.  Their 5/50/95% NAVD88 bed
elevations are respectively `[-7.61,-6.48,-4.99]`,
`[-7.94,-6.46,-4.44]`, and `[-8.13,-6.34,-3.97] m`.  These are bed elevations,
not event water depths.  A verified event water level and compatible datum
conversion are absent, so the overlap of the conditional depth ranges with
bed-elevation magnitudes is encouraging context but **not a bathymetric
validation**.

## Outcome by gate

- **A — visibility:** yes, but weak and speckle-contaminated.
- **B — measurability:** yes under the frozen primary bilinear estimator;
  nearest-neighbour sensitivity is a documented caveat.
- **C — association:** identifiable with the broad, mutually consistent FRF
  system under the frozen 25° axial criterion.
- **D — inversion:** conditionally identifiable; omega bandwidth and unknown
  projected current dominate the stated range.
- **E — validation:** not established because NAVD88 bed elevation is not
  instantaneous water depth and the interpolation sensitivity remains open.

Numerical tables are in `SPATIAL_RESULTS.csv`, `FRF_ASSOCIATION.json`,
`CONDITIONAL_INVERSION.csv`, and `SURVEY_COMPARISON.json`.  Figures are under
`figures/`; exact source windows and I/Q checks are in `PIXEL_SUPPORT.json`.


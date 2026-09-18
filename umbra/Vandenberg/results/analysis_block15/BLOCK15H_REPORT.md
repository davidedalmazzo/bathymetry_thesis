# Block15H — BP12 spatial-resolution audit

## Scope and frozen input

This audit reads only the existing BP12 complex stack, 32 × 288 × 130 at 5 m.
The fixed Block15B–G candidate remains `[133,65]`; it was not reselected.
Preprocessing is exactly Block15B: intensity `abs(z)^2`, global-plane removal,
separable Tukey alpha 0.1, then unpadded shifted 2-D FFT. No CPHD/SICD signal
read, new SAR stack, dwell sweep, frequency/period correction, bathymetric
inversion, or real Q2 fit occurred.

## Resolution scales

`delta_bin` is 0.00436332 rad/m parallel to the BP12 wavevector/grid axis and
0.00966644 rad/m perpendicular. It is only sample spacing, not resolution.

The explicitly applied Tukey window has power FWHM 0.935 and 0.939 native bins
(0.00408028 and 0.00907782 rad/m); its equivalent noise/lobe widths are 1.042
and 1.047 bins. First numerical minima are at 1.056/1.061 bins, contain 91.43%
of kernel energy, and the first sidelobe is -13.31 dB in power. The finite
sampled Tukey has no asserted exact analytical zero. These figures describe the
additional analysis window, not the unknown complete backprojection/SAR PSF.

The measured BP12 mean-power lobe through the fixed bin is broader: local
power FWHM is 2.223 bins parallel and 1.452 bins perpendicular. The conservative
effective radial scale for this audit is therefore 2.223 bins (0.009700 rad/m),
not the 0.935-bin ideal-window FWHM.

## Fixed-neighborhood result

The declared 13 × 13 neighborhood contains eight nonperiodic local maxima above
5% of the fixed-peak power. The fixed bin is a local maximum, but is the largest
instantaneous neighborhood bin in only 12/32 looks. The strongest mean-power
neighbor is `(132,65)` at 80.8% of peak; a notable feature at `(136,65)`, three
parallel bins away, is 70.5% of peak. That separation is only 1.35 measured
radial FWHM. It is not a clean second resolution element.

The signed Block15B-reference slope at the fixed bin is +0.412066 rad/s
(`R²=0.99446`, endpoint 3×3 MSC=0.41688). Neighbor slopes vary strongly, but
their amplitude trajectories are commonly correlated with the peak (for example
0.932 at `(136,65)`). Such scatter cannot be used as independent frequency
estimates and no slope was corrected or reinterpreted.

## Dependence and classification

The ideal Tukey-window covariance rank of the 169-bin neighborhood is 155.91;
this is only a white-input/window diagnostic and does not turn physical wave
bins into independent replicates. The real lobe, common temporal looks, shared
detrend and conjugacy add dependence not represented by that rank.

- Amplitude structure: **partially separated** — shoulders/local maxima exist,
  but the nearest material feature is only 1.35 observed FWHM away and the
  fixed maximum is not stable look-by-look.
- Phase structure: **not identifiable from neighboring bins**.
- Temporal-slope structure: **descriptive only**; correlated neighbor series
  do not demonstrate independent components.
- Overall: **not identifiable as multiple spatial components at BP12 effective
  resolution**. The data remain compatible with one broadened/overlapped lobe
  or a mixture; this is not a claim that a second physical wave is absent.

## Limited synthetic calibration and Block15G link

The same 288 × 130 grid, Tukey window and 32 BP12 times were used for five
predetermined coefficient-only cases. A single isolated lobe gives one maximum;
an off-grid single lobe can create two sampled local maxima. The deliberately
weak 1.5-bin component remains one maximum. Thus a local maximum count is not a
component count. The 6-bin and 1-bin synthetic cases are retained as response
controls, but their apparent maxima depend on coherent finite-record mixing;
they are not fitted to BP12.

The observed three-bin feature is 1.35 measured-lobe widths away, not “three
independent bins”. It lies between the Block15G one-bin-overlap and six-bin
clearly separated ideals, and is closer to a partially-overlapped regime. It
does not license a real-data Q2 claim.

## Stop

Cross-spectrum convention remains `F_secondary * conj(F_reference)` and slope
signs are retained. All prior results are frozen. **STOP — Block15H complete.**

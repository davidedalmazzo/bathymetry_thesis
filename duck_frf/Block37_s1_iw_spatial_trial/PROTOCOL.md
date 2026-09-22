# Block37 frozen protocol — first real Duck Sentinel-1 spatial trial

Frozen before reading a measurement TIFF or inspecting SAR pixels. The product,
Block35 ROI and Block36 geometry are immutable inputs. No alternate scene,
preflight rerun, temporal-frequency inference or method choice is introduced.

## Download and integrity

The only authorized large transfer is UUID
`c49a9c1f-9b00-5676-ab05-683975d898a2`, expected archive name
`S1A_IW_SLC__1SDV_20211028T230636_20211028T230703_040326_04C765_B6FA.zip`,
catalogue length 7,799,368,890 bytes and vendor MD5
`d1886a92315be184489eea0e072c0578`. Data stay under the Git-ignored Block37
directories. Require at least 32 GiB free before starting. Preserve `.part`,
archive and extracted SAFE; never delete another product automatically.

Resume requires HTTP 206 and a matching `Content-Range`; a 200 response to a
nonzero Range is rejected before its body is consumed. HTTPS redirects are
bounded and provenance-recorded. JSON/HTML, wrong length, non-ZIP magic,
unsafe ZIP paths, local MD5 mismatch or SAFE identity mismatch fail closed.
Compute local SHA-256. Authentication and stream attempts have a separate
Block37 ledger; they do not consume/reset Block36's metadata tranche.

## Frozen pixel support and windows

- VV, IW3, burst 0 only; primary ROI FRF x=300–850 m, y=700–1000 m.
- Three co-centered FRF-metric windows at (575,850) m: 300×300, 400×300 and
  500×300 m. They are fixed independently of waves, FRF frequencies and depth.
- Sample the source complex SLC through annotation geolocation onto the fixed
  FRF grid at dx=4 m, dy=12 m. Bilinear complex interpolation is primary;
  nearest-neighbor is a labelled interpolation sensitivity. Report the source
  window and never imply the 4 m cross-grid creates azimuth resolution.
- Exact Block36 per-line valid intervals must contain every contributing source
  sample. No burst seam, overlap duplication or invalid-to-zero replacement.

## Radiometry and visual audit

Verify TIFF identity/dimensions/bands/sample type and complex I/Q semantics
against manifest/annotation before analysis. Read bounded windows only. Primary
intensity is calibrated sigma0 power using the matching IW3/VV LUT and documented
power-domain convention. Raw DN power and calibrated noise-subtracted power are
prefixed sensitivities; negative post-noise values are masked/flagged, never
silently clipped into plausible sea. Log intensity is display-only.

Figures must show burst/ROI location, linear/log intensity, valid mask, north,
local range/azimuth and measured FRF direction. Record periodic waves, multiple
bands, gradients, TOPS/azimuth patterns, ships/wakes, pier/coast and speckle,
without allowing visual impression alone to select a result.

## Frozen spectral estimator

For every primary window: fit/subtract a plane, apply a separable 2-D Hann once,
then `numpy.fft.fft2` (negative exponent), `fftshift` and 2× zero padding as
interpolation only. Sensitivities are quadratic detrending and Tukey alpha=.25,
plus the declared radiometric/interpolation variants. No expected-wave filter,
bathymetry band or FRF-centered search is allowed.

Search conjugate-averaged power over the whole sampled spectrum except the
central ±2-bin window-response region. Keep both conjugate coordinates. Transform
image/grid wavevectors to East/North using the verified metric mapping; report
discrete bin, interpolated center, physical window response, lobe width,
orientation and lobe/annular-median power. Bin step, zero-padding, physical
resolution, lobe width and estimator/variant spread remain distinct.

A stable SAR lobe requires all geometrically available primary sizes to select
the same axial family, wavelength relative range ≤20%, axial direction range
≤15°, conjugate closure and lobe/background ≥3. Overlapping windows are
correlated sensitivities, never independent replicates. If competing lobes or
failed stability prevent a unique result, classification is not identifiable.

## FRF association and conditional inversion

Only after saving SAR-only results compare the complete frozen WR17/AWAC spectra,
published Tp, discrete peaks, half-power widths, directions, QC, offsets and
distances. A direction compatibility tolerance of 25° is preregistered; it does
not rotate or choose the SAR peak. A stable unique SAR lobe plus one compatible
dominant FRF system is `identifiable`; a broad/multimodal reference or competing
compatible pairing is `compatible but ambiguous`; otherwise `not identifiable`.

Run dispersion inversion only for `identifiable`. Use
`omega_absolute = omega_intrinsic + k dot U`; nominal U=0 and fixed projected
current sensitivities −0.5, −0.25, 0, +0.25, +0.5 m/s. Propagate k estimator
spread and the observed omega band separately. Never fit current/depth to the
survey. Compare afterward with October 24 NAVD88 bed elevations while keeping
bed elevation, instantaneous depth, water level, current, datum and spatial
coverage distinct. Negative/ambiguous outcomes at every gate are valid.

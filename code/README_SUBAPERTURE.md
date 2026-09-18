# Metadata-aware sub-aperture library

Implementation: `code/umbra_sar/subaperture.py` and
`code/umbra_sar/cross_spectrum.py`.

## Non-negotiable conventions

For the umbra/Vandenberg SICD metadata:

- `Grid.Type = RGAZIM`;
- SICD Row / NumPy axis 0 is range;
- SICD Col / NumPy axis 1 is Doppler/azimuth;
- `Grid.Col.Sgn = -1`;
- focused-image to shifted Doppler spectrum is
  `fftshift(fft(image, axis=1))`;
- shifted spectrum to focused image is
  `ifft(ifftshift(spectrum), axis=1)`.

The implementation follows SarPy `fft_sicd`/`ifft_sicd`. Synthetic tests also
show explicitly that substituting IFFT for the forward transform reverses
positive and negative Doppler bands.

The functions accept any Row/range chunk, but that chunk must retain the full or
a separately stability-tested Col/azimuth extent. A small azimuth ROI must not be
cut before `image_to_shifted_spectrum`.

## Time quantities

`ApertureDurations` has three separate fields:

- `processed_aperture_duration_s`: SICD `TEndProc-TStartProc`, equal to
  18.068061721230308 s here;
- `sicd_timeline_collect_duration_s`: 22.547940446666665 s;
- `cphd_slow_time_dwell_s`: 22.540812513364376 s.

Only `processed_aperture_duration_s` is used by
`sicd_bandwidth_fraction()`. A 20 s SICD request therefore raises an error even
though CPHD contains more than 20 s of slow time. CPHD dwell is retained as
provenance for a future CPHD focusing/time-mapping stage.

Every linear bandwidth-to-time result is named `nominal` and carries
`timing_model = nominal_linear_bandwidth_to_processed_time`.

## Processed support and 6 s plan

`ProcessedSupport.from_axis_metadata()` uses Col.SS, DeltaK1/2 and a constant
DeltaKCOAPoly. It refuses a spatially varying DeltaKCOAPoly because one global
support would then be invalid.

For 107,800 columns, the real metadata gives:

- support `10780:97020` (half-open);
- 86,240 bins, or 80% of the FFT;
- requested 6 s fraction `6/18.068061721230308 = 0.332077678977...`;
- realized width 28,638 bins;
- realized nominal duration 5.999920588736 s after integer-bin quantization.

`plan_band`, `plan_centered_band`, and `plan_tiled_bands` support explicit band
centers and overlap. The non-overlapping 6 s plan contains three bands; a 50%
overlap plan contains five.

## Windows and normalization

`make_window()` implements:

- rectangular;
- Tukey/raised-cosine with configurable alpha.

The default `energy` normalization scales each window so
`sum(abs(w)**2) == N`, matching the total window energy of a length-N rectangular
window. The metadata records applied scale, coherent gain, RMS gain, energy sum,
and ENBW. `coherent` and `none` normalization modes are also available.

Rectangular, disjoint windows that cover the complete occupied support
reconstruct the original supported image when their complex sub-looks are
summed. Smooth windows are not claimed to satisfy that partition-of-unity test.

## Native SVA weighting

The SICD declares `SVA` for Row and Col but provides no WgtFunct samples. The
context records:

```text
Native SVA weighting is declared without WgtFunct samples; exact deweighting is unavailable
```

This is a provenance warning, not a processing exception. The library preserves
the native focused data and applies only the explicitly requested additional
window. It does not invent or approximate missing SVA weights.

## Cross-spectrum convention

`spatial_cross_spectrum(reference, secondary)` returns:

```text
C_secondary,reference(k) = F_secondary(k) * conj(F_reference(k))
```

A `+phi` phase advance of a positive-frequency Fourier component in the
secondary image is therefore returned as `+phi`. Swapping the two operands
returns `-phi`. Real/intensity inputs have a conjugate negative-frequency peak
with phase `-phi`.

The synthetic end-to-end test uses intensity images made from complex
sub-looks. This establishes the code's sign convention, but does not yet declare
that intensity cross-spectra are the final ocean-wave retrieval object; that
scientific choice still requires primary-literature verification.

## Metadata-only planning example

```powershell
& '.venv\Scripts\python.exe' -B code\plan_subapertures.py `
  --sicd-xml umbra/Vandenberg\metadata\SICD_METADATA.xml `
  --cphd-json umbra/Vandenberg\metadata\CPHD_METADATA.json `
  --duration 6 --mode tiled --overlap 0 `
  --window tukey --tukey-alpha 0.25 --normalization energy `
  --output umbra/Vandenberg\metadata\SUBAPERTURE_PLAN_6S.json
```

This command reads metadata only and does not require the full NITF.


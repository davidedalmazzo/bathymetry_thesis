# Code audit

Audit date: 2026-08-29. The three supplied files were read in full. None was
modified. Replacement scientific code belongs under `code/`.

## Executive finding

`sicd_subaperture.py` is a useful prototype, but it is not suitable for a thesis
result in its current form. The actual SICD confirms `axis=1` for azimuth, yet the
script uses the wrong image-to-spectrum FFT direction for this file, crops the
azimuth dimension before the FFT, assumes metadata support is centered in the
generic case, does not normalize or characterize windows, and lacks most of the
required tests. The supplied 20 s sweep cannot run on the public SICD because its
processed aperture is only 18.068061721 s.

## `download_vandenberg_sicd.bat`

### Function, inputs, and outputs

- Downloads one fixed SICD and then one fixed STAC JSON using `curl.exe`.
- Input is a hardcoded public S3 prefix for Umbra task
  `f2f8c71e-6aec-4358-acda-93c5e68e8b4b`.
- Outputs are fixed under `D:\Dati Tesi\Umbra\Vandenberg`:
  `2025-02-16-18-55-44_UMBRA-10_SICD.nitf` and the corresponding public STAC
  JSON.
- Resume uses `curl -C -`.

### Verified facts

- The public S3 listing contains exactly that SICD key.
- HTTP status is 200, range requests are supported, and Content-Length is
  11,478,596,733 bytes.
- The public STAC property `umbra:collect_id` is
  `9d8283d8-550d-4435-899f-5483d2c1abcc`, identical to the local CPHD.
- The STAC asset map retains an internal production name
  `2025-02-16-18-55-33_UMBRA-10_SICD_MM.nitf`; the public bucket renames it to
  the `18-55-44 ... SICD.nitf` key. The `.bat` happens to use the correct public
  key but does not explain the discrepancy.

### Problems and proposed replacement behavior

- No `--fail` is passed to curl. An HTTP error document can therefore be saved
  while curl exits successfully. Add `--fail` (or `--fail-with-body`).
- No HEAD/preflight check, expected Content-Length, free-space check, final-size
  validation, collect UUID validation, or checksum/ETag record is performed.
- A pre-existing wrong or oversized local file is not validated before resume.
- STAC is fetched only after the 11.48 GB transfer, although it should be used
  for preflight identity checks.
- Failures of the STAC download do not cause a nonzero final exit.
- The script should set workspace-local TEMP/TMP, log commands and response
  metadata, and leave an explicit `.part` file until validation succeeds.

There are no FFT axes or angle conventions in this script. Its only dependency
is `curl.exe`. Peak memory is negligible; disk demand is 11.48 GB plus any
partial file.

## `README_Vandenberg_SICD.md`

### Function

The README describes download, package installation, metadata inspection, a 6 s
sub-aperture example, and a proposed dwell sweep.

### Correct statements

- Complex `.npy` data, not PNG quicklooks, must be used downstream.
- Timing inferred from a linear bandwidth fraction is only approximate and must
  ultimately be tied to CPHD/PVP geometry.
- For the actual `RGAZIM` SICD, Row is range and Col is Doppler/azimuth, so the
  split axis is NumPy axis 1.

### Incorrect or unsafe statements

- `python -m pip install ...` is presented without a venv and conflicts with the
  workspace isolation requirement.
- The recommended 1 km x 1 km ROI is cut in both axes before the azimuth FFT.
  This is exactly the spectral-convolution problem identified in the task.
- The README reasons from a ~22.6 s full aperture. Actual ImageFormation uses
  only 18.068061721 s. A requested 20 s reduced aperture is impossible from this
  SICD and the supplied script will reject it.
- “1 km” is measured along SICD slant-plane Row/Col sample coordinates; it is not
  automatically a 1 km ground-projected square.
- The expected “three non-overlapping 6 s looks” remains numerically possible,
  but their nominal time mapping must use the 18.068 s processed interval, not
  the 22.54 s CPHD dwell.

The README has no quantitative memory estimate, no ENBW/window normalization,
no coregistration/control-land step, and no cross-spectrum definition.

## `sicd_subaperture.py`

### Function, input, and output

- Opens a complex SICD with SarPy.
- `--inspect` prints a subset of metadata.
- `--self-test` performs a round-trip and rectangular split/recombine test.
- Processing reads one rectangular chip, transforms along one selected axis,
  filters centered or tiled bands, forms complex sub-looks, and writes `.npy`,
  PNG, CSV, and JSON outputs.

Dependencies are NumPy, Matplotlib, and SarPy.

### Axes and angular conventions

- `infer_axis()` maps actual `Grid.Type=RGAZIM` to axis 1. This is correct for
  this product: array axis 0 is SICD Row/range and axis 1 is Col/azimuth.
- For any other grid type the script refuses to guess unless `--axis` is given;
  this is a sound guard, although a forced value is not itself a geometry check.
- Printed SCPCOA angles are passed through in degrees without documenting their
  north/clockwise or line-of-sight convention. No pixel-to-geographic mapping is
  performed.

### Confirmed FFT error

`to_spectrum()` uses `fftshift(ifft(image))`, while `from_spectrum()` uses the
opposite `fft`. The pair round-trips, so the self-test cannot detect the physical
sign error. For the actual metadata `Grid.Col.Sgn=-1`; SarPy's
`fft_sicd(image, 1, sicd)` therefore uses `numpy.fft.fft(axis=1)` for the forward
image-to-spectrum transform and `ifft_sicd` for the inverse. The current code
reverses the physical band-location/sign convention relative to the SICD.

This matters for sub-look order, nominal time ordering, and cross-spectral phase
sign. It must be fixed and covered by a known-frequency band-location test.

### Spectral-support assumptions

- `support_bins()` estimates only a width and always centers it in the shifted
  FFT. This is unsafe when `DeltaKCOAPoly` is nonzero or spatially varying.
- It happens to be valid for this SICD because Col DeltaK1/2 are symmetric and
  Col.DeltaKCOAPoly is exactly zero. The Col support fraction is 0.8, i.e. about
  86,240 of 107,800 bins.
- Native Row/Col weighting is declared `SVA`, but WgtFunct samples are absent.
  Exact deweighting is not possible from the supplied metadata.

### ROI and memory defects

- The code reads a small azimuth ROI before its FFT. This multiplies the image by
  a spatial rectangle and convolves the Doppler spectrum. There is no guard
  region comparison or stability test.
- The default “1 km” chip is approximately 5,953 x 17,721 samples for the actual
  Row/Col spacings, about 105.5 million complex samples. Each complex64 file is
  about 0.84 GB. Full ROI plus three sub-looks is already about 3.4 GB before
  PNGs and temporary arrays.
- NumPy FFT promotes the complex64 input, and `spec`, `zeros_like(spec)`, and the
  reconstructed output coexist. Peak RAM can be several gigabytes for the
  nominally “small” example.
- Range chunking is not implemented. A correct design should retain the full or
  stability-tested azimuth span while processing limited Row/range chunks.
- `--roi-rows` and `--roi-cols` are effectively unreachable because
  `--roi-size-m` defaults to 1000 and has no CLI representation for `None`.

### Dwell and sub-look definition defects

- `infer_full_dwell()` correctly prefers TEndProc-TStartProc, which is
  18.068061721 s here. This conflicts with comments/README that imply ~22.6 s.
- The proposed `20,16,12,10,8,6,5` sweep fails at 20 s.
- Only one centered window or a fixed non-overlapping tiled set is supported.
  Arbitrary centers, overlap, and explicit look pairs are absent.
- Bandwidth fraction = dwell/full dwell is labeled approximate, which is good,
  but the CSV time is still a purely linear interpolation with no uncertainty or
  CPHD mapping identifier.

### Windowing and normalization defects

- Only rectangular and Hann windows exist; Tukey/raised-cosine is absent.
- There is no coherent-gain, energy, or ENBW normalization and no recorded ENBW.
- No resolution/ringing metric is produced.
- Output records omit per-look window, effective bandwidth, FFT sign, original
  SICD core/collect ID, and explicit processed-time bounds.

### Tests and downstream science

- The existing self-test covers only numerical round-trip and rectangular
  recombination along axis 1.
- It does not test axis discrimination, physical FFT sign/band location,
  cross-spectrum phase sign, window normalization, metadata guards, or chunk
  equivalence.
- No coherence, intensity cross-spectrum, registration, phase-ramp estimation,
  land control, reproducible ROI file, or uncertainty calculation exists.
- PNGs display magnitude, not intensity (`|z|^2`), despite some surrounding text
  calling them intensity images.

### Required replacement

Keep the supplied file unchanged. Build a tested module under `code/` that:

1. uses metadata-aware forward/inverse FFT conventions;
2. keeps the full/stability-tested azimuth span and chunks Row/range;
3. supports explicit window width, center, and overlap;
4. records coherent gain, energy gain, ENBW, native weighting caveats, and exact
   metadata provenance;
5. implements all five required synthetic test classes before real data;
6. uses only nominal timing until CPHD PVP geometry supplies a validated mapping.


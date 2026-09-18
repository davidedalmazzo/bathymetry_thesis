# Checkpoint 2 — metadata-aware library and synthetic validation

Date: 2026-08-29. No full SICD download and no real ocean-pixel processing were
performed in this block.

## Deliverables

- Core transforms, metadata guards, support/band planning and windows:
  `code/umbra_sar/subaperture.py`.
- Explicit cross-spectrum convention: `code/umbra_sar/cross_spectrum.py`.
- Method/API documentation: `code/README_SUBAPERTURE.md`.
- Metadata-only planner: `code/plan_subapertures.py`.
- Five synthetic test groups: `tests/test_subaperture.py`.
- Numerical metrics: `tests/TEST_METRICS.json`.
- Full test report: `tests/TEST_REPORT.md`.
- Metadata-only 6 s plan:
  `Vandenberg/metadata/SUBAPERTURE_PLAN_6S.json`.

## Final test status

Command:

```powershell
& 'D:\Dati Tesi\Umbra\.venv\Scripts\python.exe' -B -m pytest -vv
```

Result: **19 passed in 6.71 s**. All independent metric checks also pass.

## Five required groups

### 1. FFT/IFFT

- Tested numerical round trips for both axes and `Sgn=-1/+1`.
- Maximum relative error: `2.821737e-16`.
- With actual `Col.Sgn=-1`, a +29-bin tone peaks at shifted bin 157 when FFT is
  used. Deliberately using IFFT moves it to bin 99, reversing Doppler sign.
- Library output equals explicit FFT and SarPy `fft_sicd` numerically (reported
  relative error 0 at tested precision).

### 2. Split/recombine and windows

- Four disjoint rectangular bands exactly cover the occupied synthetic support.
- Sum of complex sub-looks reconstructs the source image with relative error
  `2.636336e-16`.
- Rectangular and Tukey windows are implemented with `none`, `energy`, and
  `coherent` normalization modes.
- Energy normalization enforces `sum(|w|^2)=N`; ENBW and gains are recorded.
- For Tukey alpha 0.25 and N=1024, ENBW is `1.1031180797` bins and RMS gain is 1.
- Missing native SVA WgtFunct is recorded as a warning and does not block tests.

### 3. Axis

- Actual XML resolves Row/range to axis 0 and Col/azimuth to axis 1.
- A modulation only along columns peaks at the expected Col bin.
- The wrong negative half-band retains only `4.805386e-15` of the norm (numerical
  leakage); the correct positive band retains 1.
- A non-RGAZIM grid is rejected rather than guessed.

### 4. Band location and durations

- Known -47 and +47 tones are recovered at shifted indices 81 and 175, with
  correct negative/positive ordering.
- Real support is `10780:97020`, 86,240 bins.
- SICD processed aperture duration is kept as `18.068061721230308 s`.
- CPHD slow-time dwell is separately kept as `22.540812513364376 s`.
- A 20 s SICD band request is rejected even though CPHD has >20 s available.
- Requested 6 s fraction is `0.332077678977`; integer quantization gives 28,638
  bins and `5.999920588736 s` realized nominal duration.
- Three non-overlapping nominal centers are 3.039271807054, 9.039192395790 and
  15.039112984526 s from CollectionStart. These remain approximate labels.

### 5. Cross-spectrum phase sign

The implemented definition is:

```text
C_secondary,reference(k) = F_secondary(k) * conj(F_reference(k))
```

- Imposed `+0.63 rad` on the secondary positive-frequency intensity component:
  recovered `+0.63 rad`, wrapped error `8.88e-16 rad`.
- The conjugate negative-frequency peak recovers `-0.63 rad`.
- Swapping operand order recovers `-0.63 rad`.
- End-to-end `Col.Sgn=-1` test constructs one synthetic focused complex image,
  performs the correct FFT, separates negative- and positive-Doppler looks,
  forms their intensity images, and computes the cross-spectrum. Imposed phase
  `+0.71 rad`; recovered `+0.71 rad`; wrapped error `0` at reported precision.
- The deliberately wrong forward IFFT produces a different, sign-reversed set
  of spectral peak indices.

Thus FFT versus IFFT, Doppler band ordering, cross-spectrum operand ordering and
phase sign are verified numerically together.

## Metadata-only 6 s plan

The planner produced three Tukey-alpha-0.25, energy-normalized bands:

| Look | Half-open bins | Nominal center from CollectionStart (s) | ENBW (bins) |
|---:|---:|---:|---:|
| 1 | 10943:39581 | 3.039271807054 | 1.10207929944 |
| 2 | 39581:68219 | 9.039192395790 | 1.10207929944 |
| 3 | 68219:96857 | 15.039112984526 | 1.10207929944 |

The remaining 163 bins on each side are the centered residual caused by fitting
three integer-width bands inside the 86,240-bin processed support.

## Limits and stop condition

- The tests use synthetic arrays and local metadata XML only.
- The full SICD NITF is still absent.
- No claim is yet made that complex-image or intensity-image cross-spectrum is
  the definitive real ocean-wave retrieval; primary-source verification remains
  required.
- No real coherence, registration, land control, ocean spectrum, wave period,
  dispersion, or bathymetry was computed.

Block 2 is complete. Block 3 has not started.


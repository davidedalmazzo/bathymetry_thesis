# Synthetic test report — block 2

Generated: `2026-08-29T14:06:22.716464+00:00`

## Scope and result

- Final pytest result: **19 passed**.
- Inputs: synthetic numerical arrays plus the already-extracted local SICD XML for metadata conventions. No SICD image pixels were read and the full SICD remains undownloaded.
- Independent metric checks: `True`; details in `TEST_METRICS.json`.
- No ocean-wave interpretation is made in this report.

During development, the first run passed 17/18 tests. The sole failure was a manually entered expectation that ignored bin quantization of the nominal 6 s windows. The test was corrected to derive centers from the realized 28,638-bin width; the algorithm was unchanged.

## 1. FFT/IFFT round trip and Col.Sgn=-1

- Maximum relative round-trip error over Sgn ±1 and axes 0/1: `2.821737e-16`.
- For a +29 bin tone in N=256, `Col.Sgn=-1` with FFT peaks at shifted index `157` (expected `157`).
- Substituting IFFT moves the peak to `99`, reversing the Doppler sign; relative difference from the correct spectrum is `2.560020e+02`.
- Library versus explicit FFT relative error: `0.000000e+00`.
- Library versus SarPy `fft_sicd` with the actual XML: `0.000000e+00`.

Conclusion: for this SICD, image→Doppler is numerically confirmed as FFT and spectrum→image as IFFT; this is not merely inferred from metadata text.

## 2. Rectangular split/recombine and windows

- Four disjoint rectangular bands cover the complete synthetic support. Sum-of-sublooks relative reconstruction error: `2.636336e-16`.
- Rectangular ENBW: `1` bin; normalized energy sum: `1024` for N=1024.
- Tukey α=0.25 ENBW: `1.1031180797` bins; energy normalization gives RMS gain `1`.
- Native weighting is recorded as `SVA` with WgtFunct present=`False`. This warning does not block synthetic filtering.

Energy normalization means `sum(|w|²)=N`, matching a rectangular window's total window energy. ENBW is also recorded and is invariant to this scale.

## 3. Axis test

- Metadata resolution: `RGAZIM`, range axis `0`, azimuth axis `1`, Col.Sgn `-1`.
- A tone modulated only along columns peaks at `169` (expected `169`).
- Negative-band rejected-energy ratio for the positive tone: `4.805386e-15`; positive-band retained ratio: `1.000000e+00`.
- A non-RGAZIM grid is explicitly rejected rather than guessed.

## 4. Band location and duration separation

- Known tones at -47 and +47 bins are recovered at shifted indices `81` and `175`, in the negative and positive bands respectively.
- Actual SICD processed support: `86240` bins (`10780:97020`).
- SICD processed aperture duration: `18.068061721230` s.
- CPHD slow-time dwell: `22.540812513364` s. It is stored separately and never used as the SICD fraction denominator.
- Requested nominal 6 s fraction: `0.332077678977`; realized width `28638` bins, corresponding to `5.999920588736` s after quantization.
- Three non-overlapping nominal centers: `3.039271807054, 9.039192395790, 15.039112984526` s from CollectionStart.
- A 20 s SICD request is rejected: `True`. Message: `nominal SICD duration 20 s exceeds processed aperture duration 18.0680617212 s; CPHD dwell cannot be substituted`.

## 5. Cross-spectrum phase sign

Convention: `C_secondary,reference(k) = F_secondary(k) * conj(F_reference(k)); a +phi Fourier phase advance in secondary is recovered as +phi at the positive-frequency peak`

- Real/intensity wave imposed phase: `0.630000000000` rad; recovered positive-peak phase: `0.630000000000` rad; wrapped error `8.881784e-16` rad.
- Negative-frequency conjugate peak is recovered with the opposite phase; wrapped error `8.881784e-16` rad.
- Swapping reference and secondary reverses the phase; wrapped error `9.992007e-16` rad.
- End-to-end `Col.Sgn=-1` case: a full synthetic focused image is transformed, split into a negative-Doppler low look and positive-Doppler high look, converted to intensities, and cross-correlated. Imposed phase `0.710000000000` rad, recovered `0.710000000000` rad, wrapped error `0.000000e+00` rad.
- Correct FFT peak indices: `[76, 83, 159, 166]`; deliberately wrong IFFT indices: `[90, 97, 173, 180]`.

Conclusion: FFT/IFFT choice, negative-to-positive Doppler ordering, cross-spectrum operand order, and phase sign are all numerically constrained by independent synthetic signals.

## Scientific limits of this block

- These tests establish numerical and metadata conventions only.
- The end-to-end ocean-style test uses sub-look **intensity** images, but this does not yet settle the literature choice for the final real-data retrieval; that decision still requires primary-source verification.
- Linear bandwidth→time labels remain nominal. Exact centers require later CPHD/PVP mapping.
- Missing SVA WgtFunct prevents exact native deweighting but does not invalidate the transform/sign tests.
- No real ocean pixels, coherence, bathymetric inversion, or scientific interpretation were processed.

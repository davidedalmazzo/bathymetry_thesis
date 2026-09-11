# Synthetic regression report — Block 3

Generated: `2026-08-29`

## Result

- Command: `D:\Dati Tesi\Umbra\.venv\Scripts\python.exe -m pytest -q`
- Result: **21 passed in 2.20 s**.
- The suite uses synthetic arrays and local metadata. Its convention tests are independent of the real ocean spectral results.

## Five required convention groups (retained from Block 2)

1. **FFT/IFFT and `Col.Sgn=-1`.** A positive synthetic image-domain tone lands in the positive shifted-Doppler bin with `fft`; deliberately substituting `ifft` mirrors it to the negative bin. FFT→IFFT reconstruction is accurate to numerical precision and matches SarPy with the real SICD XML.
2. **Rectangular recombination and tapered windows.** Disjoint bands reconstruct the source at numerical precision; rectangular and Tukey ENBW and energy normalization are checked numerically. Native SICD weighting remains documented as `SVA` without sampled `WgtFunct` and is nonblocking.
3. **Axis selection.** Column-only modulation is recovered on the RGAZIM azimuth axis, the opposite Doppler band rejects it numerically, and unsupported grid types are rejected explicitly.
4. **Band location and duration separation.** Positive/negative tones are assigned to the correct bands. The `18.068061721230308 s` SICD processed aperture and `22.540812513364376 s` CPHD available slow time remain distinct, and CPHD dwell cannot be substituted as the SICD fraction denominator.
5. **Cross-spectrum sign.** With `F_secondary * conj(F_reference)`, positive imposed phase is recovered as positive at the positive-frequency peak; the conjugate peak and reversed operands change sign. The end-to-end `Col.Sgn=-1` sub-look intensity test also distinguishes the correct FFT band order from the deliberately wrong IFFT order.

Full numerical metrics for these five groups remain in [TEST_REPORT.md](TEST_REPORT.md) and `TEST_METRICS.json`.

## Block-3 additions

- A synthetic 2-D modulation is converted through the local ground Jacobian; wavelength and EN wavevector bearing are recovered, and identical candidates pass three-look stability matching.
- A known signed two-axis image shift is recovered using `F_secondary * conj(F_reference)`. The expected phase-ramp sign, sub-pixel displacement, ramp removal, and wrapped phase operation are checked numerically.

## Scientific boundary

Passing these tests establishes transform, axis, ordering, phase-sign, physical-frequency-coordinate, and registration conventions. It does not by itself validate an ocean-wave period, a dwell sweep, or bathymetric inversion.

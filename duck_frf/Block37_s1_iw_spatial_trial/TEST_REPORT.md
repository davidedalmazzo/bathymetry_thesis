# Block37 test report

- Focused Block37 suite: **10 passed**; one expected synthetic GeoTIFF
  not-georeferenced warning.
- Authoritative complete suite: **370 passed in 40.39 s**, zero failures or
  skips; the same synthetic warning was emitted.
- Interpreter: `.venv-umbra-thesis/Scripts/python.exe`.
- Frozen Block34 baseline: **810 verified, zero mismatches**.

Coverage includes interrupted resume, refusal of non-ZIP bodies, frozen product
identity, safe ZIP traversal/inventory, complex I/Q window reads, calibration
power convention, FRF-to-geographic coordinates, exact valid support, FFT axes,
discrete conjugate pairing including the even-length Nyquist bin, a known 2-D
sinusoid, and absence of bathymetry/expected-wave inputs from SAR peak selection.
The real run additionally checked TIFF/annotation dimensions, complex sample
semantics, bounded source windows, LUT identity, and exact burst support.

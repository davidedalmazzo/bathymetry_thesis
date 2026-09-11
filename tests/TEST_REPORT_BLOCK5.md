# Synthetic and artifact regression report - Block 5

Generated: `2026-08-31`

- Command: `D:\Dati Tesi\Umbra\.venv\Scripts\python.exe -B -m pytest`
- Result: **31 passed**.
- The 19 Block-2 transform tests remain active, including numerical `fft`/`ifft`, Doppler ordering, `Col.Sgn=-1`, cross-spectrum phase sign, RGAZIM axis and strict separation of the 18.068061721-s processed aperture from the 22.540812513-s CPHD dwell.
- The three Block-3/4 wave-analysis tests remain active: geographic wavenumber conversion, registration/phase-ramp sign, and fixed-patch temporal phase recovery.
- Five new physical-identification tests verify finite-depth dispersion, OSW Eq. (34) forward/reverse sign, the analytic `S(k)/S(-k)` zero-lag slope, NDBC directional-distribution normalization, frequency bins and direction conventions.
- Four new artifact audits verify the frozen SAR hash and period, all five complete NDBC variables and requested bins, the 24 SAR-only sensitivity variants and no-dwell-sweep guardrail, and the diagnostic-only status of the dispersion depths.

These tests validate numerical conventions, artifacts and guardrails. They do not by themselves prove the physical component assignment; that conclusion follows from the documented spectral evidence and remains subject to future independent validation.

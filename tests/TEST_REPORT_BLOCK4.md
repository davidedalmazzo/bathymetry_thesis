# Synthetic regression report — Block 4

Generated: `2026-08-30`

- Command: `D:\Dati Tesi\Umbra\.venv\Scripts\python.exe -m pytest -q`
- Result: **22 passed**.
- All five Block-2 convention groups remain active: FFT/IFFT for `Col.Sgn=-1`, split/recombine and windows, RGAZIM axis, duration separation, and signed cross-spectrum ordering.
- Block-3 physical-frequency and signed phase-correlation tests remain active.
- The new Block-4 test constructs a fixed complex spectral patch with a known negative temporal phase rate, wraps it across ±π, and verifies numerically:
  - `F_secondary * conj(F_reference)` phase sign;
  - temporal unwrapping from small adjacent baselines;
  - recovery of `ω_p` to numerical precision;
  - unit adjacent coherence;
  - linear-regression residuals at numerical precision.

These tests validate numerical conventions and regression plumbing. They do not establish that the measured nearshore `T_SAR` is the physical ocean-wave peak period.

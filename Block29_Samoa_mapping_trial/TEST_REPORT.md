# Block29 — complete thesis-environment test suite

Executed after the final mapping/chronology changes on 2026-09-16:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe -m pytest -q
```

**242 passed in 13.68 s; zero failures or skips.**

Ten new Block29 tests cover structured big-endian PVP offsets and integer
fields, truncation rejection, complete time continuity, PFA angle/scale
consistency, radial dependence of a Col-band temporal kernel, full Jacobian
inverse-transpose phase invariance, cross-spectrum sign/conjugate intensity
lobe, frozen gate/no-download state, range/budget and original input hashes,
explicit image-domain mask diagnostics, ignored-range rejection before body
reading, and actual PFA reverse chronology of increasing Col bands.
Existing SarPy, FFT/IFFT and sub-aperture convention tests were re-executed.

The first focused run exposed a test expectation including image DC while
the existing cross-spectrum library subtracts the mean by default. The test
reference was corrected to the documented existing interface; no frozen
library was changed. The final full suite above includes that correction.

This suite is not a real SAR phase-history validation and does not override
the CONDITIONAL phase-A gate. No complete SICD or CPHD signal was read.

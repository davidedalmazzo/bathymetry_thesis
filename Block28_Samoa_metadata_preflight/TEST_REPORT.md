# Samoa preflight — test verification

Project-local thesis interpreter; focused suite executed 2026-09-16:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe -m pytest -q tests/test_block28_samoa_preflight.py tests/test_subaperture.py
```

26 passed, no failures or skips. Seven new Samoa tests plus 19 existing
sub-aperture/convention tests (including SarPy-dependent checks).

Coverage: metadata identity and distinct durations; exact NITF segment parsing;
no SICD image/CPHD signal range overlap; ignored-range rejection before body
read; surface coordinate push-forward versus horizontal Grid projection;
ROI boundary sampling convergence/HAE sensitivity; nominal plans within
processed support; numerical FFT sign on the actual Samoa metadata;
budget counters and original input hashes.

The first test run exposed a test-call signature mismatch for the existing
keyword-only transform interface. The test invocation was corrected; no frozen
library implementation was changed. No real SAR formation/frequency test.

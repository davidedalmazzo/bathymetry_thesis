# CHECKPOINT_32 — Duck/FRF reusable observation client

Implemented mission-neutral library, CLI and example configuration for strict
single/multi acquisitions and inventory/fetch/offline workflows. Preserves
original values/masks/QC, signed previous/next/nearest temporal associations,
historical nominal-coordinate uncertainty and WGS84 footprint/ROI distances.
No radar data accessed, frequency/depth SAR estimation, selection, commit/push.

Verified October 2021 Waverider/AWAC spectra (62×72), moments/flags, wind,
AWAC profiles and NOAA preliminary level; June cached bulk and AWAC profiles.
TDX original record 11 retains 2021-10-13T23:00:15.669Z catalogue semantics,
not aperture center. Two June Waverider references remain stale/context only;
contemporaneous AWAC values are never populated from the obsolete buoy.

The separate tranche is exhausted: **40 HTTP /2,412,291 bytes**, including
1,048,576 bytes of the incomplete June AWAC spectral stream. June spectra/QC,
wind/level and detailed survey metadata/coverage remain conditional/incomplete.
No further HTTP or automatic continuation. Historical cumulative consumption
non determinabile, not zero. Verified payloads and resume state preserved.

**269 tests passed** (24 new offline tests); 163 frozen files unchanged,
Block4 golden SHA256 unchanged. Delivery/source/payload hash checks saved;
caches excluded from Git, no file ≥100 MiB.

[Full report](Block32_frf_client/REPORT.md),
[usage and limits](code/README_FRF_CLIENT.md),
[real endpoint evidence](Block32_frf_client/REAL_ENDPOINT_REPORT.json),
[test report](Block32_frf_client/TEST_REPORT.md),
[manifest](Block32_frf_client/DELIVERY_MANIFEST.json).

Stop: client plus bounded verification complete; remote evidence explicitly
partial. No definitive choice or scientific SAR interpretation initiated.

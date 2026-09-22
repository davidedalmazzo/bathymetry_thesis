# CHECKPOINT_36 — Duck Sentinel-1 IW annotation preflight

Decision: **READY** for the first spatial-intensity technical trial. This is not
wave, phase-to-frequency or bathymetry validation.

The fixed Block35 October 28 product and ROI were not changed. Authenticated
manifest and VV IW1/IW2/IW3 annotations pass identity, orbit, interval and exact
manifest-reference checks. Matching IW3 calibration/noise XML are retained.
No measurement TIFF, full SAFE/ZIP or SAR pixel was read.

The primary 550×300 m ROI is wholly inside exact valid-sample support of
**IW3 burst 0**: valid fraction 1.0, one burst, no seam/overlap crossing and no
stitching required. Burst azimuth time is 2021-10-28 23:06:37.287243 UTC;
sensing time is 23:06:38.401751 UTC. IW1/IW2 do not contain the ROI in their
geolocation support.

At ROI center, local range/azimuth bearings are **80.571242°/350.453641°**;
incidence is **44.163763°** with ROI-boundary range 44.148162–44.179404°.
Ground sampling from the geolocation Jacobian is 3.345897 m/sample and
12.366025 m/line; effective resolution is not equated to spacing. Wavenumber
uses `k_EN=J^-T q_image`. Measured WR17/AWAC propagation differs axially from
local range by 14.22966°/14.16288° and is not imposed on SAR processing.

Authentication succeeded without MFA; secrets and token responses were not
logged. The persistent tranche used **12/40 transactions** and
**3,819,945/52,428,800 bytes**, including one retained sandbox transport
failure. Focused tests: **17 passed**; full suite: **360 passed**; frozen audit:
**810/810 hashes unchanged**. Full-product download remains **NOT EXECUTED**.

See [full report](../../duck_frf/Block36_s1_iw_annotation_preflight/REPORT.md),
[support and geometry](../../duck_frf/Block36_s1_iw_annotation_preflight/ROI_BURST_SUPPORT.geojson),
and [prepared download status](../../duck_frf/Block36_s1_iw_annotation_preflight/DOWNLOAD_NOT_EXECUTED.md).

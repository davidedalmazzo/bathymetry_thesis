# CHECKPOINT_35 — Duck Sentinel-1 IW spatial selection

Decision: conditional first technical IW SLC download, not a methodology or
phase-to-frequency validation. No download/formation/inversion was executed.

First product: `S1A_IW_SLC__1SDV_20211028T230636_20211028T230703_040326_04C765_B6FA.SAFE`,
UUID `c49a9c1f-9b00-5676-ab05-683975d898a2`, 7,799,368,890 vendor catalogue bytes.
Alternative: October 11, UUID `d982f98d-9739-5a03-aa42-27407da87d7e`.

See [full evidence and conditions](../../duck_frf/Block35_s1_spatial_selection/REPORT.md),
[complete comparison](../../duck_frf/Block35_s1_spatial_selection/ALL_CANDIDATES.csv)
and [prepared, not executed download](../../duck_frf/Block35_s1_spatial_selection/DOWNLOAD_NOT_EXECUTED.md).

Actual primary CDSE query returned all 8 October products/five physical passes.
FRF scalar/QC context for all products; spectral/native masks for five passes.
Survey support is actual points, not bounding boxes or first-N selection.
Frozen 810 hashes unchanged; new persistent tranche only, 73 charged attempts
including one reserved conservative charge, 7,041,606 bytes. Historical budget
not reconstructed or asserted respected. No Git commit/push in this task.

Decisive pending condition: authenticated manifest and VV IW1/IW2/IW3 XML to
verify ROI valid burst support/seams, local projected range/incidence/resolution.
No access token configured; XML 401 retained, no bypass. No automatic next step.

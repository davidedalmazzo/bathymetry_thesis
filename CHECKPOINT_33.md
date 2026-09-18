# CHECKPOINT_33 — FRF offline correction

Reported defects reproduced and corrected: metadata-only inventory for new
products, calendar-aware cross-file association, bounded separate event windows,
missing/zero spectral semantics, selected-sample geography/deployment validity,
truncated-response completeness and clone-shaped offline reproducibility.

310 ordinary tests passed; 68 isolated client/parser tests passed. Four cached
regression dossiers retain all 604 compared observation rows and spectral/context
distance values. 438 Block32 artifact/cache files and 163 historical inputs
retain hashes; corrected historical source references are audited separately.

**Zero actual HTTP, no radar processing/download, inversion, commit or push.**
Frozen Block32 configs/dossiers/manifests and exhausted budget remain unchanged.
Ready locally for new dates with explicit coverage/layout/QC limits; no live
certification or claim that pending files are already on GitHub.

[Report](Block33_frf_offline_correction/REPORT.md),
[defects](Block33_frf_offline_correction/DEFECT_REPORT.md),
[regressions](Block33_frf_offline_correction/REGRESSION_REPORT.md),
[tests](Block33_frf_offline_correction/TEST_REPORT.md),
[client documentation](code/README_FRF_CLIENT.md),
[manifest](Block33_frf_offline_correction/MANIFEST.json).

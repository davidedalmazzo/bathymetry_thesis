# Block 4 — fixed-width sliding-look phase

Run from `D:\Dati Tesi\Umbra` with the workspace virtual environment:

1. `python -B code/reconcile_range_axis.py`
2. `python -B code/plan_block4_sliding_looks.py`
3. `python -B code/form_block4_sliding_looks.py`
4. `python -B code/analyze_block4_phase_timeseries.py`
5. Only after step 4 is frozen, download the official NDBC station 46218 annual standard-meteorology NetCDF under `Vandenberg/external` and run `python -B code/compare_block4_external_ndbc.py`.
6. `python -B code/generate_checkpoint4_report.py`
7. `python -m pytest -q`

The formation stage processes only `nearshore` and `land_control`. For every selected range row it FFTs all 107,800 SICD azimuth columns and crops ROI columns only after IFFT. Eight new overlapping arrays are generated per ROI; chronological looks 1, 6, and 11 reuse the exact three disjoint Block-3 arrays, which remain stored separately.

The primary phase is a Gaussian-weighted 5×5 locally smoothed cross-spectrum around one fixed Block-3 nearshore peak bin. Peak drift is diagnostic only and never retunes the phase patch. Time centers come from the CPHD/PVP Doppler inversion. The SAR-only result is saved before any external observation is read.

Guardrails: fixed ~6 s width only; no dwell sweep, no bathymetric inversion, and no buoy/hindcast-assisted unwrap branch.

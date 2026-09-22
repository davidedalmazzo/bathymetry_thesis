# Sentinel-1 IW SLC geolocation: interpolate in burst azimuth time, not line number

Found 2026-09-21 while building `s1_transect_bathy.py`.

The annotation geolocation grid has rows at burst starts (lines 0, 1508, …) stamped
with the burst azimuth time. Bursts overlap: a burst spans 1508 × 2.0556 ms = 3.100 s
but grid rows are 2.757 s apart. `s1_iw_annotation.GeoGrid` (Blocks 36–37)
interpolates in *line number*, compressing time by ~12 %.

Independent check at Duck (IW3, 2021-10-28): survey z≈0 NAVD88 points (n=226)
versus the SAR land/sea edge along range (coast ~11° from azimuth):

| model | median offset (samples) | IQR | best-aligning line shift |
|---|---|---|---|
| line-number (Blocks 36/37) | 73.9 | 9.7 | −105 lines |
| burst azimuth time (`s1_iw_geometry.py`) | 0.8 | 3.4 | 0 |

Consequences for Block37 (frozen artifacts left untouched):
- the pixels read were ~105 lines (~1.4–1.5 km along azimuth, roughly alongshore
  north) away from the intended FRF ROI, outside the survey;
- the Jacobian line spacing was 12.37 m instead of ~13.90 m, biasing k and bearings;
- the λ≈77 m result, its FRF association and survey context are not valid as stated;
  the bilinear/nearest-neighbour discrepancy is superseded.

`s1_iw_geometry.SwathGeometry` maps (sample, line) → t = t_burst + (line − b·lpb)·Δt
and interpolates the grid (cubic) in (t, sample); inverse by Newton refinement; all
bursts imaging a point are returned. Tests: `tests/test_s1_transect_bathy.py`.

# `s1_transect_bathy.py` — Sentinel-1 IW SLC swell transects (scene-generic)

One script, no per-site configuration. Inputs: an unzipped SAFE, a lon/lat bbox,
a few parameters. Everything else is derived from the scene.

```
python code/s1_transect_bathy.py PRODUCT.SAFE --bbox LONMIN LATMIN LONMAX LATMAX \
       [--sea-side N|S|E|W] [--alongshore-average 4] [--period T ...] [--out DIR]
```

Pipeline
1. Multilooked σ0 (50 m) on a local UTM grid from every IW subswath/burst covering
   the bbox (burst overlaps averaged, burst-time geolocation, see below).
2. Instantaneous land/sea mask from the SAR (Otsu on dB + morphology). The open sea is
   the class component touching the bbox side `--sea-side`; `auto` takes the largest
   component (check `overview.png`). `--coast FILE` replaces the SAR mask with vector
   land polygons (e.g. TanDEM-X coastline GPKG) where the SAR split fails.
3. Coastline = sea-mask boundary, smoothed over `--smooth` m; transects = seaward
   normals every `--transect-spacing` m.
4. Windows (`--window` m square, native range/azimuth pixels) every `--step` m
   (paper: 50 m, heavy overlap) from `--offshore D0 D1` m; rejected if they leave a
   single valid burst, touch land/unmapped cells or contain bright targets.
5. Spectrum from native samples (exact separable DTFT under the local affine
   geolocation, NUDFT fallback) — no image resampling.
6. Peak: 20 contour levels, blobs above the top level, largest blob closest to the
   origin (Mudiyanselage et al. 2024). `--alongshore-average N` averages normalised
   spectra of N neighbouring transects each side first.
7. Moving mean along each transect; optional Eq. 5 depth for supplied `--period`
   (in-situ only), current sensitivity `--current`, Eq. 6 T_min check.

Outputs: `windows.csv`, `transects.geojson`, `sigma0_seamask_utm.tif`, `run.json`,
`overview.png`, `wavelength_profiles.png`, `example_spectra.png`,
`ensemble_spectra_by_distance.png` (spectra averaged in distance bands: SNR diagnostic).

Caveats
- Single-look periodograms are χ²(2): with `--alongshore-average 0` (paper-literal)
  the peak is often a speckle blob. At Duck N=0 gives median Spearman ρ(distance, λ)
  0.10 and p90 jump 90 % between 50 m steps; N=4 gives 0.34 and 19 %.
- Overlapping windows are not independent; the lobe/annulus ratio ≥ 3 is weak
  evidence for a χ² periodogram maximum.
- Period is never taken from charts or from the result (circular).

Site comparisons live in separate scripts (Duck: `duck_frf_compare.py`).

## Block39 audit fixes (2026-09-22)

- **Sea mask.** Morphology now runs on edge-replicated padding (`np.pad(..., mode="edge")`).
  The previous `border_value=1` made *both* classes touch every bbox border, so
  `--sea-side` degenerated to "largest component" and `edge_cells` in `run.json` was
  meaningless. The sea is now the class component with the longest contact with that
  side, a tie raises (pass `--coast`), and `sea_side_contact_fraction` is recorded.
- **Exact footprints.** Window corners come from the outer pixel edges
  (`s0-0.5 … s0+ns-0.5`), with the boundary densified every pixel and the sea test
  applied to it, instead of the 3× subsampled interior grid (`run.json`/`windows.csv`
  carry `footprint = "native pixel-edge corners"`). Window acceptance changed by
  +2…+3 % (SLC near 5200 → 5364 ok, GRD near 5670 → 5853).
- **Low-k cut.** The spectrum mask now excludes only DC; the cut is applied when the
  peak is picked, as `k >= kmin_factor * pi / window` (`--kmin-factor`, default 4, i.e.
  λ ≤ window/2). `peak_at_kmin_edge` flags peaks inside the first half-bin above it.
  `--parts-from DIR` finalises the same partial spectra with a different factor.
  Duck sweep (factor 2/3/4): median λ identical for 3 and 4, factor 2 keeps ~3 % fewer
  windows identifiable (low-k clutter blobs) — the cut is not driving the result, and
  ≤ 1 % of identified peaks sit at the edge.

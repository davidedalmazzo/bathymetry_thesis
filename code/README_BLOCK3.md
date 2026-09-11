# Block 3 — fixed three-look SICD analysis

This block intentionally stops before any 5–16 s dwell sweep and before any
bathymetric inversion.

## Guardrails

- The finalized SICD must be exactly `11,478,596,733` bytes and match multipart
  ETag `f06d503551fb567303477152aee18652-219`.
- The `18.068061721230308 s` SICD processed-aperture duration and the
  `22.540812513364376 s` CPHD available slow-time dwell remain separate.
- `Grid.Col.Sgn=-1` uses `fft` from image to Doppler and `ifft` back to image,
  as numerically verified in Block 2.
- Every processed SICD range row is transformed across all `107800` azimuth
  columns. ROI azimuth columns are cropped only after inverse transformation.
- Complex sub-look arrays are the master products. Intensity is derived as
  `abs(z)**2`.
- Cross-spectra use `F_secondary * conj(F_reference)` and no phase-to-period
  conversion is performed here.
- The scientific cross-spectrum is formed from sub-look **intensity** images,
  following the explicit SLC → three Doppler parts → inverse transform →
  sub-look intensity → image cross-spectrum sequence in Li et al. (2019), JGR
  Oceans, section 2.2.1, DOI `10.1029/2018JC014638`.
- SICD native weighting is `SVA` with no sampled `WgtFunct`; this is retained as
  a provenance warning and does not block the fixed-look experiment.

## Reproducible sequence

1. `download_verified_sicd.ps1` performs remote size/ETag preflight and leaves
   a resumable `.part` file.
2. `verify_s3_multipart_etag.py` scans the complete file in 50 MiB S3 parts,
   verifies the multipart ETag, and computes SHA-256.
3. `finalize_verified_sicd.ps1` moves the verified `.part` to its final name.
4. `verify_downloaded_sicd.py` validates the NITF file length, SICD semantics,
   stitched shape, image segments, and representative pixel reads.
5. `select_vandenberg_rois.py` records the GEC-to-lat/lon-to-SICD selection of
   nearshore, offshore, and land-control ROIs. The GEC is not used for wave
   metrics.
6. `cphd_doppler_time_mapping.py` derives the monotonic PVP geometry mapping
   from SICD Col spatial frequency to CPHD TxTime without reading CPHD signal.
7. `form_nominal_6s_sublooks.py` forms the three planned complex looks.
8. `analyze_block3_sublooks.py` produces intensity figures, physical 2-D power
   spectra, peak metrics and stability, conditional ocean cross-spectra and
   phase closure, plus land shift/phase-ramp controls.

The time mapping shows that `k_col` decreases with slow time: look 1 is late,
look 2 is central, and look 3 is early. This supersedes the direction of the
metadata-only nominal labels but does not alter their fixed FFT bands.

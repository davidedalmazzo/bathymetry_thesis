# CHECKPOINT_37 — Duck Sentinel-1 real spatial trial

The frozen October 28 Sentinel-1 SLC was downloaded and integrity-verified:
7,799,368,890 bytes, vendor MD5 matched, SHA-256
`0b302e9ace9b3b1714a4beb40c57c30fb6a7cc3c00e1b9711f1dae6ef7275050`.
The archive and extracted SAFE remain in Git-ignored Block37 data directories.

Bounded reads of the complex VV/IW3 TIFF place all three windows wholly in
valid burst-0 support.  The preregistered bilinear/Hann/plane estimator finds a
stable axial lobe: **k=0.08146–0.08200 rad/m, wavelength 76.63–77.14 m,
bearing 85.36–85.88°**, lobe/background 54.8–93.6.  Raw/LUT radiometry,
quadratic detrending and Tukey taper preserve it.  Nearest-neighbour resampling
instead selects 42–45 m/43–44°, a material sensitivity.  Noise-subtracted
power masks 12–13% and is correctly left unavailable rather than filled.

WR17 and AWAC complete spectra agree on one broad peak system.  The SAR axial
mismatch is 19.0–19.5°, within the frozen 25° criterion, so association is
classified **identifiable**.  Conditional U=0 depths are 4.535 m (WR17 peak)
and 5.477 m (AWAC peak); frequency-band/current sensitivities span roughly
3.72–6.57 m.  October 24 median bed elevation is about -6.3 to -6.5 m NAVD88,
but event water level is unverified, so this is not bathymetric validation.

Full suite: **370 passed**.  Frozen Block34 baseline: **810 verified, zero
mismatches**.  No commit or push was made.  See the
[full report](../../duck_frf/Block37_s1_iw_spatial_trial/REPORT.md).


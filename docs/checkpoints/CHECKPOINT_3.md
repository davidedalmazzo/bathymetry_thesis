# CHECKPOINT_3 — Vandenberg fixed three-look analysis

## Stop condition

Block 3 is complete. No 5–16 s dwell sweep, bathymetric inversion, or automatic cross-phase-to-period conversion was performed.

## SICD integrity

- Final file: `D:\Dati Tesi\Umbra\Vandenberg\2025-02-16-18-55-44_UMBRA-10_SICD.nitf`.
- Exact size: `11478596733` bytes; match: `True`.
- Multipart ETag: `f06d503551fb567303477152aee18652-219`; match: `True`.
- SHA-256: `56605c95701a5dd081c5faa7b1a39304a3907ed01f6eb576ea19ce4ea80e585d`.
- NITF file-length field matches EOF: `True`.
- SarPy stitched shape: `[[13310, 107800]]`; SICD XSD valid: `True`.
- SarPy recursive semantic flag: `False`; expected/nonblocking due to the documented negative downchirp sign check plus SVA-without-WgtFunct: `True`.

## Timing and Doppler order

- SICD processed aperture: `18.068061721230308` s.
- CPHD available PVP slow-time dwell: `22.540812513364376` s.
- These quantities remain distinct throughout the code and results.
- PVP geometry reproduces SICD `Row.KCtr` with absolute error `1.644e-11` cycles/m.
- CPHD PVP versus SICD ARP-polynomial `k_col` residual: RMS `4.449e-09` cycles/m.
- `k_col` decreases with TxTime. Therefore the fixed FFT order is look 1 = late, look 2 = central, look 3 = early.

| Look | Effective early–center–late PVP time (s) | Effective span (s) |
|---:|---|---:|
| 1 | 11.929 – 14.832 – 17.757 | 5.828 |
| 2 | 6.145 – 9.036 – 11.929 | 5.784 |
| 3 | 0.321 – 3.243 – 6.145 | 5.824 |

## Formation and ROI controls

- `Col.Sgn=-1`: image→Doppler `fft`, Doppler→image `ifft`.
- Every transformed row used all `107800` azimuth columns; pre-decomposition azimuth crop: `False`.
- Replaced nonfinite source samples: `0`.
- Native weighting: `SVA`, sampled WgtFunct present: `False`. This warning did not block processing.
- The GEC was used only to localize reproducible ROIs; every spectrum below comes from the complex SICD.

| ROI | Kind | SICD bounds (rows; cols) | Approx. ground size (m) |
|---|---|---|---|
| nearshore | ocean_nearshore | 9400:10600; 78000:87600 | 538.4 × 542.3 |
| offshore | ocean_offshore | 10900:12100; 71000:80600 | 536.9 × 542.5 |
| land_control | land_control | 6233:7769; 45512:57800 | 693.1 × 693.6 |

## 2-D intensity-spectrum peaks and stability

The peak direction is the modulation wavevector. The visible crest/stripe orientation is perpendicular to it, so a range-directed wavevector and azimuth-aligned stripes are compatible rather than contradictory.

| ROI | Robust | λ look 1 / 2 / 3 (m) | Mean λ (m) | Wavevector bearing (° mod 180) | Crest bearing (° mod 180) | Δ wavevector from range (°) | Δ crest from azimuth (°) |
|---|---|---|---:|---:|---:|---:|---:|
| nearshore | True | 137.1 / 125.5 / 129.2 | 130.6 | 79.8 | 169.8 | 21.3 | 21.6 |
| offshore | True | 50.4 / 44.5 / 41.5 | 45.5 | 115.8 | 25.8 | 14.6 | 14.3 |
| land_control | False | 295.1 / 281.9 / 285.9 | 287.6 | 174.3 | 84.3 | 73.1 | 72.4 |

### Resolution of the range/azimuth ambiguity

- **nearshore:** the robust spectral peak is oblique to both local range and azimuth axes; the preliminary binary description is too coarse (Δk from range `21.3°`, Δcrest from azimuth `21.6°`).
- **offshore:** the spectral wavevector is range-aligned while the visible crests are azimuth-aligned; the two descriptions refer to perpendicular aspects of the same modulation and are not conflicting (Δk from range `14.6°`, Δcrest from azimuth `14.3°`).

## Ocean cross-spectra and phase closure

### nearshore

Cross-spectra use detrended/windowed intensity and exactly `F_secondary * conj(F_reference)`.

| Pair | Δt = t_secondary−t_reference (s) | Raw phase (rad) | Smoothed phase (rad) | Local magnitude-squared coherence |
|---|---:|---:|---:|---:|
| 1-2 | -5.795795 | 1.840169 | 1.991057 | 0.8535 |
| 2-3 | -5.793563 | 1.887268 | 2.089765 | 0.7231 |
| 1-3 | -11.589358 | -2.555748 | -2.161434 | 0.5595 |

- Raw same-bin closure error `φ13−wrap(φ12+φ23)`: `2.449e-16` rad.
- Locally smoothed closure error: `4.093e-02` rad.
- Upper-quartile joint-amplitude field closure RMS / max: `2.221e-08` / `9.124e-08` rad.
- The raw same-bin identity is an algebraic consistency check; scientific reliability is assessed from local smoothing and coherence.
- No phase was converted into a wave period.

### offshore

Cross-spectra use detrended/windowed intensity and exactly `F_secondary * conj(F_reference)`.

| Pair | Δt = t_secondary−t_reference (s) | Raw phase (rad) | Smoothed phase (rad) | Local magnitude-squared coherence |
|---|---:|---:|---:|---:|
| 1-2 | -5.795795 | 1.561249 | 1.704330 | 0.2482 |
| 2-3 | -5.793563 | -0.722410 | -0.387232 | 0.0323 |
| 1-3 | -11.589358 | 0.838839 | 2.471783 | 0.0193 |

- Raw same-bin closure error `φ13−wrap(φ12+φ23)`: `-1.110e-16` rad.
- Locally smoothed closure error: `1.155e+00` rad.
- Upper-quartile joint-amplitude field closure RMS / max: `2.225e-08` / `9.020e-08` rad.
- The raw same-bin identity is an algebraic consistency check; scientific reliability is assessed from local smoothing and coherence.
- No phase was converted into a wave period.

## Land-control deterministic terms

Registration is performed on `log1p` of 8-column block-averaged intensity (approximately isotropic ground sampling). No correction is silently applied to the ocean products.

| Pair | SICD displacement row,col (pixels) | Ground displacement E,N (m) | Magnitude (m) | Zero-shift log Pearson | Ramp-removed resultant |
|---|---|---|---:|---:|---:|
| 1-2 | -0.0079, -0.5225 | 0.0096, 0.0282 | 0.0298 | 0.6676 | 0.4470 |
| 2-3 | -0.0025, -0.6017 | 0.0081, 0.0330 | 0.0340 | 0.6467 | 0.4020 |
| 1-3 | -0.0113, -2.3104 | 0.0320, 0.1266 | 0.1306 | 0.5636 | 0.3163 |

Shift-closure residual magnitude on ground: `0.066958` m.

Raw-intensity phase correlation was also retained as an adverse diagnostic. A few point scatterers spanning more than six orders of magnitude produced false maxima for pairs 2–3 and 1–3 at display-pixel shifts `[165.00710945173532, 137.97083597393407]` and `[164.97205356934631, 138.0428476152797]`. At those raw candidates, log-intensity Pearson correlations are only `0.0676` and `0.0456`, versus zero-shift values `0.6467` and `0.5636`. Log-intensity registration and Gaussian scales 1, 2, 4, and 8 display pixels all select the zero-shift neighborhood; therefore the apparent ~98 m raw result is rejected as an outlier-driven lock, not corrected away. Exact multi-scale shifts are retained in the metrics JSON.

Ramp-removed resultants of 0.316–0.447 are too low to support one common deterministic phase ramp across all three land looks.

## Method choice and remaining limits

- The intensity-domain choice follows Li, Mouche, Stopa & Chapron (2019), JGR Oceans, section 2.2.1, which explicitly forms sub-look intensity images after inverse transforming three nonoverlapping Doppler parts, then forms image cross-spectra: https://doi.org/10.1029/2018JC014638.
- The three complex64 sub-looks are retained as master products; intensity is derived afterward.
- The present ROI result is a fixed-look diagnostic, not yet an ensemble-averaged operational ocean-wave retrieval.
- A `T_SAR` is not declared in this checkpoint. Effective PVP look times are available, but physical phase interpretation still requires review of land terms, coherence, and dispersion across future independent tiles/dwells.
- Synthetic regression suite: `21 passed`. The original five convention groups remain explicitly documented in `tests/TEST_REPORT.md`; the two Block-3 wave/registration regressions are documented in `tests/TEST_REPORT_BLOCK3.md`.

## Explicit stop

`CHECKPOINT_3`: stopped before the requested 5–16 s dwell sweep and before depth inversion.

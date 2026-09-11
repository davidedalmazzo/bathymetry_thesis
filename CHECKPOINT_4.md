# CHECKPOINT_4 — Nearshore fixed-width sliding-look phase

## Stop condition

Block 4 is complete for the reliable nearshore ROI, with the land ROI used only as a control. No dwell sweep and no bathymetric inversion were performed.

## Range-axis reconciliation

- `105.848355722°` is CPHD `ReferenceGeometry.Monostatic.AzimuthAngle` at `11.075249663 s`; it is not SICD `SCPCOA.AzimAng`.
- SICD `SCPCOA.AzimAng=101.919310567°` at `SCPTime=9.036361296 s` is the ground-to-platform bearing.
- The groundward slant LOS is `281.919310559°`; positive Grid Row projected on the SCP tangent plane is `281.919311354°`. They define the same undirected line as SCPCOA modulo 180°.
- The geographic frequency conversion uses the local surface Jacobian, not the later CPHD reference angle:

| ROI | wavevector (° mod 180) | local surface Grid Row (°) | Δ from local Row | Δ from SICD SCPCOA axis | Δ from CPHD-reference axis |
|---|---:|---:|---:|---:|---:|
| nearshore | 79.836 | 281.179 | 21.343 | 22.084 | 26.013 |
| offshore | 115.829 | 281.189 | 14.640 | 13.910 | 9.981 |

The Block-3 values `21.3°` and `14.6°` therefore refer specifically to the local surface projection of SICD Grid Row.

## Sliding-look construction and time axis

- Count: `11`; common Doppler width: `28638` bins with energy-normalized Tukey α=0.25.
- Effective physical width: `5.784–5.828 s`.
- CPHD/PVP center spacing: `1.156–1.163 s`; Doppler overlap: approximately `80%`.
- Each processed row used all `107800` SICD columns; pre-decomposition azimuth crop: `False`.
- Nonfinite input values: `0`. Complex64 phase is preserved.
- Chronological looks 1, 6, and 11 are exactly the original three disjoint Block-3 bands (Block-3 looks 3, 2, and 1); their independent set remains stored separately for future dispersion work.
- Processed aperture and CPHD dwell remain distinct: `18.068061721230308 s` versus `22.540812513364376 s`.

## Fixed spectral coefficient

The phase uses one fixed 5×5 Gaussian-weighted patch centered at Block-3 crop bin `[60, 63]` (offset `[-4, -1]`), wavelength `130.793 m`. The coefficient is always `F_secondary * conj(F_reference)` relative to chronological look 1. Local peak drift is recorded separately and never retunes this patch.

## Nearshore phase series

| Look | PVP center t (s) | φ wrapped (rad) | φ unwrap (rad) | fit residual (rad) | direct-reference coherence |
|---:|---:|---:|---:|---:|---:|
| 1 | 3.242899 | 0.000000 | 0.000000 | 0.012358 | 1.0000 |
| 2 | 4.405555 | -0.379165 | -0.379165 | 0.041252 | 0.9783 |
| 3 | 5.565399 | -0.803834 | -0.803834 | 0.023656 | 0.9268 |
| 4 | 6.723517 | -1.300415 | -1.300415 | -0.066457 | 0.8411 |
| 5 | 7.880179 | -1.732274 | -1.732274 | -0.092360 | 0.7764 |
| 6 | 9.036463 | -2.089765 | -2.089765 | -0.044028 | 0.7231 |
| 7 | 10.192835 | -2.389413 | -2.389413 | 0.062179 | 0.6810 |
| 8 | 11.349764 | -2.775716 | -2.775716 | 0.081926 | 0.6365 |
| 9 | 12.508327 | 3.055698 | -3.227488 | 0.036777 | 0.5847 |
| 10 | 13.668796 | 2.598177 | -3.685008 | -0.013451 | 0.5645 |
| 11 | 14.832257 | 2.161434 | -4.121752 | -0.041852 | 0.5595 |

### Unwrapping decision

- Maximum direct temporal step: `0.497 rad`; maximum adjacent cross phase: `0.481 rad`, both below π/2.
- Minimum adjacent coherence: `0.9726`; maximum direct-step/adjacent-cross discrepancy: `0.036 rad`.
- Temporal unwrapping is therefore justified by SAR continuity alone. No buoy or hindcast value entered this decision.

### Linear fit

- `φ(t)=ω_p t+φ_0`, with `ω_p=-0.350972206 rad/s` and `φ_0=1.125810002 rad` for t from CollectionStart.
- Selected fit-only 1σ uncertainty on ω: `0.004844449 rad/s`; 95% interval `-0.361931111` to `-0.340013300 rad/s`.
- `T_SAR=2π/|ω_p|=17.902230 s`; fit-only 1σ `0.247103 s`; fit-only 95% interval `17.360169–18.479234 s`.
- Regression RMSE `0.053226 rad`, maximum residual `0.092360 rad`, `R²=0.998288`.
- Gaussian patch radii 1–5 give `17.884–17.940 s`; adjacent-linked accumulation gives `18.825 s`; the noisier single fixed bin gives `20.384 s`.
- The latter alternatives are a methodological sensitivity envelope, not independent Gaussian samples. The quoted ±0.247 s is therefore fit-only and does not capture all sliding-window systematics.
- The conjugate peak reverses the slope with sum `-1.110e-16 rad/s` and reproduces the period within `-3.553e-15 s`.

## Land control with identical centers

The land patch is the nearest physical EN frequency to the nearshore target: crop bin `[59, 62]`, wavelength `129.261 m`.

| Look | PVP center t (s) | land φ (rad) | land fit residual (rad) |
|---:|---:|---:|---:|
| 1 | 3.242899 | -0.000000 | -0.304012 |
| 2 | 4.405555 | 0.177422 | -0.133629 |
| 3 | 5.565399 | 0.431219 | 0.113146 |
| 4 | 6.723517 | 0.528862 | 0.203777 |
| 5 | 7.880179 | 0.557605 | 0.225517 |
| 6 | 9.036463 | 0.501069 | 0.161980 |
| 7 | 10.192835 | 0.394664 | 0.048574 |
| 8 | 11.349764 | 0.304982 | -0.048112 |
| 9 | 12.508327 | 0.281348 | -0.078760 |
| 10 | 13.668796 | 0.224754 | -0.142381 |
| 11 | 14.832257 | 0.328078 | -0.046100 |

The land slope is `0.006054 ± 0.016956 rad/s` (1σ); its 95% interval `-0.032303` to `0.044411 rad/s` includes zero. `R²=0.0193` and no land period is declared. The nearshore linear trend is therefore not a common deterministic ramp seen on land.

## External comparison performed afterward

The frozen SAR-only JSON predates and is hashed before the external comparison (`c399af008e2159ede9b6e27b8bf99dffdd17b7f808aa263ea569d20438df8fcd`). No phase, branch, fit, or uncertainty was changed afterward.

NOAA/NDBC station 46218 Harvest (CDIP 071), `17.89 km` from the ROI, reports at `2025-02-16T18:56:00+00:00` (`15.7 s` after SICD midpoint):

- Hs `2.02 m`; dominant period DPD `13.33 s`; all-wave average APD `7.31 s`.
- MWD `252°` from, corresponding to a propagation-to axis of `72°`; its undirected difference from the SAR wavevector is `7.84°`.
- `T_SAR/DPD=1.343` and the difference is `4.572 s`. The periods do not agree within the fit-only SAR interval.
- DPD is the maximum-energy spectral period and APD is the all-wave average; neither is automatically a swell-partition period.

## Interpretation boundary

The nearshore fixed-patch phase is experimentally very close to linear over the available centers, and the land control does not share its slope. `T_SAR=17.90 s` is therefore a reproducible SAR phase-rate estimator for this configuration. Its disagreement with the coincident buoy DPD, plus the strong correlation of 80%-overlapping windows, means it is not yet validated as the physical ocean-wave peak period.

No bathymetric inversion, 5–16 s dwell sweep, hindcast-forced branch selection, or retuning to the buoy was performed. Synthetic regression suite: `22 passed`.

## Explicit stop

`CHECKPOINT_4`: stopped before the dwell sweep and before bathymetric inversion.

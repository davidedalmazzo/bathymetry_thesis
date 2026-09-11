# Block 5 - phase theory audit

This note tests the assumption `dphi/dt = omega_ocean`; it does **not** modify the frozen SAR-only estimate. The frozen value remains `-0.350972205517 rad/s` (`T_SAR=17.902230457045 s`).

## Cross convention and quasi-linear model

The Sentinel-1 OSW ATBD defines the look cross-spectrum with the later/secondary intensity transform multiplied by the conjugate of the earlier/reference transform (ATBD Eq. 16), matching `F_secondary * conj(F_reference)`. Its quasi-linear ocean-to-SAR model (Eq. 34) is

`P_qlin(k,t) = C(k) [ A(k) exp(-i omega t) + B(k) exp(+i omega t) ]`,

where `A=|T(k)|^2 S(k)`, `B=|T(-k)|^2 S(-k)`, and `C` contains the stationary system transfer and azimuth-cutoff attenuation. Therefore the selected `+k` component has negative phase slope under the validated convention, while the conjugate peak has the opposite sign.

The phase is

`arg(C) + atan2((B-A) sin(omega t), (A+B) cos(omega t))`.

Only the unidirectional limit `B=0` gives `phi=-omega t+constant`. Equal counter-propagating effective energy (`A=B`) makes the cross-spectrum real and removes a continuous directional phase. At zero lag,

`dphi/dt = omega (B-A)/(A+B)`.

Thus the MTF does not simply disappear: its *phase* cancels in ideal stationary `|T|^2`, but its directional amplitudes change the effective ratio `B/A = |T(-k)|^2 S(-k) / (|T(k)|^2 S(k))`.

## Numerical implication for the two candidate periods

For 17.902230457 s, `omega=0.350972205517 rad/s`, numerically identical in magnitude to the SAR-only slope. The zero-lag effective reverse/forward ratio is `0` (essentially unidirectional).

For 13.33 s, `omega=0.471356737223 rad/s`. Matching only the *zero-lag derivative* would require `B/A=0.146395`. But over the actual 0-11.589 s PVP baselines that model fits a slope of `-0.479660 rad/s`, not -0.351. Scanning `0 <= B/A <= 0.99` never reaches the observed slope. A stationary quasi-linear directional mixture alone therefore cannot turn a 13.33-s unidirectional branch into the observed highly linear 17.902-s phase history.

If the physical ocean component were nevertheless 13.33 s, an additional net phase-rate term of about `+0.120385 rad/s` would be needed relative to the `-omega` branch.

## Terms that can bias the measured slope

1. **Nonlinear SAR contribution.** Engen-Johnsen's forward transform is nonlinear. OSW explicitly subtracts a complex `P_nlin(k,t)` simulated as a function of wind speed, direction, and inverse wave age before applying its quasi-linear inversion. Vector addition changes phase rate through `Im(P* dP/dt)/|P|^2`.
2. **Velocity-bunching/shift and RAR MTF.** OSW uses `T(k)=i k_y T_xi(k)+T_sigma(k)` (Eqs. 35-37). The ideal Eq. 34 contains its squared magnitude, but directional asymmetry changes `A/B`; different effective look filters or time variability can add differential phase.
3. **`S(k)/S(-k)`.** Counter-propagating energy makes phase nonlinear in lag and can suppress the zero-lag derivative. It is not a constant multiplicative correction to omega.
4. **Finite k-patch and peak drift.** The measured coefficient is a coherent weighted sum over 25 bins, each with different dispersion, directionality, MTF, and nonlinear contamination. `arg(sum P_k)` is not `sum arg(P_k)`.
5. **Six-second overlapping looks.** Each point is a temporally filtered observation, not an instantaneous surface. Identical symmetric windows primarily attenuate amplitude; unequal effective windows and overlap correlations can bias phase and understate uncertainty.
6. **System/registration phase.** A constant `arg U(k)` is only an intercept. A time-dependent image shift gives a ramp `-2 pi k dot Delta_x(t)`. The land control is consistent with zero common slope, constraining this mechanism.
7. **Hydrodynamic frequency.** Finite depth and current advection (`k dot U_current`) alter the observed pattern frequency relative to intrinsic deep-water dispersion.
8. **Noise and decorrelation.** Cross-spectra suppress the co-spectrum speckle pedestal, but finite averaging, clutter, and motion decorrelation still perturb phase.

## Scope warning

The OSW structure is the appropriate theoretical warning against equating phase rate and ocean frequency automatically. Its calibrated Sentinel-1 C-band open-ocean MTF and nonlinear lookup tables are not transferable as numerical corrections to this Umbra X-band nearshore case.

Sources: [Engen & Johnsen (1995)](https://doi.org/10.1109/36.406690); [Sentinel-1 OSW ATBD v1.3](https://sentinels.copernicus.eu/documents/247904/349449/S-1_L2_OSW_Detailed_Algorithm_Definition.pdf), pp. 25-26 and 36-40; [Monteban et al. (2019)](https://doi.org/10.1029/2019JC015311).

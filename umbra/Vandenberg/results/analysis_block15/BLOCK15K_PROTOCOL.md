# Block15K — protocol frozen before matched calculations

## Scope, inputs and invariants

This is the final Vandenberg causal-closure block. It reads only existing lightweight results, the three existing SICD-derived non-overlapping enlarged intensity looks, and the existing 32-look BP12 complex stack. It performs no new raw CPHD/SICD read or image formation, download, sweep, inversion, peak search, empirical frequency correction, commit or push. Frozen signed slopes are `-0.3509722055168202 rad/s` on the canonical positive geographic lobe for SICD and `-0.4120656492031189 rad/s` on the conjugate of BP12's stored negative-k peak. The cross convention remains `F_secondary * conj(F_reference)`.

Input paths, byte sizes and SHA-256 values are frozen in `BLOCK15K_CONFIG.json`. The physical ROI is the Block7 common-centred 1440 m × 650 m ocean rectangle, UTM 10N centre `(715510.6102416331, 3827627.093742074)`, sampled at 5 m on the BP grid. The fixed wavevector is the positive canonical vector parallel to bearing `79.8357237° mod 180`, with target magnitude `2π/130.6028192373831 = 0.048109... rad/m`. No temporal result may change the selected lobe or coefficient.

## Matching

The common available time interval is the intersection of the SICD processed aperture `[0,18.068061721230308] s` and CPHD `[0.0029798746666666667,22.543776109333333] s`. For the final comparison, the three already formed SICD looks retain their PVP-mapped effective supports and centres: approximately `[0.3206,6.1446]`, `[6.1448,11.9287]`, `[11.9289,17.7574] s` and centres `3.2429, 9.0365, 14.8323 s`. Their explicit sub-band window is Tukey `α=0.25`, energy-normalised, while the unknown vendor SVA/PFA contribution remains unidentifiable.

BP12 sublooks are a disjoint uniform 0.7043998823 s pulse basis. They are coherently recombined with pulse-count times the mean of each target Tukey kernel over the BP bin, then L1-normalised; this reconstructs the closest available BP kernel at the same three centres without a new backprojection. Kernel comparison uses unit-integral non-negative weights sampled at 1 ms: centre error, effective RMS duration, L1 distance and cosine similarity. Required matching tolerances are centre error ≤ half one BP bin (`0.35220 s`), RMS-duration difference ≤ one BP bin (`0.70440 s`) and kernel cosine ≥0.95. Failure makes the final comparison only partially paired.

The SICD intensities are mapped from their frozen Block7 coarse image coordinates to the fixed ground grid by the frozen affine EN→SICD Jacobian and bilinear interpolation. BP12 is already on that grid. Both paths then use the same global-plane detrend, one spatial Tukey `α=0.1`, unpadded FFT and energy scaling. The coefficient is the nearest bin to the frozen positive canonical `k`; the conjugate bin is checked, never independently selected. Mapping tolerance is half the larger native radial spacing; distances are reported in rad/m and in Block15H `delta_eff = 2.223` radial bins.

The temporal estimator is a signed OLS phase slope after continuity-guarded unwrap, with free intercept and `F_secondary*conj(F_reference)`. Reported uncertainty is the larger OLS/HAC result where enough looks exist; three-look fits are explicitly low-degree-of-freedom diagnostics. Patch MSC is calculated by smoothing cross- and auto-spectra over the same fixed 3×3 neighbourhood; single-bin normalized products are never called coherence.

## Nested ablation

A: frozen historical SICD versus frozen historical BP12. B: BP12 restricted to the SICD processed/common time support, retaining BP spatial/operator choices. C: common 1440×650 m ground ROI, detrend/window, fixed physical k and estimator, while retaining native temporal sampling. D: three BP looks kernel-matched to the three existing SICD looks. E: D interpreted only as residual formation-path dependence. Steps share one acquisition and are not independent replicates; sequential changes are not assumed additive.

## Predeclared gates and tolerances

Level 1 (kinematic detection) requires ≥0.5 observed phase cycle, fixed/conjugate sign closure ≤`1e-10 rad/s`, `R²≥0.97`, maximum adjacent phase step `<π/2`, properly defined patch MSC ≥0.5, and reproducibility with no temporal peak selection. Formation stability is “supported” only if the final signed slope difference is ≤`max(0.02 rad/s, 2*combined fit SE)`; `0.02 rad/s` is fixed from the prior BP12 phase-residual scale divided by its time span, not chosen from the matched result. If the three-look comparison lacks reliable MSC or uncertainty, Level 1 may be supported with limitations using the independently verified 11/32-look results.

Level 2 (identified wave frequency) additionally requires a single component separated by ≥2 `delta_eff`, robustness to ROI/window/formation within the Level-1 tolerance, no unresolved persistent/slow contribution, and independent directional/spectral compatibility. The `2 delta_eff` and transfer/persistence requirements are provisional validation gates, not universal thresholds.

Level 3 (bathymetry) requires Level 2, at least four independently resolved radial elements across the lobe, a resolved `ω(k)` relation, independent bathymetry/reference, and either constrained current or demonstrably negligible depth–current degeneracy. Otherwise the mandatory result is abstention.

The two paths are causally equivalent only if temporal kernels, physical grid/support, coefficient mapping and processing are within tolerance **and** the native SICD formation/weight operator is known. Missing vendor SVA samples therefore cap this experiment at partial pairing regardless of numerical agreement. Planned tests cover time intersection, centre/kernel matching, Doppler-time monotonic conversion, physical-k mapping, sign and cross convention, conjugate handling, deterministic reruns, immutable peak selection, frozen/new separation, deterministic gates, abstention and artifact guards.

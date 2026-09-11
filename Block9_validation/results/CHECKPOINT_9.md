# CHECKPOINT_9 — end-to-end synthetic validation

Generated: 2026-09-01T10:51:57.603957+00:00

## Frozen scope

- Block 8 remains a screening result only: its best available candidate is the 2025-12-02 Gulf collect, conditional because the verified buoy peak is 4.255 s wind sea rather than long swell. No candidate payload was downloaded.
- Vandenberg Blocks 4–8 and `T_SAR=17.902230457 s` were neither modified nor reinterpreted.
- No dwell sweep, bathymetric inversion, radar download, or real-data rerun was performed.

## Independent Block-6 recheck

- 68 CSV rows form 34 exact conjugate pairs and 34 independent half-plane representatives.
- The connected nearshore lobe has 22 conjugate-deduplicated bins (overlapping patches, hence fewer than 22 statistical DOF).
- Aligned conjugate slopes agree within `1.665e-16 rad/s`.
- Exact lobe range: lambda `80.535–191.508 m`, omega_obs `0.345942–0.422864 rad/s`.
- Unique-bin weighted fit: `b=1.683018 m/s`; verified numerically but **not** identified as group velocity.
- The 381/242 m low-k bins are a disconnected, smoothing-sensitive feature, not a resolved transition inside the nearshore lobe.

## Synthetic truth

- Six grid-resolved components span approximately 83–191 m and obey finite-depth gravity-wave dispersion at h=10 m.
- Their periods are independent synthetic values; neither 17.9 s nor 13.33 s is used.

## TEST A — Oracle intensity

- Maximum |omega_hat-omega_truth|: `0.002119 rad/s`; RMSE `0.001136 rad/s`.
- All bins valid: `True`. The nonlinear dispersion curve remains resolved and does not collapse to a constant.

## TEST B — negative controls

- Static maximum error: `0.000e+00 rad/s`.
- Constant-frequency maximum error: `1.818e-06 rad/s`.
- Artificial linear-law recovered coefficients: `a=0.200396 rad/s`, `b=4.992340 m/s` for injected a=0.2 and b=5.0.

## TEST C — conjugates

- Maximum synthetic +k/-k signed-slope sum: `1.110e-16 rad/s`.
- Future independent counts use one canonical half-plane; frozen Block-6 files were not edited.

## TEST D — full sub-aperture surrogate

- Construction: `Z(x,f)=R(f)[1+sum epsilon A_j exp(i k_j x-i omega_j t(f)+i phi_j)]` with an exact linear Doppler-bin to slow-time map.
- `Col.Sgn=-1` surrogate uses FFT image→Doppler and IFFT Doppler→image; 11 six-second Tukey looks have 1.2 s centers and 80% overlap.
- Doppler round-trip relative maximum error: `9.892e-16`.
- Maximum final frequency error: `0.002666 rad/s`; RMSE `0.001382 rad/s`; all bins valid `True`.
- First failing stage: `None`.

## Constant-collapse audit and fixes

- Fixed truth centers, temporal series, patch IDs, unwrap results, reference cross-spectra and sign-alignment outputs are asserted distinct per component.
- Conjugate pairs are deduplicated before fitting/statistics.
- Synthetic carrier construction uses a deterministic unit-modulus coherent carrier. A constant-phase carrier was rejected because it collapses into one azimuth impulse and makes spatial tapering dominate artificially; this correction is covered by the full-surrogate regression test.
- No production real-data estimator bug causing constant-slope reuse was found.

## Progressive realism

- `white_additive_noise`: max |bias| `0.002084` rad/s, max std `0.000218` rad/s, RMSE `0.001147` rad/s.
- `fixed_speckle_background`: max |bias| `0.002397` rad/s, max std `0.004029` rad/s, RMSE `0.002278` rad/s.
- `decorrelating_speckle`: max |bias| `0.002048` rad/s, max std `0.000595` rad/s, RMSE `0.001178` rad/s.
- `unequal_component_amplitudes`: max |bias| `0.002037` rad/s, max std `0.000000` rad/s, RMSE `0.001154` rad/s.
- `finite_width_spectral_peaks`: max |bias| `0.008773` rad/s, max std `0.000000` rad/s, RMSE `0.004798` rad/s.
- `real_data_like_detrend_Tukey_window`: max |bias| `0.002119` rad/s, max std `0.000000` rad/s, RMSE `0.001136` rad/s.
- `80_percent_overlapping_Doppler_looks`: max |bias| `0.002666` rad/s, max std `0.000000` rad/s, RMSE `0.001382` rad/s.

## Full suite and decision

- Block-9 acceptance assertions: `True`.
- Total repository suite: **49 passed in 6.32 s**, including seven new Block-9 regression tests; zero failures. Exact command/result: `BLOCK9_TEST_SUITE_RESULT.json`.

# AUTHORIZED TO RETURN TO REAL DATA

This authorization concerns software correctness only. It does not authorize a candidate SAR download; that remains a separate post-checkpoint decision.

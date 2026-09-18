# CHECKPOINT_10 — physical ocean-to-SAR forward model

Generated: 2026-09-01T13:35:02.772471+00:00

## Guardrails

- Blocks 4–9 and the Block-8 shortlist were hash-guarded and remained unchanged.
- No radar data was downloaded; no real-data dwell sweep or bathymetric inversion was performed.
- The synthetic amplitudes use fixed steepness `ka=0.012`; no coefficient was fitted to 0.35 rad/s or 17.9 s.

## Definitive real-data benchmark

- One half-plane contains `22` unique connected-lobe bins.
- k range `0.032809–0.078018 rad/m`; omega_obs `0.345942–0.422864 rad/s`.
- Weighted fit `omega_obs=0.280323+1.683018 k`, R2=0.8019.
- After k is included, the standardized angle/k effect ratio is `0.0405`; no strong independent angle law is resolved.

## Forward-model formulation

For each component `psi=k·x-omega t+phi`, linear theory gives `u_h=a omega coth(kh) cos(psi) k_hat` and `w=a omega sin(psi)`. With LOS positive toward the sensor, `u_LOS=sin(i)u_range+cos(i)w`. The real geometry is `i=21.8429 deg`, `R/V=79.7106 s`, and `y_SAR=y+(R/V)u_LOS`.

- M0: `10+eta` passive wave tracer.
- M1: geometric tilt/RAR proxy `(n·LOS/cos(i))^2`.
- M2: brightness-preserving inverse azimuth warp.
- M3: conservative forward mapping, including density/Jacobian and folds.
- M4: RAR brightness plus conservative bunching/Jacobian.

## Nominal 6-s results

| Angle | Model | max bias rad/s | RMSE rad/s | d omega_hat/dk m/s | constantness | folds/collapse |
|---|---:|---:|---:|---:|---:|---|
| range_0deg | M0 | 0.003861 | 0.002404 | 8.5781 | 0.999 | no; max fold 0.000% |
| range_0deg | M1 | 0.003449 | 0.002128 | 8.5814 | 0.999 | no; max fold 0.000% |
| range_0deg | M2 | 0.003861 | 0.002404 | 8.5781 | 0.999 | no; max fold 0.000% |
| range_0deg | M3 | 0.003861 | 0.002404 | 8.5781 | 0.999 | no; max fold 0.000% |
| range_0deg | M4 | 0.003449 | 0.002128 | 8.5814 | 0.999 | no; max fold 0.000% |
| vandenberg_like_22deg | M0 | 0.000281 | 0.000149 | 8.5594 | 1.000 | no; max fold 0.287% |
| vandenberg_like_22deg | M1 | 0.000219 | 0.000128 | 8.5587 | 1.000 | no; max fold 0.287% |
| vandenberg_like_22deg | M2 | 0.001961 | 0.001005 | 8.6110 | 1.006 | no; max fold 0.287% |
| vandenberg_like_22deg | M3 | 0.000529 | 0.000307 | 8.5722 | 1.002 | no; max fold 0.287% |
| vandenberg_like_22deg | M4 | 0.000530 | 0.000311 | 8.5725 | 1.002 | no; max fold 0.287% |

No M0–M4 case destroys the injected dispersion. Range-travelling waves are nearly insensitive to azimuth bunching, as expected from ky=0. At 22 deg, nominal folds occur locally, but the six fundamental phase rates remain distinct.

## Bunching-strength sweep (M4, 22 deg, 6 s)

| beta/beta_VDB | d omega_hat/dk m/s | RMSE rad/s | constantness | max fold % |
|---:|---:|---:|---:|---:|
| 0.00 | 8.5587 | 0.000128 | 1.000 | 0.000 |
| 0.25 | 8.5577 | 0.000123 | 1.000 | 0.000 |
| 0.50 | 8.5600 | 0.000155 | 1.000 | 0.000 |
| 1.00 | 8.5725 | 0.000311 | 1.002 | 0.276 |
| 1.50 | 8.5942 | 0.000717 | 1.004 | 3.975 |
| 2.00 | 8.6330 | 0.001516 | 1.009 | 10.637 |
| 3.00 | 8.8166 | 0.005615 | 1.030 | 19.980 |

No predeclared quasi-constant transition occurs over 0–3 times the Vandenberg R/V bunching scale.

## Synthetic look-width experiment (M4, 22 deg, nominal R/V)

| width s | d omega_hat/dk m/s | RMSE rad/s | min coherence | valid modes |
|---:|---:|---:|---:|---:|
| 6.0 | 8.5725 | 0.000311 | 0.9938 | 6 |
| 4.0 | 8.5763 | 0.000385 | 0.9917 | 6 |
| 3.0 | 8.5773 | 0.000407 | 0.9911 | 6 |
| 2.0 | 8.5779 | 0.000422 | 0.9907 | 6 |
| 1.5 | 8.5782 | 0.000427 | 0.9906 | 6 |

The model keeps spatial FFT resolution fixed; it tests temporal look averaging but not raw-SAR aperture-dependent PSF broadening.

## Frozen Vandenberg prediction gate

- Prediction: **No material short-look increase in domega_hat/dk is predicted by this model.**
- Triggered: `False`.
- Action: Do not process new Vandenberg short looks; the predeclared trigger failed.
- Because the trigger failed, no new 1.5–2 s Vandenberg processing was performed.

## Physical conclusion and limitations

This minimal linear-wave + geometric RAR + scalar velocity-bunching/Jacobian model does **not** explain Vandenberg's loss of dispersion. The first mechanism destroying omega(k) is therefore not found among M0–M4, even when local folds appear.

The forward model is not a raw-SAR simulation. Missing mechanisms include hydrodynamic modulation, coherent speckle, phase-history/focusing of moving scatterers, higher-order velocity bunching, full two-scale Bragg scattering/MTF, range migration, decorrelation, and look-dependent complex transfer terms. Failure to reproduce Vandenberg is not automatically attributed to the ROI.

## Verification

- Dedicated thesis environment: `D:\Dati Tesi\Umbra\.venv-umbra-thesis\Scripts\python.exe` (Python 3.13.9), isolated from system site packages and bootstrapped from the general Miniconda interpreter, not from `sdb-iride`.
- Scientific stack: SarPy `2.0.1`, NumPy `2.5.2`, SciPy `1.18.1`, Matplotlib `3.11.1`; exact lock in `requirements-thesis.txt`.
- The complete Block-10 analysis was rerun in this environment.
- Block-10 tests: `8 passed in 1.85 s`.
- Full suite, including SarPy-dependent tests: `57 passed in 6.56 s`.
- Frozen-artifact hash guards: unchanged.

# CHECKPOINT_10

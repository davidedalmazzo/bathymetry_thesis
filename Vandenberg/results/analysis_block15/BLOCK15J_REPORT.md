# Block15J — multi-lag complex-increment diagnostic (synthetic only)

## Scope and initial audit

No real coefficient, CPHD/SICD signal array, download, new formation, dwell sweep, inversion, commit or push was used. This is a coefficient-only synthetic experiment on the frozen BP12-style irregular time grid, support, Tukey response and spatially correlated window-noise covariance.

The frozen Block15I CSV has 72 sequences: 24 calibration and 48 evaluation (`A=16`, `B_static=16`, `B_slow=16`). Its decision matrix is `A→B=0/16`, `B detected=0/32`, and `abstain=48/48`; this agrees with its summary. In the CSV, the `frozen_criteria_pass` column (the fit/circular validity field) is true for `A 16/16`, `B_static 13/16`, `B_slow 12/16`. For B, 7/32 have slope error >10% (3 static, 4 slow), 25/32 are <=10%, none has a missing slope, and none of the seven >10% cases has that fit/circular-valid flag. Thus “no distorted B passes all criteria” in the frozen summary is correct, but it must not be read as “no B is fit-valid”: 25 B have <=10% error and the fit/circular validity flag. The 15I narrative's 107-test count is inherited from Block15H: no `test_*15i*` pytest module exists, so the 15I runner itself had no direct focused coverage. This is an audit discrepancy, not a modification of 15I.

All five current 15I guards match: H and G delivery manifests plus F, B and E configurations. They are provenance/input guards only; they aggregate the earlier blocks’ own manifests and do not hash the 15I runner, CSV, report, protocol or its delivery manifest. Consequently they are not a full integrity manifest for frozen 15I.

## Frozen primary diagnostic

For coefficients `z(k,t)`, I formed `Δz_ab=z(k,t_b)-z(k,t_a)` and, on a fixed 17x7 support, the support-weighted mean `E_j=mean_ab sum_k w_k |Δz_ab(k)|² / median_t sum_k w_k |z(k,t)|²`. The four fixed classes are `[0.6,2)`, `[2,5)`, `[5,12)`, `[12,23)` s, approximately 0.027–1.0 of the 22.19 s span. Classes need at least three pairs. The sole score is `log(E_late/E_early)`.

Pairs, lag bins and support bins share looks and windowed information; they are not samples. A whole Monte-Carlo sequence is the only statistical unit. The support Tukey response is applied once, and no unwrap, truth phase alignment, transfer division or fitted component frequency enters the score. The calibrated one-sided rule is B only when the score is at or below the A-calibration 5th-percentile conservative order statistic, otherwise abstain. Its frozen threshold is 0.273474. The predeclared utility gate requires A→B <=10%, B detection >=50%, decisions >=40%, and >=40% B detection on held-out geometry.

Analytically, an observed constant `c` cancels: `(z_b+c)-(z_a+c)=z_b-z_a`. For `z=a exp(i s t)`, the increment energy is `4|a|² sin²(s Δt/2)`. Additive iid circular noise contributes a lag-independent expected `2σ²`; stationary OU noise contributes `2σ²[1-exp(-Δt/τ)]`. Differencing eliminates DC information, so cancellation is explicitly not detection. A source-static term `c` observed through time-varying `H(t)` instead gives `c[H(t_b)-H(t_a)]`: it does not cancel. The primary campaign holds H constant; variable-H non-cancellation is only an analytic/unit-test control, hence no transfer-robust real-data claim is supported.

## Predeclared campaign and outcome

Calibration used 24 independent sequences (A finite spatial-band propagation, B observed-static, B slow OU; eight each; seed 151000); evaluation used 48 independent sequences (three families × radial/tangential held-out separations × eight; seed 151001). Evaluation has ratio 1.0 and radial 3.0-bin or tangential 1.452-bin separation, excluded from calibration. A has three finite-depth-dispersive modes at depth 10 m and zero current, so it intentionally has no single frequency truth. B has one primary slope and a nearby observed-static or τ=5 s OU coefficient. iid and 5 s measurement-noise cases alternate at amplitude SNR 10. Four fixed controls are recorded separately.

| Evaluation unit | B calls / n | Abstentions | 95% Wilson interval |
|---|---:|---:|---:|
| A band (false A→B) | 3 / 16 | 13 | 6.6–43.0% |
| B static observed | 8 / 16 | 8 | 28.0–72.0% |
| B slow OU | 0 / 16 | 16 | 0.0–19.4% |
| All B | 8 / 32 | 24 | 13.3–42.1% |
| Held-out tangential B | 4 / 16 | 12 | 10.2–49.5% |

Overall, 11/48 sequences receive a B decision (22.9%) and 37/48 abstain. B slope error is >10% in 8/32 and <=10% in 24/32; no B slope is unavailable, and 24/32 carry the frozen fit/circular validity flag. The score fails every material utility condition: false A→B is 18.75%, all-B detection is 25%, decision fraction is 22.9%, and held-out B detection is 25%. The wide stratified intervals are reported descriptively; no pooled-binomial homogeneity assumption is made across B mechanisms.

On the *same 48 newly generated sequences*, the unchanged frozen Block15I score makes 0 A→B calls, detects 0/32 B and abstains 48/48. Block15J is less conservative and does detect part of the exact observed-static B condition, but it does not meet the prespecified utility threshold and entirely misses slow-OU B. It therefore does not establish useful A/B discrimination, slope validity, or recovery of a physically interpretable wave frequency.

## Decision

The new hypothesis is not supported at the predeclared utility level. The apparent static-offset sensitivity is insufficient and does not transfer to slow persistence or the held-out geometry. No post-hoc score, threshold, transfer correction, real-data application or further synthetic campaign was added. Stop at Block15J.

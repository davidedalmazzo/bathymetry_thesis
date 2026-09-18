# BLOCK 9 — independent Block-6 real-data recheck

This report is read-only with respect to all frozen Vandenberg artifacts.

## Conjugate deduplication

- CSV rows: **68**.
- Exact +k/-k pairs: **34**; unpaired rows: **0**.
- Independent half-plane representatives: **34**.
- Conjugate-deduplicated bins on the connected frozen nearshore lobe: **22**.
- Maximum aligned pair mismatch: `1.665e-16 rad/s`.
- These are unique spectral-bin observations, not independent statistical DOF, because adjacent 5x5 patches overlap.

## Recomputed omega_obs(k)

- Connected-lobe wavelength range: `80.535–191.508 m`.
- Exact `|dphi/dt|` range: `0.345942–0.422864 rad/s`.
- Therefore the earlier 80.5–191.5 m range is verified, but 0.352–0.407 rad/s is only an approximate trimmed description; the complete lobe reaches 0.34594–0.42286 rad/s.
- Inverse-variance WLS on 22 unique bins: `omega=0.280323+1.683018 k`, with descriptive bootstrap 95% interval for b `1.467–2.022 m/s`.
- Unweighted sensitivity gives `b=1.586448 m/s`.
- The reported ~1.68 m/s is verified numerically, but it is not called group velocity: finite-depth `domega/dk` over h=5–20 m is much larger and the observed points do not follow a gravity-wave dispersion curve.

## Apparent low-k transition

- lambda=241.694 m: |rate|=0.019519 rad/s, signed rate=-0.019519, R2=0.9769.
- lambda=381.154 m: |rate|=0.031210 rad/s, signed rate=-0.031210, R2=0.9647.

Two low-k high-quality bins exist at about 381 and 242 m, but they form a disconnected component and have the opposite signed branch on the chosen half-plane. Their small rate persists qualitatively yet changes materially with patch size and loses validity for wider patches. This is not a resolved transition inside the connected nearshore lobe.

The coherence thresholds do not create the numerical slope; they only gate it. The strongest implementation sensitivity is local spectral smoothing. The original small phase steps exclude an unwrap-branch explanation, and direct offset checks exclude a patch-index mapping error.

**Conclusion:** the connected nearshore lobe is a relatively flat phase-rate ridge, not an observed ocean-wave dispersion curve. The two low-k points are a separate, processing-sensitive feature and cannot be interpreted as a resolved regime transition.

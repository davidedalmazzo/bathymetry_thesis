# CHECKPOINT_29 — Samoa Doppler–time gate

**Phase A CONDITIONAL; SICD download not started.**

The full compact PVP block was recovered: 21,716 records ×376 bytes,
8,165,216 bytes. Big-endian layout from the original CPHD XML, integer SIGNAL
and PulseNumber parsed correctly. Tx/Rcv/scene-interaction times monotone;
gap max/median 1.00543, SIGNAL=1. PVP angle agrees with the declared PFA
polynomial at ~1.1e-8 s equivalent timing error and independent SICD ARP
geometry at ~3.5e-7 s. TxTime span 3.691770699 s remains distinct from SICD
processed aperture 2.975363044 s and catalog 3.6 s.

The geometric SCP mapping is consistent. Increasing Col-frequency bands
have decreasing physical times: three SCP carrier-center times
3.126629 / 2.216655 / 1.302203 s; support durations ~0.908/0.912/0.917 s,
not automatically nominal 0.95 s. Numerical sign/conjugate tests re-executed.

The frozen timing gate is not met for the local-gradient transport diagnostic:
combined center sensitivity 0.392281 s versus 0.05 s threshold; 19/90 local
candidate kernels not identifiable in the assumed geometry support. Radial
center sensitivity at SCP is 0.037861 s, k/time-weight center difference
0.000888 s; baseline/duration sensitivities ~4.58/4.59% meet their thresholds.

Important: local phase-gradient reprojection is NOT a verified re-indexing
of the shared global PFA output grid. Offsets may include deterministic focus
phase/carrier effects, not physical temporal bias. The missing local/global
kernel transport is an explicit modelling impediment, not scene invalidity.
No tolerances relaxed, no alternate formation, no buoy tuning/q.

Actual oblique ValidData geometry was used in a small complex image-domain
carrier-multiplex synthetic, static and known dynamics, hard mask plus one
taper sensitivity. Static slopes ~zero; dynamic -0.700336/-0.699960 rad/s for
truth -0.7. Not a raw SAR simulator or certification of actual SAR leakage.

Real SICD integrity/SHA256, overview, ocean peaks, leakage, land control,
real phase and slope stability remain NOT EVALUATED because the gate halted
before download. Complete source metadata size/identity remain from Block28.

242 complete-suite tests passed, no failures/skips. Phase A: 3 transactions,
8,165,216 bytes, including initial sandbox proxy failure and sanctioned
public-network HEAD/range execution. Phase B zero traffic. All prior frozen
files preserved; no CPHD signal, complete SICD, dwell sweep, inversion,
Vandenberg, AIS, commit or push.

[Full report](Block29_Samoa_mapping_trial/REPORT.md),
[gate](Block29_Samoa_mapping_trial/GATE_A.json),
[tests](Block29_Samoa_mapping_trial/TEST_REPORT.md),
[manifest](Block29_Samoa_mapping_trial/MANIFEST.json).

Single proposed next step: resolve the global PFA/local ROI temporal-kernel
transport, including Row dependence, before another download-authorizing gate.

# Block30 FRF execution and corrections — 2026-09-16

Interpreter: `.venv-umbra-thesis/Scripts/python.exe`, working directory repository root. No radar access; scene CSV unmodified (SHA256 `f074ee7d9fbd753a49258a3e38ed204fe3bd92f0dad91e71e9b53a81dfab0597`).

## Required sequence

1. `python code/run_block30_frf_conditions.py --smoke`: initial sandbox proxy connection refused; approved public-network execution succeeded. 201910 waverider-17m: 1487 samples, all six variables parsed. Original parser and monthly filenames were correct.
2. `python code/run_block30_frf_conditions.py --months 202110 --gauges waverider-17m`: succeeded, 2 requests after query batching. Scene 2098202: Hs 1.108 m, Tp 9.547 s, Tm 6.757 s, mean from-direction 59.255 degrees true, offset +15 min. Propagation 239.255 degrees; axial range mismatch 40.2 degrees. These are plausible, not assumed 250 degrees.
3. `python code/run_block30_frf_conditions.py`: succeeded, 72 observation rows and 18 gate rows; 79 requests, approximately 3.5 MB. Final repeat uses cached successful payloads and the verified awac-8m year inventory, requiring no HTTP.

## Script corrections

- Query available variables together with time rather than eight requests per instrument/month, avoiding exhaustion of the existing 120-request cap. Persist URL-addressed payload cache, SHA256 and started/success/error request log; count failed attempts before transport.
- Use DAS availability and variable fill values. Previously -999 passed the loose numeric check and could enter dispersion calculations. Reject missing/nonfinite and negative sentinel values; do not treat non-404 HTTP errors as missing products.
- Preserve all scenes in the gate, including missing or stale observations. Record selected reference and nearest-any-instrument offsets separately. Flag over-60-minute cases and mark the selected waverider reference temporally unusable rather than silently omitting scenes or ranking stale measurements as current.
- Verified awac-8m catalog contains years 2007–2014 only. Skip unsupported years from that inventory; do not rename files or substitute another instrument.
- Sort current references before stale diagnostic-only rows. No direction correction, refraction, Snell transformation, declination adjustment or fixed-direction substitution.

The FRF DAS explicitly states `waveMeanDirection` is MET from-direction clockwise from true north; the dataset has already performed its provider magnetic-to-true conversion. Adding 180 degrees expresses propagation, not an empirical correction. `phi_k_range_deg` uses this measured mean direction and the supplied range axis modulo 180 degrees. Mean direction is not claimed to be the direction at Tp; the latter remains separately available in the conditions table.

## Results and temporal warnings

Event-associated values over the four available instruments: Hs 0.288–1.577 m, Tp 4.592–13.889 s. These are physically plausible bulk values, not a complete spectrum/QC certification. At waverider-17m: Hs 0.393–1.444 m, Tp 4.745–13.514 s, except that two nearest samples are stale and not event references.

No scene has its nearest-any-instrument sample more than 60 minutes away. However waverider-17m is stale for:

- 1941935, 2021-06-29 22:56:51 UTC: -29066.8 min; nearest awac-11m +3.2 min.
- 1942455, 2021-06-30 10:54:50 UTC: -29784.8 min; nearest awac-11m +5.2 min.

For these two rows `temporal_reference_usable=False` and status is `stale_wr17_reference_diagnostic_only`. Their calculated values are retained transparently but must not represent the sea state at acquisition. No automatic substitution of AWAC direction or depth into the 17.8 m diagnostic.

Wavelength at fixed assumed water depth 17.8 m, orbital-velocity cutoff, estimated dwell/baseline and 45–180 degree indicator remain the supplied script's descriptive diagnostics, not validated radar physics or an acceptance threshold. NAVD88 bottom elevation is not automatically instantaneous water depth. No frequency retrieval or bathymetric inversion was performed.

The three new targeted tests cover multi-variable ASCII extraction, epoch/filename and the dispersion diagnostic. Final full repository suite: **245 passed in 20.61 s**, including the final cached-catalog and stale-ranking adjustment. Payloads and metadata are retained in `http_cache/`; request log is not a reconstruction of the earlier uncached smoke and standalone DAS/catalog diagnostics.

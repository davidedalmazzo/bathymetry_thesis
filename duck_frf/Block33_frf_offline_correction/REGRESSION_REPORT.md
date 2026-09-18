# Four cached regression dossiers

Offline outputs: regressions/; private payloads copied to a separate cache and
verified before reuse. No modification of source Block32 cache/budget. Final
copied state remains 40 transactions / 2,412,291 bytes, not reset or enlarged.
Actual new HTTP: zero. Historical consumption remains non determinabile.

| Acquisition | Original/new observation rows | Changed matched measurements |
|---|---:|---:|
| TDX-1 record 11 | 233 / 233 | 0 |
| COSMO 2098202 | 233 / 233 | 0 |
| COSMO 1942455 | 69 / 69 | 0 |
| COSMO 1941935 | 69 / 69 | 0 |

REGRESSION_COMPARISON.json checks product, exact timestamp and original CF time,
offset, value, QC flag, status, tolerance, eligibility and valid fraction for all
604 common rows. No added/removed keys. Original spectral moments/Hm0/periods,
published peak-band parameters and missing bins match. Original nearest-context
position/distance fields match for every product.

Expected schema/provenance differences: per-sample DISTANCES rows (instead of one
raw-nearest row), position_id/original_sample_index references, per-file tensor
names, cross-segment selection references, spectrum-state CSV and explicit
coverage/duplicate diagnostics. Nearest QC position can now differ from raw
context position without changing the measurement itself. Spectral missing and
zero cases are exercised synthetically; the October spectra remain energetic.

Separate June event windows reuse verified historical superset payloads locally
with actual source provenance retained. No missing June spectrum/QC, wind, level
or survey data is manufactured. Stale Waverider remains context only.
TDX milliseconds/catalogue semantics and frozen T_SAR are unchanged.

Source hashes in regenerated manifests intentionally differ from historical
Block32 source references: client corrections are not frozen-artifact changes.

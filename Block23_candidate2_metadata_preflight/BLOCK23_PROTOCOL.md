# Block23 protocol — candidate 2 metadata preflight

## Frozen scope

Only Block21 finalist 2 (`f7ced35f-8a2c-45ef-a822-c442bb47662d`) is audited. Block21/22 and Vandenberg remain immutable. No Block20, buoy query, other candidate, SAR pixel/signal read, formation, sub-aperture extraction, frequency/depth/q estimate, commit or push is permitted.

## Initial provenance

- start commit: `1eb6e75caf20adbb3f51b1e810eb2b9cb817b067`;
- expected identity is checked against Block21 and remote STAC/SICD/CPHD metadata rather than trusted from filenames;
- the same archived Block21 NDBC 46268 dominant half-power band is reused unchanged: 0.0575–0.0775 Hz, peak 0.065 Hz, period 15.384615 s, propagation-to 37.318369°, resultant 0.997049;
- corrected Block22 ROI/coast/edge distances are reused and independently checked against SICD valid support.

## Remote procedure

Order: fetch official STAC; determine object availability and size; try sidecars; recover embedded SICD/CPHD XML via exact byte ranges when necessary; inspect only a fixed small PVP sample set including endpoints if metadata alone cannot establish the observed TxTime span. Never read CPHD signal or SICD pixels.

All original responses, URLs, ranges, timestamps, byte counts and hashes are retained. Exact HTTP 206 and `Content-Range` are required for partial reads. Limits including retry/redirect are 60 transactions, 50 MiB total, 10 MiB per response, two retries, 45 s timeout.

## Geometry and decision

Grid Row is treated as oriented ground-projected range and also modulo 180°. It is compared to the frozen propagation-to direction from the same Block21 wave band. Directional resultant is descriptive; it is not converted into a confidence interval or local-ROI certainty.

The decision is one of: recommendable, conditional on one named verification, or non-priority. Favorable geometry is not evidence that phase-to-frequency observability has already been demonstrated.

Stop at `CHECKPOINT_23` without starting any product download.


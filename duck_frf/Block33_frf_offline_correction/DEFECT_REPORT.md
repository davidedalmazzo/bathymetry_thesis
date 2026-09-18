# Defect reproduction and correction

Before edits, 11 targeted assertions failed (REPRODUCTION.json). No real HTTP.

| Topic | Reproduced evidence | Correction |
|---|---|---|
| New-product inventory | Tried legacy observed ASCII, failed instead of inventory | Every family inventories DAS/DDS; optional variables are not required; per-product failures retained independently |
| Calendar boundaries | Better February observation discarded for March event | Configured context/tolerance defines all needed calendar months; cross-file association retains source/index |
| Far same-month events | Raised event_window_too_broad_split_manifest | Separate bounded subsets, merging only overlapping windows; verified cached supersets sliced locally |
| Entirely missing spectrum | Returned m0=0 / Hm0=0 | Null moments/parameters, no_valid_spectral_bins |
| Valid zero spectrum | Arbitrary first-bin Tp=20 s | Real zero Hm0 allowed, no positive-energy peak/Tp |
| Invalid grid/width | Accepted NaN frequency, NaN width or zero frequency | Finite positive monotone frequency and finite positive width required |
| Selected sample position | No observation→position key, raw-nearest gauge reused | Stable per-sample position_id referenced by all four temporal roles; effective gauge ID resolved at selected index |
| Deployment end | Coordinates retained after deployment_end | Both supplied boundaries checked; outside bounds position unresolved |
| Silent short HTTP stream | Content-Length 20, body 5 accepted/cached as ok | Specific truncated_response, counted bytes, non-ok failure cache, resumable after TTL |
| Clone reproducibility | Block30 test was present locally but absent from Git | Existing unchanged lightweight test explicitly included in pending delivery; synthetic catalog/DAS/DDS fixtures provided |

All reports were confirmed. Additional tests cover December/January, leap day,
missing segment, consistent/conflicting duplicates, different spectral grids,
changing coordinates, unresolved gauge, footprint-vs-ROI, interrupted stream,
unknown length, byte cap and explicit absolute-path remapping.

No corrections to measured directions, radar processing, new physical thresholds
or fabricated historical products. Legacy parsing source and its tests remain
byte-identical; only the reusable client/CLI and new verification code change.

# Block16A — metadata-only Umbra validation-scene selection

Generated: 2026-09-14T08:52:34.308673+00:00  
Catalog snapshot: `Block16_scene_selection/catalog_snapshots/20260913T231747Z` (`complete`)  
Frozen configuration SHA-256: `f6a9829de8526ea05af948546546f6560037416fa4269ae626637b34432ba1a5`

## Outcome

No Category-A primary scene passes every frozen gate. Thresholds were not relaxed.

Conditional alternatives:
- `2024-10-22-22-04-46_UMBRA-09` (collect:0965638a-a446-4fd7-afcd-7a4d96903af2): category B, catalog/CPHD/SICD durations 16.8/16.664182288/13.069074825927965 s, period 4.5 s (model_mean_period_proxy), cycles 2.46876774637037, reference model_only, CPHD/SICD 32698679872/7027712010 bytes.
- `2024-09-16-22-14-37_UMBRA-05` (collect:683a3778-7ef1-4653-bd9b-1777367585d5): category C, catalog/CPHD/SICD durations 43.199999/43.18645380266666/24.955108510644962 s, period 3.5 s (model_mean_period_proxy), cycles 10.62470108647619, reference model_only, CPHD/SICD 90542853856/15455837053 bytes.
- `2025-12-02-16-00-55_UMBRA-07` (collect:ae8a3c9f-ee1e-4fad-82d1-ffe5ec409cf1): category C, catalog/CPHD/SICD durations 17.0/17.163844698666665/11.889154387579627 s, period 4.25531914893617 s (measured_peak_period), cycles 2.6890023361244446, reference measured_complete, CPHD/SICD 74483823488/17007018143 bytes.
- `2023-07-02-02-01-27_UMBRA-05` (collect:038615a1-9f6c-4ab5-ae73-704f2406ab8c): category C, catalog/CPHD/SICD durations 5.999999/None/None s, period None s (missing), cycles None, reference no_reference, CPHD/SICD 9975572352/2571225785 bytes.
- `2025-07-21-07-16-35_UMBRA-05` (collect:048762ec-0eb2-4aca-85aa-ee6ebed84a59): category C, catalog/CPHD/SICD durations 5.199999/None/None s, period None s (missing), cycles None, reference no_reference, CPHD/SICD 31990688448/5058288871 bytes.

No SAR product was downloaded and no scene pixels or CPHD signal samples were read. The byte-range audit was restricted to header/XML and nine stratified TxTime PVP values per audited CPHD.

## Required counts

1. Unique physical acquisitions: **10140**.
2. Duplicate processing rows beyond one preferred processing: **2402**.
3. Acquisitions excluded for anomalous dates/durations: **45**.
4. Preferred records with both CPHD and SICD: **5438**; byte-range-coherent finalists: **5**.
5. Preliminary useful marine ROI: **215**.
6. Complete measured directional reference: **4**.
7. Minimum/preferred cycle threshold: **27 / 22**.
8. Joint temporal, preliminary-spatial and directional geometry gate: **3**.
9. Category-A primary exists: **no**.
10. Remaining preview/small-product gates: measured SAR `delta_eff`, interior coast clearance at SAR scale, lobe separability (>=2 `delta_eff`), usable intensity ROI, SNR/coherence, and full Doppler–slow-time mapping. These are not inferred from Natural Earth or pixel spacing.
11. Non-hard sensitivity: **top candidate stable** under ±10% direction-weight perturbation.
12. Difference from Block8: acquisitions are deduplicated by `collect_id`, anomalous timing is fail-closed, cycles replace a long-period reward, references are queried from the first gate rather than a six-case list, measured/model quantities are separated, and finalist range geometry is independently audited.

## Eligibility categories

| Category | Count | Meaning |
|---|---:|---|
| A | 0 | positive validation with complete measured directional spectrum |
| B | 1 | promising, model-only |
| C | 33 | control/weak/incomplete reference |
| D | 10106 | excluded by an explicit hard gate |
| E | 0 | not evaluable without missing metadata/reference |

## Legacy Block8 audit

1. Confirmed: both legacy crawlers target `Block8_validation/umbra_all.csv`; schemas differ (static-STAC asset metadata versus S3 size-joined fields).
2. Confirmed: legacy finalization keys catalog/waves/references by `collect_name`, despite repeated processing variants.
3. Confirmed: historical catalog has 12,539 rows, 10,137 unique `collect_id`, hence 2,402 duplicate processing rows.
4. Confirmed and more severe: historical durations include 962.6/1848.6 s and values up to 769,206,143.2 s; 82 exceed 120 s.
5. Confirmed: legacy `catalog_dwell_s` is exactly STAC end minus start and is not PVP-verified dwell.
6. Confirmed: legacy scores include a monotone dwell/period reward and no observable-cycle metric.
7. Confirmed: six long-dwell spectra were manually verified (plus two short-dwell rows in a separate output).
8. Confirmed: legacy score assigns up to 15 points for a verified buoy, coupling manual verification and rank.
9. Confirmed: `analyze_block8_ndbc_short_spectra.py` contains six hardcoded `CASES`.
10. Confirmed: legacy score combines model mean-period proxies, measured peak periods, height ratios, long-band energy and verification status.
11. Confirmed: marine fraction alone was used; no interior clean-ROI size was estimated.
12. Confirmed: ocean fraction contributed a positive score and land-control availability was absent.
13. Confirmed: STAC `view:azimuth` was treated as range axis without finalist local-grid verification.
14. Confirmed: baseline suite had no Block8 selector pytest module; Block16A adds an offline dedicated suite.

## Method boundaries

`catalog_duration_s`, `cphd_tx_time_span_s`, and `sicd_processed_aperture_s` remain distinct. A model mean period is never relabelled as a peak period. Model results are `screening_not_independent_validation`. `view:azimuth` is preliminary; only audited SICD Grid Row ground projection is labelled local range. Natural Earth 1:10m is preliminary and cannot establish SAR-scale coast clearance. Deep-water wavelength is a descriptive limit, not truth, and `delta_eff` remains unverified until a small preview/product is inspected.

## Stop

Block16A stops here. No download is authorized automatically.

# Block22 — geographic, visual and SICD metadata preflight

## Result

The five Block21 finalists were re-audited without changing their frozen ROI polygons or ranking. Block21's `local_exact` coast label was too strong: its distance used land clipped to the footprint, so artificial clipping edges could enter the boundary. Block22 instead uses boundaries of the original Natural Earth 1:10m polygons queried in a 250 km neighborhood and reports mask-relative accuracy only.

All five baseline ROI polygons are contained in the footprint-minus-land geometry at Natural Earth resolution. This is not certification against a survey-grade coastline. Center distances, polygon clearances, footprint-edge clearances and buoy distances are now distinct.

## Corrected finalist geography

| Rank | Buoy | center–coast | ROI–coast | center–edge | ROI–edge | buoy–center | buoy–ROI |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | 46268 | 1763.7 m | 1013.6 m | 2127.5 m | 1067.3 m | 437.7 m | 0 m |
| 2 | 46268 | 757.1 m | 181.6 m | 726.8 m | 90.1 m | 1206.5 m | 570.1 m |
| 3 | 46256 | 1766.6 m | 970.6 m | 1309.9 m | 388.5 m | 3128.3 m | 2210.8 m |
| 4 | 44087 | 7361.1 m | 6381.7 m | 1998.5 m | 954.3 m | 3508.3 m | 2528.9 m |
| 5 | 46256 | 1015.0 m | 368.5 m | 743.9 m | 58.0 m | 3766.0 m | 3133.3 m |

`buoy–ROI = 0` means the station coordinate lies inside the candidate-1 ROI polygon. It does not prove that a point buoy represents the entire 1.5 km square or that local wave direction is spatially uniform. Candidate 2 and 5 have only about 90 m and 58 m minimum clearance from the product boundary, respectively.

Maps use a scene-centered metric plane, north arrow and metric scale. Wave arrows are omitted rather than implying that buoy direction was measured throughout the ROI.

## Candidate 1 SICD preflight

The standalone XML URL returned 404. The XML was recovered from an exact 2 MiB byte range at the tail of the 13,799,853,988-byte NITF. The server returned HTTP 206 with the exact requested range. No image pixels were read.

- identity: Umbra-09, core `2025-11-15-18-57-13_Umbra-09`, spotlight, right-looking;
- processing: Umbra SAR Processor 5.0.14, product timestamp 2026-05-06;
- polarization: V:V;
- image: 26,620 × 64,800 complex pixels;
- sampling: row 0.3091 m, column 0.1959 m;
- approximate impulse-response resolution: row 0.3863 m, column 0.2449 m; sampling is not resolution;
- SICD processed aperture: **6.587138417 s** from `ImageFormation.TStartProc/TEndProc`;
- Timeline IPP span: 7.495363670 s;
- catalog duration: 7.6 s. These three quantities are not interchangeable;
- grid: RGAZIM, slant plane, PFA present, `TimeCOAPoly` present, both grid signs −1;
- ground-projected Grid Row/range axis: 316.8276° oriented, or 136.8276° as an unoriented axis;
- incidence: 43.1978°; `SCPCOA.AzimAng=136.8276°`;
- Block21 ROI is inside the SICD image-corner polygon.

The buoy dominant propagation-to direction is 24.0°. Against the unoriented local range axis the axial difference is about **67.17°**, not a favorable near-range alignment. This is a metadata finding, not a new wave-frequency estimate. It materially weakens candidate 1 for the intended phase-to-frequency validation even though the station is spatially excellent.

For the 6.587 s processed aperture, the descriptive 1 s-step paths contain 6, 5, 3 and 1 sliding centers for 1.5, 2.5, 4 and 6 s looks. These overlapping counts are not independent samples.

## Preview and ROI alternatives

The STAC sidecar was recovered, but it advertises no small browse asset. The available SIDD is about 819 MB and the GEC/CSI sizes are not safely bounded in the catalog, so none was downloaded. Consequently wave structure for all five finalists is **not evaluable at available preview resolution**, not absent.

Three neutral 1.5 km alternatives were generated geometrically for candidate 1. A2 has the greatest coast clearance (ROI–coast 1704 m) and keeps the buoy only 89 m outside the polygon, but its visual texture cannot be assessed. The original Block21 ROI remains preferred for now because it contains the buoy coordinate, retains 1014 m mask-relative coast clearance and 1067 m product-edge clearance. No ROI was selected using agreement with buoy period.

## Vandenberg audit

The existing 16,001×16,001 GEC and verified affine georeference were reused read-only. Initial nearshore, offshore and land-control polygons from `ROIS.json` were overlaid. The later Block7/Block15K common support is documented as 1440×650 m in a rotated ground grid, but an exact reversible GEC polygon is not archived; it is therefore not drawn as though its provenance were exact.

The visual seed at GEC columns 2000–9000 and rows 14000–16000 is predominantly marine in the overview and shows banded texture. It is distinct from the original nearshore/offshore centers and does not establish algorithmic suitability. No extraction or spectral analysis was performed. Block15K remains unchanged: Vandenberg is a development stress test and a single physical frequency is not identifiable.

## Remote and integrity audit

Across the preliminary sidecar attempt and final bounded-range run: 5 HTTP transactions and 2,110,160 bytes, below 60 transactions and 50 MiB. The retained final request log contains the final run's three requests; the preliminary two-request run is separately declared in the summary. Historical Block21 and Vandenberg hashes were not rewritten.

## Decision

Candidate 1 is **not recommended for the 13.8 GB download** for the intended range-aligned experiment: the newly verified range-axis difference is approximately 67°. Its spatial reference and ROI are excellent, but that does not compensate for the unfavorable geometry.

The single next step is a bounded SICD-metadata preflight of frozen candidate 2, which has both SICD and CPHD and a 15 s catalog duration, to verify its local range-axis alignment before considering any download.


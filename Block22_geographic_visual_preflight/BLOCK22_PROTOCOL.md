# Block22 protocol — geographic, visual and SICD metadata preflight

## Frozen scope

Block22 audits the five frozen Block21 finalists and Vandenberg geography without changing either source result set. Block20 is not opened or audited. No wave frequency is estimated, no SAR image is formed, and no full SICD/CPHD/GEC is downloaded.

The Block21 ranking and ROI polygons are immutable baselines. Corrections are emitted only in Block22 tables and figures.

## Inputs and provenance

- repository commit at start: `a9dc43da5995b26007bf8b0e146876fc469ecf2b`;
- pre-existing untracked files are listed in `BLOCK22_INPUT_INVENTORY.json` and remain untouched;
- Block21 report, config, shortlist, cards, manifest, selector runner and primitives;
- Natural Earth 1:10m land polygons already archived locally;
- verified Block21 NDBC station associations and payloads;
- local Vandenberg GEC/overview, georeference, `ROIS.json`, BP12/Block15 supports and Block15K classification.

## Geography

All distances are computed in a local azimuthal-equidistant-style tangent metric approximation centered on each scene. Coastline comes from original, un-clipped Natural Earth geometry in a search neighborhood; clipping edges are never treated as coast.

For each frozen ROI report separately:

1. center-to-coast distance;
2. ROI-polygon-to-coast minimum distance;
3. center-to-footprint-boundary distance;
4. ROI-polygon-to-footprint-boundary minimum distance;
5. buoy-to-center geodesic distance;
6. buoy-to-ROI-polygon minimum distance.

Full polygon containment in the footprint-minus-land water geometry is tested. Natural Earth is a coarse geometric reference, not a real-coast certification.

## Remote preflight

Only candidate 1 may use remote access. Order: inventory local assets, obtain a small official sidecar/preview when exposed, otherwise bounded byte ranges from the SICD container header/XML. Limits include redirects/retries: 60 transactions, 50 MiB total, 10 MiB per response, two retries, 45 s timeout. A response that ignores a range and exceeds the requested safe envelope is aborted.

No radar signal array or full product is read.

## Decision policy

Visual wave structure may be `evaluable`, `not evaluable at preview resolution`, or `not inspected`; it is never inferred absent from a coarse image. Alternative ROI identifiers are neutral and cannot be chosen to match the buoy period. A download recommendation requires verified acquisition/product identity, processed SICD aperture, grid/range geometry, image support containing the ROI, and adequate metadata/preview evidence. Otherwise the missing verification is named.

## Stop

Stop at `CHECKPOINT_22`. No commit or push is authorized.


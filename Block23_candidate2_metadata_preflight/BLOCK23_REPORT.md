# Block23 — candidate 2 metadata preflight

## Outcome

Block21 finalist 2 was examined alone. Its identity and vendor metadata are public, but neither declared complex product is publicly retrievable from the frozen Umbra catalog location. The result is therefore **non-priority for this experiment**, without searching another candidate.

## Identity and provenance

Block21 expected collect `f7ced35f-8a2c-45ef-a822-c442bb47662d`, `2025-01-09-06-35-11_UMBRA-10`, Umbra-10, spotlight and VV. The official STAC and `METADATA.json` independently reproduce the collect UUID, Umbra-10, spotlight, right-looking, X band, VV, start `06:35:12 UTC` and end `06:35:27.101624 UTC`.

Block21 records processing version 4.6.2 and creation 2025-01-10. The metadata JSON schema says version 2.0.0; this is not relabeled as processor version. Filename timestamps, catalog center timestamp and metadata start/end are kept distinct.

## Actual asset availability

The STAC declares SICD and CPHD private `s3://prod-prod-processed-sar-data/...` assets. That declaration caused Block21's `has_sicd=True` and `has_cphd=True`, but the frozen public S3 listing contains no SICD or CPHD object for this collect.

Direct checks returned:

| Object | Result |
|---|---|
| STAC | HTTP 200, 8,221 bytes |
| vendor metadata JSON | HTTP 200, 3,761 bytes |
| declared `_SICD_MM.nitf` | HTTP 404 |
| public alias `_SICD.nitf` | HTTP 404 |
| declared `_MM.cphd` | HTTP 404 |
| public alias `_CPHD.cphd` | HTTP 404 |

Consequently complex-object sizes, NITF/CPHD identities, SICD processed aperture, Timeline/IPP, PVP layout, CPHD channel/vector counts and sampled `TxTime` cannot be verified. No pixel or signal data were read.

## Durations

- Block21 catalog descriptor: 15.0 s.
- Vendor collect start/end span: 15.101624 s.
- SICD processed aperture: unknown.
- SICD Timeline/IPP span: unknown.
- CPHD observed `TxTime` span: unknown.

The vendor `timeOfCenterOfAperturePolynomial` constant 6.701384 s is a center-of-aperture value, not an aperture duration. Only catalog-based look scenarios are retained and marked descriptive. Sliding looks are not independent.

## Wave–radar geometry

The frozen Block21 reference is reused unchanged: NDBC 46268, half-power band 0.0575–0.0775 Hz, peak 0.065 Hz (15.3846 s), propagation-to 37.3184° and directional resultant 0.99705. No buoy request or band reselection occurred.

The vendor center metadata gives azimuth 289.1379° and incidence 47.9285°. If that azimuth is treated provisionally as the viewing/range direction, its unoriented axis is 109.1379° and differs axially from the buoy propagation by about 71.82°. This is not substituted for the required SICD Grid Row projection: local range at the ROI, its variation and directed difference remain unverified. Candidate 1's verified Block22 mismatch was 67.17°; candidate 2 is therefore not demonstrably better and is provisionally similarly unfavorable.

## ROI and preview

The immutable Block21 ROI remains fully inside the coarse mask-relative water polygon. Corrected Block22 values are retained: 181.6 m minimum ROI–coast distance, 90.1 m minimum ROI–STAC-footprint distance, buoy–center 1.207 km and buoy–ROI 0.570 km. Ninety metres is a weak product-edge margin for preprocessing, and valid SICD support cannot be checked without its XML. No alternative ROI is proposed because optimization against an unavailable complex support would not be auditable.

No small browse is exposed. Public GEC is 926,486,405 bytes and SIDD 819,268,302 bytes in the frozen listing, both outside the purpose and budget. Marine structure is **not evaluable before download/access**, not absent.

## Decision

Classification: **non-priority for this experiment**.

There is no publicly accessible complex product to recommend for download, its true SICD/CPHD temporal support is unknown, the original ROI has only ~90 m STAC-edge clearance, and the only available center geometry suggests a ~71.82° axial mismatch rather than range alignment. This does not test or invalidate the phase-to-frequency method; it only rejects this acquisition as the first economical validation download under the present access path.

The single next step is to request or verify authorized access to the exact private SICD object for this collect; only if access is confirmed should its XML be audited before any payload download.


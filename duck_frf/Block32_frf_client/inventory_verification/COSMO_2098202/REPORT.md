# FRF observational dossier: COSMO_2098202

Timestamp: 2021-10-13T22:45:03+00:00; semantics: requested_catalogue_timestamp_at_second_precision_not_verified_aperture_center

Catalogue footprint only; valid SAR support NOT VERIFIED. No SAR data read.

## A. Original measurements (independent per product/instrument)

| instrument | variable | value | units | offset s | status |
|---|---|---:|---|---:|---|

Only rows with representative_eligible=True pass the configured QC and time policy; context never fills another instrument.

## B. Calculated quantities

WGS84 distances in DISTANCES.csv, signed offsets and previous/next/nearest QC association in ASSOCIATIONS.json. Spectral integrals are diagnostic, with missing-bin coverage and published-Hs difference. No directional reconstruction or SAR inversion.

## C. Assumptions

Configured temporal tolerances are operational, not universal physical limits. Historical nominal coordinates are conditioned on the dated source; conflicting deployment text remains in metadata. No interpolation, wave refraction or wind-height conversion. Depth datum is preserved, not assumed instantaneous water depth.

## D. Missing/conditional information

No joint state of the tile is asserted. Position is not automatically a measured GPS location. Unverified burst anchoring leaves interval bounds/distance unknown. Unflagged products are QC-unknown under the default strict policy. Survey point/line coverage is not inferred from a bounding box. Unsupported/unfetched families and network limits are listed below:

```json
[
  {
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/meteorology/wind/derived/2021/FRF-met_wind_derived_202106.nc",
    "family": "wind",
    "instrument": "derived",
    "month": "202106",
    "status": "incomplete_budget",
    "detail": "FetchError"
  },
  {
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waterlevel/eopNoaaTide/2021/FRF-ocean_waterlevel_eopNoaaTide_202106.nc",
    "family": "water_level",
    "instrument": "eopNoaaTide",
    "month": "202106",
    "status": "incomplete_budget",
    "detail": "FetchError"
  }
]
```

Source metadata warnings: []

Profiles/2D spectra, when present, are preserved in TENSORS.json with source definitions and masks. Ancillary meteorology/temperature only from selected products. NDBC/CDIP alias republication is not counted independently.

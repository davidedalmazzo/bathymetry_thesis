# FRF observational dossier: COSMO_1941935

Timestamp: 2021-06-29T22:56:51.912000+00:00; semantics: catalogue_start_not_verified_aperture_center

Catalogue footprint only; valid SAR support NOT VERIFIED. No SAR data read.

## A. Original measurements (independent per product/instrument)

| instrument | variable | value | units | offset s | status |
|---|---|---:|---|---:|---|
|FRF:waverider-17m|waveHs|0.47502896|m|-1744011.912|qc_unknown|
|FRF:waverider-17m|waveTp|8.213552|s|-1744011.912|qc_unknown|
|FRF:waverider-17m|waveMeanDirection|124.82897|degree|-1744011.912|qc_unknown|
|FRF:awac-11m|waveHs|0.58215046|m|188.588|qc_unknown|
|FRF:awac-11m|waveTp|7.5901327|s|188.588|qc_unknown|
|FRF:awac-11m|waveMeanDirection|90.99792|degree|188.588|qc_unknown|
|FRF:8m-array|waveHs|0.5347453|m|188.088|qc_unknown|
|FRF:8m-array|waveTp|7.214519|s|188.088|qc_unknown|
|FRF:8m-array|waveMeanDirection|89.8044|degree|188.088|qc_unknown|
|FRF:waverider-26m|waveHs|0.8719761|m|188.088|qc_unknown|
|FRF:waverider-26m|waveTp|6.802721|s|188.088|qc_unknown|
|FRF:waverider-26m|waveMeanDirection|134.20616|degree|188.088|qc_unknown|
|FRF:awac-11m|currentSpeed|0.28975197672843933|m s-1|2888.088|retrieved|

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
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waves/awac-11m/2021/FRF-ocean_waves_awac-11m_202106.nc",
    "family": "waves",
    "instrument": "awac-11m",
    "month": "202106",
    "status": "incomplete_budget_cache_not_available",
    "detail": "FetchError"
  },
  {
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/meteorology/wind/derived/2021/FRF-met_wind_derived_202106.nc",
    "family": "wind",
    "instrument": "derived",
    "month": "202106",
    "status": "incomplete_budget_cache_not_available",
    "detail": "FetchError"
  },
  {
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waterlevel/eopNoaaTide/2021/FRF-ocean_waterlevel_eopNoaaTide_202106.nc",
    "family": "water_level",
    "instrument": "eopNoaaTide",
    "month": "202106",
    "status": "incomplete_budget_cache_not_available",
    "detail": "FetchError"
  }
]
```

Source metadata warnings: [{"instrument": "awac-11m", "family": "currents", "status": "supplier_identifier_conflict", "detail": "URL/title identify 11m AWAC but NC_GLOBAL.id identifies awac5m; both original fields retained, stable logical site ID uses discovered path"}, {"instrument": "awac-11m", "family": "currents", "status": "averaging_time_metadata_conflict", "detail": "aveTime long_name says seconds, units says index; raw 900 retained, interval duration/anchor not automatically inferred"}]

Search coverage: [{"family": "waves", "instrument_id": "FRF:waverider-17m", "required_months": ["202106"], "missing_or_unverified_months": ["202106"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "waves", "instrument_id": "FRF:awac-11m", "required_months": ["202106"], "missing_or_unverified_months": ["202106"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "waves", "instrument_id": "FRF:8m-array", "required_months": ["202106"], "missing_or_unverified_months": ["202106"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "waves", "instrument_id": "FRF:waverider-26m", "required_months": ["202106"], "missing_or_unverified_months": ["202106"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "wind", "instrument_id": "FRF:derived", "required_months": ["202106"], "missing_or_unverified_months": ["202106"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "currents", "instrument_id": "FRF:awac-11m", "required_months": ["202106"], "missing_or_unverified_months": [], "status": "verified_configured_context", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "water_level", "instrument_id": "FRF:eopNoaaTide", "required_months": ["202106"], "missing_or_unverified_months": ["202106"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}]

Spectral states (missing is not calm): []

Duplicate timestamp diagnostics: []

Profiles/2D spectra, when present, are preserved in TENSORS.json with source definitions and masks. Ancillary meteorology/temperature only from selected products. NDBC/CDIP alias republication is not counted independently.

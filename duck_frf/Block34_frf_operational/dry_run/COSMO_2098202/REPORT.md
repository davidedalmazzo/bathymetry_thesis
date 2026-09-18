# FRF observational dossier: COSMO_2098202

Timestamp: 2021-10-13T22:45:03+00:00; semantics: requested_catalogue_timestamp_at_second_precision_not_verified_aperture_center

Catalogue footprint only; valid SAR support NOT VERIFIED. No SAR data read.

## A. Original measurements (independent per product/instrument)

| instrument | variable | value | units | offset s | status |
|---|---|---:|---|---:|---|
|FRF:waverider-17m|waveHs|1.1081544|m|897.000|qc_unknown|
|FRF:waverider-17m|waveTp|9.546539|s|897.000|qc_unknown|
|FRF:waverider-17m|waveMeanDirection|59.25528|degree|897.000|qc_unknown|
|FRF:8m-array|waveHs|1.0385377|m|897.000|qc_unknown|
|FRF:8m-array|waveTp|10.578512|s|897.000|qc_unknown|
|FRF:8m-array|waveMeanDirection|63.65572|degree|897.000|qc_unknown|
|FRF:waverider-26m|waveHs|1.3018659|m|897.000|qc_unknown|
|FRF:waverider-26m|waveTp|10.810811|s|897.000|qc_unknown|
|FRF:waverider-26m|waveMeanDirection|56.356594|degree|897.000|qc_unknown|
|FRF:awac-11m|waveHs|1.1006101|m|897.500|qc_unknown|
|FRF:awac-11m|waveTp|8.316009|s|897.500|qc_unknown|
|FRF:awac-11m|waveMeanDirection|64.31241|degree|897.500|qc_unknown|

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
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waves/waverider-17m/2021/FRF-ocean_waves_waverider-17m_202110.nc",
    "family": "waves",
    "instrument": "waverider-17m",
    "month": "202110",
    "status": "offline_cache_miss",
    "detail": "FetchError"
  },
  {
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waves/8m-array/2021/FRF-ocean_waves_8m-array_202110.nc",
    "family": "waves",
    "instrument": "8m-array",
    "month": "202110",
    "status": "offline_cache_miss",
    "detail": "FetchError"
  },
  {
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waves/waverider-26m/2021/FRF-ocean_waves_waverider-26m_202110.nc",
    "family": "waves",
    "instrument": "waverider-26m",
    "month": "202110",
    "status": "offline_cache_miss",
    "detail": "FetchError"
  },
  {
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waves/awac-11m/2021/FRF-ocean_waves_awac-11m_202110.nc",
    "family": "waves",
    "instrument": "awac-11m",
    "month": "202110",
    "status": "offline_cache_miss",
    "detail": "FetchError"
  },
  {
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/currents/awac-11m/2021/FRF-ocean_currents_awac-11m_202110.nc",
    "family": "currents",
    "instrument": "awac-11m",
    "month": "202110",
    "status": "offline_cache_miss",
    "detail": "FetchError"
  },
  {
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/meteorology/wind/derived/2021/FRF-met_wind_derived_202110.nc",
    "family": "wind",
    "instrument": "derived",
    "month": "202110",
    "status": "offline_cache_miss",
    "detail": "FetchError"
  },
  {
    "source": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waterlevel/eopNoaaTide/2021/FRF-ocean_waterlevel_eopNoaaTide_202110.nc",
    "family": "water_level",
    "instrument": "eopNoaaTide",
    "month": "202110",
    "status": "offline_cache_miss",
    "detail": "FetchError"
  }
]
```

Source metadata warnings: []

Search coverage: [{"family": "waves", "instrument_id": "FRF:waverider-17m", "required_months": ["202110"], "missing_or_unverified_months": ["202110"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "waves", "instrument_id": "FRF:awac-11m", "required_months": ["202110"], "missing_or_unverified_months": ["202110"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "waves", "instrument_id": "FRF:8m-array", "required_months": ["202110"], "missing_or_unverified_months": ["202110"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "waves", "instrument_id": "FRF:waverider-26m", "required_months": ["202110"], "missing_or_unverified_months": ["202110"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "currents", "instrument_id": "FRF:awac-11m", "required_months": ["202110"], "missing_or_unverified_months": ["202110"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "wind", "instrument_id": "FRF:derived", "required_months": ["202110"], "missing_or_unverified_months": ["202110"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "water_level", "instrument_id": "FRF:eopNoaaTide", "required_months": ["202110"], "missing_or_unverified_months": ["202110"], "status": "incomplete_search", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}]

Spectral states (missing is not calm): []

Duplicate timestamp diagnostics: []

Profiles/2D spectra, when present, are preserved in TENSORS.json with source definitions and masks. Ancillary meteorology/temperature only from selected products. NDBC/CDIP alias republication is not counted independently.

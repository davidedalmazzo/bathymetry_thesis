# FRF observational dossier: b1d1d660-87fc-5790-9275-8df4034e8d82

Timestamp: 2021-10-04T23:06:36.304000Z; semantics: catalogue ContentDate start/end; not local ROI sensing time

Catalogue footprint only; valid SAR support NOT VERIFIED. No SAR data read.

## A. Original measurements (independent per product/instrument)

| instrument | variable | value | units | offset s | status |
|---|---|---:|---|---:|---|
|FRF:waverider-17m|waveHs|0.6021346|m|-396.304|retrieved|
|FRF:waverider-17m|waveTp|10.471204|s|-396.304|retrieved|
|FRF:waverider-17m|waveMeanDirection|115.291695|degree|-396.304|retrieved|
|FRF:awac-11m|waveHs|0.59333867|m|-395.804|retrieved|
|FRF:awac-11m|waveTp|10.958904|s|-395.804|retrieved|
|FRF:awac-11m|waveMeanDirection|89.1157|degree|-395.804|retrieved|

Only rows with representative_eligible=True pass the configured QC and time policy; context never fills another instrument.

## B. Calculated quantities

WGS84 distances in DISTANCES.csv, signed offsets and previous/next/nearest QC association in ASSOCIATIONS.json. Spectral integrals are diagnostic, with missing-bin coverage and published-Hs difference. No directional reconstruction or SAR inversion.

## C. Assumptions

Configured temporal tolerances are operational, not universal physical limits. Historical nominal coordinates are conditioned on the dated source; conflicting deployment text remains in metadata. No interpolation, wave refraction or wind-height conversion. Depth datum is preserved, not assumed instantaneous water depth.

## D. Missing/conditional information

No joint state of the tile is asserted. Position is not automatically a measured GPS location. Unverified burst anchoring leaves interval bounds/distance unknown. Unflagged products are QC-unknown under the default strict policy. Survey point/line coverage is not inferred from a bounding box. Unsupported/unfetched families and network limits are listed below:

```json
[]
```

Source metadata warnings: []

Search coverage: [{"family": "waves", "instrument_id": "FRF:waverider-17m", "required_months": ["202110"], "missing_or_unverified_months": [], "status": "verified_configured_context", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}, {"family": "waves", "instrument_id": "FRF:awac-11m", "required_months": ["202110"], "missing_or_unverified_months": [], "status": "verified_configured_context", "nearest_claim": "nearest within available segments, not absolute deployment nearest"}]

Spectral states (missing is not calm): [{"instrument_id": "FRF:waverider-17m", "product": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waves/waverider-17m/2021/FRF-ocean_waves_waverider-17m_202110.nc", "status": "complete_spectrum", "Hm0_m": 0.6021345668303721, "valid_bin_fraction": 1.0}, {"instrument_id": "FRF:awac-11m", "product": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waves/awac-11m/2021/FRF-ocean_waves_awac-11m_202110.nc", "status": "complete_spectrum", "Hm0_m": 0.593338696348047, "valid_bin_fraction": 1.0}]

Duplicate timestamp diagnostics: []

Profiles/2D spectra, when present, are preserved in TENSORS.json with source definitions and masks. Ancillary meteorology/temperature only from selected products. NDBC/CDIP alias republication is not counted independently.

## Operational reading guide

`representative_eligible` is ONLY implemented availability/QC/time eligibility, NOT proof of physical representativity of footprint or ROI.

### Original measurements and per-sample distances

| instrument | parameter | original value/profile | units | UTC | offset s | QC/status | footprint min m | ROI min m |
|---|---|---|---|---|---:|---|---:|---:|
|FRF:waverider-17m|waveHs|0.6021346|m|2021-10-04T23:00:00.000003+00:00|-396.304|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveTp|10.471204|s|2021-10-04T23:00:00.000003+00:00|-396.304|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveTm|7.888412|s|2021-10-04T23:00:00.000003+00:00|-396.304|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveMeanDirection|115.291695|degree|2021-10-04T23:00:00.000003+00:00|-396.304|1.0: retrieved|0.0|None|
|FRF:waverider-17m|wavePeakDirectionPeakFrequency|90.0|degree|2021-10-04T23:00:00.000003+00:00|-396.304|1.0: retrieved|0.0|None|
|FRF:waverider-17m|directionalPeakSpread|27.809208|deg|2021-10-04T23:00:00.000003+00:00|-396.304|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveTm1|5.161339|s|2021-10-04T23:00:00.000003+00:00|-396.304|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveTm2|4.209098|s|2021-10-04T23:00:00.000003+00:00|-396.304|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveMeanDirectionPeakFrequency|86.02917|degree|2021-10-04T23:00:00.000003+00:00|-396.304|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveHs|0.59333867|m|2021-10-04T23:00:00.500001+00:00|-395.804|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveTp|10.958904|s|2021-10-04T23:00:00.500001+00:00|-395.804|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveTm|8.581391|s|2021-10-04T23:00:00.500001+00:00|-395.804|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveMeanDirection|89.1157|degree|2021-10-04T23:00:00.500001+00:00|-395.804|1.0: retrieved|0.0|None|
|FRF:awac-11m|wavePeakDirectionPeakFrequency|95.0|degree|2021-10-04T23:00:00.500001+00:00|-395.804|1.0: retrieved|0.0|None|
|FRF:awac-11m|directionalPeakSpread|23.839045|deg|2021-10-04T23:00:00.500001+00:00|-395.804|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveTm1|6.0348086|s|2021-10-04T23:00:00.500001+00:00|-395.804|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveTm2|4.8995466|s|2021-10-04T23:00:00.500001+00:00|-395.804|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveMeanDirectionPeakFrequency|93.16989|degree|2021-10-04T23:00:00.500001+00:00|-395.804|1.0: retrieved|0.0|None|

Nearest QC-eligible can be a different sample/gauge: OBSERVATIONS.csv references its own position_id in DISTANCES.csv. Previous/next/nearest selection remains in ASSOCIATIONS.json.

### Original height/depth/interval definitions

- FRF:waverider-17m / waves: original vertical context {"nominalDepth": {"value": 18.0, "attributes": {"_FillValue": -999.0, "units": "m", "description": "Nominal bottom vertical location from NAVD88", "long_name": "Bottom Elevation (NAVD88)", "short_name": "Bottom Elevation"}}, "gaugeDepth": {"value": 0.0, "attributes": {"_FillValue": -999.0, "units": "m", "long_name": "Sensor Depth Using Pressure, relative to mean water level", "short_name": "Gauge Depth", "_ChunkSizes": 10.0}}}; duration hint 1800 s; anchored interval None to None.
- FRF:awac-11m / waves: original vertical context {"nominalDepth": {"value": 11.3, "attributes": {"_FillValue": -999.0, "units": "m", "description": "Nominal bottom vertical location from NAVD88", "long_name": "Bottom Elevation (NAVD88)", "short_name": "Bottom Elevation"}}}; duration hint None s; anchored interval None to None.

Sensor elevation is not automatically wind height above instantaneous water. Profile depth/elevation and depth-integrated currents are distinct; no surface/effective-wave-current substitution.

### Derived diagnostic spectral quantities

- FRF:waverider-17m: complete_spectrum; Hm0=0.6021345668303721 m; Tp discrete-bin=10.81081081081081 s; Tm01=5.2617365161834995 s; Tm02=4.284071941859701 s; bin widths=reconstructed_midpoint_edges; these do not replace published parameters.
- FRF:awac-11m: complete_spectrum; Hm0=0.593338696348047 m; Tp discrete-bin=10.81081081081081 s; Tm01=6.079059773144507 s; Tm02=4.935621934283383 s; bin widths=reconstructed_midpoint_edges; these do not replace published parameters.

### Bathymetric references

[]

Filename dates/nominal bounding boxes do not prove measured survey coverage. Datum/method/unsupported layouts remain explicit. No depth inversion.

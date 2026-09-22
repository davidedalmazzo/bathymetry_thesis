# FRF observational dossier: c50e8065-702c-538b-b5d6-3e4399d68698

Timestamp: 2021-10-28T23:06:10.569000Z; semantics: catalogue ContentDate start/end; not local ROI sensing time

Catalogue footprint only; valid SAR support NOT VERIFIED. No SAR data read.

## A. Original measurements (independent per product/instrument)

| instrument | variable | value | units | offset s | status |
|---|---|---:|---|---:|---|
|FRF:waverider-17m|waveHs|1.7103801|m|-370.569|retrieved|
|FRF:waverider-17m|waveTp|11.396011|s|-370.569|retrieved|
|FRF:waverider-17m|waveMeanDirection|61.399113|degree|-370.569|retrieved|
|FRF:awac-11m|waveHs|1.717457|m|-370.069|retrieved|
|FRF:awac-11m|waveTp|10.869565|s|-370.069|retrieved|
|FRF:awac-11m|waveMeanDirection|69.948616|degree|-370.069|retrieved|

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

Spectral states (missing is not calm): []

Duplicate timestamp diagnostics: []

Profiles/2D spectra, when present, are preserved in TENSORS.json with source definitions and masks. Ancillary meteorology/temperature only from selected products. NDBC/CDIP alias republication is not counted independently.

## Operational reading guide

`representative_eligible` is ONLY implemented availability/QC/time eligibility, NOT proof of physical representativity of footprint or ROI.

### Original measurements and per-sample distances

| instrument | parameter | original value/profile | units | UTC | offset s | QC/status | footprint min m | ROI min m |
|---|---|---|---|---|---:|---|---:|---:|
|FRF:waverider-17m|waveHs|1.7103801|m|2021-10-28T23:00:00.000003+00:00|-370.569|1.0: retrieved|5428.047505918498|None|
|FRF:waverider-17m|waveTp|11.396011|s|2021-10-28T23:00:00.000003+00:00|-370.569|1.0: retrieved|5428.047505918498|None|
|FRF:waverider-17m|waveTm|8.398706|s|2021-10-28T23:00:00.000003+00:00|-370.569|1.0: retrieved|5428.047505918498|None|
|FRF:waverider-17m|waveTm1|6.55734|s|2021-10-28T23:00:00.000003+00:00|-370.569|1.0: retrieved|5428.047505918498|None|
|FRF:waverider-17m|waveTm2|5.681095|s|2021-10-28T23:00:00.000003+00:00|-370.569|1.0: retrieved|5428.047505918498|None|
|FRF:waverider-17m|wavePeakDirectionPeakFrequency|70.0|degree|2021-10-28T23:00:00.000003+00:00|-370.569|1.0: retrieved|5428.047505918498|None|
|FRF:waverider-17m|waveMeanDirection|61.399113|degree|2021-10-28T23:00:00.000003+00:00|-370.569|1.0: retrieved|5428.047505918498|None|
|FRF:waverider-17m|waveMeanDirectionPeakFrequency|66.34158|degree|2021-10-28T23:00:00.000003+00:00|-370.569|1.0: retrieved|5428.047505918498|None|
|FRF:waverider-17m|directionalPeakSpread|23.245344|deg|2021-10-28T23:00:00.000003+00:00|-370.569|1.0: retrieved|5428.047505918498|None|
|FRF:awac-11m|waveHs|1.717457|m|2021-10-28T23:00:00.500001+00:00|-370.069|1.0: retrieved|4684.735179763001|None|
|FRF:awac-11m|waveTp|10.869565|s|2021-10-28T23:00:00.500001+00:00|-370.069|1.0: retrieved|4684.735179763001|None|
|FRF:awac-11m|waveTm|8.675288|s|2021-10-28T23:00:00.500001+00:00|-370.069|1.0: retrieved|4684.735179763001|None|
|FRF:awac-11m|waveTm1|6.816343|s|2021-10-28T23:00:00.500001+00:00|-370.069|1.0: retrieved|4684.735179763001|None|
|FRF:awac-11m|waveTm2|5.8528523|s|2021-10-28T23:00:00.500001+00:00|-370.069|1.0: retrieved|4684.735179763001|None|
|FRF:awac-11m|wavePeakDirectionPeakFrequency|70.0|degree|2021-10-28T23:00:00.500001+00:00|-370.069|1.0: retrieved|4684.735179763001|None|
|FRF:awac-11m|waveMeanDirection|69.948616|degree|2021-10-28T23:00:00.500001+00:00|-370.069|1.0: retrieved|4684.735179763001|None|
|FRF:awac-11m|waveMeanDirectionPeakFrequency|66.40836|degree|2021-10-28T23:00:00.500001+00:00|-370.069|1.0: retrieved|4684.735179763001|None|
|FRF:awac-11m|directionalPeakSpread|24.212297|deg|2021-10-28T23:00:00.500001+00:00|-370.069|1.0: retrieved|4684.735179763001|None|

Nearest QC-eligible can be a different sample/gauge: OBSERVATIONS.csv references its own position_id in DISTANCES.csv. Previous/next/nearest selection remains in ASSOCIATIONS.json.

### Original height/depth/interval definitions

- FRF:waverider-17m / waves: original vertical context {"nominalDepth": {"value": 18.0, "attributes": {"_FillValue": -999.0, "units": "m", "description": "Nominal bottom vertical location from NAVD88", "long_name": "Bottom Elevation (NAVD88)", "short_name": "Bottom Elevation"}}, "gaugeDepth": {"value": 0.0, "attributes": {"_FillValue": -999.0, "units": "m", "long_name": "Sensor Depth Using Pressure, relative to mean water level", "short_name": "Gauge Depth", "_ChunkSizes": 10.0}}}; duration hint 1800 s; anchored interval None to None.
- FRF:awac-11m / waves: original vertical context {"nominalDepth": {"value": 11.3, "attributes": {"_FillValue": -999.0, "units": "m", "description": "Nominal bottom vertical location from NAVD88", "long_name": "Bottom Elevation (NAVD88)", "short_name": "Bottom Elevation"}}}; duration hint None s; anchored interval None to None.

Sensor elevation is not automatically wind height above instantaneous water. Profile depth/elevation and depth-integrated currents are distinct; no surface/effective-wave-current substitution.

### Derived diagnostic spectral quantities


### Bathymetric references

[]

Filename dates/nominal bounding boxes do not prove measured survey coverage. Datum/method/unsupported layouts remain explicit. No depth inversion.

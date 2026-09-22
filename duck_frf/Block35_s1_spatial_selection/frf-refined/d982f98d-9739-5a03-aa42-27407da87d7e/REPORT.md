# FRF observational dossier: d982f98d-9739-5a03-aa42-27407da87d7e

Timestamp: 2021-10-11T22:58:06.126000Z; semantics: catalogue ContentDate start/end; not local ROI sensing time

Catalogue footprint only; valid SAR support NOT VERIFIED. No SAR data read.

## A. Original measurements (independent per product/instrument)

| instrument | variable | value | units | offset s | status |
|---|---|---:|---|---:|---|
|FRF:waverider-17m|waveHs|2.110663|m|113.874|retrieved|
|FRF:waverider-17m|waveTp|8.826125|s|113.874|retrieved|
|FRF:waverider-17m|waveMeanDirection|45.960007|degree|113.874|retrieved|
|FRF:awac-11m|waveHs|1.858859|m|114.374|retrieved|
|FRF:awac-11m|waveTp|8.96861|s|114.374|retrieved|
|FRF:awac-11m|waveMeanDirection|66.01153|degree|114.374|retrieved|

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

Spectral states (missing is not calm): [{"instrument_id": "FRF:waverider-17m", "product": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waves/waverider-17m/2021/FRF-ocean_waves_waverider-17m_202110.nc", "status": "complete_spectrum", "Hm0_m": 2.1106629509800943, "valid_bin_fraction": 1.0}, {"instrument_id": "FRF:awac-11m", "product": "https://chldata.erdc.dren.mil/thredds/dodsC/frf/oceanography/waves/awac-11m/2021/FRF-ocean_waves_awac-11m_202110.nc", "status": "complete_spectrum", "Hm0_m": 1.8588589316997672, "valid_bin_fraction": 1.0}]

Duplicate timestamp diagnostics: []

Profiles/2D spectra, when present, are preserved in TENSORS.json with source definitions and masks. Ancillary meteorology/temperature only from selected products. NDBC/CDIP alias republication is not counted independently.

## Operational reading guide

`representative_eligible` is ONLY implemented availability/QC/time eligibility, NOT proof of physical representativity of footprint or ROI.

### Original measurements and per-sample distances

| instrument | parameter | original value/profile | units | UTC | offset s | QC/status | footprint min m | ROI min m |
|---|---|---|---|---|---:|---|---:|---:|
|FRF:waverider-17m|waveHs|2.110663|m|2021-10-11T23:00:00.000003+00:00|113.874|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveTp|8.826125|s|2021-10-11T23:00:00.000003+00:00|113.874|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveTm|6.6751733|s|2021-10-11T23:00:00.000003+00:00|113.874|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveMeanDirection|45.960007|degree|2021-10-11T23:00:00.000003+00:00|113.874|1.0: retrieved|0.0|None|
|FRF:waverider-17m|wavePeakDirectionPeakFrequency|65.0|degree|2021-10-11T23:00:00.000003+00:00|113.874|1.0: retrieved|0.0|None|
|FRF:waverider-17m|directionalPeakSpread|26.64921|deg|2021-10-11T23:00:00.000003+00:00|113.874|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveTm1|5.6654754|s|2021-10-11T23:00:00.000003+00:00|113.874|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveTm2|5.1713176|s|2021-10-11T23:00:00.000003+00:00|113.874|1.0: retrieved|0.0|None|
|FRF:waverider-17m|waveMeanDirectionPeakFrequency|71.96895|degree|2021-10-11T23:00:00.000003+00:00|113.874|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveHs|1.858859|m|2021-10-11T23:00:00.500001+00:00|114.374|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveTp|8.96861|s|2021-10-11T23:00:00.500001+00:00|114.374|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveTm|6.5867643|s|2021-10-11T23:00:00.500001+00:00|114.374|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveMeanDirection|66.01153|degree|2021-10-11T23:00:00.500001+00:00|114.374|1.0: retrieved|0.0|None|
|FRF:awac-11m|wavePeakDirectionPeakFrequency|80.0|degree|2021-10-11T23:00:00.500001+00:00|114.374|1.0: retrieved|0.0|None|
|FRF:awac-11m|directionalPeakSpread|24.352789|deg|2021-10-11T23:00:00.500001+00:00|114.374|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveTm1|5.5951834|s|2021-10-11T23:00:00.500001+00:00|114.374|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveTm2|5.126592|s|2021-10-11T23:00:00.500001+00:00|114.374|1.0: retrieved|0.0|None|
|FRF:awac-11m|waveMeanDirectionPeakFrequency|78.81856|degree|2021-10-11T23:00:00.500001+00:00|114.374|1.0: retrieved|0.0|None|

Nearest QC-eligible can be a different sample/gauge: OBSERVATIONS.csv references its own position_id in DISTANCES.csv. Previous/next/nearest selection remains in ASSOCIATIONS.json.

### Original height/depth/interval definitions

- FRF:waverider-17m / waves: original vertical context {"nominalDepth": {"value": 18.0, "attributes": {"_FillValue": -999.0, "units": "m", "description": "Nominal bottom vertical location from NAVD88", "long_name": "Bottom Elevation (NAVD88)", "short_name": "Bottom Elevation"}}, "gaugeDepth": {"value": 0.0, "attributes": {"_FillValue": -999.0, "units": "m", "long_name": "Sensor Depth Using Pressure, relative to mean water level", "short_name": "Gauge Depth", "_ChunkSizes": 10.0}}}; duration hint 1800 s; anchored interval None to None.
- FRF:awac-11m / waves: original vertical context {"nominalDepth": {"value": 11.3, "attributes": {"_FillValue": -999.0, "units": "m", "description": "Nominal bottom vertical location from NAVD88", "long_name": "Bottom Elevation (NAVD88)", "short_name": "Bottom Elevation"}}}; duration hint None s; anchored interval None to None.

Sensor elevation is not automatically wind height above instantaneous water. Profile depth/elevation and depth-integrated currents are distinct; no surface/effective-wave-current substitution.

### Derived diagnostic spectral quantities

- FRF:waverider-17m: complete_spectrum; Hm0=2.1106629509800943 m; Tp discrete-bin=8.695652173913043 s; Tm01=5.7352659277089435 s; Tm02=5.23103441440267 s; bin widths=reconstructed_midpoint_edges; these do not replace published parameters.
- FRF:awac-11m: complete_spectrum; Hm0=1.8588589316997672 m; Tp discrete-bin=9.30232558139535 s; Tm01=5.603509114506307 s; Tm02=5.1345685487159995 s; bin widths=reconstructed_midpoint_edges; these do not replace published parameters.

### Bathymetric references

[]

Filename dates/nominal bounding boxes do not prove measured survey coverage. Datum/method/unsupported layouts remain explicit. No depth inversion.

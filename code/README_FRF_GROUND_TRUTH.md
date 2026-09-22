# Ground truth for a SAR acquisition at Duck — `frf_ground_truth.py`

One command, linked modules, no scene-specific config files:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe code\frf_ground_truth.py --timestamp-utc 2021-10-28T23:06:39Z `
    --bbox -75.79 36.15 -75.70 36.22 --out outputs\ground_truth_20211028 `
    --acquisition-id s1a_20211028_duck --tranche gt_20211028 --new-tranche
```

| piece | module | source |
|---|---|---|
| waves (spectra, Hm0, Tp, direction), currents, wind, water level | existing FRF client (`run_block32_frf_client.py`) | FRF THREDDS (WR17, WR26, AWAC 11 m, 8 m array, eopNoaaTide) |
| gridded survey DEM nearest in time (≤ `--dem-max-days`) | `frf_client/dem.py` | FRF THREDDS `geomorphology/DEMs/surveyDEM` (x 50–950 m, y −100–1100 m) |
| topobathy for the whole bbox | `coastal_dem.py` (generic, US) | NOAA NCEI CUDEM 1/9″, NAVD88; bbox window read by HTTP range |
| merge + event depth | `frf_ground_truth.py` | FRF DEM where present, CUDEM elsewhere; depth = water level − bed |

Outputs in `--out`: `GROUND_TRUTH.json`, `bathymetry_merged_utm.tif` (bands: bed
elevation NAVD88, source, event depth), `cudem_bbox_navd88.tif` (+ provenance),
`frf_survey_dem.npz`, `frf_observations/` (full FRF dossier), `bathymetry_merged.png`.

FRF network use needs a named tranche and a budget file (`examples/frf/budget_ground_truth.json`).

Caveats: eopNoaaTide is NOAA preliminary data (no NOAA QC) and excludes wave
setup; AWAC currents are near-bed/profile averages at 11 m, not the surface current
seen by SAR; CUDEM mixes survey years (at Duck, FRF DEM − CUDEM median +0.09 m,
p10/p90 −0.84/+0.84 m in the overlap, i.e. bar migration).


## Legacy grids and empirical accuracy (2026-09-22)

`--legacy-grid PATH|URL.zip,OFFSET,LABEL,YEAR` adds older gridded surveys. OFFSET brings
their datum to NAVD88 (use the nearest NOAA tide-station datums). A constant bias is
then estimated against modern data (FRF survey + recent non-interpolated BlueTopo) in
the overlap deeper than 9 m and removed; the residual NMAD becomes its uncertainty.
Band 8 of `bathymetry_merged_utm.tif` holds this *empirical* uncertainty for every
cell; `forward_lambda_check.py` certifies on it. Duck example:

```
--legacy-grid https://pubs.usgs.gov/of/2011/1015/data/bathymetry/innershelf/nhatt.zip,-0.128,nhatt,2001
--legacy-grid https://pubs.usgs.gov/of/2011/1015/data/bathymetry/nearshore/vims_2002.zip,-0.623,vims_2002,2002
```

## Water-level policy (2026-09-22)

`--water-level-policy qc_only` (default) uses the measured water level for band 3 only
if it passed QC *and* is `representative_eligible`; otherwise band 3 is the still-water
depth on the NAVD88 datum (`-bed`) and `GROUND_TRUTH.json` / `MERGE_REPORT.json` record
`event_water_level_status` with the value that was rejected. At Duck on 2021-10-28 the
FRF `eopNoaaTide` reading (+0.235 m, 39 s from the acquisition) is NOAA *preliminary*
data with `status = qc_unknown`, so it is not applied: +0.235 m (plus unmodelled wave
setup) belongs in the error budget instead. `--water-level-policy preliminary` restores
the old behaviour. `rebuild_merged_bathymetry.py` re-runs the merge of an existing
output directory offline (no FRF budget spent) when this logic changes.

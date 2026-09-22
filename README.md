# SAR ocean-wave kinematics for coastal bathymetry — analysis pipeline

Scientific Python project investigating whether the **temporal** wave quantity —
the angular frequency `omega` — can be recovered from the SAR data itself, from
the phase of a cross-spectrum between two time-separated looks of the same sea.

**The route is not fixed.** Two families of candidates are open, and this
repository must not declare either as chosen:

- **sub-aperture splitting** of a long-dwell spotlight acquisition (Umbra,
  TerraSAR-X Staring Spotlight, COSMO-SkyMed CSG Spotlight-2A): the look
  separation is chosen, up to about 0.65 of the dwell;
- **inter-burst overlap** in TOPS (Sentinel-1 IW): the separation is fixed by
  instrument timing, of order seconds, on an open archive, but the overlap phase
  also carries the systematic term that spectral diversity uses for
  co-registration, and over water there is no static reference for it.

umbra/Vandenberg (Umbra) is the development and debug scene, and the folder name is
historical: from Block 30 onward the candidate scenes are TerraSAR-X,
COSMO-SkyMed and Sentinel-1 over the USACE Field Research Facility at Duck, NC.

## Repository scope

The Duck spatial-validation screening is now in
[Block35](duck_frf/Block35_s1_spatial_selection/REPORT.md): a real public CDSE
October 2021 search and FRF spectral/survey comparison, with a **conditional**
first IW SLC choice. It does not select/exclude the temporal routes above or
validate phase retrieval. No SAR download/inversion was performed. Stable
commands and limitations are in [README_S1_SPATIAL](code/README_S1_SPATIAL.md).

This repository contains source code, tests, metadata summaries, lightweight numerical results, plots and checkpoints. It intentionally does **not** contain the original CPHD/SICD/GEC products, large complex arrays, bathymetric rasters, NetCDF files, virtual environments or credentials.

The local raw products remain read-only and must never be committed:

- Umbra CPHD: approximately 140 GB;
- Umbra SICD: approximately 11.5 GB;
- derived complex `.npy` arrays: approximately 5 GB.

## Reproducible environment

The active project environment is `.venv-umbra-thesis`, created from the general Miniconda Python 3.13 interpreter and isolated from system site packages. The retired `sdb-iride` environment must not be used.

```powershell
C:\Users\ASUS\miniconda3\python.exe -m venv .venv-umbra-thesis
.\.venv-umbra-thesis\Scripts\python.exe -m pip install -r requirements-thesis.txt
.\.venv-umbra-thesis\Scripts\python.exe -m pytest -q
```

The verified suite at `CHECKPOINT_10` contains 57 passing tests, including SarPy-dependent tests.

## Structure

The Git repository stays at `D:\Dati Tesi\Umbra` (historical root name).
Its contents are now grouped by function: `umbra/` for Umbra scenes,
validation and scene selection; `duck_frf/` for Duck/CSK/TSX/FRF blocks;
`docs/` for guides and `docs/checkpoints/` for root-level checkpoints;
`scripts/` for maintenance; `code/`, `tests/`, `examples/` remain shared.
See [layout and migration](docs/REPOSITORY_LAYOUT.md).
Frozen block files retain their original contents: legacy paths are resolved
using `repository_paths.json`, not edited in old manifests.

- `code/umbra_sar/`: reusable metadata-aware SAR and wave-analysis library;
- `code/analyze_block*.py`: reproducible analysis entry points;
- `tests/`: synthetic, convention and artifact-regression tests;
- `umbra/Vandenberg/metadata/`: SICD/CPHD metadata summaries and Doppler-to-time mapping;
- `umbra/Vandenberg/results/analysis_block*/`: lightweight scientific outputs and checkpoints;
- `umbra/validazione/Block8_validation/`: validation-scene screening and buoy matching;
- `umbra/validazione/Block9_validation/`, `umbra/validazione/Block10_validation/`: synthetic and physical forward-model validation;
- `CHECKPOINT_*.md`, `WORKLOG.md`: chronological decisions and frozen results.

## Frozen conventions and quantities

- SICD processed-aperture duration and CPHD available slow time are distinct quantities.
- `Col.Sgn = -1` FFT/IFFT, Doppler-band order and cross-spectrum sign conventions are covered by numerical tests.
- Cross-spectrum convention: `F_secondary * conj(F_reference)`.
- The umbra/Vandenberg SAR-only value `T_SAR = 17.902230457 s` is frozen and must not be tuned to external buoy data.
- Raw radar files are read-only; do not run large downloads or dwell sweeps without an explicit task.

Sentinel-1 Duck pipeline (Blocks 35–38), scripts and results: [docs/S1_DUCK_PIPELINE.md](docs/S1_DUCK_PIPELINE.md). Note: the Block37 spatial result is superseded by a geolocation fix ([docs/NOTE_S1_GEOLOCATION_BURST_TIME.md](docs/NOTE_S1_GEOLOCATION_BURST_TIME.md)).

Start with [AGENTS.md](AGENTS.md), [TASK_SPEC.md](TASK_SPEC.md) and the checkpoints in numerical order. The implemented client and checkpoints extend through Block34; migration verification is recorded separately under `docs/reorganization/`.
The Duck Sentinel-1 work now extends through the first real spatial trial in
[Block37](docs/checkpoints/CHECKPOINT_37.md). The selected full SLC was
integrity-verified and bounded IW3/VV reads found a stable primary intensity
lobe, with explicit interpolation sensitivity and only a conditional
dispersion comparison. This does not select the sub-aperture or TOPS temporal
route and is not bathymetric validation.

## Operational FRF observational client (Blocks32–34)

The mission-independent Duck/FRF client accepts strict GeoJSON/CSV acquisition
inputs and offers inventory, limited fetch and offline dossier modes. It
preserves per-instrument QC, temporal association, historical-position uncertainty
and source spectra/profiles without reading radar data. See
[client documentation](code/README_FRF_CLIENT.md) and
[operational quickstart](docs/FRF_QUICKSTART.md) and
[Block34 checkpoint](docs/checkpoints/CHECKPOINT_34.md). Stable entry point:
`code/frf_client_cli.py`; the historical Block32 command remains available.
Named persistent network tranches are separate from reusable configuration,
acquisition inputs, verified payload cache and output directories. Missing
products remain explicitly incomplete, not automatically substituted.
Blocks33/34 were published in commit `691d44f`; the subsequent directory
migration remains a local change until a separately authorized commit/push.
Their isolated source-copy test is not called a clean GitHub clone.

## Data and licensing

Radar and third-party oceanographic/geospatial datasets retain their original providers' terms and are not redistributed here. No open-source license has yet been assigned to the thesis code; repository access alone does not grant reuse rights.

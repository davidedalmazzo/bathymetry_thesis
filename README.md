# Umbra SAR ocean-wave sub-aperture thesis project

Scientific Python project for investigating whether temporal ocean-wave information can be recovered from Umbra spotlight SAR sub-apertures and inter-look intensity cross-spectra. Vandenberg is the development/debug scene; separate open-ocean scenes are screened for validation.

## Repository scope

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

- `code/umbra_sar/`: reusable metadata-aware SAR and wave-analysis library;
- `code/analyze_block*.py`: reproducible analysis entry points;
- `tests/`: synthetic, convention and artifact-regression tests;
- `Vandenberg/metadata/`: SICD/CPHD metadata summaries and Doppler-to-time mapping;
- `Vandenberg/results/analysis_block*/`: lightweight scientific outputs and checkpoints;
- `Block8_validation/`: validation-scene screening and buoy matching;
- `Block9_validation/`, `Block10_validation/`: synthetic and physical forward-model validation;
- `CHECKPOINT_*.md`, `WORKLOG.md`: chronological decisions and frozen results.

## Frozen conventions and quantities

- SICD processed-aperture duration and CPHD available slow time are distinct quantities.
- `Col.Sgn = -1` FFT/IFFT, Doppler-band order and cross-spectrum sign conventions are covered by numerical tests.
- Cross-spectrum convention: `F_secondary * conj(F_reference)`.
- The Vandenberg SAR-only value `T_SAR = 17.902230457 s` is frozen and must not be tuned to external buoy data.
- Raw radar files are read-only; do not run large downloads or dwell sweeps without an explicit task.

Start with [AGENTS.md](AGENTS.md), [TASK_SPEC.md](TASK_SPEC.md) and the checkpoints in numerical order. The most recent implemented scripts currently extend through Block 14, while formal checkpoint reports are present through Block 12.

## Data and licensing

Radar and third-party oceanographic/geospatial datasets retain their original providers' terms and are not redistributed here. No open-source license has yet been assigned to the thesis code; repository access alone does not grant reuse rights.


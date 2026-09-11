# Agent operating instructions

## Purpose

This is a scientific thesis repository for Umbra SAR ocean-wave sub-aperture and cross-spectrum analysis. Preserve physical sign conventions, metadata provenance, frozen results and uncertainty reporting.

## Required reading order

1. `README.md`
2. `TASK_SPEC.md`
3. `WORKLOG.md`
4. `CHECKPOINT_1.md` through the latest checkpoint
5. the relevant `code/README_*.md` and result manifest for the requested block

## Runtime

- Work only inside the repository root.
- Use `.venv-umbra-thesis/Scripts/python.exe` on Windows.
- Never use the retired `sdb-iride` environment.
- Install only from `requirements-thesis.txt` into the project-local environment.

## Data safety

- CPHD, SICD, GEC, complex arrays and raster/NetCDF source products are intentionally absent from Git.
- Treat any locally available radar source product as read-only.
- Never commit secrets, downloaded radar data, virtual environments, caches or generated multi-GB intermediates.
- Do not initiate large downloads, a dwell sweep or a bathymetric inversion unless the user explicitly requests it.

## Scientific invariants

- Keep processed SICD aperture duration separate from CPHD available dwell/slow time.
- Use cross-spectrum convention `F_secondary * conj(F_reference)`.
- Do not infer FFT/IFFT or phase signs only from metadata; preserve the numerical convention tests.
- Keep `T_SAR = 17.902230457 s` and frozen Blocks/shortlists unchanged unless an explicit new task supersedes them.
- Never tune synthetic truth or model coefficients to force agreement with Vandenberg or external buoy data.
- State clearly when a model is an intensity-domain approximation rather than a raw phase-history SAR simulator.

## Before committing changes

Run:

```powershell
.\.venv-umbra-thesis\Scripts\python.exe -m pytest -q
git status --short
```

Inspect every newly tracked file and ensure no file exceeds GitHub's 100 MB per-file limit.


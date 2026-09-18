# Agent operating instructions

## Purpose

This is a scientific thesis repository for recovering ocean-wave angular frequency `omega` from SAR data and inverting it for coastal bathymetry. Preserve physical sign conventions, metadata provenance, frozen results and uncertainty reporting.

**The method is not decided.** Sub-aperture splitting of long-dwell spotlight acquisitions and inter-burst overlap in TOPS are both open candidates, and so are combinations of the two. Do not write, in code, documentation or reports, that the project has adopted one of them. State the objective and describe the alternatives.

The folder is named `Umbra` for historical reasons; the work is sensor-independent from Block 30 onward.

## Required reading order

1. `README.md`
2. `TASK_SPEC.md`
3. `WORKLOG.md`
4. `docs/checkpoints/CHECKPOINT_1.md` through the latest checkpoint (remaining checkpoints are inside their original block directories)
5. the relevant `code/README_*.md` and result manifest for the requested block

## Runtime

- Work only inside the repository root.
- The native layout is `umbra/`, `duck_frf/`, `docs/`, `code/`, `tests/`, `scripts/`. Resolve historical manifest paths with `repository_paths.json` / `code/repository_paths.py`; never rewrite frozen manifests solely to change locations.
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

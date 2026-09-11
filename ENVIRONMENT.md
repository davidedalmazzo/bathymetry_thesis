# Reproducible environment

Updated on 2026-09-11 (Europe/Rome).

## Filesystem and runtime

- Workspace: `D:\Dati Tesi\Umbra`
- Dedicated Python: `D:\Dati Tesi\Umbra\.venv-umbra-thesis\Scripts\python.exe`
- Python: 3.13.9 (Anaconda build, 64 bit)
- Base interpreter: `C:\Users\ASUS\miniconda3\python.exe`
- `include-system-site-packages`: `false`
- `TEMP`: `D:\Dati Tesi\Umbra\_tmp`
- `TMP`: `D:\Dati Tesi\Umbra\_tmp`
- `PIP_CACHE_DIR`: `D:\Dati Tesi\Umbra\_cache\pip`
- D: total size at initial checkpoint: 1,000,169,668,608 bytes
- D: free space at initial checkpoint: 700,395,421,696 bytes (652.294 GiB)

The environment is project-specific and was created from the general Miniconda
interpreter. It does not use the retired `sdb-iride` environment. Packages are
installed only inside `.venv-umbra-thesis`.

## Scientific packages

| Package | Version |
|---|---:|
| NumPy | 2.5.2 |
| SciPy | 1.18.1 |
| SarPy | 2.0.1 |
| Matplotlib | 3.11.1 |
| h5py | 3.16.0 |
| lxml | 6.1.2 |
| sarkit | 1.10.1 |
| pytest | 9.1.1 |

The exact dependency snapshot is in `requirements-thesis.txt`. No global package
installation was performed.

## Invocation pattern

Before running Python or pip, use:

```powershell
$env:TEMP='D:\Dati Tesi\Umbra\_tmp'
$env:TMP='D:\Dati Tesi\Umbra\_tmp'
$env:PIP_CACHE_DIR='D:\Dati Tesi\Umbra\_cache\pip'
& 'D:\Dati Tesi\Umbra\.venv-umbra-thesis\Scripts\python.exe' -B ...
```

`-B` prevents Python bytecode cache files outside controlled execution paths.

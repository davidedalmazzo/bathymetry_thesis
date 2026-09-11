# Running the synthetic validation

From `D:\Dati Tesi\Umbra`:

```powershell
$env:TEMP='D:\Dati Tesi\Umbra\_tmp'
$env:TMP='D:\Dati Tesi\Umbra\_tmp'
& '.venv\Scripts\python.exe' -B -m pytest -vv
& '.venv\Scripts\python.exe' -B tests\generate_test_report.py
```

The first command performs the assertions. The second independently calculates
and threshold-checks the published metrics, then rewrites `TEST_METRICS.json`
and `TEST_REPORT.md`.

The tests do not require or download the full SICD.


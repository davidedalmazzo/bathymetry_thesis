@echo off
REM Block 13 - supporto allargato a 3 km verso il largo + test di shoaling.
REM Durata attesa 60-75 minuti. Legge 140 GB dal CPHD.
REM Il bordo a riva resta dov'era; il centro e' spostato 780 m verso il largo.
cd /d "%~dp0code"
set PY="%~dp0.venv\Scripts\python.exe"
if not exist %PY% set PY=python
%PY% -u form_block12_backprojection.py form ^
  --center-easting-m 714742.85 --center-northing-m 3827489.45 ^
  --length-parallel-m 3000 --length-perpendicular-m 650 ^
  --spacing-m 5.0 --look-count 32 --delay-window-m 2400 ^
  --outdir "%~dp0Vandenberg\results\block13_backprojection"
echo.
echo === analisi a finestra scorrevole ===
%PY% -u analyze_block13_sliding.py
pause

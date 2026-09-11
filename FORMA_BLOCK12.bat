@echo off
REM Block 12 - formazione dei sub-look per retroproiezione dalla fase grezza CPHD.
REM Durata attesa 35-50 minuti. Legge 140 GB dal CPHD, scrive ~30 MB.
cd /d "%~dp0code"
set PY="%~dp0.venv\Scripts\python.exe"
if not exist %PY% set PY=python
%PY% -u form_block12_backprojection.py form --spacing-m 5.0 --length-parallel-m 1440 --length-perpendicular-m 650 --look-count 32
echo.
echo === analisi ===
%PY% -u analyze_block12_phase_slope.py
pause

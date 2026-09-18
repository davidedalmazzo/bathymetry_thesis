@echo off
REM Block 12 - formazione dei sub-look per retroproiezione dalla fase grezza CPHD.
REM Durata attesa 35-50 minuti. Legge 140 GB dal CPHD, scrive ~30 MB.
setlocal
for %%I in ("%~dp0..\..") do set "THESIS_ROOT=%%~fI"
cd /d "%THESIS_ROOT%"
set "THESIS_PY=%THESIS_ROOT%\.venv-umbra-thesis\Scripts\python.exe"
if not exist "%THESIS_PY%" exit /b 1
"%THESIS_PY%" -u code\form_block12_backprojection.py form --spacing-m 5.0 --length-parallel-m 1440 --length-perpendicular-m 650 --look-count 32
echo.
echo === analisi ===
"%THESIS_PY%" -u code\analyze_block12_phase_slope.py
pause

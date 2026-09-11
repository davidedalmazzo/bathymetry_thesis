@echo off
setlocal
set "OUTDIR=D:\Dati Tesi\Umbra\Vandenberg"
set "BASE=2025-02-16-18-55-44_UMBRA-10"
set "PREFIX=https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/sar-data/task-data/f2f8c71e-6aec-4358-acda-93c5e68e8b4b/2025-02-16-18-55-44_UMBRA-10"

if not exist "%OUTDIR%" mkdir "%OUTDIR%"
cd /d "%OUTDIR%"

echo.
echo === Download SICD Vandenberg ===
echo Cartella: %CD%
echo Il download e' riprendibile: se si interrompe, rilancia questo .bat.
echo.

curl.exe -L -C - --retry 10 --retry-all-errors -o "%BASE%_SICD.nitf" "%PREFIX%/%BASE%_SICD.nitf"
if errorlevel 1 (
  echo.
  echo ERRORE nel download SICD. Il file parziale viene lasciato per il resume.
  exit /b 1
)

echo.
echo === Download metadata STAC ===
curl.exe -L --retry 5 --retry-all-errors -o "%BASE%.stac.v2.json" "%PREFIX%/%BASE%.stac.v2.json"

echo.
echo === File presenti ===
dir "%BASE%_SICD.nitf" "%BASE%.stac.v2.json"
echo.
echo Download terminato.
endlocal

@echo off
REM Pushes Block 17 + Block 18 + docs to GitHub from this machine,
REM where your git credentials live. Review, then run once.
setlocal
cd /d "D:\Dati Tesi\Umbra"

echo === current state ===
git status --short
echo.
echo === staging Block 17 / Block 18 / code / tests / docs / WORKLOG ===
git add Block17_selector_consolidation
git add Block18_reference_recovery
git add docs
git add code
git add tests
git add WORKLOG.md
git add Block16_scene_selection
git add Vandenberg/results/analysis_block16
echo.
echo === what will be committed ===
git status --short
echo.
pause
git commit -F "D:\Dati Tesi\Umbra\COMMIT_MSG_BLOCK17_18.txt"
git push origin main
echo.
echo === done ===
git log --oneline -3
pause

# Runs the full pipeline: SQLite load -> SQL -> cleaning/EDA -> RFM/cohort/stats -> Excel -> regression -> pivots -> PowerPoint
# Usage:  powershell -ExecutionPolicy Bypass -File .\run_all.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

$steps = "01_load_to_sqlite.py", "02_run_sql.py", "03_clean_eda.py", "04_rfm_cohort_stats.py", "05_build_excel.py", "06_regression.py", "07_excel_pivots.py", "08_build_ppt.py"
foreach ($step in $steps) {
    Write-Host "`n########## $step ##########" -ForegroundColor Cyan
    python "scripts\$step"
    if ($LASTEXITCODE -ne 0) { throw "$step failed" }
}
Write-Host "`nDone. Open outputs\insights_summary.txt for the numbers." -ForegroundColor Green

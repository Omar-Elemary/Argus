# Lint and run the test suite (hermetic - no RPC needed).
Set-Location $PSScriptRoot\..
ruff check backend/app backend/tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest backend/tests
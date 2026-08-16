# Run the Argus backend in development mode (auto-reload).
Set-Location (Join-Path $PSScriptRoot "..\backend")
$env:PYTHONPATH = "."
$HOST_ADDR = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$PORT = if ($env:PORT) { $env:PORT } else { "8000" }
& uvicorn app.main:app --host $HOST_ADDR --port $PORT --reload
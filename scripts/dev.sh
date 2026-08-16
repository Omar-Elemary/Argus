#!/usr/bin/env bash
# Run the Argus backend in development mode (auto-reload).
set -euo pipefail
cd "$(dirname "$0")/../backend"
export PYTHONPATH="."
exec uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}" --reload
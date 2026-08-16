#!/usr/bin/env bash
# Lint and run the test suite (hermetic - no RPC needed).
set -euo pipefail
cd "$(dirname "$0")/.."
ruff check backend/app backend/tests
python -m pytest backend/tests
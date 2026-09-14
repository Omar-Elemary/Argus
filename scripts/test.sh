#!/usr/bin/env bash
# Lint and run the backend test suite.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m ruff check backend/app backend/tests
python3 -m pytest backend/tests

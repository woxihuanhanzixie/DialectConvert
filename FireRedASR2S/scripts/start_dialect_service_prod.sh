#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
export PYTHON_BIN="${PYTHON_BIN:-python3}"
export DIALECT_SERVICE_HOST="${DIALECT_SERVICE_HOST:-127.0.0.1}"
export DIALECT_SERVICE_PORT="${DIALECT_SERVICE_PORT:-8002}"

cd "${PROJECT_ROOT}"
exec "${PYTHON_BIN}" -m uvicorn dialect_service.app:app --host "${DIALECT_SERVICE_HOST}" --port "${DIALECT_SERVICE_PORT}"

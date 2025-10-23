#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"

if [[ ! -f "${PROJECT_ROOT}/.venv/bin/activate" ]]; then
  echo "error: .venv not found. Run ./scripts/rebuild_env.sh first." >&2
  exit 1
fi

export PYTHONNOUSERSITE=1
source "${PROJECT_ROOT}/.venv/bin/activate"

if [[ $# -gt 0 ]]; then
  exec "$@"
else
  exec "${SHELL:-/bin/bash}"
fi

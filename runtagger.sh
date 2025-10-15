#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
UVICORN_ARGS=("app.main:app" "--host" "0.0.0.0" "--port" "7860" "--reload")

if [[ ! -d "$VENV_DIR" ]]; then
    echo "Virtualenv not found at $VENV_DIR. Run 'python -m venv .venv' and install deps first." >&2
    exit 1
fi

source "$VENV_DIR/bin/activate"

if [[ ${#} -gt 0 ]]; then
    UVICORN_ARGS+=("$@")
fi

exec uvicorn "${UVICORN_ARGS[@]}"

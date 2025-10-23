#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3.10}"
VENV_DIR="${ROOT_DIR}/.venv"

export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"
export APP_ROOT="${ROOT_DIR}"
export PYTHONNOUSERSITE=1

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

bootstrap_python() {
    if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
        echo "[env] Creating virtual environment at ${VENV_DIR}"
        "${PYTHON_BIN}" -m venv "${VENV_DIR}"
    fi

    # shellcheck disable=SC1090
    source "${VENV_DIR}/bin/activate"
    export PYTHONNOUSERSITE=1

    if ! python -m pip show photo-tagger >/dev/null 2>&1; then
        echo "[env] Installing project dependencies (editable + dev extras)..."
        python -m pip install --upgrade pip setuptools wheel
        python -m pip install -e ".[dev]"
    elif ! python -m pip show uvicorn >/dev/null 2>&1; then
        echo "[env] Installing uvicorn dependency..."
        python -m pip install uvicorn[standard]
    fi
}

bootstrap_frontend() {
    (
        cd frontend
        npm config set audit false >/dev/null 2>&1 || true
        local lockfile="package-lock.json"
        if [[ ! -d node_modules ]] || [[ -f "${lockfile}" && "${lockfile}" -nt node_modules ]]; then
            echo "[env] Installing frontend dependencies..."
            npm install --no-progress
        fi
    )
}

ensure_port() {
    local port="$1"
    if lsof -Pi "tcp:${port}" -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "[start-tagger] Port ${port} is in use. Attempting graceful shutdown of existing process..."
        lsof -Pi "tcp:${port}" -sTCP:LISTEN -t | xargs -r kill -TERM
        sleep 1
        if lsof -Pi "tcp:${port}" -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "[start-tagger] Port ${port} is still in use after SIGTERM. Sending SIGKILL."
            lsof -Pi "tcp:${port}" -sTCP:LISTEN -t | xargs -r kill -KILL
            sleep 1
        fi
        if lsof -Pi "tcp:${port}" -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "[start-tagger] Unable to free port ${port}. Please choose a different port or stop the conflicting service." >&2
            exit 1
        fi
    fi
}

ensure_port "${API_PORT}"
ensure_port "${FRONTEND_PORT}"

bootstrap_python
bootstrap_frontend

trap_handler() {
    echo "\n[start-tagger] Shutting down..."
    [[ -n "${API_PID:-}" ]] && kill "${API_PID}" 2>/dev/null || true
    [[ -n "${WEB_PID:-}" ]] && kill "${WEB_PID}" 2>/dev/null || true
    wait
}

trap trap_handler INT TERM EXIT

echo "[start] API on http://${API_HOST}:${API_PORT}  ROOT=${ROOT_DIR}"
uvicorn backend.api.index:app \
    --host "${API_HOST}" \
    --port "${API_PORT}" \
    --reload \
    --log-level info \
    --app-dir "${ROOT_DIR}" \
    --reload-dir backend \
    --reload-dir app \
    > backend.log 2>&1 &
API_PID=$!

export VITE_API_BASE="http://${API_HOST}:${API_PORT}"

echo "[start] Waiting for backend..."
for i in {1..50}; do
    if curl -fsS "http://${API_HOST}:${API_PORT}/api/health" >/dev/null; then
        echo "[start] Backend is up."
        break
    fi
    sleep 0.2
done
echo "[start] PYTHONPATH=${PYTHONPATH}"
echo "[start] Routes: $(curl -fsS "http://${API_HOST}:${API_PORT}/api/routes" || echo 'n/a')"

echo "[frontend] Starting Vite dev server on http://127.0.0.1:${FRONTEND_PORT}"
(
    cd frontend
    npm run dev -- --host 127.0.0.1 --port "${FRONTEND_PORT}"
) &
WEB_PID=$!

wait "$API_PID" "$WEB_PID"

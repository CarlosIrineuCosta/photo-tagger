#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[start-all] launching API/backend via start-tagger.sh"
"${ROOT_DIR}/start-tagger.sh" &
API_PID=$!

echo "[start-all] launching frontend dev server"
(
  cd "${ROOT_DIR}/frontend"
  npm run dev
) &
FRONTEND_PID=$!

trap 'echo "[start-all] stopping services"; kill ${API_PID} ${FRONTEND_PID} 2>/dev/null || true' INT TERM

wait "${API_PID}" "${FRONTEND_PID}"

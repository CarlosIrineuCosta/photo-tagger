#!/usr/bin/env bash
set -euo pipefail

# Ensure a display is available (WSLg / local X11 sessions usually set this already).
export DISPLAY="${DISPLAY:-:0}"

exec python scripts/capture_screenshots.py --feature gallery_status --auto

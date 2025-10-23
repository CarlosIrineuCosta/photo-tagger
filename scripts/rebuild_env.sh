#!/usr/bin/env bash
set -euo pipefail

# Recreate a clean virtual environment and install Photo Tagger dev deps.

python -m venv .venv
source .venv/bin/activate

export PYTHONNOUSERSITE=1

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .[dev]

echo "Environment rebuilt. Activate with: source .venv/bin/activate (remember PYTHONNOUSERSITE=1)"

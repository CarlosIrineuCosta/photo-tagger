# Repository Guidelines

## Project Structure & Module Organization
The pipeline lives in `app/`, with step-specific modules such as `scanner.py`, `proxy.py`, `embed.py`, `cluster.py`, and the FastAPI/Gradio entry point (`main.py`, `ui.py`). Configuration templates in `config/` should be copied per deployment, while support utilities sit in `scripts/` (notably `medoid_batch.py` and `smoke_test.py`). Tests and synthetic fixtures reside in `tests/`, and generated caches stay outside the repo by pointing `runtime.cache_root` at fast local storage.

## Build, Test, and Development Commands
- `python -m pip install -e .[dev]` — install the package and tooling in an activated Python 3.11 environment.
- `uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload` — run the Gradio UI with live reload for development.
- `pytest` — execute the unit suite configured in `pyproject.toml`.
- `python scripts/smoke_test.py --wipe` — run the synthetic end-to-end pipeline; add `--write` to test XMP output.
- `python scripts/medoid_batch.py --openai` — batch-tag medoids without the UI; omit `--openai` to stay offline.

## Coding Style & Naming Conventions
Target Python 3.11 with 4-space indentation, type hints, and explicit imports (e.g., `from app import store`). Format with `black` and `isort`, then lint with `ruff` before pushing. Modules and functions follow `snake_case`, classes use `PascalCase`, and constants or environment variables stay `UPPER_SNAKE_CASE`.

## Testing Guidelines
Unit tests live in `tests/test_*.py`; keep new files aligned with that pattern and use descriptive function names. Run `pytest` locally prior to commits, and re-run the smoke test whenever changes touch ingestion, embedding, clustering, or XMP writing. Place new fixtures under `tests/smoke/` and avoid committing large binary assets.

## Commit & Pull Request Guidelines
Write concise, present-tense commit subjects that describe the impact (e.g., `Improve cluster warm-start heuristics`). When a change spans multiple stages, call out the primary module in the subject or body. Pull requests should summarize behavior shifts, list configuration/schema updates, and attach screenshots or CLI output for UI or logging changes. Link related issues and flag follow-up risks to help reviewers plan next work.

## Configuration & Data Safety
Do not commit populated configs; copy `config/config.example.yaml` to `config/config.yaml` locally and inject secrets such as `OPENAI_API_KEY` via the environment. Confirm `runtime.cache_root` points to scratch storage before running smoke tests to avoid polluting production shares. Treat Samba mounts as read-only inputs and review people-tagging policy flags when enabling Vision or OCR features.

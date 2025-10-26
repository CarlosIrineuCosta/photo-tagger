# Repository Guidelines

## Project Structure & Module Organization
The pipeline lives in `app/` with the following modular structure:
- `app/core/` — Core processing modules (clip_model.py, export.py, labels.py, medoid.py, scan.py, score.py, thumbs.py)
- `app/cli/` — Command-line interface (tagger.py with all CLI subcommands)
- `app/util/` — Utility helpers (monitor_vram.py, review_table.py)
- `backend/api/` — FastAPI bridge used by the React frontend
- `frontend/` — Vite + React + Shadcn UI

Configuration is managed via `config.yaml` in the project root. Run artifacts are stored in `runs/` with timestamped directories. Thumbnail cache lives in `thumb_cache/`.

## Build, Test, and Development Commands
- `python -m pip install -e .[dev]` — install the package and tooling in an activated Python 3.11 environment.
- `./start-tagger.sh` — launch FastAPI + Vite for the interactive React UI.
- `python -m app.cli.tagger run --root /path/to/photos` — execute the complete pipeline via CLI.
- `pytest` — execute the unit suite configured in `pyproject.toml`.

## Coding Style & Naming Conventions
Target Python 3.11 with 4-space indentation, type hints, and explicit imports (e.g., `from app.core import scan`). Format with `black` and `isort`, then lint with `ruff` before pushing. Modules and functions follow `snake_case`, classes use `PascalCase`, and constants or environment variables stay `UPPER_SNAKE_CASE`.

## Testing Guidelines
Unit tests live in `tests/test_*.py`; keep new files aligned with that pattern and use descriptive function names. Run `pytest` locally prior to commits. Place new fixtures under `tests/smoke/` and avoid committing large binary assets.

## Commit & Pull Request Guidelines
Write concise, present-tense commit subjects that describe the impact (e.g., `Improve CLIP embedding caching`). When a change spans multiple stages, call out the primary module in the subject or body. Pull requests should summarize behavior shifts, list configuration/schema updates, and attach screenshots or CLI output for UI or logging changes. Link related issues and flag follow-up risks to help reviewers plan next work.

## Configuration & Data Safety
Do not commit populated configs; use `config.yaml` as the primary configuration file. Inject secrets such as `OPENAI_API_KEY` via the environment if needed. Confirm `run_dir` points to scratch storage before running tests to avoid polluting production shares. Treat photo directories as read-only inputs.
- Confirm with the operator before making changes—they may flip the repo into read-only mode to review plans before execution.

## Agent Guidance

- Default to UI-first solutions. Do not propose CLI-based fixes or workflows unless explicitly requested by the operator or in an urgent recovery scenario.
- Coordinate with the GLM and Gemini assistants: for every working session, document actionable tasks for Codex, GLM, and Gemini in `docs/ongoing.md` before execution, keeping assignments current until project completion.

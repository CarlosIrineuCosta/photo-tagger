# Initial Setup

This guide replaces the legacy Streamlit + Gradio instructions with the current React frontend and FastAPI backend workflow. Keep `docs/project_map.md` and `docs/ongoing.md` handy while onboarding—they stay in sync with day-to-day development and supersede any previous setup checklists. (The historical plan lives in `docs/archive/ui-refactor.md`.)

---

## Architecture Snapshot

- **Back end:** `backend/api/index.py` exposes FastAPI routes that call into the stable processing modules under `app/core/`. Never edit the `app/core/` logic when working on UI tasks.
- **Front end:** `/frontend` hosts the React + Vite + Shadcn/UI app. It consumes JSON from the FastAPI bridge and mirrors the layout described in the UI refactor docs.
- **Pipeline runtime:** CLI entry points under `app/cli/` run the full scan → embed → cluster → tag pipeline and populate artifacts in `runs/` and `thumb_cache/`.
- **Configuration:** `config/config.yaml` (copied from `config/config.example.yaml`) controls roots, cache directories, and model choices. Controlled vocabulary lives beside it.

---

## Prerequisites

- Linux or macOS with Python 3.11
- Node.js 20 LTS (Vite 7 requires Node ≥ 18.18; 20.x is recommended)
- CUDA-capable GPU (optional but recommended) with NVIDIA drivers + `nvidia-smi`
- System packages: `exiftool`, `libraw` (for `rawpy` wheels), optional `tesseract-ocr`

> Tip: Install GPU drivers before the Python environment so PyTorch picks up CUDA support automatically.

---

## 1. Clone and Create a Python Environment

```bash
git clone git@github.com:your-org/photo-tagger.git
cd photo-tagger
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

---

## 2. Install Python Dependencies

Install the package in editable mode with the common extras (add or remove extras as needed for your workstation):

```bash
pip install -e .[dev,raw,people,vision]
```

- `raw` enables RAW proxy generation with `rawpy`.
- `people` adds torchvision models used by person/nude heuristics.
- `vision` installs the OpenAI client for Vision tagging; omit if you do not plan to call the API.
- `dev` pulls in `black`, `isort`, `ruff`, and `pytest`.

Run `pytest` once to confirm the virtualenv is wired correctly:

```bash
pytest
```

---

## 3. Install Frontend Tooling

```bash
cd frontend
npm install
cd ..
```

- Use `npm run dev` for standalone frontend work.
- Keep `npm run build` and `npm run lint` passing before opening a pull request.

---

## 4. Configure the Pipeline

Copy the sample configuration files and adjust paths:

```bash
cp config/config.example.yaml config/config.yaml
cp config/ck_vocab.example.yaml config/ck_vocab.yaml
```

Key fields in `config/config.yaml`:

- `root`: photo library root (read-only).
- `run_dir`: run artifacts (`runs/<timestamp>/`); defaults to the repo `runs/` folder.
- `thumb_cache`: thumbnail cache directory; defaults to `thumb_cache/`.
- `ck_tagging.vocab_file`: path to the controlled vocabulary YAML.
- `ai_tagging.use_openai_vision`: toggle OpenAI Vision for medoid tagging.
- `runtime.reuse_cache`: keep `true` to reuse embeddings and thumbnails between runs.

Update `config/config.yaml` whenever you add new photo roots or change cache locations. The FastAPI backend reads this file on startup.

---

## 5. Start the Full Dev Stack

The `start-tagger.sh` helper launches FastAPI (with auto-reload) and the Vite development server in parallel.

```bash
chmod +x start-tagger.sh
./start-tagger.sh
```

What happens:

- Sets `PYTHONPATH` so FastAPI can import `app.core`.
- Starts `uvicorn backend.api.index:app` on `http://127.0.0.1:8010`.
- Boots the Vite dev server on `http://127.0.0.1:5173` after the API health-check passes.
- Streams backend logs into `backend.log`.

Visit `http://127.0.0.1:5173` to use the React UI. The frontend reads gallery data, config, and export actions through the FastAPI routes documented in `docs/ui-refactor.md`.

To stop the stack, press `Ctrl+C`; the script cleans up both processes.

---

## 6. Run the Pipeline Manually (Optional)

You can run the CLI end-to-end without touching the UI:

```bash
python -m app.cli.tagger run --root /path/to/photos
```

- Outputs live under `runs/<timestamp>/`.
- Thumbnails and medoid previews land in `thumb_cache/` (configurable).
- Review the generated CSV and XMP sidecars before exporting to your photo library.

Refer to `app/cli/tagger.py` for additional subcommands (`scan`, `embed`, `cluster`, etc.) when you need to re-run individual stages.

---

## 7. Linting, Formatting, and Tests

- `ruff check` — project-wide lint pass (runs via `python -m ruff check`).
- `black .` and `isort .` — format Python files.
- `pytest` — backend/unit tests.
- `npm run lint` — frontend ESLint.
- `npm run build` — verifies the production build for the React app.

CI expects all of the above to pass before merging. Run them locally to avoid surprises.

---

## 8. Troubleshooting Cheatsheet

- **FastAPI cannot import `app.core`:** ensure `start-tagger.sh` is executed from the repo root or export `PYTHONPATH=$(pwd)`.
- **Frontend shows empty gallery:** confirm the backend can read `config/config.yaml` and that `runs/` contains recent artifacts. Use `/api/diag` for quick backend diagnostics.
- **Slow embedding on GPU:** check `nvidia-smi` for stale processes before running the pipeline; adjust `embeddings.batch_size` in `config/config.yaml` if VRAM is constrained.
- **OpenAI Vision errors:** set `OPENAI_API_KEY` in your shell before launching the stack or disable Vision in the config.

---

## 9. Reference Materials

- `docs/project_map.md` — module-by-module overview of the backend and legacy touch points.
- `docs/ongoing.md` — current backlog and follow-up tasks for the React + FastAPI stack (the original plan is archived under `docs/archive/ui-refactor.md`).
- `Photo-Tagger Documentation.md` — broader context, decisions, and terminology.

Keep `initial_setup.md` up to date whenever the UI refactor phases advance (e.g., when Streamlit artifacts are removed or new API routes land). Once Phase 2 completes, refresh this doc to capture the Docker and QA changes.

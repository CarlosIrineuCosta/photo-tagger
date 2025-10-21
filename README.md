# photo-tag-pipeline (MVP)

Pipeline for indexing RAW/JPEG photos, generating 1024px proxies, embedding with OpenCLIP, clustering by time windows, tagging medoids with CK/AI layers, reviewing in the React UI, and writing keywords to XMP sidecars.

## Prerequisites

- Python 3.11 (virtualenv or conda)
- GPU recommended (CUDA for PyTorch/OpenCLIP); CPU fallback supported but slower
- System dependencies: `exiftool`, `tesseract-ocr` (optional OCR), libraw (included via `rawpy` wheels)

Example setup (conda):

```bash
conda create -n photo python=3.11 -y
conda activate photo
pip install .
sudo apt install exiftool
```

> Optional: install `tesseract-ocr` later if you decide to enable OCR tagging.

## Configuration

Copy and edit the example files:

```bash
cp config/config.example.yaml config/config.yaml
cp config/ck_vocab.example.yaml config/ck_vocab.yaml
```

Important keys:

- `roots`: Samba-mounted photo folders (read-only).
- `runtime.cache_root`: cache location (defaults to `/home/cdc/Storage/SSD500/photo-tag-cache`).
- `ck_tagging.vocab_file`: controlled vocabulary YAML.
- `ai_tagging.city_whitelist`: proper nouns Vision may emit.
- `people_policy.allow_openai_on_people_sets`: keep nude/person sets local by default.
- `people_policy.treat_people_sets_as_nude`: when true, person clusters suppress `CK:hand` and default to local-only tagging unless toggled in the UI.
- `runtime.reuse_cache`: keep as `true` to reuse existing parquet/proxy outputs on later runs; set to `false` for full rebuilds.

## Pipeline steps

1. **Scan** – crawl roots, hash files, collect EXIF, resolve capture date.
2. **Proxies** – render/sRGB RAWs to 1024px JPEG proxies, compute luminance stats.
3. **Embeddings** – OpenCLIP ViT-L/14 embeddings (GPU recommended).
4. **Cluster** – time-window grouping + HDBSCAN/threshold clustering; pick medoids.
5. **Tag medoids** – CK tags (controlled vocab + heuristics) and AI tags (BLIP + CLIP + optional OpenAI Vision).
6. **Audit/Review** – inspect the React gallery before enabling writes.
7. **Write XMP** – append CK/AI keywords via `exiftool` (sidecars only).

## Running

Interactive UI + API:

```bash
./start-tagger.sh
# FastAPI → http://127.0.0.1:8010
# React UI → http://127.0.0.1:5173
```

The gallery pulls live data from `/api/gallery`, kicks off the full pipeline via **Process images**, and lets you review/save/export tags in place.

CLI pipeline (headless):

```bash
python scripts/medoid_batch.py --openai   # optional --openai for Vision on medoids
```

### Incremental reruns

With `runtime.reuse_cache` left enabled, rerunning steps 1–4 will reuse existing parquet caches (`index`, `proxies`, `embeds`, `clusters`) when present, keeping medoid tagging quick for iterative reviews. Set that flag to `false` (or delete cache files) when you need a full rebuild after adding new folders.

### First-run checklist

1. Mount your Samba shares (e.g., `/mnt/photos/E`, `/mnt/photos/F`) read-only on the Linux box.
2. Copy `config/config.example.yaml` → `config/config.yaml` and edit `roots`, city list, and CK vocabulary.
3. Ensure `runtime.cache_root` points to fast local storage (`/home/cdc/Storage/SSD500/photo-tag-cache`).
4. Run the React UI with `./start-tagger.sh`, open http://127.0.0.1:5173, and process a smoke run to confirm connectivity.
5. Export the audit CSV from the React UI (Status strip shows the run id) if you need an offline log of proposed tags.
6. Use the gallery filters (Only unapproved / Hide after save) to spot-check clusters before writing XMP sidecars.

### Using the UI

1. Set the photo root, labels source (`labels`), and output folder in the Config screen, then save.
2. Click **Process images** to run the full CLI pipeline. The Status strip logs success with the run id.
3. Toggle label chips in the gallery to approve/reject CK/AI suggestions. Use **Save approved** to persist, **Export ▾** for CSV/sidecars, and the filters to focus on remaining work.

### Smoke test

Run the bundled smoke test to exercise the pipeline on synthetic data:

```bash
source .venv/bin/activate
python scripts/smoke_test.py --wipe
```

Add `--write` to perform real XMP writes (otherwise a dry-run summary is printed). Synthetic images and caches live under `tests/smoke/`.

## Notes

- People detection uses torchvision Faster R-CNN; falls back to "no-person" if model unavailable.
- Treat person clusters as nude-sensitive when `people_policy.treat_people_sets_as_nude` is true; this suppresses `CK:hand` and disables Vision unless you flip the toggle.
- OCR hooks exist but default to disabled; enable in `config.yaml` if `tesseract-ocr` is installed.
- All caches/parquet/proxies live under `runtime.cache_root`, not `/data`.
- `OPENAI_API_KEY` must be set in the environment to enable Vision calls.

## Next steps / TODO

- Implement robust nude detection for `CK:hand` suppression and Vision gating.
- Add progress reporting and error surfacing in the UI.
- Harden HDBSCAN fallback for small batches.

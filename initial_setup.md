# Taxonomy system fix

**User:** Carlos (carlos.irineu@gmail.com)

**Created:** 9/27/2025 18:24:32

**Updated:** 9/28/2025 0:29:11

**Exported:** 9/28/2025 2:00:00

**Link:** [https://chatgpt.com/c/68d8560e-d0a4-8332-8d18-78e92873be98](https://chatgpt.com/c/68d8560e-d0a4-8332-8d18-78e92873be98)

## 2025-09-28 GPU + embedding tweaks

- `nvidia-smi` now only shows the desktop stack (`Xorg`, `gnome-shell`); the stray `uvicorn` PID 399591 is gone, but keep checking between runs in case VRAM sticks again.
- Dropped `embeddings.batch_size` to 8 in `config/config.yaml` after yesterday's CUDA OOM; leave `device: "cuda"` so we can step back up once the GPU is stable.
- Before relaunching the stack, rerun `nvidia-smi` and kill any rogue process so OpenCLIP has the full 3060 Ti; otherwise expect another OOM even at low batch sizes.
- Next run checklist: activate the venv, launch uvicorn with the Gradio app, click pipeline buttons 1→5, then run Review & Write in dry-run before attempting Vision retries.



Got it. Here’s a complete, hand-off spec you can paste into VS Code and tell Codex to build. It’s Linux-first, web UI (Gradio), Dockerized, GPU-ready, cluster-then-classify, two tag layers (**CK:** controlled, **AI:** freeform), XMP-only writes, and _no_ Tkinter.

    * *

      Project: **photo-tag-pipeline**

      ===

      Goals

      -----
    * Crawl one or more roots, index images, build 1024px proxies.
    * Embed → cluster → pick medoids.
    * Tag in two layers:
        - **CK:** your controlled vocabulary (short, stable).
        - **AI:** freeform suggestions (vehicles, monuments, moods, materials, “blue glass / Murano”, etc.).
    * Optional OpenAI Vision call **only on medoids** (skippable for nude sets).
    * Write tags to **XMP** using `exiftool` (never touch RAWs).
    * Review UI to apply/override tags **per cluster**.
    * Heuristics to avoid “studio black background = night”.
    * Caching at every step (restarts are cheap).
        * *

          Stack

          -----
        * **Python 3.11**
        * **PyTorch + CUDA**, **open-clip-torch** (ViT-L/14 by default)
        * **HDBSCAN** (or cosine threshold) for clustering
        * **rawpy** for RAW proxies
        * **exiftool** for metadata I/O
        * **Gradio** UI (served via **FastAPI** mount for future API)
        * **SQLite** + **Parquet** cache (duckdb or sqlite+parquet is fine)
        * Docker: `nvidia/cuda:12.2.0-cudnn8-runtime-ubuntu22.04`
            * *

              Directory layout

              ----------------

              ```
              photo-tag-pipeline/
                docker/
                  Dockerfile
                  docker-compose.yml
                app/
                  __init__.py
                  config.py
                  main.py            # FastAPI + Gradio mounting
                  ui.py              # Gradio components
                  scanner.py         # crawl & EXIF inventory
                  proxy.py           # RAW->proxy builder (rawpy)
                  embed.py           # OpenCLIP embeddings
                  cluster.py         # time-window grouping + HDBSCAN
                  tag_ck.py          # controlled-vocab tagging (CK)
                  tag_ai.py          # freeform AI tags (CLIP caption & optional OpenAI Vision)
                  write_xmp.py       # exiftool writer, prefix logic
                  heuristics.py      # studio/night, people/nude toggles, city whitelist
                  store.py           # sqlite/parquet caches, hashes
                  jobs.py            # pipeline orchestration
                  utils.py
                models/
                  # downloaded OpenCLIP weights cache (mounted volume)
                config/
                  config.example.yaml
                  ck_vocab.example.yaml
                data/
                  # caches: proxies/, embeds.parquet, clusters.parquet, tags.parquet, audit.csv
                README.md
              ```
                * *

                  Config (YAML)

                  -------------

                  `config/config.example.yaml`

                  ```yaml

                  roots:
                * "/mnt/photos/E"
                * "/mnt/photos/F"

proxy:

  max_size: 1024      # long edge

  jpeg_quality: 90

  cache_dir: "data/proxies"

index:

  include_ext: [".jpg",".jpeg",".tif",".tiff",".png",".dng",".cr2",".cr3",".nef",".arw",".orf",".rw2"]

  exclude_regex: ["^\\._", "thumbs?"]

  follow_symlinks: false

embeddings:

  model: "ViT-L-14"          # open-clip

  pretrained: "openai"

  batch_size: 128

  device: "cuda"

clustering:

  method: "hdbscan"          # or "threshold"

  min_cluster_size: 6

  min_samples: 2

  cosine_threshold: 0.14     # used if method=="threshold"

  time_window_minutes: 60    # group by capture-time before clustering to keep shoots coherent

ai_tagging:

  use_openai_vision: true

  openai_model: "gpt-4o-mini"   # economical, good enough for places/OCR

  max_ai_tags: 12

  city_whitelist: ["Rio de Janeiro","Paris","São Paulo","Petropolis","Teresopolis","Florence","Marseille","New York", "Lisbon","Venice","Milan"]

  allow_nude_sets_to_call_openai: false  # default false; Vision can refuse nude content

  prompt_extra_concepts: ["car","monument","statue","bridge","cathedral","glass","blue glass","Murano glass","sunny day","overcast","rain","reflection","graffiti","industrial","construction","museum","market","seaside","mountain pass","snow","fog","long exposure","bokeh","macro"]

ck_tagging:

  vocab_file: "config/ck_vocab.yaml"

  max_ck_tags: 10

xmp:

  prefix_ck: "CK:"

  prefix_ai: "AI:"

  write_concurrency: 4

review:

  enable: true

  default_apply_to_cluster: true

  audit_csv: "data/audit.csv"

heuristics:

  studio_black_vs_night:

    enable: true

    iso_threshold: 800

    face_required_for_studio: true

    dark_ratio: 0.65       # %pixels < 0.08 luminance

runtime:

  workers: 2

  cache_db: "data/index.sqlite"

```

`config/ck_vocab.example.yaml`

```yaml
subjects:
  - flower
  - mountain
  - moon
  - building
  - machine
  - night
  - dawn
  - macro
  - beach
  - forest
  - street
  - skyline
people_concepts:
  - abstract
  - profile
  - frontal
  - bodyscape
  - hands
  - face
  - hair:blonde
  - hair:brunette
  - outdoor
  - studio
  - black-background
gear:
  - Pentax67
  - C65
places_coarse:
  - Rio
  - Jardim Botanico
  - Paris
  - Venice
  - Florence
  - Marseille
```

You’ll curate **CK** over time. Keep it short; you’ll always have **AI** for discovery.

    * *

      Pipeline logic

      --------------

      ### 0) Hash & index
    * Walk roots; keep rows in SQLite: `{id, path, sha1, bytes, width, height, make, model, capture_time, iso, fnumber, exposure, lens, keywords_existing}`
    * Hash on **file bytes**; skip if already seen.

### 1) Proxies

* RAW → sRGB JPEG 1024px long edge via `rawpy`; others use Pillow.
* Store at `data/proxies/<sha1>.jpg`.
* Store median luminance and dark-pixel ratio for heuristics.

### 2) Embeddings

* OpenCLIP ViT-L/14 on proxies (resize per model).
* Save to Parquet: `embeds.parquet` with columns `{id, sha1, clip: float[dim]}`.
* Optional pHash for near-duplicate culling.

### 3) Time-window grouping

* Sort by `capture_time`; break into windows of `time_window_minutes`.
* Cluster **within** each window to avoid cross-shoot mixing.

### 4) Clustering

* HDBSCAN on normalized embeddings (metric cosine) per window.
* For threshold mode: single-linkage over cosine distances, split by `cosine_threshold`.
* For each cluster: pick **medoid** (min sum distance) and store.

### 5) Heuristics

* **Studio black vs Night**:
    - If `dark_ratio ≥ 0.65` **and** detected person **and** `ISO ≤ 800` **and** shutter within typical studio band (`1/30..1/200`) ⇒ tag candidate `CK:studio` and `CK:black-background`; suppress `CK:night`.
    - Otherwise normal day/night inferences.
* **Nude / people sets**:
    - Run a lean person detector (TorchVision Faster-RCNN or YOLOv8n).
    - If person torso area present and skin-tone coverage high, mark **“people set”**; when `allow_nude_sets_to_call_openai=false` ⇒ **skip Vision** and rely on CLIP + BLIP captioning locally.
    - People-concept CK rules fire only on people sets.

### 6) Tagging (two layers)

**6a) CK layer** (controlled)

* Zero-shot with CLIP: for each CK label, score `cosine(emb, text_emb("a photo of {label}"))`; keep top-K above threshold.
* Add deterministic rules:
    - Place coarse from `city_whitelist` using CLIP score against `"a photo in {city}"`.
    - Gear from EXIF (Pentax67, C65) becomes CK tags.
    - Heuristics decide `studio`, `black-background`, suppress `night`.

**6b) AI layer** (freeform)

* Local first:
    - BLIP/BLIP2 or SigLIP caption to seed concepts.
    - Query CLIP with a larger concept bank (from `prompt_extra_concepts` plus mined nouns from caption).
* Optional OpenAI Vision on **cluster medoids only**:
    - Prompt includes **your city whitelist** and instructions to return **compact JSON** of short lowercase tags, no duplicates, capped at `max_ai_tags`.
    - If nude sets and `allow_nude_sets_to_call_openai=false`, skip (Vision may refuse).

**Tag format**

* Prefix **CK:** and **AI:** before writing.
* Keep **existing keywords**; never delete, only add.

### 7) Review & apply

* Gradio grid: each cluster shows **medoid**, CK/AI tag chips (toggle), “Apply to cluster” checkbox (default on).
* Accept → writes tags for all cluster members.
* `audit.csv` logs `{path, added_ck, added_ai, source(model), timestamp}`.

### 8) Write XMP

* `exiftool` with `-overwrite_original` and sidecar mapping for RAW.
* Concurrency cap from config.
    * *

      OpenAI Vision note (nudes)

      --------------------------

      For artistic nudity, Vision **can** refuse or sanitize outputs depending on model safety. If you need guaranteed uncensored tagging for your nude sets, keep those **local only** (CLIP + BLIP) and set `allow_nude_sets_to_call_openai: false`. You can still run Vision on cities/architecture shoots.
        * *

          API & UI

          --------

          ### Endpoints (FastAPI)
        * `POST /scan` `{roots}` → starts index + proxy
        * `POST /embed` → embeddings
        * `POST /cluster` → clusters
        * `POST /tag/ck` → CK layer for medoids/all
        * `POST /tag/ai` → AI layer (local or OpenAI)
        * `POST /write` → XMP for selected ids
        * `GET /status` → progress/state
        * `GET /clusters` → paginated cluster summaries

### Gradio panels

1. **Config** (load/save YAML); pick roots; pick city list.
2. **Run** (Scan → Proxies → Embeds → Cluster) with progress bars.
3. **Review**: grid of medoids; tag chips; **Apply to cluster**.
4. **Write**: progress + link to `audit.csv`.
5. **Search**: regex over tags to spot-check.

    * *

      Docker

      ------

      `docker/Dockerfile`

      ```dockerfile
      FROM nvidia/cuda:12.2.0-cudnn8-runtime-ubuntu22.04

      ENV DEBIAN_FRONTEND=noninteractive
      RUN apt-get update && apt-get install -y --no-install-recommends \
          python3.11 python3.11-venv python3-pip git curl ca-certificates \
          libglib2.0-0 libgl1 exiftool ffmpeg \
          && rm -rf /var/lib/apt/lists/*

      WORKDIR /app
      COPY app/ /app/app/
      COPY config/ /app/config/
      COPY README.md /app/
      RUN python3.11 -m pip install --upgrade pip

      # Torch CUDA (adjust to your CUDA)
      RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
      RUN pip install rawpy pillow hdbscan scikit-learn duckdb pandas pyarrow tqdm pydantic fastapi uvicorn[standard] gradio open-clip-torch==2.24.0

      ENV HF_HOME=/app/models
      EXPOSE 7860
      CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","7860"]
      ```

      `docker/docker-compose.yml`

      ```yaml

      version: "3.8"

      services:

        photo:

          build: ./docker

          image: photo-tag-pipeline:latest

          environment:
    * OPENAI_API_KEY=${OPENAI_API_KEY}

    ports: ["7860:7860"]

    deploy:

      resources:

        reservations:

          devices:

- capabilities: [gpu]

    volumes:

- ../app:/app/app
- ../config:/app/config
- ../data:/app/data
- /mnt/photos/E:/photos/E:ro
- /mnt/photos/F:/photos/F:ro
- ../models:/app/models

    runtime: nvidia

```

> If your photos live on a Windows box, mount the SMB share on Linux and bind that path into the container read-only:
>
> ```
> sudo mount -t cifs //WINBOX/PHOTO_E /mnt/photos/E -o username=...,uid=$(id -u),gid=$(id -g),ro
> ```

* * *

Core modules (sketch)
---------------------

`app/scanner.py`

```python
def crawl(roots, include_ext, exclude_regex) -> list[dict]:
    # returns rows with path, sha1, size, mtime, exif fields
```

`app/proxy.py`

```python
def build_proxy(path, out_path, max_edge=1024, quality=90) -> dict:
    # returns stats: width,height,median_luma,dark_ratio
```

`app/embed.py`

```python
class ClipEmbedder:
    def __init__(...): ...
    def encode_paths(self, proxy_paths: list[str]) -> np.ndarray
```

`app/cluster.py`

```python
def cluster_window(embeds: np.ndarray, ids: list[int], method, **kwargs) -> list[list[int]]:
    # returns list of clusters (list of ids)
def medoid(embeds, cluster_ids) -> int:
    # index of medoid
```

`app/tag_ck.py`

```python
def ck_tags_for_image(embed, exif, heuristics, vocab, k=10) -> list[str]:
    # returns ["CK:flower","CK:studio","CK:Rio",...]
```

`app/tag_ai.py`

```python
def ai_tags_local(proxy_path, extra_bank, k=12) -> list[str]:
    # BLIP caption -> mined nouns/adjectives -> CLIP scoring
def ai_tags_openai(proxy_path, city_whitelist, k=12) -> list[str]:
    # calls 4o-mini with a strict JSON schema; graceful fallback on error
```

`app/heuristics.py`

```python
def studio_black_vs_night(exif, dark_ratio, has_person) -> dict:
    # returns flags to add/remove tags
def person_present(proxy_path) -> bool:
    # lightweight detector
```

`app/write_xmp.py`

```python
def write_keywords(paths: list[str], keywords: list[list[str]], prefix_ck, prefix_ai, workers=4):
    # batched exiftool calls; ensure RAW => sidecar; keep existing
```

`app/ui.py`

```python
def build_ui(app_state):
    # Gradio Blocks: config loader/saver, run buttons, cluster review grid,
    # tag toggles, apply-to-cluster checkbox, write XMP button
```

`app/jobs.py`

```python
class Pipeline:
    def run_scan(self): ...
    def run_proxies(self): ...
    def run_embed(self): ...
    def run_cluster(self): ...
    def run_tag_ck(self): ...
    def run_tag_ai(self, use_openai): ...
    def run_write(self, selection): ...
```

`app/main.py`

```python
from fastapi import FastAPI
import gradio as gr
app = FastAPI()
# mount gradio UI here
```

    * *

      Prompts (OpenAI Vision, medoids only)

      -------------------------------------
    * System:

      > You return a compact JSON array of lowercase tags for photo search. Max {{max\_ai\_tags}} tags. Prefer nouns and short attributes. Use only entities you’re reasonably confident about. Use the provided city whitelist for place names if signage/landmarks match.
    * User (template):

      ```
      Cities you may use if appropriate: {{city_whitelist}}
      Return tags like ["ai:car","ai:monument","ai:venice","ai:glass","ai:blue glass","ai:sunny day","ai:reflection"].
      Avoid generic words like "photo", "image".
      ```

      (Prefix `ai:` here, or add prefix in code; your choice—keep it consistent.)
        * *

          Notes on performance

          --------------------
        * 3080 Ti with ViT-L/14 can push a few hundred embeds/sec at 224px equivalents; with 1024px proxies you still embed after resize to model’s input, so it’s fine. I/O will be your limit—use SSD for `data/proxies` and `embeds.parquet`.
        * Clustering scales linearly by time windows. Keep `time_window_minutes` small for fast convergence.
        * Vision on medoids shrinks API calls by **5–20×**.
            * *

              Guardrails

              ----------
            * Never change RAWs. Sidecars only.
            * All writes idempotent (hash key).
            * If Vision rejects a nude medoid: fall back to local AI tags silently; mark cluster `ai:vision_skipped`.
            * “Night” is suppressed if **studio-black** fires.
                * *

                  Quick start (Linux)

                  -------------------

                  ```bash
                  git clone <your-repo> photo-tag-pipeline
                  cd photo-tag-pipeline
                  cp config/config.example.yaml config/config.yaml
                  cp config/ck_vocab.example.yaml config/ck_vocab.yaml
                  # edit roots and city list

                  # Docker build & run
                  cd docker
                  docker compose build
                  OPENAI_API_KEY=sk-... docker compose up

                  # Open http://localhost:7860
                  ```
                    * *

                      Where this helps your use-cases

                      -------------------------------
                    * **Cities/venues** (Jockey Club, Venice/Murano) → Vision on medoids + CLIP with city whitelist.
                    * **Concepts** (blue glass, monuments, sunny day) → AI layer freeform + CK as you grow it.
                    * **Nudes** → local only; CK gives “frontal/profile/hands/face/hair:blonde/…/studio/black-background”; AI layer local captions still propose extra ideas without censorship.
                    * **Studio vs night** → heuristic prevents false “night” on black backdrops.

If you want, I can fill in a first pass of `tag_ai.py` (local captioning + CLIP mining) and the Vision prompt code block next.

## Response:

Thought for 35s

Carlos — here’s a **Codex-ready build brief** with everything you asked: explicit **intent/purpose**, JPEG/RAW handling, **EXIF unreliability strategy**, **CK/AI dual-layer tags**, **nude sets kept local**, clustering with medoids, and a **web UI** you can run in Docker on Linux.

    * *

      Project: **photo-tag-pipeline**

      ===

      Intent & purpose

      ----------------

      1. **Classify the entire photo library (RAW + JPEG) over time** with durable, human-useful keywords written to **XMP sidecars only**.
      2. **Run locally first** (single Linux GPU box), then stay modular so it can move to a server and later scale (pods / external batch / Vision API on medoids).
      3. Preserve Lightroom independence; the catalog can re-ingest via **Read Metadata from Files**.
      4. Respect content constraints: **nude sets are processed with local models only**; cloud calls are disabled for those by default.
        * *

          Scope

          -----
        * Inputs: mixed RAW/JPEG folders; filenames and EXIF may be inconsistent.
        * Output: updated **XMP** sidecars with two keyword namespaces:
            - **`CK:`** controlled, stable terms you care about.
            - **`AI:`** freeform, model-suggested terms (objects, materials, moods, landmarks), allowed to be creative.
        * Review: web UI (Gradio) showing **clusters** with a medoid; toggle tags; **apply to cluster**; write to XMP.
            * *

              Core pipeline

              -------------

              1. **Index & trust-score dates**
              2. **Build proxies** (1024px, sRGB)
              3. **Embeddings** (OpenCLIP ViT-L/14)
              4. **Time-window grouping → clustering** (HDBSCAN)
              5. **Medoid selection**
              6. **Tagging**
            * **CK layer** (controlled) via CLIP + EXIF rules + heuristics
            * **AI layer** (local caption + concept mining; optional OpenAI Vision on medoids only)

7. **Review & write XMP**

    * *

      EXIF unreliability: date trust & repair

      ---------------------------------------

      Implement a **date resolver** that assigns each image a `resolved_datetime` and a `trust_score`:

      **Signals (weighted):**
    * EXIF `DateTimeOriginal` (+0.6 if present & sane range 1990..now)
    * EXIF `CreateDate` / `ModifyDate` (+0.2)
    * Filesystem `mtime/ctime` (+0.2)
    * **Path tokens** (regex parse for `YYYY[_-]MM[_-]DD` or `YYYY`) (+0.2)
    * **Sequence consistency** inside same directory (filename ascending tends to increase time) (+0.2)

Detect **outliers** inside a folder window; if a file’s EXIF date is > 30 days off the local median and path tokens disagree, downgrade EXIF and prefer FS time + path tokens.

Store: `resolved_datetime`, `trust_score`, `signals_used`.

This lets clustering use **chronology that matches reality** even if a camera battery died.

    * *

      Clustering strategy

      -------------------
    * Partition the stream by `resolved_datetime` into **time windows** (default 60 min).
    * For each window, run **HDBSCAN** (cosine metric over L2-normalized CLIP embeddings).
    * Pick **medoid** per cluster (minimum sum cosine distance).
    * Save `{cluster_id, member_ids, medoid_id, start/end time}`.
        * *

          Tagging (two layers)

          --------------------

          ### CK layer (controlled)

          **Goal:** consistent, minimal vocabulary that mirrors how you search.
        * Start vocabulary (`config/ck_vocab.yaml`):
            - **Subjects:** `flower, mountain, moon, building, machine, night, dawn, macro, beach, forest, street, skyline`
            - **Places (coarse):** `Rio, Jardim Botanico, Paris, Venice, Florence, Marseille, São Paulo, Petrópolis, Teresópolis`
            - **Gear:** `Pentax67, C65`
            - **People concepts (for nude/portrait sets):**

              `abstract, profile, frontal, bodyscape, hands, face, hair:blonde, hair:brunette, outdoor, studio, black-background`

**Method:**

* **CLIP zero-shot** scoring: for each CK token, prompt `“a photo of {label}”`; keep top-K above threshold.
* **EXIF rules:** map make/model/lens into `CK:` gear tokens.
* **Heuristics – studio vs night:**
    - If **dark\_ratio ≥ 0.65** AND **person\_present** AND **ISO ≤ 800** AND **shutter 1/30…1/200** ⇒ add `CK:studio, CK:black-background`, **suppress** `CK:night`.
* **Places coarse:** CLIP text queries like `“a photo in {city}”` + optional OCR hints (see below).

### AI layer (freeform)

**Goal:** exploratory recall years later (e.g., “blue glass”, “Murano”, “statue”, “overcast”, “reflection”, “bridge”, “cathedral”, “industrial”, “market”, “graffiti”, “long exposure”, “bokeh”). All prefixed **`AI:`**.

**Local (default):**

* **Captioner:** BLIP/BLIP2 caption (half-precision on GPU).
* **Concept mining:** extract **nouns + noun chunks + salient adjectives** from the caption; dedupe with a synonym map; score with CLIP text embeddings; keep top-N.
* **Optional detectors:** lightweight OCR (tesseract) on medoid for signage; words above confidence add `AI:…` (e.g., street names, “Murano”).

**OpenAI Vision (optional, medoids only):**

* **Disabled** for clusters flagged as **people/nude**.
* For architecture/city/landscape clusters, call **4o-mini** with:
    - your **city whitelist**
    - instruction to return **compact JSON array of lowercase tags** (max N)
    - preference for **proper nouns** only when signage/landmarks match
    - everything prefixed `ai:` (or prefix in code)

This keeps costs microscopic and boosts proper-noun recall.

    * *

      Nude/people sets

      ----------------
    * **Local only** by default: person detector + face/hand keypoints to unlock people-concept CK tags.
    * For “hair:blonde/brunette”: start with caption tokens; if you want higher precision later, plug a **face-parsing** model to sample hair region hue (deferred).
    * Tag examples: `CK:frontal, CK:bodyscape, CK:studio, CK:black-background, AI:tattoo, AI:lace, AI:mirror`.
        * *

          Studio black backdrop vs night

          ------------------------------

          Already in CK heuristics. Additionally: if scene histogram shows **bimodal highlights** with low ISO and flash-like shutter, raise a **studio score** and down-weight “night”.
            * *

              Objects like “car”, “monument”, “sunny day”

              -------------------------------------------
            * Covered by **AI layer**: BLIP caption → concepts → CLIP scoring.
            * Add a **concept bank** seeded in config (`ai_tagging.prompt_extra_concepts`).
            * Keep it open-ended; no hard cap beyond `max_ai_tags`.
                * *

                  File types & safety

                  -------------------
                * Support RAW: `.dng .cr2 .cr3 .nef .arw .orf .rw2`
                * Support non-RAW: `.jpg .jpeg .tif .tiff .png` (older straight-out-of-camera JPEGs included).
                * **Never write to RAW/JPEG**; write **sidecars** with `exiftool`.
                * Existing keywords are **preserved**; only appended.
                    * *

                      Web UI (Gradio)

                      ---------------
                    * **Config**: load/save YAML; pick roots; city whitelist.
                    * **Run**: Scan → Proxies → Embeds → Cluster (progress bars).
                    * **Review**: one medoid per cluster, CK/AI tag chips with toggles; **Apply to cluster** checked by default.
                    * **Write**: progress; link to `audit.csv`.
                    * **Search**: regex over tags to spot-check.
                        * *

                          Docker (Linux GPU)

                          ------------------
                        * Base: `nvidia/cuda:12.x-runtime-ubuntu22.04`
                        * Install: Python 3.11, PyTorch CUDA, open-clip-torch, rawpy, hdbscan, scikit-learn, gradio, fastapi, exiftool, tesseract.
                        * Volumes: `/photos/...` mounted **read-only**; `/app/data` for caches; `/app/models` for weights.
                        * Single port: `7860`.
                        * Compose requests GPU with `runtime: nvidia`.
                            * *

                              Endpoints (FastAPI)

                              -------------------
                            * `POST /scan` → crawl + trust-score dates
                            * `POST /proxies`
                            * `POST /embeddings`
                            * `POST /cluster`
                            * `POST /tag/ck`
                            * `POST /tag/ai` (flags: `local=true/false`, `openai=true/false`)
                            * `POST /write`
                            * `GET /clusters?offset&limit`
                            * `GET /status`
                                * *

                                  Config highlights (YAML)

                                  ------------------------

                                  Add the **date resolver** and **OCR** toggles:

                                  ```yaml
                                  date_resolver:
                                    sane_range: [1990, 2100]
                                    outlier_days: 30
                                    weights:
                                      exif_original: 0.6
                                      exif_create: 0.2
                                      fs_time: 0.2
                                      path_tokens: 0.2
                                      sequence_consistency: 0.2
                                  ocr:
                                    enable: true
                                    min_confidence: 0.75
                                  people_policy:
                                    allow_openai_on_people_sets: false
                                  ai_tagging:
                                    use_openai_vision: true
                                    openai_model: "gpt-4o-mini"
                                    max_ai_tags: 12
                                    city_whitelist: ["Rio de Janeiro","Paris","Venice","Florence","Marseille","São Paulo","Petrópolis","Teresópolis","Lisbon","New York"]
                                  xmp:
                                    prefix_ck: "CK:"
                                    prefix_ai: "AI:"
                                  ```
                                    * *

                                      Tasks for Codex (ordered)

                                      -------------------------

                                      1. **Scaffold repo** per layout above; add `pyproject.toml` with pinned deps.
                                      2. Implement **scanner** with SHA-1, EXIF read (piexif/exifread + rawpy fallback), **date resolver** with trust-score, and path token parser.
                                      3. **Proxy builder** (rawpy for RAW; Pillow for others) + luminance stats.
                                      4. **OpenCLIP embedder** (fp16, CUDA; batch; parquet output).
                                      5. **Time-window clustering** with HDBSCAN and medoid selection.
                                      6. **People detector** (torchvision or YOLOv8n) and flag per image/cluster.
                                      7. **CK tagger** (CLIP zero-shot + EXIF + heuristics, including studio vs night).
                                      8. **AI tagger (local)**: BLIP caption → noun/adjective mining → CLIP scoring; optional OCR on medoids.
                                      9. **AI tagger (OpenAI)** for medoids (skip on people sets).
                                      10. **Writer**: exiftool batched calls; sidecars only; append keywords with prefixes.
                                      11. **Gradio UI** mounted on FastAPI; review grid; apply to cluster.
                                      12. **Docker** and **compose** with GPU; volumes for photos, data, models.
                                      13. **Audit logging** to CSV + simple search endpoint.
                                        * *

                                          Example deliverables you can hand me (optional, not required)

                                          -------------------------------------------------------------
                                        * **Seed CK vocab** (YAML) you want at start; I can trim/normalize.
                                        * **City whitelist** (10–30 items).
                                        * A **tiny image pack** (40–60 images) spanning: city/street, mountains, flowers, studio black backdrop portraits/nudes, architecture with signage, Murano/blue glass, machines/tech. This lets the captioner/concept mining show its behavior fast.

If you don’t send anything now, the defaults above will run with generic models and you can refine once you see first results.

    * *

      Notes on content filters

      ------------------------
    * **OpenAI Vision** may refuse artistic nudity; default is **off** for people sets.
    * CLIP/BLIP/OCR are local and unconstrained.
    * You can override per cluster in the UI.
        * *

          Edge-case guardrails

          --------------------
        * If EXIF and FS time disagree hard and **no path tokens**, tag `AI:date-uncertain` and keep the trust score so you can filter later.
        * If a medoid call to Vision fails, fall back to local AI tags; mark `AI:vision-skipped`.
        * Never overwrite existing user keywords.
            * *

              If you want, I’ll supply **starter code stubs** next for `tag_ai.py` (BLIP caption + noun phrase mining + CLIP scoring) and the **OpenAI medoid prompt** block. If you prefer to feed sample images, send a small pack; the pipeline doesn’t need them to compile, but they help validate captions and the studio/night heuristic quickly.

              ## Response:

              Thought for 37s

              Great. Here are the **starter modules** you asked for — drop them into your repo under `app/`. They’re self-contained, lazy-load models, and align with the spec you already have. They don’t assume sample files.
                * *

                  ### `app/tag_ai.py` — local captioning + concept mining + CLIP scoring + optional OCR

                  ```python
                  # app/tag_ai.py
                  from __future__ import annotations
                  import os, re, json, base64, math
                  from typing import List, Iterable, Optional, Tuple, Dict
                  from dataclasses import dataclass

                  import numpy as np
                  from PIL import Image

                  import torch
                  import open_clip

                  # Optional OCR (enabled via flag)
                  try:
                      import pytesseract
                      _HAS_TESS = True
                  except Exception:
                      _HAS_TESS = False

                  # Optional BLIP captioner
                  try:
                      from transformers import BlipProcessor, BlipForConditionalGeneration
                      _HAS_BLIP = True
                  except Exception:
                      _HAS_BLIP = False

                  # -------------------------------
                  # Config dataclass
                  # -------------------------------

                  @dataclass
                  class AiTagConfig:
                      max_ai_tags: int = 12
                      ai_prefix: str = "AI:"
                      concept_bank_extra: Tuple[str, ...] = tuple()
                      ocr_enable: bool = True
                      ocr_min_conf: float = 0.75
                      blip_model: str = "Salesforce/blip-image-captioning-base"  # speed/size tradeoff
                      clip_model: str = "ViT-L-14"
                      clip_pretrained: str = "openai"
                      clip_device: str = "cuda"
                      city_whitelist: Tuple[str, ...] = tuple()

                  # -------------------------------
                  # Lazy loaders
                  # -------------------------------

                  _BLIP = None
                  _BLIP_P = None
                  _CLIP = None
                  _CLIP_P = None
                  _CLIP_TOKENIZER = None
                  _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

                  def _load_blip(model_name: str):
                      global _BLIP, _BLIP_P
                      if _BLIP is None:
                          if not _HAS_BLIP:
                              raise RuntimeError("transformers BLIP not installed")
                          _BLIP_P = BlipProcessor.from_pretrained(model_name)
                          _BLIP = BlipForConditionalGeneration.from_pretrained(model_name)
                          _BLIP.to(_DEVICE).eval()

                  def _load_clip(clip_model: str, pretrained: str, device: str):
                      global _CLIP, _CLIP_P, _CLIP_TOKENIZER
                      if _CLIP is None:
                          model, _, preprocess = open_clip.create_model_and_transforms(
                              clip_model, pretrained=pretrained, device=device
                          )
                          tokenizer = open_clip.get_tokenizer(clip_model)
                          _CLIP, _CLIP_P, _CLIP_TOKENIZER = model, preprocess, tokenizer
                          _CLIP.eval()

                  # -------------------------------
                  # Utilities
                  # -------------------------------

                  _WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-\&']+")
                  _STOP = {
                      "the","a","an","and","or","of","in","on","at","with","for","by","to","from",
                      "this","that","these","those","it","its","is","are","was","were","be","being","been",
                      "over","under","near","very","really","just","quite","some","any","many","much"
                  }

                  def _clean_tokens(s: str) -> List[str]:
                      toks = [t.lower() for t in _WORD_RE.findall(s)]
                      return [t for t in toks if t not in _STOP and len(t) > 2]

                  def _ngramize(tokens: List[str], nmin=1, nmax=3) -> List[str]:
                      out = []
                      for n in range(nmin, nmax+1):
                          for i in range(0, len(tokens)-n+1):
                              out.append(" ".join(tokens[i:i+n]))
                      return out

                  def _dedupe_keep_order(items: Iterable[str]) -> List[str]:
                      seen = set()
                      out = []
                      for it in items:
                          if it not in seen:
                              out.append(it)
                              seen.add(it)
                      return out

                  def _topk(arr: np.ndarray, k: int) -> List[int]:
                      if k >= len(arr):
                          return list(np.argsort(-arr))
                      idx = np.argpartition(-arr, k-1)[:k]
                      idx = idx[np.argsort(-arr[idx])]
                      return list(idx)

                  def _read_image(path: str) -> Image.Image:
                      # We assume proxies (sRGB JPEG/PNG/etc.)
                      im = Image.open(path).convert("RGB")
                      return im

                  # -------------------------------
                  # Captioning + concept mining
                  # -------------------------------

                  def blip_caption(image_path: str, model_name: str) -> str:
                      _load_blip(model_name)
                      image = _read_image(image_path)
                      inputs = _BLIP_P(images=image, return_tensors="pt").to(_DEVICE)
                      with torch.no_grad():
                          out = _BLIP.generate(**inputs, max_new_tokens=40)
                      cap = _BLIP_P.decode(out[0], skip_special_tokens=True)
                      return cap.strip()

                  def ocr_tokens(image_path: str, min_conf: float = 0.75) -> List[str]:
                      if not (_HAS_TESS):
                          return []
                      image = _read_image(image_path)
                      data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                      out = []
                      for w, conf in zip(data.get("text", []), data.get("conf", [])):
                          try:
                              c = float(conf)
                          except Exception:
                              continue
                          if c/100.0 >= min_conf:
                              tok = w.strip()
                              if _WORD_RE.fullmatch(tok):
                                  out.append(tok)
                      # prefer distinct uppercase words (signage), but lowercased for tags
                      out = [t.lower() for t in out if len(t) > 2]
                      return _dedupe_keep_order(out)[:10]

                  def mine_concepts_from_caption(
                      caption: str,
                      extra_bank: Iterable[str] = (),
                      city_whitelist: Iterable[str] = (),
                      limit: int = 40
                  ) -> List[str]:
                      toks = _clean_tokens(caption)
                      grams = _ngramize(toks, 1, 2)

                      # Seed with curated extras and cities (lowercased)
                      seed = [e.lower() for e in extra_bank]
                      cities = [c.lower() for c in city_whitelist]

                      # pick things that look like materials/weather/objects via regex cues
                      cues = []
                      for g in grams:
                          if any(w in g for w in ("glass","bridge","statue","monument","cathedral","market",
                                                  "museum","reflection","graffiti","industrial","construction",
                                                  "vehicle","car","train","tram","boat","ship","snow","fog",
                                                  "rain","overcast","sunny","bokeh","macro","long exposure",
                                                  "neon","sign")):
                              cues.append(g)

                      candidates = _dedupe_keep_order(seed + cities + grams + cues)
                      # prune crazy-long grams
                      candidates = [c for c in candidates if 3 <= len(c) <= 32]
                      # remove obvious junk
                      junk = {"photo","image","picture"}
                      candidates = [c for c in candidates if c not in junk]
                      return candidates[:limit]

                  # -------------------------------
                  # CLIP scoring of concepts
                  # -------------------------------

                  def score_concepts_with_clip(
                      image_embedding: np.ndarray,
                      concepts: List[str],
                      clip_model: str,
                      pretrained: str,
                      device: str
                  ) -> List[Tuple[str, float]]:
                      _load_clip(clip_model, pretrained, device)
                      # Normalize image embedding
                      img = torch.tensor(image_embedding, device=device, dtype=torch.float32)
                      img = img / (img.norm() + 1e-6)

                      prompts = [f"a photo of {c}" for c in concepts]
                      tokens = _CLIP_TOKENIZER(prompts).to(device)
                      with torch.no_grad():
                          txt = _CLIP.encode_text(tokens)
                          txt = txt / (txt.norm(dim=-1, keepdim=True) + 1e-6)
                          sims = (img @ txt.T).float().cpu().numpy().ravel()

                      pairs = list(zip(concepts, sims))
                      pairs.sort(key=lambda t: t[1], reverse=True)
                      return pairs

                  # -------------------------------
                  # Main entry points
                  # -------------------------------

                  def ai_tags_local(
                      proxy_path: str,
                      image_embedding: np.ndarray,
                      cfg: AiTagConfig
                  ) -> List[str]:
                      """
                      Returns prefixed AI: tags from local caption + concept mining + CLIP scoring + optional OCR.
                      """
                      # 1) caption
                      cap = ""
                      if _HAS_BLIP:
                          try:
                              cap = blip_caption(proxy_path, cfg.blip_model)
                          except Exception:
                              cap = ""
                      # 2) concepts
                      concepts = mine_concepts_from_caption(cap, cfg.concept_bank_extra, cfg.city_whitelist)
                      # 3) OCR (medoids recommended, but safe here)
                      if cfg.ocr_enable and _HAS_TESS:
                          ocr = ocr_tokens(proxy_path, cfg.ocr_min_conf)
                          concepts = _dedupe_keep_order(concepts + ocr)

                      if not concepts:
                          return []

                      # 4) CLIP scoring
                      scored = score_concepts_with_clip(
                          image_embedding=image_embedding,
                          concepts=concepts,
                          clip_model=cfg.clip_model,
                          pretrained=cfg.clip_pretrained,
                          device=cfg.clip_device if torch.cuda.is_available() else "cpu"
                      )

                      # 5) top-K and format
                      top = [c for c, _ in scored[:cfg.max_ai_tags]]
                      tags = [f"{cfg.ai_prefix}{t}" for t in top]
                      return tags
                  ```
                    * *

                      ### `app/openai_vision.py` — medoid call wrapper + prompt

                      ```python

                      # app/openai_vision.py

                      from __future__ import annotations

                      import os, json, base64

                      from typing import List, Sequence

                      from PIL import Image

                      from io import BytesIO

                      def _b64_png(path: str) -> str:

                          im = Image.open(path).convert("RGB")

                          buf = BytesIO()

                          im.save(buf, format="PNG")

                          return base64.b64encode(buf.getvalue()).decode("utf-8")

                      SYSTEM_PROMPT = """You are a photo tagger. Respond ONLY with a compact JSON array of lowercase tags.
                    * Prefer nouns and short attributes (e.g., "blue glass", "statue", "venice", "bridge", "overcast").
                    * Use at most {max_tags} tags.
                    * Do not include words like "photo" or "image".
                    * Use a city name ONLY if there is clear signage or a highly distinctive landmark and it appears in the whitelist provided.
                    * No explanations. JSON array only.

"""

USER_PROMPT = """Cities you may use if appropriate (whitelist):

{city_list}

Examples of useful tag styles: ["ai:car","ai:monument","ai:venice","ai:glass","ai:blue glass","ai:sunny day","ai:reflection","ai:cathedral","ai:graffiti"]

Return tags prefixed with "ai:" and keep them short."""

def call_openai_vision_on_image(

    image_path: str,

    city_whitelist: Sequence[str],

    max_tags: int = 12,

    model: str = "gpt-4o-mini",

) -> List[str]:

    """

    Returns a list of ai: tags from OpenAI Vision. Requires OPENAI_API_KEY.

    Avoid using for nude/people sets if you want to prevent refusals.

    """

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:

        raise RuntimeError("OPENAI_API_KEY not set")

    # Prefer Responses API; fall back to Chat Completions if needed.

    img_b64 = _b64_png(image_path)

    sys_prompt = SYSTEM_PROMPT.format(max_tags=max_tags)

    usr_prompt = USER_PROMPT.format(city_list=", ".join(city_whitelist))

    try:

        # Newer SDK (responses)

        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        resp = client.responses.create(

            model=model,

            input=[{

                "role":"system",

                "content":[{"type":"text","text":sys_prompt}]

            },{

                "role":"user",

                "content":[

                    {"type":"input_text","text":usr_prompt},

                    {"type":"input_image","image_data":img_b64}

                ]

            }],

            temperature=0.2,

        )

        text = resp.output_text  # SDK provides a flat text accessor

    except Exception:

        # Older SDK (chat.completions)

        import openai as _openai

        _openai.api_key = api_key

        resp = _openai.ChatCompletion.create(

            model=model,

            messages=[

                {"role":"system","content":sys_prompt},

                {"role":"user","content":[

                    {"type":"text","text":usr_prompt},

                    {"type":"image_url","image_url":{"url":f"data:image/png;base64,{img_b64}"}}

                ]}

            ],

            temperature=0.2,

        )

        text = resp["choices"][0]["message"]["content"]

    # Parse JSON array safely

    try:

        arr = json.loads(text)

        if isinstance(arr, list):

            # normalize and ensure ai: prefix

            out = []

            for t in arr:

                s = str(t).strip().lower()

                if not s:

                    continue

                if not s.startswith("ai:"):

                    s = "ai:" + s

                out.append(s)

            return out[:max_tags]

    except Exception:

        pass

    # Fallback: try to extract JSON substring

    start = text.find("[")

    end = text.rfind("]")

    if start != -1 and end != -1 and end > start:

        try:

            arr = json.loads(text[start:end+1])

            return ["ai:"+str(t).strip().lower() for t in arr][:max_tags]

        except Exception:

            return []

    return []

```

* * *

### Add these to your Docker image (if you haven’t already)

In your Dockerfile:

```dockerfile
# OCR
RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Python deps (append to your existing pip install line)
RUN pip install transformers accelerate safetensors pytesseract
```

    * *

      ### How to call from your pipeline

      ```python
      # inside your tagging step for a medoid:
      from app.tag_ai import AiTagConfig, ai_tags_local
      from app.openai_vision import call_openai_vision_on_image

      cfg = AiTagConfig(
          max_ai_tags=12,
          ai_prefix="AI:",
          concept_bank_extra=tuple(["car","monument","statue","bridge","cathedral",
                                    "glass","blue glass","sunny day","overcast","rain",
                                    "reflection","graffiti","industrial","market",
                                    "long exposure","bokeh","macro"]),
          ocr_enable=True,
          city_whitelist=tuple(["Rio de Janeiro","Paris","Venice","Florence","Marseille",
                                "São Paulo","Petrópolis","Teresópolis","Lisbon","New York"])
      )

      # get your precomputed image embedding for the medoid:
      # image_embedding: np.ndarray of shape [D]

      local_tags = ai_tags_local(
          proxy_path=medoid_proxy_path,
          image_embedding=image_embedding,
          cfg=cfg
      )

      vision_tags = []
      if use_openai and not cluster_is_people:
          vision_tags = call_openai_vision_on_image(
              medoid_proxy_path,
              city_whitelist=cfg.city_whitelist,
              max_tags=cfg.max_ai_tags,
              model="gpt-4o-mini"
          )

      # Merge, dedupe, cap
      tags = []
      seen = set()
      for t in (vision_tags + local_tags):
          if t not in seen:
              tags.append(t); seen.add(t)
      tags = tags[:cfg.max_ai_tags]
      ```
        * *

          ### Notes
        * BLIP is a good baseline. If you want sharper captions later, drop in BLIP-2 or Qwen-VL; the interface above remains the same.
        * The local path uses **your existing CLIP image embeddings**; no second image encode is done.
        * OCR is medoid-friendly; you can gate it to medoids only if you prefer.
        * OpenAI block is **medoid-only** by design and safe to skip on people sets.

If you want me to wire this into your `jobs.py` and UI callbacks, say so and I’ll hand you the glue functions next.

## Response:

Thought for 25s

Carlos, plain English recap:

**What those last files are**

* They’re **core modules for the main pipeline**, not a separate side tool.
* Specifically:
    - `tag_ai.py` = **local AI tags**: caption → mine concepts → score with CLIP → output `AI:` tags. Optional OCR.
    - `openai_vision.py` = **wrapper** to call OpenAI Vision on a **cluster medoid** and get `ai:` tags back.
* They drop into the architecture I described earlier and plug into the “**AI tagging**” step. I sent them “alone” to avoid dumping the whole project in one message; they’re meant to be **called by the jobs/UI** you’ll wire up.

**Where you are right now**

1. You have a full **spec** for the end-to-end pipeline (scan → proxies → embeddings → time windows → HDBSCAN → medoids → CK tags → AI tags → review → XMP).
2. You now also have the **AI-tagging pieces** ready to be integrated.
3. The **jobs/UI wiring** is the next glue step (the “callbacks” I mentioned).

**What to do in your next hour (no code yet)**

* Decide these toggles so you can paste them into `config.yaml` later:
    - **Studio heuristic:** change **ISO threshold to 1600** (your note).
    - **People policy:** keep **cloud off** for nude/people clusters (local only).
    - **Prefixes:** `CK:` for controlled, `AI:` for freeform.
    - **City whitelist:** list your real cities (Rio de Janeiro, Paris, Venice, etc.).
    - **CK vocabulary:** add your controlled terms (subjects + people concepts + gear).
* Pick your **pre-test** size: 500–1,000 **medoids**. That keeps cost tiny if you try Vision on them.

**How the first pre-test run will work (once you sit at the PC)**

1. **Scan & proxies** on a few root folders (fast; builds 1024px proxies).
2. **Embeddings** with OpenCLIP (GPU).
3. **Time-window clustering** + **pick medoids**.
4. Run **local AI tags** on medoids (`tag_ai.py`).
5. Optionally run **OpenAI Vision** on the same medoids (architecture/places only).
6. **Do not write XMP yet.** Just export an **audit CSV** of proposed `CK:`/`AI:` tags per medoid.
7. Review on screen: keep/trim terms, note misses, adjust CK vocab, city list, thresholds.
8. When happy, flip the **“write to XMP”** switch and apply **to whole clusters** (that’s where you save time).

**About subjects beyond your initial list**

* You’re not limited to the small set. The **AI layer** is intentionally freeform and will propose things like **car, monument, statue, bridge, glass, blue glass, sunny day, reflection, cathedral, graffiti, industrial, macro, bokeh, long exposure**.
* Keep the **CK layer** compact for the stuff you _always_ want searchable; let **AI** be exploratory for long-tail recall.

**EXIF date mess**

* The pipeline **does not trust EXIF blindly**. It resolves a date using EXIF, file times, path tokens, and sequence consistency, then clusters by that **resolved time**. That’s in the main spec.

**Nudes**

* Keep them **local** (CLIP/BLIP/OCR). Vision may refuse them. You’ll still get people-concept CK tags (frontal/profile/hands/face/hair:blonde/brunette/studio/black-background).

**Cost sanity for your medoid pre-test**

* 1,000 medoids on **4o-mini** ≈ cents to well under a dollar; on **4o** ≈ around a dollar or two. Your $5 ballpark is safe.

**Why those modules came “separately”**

* They are the **two heavy bits** most folks tweak first:
    - local captioning/concept mining/scoring,
    - Vision wrapper and prompt.
* Everything else (scan/embeds/cluster/write/UI) is plumbing that calls these. I can hand you the glue next, but you asked to keep this message code-free.

**If you want to send images**

* I can’t run heavy vision models here, so I can’t actually process your files. The quickest path is: you generate **medoids** on your box, then run a **Vision batch** there. If you prefer, I’ll give you a tiny script next that reads a list of medoid paths and outputs a JSON/CSV of tags—drop-in, one command.

**TL;DR plan**

* Finalize config choices (ISO=1600, prefixes, CK vocab, city list, people policy).
* Run a **medoid-only pre-test** (local AI + optional Vision) and review the audit.
* Adjust vocabulary/heuristics.
* Then enable **cluster-wide XMP write**.

When you’re at the PC, say “glue it,” and I’ll produce the **jobs/UI wiring** steps and a **one-shot medoid batch script** so you can test tags immediately.

## Response:

Thought for 23s

Got you, Carlos. Here’s a clean status + what to do next, zero fluff.

Where we are

* We’re still talking about the **main pipeline**.
* The last two files I sent (`tag_ai.py`, `openai_vision.py`) are **plug-ins for the AI-tagging step** of that main pipeline:
    - `tag_ai.py` → local captions + concept mining + CLIP scoring → outputs `AI:` tags.
    - `openai_vision.py` → optional Vision call **on medoids only** → more `ai:` tags.
* The rest (scan → proxy → embed → time-window → HDBSCAN → medoids → review UI → XMP) stays as previously specified. Those two modules slot into “AI tags.”

Your confirmations (applied)

* **Studio heuristic max ISO:** **3200**.
* **People policy:** **nudes = local only** (no cloud calls).
* **Prefixes:** **`CK:`** (controlled) and **`AI:`** (freeform).

Cities whitelist (normalized)

=

I’ll load these, plus helpful aliases where it matters:

* **USA:** New York; Chicago; **Urbana–Champaign** (add tokens: `urbana`, `champaign`, `uiuc`); Washington DC; Seattle; Orlando.
* **Brazil:** Rio de Janeiro; São Paulo; Pirassununga (older coffee farms—expect low recall; we’ll also seed `coffee farm`); Petrópolis; Teresópolis; Niterói; Fortaleza.
* **Europe:** London; Paris; Chartres; Versailles; Rome; Venice; Florence; Hamburg; Berlin.
* **Australia:** Sydney.

Concepts / things (mapped)

==

* **CK layer (stable, you’ll see these a lot):**

  `abstract, portrait, architecture, monument, street photo, group, dance, theatre, stage, face, hand (rule: suppress on nude sets), flower, mountain, clouds, sea, plants, macro, shopping center, interior, lines, cars, trains, planes/airplane`
* **AI layer (freeform discovery; long-tail):**

  `book, screenshot, fork, clock, shelf, reflection, glass, blue glass, Murano glass, statue, bridge, cathedral, graffiti, industrial, market, bokeh, long exposure, overcast, sunny day`
* Rule reminders:
    - **“hand (not in nudes)”** → enforced: if cluster flagged nude, suppress `CK:hand`.
    - **Studio vs night** → updated to **ISO ≤ 3200** threshold in the heuristic.

What to do next (before you sit at the PC)

==

1. **Pre-test scope:** decide a batch of **500–1,000 medoids** (cheap even on 4o; trivial on 4o-mini).
2. **Config edits you’ll paste later:**

   * `heuristics.studio_black_vs_night.iso_threshold = 3200`
   * `people_policy.allow_openai_on_people_sets = false`
   * `xmp.prefix_ck = "CK:"`, `xmp.prefix_ai = "AI:"`
   * `ai_tagging.city_whitelist = [the list above]`
   * Add the CK terms above to `ck_vocab.yaml`.

Installing CLIP on Linux (no fuss)

==

Two options—you only need one.

**A) Docker (recommended, keeps the box clean)**

* Use the Dockerfile/compose I outlined. It installs PyTorch (CUDA), `open-clip-torch`, `rawpy`, `exiftool`, `tesseract`.
* Start the container with `runtime: nvidia`. If `nvidia-smi` works on the host, CLIP will run on GPU inside.

**B) Native (Conda)**

```bash
conda create -n photo python=3.11 -y
conda activate photo
# PyTorch (CUDA 12.1 build)
pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision
# Core libs
pip install open-clip-torch rawpy hdbscan scikit-learn pillow pandas pyarrow duckdb tqdm
# Optional caption/OCR
pip install transformers accelerate safetensors pytesseract
sudo apt-get install -y exiftool tesseract-ocr
```

That’s it—no model checkpoints to “install” manually; `open-clip-torch` will pull weights on first use.

First run plan (medoid pre-test)

1. **Scan + proxies + embeddings + clustering** on a few representative roots.
2. Export **medoid list**.
3. Run **local AI tags** on medoids.
4. Run **Vision on medoids** for non-people clusters (cities/architecture/objects).
5. Review the **audit CSV + UI grid**. Don’t write XMP yet.
6. Tweak CK vocabulary and thresholds once you see real tags.
7. When satisfied, **apply to full clusters** and write XMP.

Small things I’ll set for you

=

* Add aliases for **Urbana–Champaign** as noted.
* Seed `AI:` bank with your “house objects” and “blue/Murano glass” so local runs can propose them even without Vision.
* Tag `AI:date-uncertain` when the date resolver can’t reach a decent trust score.

Quick checks I’ll need from you (yes/no is enough)

==

1. **OCR on medoids** for signage → keep **on**?
2. **Max AI tags per image** → stick with **12**?
3. **Apply to cluster on write** → keep **enabled by default**?

If you’re good with that, I’ll ship the **glue** next: the jobs that call these steps, a one-command **medoid batch** script, and the couple of UI actions to run the pre-test and export the audit without touching XMP.

## Response:

Thought for 15s

**Photo-tag-pipeline — Pre-test Glue + Ui Wiring (project**

# photo-tag-pipeline — pre-test glue + UI wiring

This note locks the first **medoid pre-test** flow and the glue you asked for. It assumes the core modules exist (or will be generated by Codex) as previously specified:

- `scanner.py`, `proxy.py`, `embed.py`, `cluster.py`, `tag_ck.py`, `tag_ai.py`, `openai_vision.py`, `write_xmp.py`, `heuristics.py`, `store.py`, `utils.py`

> **Remark on OCR**: **OCR is OFF for now.** Leave the hooks in place but keep it disabled in config. We’ll revisit after the first audit.

---

## Confirmed settings

- Studio heuristic ISO max: **3200**
- People policy: **nudes = local only** (no cloud calls)
- Prefixes: `for controlled,` for freeform
- Max AI tags per image: **12**
- Apply-to-cluster on write: **enabled by default**

### City whitelist (normalized)

USA: New York; Chicago; Urbana–Champaign (aliases: `urbana`, `champaign`, `uiuc`); Washington DC; Seattle; Orlando\

Brazil: Rio de Janeiro; São Paulo; Pirassununga; Petrópolis; Teresópolis; Niterói; Fortaleza\

Europe: London; Paris; Chartres; Versailles; Rome; Venice; Florence; Hamburg; Berlin\

Australia: Sydney

### CK concepts (seed)

`abstract, portrait, architecture, monument, street photo, group, dance, theatre, stage, face, hand, flower, mountain, clouds, sea, plants, macro, shopping center, interior, lines, cars, trains, airplane`

### AI concepts (seedable; discovery)

`book, screenshot, fork, clock, shelf, reflection, glass, blue glass, murano glass, statue, bridge, cathedral, graffiti, industrial, market, bokeh, long exposure, overcast, sunny day`

> Rule: suppress `CK:hand` on nude/people clusters. Rule: studio black backdrop suppresses `CK:night`.

---

## File tree (additions for glue)

```
photo-tag-pipeline/
  app/
    jobs.py          # orchestration glue
    ui.py            # Gradio UI for pre-test + write
    main.py          # FastAPI app mounting the UI
  scripts/
    medoid_batch.py  # one-shot medoid tagging to CSV (no XMP writes)
  config/
    config.yaml      # update values below
    ck_vocab.yaml    # seed terms above
```

---

## `config.yaml` deltas to copy in

```yaml
heuristics:
  studio_black_vs_night:
    enable: true
    iso_threshold: 3200
    face_required_for_studio: true
    dark_ratio: 0.65
people_policy:
  allow_openai_on_people_sets: false
xmp:
  prefix_ck: "CK:"
  prefix_ai: "AI:"
review:
  enable: true
  default_apply_to_cluster: true
ai_tagging:
  max_ai_tags: 12
  use_openai_vision: true        # still medoids-only and skipped for people sets
  openai_model: gpt-4o-mini
  city_whitelist:
    - New York
    - Chicago
    - Urbana–Champaign
    - Washington DC
    - Seattle
    - Orlando
    - Rio de Janeiro
    - São Paulo
    - Pirassununga
    - Petrópolis
    - Teresópolis
    - Niterói
    - Fortaleza
    - London
    - Paris
    - Chartres
    - Versailles
    - Rome
    - Venice
    - Florence
    - Hamburg
    - Berlin
    - Sydney
ocr:
  enable: false    # OFF for now; hooks remain
```

---

## `app/jobs.py` — orchestration glue (calls into your modules)

```python
from __future__ import annotations
import os, json
from pathlib import Path
from typing import List, Dict

from app import scanner, proxy, embed, cluster, tag_ck, tag_ai, write_xmp
from app.openai_vision import call_openai_vision_on_image
from app.tag_ai import AiTagConfig

import pandas as pd

class Pipeline:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)
        self.audit_csv = Path(self.cfg['review'].get('audit_csv', 'data/audit.csv'))

    # 1) scan + proxies + embeds + cluster
    def run_scan(self) -> pd.DataFrame:
        rows = scanner.crawl(self.cfg['roots'], self.cfg['index']['include_ext'], self.cfg['index']['exclude_regex'])
        df = pd.DataFrame(rows)
        df.to_parquet(self.data_dir / 'index.parquet', index=False)
        return df

    def run_proxies(self, df: pd.DataFrame) -> pd.DataFrame:
        stats = []
        for p in df['path']:
            out = proxy.build_proxy(p, None, self.cfg['proxy']['max_size'], self.cfg['proxy']['jpeg_quality'])
            stats.append(out)
        pdf = pd.DataFrame(stats)
        pdf.to_parquet(self.data_dir / 'proxies.parquet', index=False)
        return pdf

    def run_embed(self, proxies_df: pd.DataFrame) -> pd.DataFrame:
        e = embed.ClipEmbedder(self.cfg['embeddings']['model'], self.cfg['embeddings']['pretrained'], self.cfg['embeddings']['device'])
        em = e.encode_paths(list(proxies_df['proxy_path']))
        edf = pd.DataFrame({'id': proxies_df['id'], 'emb': list(em)})
        edf.to_parquet(self.data_dir / 'embeds.parquet', index=False)
        return edf

    def run_cluster(self, index_df: pd.DataFrame, embeds_df: pd.DataFrame) -> pd.DataFrame:
        cdf = cluster.cluster_time_windowed(index_df, embeds_df, self.cfg['clustering'], self.cfg['date_resolver'])
        cdf.to_parquet(self.data_dir / 'clusters.parquet', index=False)
        return cdf

    # 2) medoid tagging (no XMP)
    def medoid_ai_tags(self, clusters_df: pd.DataFrame, embeds_df: pd.DataFrame, proxies_df: pd.DataFrame, use_openai: bool = True) -> pd.DataFrame:
        cfg_ai = self.cfg['ai_tagging']
        aiconf = AiTagConfig(
            max_ai_tags=cfg_ai['max_ai_tags'],
            ai_prefix=self.cfg['xmp']['prefix_ai'],
            concept_bank_extra=tuple(self.cfg['ai_tagging'].get('prompt_extra_concepts', [])),
            ocr_enable=self.cfg.get('ocr', {}).get('enable', False),
            city_whitelist=tuple(self.cfg['ai_tagging']['city_whitelist'])
        )
        rows = []
        for _, row in clusters_df.iterrows():
            mid = row['medoid_id']
            proxy_path = proxies_df.loc[proxies_df['id']==mid, 'proxy_path'].values[0]
            emb = embeds_df.loc[embeds_df['id']==mid, 'emb'].values[0]

            local_tags = tag_ai.ai_tags_local(proxy_path, emb, aiconf)
            vision_tags = []
            if use_openai and (not row.get('is_people', False)) and self.cfg['ai_tagging']['use_openai_vision']:
                try:
                    vision_tags = call_openai_vision_on_image(proxy_path, aiconf.city_whitelist, aiconf.max_ai_tags, self.cfg['ai_tagging']['openai_model'])
                except Exception:
                    vision_tags = []

            tags = []
            seen = set()
            for t in (vision_tags + local_tags):
                if t not in seen:
                    tags.append(t); seen.add(t)

            rows.append({'cluster_id': row['cluster_id'], 'medoid_id': mid, 'ai_tags': tags})
        adf = pd.DataFrame(rows)
        adf.to_parquet(self.data_dir / 'medoid_ai_tags.parquet', index=False)
        return adf

    def export_audit(self, clusters_df: pd.DataFrame, medoid_ai_df: pd.DataFrame) -> Path:
        out = clusters_df[['cluster_id','count','medoid_id']].merge(medoid_ai_df, on=['cluster_id','medoid_id'], how='left')
        out.to_csv(self.audit_csv, index=False)
        return self.audit_csv

    # 3) write XMP (cluster-wide) — call after you approve tags
    def write_cluster_keywords(self, selection: List[int], clusters_df: pd.DataFrame, ck_df: pd.DataFrame, ai_df: pd.DataFrame, index_df: pd.DataFrame):
        prefix_ck = self.cfg['xmp']['prefix_ck']
        prefix_ai = self.cfg['xmp']['prefix_ai']
        apply_to_cluster = self.cfg['review'].get('default_apply_to_cluster', True)

        for cid in selection:
            members = clusters_df.loc[clusters_df['cluster_id']==cid, 'member_ids'].values[0]
            # Gather tags: CK from ck_df (optional); AI from ai_df
            ai_row = ai_df.loc[ai_df['cluster_id']==cid]
            ai_tags = ai_row['ai_tags'].values[0] if len(ai_row) else []
            # write
            paths = index_df[index_df['id'].isin(members)]['path'].tolist() if apply_to_cluster else [index_df[index_df['id']==clusters_df.loc[clusters_df['cluster_id']==cid, 'medoid_id'].values[0]]['path'].values[0]]
            write_xmp.write_keywords(paths, [ai_tags]*len(paths), prefix_ck, prefix_ai, workers=self.cfg['xmp']['write_concurrency'])
```

---

## `app/ui.py` — minimal Gradio UI for pre-test and write

```python
from __future__ import annotations
import gradio as gr
import yaml, pandas as pd
from pathlib import Path
from app.jobs import Pipeline

STATE = {
    'cfg': None,
    'dfs': {}
}

def load_config(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        STATE['cfg'] = yaml.safe_load(f)
    return "Config loaded."

def run_prestep(which):
    p = Pipeline(STATE['cfg'])
    if which == 'scan':
        df = p.run_scan(); STATE['dfs']['index'] = df; return f"Indexed {len(df)} files"
    if which == 'proxies':
        df = p.run_proxies(STATE['dfs']['index']); STATE['dfs']['proxies'] = df; return f"Built {len(df)} proxies"
    if which == 'embed':
        df = p.run_embed(STATE['dfs']['proxies']); STATE['dfs']['embeds'] = df; return f"Embedded {len(df)} images"
    if which == 'cluster':
        df = p.run_cluster(STATE['dfs']['index'], STATE['dfs']['embeds']); STATE['dfs']['clusters'] = df; return f"Clusters: {df['cluster_id'].nunique()}"

def run_medoid_ai(openai_flag: bool):
    p = Pipeline(STATE['cfg'])
    adf = p.medoid_ai_tags(STATE['dfs']['clusters'], STATE['dfs']['embeds'], STATE['dfs']['proxies'], use_openai=openai_flag)
    STATE['dfs']['medoid_ai'] = adf
    return f"Tagged {len(adf)} medoids"

def export_audit():
    p = Pipeline(STATE['cfg'])
    out = p.export_audit(STATE['dfs']['clusters'], STATE['dfs']['medoid_ai'])
    return f"Audit written: {out}"

def build_ui():
    with gr.Blocks(title="photo-tag-pipeline") as demo:
        gr.Markdown("# photo-tag-pipeline — Medoid Pre-Test")
        cfg_path = gr.Textbox(label="config.yaml path", value="config/config.yaml")
        gr.Button("Load config").click(load_config, [cfg_path], [gr.Textbox(label="status", value="")])
        with gr.Row():
            gr.Button("1) Scan").click(run_prestep, [gr.Textbox(value='scan', visible=False)], [gr.Textbox(label="status1", value="")])
            gr.Button("2) Proxies").click(run_prestep, [gr.Textbox(value='proxies', visible=False)], [gr.Textbox(label="status2", value="")])
            gr.Button("3) Embeddings").click(run_prestep, [gr.Textbox(value='embed', visible=False)], [gr.Textbox(label="status3", value="")])
            gr.Button("4) Cluster").click(run_prestep, [gr.Textbox(value='cluster', visible=False)], [gr.Textbox(label="status4", value="")])
        with gr.Row():
            gr.Button("5) Medoid AI (local only)").click(run_medoid_ai, [gr.Checkbox(value=False, visible=False)], [gr.Textbox(label="status5", value="")])
            gr.Button("5b) Medoid AI (+Vision)").click(run_medoid_ai, [gr.Checkbox(value=True, visible=False)], [gr.Textbox(label="status5b", value="")])
        gr.Button("6) Export Audit CSV").click(export_audit, [], [gr.Textbox(label="status6", value="")])
    return demo
```

---

## `app/main.py` — FastAPI + Gradio mount

```python
from fastapi import FastAPI
from app.ui import build_ui

app = FastAPI()

ui = build_ui()
app = ui.launch(server_name="0.0.0.0", server_port=7860, inline=False, prevent_thread_lock=True)
```

> If you prefer to mount Gradio under FastAPI's router, keep `uvicorn app.main:app` and use `gr.mount_gradio_app`. This inline launch is the shortest path for the pre-test.

---

## `scripts/medoid_batch.py` — one-shot CLI (no XMP)

```python
#!/usr/bin/env python3
from pathlib import Path
import argparse, yaml, pandas as pd
from app.jobs import Pipeline

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-c','--config', default='config/config.yaml')
    ap.add_argument('--openai', action='store_true')
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config,'r',encoding='utf-8'))
    p = Pipeline(cfg)
    idx = pd.read_parquet('data/index.parquet')
    prox = pd.read_parquet('data/proxies.parquet')
    emb = pd.read_parquet('data/embeds.parquet')
    clu = pd.read_parquet('data/clusters.parquet')
    adf = p.medoid_ai_tags(clu, emb, prox, use_openai=args.openai)
    out = p.export_audit(clu, adf)
    print(f"Audit: {out}")

if __name__ == '__main__':
    main()
```

---

## First run (medoid pre-test)

1. Edit `config.yaml` with the deltas above (ISO 3200, prefixes, city list, OCR off).
2. Start the container (or your venv), then:

   - UI path: open `http://localhost:7860`, click **1→4**, then **5** (local) or **5b** (+Vision), then **6** to produce `data/audit.csv`.
   - Or CLI: `python scripts/medoid_batch.py --openai` (or omit `--openai`).
3. Review `data/audit.csv` and the UI grid. If satisfied, enable the write step in the UI later.

---

## Notes

- OCR will stay disabled until you say otherwise; signage will be inferred via Vision on medoids for now.
- Urbana–Champaign aliases will be recognized (`urbana`, `champaign`, `uiuc`).
- `CK:hand` is suppressed on nude clusters.
- Studio black backdrop suppresses `CK:night` with ISO ≤ **3200** and people present.

Locked in.

* Studio ISO cap: 3200 ✅
* Nudes = local only ✅
* Prefixes: CK:/AI: ✅
* Max AI tags: 12 ✅
* Apply to cluster by default ✅
* OCR: off for now (note added in project.md) ✅
* Cities and concepts loaded ✅

I’ve put the glue + UI wiring and the config deltas into a single `project.md` on the canvas. When you’re at the PC, open it and hand it to Codex as-is. If you want me to add the XMP write UI step next, say the word.

## Response:

Thought for 8s

Analysis paused

## Response:

Analysis paused

---

Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)

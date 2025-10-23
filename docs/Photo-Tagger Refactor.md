# Photo-Tagger Refactor Plan

**Authoritative instructions for Codex (or any automated agent).**

Do not improvise.

If any step fails, write a `REPORT.md` using the provided template and wait for User confirmation.

---

## 🧩 Overview

We are migrating Photo-Tagger away from Gradio and FastAPI into a **Streamlit + CLI** architecture.

Goals:

* Local CLIP tagging (deterministic, reproducible)
* Sidecar `.xmp` writing (no modification of originals)
* Cached embeddings, thumbnails, and medoids
* Minimal dependencies
* Hooks for future “discovery” modes (e.g., open-vocab models or APIs)

---

## ⚙️ Environment

* **Branch:** `streamlit-cli-refactor`
* **Python:** ≥ 3.11
* **GPU:** assume CUDA; if unavailable, fall back to CPU without crashing.
* **No Docker, no Gradio, no FastAPI.**

---

## 🧭 Step 0 – Create branch and scaffolding

```bash
git checkout -b streamlit-cli-refactor
mkdir -p app/core app/cli app/ui thumb_cache runs
```

`.gitignore`

```
__pycache__/
.venv/
thumb_cache/
runs/
*.xmp
```

✅ **Pause and confirm with User before Step 1.**

---

## 🔩 Step 1 – Implement core logic (reuse existing code)
_(This replaces the old Step 3 from prior drafts.)_

That’s a good question from Codex — and it’s right to ask.

When you merged the files, the section headers got slightly offset: **the original Step 3** was the *implementation of the core modules* (after Step 2 — creating the stubs).
The **Addendum** refers to this same step.

Here’s exactly what **Step 3** should contain — you can paste this directly into your document under the Step 3 heading if you want Codex to see it clearly:

---

## 🧩 Step 3 – Implement Core Modules (Detailed Tasks)

Implement the actual logic in the seven files under `app/core/`.
Each function already has a docstring and signature; fill in the logic using the code migrated from the previous repo.

### ✅ Modules to implement

| File            | Purpose                                          | Implementation Notes                                                                                                          |
| --------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `scan.py`       | Walk the target directory and list valid images. | Reuse logic from the old `scanner.py`. Limit to `.jpg`, `.jpeg`, `.png`. Respect `max_images`. Return list of absolute paths. |
| `thumbs.py`     | Generate cached 512 px thumbnails.               | Adapt from `proxy.py`. Use deterministic SHA-1 names. Save in `thumb_cache/`.                                                 |
| `clip_model.py` | Load CLIP and embed images / labels.             | Copy from `embed.py`. Use AMP (`torch.cuda.amp.autocast()`). Return `float32` arrays.                                         |
| `score.py`      | Compute cosine similarities and ranking.         | Already implemented per Addendum. Returns `top1`, `topk_labels`, `topk_scores`, `over_threshold`.                             |
| `medoid.py`     | Compute per-folder medoids.                      | Reuse your centroid + argmin logic. Inputs: folder→indices dict + image embeddings.                                           |
| `export.py`     | Write results CSV and sidecars.                  | Follow the Addendum: create/update `.xmp` sidecars only (via ExifTool). Use the defined CSV schema.                           |
| `labels.py`     | Load and normalize label lists.                  | Lowercase, strip, deduplicate, one label per line.                                                                            |

### ⚙️ Dependencies

Use only:

```
numpy
pandas
pillow
torch
open-clip-torch
pyyaml
tqdm
```

### 🧾 Output schema (for CSV)

```
path,rel_path,width,height,top1,top1_score,top5_labels,top5_scores,approved_labels,run_id,model_name
```

Lists are pipe-separated (`|`).

### 🧠 Sidecar policy

* Never overwrite originals.
* Command pattern:

  ```
  exiftool -P -overwrite_original -o %d%f.xmp \
           -XMP-dc:Subject+=<kw> -IPTC:Keywords+=<kw> <image>
  ```
* Batch in groups of ≤ 256 files.

When all modules pass basic import tests, continue to **Step 4 – CLI wrapper**.

---

That’s the full Step 3 description Codex was missing.
You can insert this right after “Step 2 – Create empty core modules” in your Markdown file (before Step 4).


### `scan.py`

Reuse your existing walker from `scanner.py`, but **limit to JPEG/PNG**.

Return list of absolute paths.

### `thumbs.py`

Adapt from `proxy.py`.

* Cache in `thumb_cache/`
* Long edge = 512 px
* Deterministic file names (SHA-1)

### `clip_model.py`

Lift CLIP init + batching from `embed.py`.

* Use AMP (`torch.cuda.amp.autocast()`)
* Precompute text embeddings once per label file.
* Cache image embeddings if `runs/<timestamp>/embeddings/` exists.

### `score.py`

Compute cosine similarities between image and text embeddings.

Return for each image:

```
top1, top1_score, topk_labels, topk_scores, over_threshold
```

### `medoid.py`

Copy existing centroid + argmin logic.

### `export.py`

**CSV schema**

```
path,rel_path,width,height,top1,top1_score,top5_labels,top5_scores,approved_labels,run_id,model_name
```

Lists are pipe-separated.

Use **ExifTool** for sidecars only:

```bash
exiftool -P -overwrite_original -o %d%f.xmp -XMP-dc:Subject+=<kw> -IPTC:Keywords+=<kw> <image>
```

### `labels.py`

Lowercase, strip, dedupe, load from `labels.txt`.

✅ **Confirm with User before Step 4.**

---

## 💻 Step 4 – CLI wrapper (`app/cli/tagger.py`)

Implement a single `argparse` CLI with subcommands:

```
scan | thumbs | embed | score | medoids | sidecars | export | run
```

Each calls its corresponding core function.

Write a short line to `runs/<timestamp>/log.txt` on completion.

✅ **Confirm with User before Step 5.**

---

## 🧮 Step 5 – Streamlit skeleton (`app/ui/streamlit_app.py`)

### Sidebar controls

| Field       | Type    | Notes                                                           |
| ----------- | ------- | --------------------------------------------------------------- |
| Root path   | text    | folder of images                                                |
| Labels file | text    | defaults to `labels.txt`                                        |
| Model name  | text    | e.g. ViT-L-14                                                   |
| Batch sizes | int     | 64 default                                                      |
| Threshold   | float   | 0.25 default                                                    |
| top-K       | int     | 5                                                               |
| Max images  | int     | limit for tests                                                 |
| Buttons     | actions | Scan, Thumbs, Embed, Score, Medoids, Export CSV, Write Sidecars |

### Caching

```python
@st.cache_resource  # model
@st.cache_data      # scans and thumbnails
```

### Grid

* Fixed `st.columns(6)`
* Each cell: thumbnail + filename + top-K chips + multiselect for `approved_labels`
* Buttons: “Select all over threshold”, “Clear”
* Keep a dict `approved = {path: [labels]}`

If layout breaks, generate `REPORT.md`.

✅ **Confirm with User before Step 6.**

---

## 🔗 Step 6 – Wire UI ↔ Core

Hook buttons sequentially:

1. Scan
2. Thumbs
3. Embed
4. Load labels
5. Score
6. Show grid
7. Save edits → `approved.csv`
8. Export CSV
9. Write Sidecars

✅ **Confirm with User before Step 7.**

---

## 🧾 Step 7 – Config & reproducibility

Create `config.yaml`:

```yaml
root: "/path/to/test"
labels_file: "labels.txt"
model_name: "ViT-L-14"
pretrained: "openai"
batch_images: 64
batch_labels: 64
threshold: 0.25
topk: 5
max_images: 10000
run_dir: "runs"
```

On each run:

* Save frozen config → `runs/<timestamp>/config.json`
* Save `folder_medoids.csv`:

  ```
  folder,medoid_rel_path,cosine_to_centroid
  ```

✅ **Confirm with User before Step 8.**

---

## 🧪 Step 8 – Acceptance test

Run a small set (~200 images):

```bash
python -m app.cli.tagger run --root /photos/test --labels labels.txt --threshold 0.25 --topk 5
```

Then:

* Launch Streamlit and verify grid
* Confirm CSV + sidecars appear
* Validate sidecars in ExifTool or Lightroom

If blocked, produce `REPORT.md`.

✅ **Confirm with User before Step 9.**

---

## 🔮 Step 9 – Leave hooks for discovery modes

Add TODOs (no implementation yet) in `score.py`:

* Nearest-label expansion
* Open-vocab detector hook
* Optional remote API pass (`openai_vision`)

✅ **Confirm with User to close project.**

---

## 🧾 REPORT.md Template

```markdown
# Build/Run Report

## Step that failed
<step number and name>

## Command executed
<exact command or action>

## Error output
<stderr/stdout snippet>

## Likely cause
<short hypothesis>

## Proposed fix
<one-line next action>

## What completed successfully
<bulleted list>

## Awaiting User confirmation
yes / no
```

---

## ✅ Final Checklist for this part

- [ ] Branch created and pushed
- [ ] Dependencies trimmed
- [x] Core modules stubbed (Step 2 complete)
- [x] Core logic implemented ✅ (Step 1 complete)
- [x] CLI operational ✅ (Step 4 complete)
- [x] Streamlit grid stable ✅ (Step 5 skeleton)
- [x] UI wired to core ✅ (Step 6 complete)
- [ ] CSV + XMP sidecars verified
- [ ] Medoids CSV produced
- [ ] Discovery TODOs added

---

## Next actions

- Resolve SciPy/NumPy mismatch by either pinning NumPy < 1.25 or upgrading SciPy to a build compatible with NumPy 2.x.
- Update `app/core/clip_model.py` to use `torch.amp.autocast("cuda", ...)` instead of the deprecated `torch.cuda.amp.autocast()`.

---

# ADDENDUM — Patch notes for Codex

*This addendum clarifies Step 1 details. It does not replace the plan.*

## A. Step 1 (Score): implemented

`app/core/score.py` has been implemented with cosine similarity and returns:

```python
{
  "top1": str,
  "top1_score": float,
  "topk_labels": List[str],
  "topk_scores": List[float],
  "over_threshold": List[Tuple[str,float]]
}
```

No further changes required.

## B. Step 1 (Export): sidecar policy (explicit)

When writing metadata, **create/update `.xmp` sidecars only**.

Use exiftool with sidecar output; never modify originals.

* Required flags per batch:
    - `-P -overwrite_original -m`
    - `-o %d%f.xmp`
    - For each label `kw`: `-XMP-dc:Subject+=kw -IPTC:Keywords+=kw`
* Apply in `app/core/export.py::write_sidecars()`.

## C. Step 1 (CLIP model): required signatures

`app/core/clip_model.py` must expose exactly:

```python
load_clip(model_name="ViT-L-14", pretrained="openai", device=None)
-> (model, preprocess, tokenizer, device)

embed_images(paths, model, preprocess, batch_size=64, device=None)
-> np.ndarray  # float32, shape [N,D]

embed_labels(labels, model, tokenizer, device=None, prompt="a photo of {}")
-> np.ndarray  # float32, shape [M,D]
```

* Use AMP on image embedding.
* Normalize embeddings in `score.py`, not here.

## D. Hygiene

Delete stray bytecode so imports don’t drift:

```bash
find app -name "*.pyc" -delete
```

## E. No other plan changes

* Gradio/FastAPI remain out.
* Sidecars are opt-in via the separate CLI command.
* Streamlit grid uses cached thumbnails and a fixed column count.

---

## Next action (for Codex)

* Continue the **original plan** from **Step 1 (remaining modules)** → Step 4 → Step 5, using this addendum as clarifications.
* If anything blocks, stop and produce `REPORT.md` per the template.

**End of Refactor Plan**

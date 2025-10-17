## 🗂️ **project_map.md**

### Root: `app/`

| Path              | Files | Purpose                                 |
| ----------------- | ----- | --------------------------------------- |
| `app/__init__.py` | —     | Defines the package; no logic expected. |

### Core Logic: `app/core/`

| File                | Functionality Summary                                                                                  |
| ------------------- | ------------------------------------------------------------------------------------------------------ |
| **`clip_model.py`** | Handles CLIP (or similar) model loading, embedding generation, and possibly cosine similarity scoring. |
| **`scan.py`**       | Scans directories for image files, validates paths, and builds dataset manifests.                      |
| **`labels.py`**     | Loads and manages label lists (`objects.txt`, `scenes.txt`, `styles.txt`, etc.).                       |
| **`score.py`**      | Contains scoring or classification logic (e.g., computing similarity or confidence scores).            |
| **`medoid.py`**     | Selects representative (medoid) images per cluster; used for gallery filtering.                        |
| **`thumbs.py`**     | Creates or caches thumbnails (used in Streamlit/HTML gallery).                                         |
| **`export.py`**     | Handles saving approved tags, exporting to CSV and sidecar files.                                      |

### UI Layer: `app/ui/`

| File                   | Functionality Summary                                                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **`streamlit_app.py`** | Current Streamlit-based interface, calling modules under `app/core`. This will be deprecated and replaced by the new Shadcn/React UI. |

---

## 🔒 Configuration and Environment

No `.env` or config files were detected in this archive, but it’s safe to assume:

* Any API keys (e.g., OpenAI, CLIP backends) should remain in a `.env` or OS-level variable.
* Codex must **never expose or modify environment variables** — only reference them via `os.getenv`.

If you use a `pyenv.cfg`, it’s purely metadata (safe, not sensitive).

---

## ⚙️ **backend_interface_spec.md**

### Backend Functional Layers

| Layer                 | Modules                | Description                                                           |
| --------------------- | ---------------------- | --------------------------------------------------------------------- |
| **Data ingestion**    | `scan.py`, `thumbs.py` | Scans folder, generates thumbnails, caches them for gallery.          |
| **Model embedding**   | `clip_model.py`        | Loads CLIP model and creates embeddings for all images.               |
| **Scoring & ranking** | `score.py`             | Computes similarity scores; integrates with labels.                   |
| **Label management**  | `labels.py`            | Loads label text files and provides lookup/filter functions.          |
| **Medoid selection**  | `medoid.py`            | Clustering and representative image selection.                        |
| **Export subsystem**  | `export.py`            | Outputs CSV + sidecar data for approved tags.                         |
| **Legacy UI bridge**  | `streamlit_app.py`     | (to be replaced) currently binds core logic to a Streamlit interface. |

---

### Backend API Design (to be implemented)

| Endpoint       | Method   | Calls Core              | Returns                                                             |
| -------------- | -------- | ----------------------- | ------------------------------------------------------------------- |
| `/api/gallery` | GET      | `scan.py`, `thumbs.py`  | JSON list: filename, thumb URL, medoid flag, tags, approved status. |
| `/api/tag`     | POST     | `score.py`, `export.py` | Confirms updated tag list for image.                                |
| `/api/export`  | POST     | `export.py`             | Runs export to CSV/sidecars.                                        |
| `/api/config`  | GET/POST | `labels.py`             | Returns or updates configuration parameters.                        |

---

## 🔄 Updated Reference — `UI-Refactor.md` Integration Note

Add this section at the top of your `UI-Refactor.md` file (I’ll include it when I rewrite it next):

```markdown
> 🧩 **Reference Files**
> - For backend mapping: see `project_map.md`
> - For data flow & API routes: see `backend_interface_spec.md`
> - Codex must keep all `app/core/*.py` logic unchanged.
> - The only deprecated file is `app/ui/streamlit_app.py` (replace by `/frontend/` React app).
```

---

## 🚧 Future refinements

- Reinstate per-card “Add approved labels” input once duplicate detection and semantic lookup against the label corpus are available.
- Introduce theme variants by layering additional CSS variable scopes (e.g., `.theme-slate`, `.theme-sage`) to swap palettes without touching component code.
- Confirm final badge/terminology for “Selected” vs “Saved” once end-to-end tag persistence is wired and manually testable.

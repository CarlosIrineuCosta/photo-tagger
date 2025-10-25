/stat# Photo Tagger User Guide

> ⚠️ This document is a living outline. Environment setup notes are current; other sections are stubs for upcoming GLM work once the system stabilises.

## How to Create the Environment

- Run `./reset-tagger-env.sh` whenever you need to bootstrap or refresh dependencies.
  - This script rebuilds `.venv` with Python 3.10 and exports `PYTHONNOUSERSITE=1` so no global/user-site packages leak in.
  - `start-tagger.sh` now mirrors that behaviour (Python 3.10 default, `pip/setuptools/wheel` upgrade, dev extras installed).
- For ad‑hoc commands, launch an isolated shell via `./scripts/devshell.sh` (it activates `.venv` with `PYTHONNOUSERSITE=1` set).
- After a rebuild, sanity check with:
  ```bash
  ./scripts/devshell.sh python -m pip check
  ./scripts/devshell.sh python -c "import rawpy; print(rawpy.__version__)"
  ```

## First Run

- Always start with a fresh `./reset-tagger-env.sh` if you pulled new dependencies.
- Kick off the stack with `./start-tagger.sh` (ensures backend + Vite, handles port conflicts, installs frontend deps when needed).
- RAW support is enabled by default: `config.yaml` lists `.jpg/.jpeg/.png/.dng/.cr2/.cr3/.nef/.arw/.rw2/.orf`.
- Two new config keys control runtime behaviour:
  - `max_tiff_mb`: refuse TIFFs above this size (default `1024`).
  - `apply_xmp_light`: enable RAW/XMP exposure adjustments during thumbnail generation.
- Quick validation workflow (inside the dev shell):
  ```bash
  python -m app.cli.tagger --run-dir runs scan --root tests/images
  ```
  Expect a file count close to `find tests/images -type f \( -iname '*.jpg' -o ... -iname '*.orf' \) | wc -l`.

## CLI Options

### Scan Command
```bash
python -m app.cli.tagger --run-dir runs scan --root /path/to/images [--include ...] [--max-images N] [--run-id RUN_ID]
```
- Scans the specified directory for supported image formats
- `--include`: Additional file extensions to include beyond defaults
- `--max-images`: Limit the number of images to process
- `--run-id`: Use existing run identifier instead of generating a new one

### Individual Pipeline Commands
```bash
# Generate thumbnails
python -m app.cli.tagger --run-dir runs thumbs --run-id RUN_ID [--cache-root PATH] [--max-edge SIZE] [--overwrite]

# Generate image embeddings
python -m app.cli.tagger --run-dir runs embed --run-id RUN_ID [--model-name MODEL] [--pretrained PRETRAINED] [--batch-size N] [--device DEVICE]

# Score images against labels
python -m app.cli.tagger --run-dir runs score --run-id RUN_ID --labels PATH [--topk N] [--threshold VALUE] [--prompt TEMPLATE]

# Compute medoids
python -m app.cli.tagger --run-dir runs medoids --run-id RUN_ID [--tag-aware] [--cluster-min-size N] [--cluster-mode MODE] [--embedding-threshold VALUE]

# Export results
python -m app.cli.tagger --run-dir runs export --run-id RUN_ID [--output PATH] [--approved PATH]

# Generate XMP sidecars
python -m app.cli.tagger --run-dir runs sidecars --run-id RUN_ID [--source PATH] [--column COLUMN] [--batch-size N]
```

### Full Pipeline Command
```bash
python -m app.cli.tagger --run-dir runs run --root /path/to/images [FLAGS...]
```
This command executes the complete pipeline in order:
1. Scan
2. Generate thumbnails
3. Generate embeddings
4. Score images
5. Compute medoids
6. Export results
7. Optionally write sidecars

### Additional Commands
```bash
# Compute evaluation metrics
python -m app.cli.tagger --run-dir runs metrics --dataset PATH [--k N]
```

## Using the UI

- Launch via `./start-tagger.sh`; backend listens on `127.0.0.1:8010`, frontend at `127.0.0.1:5173`.
- Workflow sidebar now streams gallery status messages with tone-aware badges (see Gallery enhanced page).

### Gallery Page

The Gallery page is your primary interface for reviewing and approving image tags:

1. **Filtering Options**:
   - **Medoids only**: Show only representative images from each cluster
   - **Unapproved only**: Show only images that haven't been reviewed yet
   - **Hide after save**: Hide images after you've saved your selections
   - **Center crop**: Change image display mode
   - **Stage filter**: Use the segmented control to jump between `New`, `Needs tags`, `Draft`, `Saved`, and `Blocked` stages. The numeric chips reflect the real-time counts returned by `/api/gallery`.

2. **Image Review**:
   - Each image shows its top-scoring labels as toggleable badges
   - Click badges to approve/disapprove labels for each image
   - Approved labels are highlighted in green
   - Selected (but not yet saved) labels are highlighted in blue

3. **Medoid Badges**:
   - Medoid images show special badges indicating their cluster type
   - **Folder medoid**: Representative of a folder cluster
   - **Tag cluster**: Representative of a tag-based cluster
   - **Embedding cluster**: Representative of an embedding-based cluster
   - Badges show cluster size and cosine similarity to centroid

4. **Actions**:
   - **Process Images**: Run the full pipeline on your image directory
   - **Save Approved**: Save your current selections
   - **Export**: Export results as CSV or XMP sidecars
   - **Prefetch thumbnails**: When new files are detected, use the blue banner to warm the thumbnail cache via `/api/thumbs/prefetch` before diving into review.

5. **Status & Telemetry**:
   - The **Processing** button triggers the CLI pipeline and streams updates into `/api/process/status`, which now exposes recent telemetry events for each run (`runs/<RUN_ID>/telemetry.jsonl`).
   - Oversized TIFFs (default limit 1 GB, configurable via `max_tiff_mb`) are marked as `Blocked` with detailed reasons so you can convert or exclude them before the next pass.
   - Run `/api/process/benchmark` (or use the UI shortcut once exposed) to capture CPU-only timing on a small sample without touching your existing review state.

### Tags Page

The Tags page is where you manage your vocabulary and promote orphan tags:

1. **Tag Groups**:
   - View and manage structured label groups (objects, scenes, styles)
   - Add new tags to existing groups
   - Remove tags from groups
   - See group statistics and file paths

2. **Orphan Tags**:
   - View tags detected in recent reviews but not yet in structured groups
   - See occurrence counts for each orphan tag
   - View ML-suggested target groups with confidence scores
   - Use "Get Suggestion" to fetch group recommendations
   - **Quick Promote**: One-click promotion to suggested groups
   - **Promote**: Open detailed promotion dialog with more options

3. **Bulk Promotion**:
   - Select multiple orphan tags using checkboxes
   - Open bulk promotion drawer to promote multiple tags at once
   - Customize target groups for each selected tag
   - View promotion results with success/failure status

4. **Graduation Review**:
   - Review pending tag graduations grouped by canonical label
   - See all promoted tags that share the same canonical label
   - **Resolve**: Mark graduations as complete
   - **Skip**: Dismiss graduations without resolving
   - View statistics for pending and resolved graduations

### Configuration Page

The Configuration page allows you to adjust system settings:

1. **Paths**: Configure file paths for labels, run directory, and cache
2. **Model Settings**: Adjust CLIP model parameters
3. **Processing Settings**: Configure batch sizes and thresholds
4. **UI Settings**: Adjust display preferences

### Status Log

The status log (bottom-right) shows real-time system messages:
- **Info**: General information messages
- **Success**: Successful operation completions
- **Error**: Error messages with details
- **Warning**: Non-critical issues

### Troubleshooting

- **Images not loading**: Check that your image directory is correctly configured
- **No tags detected**: Ensure your labels file is properly formatted
- **Slow performance**: Consider reducing batch sizes or image limits
- **Error messages**: Check the status log for detailed error information

## Medoids Workflow

The medoids workflow helps you quickly evaluate the quality of your label clusters by reviewing representative images:

### When to Run Medoids
After completing an end-to-end pipeline pass (`scan → embed → score → export`), run the medoids computation:
```bash
python scripts/run_medoids.py
```

### Medoid Types
1. **Folder Medoids**: Representative images from each folder structure
2. **Tag Cluster Medoids**: Representative images for each tag cluster (when using tag-aware mode)
3. **Embedding Cluster Medoids**: Representative images from embedding-based clusters (when using hybrid mode)

### Reviewing Medoids in the UI
1. Open the Gallery page
2. Toggle **Medoids only** to show only medoid images
3. Review the badges on each medoid to understand its cluster type
4. Click into any medoid to review the full cluster in context

### Helper Script Options
The `scripts/run_medoids.py` script supports several options:
- **Mode**: Choose between folder-only, tag-aware, or hybrid clustering
- **Thresholds**: Adjust similarity thresholds for clustering
- **Output**: Specify custom output path for medoids CSV

### Interpreting Medoids
Use medoids to answer:
- Does the cluster match the canonical tag? If not, consider renaming or adding synonyms.
- Do you see new tags that should join the structured pack? Promote them via the Tags page.
- Are there cluttered clusters that need better thresholds or alternate group splits?

### What Medoids Do Not Do
- They do **not** promote tags automatically
- They do **not** replace orphan-tag analysis
- They are a visual sanity check that complements the orphan-tag brief

## RAW File Handling

The system supports processing RAW files from various camera manufacturers:

### Supported RAW Formats
- **Canon**: `.cr2`, `.cr3`
- **Nikon**: `.nef`
- **Sony**: `.arw`
- **Olympus**: `.orf`
- **Panasonic**: `.rw2`
- **Adobe**: `.dng`
- And standard formats: `.jpg`, `.jpeg`, `.png`

### RAW Processing Tips
1. **Performance**: RAW files are larger than JPEGs and require more processing time
   - Consider using `--max-images` to limit the number of RAW files during testing
   - RAW processing benefits from GPU acceleration when available

2. **Thumbnail Generation**: RAW thumbnails are extracted using embedded preview images
   - If thumbnails appear low quality, the embedded preview might be small
   - Full-size RAW processing happens during embedding, not thumbnailing

3. **Storage Considerations**:
   - RAW files require more disk space for thumbnails cache
   - Ensure adequate space in your thumbnail cache directory
   - Consider using an SSD cache directory for better performance

4. **Color Accuracy**: RAW files maintain better color fidelity than compressed formats
   - This can result in more accurate CLIP embeddings
   - Consider using RAW files for critical applications where color accuracy matters

---

### Tag Promotion Workflow

The system provides a comprehensive workflow for managing orphan tags:

1. **Discovery**: Orphan tags are automatically detected during image scoring
2. **Suggestion**: ML heuristics suggest appropriate groups for each orphan tag
3. **Quick Promotion**: One-click promotion to suggested groups
4. **Bulk Promotion**: Promote multiple tags at once with custom group assignments

5. **LLM Enhancement (preview)**:
   - The UI now gates LLM-based tag suggestions behind a preview flag.
   - Backend stub `/api/llm/tags/enhance` echoes normalized tags and placeholder suggestions so the frontend contract can stabilise ahead of the real model.
5. **Graduation Review**: Review and resolve pending graduations grouped by canonical label

### Best Practices

1. **Start with Quick Promote**: Use the one-click promotion for high-confidence suggestions
2. **Review in Batches**: Use bulk promotion to efficiently handle multiple orphan tags
3. **Regular Graduation Review**: Periodically review the graduation panel to resolve pending promotions
4. **Monitor Suggestions**: Pay attention to confidence scores when reviewing ML suggestions
5. **Maintain Consistency**: Use the graduation review to ensure consistent canonical labels

---

### Pending Additions (for GLM follow-up)

- Capture screenshots/log snippets once the interface stabilises
- Add performance benchmarks for RAW file processing
- Document advanced configuration options for power users
- Create troubleshooting guide for common issues

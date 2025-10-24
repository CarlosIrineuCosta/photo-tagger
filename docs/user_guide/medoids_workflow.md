# Medoid Selection Strategy & Review Workflow

Medoids highlight representative images from each label cluster so you can judge
quality quickly before promoting tags or pruning vocabulary. They are an
operator tool; nothing happens automatically until you decide what to promote.

The medoid command picks a representative image per folder and can expose
clusters that deserve a closer look. It now supports two clustering modes:

- **simple** (default): optionally group images by their top tags and compute a
  medoid per tag cluster.
- **hybrid**: perform the tag pass and then run an embedding-based sweep to
  gather remaining images into high-similarity clusters.

## CLI Usage

```
python -m app.cli.tagger medoids --run-id RUN123 --cluster-mode hybrid \
  --tag-aware --cluster-min-size 2 \
  --embedding-threshold 0.86 --max-embedding-clusters 4
```

Key flags:

| Flag | Description |
| --- | --- |
| `--cluster-mode {simple,hybrid}` | choose clustering strategy |
| `--tag-aware` | enable tag-derived clusters |
| `--cluster-min-size` | minimum members required for tag clusters |
| `--embedding-threshold` | cosine similarity threshold for embedding clusters |
| `--max-embedding-clusters` | limit embedding clusters per folder (`0` = unlimited) |

Each CSV row now includes `cluster_type` and `label_hint` to make it easy to
distinguish folder-level medoids, tag clusters, and embedding clusters.

```
folder,cluster_type,cluster_tag,label_hint,cluster_size,medoid_rel_path,cosine_to_centroid
atlanta-trip,folder,,,"12","20240214/IMG_1234.jpg","0.912345"
atlanta-trip,tag,skyline,skyline,"4","20240214/IMG_1229.jpg","0.945678"
atlanta-trip,embedding,,embedding_1,"3","20240214/IMG_1238.jpg","0.921004"
```

Tag clusters inherit the tag as their `label_hint`. Embedding clusters receive
auto-generated hints (`embedding_1`, `embedding_2`, …) while tracking the member
indices internally for downstream tooling.

When the API serves gallery data it now marks medoid images and surfaces the
first three cluster badges (folder, tag, embedding) so reviewers can see why an
image was chosen without opening the CSV. The enhanced gallery view reuses the
same metadata, making medoid triage consistent across both experiences.

## When to Run

After every end‑to‑end pipeline pass (`scan → embed → score → export`):

1. Finish scoring/exporting a run (via CLI or Process Images button).
2. Run the helper script to regenerate medoids for the latest run:
   ```bash
   python scripts/run_medoids.py
   ```
   * Accept the default `hybrid` mode (folder + tag + embedding clusters) or
     pick mode/thresholds you prefer.
   * The script writes `runs/<RUN_ID>/medoids.csv` (used by the app) and keeps a
     copy under `docs/runs/<RUN_ID>_medoids.csv` for reference.
3. Restart the dev server if it was already running (the helper prints the path
   so you can double‑check the file landed).

## Reviewing in the UI

1. Open the Gallery page.
2. Toggle **Medoids only**. Every medoid is flagged with badges:
   * Folder medoid (always present)
   * Tag cluster medoids (if `--tag-aware` was enabled)
   * Embedding clusters (if using hybrid mode)
3. Click into any medoid to review the full cluster in context.

Use this pass to answer:
- Does the cluster match the canonical tag? If not, we may need to rename or
  add synonyms.
- Do we see new tags that should join the structured pack? Promote them via the
  Tags page (single or bulk) once the new flow lands.
- Are there cluttered clusters that need better thresholds or alternate group
  splits?

## What Medoids Do *Not* Do

- They do **not** promote tags automatically.
- They do **not** replace orphan-tag analysis. Treat them as a quick visual
  sanity check that complements the orphan‑tag brief.

Once GLM finishes the bulk promotion/graduation UI, these medoid badges will
feed into promotion dialogs so the workflow becomes "review medoid → promote
or adjust tags" without leaving the app.

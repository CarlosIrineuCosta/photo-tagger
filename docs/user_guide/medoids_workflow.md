# Medoid Review Workflow

Medoids highlight representative images from each label cluster so you can judge
quality quickly before promoting tags or pruning vocabulary. They are an
operator tool; nothing happens automatically until you decide what to promote.

## When to Run

After every end‑to‑end pipeline pass (`scan → embed → score → export`):

1. Finish scoring/exporting a run (via CLI or the Process Images button).
2. Run the helper script to regenerate medoids for the latest run:
   ```bash
   python scripts/run_medoids.py
   ```
   * Accept the default `hybrid` mode (folder + tag + embedding clusters) or
     pick the mode/thresholds you prefer.
   * The script writes `runs/<RUN_ID>/medoids.csv` (used by the app) and keeps a
     copy under `docs/runs/<RUN_ID>_medoids.csv` for reference.
3. Restart the dev server if it was already running (the helper prints the path
   so you can double‑check the file landed).

## Reviewing in the UI

1. Open the Gallery page.
2. Toggle **Medoids only**. Every medoid is flagged with badges:
   * Folder medoid (always present)
   * Tag cluster medoids (if `--tag-aware` was enabled)
   * Embedding clusters (if using the hybrid mode)
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
feed into the promotion dialogs so the workflow becomes “review medoid → promote
or adjust tags” without leaving the app.

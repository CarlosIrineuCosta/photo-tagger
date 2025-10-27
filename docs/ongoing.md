# // Ongoing Work

## Active Session Plan (2025-10-25)

## Active Session Plan (2025-10-27)

### Shared Focus

- [ ] Establish reliable ingestion of exposure compensation and white balance temperature from existing XMP sidecars, and verify the data flows from pipeline to UI without regressions.
- [ ] Capture representative dark-exposure samples so all assistants can exercise the metadata path while guarding highlight preservation use cases.

### Codex 2025-10-27 – XMP Metadata Pipeline

- [ ] Audit current metadata loaders (`app/core/scan.py`, related helpers) to document how EXIF/XMP is parsed today and what fields reach downstream stages.
- [ ] Prototype XMP parsing for exposure (`Exposure2012`, `ExposureCompensation`, `crs:Exposure`) and color temperature (`ColorTemperature`, `WhiteBalance`, `crs:Temperature`) using existing dependencies; surface normalized values in the scan payload or a new metadata structure.
- [ ] Add regression coverage (unit + smoke fixture) ensuring the parsed exposure and temperature values persist through telemetry/run artifacts for Gemini + GLM consumers.

### GLM 2025-10-27 – UI Surfacing

- [ ] Coordinate with Codex on the metadata shape, then bind the new exposure + temperature fields into gallery/detail views (consider histogram overlays or metadata tooltips without new CLI steps).
- [ ] Update review UI affordances to highlight when imported XMP adjustments differ from computed scores, so operators can quickly triage dark-shot corrections.
- [ ] Validate that existing thumbnail and stage components remain stable when the new metadata arrives, adding Vitest coverage if needed.

### Gemini 2025-10-27 – Pipeline Validation

- [ ] Supply or curate sample images + XMP sidecars that cover underexposed, neutral, and corrected cases; document the dataset path in `tests/smoke/`.
- [ ] Extend the CLI smoke test to assert exposure/temperature propagation (runs/<timestamp>/telemetry.jsonl + cache summaries) and capture before/after metrics.
- [ ] Cross-check parsed values against Lightroom or other ground truth exports to confirm fidelity and note any normalization edge cases for follow-up.

### Shared Focus

- [ ] Confirm that Photo Tagger stack boots cleanly (FastAPI + Vite + CLI) after resolving `ThumbPrefetchResponse` import failure logged in `backend.log`.
- [ ] Coordinate Codex, GLM, and Gemini hand-off now that GLM capacity is restored; ensure UI, backend, and pipeline validation run in parallel.

### Codex 2025-10-25 – Backend Bring-up

- [x] Deduplicate and export `ThumbPrefetchRequest`/`ThumbPrefetchResponse` Pydantic models in `backend/api/index.py` so that `/api/thumbs/prefetch` route no longer triggers a NameError during import.
- [x] Re-run backend startup (`./start-tagger.sh` or equivalent `uvicorn` invocation) to validate a clean launch; capture any residual errors or warnings in `backend.log`.
- [x] Document next validation steps for thumb prefetch (API call sequence, expected telemetry) so GLM and Gemini can verify their parts once the server is stable.

  - Call `POST /api/thumbs/prefetch` with `{"paths": ["<abs-image-path>"], "overwrite": false}`; 200 response should include a `job_id` and number of thumbnails `scheduled`.
  - Call `GET /api/thumbs/prefetch/{job_id}` to confirm the status payload (`status`, `processed`, `total`, `errors`) reflects completed work.
  - Because the job runs inline today, verify that requested files appear in `thumb_cache/` immediately after the call (the response returns as soon as processing finishes).
  - Tail `backend.log` for `Thumbnail prefetch job …` log line; capture any reported errors and corresponding paths so Gemini can reproduce them in the CLI smoke test.
- [x] Add regression coverage for gallery summary counts and stage filtering (`tests/test_gallery_api.py`); patch telemetry persistence to serialize `TelemetryEvent` safely.
- [ ] Investigate residual UI anomalies by comparing live `/api/gallery` responses against the new tests; document any discrepancies that remain after GLM/Gemini updates.

### GLM 2025-10-25 – UI Integration

- [x] Wire up gallery/thumbnail UI to consume `/api/thumbs/prefetch` responses (job id, scheduled count) and display queued/processing states in the React components responsible for cache warming.
- [x] Add defensive error handling for thumb prefetch failures (surface toast + sidebar log entry) to avoid blocking the gallery when the backend returns 500s.
- [x] After Codex confirms backend stability, run the gallery smoke scenario to ensure thumbnails render and stage filters continue to work with the new prefetch flow.
- [ ] Stabilize `GalleryPage.test.tsx`/`GalleryStageFilters.test.tsx` so Vitest exits cleanly in CI (mock IntersectionObserver + Enhanced API without real network calls).
- [ ] Replace placeholder screenshot artifacts with actual captures by running `./scripts/run_gallery_screenshots.sh` on a GUI-enabled machine; remove `scripts/generate_screenshots.py` once real PNGs exist.
- [ ] Tidy up enhanced gallery layout (spacing, counter placement, toggle behaviour) after automation passes; ensure “All/New/Needs tags/Saved/Blocked” views surface the full inventory without pagination gaps.

### Gemini 2025-10-25 – Pipeline Reliability

- [x] Run a CLI smoke test (`python -m app.cli.tagger run --root tests/smoke/photos`) to confirm the end-to-end pipeline completes with the updated thumb prefetch job definitions.
- [x] Inspect the resulting run artifacts (`runs/<timestamp>/telemetry.jsonl` and cache entries) to verify that thumb prefetch telemetry is recorded without schema regressions.
- [x] Update any relevant operator docs if the cache or telemetry formats changed as part of the new prefetch job flow.
- [x] Refresh the smoke dataset and publish a trimmed `runs/api_state.json` fixture aligned with `tests/test_gallery_api.py`; share the fixture path with GLM so UI automation and screenshots operate on identical data.
- [x] Summarize current pipeline timing (scan/thumb/embed/score) from the latest telemetry to feed into future RAW-ingestion optimisation work.
- [x] Run `pytest tests/test_gallery_api.py` to confirm that the new fixture and regression coverage stay green after the refresh.
- [x] Ensure `tests/fixtures/api_state.json` is tracked in Git and prune any redundant keys that UI/backend automation does not consume (keep the fixture lean for Playwright runs).
- [ ] Draft `labels/label_pack.yaml` scaffold (tier, aliases, equivalences) plus loader notes so we can start the structured label work.
- [ ] Prototype a CLI helper (or `python -m app.cli.tagger medoids --regen`) that triggers medoid regeneration and emits summary stats for dashboards.

## Smoke Test Performance (2025-10-26)

Observed processing times from smoke test run `20251026-001309`:

*   **Scan:** 0.52 ms
*   **Thumbs:** 17.25 ms
*   **Embed:** 6450.72 ms
*   **Score:** 7419.69 ms

**Conclusion:** The embedding and scoring steps are the most time-consuming parts of the pipeline. Future optimization efforts should focus on these areas.

## Backlog Overview

### Pipeline & Data Quality

- [ ] Investigate slow RAW thumbnail generation (rawpy path) and cache optimisation strategies.
- [x] Document current RAW ingestion telemetry and potential optimisation levers (`docs/raw_ingestion_notes.md`).
- [ ] Tag corpus management – finish enhanced tagging workflow: orphan promotion, bulk actions, and graduation path for user-added labels.
- [ ] Structured label pack YAML – draft `labels/label_pack.yaml` with canonical IDs, aliases, and disambiguation lists for deterministic scoring.
- [ ] Label quality – iterate structured label pack (`labels/`), maintain evaluation set, and log precision/recall after each tweak.
- [ ] Automate medoid regeneration during `tagger run` and persist summary stats for dashboards.
- [ ] Draft automated pipeline surfacing new user tags for review/export (CSV of recent additions, optional delete flow).
- [ ] Outline API automation for review state (init, approve, exclude) for batch QA scripting.

### UI & Review Experience

- [ ] Surface gallery stage summary chips using `summary.counts` and tie them to segmented control selections.
- [ ] Add inline help tooltips/modal explaining ReviewStage meanings directly in the gallery UI.
- [ ] Polish Tags page ergonomics (keyboard navigation + bulk action bins) and capture a short demo clip for release notes.
- [ ] Review stack controls – expose per-image `k`, stack progress indicators, and API endpoints for scripted approvals/exclusions.

### QA & Validation

- [ ] Refresh runs to capture current orphan tags, then walk the updated Tags page.
- [ ] Promote every synonym cluster encountered during a 100-image validation slice; note source tag, chosen group, and rationale.
- [ ] Record QA log (timestamp, image id or sample, action taken, friction notes) in the shared tracker.
- [ ] Re-run validation after promotions to confirm orphan tally and highlight any lingering duplicates.
- [ ] Capture evaluation metrics (Precision@K, stack coverage, time-to-review) on curated image set; refresh smoke fixtures for synonym-heavy cases.

### Infrastructure & Deployment

- [ ] Production packaging – update Dockerfile for frontend build, static asset bundle, and FastAPI launch via `uvicorn`, then validate for VPS deploy.
- [ ] Operations documentation – refresh `initial_setup.md` and operator notes with `./start-tagger.sh`, label-pack workflow, and MVP recovery checklist.
- [ ] Decide whether CLIP inference remains CPU-only on VPS or requires remote GPU resources (document trade-offs).
- [ ] Determine secure RAW upload flow for testers (S3, rsync, portal) and privacy guarantees.
- [ ] Evaluate making `/api/process` asynchronous to keep API responsive during long pipelines.
- [ ] Add operator tooling for cache maintenance (clear thumbnails, refresh embeddings, wipe run history).

### Future Enhancements

- [ ] Expand label packs with additional tiers/localization post-scoring validation.
- [ ] Refine UI affordances (Saved vs Selected badges, progress feedback) after more review sessions are captured.
- [ ] Investigate queueing/monitoring for concurrent remote runs.
- [ ] Revisit gallery pagination/infinite scrolling once we can track active review position.

# Photo Tagger – Pending Evaluation (Codex, 2025‑10‑24)

This document captures the current system assessment, reconciles Codex findings with prior guidance (`docs/next_steps_GLM_20251024.md`, `docs/system_evaluation_and_improvements.md`), and outlines the API‑centric plan now marked as **ongoing**.

## 1. Current Standing

- **Workflow signals** – `backend/api/index.py:483` returns only `selected`/`saved`, so the UI cannot distinguish “never processed”, “generated but unsaved”, or “saved then modified”. The XOR filters in `frontend/src/pages/GalleryPage.tsx:138` therefore misclassify work states.  
- **Incremental ingestion** – `app/core/scan.py` simply lists files; neither the API nor frontend tracks deltas when new assets enter an existing folder. There is no notion of `new_since_last_run` required by requirements (points 2, 5, 8).  
- **Thumbnails & RAW** – `app/core/thumbs.py:70` eagerly processes RAW/TIFF without size checks or XMP-aware exposure tweaks, conflicting with requirements 7, 8, 10.  
- **Medoids** – `app/core/medoid.py` supports hybrid clustering but lacks heuristics for highly variable shoots and exposes limited metadata to the UI; current gallery payload only includes `medoid` boolean.  
- **Gallery performance** – `/api/gallery` emits full dataset (bounded only by `max_images`), and CommandBar still exposes fixed page sizes; lazy loading from `docs/next_steps_GLM_20251024.md` and `docs/system_evaluation_and_improvements.md` isn’t wired.  
- **Tags management** – `frontend/src/pages/TagsPage.tsx` renders full tables with checkboxes; no virtualization or pill-style interactions, so requirement 14 remains unmet.  
- **Deployment readiness** – `/api/process` shells into the pipeline synchronously, assumes GPU by default, and offers no timing telemetry or CPU mode insights (requirement 9).  
- **Future extensibility** – No modular entry point for upcoming LLM-assisted tagging (requirement 13); only placeholder references in docs.  
- **Error recovery** – State storage `runs/api_state.json` lacks timestamps or error markers, complicating recovery flows highlighted in the user prompt.

## 2. Requirements Mapping & Spec Suggestions

The items below align with the 15 user requirements while integrating prior GLM/Gemini guidance. All changes are API-first (no CLI UX exposure).

1. **Single-folder tagging workflow**  
   - Introduce `app/state/models.py` with `ReviewStage` enum (`NEW`, `NEEDS_TAGS`, `HAS_DRAFT`, `SAVED`, `BLOCKED`).  
   - Extend backend gallery payload with `stage`, `first_seen`, `last_reviewed`. UI renders “Next actions” panel keyed to this enum.

2. **Action coverage (retag, partial tag)**  
   - `/api/process` gains `scope` parameter: `{"mode":"all"|"new"|"modified","paths":[...]}` defaulting to new + modified files only.  
   - Persist `last_processed_at` per path; diff performed via API-managed cache (no CLI invocation).

3. **File state tracking**  
   - Maintain per-image record: `{"stage": ReviewStage, "approved_labels": [...], "generated_at": ..., "saved_at": ...}` in `api_state.json`.  
   - Add migration that infers stage: saved==true → `SAVED`; saved==false && selected->`HAS_DRAFT`; missing entry→`NEW`.

4. **Filters clarity**  
   - Replace the boolean trio with segmented control: `To Tag`, `Needs Review`, `Saved`, `All`, `Blocked`.  
   - Frontend hook example:  
     ```ts
     export function useStageFilter(items: GalleryItem[], active: ReviewStageFilter) { /* ... */ }
     ```

5. **New file awareness**  
   - `scan_directory` returns `(paths, metadata)` where metadata includes `mtime` and `size`.  
   - API computes diff vs. `state["images"]` to surface `new_files_count` and `modified_files`.  
   - UI shows banner: “Detected X new files – warm previews?” with call into thumbnail prefetch endpoint.

6. **Lazy loading & infinite scroll**  
   - Replace `/api/gallery` with `/api/gallery/page?cursor=...&limit=60`, returning `{"items":[],"next_cursor":...,"total":...}`.  
   - Frontend uses `useIntersectionObserver` (already available per `ongoing.md`) to request next page; remove page-size toggle.

7. **Large TIFF guardrail**  
   - During scan, classify TIFF > configurable cap (default 1GB) as `BLOCKED` with `blocked_reason`.  
   - UI badge explains refusal; API allows override via explicit `scope.paths` for advanced users.

8. **Thumbnail cache priming**  
   - Add `/api/thumbs/prefetch` accepting list of paths; runs asynchronous task queue (e.g., FastAPI `BackgroundTasks`) to call `thumbs.build_thumbnails`.  
   - Gallery entries with pending thumbs expose `thumb_status: "pending"` so cards render placeholders.

9. **VPS / CPU mode readiness**  
   - Config holds `inference_device` and `model_variant`. Provide `/api/process/benchmark` to time a short batch and log into run metadata.  
   - Document CPU fallback cost in `docs/deployment.md`; `Process` endpoint returns ETA + telemetry.

10. **RAW + XMP adjustments**  
   - Enhance `thumbs.build_thumbnail` to parse companion `.xmp` for `Exposure2012`, `Temperature`, `Tint`. Apply corrections via `rawpy.postprocess` (toggleable `apply_xmp_light`).  
   - Cache parsed adjustments keyed by SHA1 to avoid repeated XML parsing.

11. **Medoid robustness**  
   - Extend medoid output with `cluster_summary` (size, cosine, label_hint) surfaced to frontend.  
   - Adjust `DEFAULT_MAX_EMBEDDING_CLUSTERS` dynamically based on folder variance (e.g., filename entropy, EXIF capture span).  
   - Add unit tests covering high-variance dataset.

12. **Ingestion pipeline refinement**  
   - Sequence orchestrated via API: detect delta → ensure thumbnails → queue embeddings/medoids for affected files only.  
   - Expose pipeline progress via `/api/process/status` with stage-level counters for recovery insight.

13. **LLM-ready extension point**  
   - Define placeholder FastAPI router (`backend/api/llm_tags.py`) with POST schema returning mock results.  
   - Frontend `EnhancedTaggingAPI` should call this new route when feature flag enabled.

14. **Scalable tags UI**  
   - Replace tables with virtualized pill list (e.g., `@tanstack/react-virtual`). Provide bulk add/remove via drag bins.  
   - Add search, frequency badges, and grouping (objects/scenes/styles) as per docs guidance.

15. **Faster initial rendering**  
   - Initial fetch split into summary endpoint plus streaming first page.  
   - Use skeleton cards; hydrate as `/api/gallery/page` responses land. Logging into status strip clarifies progress.

## 3. Testing & Telemetry

- **Unit tests**: review-stage transitions, TIFF blocking, thumbnail XMP adjustments, medoid heuristics.  
- **Integration tests**: large folder pagination, CPU benchmark, process recovery after interruption.  
- **Operational telemetry**: Structured logs per stage (`stage`, `elapsed_ms`, `item_count`) persisted in run metadata for postmortems.

## 4. Next Actions

1. Finalize API schemas (`ReviewStage`, paginated gallery, process scope).  
2. Implement backend deltas + thumbnail prefetch, then wire frontend filters & lazy loading.  
3. Instrument pipeline telemetry and benchmark endpoints for VPS readiness.  
4. Schedule tags UI overhaul and medoid visualization as subsequent sprint once core workflow stabilizes.  
5. When ready for LLM integration, promote placeholder router to live service without altering current contracts.

This evaluation supersedes ad-hoc test helpers; state recovery will rely on the structured `stage` and telemetry fields described above.

# Ongoing Work

## Active Session Plan (2024-00-00) <!-- replace date on close-out -->

### Architect / Coding (Assistant)

- [x] Convert ongoing tracking doc into actionable checkbox format. <!-- keep history -->
- [x] Backend/API: add orphan-to-group promotion endpoint with audit logging.
- [x] Frontend: add promote-orphan dialog on `TagsPage` with search + quick-create group flow.
- [x] CLI: extend `app/cli/tagger run` with `--export-new-tags` CSV emitter for recent additions.
- [x] Core: introduce tag-aware clustering toggle in `app/core/medoid.py` and cover with smoke test.
- [x] Align blocking overlays with warning tone across processing states.
- [x] Skip redundant gallery processing when no updates are pending.

### GLM Assist (trigger after core changes are ready)

- [x] Generate `app/util/metrics.py` with `compute_precision_at_k`, `compute_stack_coverage`, and `load_eval_dataset`.
- [x] Update `app/cli/tagger.py` with `metrics` subcommand using the new utilities.
- [x] Draft `docs/metrics.md` documenting metric definitions, dataset prep, and CLI usage.
- [x] Create `frontend/src/hooks/useIntersectionObserver.ts` for intersection observation.
- [ ] Wire hybrid promotion UI on `TagsPage`: fetch suggestion metadata, surface single-click promote actions, and implement optimistic updates with rollback on failure.
- [ ] Build bulk promotion drawer with multi-select table, status toasts, and retry queue using the `/api/tags/promote/bulk` endpoint.
- [ ] Add graduation review panel that reads `pending_graduations`, enables grouping by canonical label, and exposes resolve/skip flows persisted to the manifest ledger.

### Operator / QA (run once UI shipping)

- [ ] Refresh runs to capture current orphan tags, then walk the updated Tags page.
- [ ] Promote every synonym cluster encountered during a 100-image validation slice; note source tag, chosen group, and rationale.
- [ ] Record QA log (timestamp, image id or sample, action taken, friction notes) in the shared tracker.
- [ ] Re-run validation after promotions to confirm orphan tally and highlight any lingering duplicates.

## Tags and Medoids

- [ ] Extend Tags page so orphan tags can be promoted directly into chosen groups (single-click add).
- [ ] Tag corpus management – finish enhanced tagging workflow: orphan promotion, bulk actions, and graduation path for user-added labels.
- [ ] Structured label pack YAML – draft `labels/label_pack.yaml` with canonical IDs, aliases, and disambiguation lists for deterministic scoring.
- [x] Design clustering strategy for medoids (per dominant tag/embed cluster) and prototype on mixed-content folder.
- [ ] Label quality – iterate structured label pack (`labels/`), maintain evaluation set, and log precision/recall after each tweak.
- [x] Evolve medoid selection with tag/embedding clustering before medoid choice for mixed folders.
- [ ] Review stack controls – expose per-image `k`, stack progress indicators, and CLI helpers for scripted approvals/exclusions.
- [ ] Draft automated pipeline surfacing new user tags for review/export (CSV of recent additions, optional delete flow).
- [ ] Outline CLI automation for review state (init, approve, exclude) for batch QA scripting.
- [ ] Capture evaluation metrics (Precision@K, stack coverage, time-to-review) on curated image set; refresh smoke fixtures for synonym-heavy cases.

## Infrastructure & Operations

- [ ] Production packaging – update Dockerfile for frontend build, static asset bundle, and FastAPI launch via `uvicorn`, then validate for VPS deploy.
- [ ] Operations documentation – refresh `initial_setup.md` and operator notes with `./start-tagger.sh`, label-pack workflow, and MVP recovery checklist.
- [ ] Decide whether CLIP inference remains CPU-only on VPS or requires remote GPU resources (document trade-offs).
- [ ] Determine secure RAW upload flow for testers (S3, rsync, portal) and privacy guarantees.
- [ ] Evaluate making `/api/process` asynchronous to keep API responsive during long pipelines.
- [ ] Add operator tooling for cache maintenance (clear thumbnails, refresh embeddings, wipe run history).

## Future Enhancements

- [ ] Expand label packs with additional tiers/localization post-scoring validation.
- [ ] Refine UI affordances (Saved vs Selected badges, progress feedback) after more review sessions are captured.
- [ ] Investigate queueing/monitoring for concurrent remote runs.
- [ ] Revisit gallery pagination/infinite scrolling once we can track active review position.

## Discussion Items / Open Questions

- [ ] Decide whether CLIP inference remains CPU-only on VPS or requires remote GPU resources (document trade-offs).
- [ ] Determine secure RAW upload flow for testers (S3, rsync, portal) and privacy guarantees.
- [ ] Evaluate making `/api/process` asynchronous to keep API responsive during long pipelines.

## Recent Progress

- [x] Landed enhanced tagging manager (backend + CLI helpers) with synonym handling and tag stacks.
- [x] Shipped enhanced gallery UI with exclusion buttons, user-tag insertion, blocking overlays, and reliable save flow.
- [x] Added `/api/tags` endpoints plus Tags admin page for reviewing label groups, managing tags, surfacing orphans.
- [x] Introduced reusable blocking overlay component with consistent loading/saving states across gallery.
- [x] Implemented metrics module with Precision@K and stack coverage calculations.
- [x] Added metrics CLI subcommand for evaluation dataset analysis.
- [x] Created useIntersectionObserver hook for frontend intersection detection.

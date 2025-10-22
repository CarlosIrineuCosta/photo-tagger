# Ongoing Work

## Active Session Plan (2024-00-00) <!-- replace date on close-out -->

### Architect / Coding (Assistant)

- [x] Convert ongoing tracking doc into actionable checkbox format. <!-- keep history -->
- [x] Backend/API: add orphan-to-group promotion endpoint with audit logging.
- [x] Frontend: add promote-orphan dialog on `TagsPage` with search + quick-create group flow.
- [x] CLI: extend `app/cli/tagger run` with `--export-new-tags` CSV emitter for recent additions.
- [x] Core: introduce tag-aware clustering toggle in `app/core/medoid.py` and cover with smoke test.

### GLM Assist (trigger after core changes are ready)

- [x] Generate `app/util/metrics.py` with `compute_precision_at_k`, `compute_stack_coverage`, and `load_eval_dataset`.
- [x] Update `app/cli/tagger.py` with `metrics` subcommand using the new utilities.
- [x] Draft `docs/metrics.md` documenting metric definitions, dataset prep, and CLI usage.

### Operator / QA (run once UI shipping)

- [ ] Refresh runs to capture current orphan tags, then walk the updated Tags page.
- [ ] Promote every synonym cluster encountered during a 100-image validation slice; note source tag, chosen group, and rationale.
- [ ] Record QA log (timestamp, image id or sample, action taken, friction notes) in the shared tracker.
- [ ] Re-run validation after promotions to confirm orphan tally and highlight any lingering duplicates.

## Short-Term Priorities

- [ ] Production packaging – update Dockerfile for frontend build, static asset bundle, and FastAPI launch via `uvicorn`, then validate for VPS deploy.
- [ ] Operations documentation – refresh `initial_setup.md` and operator notes with `./start-tagger.sh`, label-pack workflow, and MVP recovery checklist.
- [ ] Label quality – iterate structured label pack (`labels/`), maintain evaluation set, and log precision/recall after each tweak.
- [ ] Tag corpus management – finish enhanced tagging workflow: orphan promotion, bulk actions, and graduation path for user-added labels.
- [ ] Structured label pack YAML – draft `labels/label_pack.yaml` with canonical IDs, aliases, and disambiguation lists for deterministic scoring.
- [ ] Review stack controls – expose per-image `k`, stack progress indicators, and CLI helpers for scripted approvals/exclusions.

## Discussion Items / Open Questions

- [ ] Decide whether CLIP inference remains CPU-only on VPS or requires remote GPU resources (document trade-offs).
- [ ] Determine secure RAW upload flow for testers (S3, rsync, portal) and privacy guarantees.
- [ ] Evaluate making `/api/process` asynchronous to keep API responsive during long pipelines.

## Backlog / Future Enhancements

- [ ] Add operator tooling for cache maintenance (clear thumbnails, refresh embeddings, wipe run history).
- [ ] Expand label packs with additional tiers/localization post-scoring validation.
- [ ] Refine UI affordances (Saved vs Selected badges, progress feedback) after more review sessions are captured.
- [ ] Investigate queueing/monitoring for concurrent remote runs.
- [ ] Evolve medoid selection with tag/embedding clustering before medoid choice for mixed folders.

## Recent Progress

- [x] Landed enhanced tagging manager (backend + CLI helpers) with synonym handling and tag stacks.
- [x] Shipped enhanced gallery UI with exclusion buttons, user-tag insertion, blocking overlays, and reliable save flow.
- [x] Added `/api/tags` endpoints plus Tags admin page for reviewing label groups, managing tags, surfacing orphans.
- [x] Introduced reusable blocking overlay component with consistent loading/saving states across gallery.

## Next Session Starting Point

- [ ] Extend Tags page so orphan tags can be promoted directly into chosen groups (single-click add).
- [ ] Design clustering strategy for medoids (per dominant tag/embed cluster) and prototype on mixed-content folder.
- [ ] Draft automated pipeline surfacing new user tags for review/export (CSV of recent additions, optional delete flow).
- [ ] Revisit ops tasks (Docker packaging, VPS assumptions, documentation refresh) after tag tooling stabilizes.
- [ ] Outline CLI automation for review state (init, approve, exclude) for batch QA scripting.
- [ ] Capture evaluation metrics (Precision@K, stack coverage, time-to-review) on curated image set; refresh smoke fixtures for synonym-heavy cases.

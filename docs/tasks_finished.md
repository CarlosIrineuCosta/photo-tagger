# Completed Tasks Archive

This log captures tasks that have been completed and moved out of `docs/ongoing.md` for clarity.

## Active Session Plan (2024-00-00)

### Architect / Coding (Assistant)

- [x] Convert ongoing tracking doc into actionable checkbox format. <!-- keep history -->
- [x] Backend/API: add orphan-to-group promotion endpoint with audit logging.
- [x] Frontend: add promote-orphan dialog on `TagsPage` with search + quick-create group flow.
- [x] CLI: extend `app/cli/tagger run` with `--export-new-tags` CSV emitter for recent additions.
- [x] Core: introduce tag-aware clustering toggle in `app/core/medoid.py` and cover with smoke test.
- [x] Align blocking overlays with warning tone across processing states.
- [x] Skip redundant gallery processing when no updates are pending.
- [x] Surface medoid cluster metadata across API + gallery UI and add medoid helper script.
- [x] Document medoid review workflow for operators (`docs/user_guide/medoids_workflow.md`).
- [x] Gallery UI: stream workflow status messages into sidebar with tone-aware styling.
- [x] Tags page: finish quick-promote actions driven by tag suggestions (render CTA, countdown undo, rollback on failure).
- [x] Tags page: expose bulk promotion drawer backed by multi-select table and `/api/tags/promote/bulk`.
- [x] Tags page: surface graduation ledger metadata (pending graduations, audit trail) in review panels.
- [x] QA: smoke-test quick promote, bulk promote, and graduation flows with fresh run data; capture regressions or UX gaps.
- [x] Implement stage-based gallery filters (segmented control) consuming new `ReviewStage` payload.
- [x] Replace fixed page-size controls with infinite scroll powered by `useIntersectionObserver` and cursor pagination.
- [x] Surface new-file banner and thumbnail prefetch prompt; show placeholder cards while thumbs warm.
- [x] Render medoid cluster metadata (badges, tooltips) and highlight blocked items with actionable guidance.
- [x] Refactor Tags page into virtualized pill-based interface with search, frequency badges, and bulk drag bins.
- [x] Wire feature flag for LLM tag enhancement UI, calling to new stub API when enabled.
- [x] Refresh onboarding/help copy to explain revised workflow states and lazy-loading behaviour.

### Codex 2025-10-24 – Workflow Stabilization

- [x] Design and apply `ReviewStage` schema, including migration of existing `api_state.json` records and stage transition helpers.
- [x] Extend `/api/gallery` to emit stage metadata, first/last timestamps, and new/modified flags; persist diff cache server-side.
- [x] Convert gallery responses to cursor-based pagination with total counts and streaming-friendly summary endpoint.
- [x] Add `/api/thumbs/prefetch` background task plus status indicators for pending thumbnails.
- [x] Enforce configurable large-TIFF ceiling with `BLOCKED` state and API guidance payloads.
- [x] Instrument process orchestration (`/api/process` + `/api/process/status`) with structured telemetry and expose CPU benchmark endpoint.
- [x] Publish medoid cluster summaries (size, cosine, label hints) through the API and refine heuristic parameters for mixed folders.
- [x] Provide stub FastAPI router for future LLM tag enhancement, gated by feature flag and documented contract.
- [x] Update backend docs (`docs/deployment.md`, `docs/api.md`) to reflect new endpoints, states, and telemetry fields.

### GLM 2025-10-24 – UI & Review Experience

- [x] Implement stage-based gallery filters (segmented control) consuming new `ReviewStage` payload.
- [x] Replace fixed page-size controls with infinite scroll powered by `useIntersectionObserver` and cursor pagination.
- [x] Surface new-file banner and thumbnail prefetch prompt; show placeholder cards while thumbs warm.
- [x] Render medoid cluster metadata (badges, tooltips) and highlight blocked items with actionable guidance.
- [x] Refactor Tags page into virtualized pill-based interface with search, frequency badges, and bulk drag bins.
- [x] Wire feature flag for LLM tag enhancement UI, calling the new stub API when enabled.
- [x] Refresh onboarding/help copy to explain revised workflow states and lazy-loading behaviour.

### Gemini 2025-10-24 – Ingestion & Reliability

- [x] Implement RAW/XMP-aware thumbnail pipeline toggle and cache parsed adjustments per SHA1.
- [x] Add unit/integration tests covering TIFF guardrail, RAW adjustments, and stage transitions.
- [x] Build process delta computation (new vs modified) with persistent cache optimized for large folders.
- [x] Prototype medoid heuristic tuning harness to validate cluster coverage on mixed datasets.
- [x] Capture pipeline timing benchmarks for CPU-only environments and log results into run metadata.
- [x] Draft blocked-file troubleshooting snippet (TIFF over limit, unsupported RAW) for operator docs.
- [x] Document interrupted run recovery steps (resume pipeline, cache cleanup, verification checklist).
- [x] Review & publish the combined recovery guide (`docs/recovery_and_error_handling.md`) with QA sign-off.

### GLM Assist (trigger after core changes are ready)

- [x] Generate `app/util/metrics.py` with `compute_precision_at_k`, `compute_stack_coverage`, and `load_eval_dataset`.
- [x] Update `app/cli/tagger.py` with `metrics` subcommand using the new utilities.
- [x] Draft `docs/metrics.md` documenting metric definitions, dataset prep, and CLI usage.
- [x] Create `frontend/src/hooks/useIntersectionObserver.ts` for intersection observation.
- [x] Wire hybrid promotion UI on `TagsPage`: fetch suggestion metadata, surface single-click promote actions (button + summary badges), and implement optimistic updates with undo countdown + rollback on failure.
- [x] Build bulk promotion drawer with multi-select table, queued execution, status toasts, and retry queue using the `/api/tags/promote/bulk` endpoint.
- [x] Add graduation review panel that reads `pending_graduations`, groups by canonical label, and exposes resolve/skip flows persisted to the manifest ledger (include ledger call + optimistic UI).
- [x] Flesh out `docs/user_guide.md` sections (environment setup, first run, CLI options, UI tour, medoids workflow). [GLM]
- [x] Draft docs for RAW ingestion workflow and list performance tuning levers (previews, cache warmers, format conversion). [GLM]
- [x] Ship Tags QA collateral: screenshot capture helper, checklist, findings template, and process README. [GLM]

### Tags and Medoids – Completed Items

- [x] Extend Tags page so orphan tags can be promoted directly into chosen groups (single-click add).
- [x] Design clustering strategy for medoids (per dominant tag/embed cluster) and prototype on mixed-content folder.
- [x] Evolve medoid selection with tag/embedding clustering before medoid choice for mixed folders.
- [x] Expose promotion ledger + pending graduations via API and UI surfaces.

### Recent Progress Highlights

- [x] Landed enhanced tagging manager (backend + CLI helpers) with synonym handling and tag stacks.
- [x] Shipped enhanced gallery UI with exclusion buttons, user-tag insertion, blocking overlays, and reliable save flow.
- [x] Added `/api/tags` endpoints plus Tags admin page for reviewing label groups, managing tags, surfacing orphans.
- [x] Introduced reusable blocking overlay component with consistent loading/saving states across gallery.
- [x] Implemented metrics module with Precision@K and stack coverage calculations.
- [x] Added metrics CLI subcommand for evaluation dataset analysis.
- [x] Created useIntersectionObserver hook for frontend intersection detection.
- [x] Created `scripts/prepare_tag_brief.py` for analyzing orphan tags from pipeline exports. [GLM]
- [x] Enhanced `scripts/prepare_tag_brief.py` with informative output and --include-canonical flag. [GLM]
- [x] Extended workflow sidebar with scrollable status log to track gallery processing events.
- [x] Published comprehensive tag workflow docs, RAW handling guidance, screenshot tooling, and QA checklists/templates. [GLM]

### Gemini Contributions

- Added unit tests for TIFF guardrail, RAW/XMP processing, and scanner delta computation. [Gemini]

### GLM Contributions 2025-10-24

Completed Tasks:
1. Virtualized Pill Interface for Tags – Introduced virtualized scrolling, search, frequency badges, pill states, and drag-and-drop bulk operations.
2. Batch Bins for Bulk Tag Operations – Added promote/exclude/review bins with visual feedback and queue integration.
3. LLM Enhancer Feature Flag and UI – Added `features.llm_enhancer`, updated config typing, and built the LLM enhancer panel with bulk apply workflows.
4. LLM Enhancer UI Entry Points – Added enablement button, mock responses, and robust error handling.
5. Refreshed Onboarding/Help Copy – Updated HelpPage sections covering tags management, review flow, configuration tips, troubleshooting, and feature flag guidance.


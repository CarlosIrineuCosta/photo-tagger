# Ongoing Work

## Short-Term Priorities

1. **Production packaging** – Create/update the Dockerfile to build the frontend (`npm run build`), bundle static assets, and launch FastAPI via `uvicorn`. Validate locally, then prepare for VPS deployment.
2. **Operations documentation** – Refresh `initial_setup.md` (and related operator notes) with the new `./start-tagger.sh` flow, label-pack usage, and the MVP recovery checklist.
3. **Label quality** – Iterate on the structured label pack (`labels/`). Establish an evaluation set, run smoke/batch tests after each tweak, and log precision/recall observations here.

## Discussion Items / Open Questions

- Can CLIP inference remain CPU-only on the VPS, or do we need remote GPU resources? What are the performance trade-offs?
- How should friends upload RAWs securely for testing (S3, rsync, portal)? What privacy guarantees do we owe them?
- Should `/api/process` run asynchronously (background worker/queue) to keep the API responsive during long pipelines?

## Backlog / Future Enhancements

- Add operator tools for cache maintenance (clear thumbnails, refresh embeddings, wipe run history).
- Broaden label packs with additional tiers/localization after scoring validation.
- Refine UI affordances (Saved vs. Selected badges, progress feedback) once more review sessions are captured.
- Investigate queueing/monitoring if multiple remote runs will be triggered concurrently.

## Next Session Starting Point

1. Decide the initial label-pack experiments (which tier/tag groups to tune first) and set up the evaluation checklist.
2. Outline the Docker build steps (base image, Python deps, frontend build) so we can draft the container in one pass.
3. Capture security/performance assumptions for the VPS rollout (upload method, privacy, CPU/GPU expectations) to guide the deployment discussion.

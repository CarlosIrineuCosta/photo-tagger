# RAW Ingestion Observations — 2025-10-25

This note captures the current state of RAW processing so we can prioritise fixes.

## Telemetry Snapshot

Latest `runs/*/telemetry.jsonl` (5 most recent):

- 20251025-181413 — scan 0.2 ms, thumbs 8.8 ms, embed 3.19 s, score 3.80 s
- 74080b7a / b94cbc6b / d7d8a182 — scan ~0.7 ms, thumbs ~1.28 s, embed ~34 s, score ~3.6 s

Key takeaways:

* Thumbnail cost depends entirely on RAW availability (`rawpy` present → ~1.3 s per batch; missing RAW support → <10 ms because only JPEGs are processed).
* Embeddings dominate runtime (30–35 s averages, 65–70 s peaks); any “slow pipeline” reports are almost certainly due to CLIP inference latency.
* Scan/medoids/export are negligible compared to embedding.

## Current Behaviour

* `app/core/thumbs.py` raises `RuntimeError` if `rawpy` is missing when a `.nef/.cr2/.arw` is encountered. In our headless test session, this stopped benchmarking immediately.
* Thumbnail generation honours a `thumbnails.xmp_processing` toggle — when enabled, it parses the XMP sidecar, caches the exposure tweak (`xmp_cache/`), and calls `rawpy.postprocess` with a calculated `bright` factor.
* The CLI pipeline does **not** skip RAWs; without `rawpy`, we fail instead of falling back to embedded previews.

## Suggested Follow-ups

1. **Dependency Check** — add a startup warning (CLI + API) when RAW files exist but `rawpy` is unavailable, so operators aren’t surprised by runtime failures.
2. **Fallback Mode** — consider a config flag (`thumbnails.allow_raw_fallback`) that uses embedded previews via `PIL.Image` rather than raising when `rawpy` is missing. Visual fidelity will drop, but the workflow stays unblocked for CPU-only machines.
3. **Batch Prefetch** — extend `/api/thumbs/prefetch` to accept a `batch_size` and stream progress updates so we can pre-warm RAW thumbnails without locking the UI thread. A background worker would help amortise the 1.3 s cost across multiple files.
4. **Embedding Optimisation** — since embeddings dominate, expose `config.embedding.batch_size` and document the GPU/CPU trade-offs; today’s defaults (batch 8) may be too aggressive for low-memory systems.
5. **Telemetry Doc** — document how to read `runs/<id>/telemetry.jsonl` so future investigations can reference a standard workflow.

These items give us a roadmap once GLM and Gemini finish their automation tasks.

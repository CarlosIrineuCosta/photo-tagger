# Photo Tagger MVP Recovery Checks

> Run these checks sequentially to confirm the rebuilt environment matches the expected FastAPI + React baseline. Use a fresh terminal for each block when practical so environment variables are easy to reason about.

## 1. Environment + Bootstrap
- `./start-tagger.sh`
  - First run should emit `[env] Creating virtual environment` and `[env] Installing project dependencies`.
  - Wait for `[start] Backend is up.` and the Vite banner (`VITE v... ready in ...`).
- `ps -ef | grep uvicorn | grep backend.api.index:app`
  - Expect a uvicorn process spawned from `.venv/bin/python`.
- `ps -ef | grep vite | grep frontend`
  - Confirms the dev server is live on port `5173`.

## 2. Backend Health
- `curl -fsS http://127.0.0.1:8010/api/health`
  - Expect `{"ok":true}`.
- `curl -fsS http://127.0.0.1:8010/api/routes`
  - Verify the list includes `/api/gallery`, `/api/tag`, `/api/export`, `/api/process`, `/api/config`, `/api/thumbs/{thumb_name}`.
- `tail -n 20 backend.log`
  - Ensure the latest entries include the above routes returning `200 OK`.

## 3. Fixture Reset
- `python -m venv .venv` *(skip if `.venv/bin/python` already exists; `start-tagger.sh` handles creation)*.
- `source .venv/bin/activate`
- `python scripts/smoke_test.py --wipe`
  - Confirm it reports regenerating sample photos and thumbnails without errors.
- `ls -1 tests/smoke/images | head`
  - Expect synthetic fixtures present for gallery QA.

## 4. API Surface
- `curl -fsS http://127.0.0.1:8010/api/gallery | jq '.items | length'`
  - Should return a positive integer matching smoke fixtures.
- `curl -fsS http://127.0.0.1:8010/api/config | jq '.root'`
  - Expect a valid path (default smoke root or configured value).
- `curl -fsS -X POST http://127.0.0.1:8010/api/process -H "Content-Type: application/json" -d '{"root":"tests/smoke/images","max_images":12}'`
  - Expect `{ "status": "queued", "run_id": "<timestamp or hash>" }`. If 400 appears, note the error message and verify `root` exists.
- `curl -fsS http://127.0.0.1:8010/api/export | jq '.formats'`
  - Confirm it lists export modes `["csv","sidecars","both"]`.

## 5. Frontend Sanity
- Visit `http://127.0.0.1:5173` in a browser (or `curl` + `grep` if headless).
  - Confirm the gallery grid renders items for the smoke fixtures.
- Toggle letterbox vs. center-crop, verify the state persists between navigation events.
- Open the Workflow sidebar and confirm controls appear without JS errors (`frontend` terminal remains clean).
- Navigate to `/config`, `/help`, `/login` via the top bar; expect routed pages without 404.

## 6. Pipeline Integration
- From UI: trigger “Process Images” (mirrors `/api/process` call). Watch StatusStrip for success message with `run_id`.
- On completion: `ls runs | tail`
  - Expect a new timestamped run folder.
- Inspect `runs/<latest>/scores.json`
  - Ensure file exists and includes labels array per `backend_interface_spec.md`.

## 7. Regression Guards
- `pytest`
  - All tests pass.
- `npm run build --prefix frontend`
  - Builds without warnings or type errors.
- `python -m pip check`
  - Confirms dependency graph is consistent inside the venv.

## 8. Shutdown
- `Ctrl+C` in the `start-tagger.sh` session.
- `ps -ef | grep -E "uvicorn|vite" | grep -v grep`
  - No lingering processes.

Document any deviations (command, output, suspected root cause) so we can focus follow-up tasks.

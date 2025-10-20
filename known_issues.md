# Known Issues & Decisions

- **Legacy web stack retired**: The previous UI/API stack introduced too much churn; Streamlit + CLI is now the only supported path—avoid reintroducing the old stack.
- **Sidecar-only writes**: Metadata must go through ExifTool-generated XMP sidecars. Direct RAW edits are out of scope and should be rejected in future ideas.
- **GPU batch pressure**: Keep `embeddings.batch_size` conservative (currently 8) until VRAM stability stops fluctuating; always spot-check `nvidia-smi` before long runs.
- **Pinned Torch stack required**: Rehydrating the repo with loose `torch/torchvision` constraints caused hour-long pip backtracks. Keep `torch==2.2.2` and `torchvision==0.17.2` pinned in `pyproject.toml` or installs stall.
- **npm audit stalls installs**: Fresh `npm install` on the frontend can sit in the audit loop indefinitely. Work around with `npm config set audit false && npm install --no-progress` inside `frontend/`.
- **UI font sizing**: The React/Shadcn build renders text too small after the restore; revisit the typography scale before wider testing.
- **Test fixtures wiped**: Synthetic smoke images and cached thumbnails were lost with the drive. Regenerate via `python scripts/smoke_test.py --wipe` (or copy the archived set) before QA.

## Next Session Starting Point

- Launch `./start-tagger.sh`, confirm the FastAPI backend and Vite dev server both respond, then run a quick gallery walk-through.
- Recreate the smoke-test assets and re-run `python scripts/smoke_test.py --wipe` so we have sample images for regression checks.
- Adjust the frontend font sizes once the gallery is visible, then capture notes/screenshots for the refactor doc.

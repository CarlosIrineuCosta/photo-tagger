# Known Issues & Decisions

- **React + FastAPI architecture**: The project has migrated from Streamlit to React + FastAPI architecture. All new development should target this stack.
- **Sidecar-only writes**: Metadata must go through ExifTool-generated XMP sidecars. Direct RAW edits are out of scope and should be rejected in future ideas.
- **GPU batch pressure**: Keep `embeddings.batch_size` conservative (currently 8) until VRAM stability stops fluctuating; always spot-check `nvidia-smi` before long runs.
- **Pinned Torch stack required**: Rehydrating the repo with loose `torch/torchvision` constraints caused hour-long pip backtracks. Keep `torch==2.2.2` and `torchvision==0.17.2` pinned in `pyproject.toml` or installs stall.
- **npm audit stalls installs**: Fresh `npm install` on the frontend can sit in the audit loop indefinitely. Work around with `npm config set audit false && npm install --no-progress` inside `frontend/`.
- **Test fixtures wiped**: Synthetic smoke images and cached thumbnails were lost with the drive. Regenerate via `python scripts/smoke_test.py --wipe` (or copy of archived set) before QA.
- **Enhanced tagging system**: The enhanced tagging system with tag stacks and synonym resolution is now part of the core workflow. Ensure all new tag-related features integrate with this system.

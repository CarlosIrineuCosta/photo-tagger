# Known Issues & Decisions

- **Legacy web stack retired**: The previous UI/API stack introduced too much churn; Streamlit + CLI is now the only supported path—avoid reintroducing the old stack.
- **Sidecar-only writes**: Metadata must go through ExifTool-generated XMP sidecars. Direct RAW edits are out of scope and should be rejected in future ideas.
- **GPU batch pressure**: Keep `embeddings.batch_size` conservative (currently 8) until VRAM stability stops fluctuating; always spot-check `nvidia-smi` before long runs.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation and Setup
```bash
# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install .

# For development dependencies (linting/formatting)
pip install -e ".[dev]"

# System dependencies required
sudo apt install exiftool
# Optional for OCR: sudo apt install tesseract-ocr
```

### Running the Application
```bash
# Start the web UI (FastAPI + React)
./start-tagger.sh  # FastAPI on 8010, Vite on 5173

# Batch processing (medoid tagging only, no XMP writes)
python scripts/medoid_batch.py --openai  # optional --openai for Vision API

# Smoke test with synthetic data
python scripts/smoke_test.py --wipe  # add --write for actual XMP writes
```

### Code Quality Tools
```bash
# Formatting and linting (available as optional dev dependencies)
black .
isort .
ruff check .
```

## Configuration

### Required Configuration Files
- Copy `config/config.example.yaml` to `config/config.yaml`
- Copy `config/ck_vocab.example.yaml` to `config/ck_vocab.yaml`
- Set `OPENAI_API_KEY` environment variable for Vision API features

### Key Configuration Areas
- `roots`: Photo source directories (typically Samba mounts)
- `runtime.cache_root`: Local cache storage location
- `people_policy`: Controls privacy/nude detection behavior
- `ai_tagging.city_whitelist`: Proper nouns allowed from Vision API
- `ck_tagging.vocab_file`: Controlled vocabulary for CK tags

## Architecture Overview

### Pipeline Flow
The application implements a 6-step photo processing pipeline:
1. **Scan** (`app/scanner.py`) - File discovery, EXIF extraction, date resolution
2. **Proxies** (`app/proxy.py`) - Generate 1024px JPEG proxies from RAW files
3. **Embeddings** (`app/embed.py`) - OpenCLIP ViT-L/14 feature extraction
4. **Clustering** (`app/cluster.py`) - Time-window + HDBSCAN clustering, medoid selection
5. **Tagging** (`app/tag_ck.py`, `app/tag_ai.py`) - CK vocabulary + AI Vision tagging
6. **XMP Writing** (`app/write_xmp.py`) - Keyword export via exiftool sidecars

### Core Components
- **FastAPI + React UI** (`backend/api`, `frontend/`) - Web interface for pipeline control
- **Pipeline Orchestration** (`app/jobs.py`) - Coordinates all processing steps
- **Configuration System** (`app/config.py`) - YAML-based configuration management
- **People Detection** (`app/person.py`) - Privacy-aware people/nude detection
- **Date Resolution** (`app/scanner.py`) - Multi-source timestamp resolution with heuristics

### Data Storage
- **Parquet Caches**: Index, proxies, embeddings, clusters stored as parquet files
- **Cache Reuse**: `runtime.reuse_cache: true` enables incremental processing
- **Audit Trail**: `audit.csv` exports all proposed tags for review

### Privacy and Safety
- People detection automatically applied to control Vision API usage
- `treat_people_sets_as_nude: true` suppresses hand detection and gates Vision API
- Local-only processing fallback for sensitive content
- CK vocabulary provides curated, controlled tagging separate from AI tags

### Key Design Patterns
- Configuration-driven pipeline with extensive YAML customization
- Incremental processing with cache reuse for iterative workflows
- Dual tagging system: controlled vocabulary (CK:) + AI-generated (AI:) tags
- Privacy-first approach with configurable nude/people detection policies
- Medoid-based cluster representation for efficient manual review

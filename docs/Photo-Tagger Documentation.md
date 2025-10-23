# Photo Tagger Documentation Update

This document summarizes the comprehensive documentation updates made to reflect the current React + FastAPI + CLI workflow.

## Overview of Changes

The Photo Tagger system has been refactored into a streamlined React + FastAPI + CLI workflow. All documentation has been updated to reflect this change and provide accurate guidance for users and developers.

## Updated Documentation Files

### 1. README.md - Complete Rewrite
**Key Changes:**
- Documented the React + FastAPI + CLI workflow end-to-end
- Updated installation prerequisites to highlight the React frontend and Vite toolchain
- Added `./start-tagger.sh` as primary UI launch command
- Documented all CLI subcommands: scan, thumbs, embed, score, medoids, export, sidecars, run
- Updated configuration guidance to match config.yaml structure
- Added comprehensive section on run-directory artifacts
- Included hardware considerations (GPU optional, performance tips)
- Documented caching system (thumb_cache/, embedding caches)
- Added CSV schema documentation
- Removed clustering and OpenAI sections

### 2. AGENTS.md - Repository Guidelines Update
**Key Changes:**
- Updated project structure to reflect app/core, backend/api, frontend layout
- Documented the React + FastAPI + CLI commands
- Removed references to CK vocabulary and clustering
- Updated development commands and workflows

### 3. CLAUDE.md - Development Guide Refresh
**Key Changes:**
- Updated architecture description for the new backend/api and frontend layout
- Documented current CLI commands and React UI
- Updated dependencies list to match the FastAPI/React workflow
- Removed obsolete features (CK vocabulary, OpenAI Vision, clustering)

### 4. codex_notes.md - Developer Documentation Enhancement
**New Developer Sections Added:**
- CLI/UI artifact sharing architecture
- Run directory structure details
- CSV schema (app/core/export.py#L9) documentation
- Label embedding caching system details
- Cache invalidation rules
- Extending labels and prompt templates
- Performance optimization guidelines

## Legacy Documents Preserved

### Photo-Tagger Refactor.md
- **Status:** Preserved in root directory (important historical document)
- **Content:** Original refactoring documentation maintained
- **Purpose:** Reference for understanding the evolution of the system

## Key Technical Changes Documented

### Configuration System
- **Before:** Multiple config files in config/ directory
- **After:** Single config.yaml in project root
- **Documentation:** Updated across all files to reflect new structure

### Module Organization
- Clean separation: app/core/, app/cli/, backend/api/, frontend/, app/util/
- **Documentation:** Updated in AGENTS.md and CLAUDE.md

### Workflow Changes
- CLI commands + React UI
- **Documentation:** Complete workflow rewrite in README.md

## Validation Checklist

- [x] All documentation reflects the React + FastAPI + CLI workflow
- [x] Configuration guidance matches config.yaml
- [x] CLI subcommands documented
- [x] Run-directory artifacts explained
- [x] Caching system documented
- [x] Hardware considerations included
- [x] Developer notes comprehensive
- [x] Legacy documents preserved
- [x] Operator guide created

## Conclusion

The documentation has been comprehensively updated to reflect the new React + FastAPI + CLI workflow while preserving important historical documents. The new documentation provides clearer guidance for both operators and developers, with detailed technical references and practical examples.

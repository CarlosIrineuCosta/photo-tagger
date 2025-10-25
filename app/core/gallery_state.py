from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Tuple

from app.core import labels as labels_core
from app.state.models import ImageState, ReviewStage


def build_directory_index(paths: Iterable[str]) -> Dict[str, Dict[str, float | int]]:
    """
    Return filesystem metadata (mtime + size) for each path that exists.
    """
    index: Dict[str, Dict[str, float | int]] = {}
    for raw_path in paths:
        try:
            stat = Path(raw_path).stat()
        except OSError:
            continue
        index[raw_path] = {
            "mtime": float(stat.st_mtime),
            "size": int(stat.st_size),
        }
    return index


def detect_changes(
    previous_index: Mapping[str, Mapping[str, float | int]],
    current_index: Mapping[str, Mapping[str, float | int]],
) -> Tuple[set[str], set[str], set[str]]:
    """
    Compare directory snapshots and compute new, modified, and removed paths.
    """
    previous_paths = set(previous_index.keys())
    current_paths = set(current_index.keys())
    new_paths = current_paths - previous_paths
    removed_paths = previous_paths - current_paths
    modified_paths: set[str] = set()

    for path in current_paths & previous_paths:
        previous = previous_index.get(path) or {}
        current = current_index.get(path) or {}
        if (previous.get("mtime"), previous.get("size")) != (current.get("mtime"), current.get("size")):
            modified_paths.add(path)
    return new_paths, modified_paths, removed_paths


def detect_blocked_files(
    file_index: Mapping[str, Mapping[str, float | int]],
    *,
    max_tiff_mb: float,
) -> Dict[str, str]:
    """
    Identify files that should be blocked from processing (currently oversized TIFFs).
    """
    blocked: Dict[str, str] = {}
    limit_bytes = max_tiff_mb * 1024 * 1024
    for path, meta in file_index.items():
        suffix = Path(path).suffix.lower()
        size = int(meta.get("size", 0))
        if suffix in {".tif", ".tiff"} and size > limit_bytes:
            blocked[path] = "oversized_tiff"
    return blocked


def ensure_image_state(entry: Optional[Mapping[str, object]]) -> ImageState:
    """
    Convert a persisted mapping into an ImageState with normalized labels.
    """
    if entry is None:
        return ImageState(stage=ReviewStage.NEW)
    state = ImageState.from_dict(dict(entry))
    state.selected = labels_core.normalize_labels(state.selected)
    if state.saved and state.stage != ReviewStage.SAVED:
        state.stage = ReviewStage.SAVED
    return state


def resolve_review_stage(
    image_state: ImageState,
    *,
    blocked_reason: Optional[str],
    is_new: bool,
    is_modified: bool,
) -> ReviewStage:
    """
    Determine the canonical review stage based on current metadata.
    """
    if blocked_reason:
        return ReviewStage.BLOCKED
    if is_new and image_state.last_processed is None:
        return ReviewStage.NEW
    if image_state.saved:
        if is_modified:
            return ReviewStage.NEEDS_TAGS
        return ReviewStage.SAVED
    if image_state.selected:
        return ReviewStage.HAS_DRAFT
    return ReviewStage.NEEDS_TAGS


def persist_image_state(
    images_state: MutableMapping[str, dict],
    path: str,
    image_state: ImageState,
) -> None:
    """
    Store the image state into the persisted mapping.
    """
    images_state[path] = image_state.to_dict()


def mark_saved(image_state: ImageState) -> None:
    """
    Update state to reflect a successful save.
    """
    image_state.saved = True
    image_state.stage = ReviewStage.SAVED
    image_state.last_saved = time.time()


def mark_processed(image_state: ImageState) -> None:
    """
    Update timestamps after processing pipeline completes.
    """
    image_state.last_processed = time.time()
    if image_state.stage == ReviewStage.NEW:
        image_state.stage = ReviewStage.NEEDS_TAGS


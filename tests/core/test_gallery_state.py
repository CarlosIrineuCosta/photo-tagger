from __future__ import annotations

import time
from pathlib import Path

from app.core.gallery_state import (
    build_directory_index,
    detect_blocked_files,
    detect_changes,
    ensure_image_state,
    mark_processed,
    mark_saved,
    persist_image_state,
    resolve_review_stage,
)
from app.state.models import ImageState, ReviewStage


def test_build_directory_index(tmp_path: Path):
    file_a = tmp_path / "a.jpg"
    file_a.write_bytes(b"hello")
    file_b = tmp_path / "b.tif"
    file_b.write_bytes(b"world")

    index = build_directory_index([str(file_a), str(file_b), str(tmp_path / "missing.png")])
    assert set(index.keys()) == {str(file_a), str(file_b)}
    assert index[str(file_a)]["size"] == 5
    assert index[str(file_b)]["size"] == 5


def test_detect_changes_identifies_new_modified_removed(tmp_path: Path):
    file_a = tmp_path / "a.jpg"
    file_a.write_bytes(b"a")
    file_b = tmp_path / "b.jpg"
    file_b.write_bytes(b"b")

    prev = build_directory_index([str(file_a)])
    time.sleep(0.01)
    file_a.write_bytes(b"aa")  # modify
    current = build_directory_index([str(file_a), str(file_b)])

    new_paths, modified_paths, removed_paths = detect_changes(prev, current)
    assert new_paths == {str(file_b)}
    assert modified_paths == {str(file_a)}
    assert removed_paths == set()


def test_detect_blocked_files_oversized_tiff(tmp_path: Path):
    small_tiff = tmp_path / "small.tif"
    small_tiff.write_bytes(b"x" * (1024 * 10))
    large_tiff = tmp_path / "large.tif"
    large_tiff.write_bytes(b"x" * (1024 * 1024 * 2))
    index = build_directory_index([str(small_tiff), str(large_tiff)])

    blocked = detect_blocked_files(index, max_tiff_mb=1.0)
    assert str(large_tiff) in blocked
    assert blocked[str(large_tiff)] == "oversized_tiff"
    assert str(small_tiff) not in blocked


def test_ensure_image_state_defaults():
    state = ensure_image_state(None)
    assert state.stage == ReviewStage.NEW
    assert not state.selected


def test_resolve_review_stage_transitions():
    base = ImageState(stage=ReviewStage.NEW)

    assert resolve_review_stage(base, blocked_reason=None, is_new=True, is_modified=False) == ReviewStage.NEW

    saved = ImageState(stage=ReviewStage.SAVED, saved=True, last_processed=time.time())
    assert resolve_review_stage(saved, blocked_reason=None, is_new=False, is_modified=False) == ReviewStage.SAVED
    assert resolve_review_stage(saved, blocked_reason=None, is_new=False, is_modified=True) == ReviewStage.NEEDS_TAGS

    draft = ImageState(stage=ReviewStage.HAS_DRAFT, selected=["tag"])
    assert resolve_review_stage(draft, blocked_reason=None, is_new=False, is_modified=False) == ReviewStage.HAS_DRAFT

    blocked = resolve_review_stage(base, blocked_reason="oversized_tiff", is_new=False, is_modified=False)
    assert blocked == ReviewStage.BLOCKED


def test_persist_and_mark_helpers():
    image_state = ImageState(stage=ReviewStage.NEEDS_TAGS)
    container: dict[str, dict] = {}

    persist_image_state(container, "path.jpg", image_state)
    assert "path.jpg" in container

    mark_processed(image_state)
    assert image_state.last_processed is not None
    assert image_state.stage != ReviewStage.NEW

    mark_saved(image_state)
    assert image_state.stage == ReviewStage.SAVED
    assert image_state.saved is True
    assert image_state.last_saved is not None

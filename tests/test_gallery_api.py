from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Tuple
from fastapi import Request

from app.state.models import ImageState, ReviewStage
from backend.api import index


def make_image_entry(
    stage: ReviewStage,
    *,
    saved: bool,
    selected: List[str] | None = None,
) -> dict:
    return {
        "stage": stage.value,
        "saved": saved,
        "selected": list(selected or []),
        "first_seen": 0.0,
        "last_processed": None,
        "last_saved": None,
        "blocked_reason": None,
        "pending_reasons": [],
    }


def test_prepare_gallery_records_stage_counts(monkeypatch, tmp_path):
    cfg = {"root": str(tmp_path), "max_tiff_mb": 1}
    base_dir = tmp_path / "images"
    base_dir.mkdir()

    paths = {
        "new": str(base_dir / "new.jpg"),
        "needs": str(base_dir / "needs.jpg"),
        "draft": str(base_dir / "draft.jpg"),
        "saved": str(base_dir / "saved.jpg"),
        "blocked": str(base_dir / "blocked.tif"),
    }
    metadata = {path: {"mtime": 1.0, "size": 100} for path in paths.values()}

    template_state = {
        "images": {
            paths["needs"]: make_image_entry(ReviewStage.NEEDS_TAGS, saved=False, selected=[]),
            paths["draft"]: make_image_entry(ReviewStage.HAS_DRAFT, saved=False, selected=["draft"]),
            paths["saved"]: make_image_entry(ReviewStage.SAVED, saved=True, selected=["approved"]),
            paths["blocked"]: make_image_entry(ReviewStage.NEEDS_TAGS, saved=False, selected=[]),
        },
        "directory_index": {},
        "blocked_reason_counts": {},
        "_version": 1,
    }

    monkeypatch.setattr(
        index,
        "_scan_with_metadata",
        lambda root, include_exts, max_images: (list(paths.values()), metadata),
    )
    monkeypatch.setattr(
        index,
        "_detect_directory_changes",
        lambda directory_index, new_meta: ([paths["new"]], [], []),
    )
    monkeypatch.setattr(
        index,
        "_detect_blocked_files",
        lambda file_index, limit_mb: {paths["blocked"]: "oversized_tiff"},
    )
    monkeypatch.setattr(index, "save_state", lambda cfg, state: state)
    monkeypatch.setattr(index, "get_state", lambda cfg: deepcopy(template_state))

    records, summary_counts, final_state = index._prepare_gallery_records(cfg)

    assert {record["path"] for record in records} == set(paths.values())
    assert summary_counts == {
        ReviewStage.NEW.value: 1,
        ReviewStage.NEEDS_TAGS.value: 1,
        ReviewStage.HAS_DRAFT.value: 1,
        ReviewStage.SAVED.value: 1,
        ReviewStage.BLOCKED.value: 1,
    }
    assert final_state["blocked_reason_counts"] == {"oversized_tiff": 1}


def test_get_gallery_returns_summary_and_supports_stage_filter(monkeypatch, tmp_path):
    root = tmp_path / "gallery"
    root.mkdir()
    files = {
        "new": root / "item_new.jpg",
        "needs": root / "item_needs.jpg",
        "draft": root / "item_draft.jpg",
        "saved": root / "item_saved.jpg",
        "blocked": root / "item_blocked.jpg",
    }
    for file in files.values():
        file.write_text("stub", encoding="utf-8")

    def build_payload() -> Tuple[List[dict], Dict[str, int], Dict[str, dict]]:
        summary = {stage.value: 0 for stage in ReviewStage}
        records: List[dict] = []
        state = {"images": {}, "blocked_reason_counts": {}, "_version": 1}

        specs = [
            ("new", ReviewStage.NEW, False, [], True, False),
            ("needs", ReviewStage.NEEDS_TAGS, False, [], False, False),
            ("draft", ReviewStage.HAS_DRAFT, False, ["draft"], False, False),
            ("saved", ReviewStage.SAVED, True, ["approved"], False, False),
            ("blocked", ReviewStage.BLOCKED, False, [], False, False),
        ]

        for name, stage, saved, selected, is_new, is_modified in specs:
            path = str(files[name])
            image_state = ImageState(stage=stage, saved=saved, selected=list(selected))
            records.append(
                {
                    "path": path,
                    "metadata": {"mtime": 1.0, "size": 100},
                    "state": image_state,
                    "is_new": is_new,
                    "is_modified": is_modified,
                }
            )
            summary[stage.value] += 1
            state["images"][path] = image_state.to_dict()

        return records, summary, state

    monkeypatch.setattr(index, "_prepare_gallery_records", lambda cfg: build_payload())
    monkeypatch.setattr(index, "_load_run_context", lambda cfg, root_path: (None, {}, root))
    monkeypatch.setattr(index, "_extract_sidecar_keywords", lambda path: [])
    monkeypatch.setattr(
        index,
        "_ensure_thumbnail",
        lambda path, cache_root: {
            "sha1": Path(path).stem,
            "thumbnail": str(root / f"{Path(path).stem}.jpg"),
            "width": 640,
            "height": 480,
        },
    )
    monkeypatch.setattr(index, "get_label_pool", lambda cfg: ["alpha", "beta", "gamma"])
    monkeypatch.setattr(index, "save_state", lambda cfg, state: state)
    monkeypatch.setattr(
        index,
        "load_config",
        lambda: {
            "root": str(root),
            "thumb_cache": str(root / "thumbs"),
            "topk": 3,
            "run_dir": str(root / "runs"),
        },
    )

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/gallery",
        "headers": [],
        "app": index.app,
    }
    request = Request(scope)

    response = index.get_gallery(request)
    payload = response.model_dump()
    assert payload["summary"]["counts"] == {
        ReviewStage.NEW.value: 1,
        ReviewStage.NEEDS_TAGS.value: 1,
        ReviewStage.HAS_DRAFT.value: 1,
        ReviewStage.SAVED.value: 1,
        ReviewStage.BLOCKED.value: 1,
    }
    assert payload["total"] == 5
    assert len(payload["items"]) == 5

    filtered_response = index.get_gallery(request, stage=ReviewStage.SAVED.value)
    filtered = filtered_response.model_dump()
    assert filtered["total"] == 1
    assert len(filtered["items"]) == 1
    assert all(item["stage"] == ReviewStage.SAVED.value for item in filtered["items"])
    assert filtered["summary"]["counts"] == payload["summary"]["counts"]

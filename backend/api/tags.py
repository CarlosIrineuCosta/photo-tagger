"""
Tag management endpoints for label packs.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Mapping, Set

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import labels as label_utils

router = APIRouter(prefix="/api/tags", tags=["tags"])

DEFAULT_GROUP_ORDER = ("objects", "scenes", "styles")
IGNORE_GROUP_FILES = {"candidates.txt"}
PROMOTION_LOG_NAME = "tag_events.log"

CONFIG_PATH = Path("config.yaml")


def _load_yaml(path: Path) -> Dict:
    if not path.exists():
        return {}
    import yaml  # local import to avoid global dependency at import time

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _load_config() -> Dict:
    return _load_yaml(CONFIG_PATH)


def _resolve_label_dir(config: Mapping[str, object] | None = None) -> Path:
    config = dict(config or _load_config())
    value = config.get("labels_file")
    if value:
        path = Path(value).expanduser()
        if path.is_dir():
            return path
    fallback = Path("labels")
    return fallback.resolve()


def _resolve_run_dir(config: Mapping[str, object] | None = None) -> Path:
    config = dict(config or _load_config())
    value = config.get("run_dir", "runs")
    path = Path(value).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_state_path(config: Mapping[str, object] | None = None) -> Path:
    return _resolve_run_dir(config) / "api_state.json"


def _read_group_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return label_utils.normalize_labels(lines)


def _write_group_file(path: Path, values: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_values = sorted(set(label_utils.normalize_labels(values)))
    path.write_text("\n".join(sorted_values) + ("\n" if sorted_values else ""), encoding="utf-8")


def _collect_state_tags(config: Mapping[str, object] | None = None) -> Counter:
    state_path = _run_state_path(config)
    if not state_path.exists():
        return Counter()

    with state_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    images = data.get("images", {})
    counts: Counter = Counter()
    for item in images.values():
        selected = item.get("selected") or []
        normalized = label_utils.normalize_labels(selected)
        counts.update(normalized)
    return counts


class TagSummaryResponse(BaseModel):
    class Group(BaseModel):
        id: str
        label: str
        path: str
        tags: List[str]

    class OrphanTag(BaseModel):
        name: str
        occurrences: int

    groups: List[Group]
    orphan_tags: List[OrphanTag]
    stats: Dict[str, int]


class MutateTagRequest(BaseModel):
    group: str = Field(..., description="Label group id (objects, scenes, styles)")
    tag: str = Field(..., description="Tag text to add or remove")


class MutateTagResponse(BaseModel):
    status: str
    group: str
    tag: str
    total: int


class PromoteTagRequest(BaseModel):
    tag: str = Field(..., description="Orphan tag to promote")
    target_group: str | None = Field(default=None, description="Existing group id to receive the tag")
    new_group_label: str | None = Field(
        default=None, description="Optional label for a new group (will be slugified)"
    )


class PromoteTagResponse(BaseModel):
    status: str
    tag: str
    group: str
    group_label: str
    total: int
    created_group: bool = False
    occurrences: int | None = Field(default=None, description="Occurrences tracked in recent runs")


def _slugify_group(label: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", label.lower())
    slug = text.strip("-")
    return slug or "group"


def _format_group_label(group_id: str) -> str:
    if not group_id:
        return "Group"
    parts = group_id.replace("-", " ").replace("_", " ").split()
    return " ".join(word.capitalize() for word in parts)


def _discover_group_files(label_dir: Path) -> Dict[str, Path]:
    """
    Return a mapping of group id to file path, ensuring default groups are listed first.
    """
    mapping: Dict[str, Path] = {}
    for group_id in DEFAULT_GROUP_ORDER:
        mapping[group_id] = label_dir / f"{group_id}.txt"

    for candidate in sorted(label_dir.glob("*.txt")):
        if candidate.name in IGNORE_GROUP_FILES:
            continue
        group_id = candidate.stem.lower()
        mapping.setdefault(group_id, candidate)

    return mapping


def _log_event(action: str, payload: Dict[str, object], config: Mapping[str, object] | None = None) -> None:
    entry = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "action": action,
        **payload,
    }
    try:
        log_path = _resolve_run_dir(config) / PROMOTION_LOG_NAME
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Logging failure should not break the API.
        pass


@router.get("/summary", response_model=TagSummaryResponse)
def summarize_tags() -> TagSummaryResponse:
    config = _load_config()
    label_dir = _resolve_label_dir(config)
    group_files = _discover_group_files(label_dir)
    groups: List[TagSummaryResponse.Group] = []
    all_tags: Set[str] = set()

    for group_id, path in group_files.items():
        tags = _read_group_file(path)
        groups.append(
            TagSummaryResponse.Group(
                id=group_id,
                label=_format_group_label(group_id),
                path=str(path),
                tags=tags,
            )
        )
        all_tags.update(tags)

    state_counts = _collect_state_tags(config)
    orphan_counts = {tag: count for tag, count in state_counts.items() if tag not in all_tags}
    orphan_tags = [
        TagSummaryResponse.OrphanTag(name=tag, occurrences=count)
        for tag, count in sorted(orphan_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    stats = {
        "groups": len(groups),
        "total_labels": sum(len(group.tags) for group in groups),
        "orphan_labels": len(orphan_tags),
        "samples_indexed": sum(state_counts.values()),
    }

    return TagSummaryResponse(groups=groups, orphan_tags=orphan_tags, stats=stats)


@router.post("/item", response_model=MutateTagResponse)
def add_tag(request: MutateTagRequest) -> MutateTagResponse:
    config = _load_config()
    label_dir = _resolve_label_dir(config)
    group_files = _discover_group_files(label_dir)

    group_id = request.group.lower()
    path = group_files.get(group_id)
    if path is None:
        raise HTTPException(status_code=400, detail="Unknown label group")

    tag = label_utils.normalize_labels([request.tag])
    if not tag:
        raise HTTPException(status_code=400, detail="Tag cannot be empty")
    normalized = tag[0]

    tags = _read_group_file(path)
    if normalized in tags:
        raise HTTPException(status_code=409, detail="Tag already exists in this group")

    tags.append(normalized)
    _write_group_file(path, tags)

    return MutateTagResponse(status="created", group=group_id, tag=normalized, total=len(tags))


@router.delete("/item", response_model=MutateTagResponse)
def delete_tag(request: MutateTagRequest) -> MutateTagResponse:
    config = _load_config()
    label_dir = _resolve_label_dir(config)
    group_files = _discover_group_files(label_dir)

    group_id = request.group.lower()
    path = group_files.get(group_id)
    if path is None:
        raise HTTPException(status_code=400, detail="Unknown label group")

    tag = label_utils.normalize_labels([request.tag])
    if not tag:
        raise HTTPException(status_code=400, detail="Tag cannot be empty")
    normalized = tag[0]

    tags = _read_group_file(path)
    if normalized not in tags:
        raise HTTPException(status_code=404, detail="Tag not found in group")

    tags = [value for value in tags if value != normalized]
    _write_group_file(path, tags)

    return MutateTagResponse(status="deleted", group=group_id, tag=normalized, total=len(tags))


@router.post("/promote", response_model=PromoteTagResponse)
def promote_orphan_tag(request: PromoteTagRequest) -> PromoteTagResponse:
    config = _load_config()
    label_dir = _resolve_label_dir(config)
    group_files = _discover_group_files(label_dir)

    normalized_tag_list = label_utils.normalize_labels([request.tag])
    if not normalized_tag_list:
        raise HTTPException(status_code=400, detail="Tag cannot be empty")
    normalized_tag = normalized_tag_list[0]

    created_group = False
    group_id: str | None = None
    group_label = ""
    target_path: Path | None = None

    if request.target_group:
        candidate = request.target_group.lower()
        target_path = group_files.get(candidate)
        if target_path is None:
            raise HTTPException(status_code=404, detail="Target group not found")
        group_id = candidate
        group_label = _format_group_label(group_id)
    elif request.new_group_label:
        slug = _slugify_group(request.new_group_label)
        candidate = slug
        suffix = 2
        while candidate in group_files:
            candidate = f"{slug}-{suffix}"
            suffix += 1
        target_path = label_dir / f"{candidate}.txt"
        group_id = candidate
        group_label = request.new_group_label.strip() or _format_group_label(candidate)
        created_group = True
    else:
        raise HTTPException(status_code=400, detail="Provide target_group or new_group_label")

    assert group_id and target_path

    tags = _read_group_file(target_path)
    if normalized_tag in tags:
        raise HTTPException(status_code=409, detail="Tag already exists in target group")

    tags.append(normalized_tag)
    _write_group_file(target_path, tags)

    occurrences = _collect_state_tags(config).get(normalized_tag)
    payload = {
        "status": "promoted",
        "tag": normalized_tag,
        "group": group_id,
        "group_label": group_label,
        "total": len(tags),
        "created_group": created_group,
        "occurrences": occurrences,
    }
    _log_event("promote_orphan_tag", payload, config)

    return PromoteTagResponse(**payload)


__all__ = ["router"]

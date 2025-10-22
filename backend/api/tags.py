"""
Tag management endpoints for label packs.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import label_pack as label_pack_core
from app.core import labels as label_utils

router = APIRouter(prefix="/api/tags", tags=["tags"])

LABEL_GROUP_FILES = {
    "objects": "objects.txt",
    "scenes": "scenes.txt",
    "styles": "styles.txt",
}

CONFIG_PATH = Path("config.yaml")
RUN_STATE_PATH = Path("runs/api_state.json")


def _load_yaml(path: Path) -> Dict:
    if not path.exists():
        return {}
    import yaml  # local import to avoid global dependency at import time

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _resolve_label_dir() -> Path:
    config = _load_yaml(CONFIG_PATH)
    value = config.get("labels_file")
    if value:
        path = Path(value).expanduser()
        if path.is_dir():
            return path
    fallback = Path("labels")
    return fallback.resolve()


def _read_group_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return label_utils.normalize_labels(lines)


def _write_group_file(path: Path, values: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_values = sorted(set(label_utils.normalize_labels(values)))
    path.write_text("\n".join(sorted_values) + ("\n" if sorted_values else ""), encoding="utf-8")


def _collect_state_tags() -> Counter:
    if not RUN_STATE_PATH.exists():
        return Counter()
    import json

    with RUN_STATE_PATH.open("r", encoding="utf-8") as handle:
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


@router.get("/summary", response_model=TagSummaryResponse)
def summarize_tags() -> TagSummaryResponse:
    label_dir = _resolve_label_dir()
    groups: List[TagSummaryResponse.Group] = []
    all_tags: Set[str] = set()

    for group_id, filename in LABEL_GROUP_FILES.items():
        path = label_dir / filename
        tags = _read_group_file(path)
        groups.append(
            TagSummaryResponse.Group(
                id=group_id,
                label=group_id.capitalize(),
                path=str(path),
                tags=tags,
            )
        )
        all_tags.update(tags)

    state_counts = _collect_state_tags()
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
    group_id = request.group.lower()
    filename = LABEL_GROUP_FILES.get(group_id)
    if filename is None:
        raise HTTPException(status_code=400, detail="Unknown label group")

    tag = label_utils.normalize_labels([request.tag])
    if not tag:
        raise HTTPException(status_code=400, detail="Tag cannot be empty")
    normalized = tag[0]

    path = _resolve_label_dir() / filename
    tags = _read_group_file(path)
    if normalized in tags:
        raise HTTPException(status_code=409, detail="Tag already exists in this group")

    tags.append(normalized)
    _write_group_file(path, tags)

    return MutateTagResponse(status="created", group=group_id, tag=normalized, total=len(tags))


@router.delete("/item", response_model=MutateTagResponse)
def delete_tag(request: MutateTagRequest) -> MutateTagResponse:
    group_id = request.group.lower()
    filename = LABEL_GROUP_FILES.get(group_id)
    if filename is None:
        raise HTTPException(status_code=400, detail="Unknown label group")

    tag = label_utils.normalize_labels([request.tag])
    if not tag:
        raise HTTPException(status_code=400, detail="Tag cannot be empty")
    normalized = tag[0]

    path = _resolve_label_dir() / filename
    tags = _read_group_file(path)
    if normalized not in tags:
        raise HTTPException(status_code=404, detail="Tag not found in group")

    tags = [value for value in tags if value != normalized]
    _write_group_file(path, tags)

    return MutateTagResponse(status="deleted", group=group_id, tag=normalized, total=len(tags))


__all__ = ["router"]

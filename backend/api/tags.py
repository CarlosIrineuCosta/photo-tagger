"""
Tag management endpoints for label packs.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import label_pack as label_pack_core
from app.core import labels as label_utils

router = APIRouter(prefix="/api/tags", tags=["tags"])

DEFAULT_GROUP_ORDER = ("objects", "scenes", "styles")
IGNORE_GROUP_FILES = {"candidates.txt"}
PROMOTION_LOG_NAME = "tag_events.log"
MANIFEST_FILENAME = "label_pack.yaml"

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
        description: str | None = None
        canonical_count: int | None = None
        supports_bulk: bool = False

    class OrphanTag(BaseModel):
        name: str
        occurrences: int
        suggested_group_id: str | None = Field(default=None, description="ML-suggested target group")
        suggested_label_id: str | None = None
        label_hint: str | None = None
        confidence: float | None = Field(default=None, ge=0.0, le=1.0)

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
    label_id: str | None = Field(default=None, description="Optional canonical label id to assign")


class PromoteTagResponse(BaseModel):
    status: str
    tag: str
    group: str
    group_label: str
    total: int
    created_group: bool = False
    occurrences: int | None = Field(default=None, description="Occurrences tracked in recent runs")


class BulkPromoteRequest(BaseModel):
    promotions: List[dict] = Field(..., description="List of promotions to apply")
    default_group_id: str | None = Field(default=None, description="Fallback group for unspecified targets")
    create_new_groups: bool = Field(default=False, description="Allow auto-creation of new groups")


class BulkPromoteItem(BaseModel):
    tag: str
    status: str = "pending"  # pending, promoted, skipped, failed
    group_id: str | None = None
    group_label: str | None = None
    created_group: bool = False
    error: str | None = None


class BulkPromoteResponse(BaseModel):
    results: List[BulkPromoteItem]
    summary: dict = Field(..., description="Summary statistics of the operation")


class SuggestGroupResponse(BaseModel):
    suggested_group_id: str
    confidence: float = Field(..., description="Confidence score 0-1")
    reasoning: str | None = Field(default=None, description="ML heuristic explanation")
    alternatives: List[dict] = Field(default_factory=list, description="Alternative group suggestions")
    label_id: str | None = Field(default=None, description="Canonical label identifier")


class BulkPromoteAction(BaseModel):
    tag: str = Field(..., description="Orphan tag to promote")
    target_group: str | None = Field(default=None, description="Existing group id to receive the tag")
    new_group_label: str | None = Field(
        default=None, description="Optional label for a new group (will be slugified)"
    )
    label_id: str | None = Field(default=None, description="Optional canonical label id override")


class BulkPromoteRequest(BaseModel):
    actions: List[BulkPromoteAction] = Field(..., description="List of promotion actions to perform")


class BulkPromoteResult(BaseModel):
    tag: str
    status: str
    group: str | None = None
    group_label: str | None = None
    total: int | None = None
    created_group: bool = False
    occurrences: int | None = None
    label_id: str | None = None
    detail: str | None = None


class BulkPromoteResponse(BaseModel):
    results: List[BulkPromoteResult]


@router.get("/summary", response_model=TagSummaryResponse)
def summarize_tags() -> TagSummaryResponse:
    config = _load_config()
    label_dir = _resolve_label_dir(config)

    label_pack: Optional[label_pack_core.LabelPack] = None
    if label_dir.is_dir():
        try:
            label_pack = label_pack_core.load_label_pack(label_dir)
        except Exception:
            label_pack = None

    groups: List[TagSummaryResponse.Group] = []
    all_tags: Set[str] = set()

    if label_pack:
        group_tags: Dict[str, List[str]] = defaultdict(list)
        for label in label_pack.labels:
            group_id = label_pack.tier_for_label.get(label)
            if not group_id:
                continue
            group_tags[group_id].append(label)
            all_tags.add(label)

        sorted_groups: Sequence[Tuple[str, label_pack_core.LabelGroupInfo]] = sorted(
            label_pack.groups.items(),
            key=lambda item: _group_sort_key(item[0], item[1]),
        )

        for group_id, info in sorted_groups:
            tags = group_tags.get(group_id, [])
            canonical_count = sum(1 for meta in label_pack.label_metadata.values() if meta.group == group_id)
            groups.append(
                TagSummaryResponse.Group(
                    id=group_id,
                    label=info.label,
                    path=str(info.path),
                    tags=tags,
                    description=info.description,
                    canonical_count=canonical_count,
                    supports_bulk=info.supports_bulk,
                )
            )
    else:
        group_files = _discover_group_files(label_dir)
        for group_id, path in group_files.items():
            tags = _read_group_file(path)
            groups.append(
                TagSummaryResponse.Group(
                    id=group_id,
                    label=_format_group_label(group_id),
                    path=str(path),
                    tags=tags,
                    canonical_count=len(tags),
                )
            )
            all_tags.update(tags)

    state_counts = _collect_state_tags(config)
    orphan_counts = {tag: count for tag, count in state_counts.items() if tag not in all_tags}
    orphan_tags = [
        _build_orphan_entry(tag, count, label_pack)
        for tag, count in sorted(orphan_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    if label_pack:
        pending_graduations = sum(
            1 for entry in label_pack.promotions if entry.get("status", "pending") != "resolved"
        )
    else:
        pending_graduations = 0

    stats = {
        "groups": len(groups),
        "total_labels": sum(len(group.tags) for group in groups),
        "orphan_labels": len(orphan_tags),
        "samples_indexed": sum(state_counts.values()),
        "pending_graduations": pending_graduations,
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
    state_counts = _collect_state_tags(config)

    payload = _perform_promotion(
        tag=request.tag,
        target_group=request.target_group,
        new_group_label=request.new_group_label,
        config=config,
        label_dir=label_dir,
        group_files=group_files,
        state_counts=state_counts,
        preferred_label_id=request.label_id,
    )
    _log_event("promote_orphan_tag", payload, config)

    return PromoteTagResponse(**payload)


@router.post("/promote/bulk", response_model=BulkPromoteResponse)
def promote_orphan_bulk(request: BulkPromoteRequest) -> BulkPromoteResponse:
    if not request.actions:
        raise HTTPException(status_code=400, detail="Provide at least one action")

    config = _load_config()
    label_dir = _resolve_label_dir(config)
    group_files = _discover_group_files(label_dir)
    state_counts = _collect_state_tags(config)

    results: List[BulkPromoteResult] = []
    for action in request.actions:
        try:
            payload = _perform_promotion(
                tag=action.tag,
                target_group=action.target_group,
                new_group_label=action.new_group_label,
                config=config,
                label_dir=label_dir,
                group_files=group_files,
                state_counts=state_counts,
                preferred_label_id=action.label_id,
            )
            _log_event("promote_orphan_tag_bulk", payload, config)
            results.append(BulkPromoteResult(**payload))
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            results.append(
                BulkPromoteResult(
                    tag=action.tag,
                    status="error",
                    detail=detail,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            results.append(
                BulkPromoteResult(
                    tag=action.tag,
                    status="error",
                    detail=str(exc),
                )
            )

    return BulkPromoteResponse(results=results)


@router.get("/suggest-group", response_model=SuggestGroupResponse)
def suggest_group_for_tag(tag: str, context: str | None = None) -> SuggestGroupResponse:
    """Suggest a target group for an orphan tag based on ML heuristics."""
    config = _load_config()
    label_dir = _resolve_label_dir(config)

    # Load label pack if available
    pack = None
    if label_dir.is_dir():
        try:
            pack = label_pack_core.load_label_pack(label_dir)
        except Exception:
            pack = None

    if not pack:
        # Fallback to simple heuristic if no label pack
        suggested_group = _fallback_suggestion(tag)
        return SuggestGroupResponse(
            suggested_group_id=suggested_group,
            confidence=0.5,
            reasoning="Fallback suggestion based on tag name"
        )

    # Get state counts for context
    state_counts = _collect_state_tags(config)
    occurrences = state_counts.get(tag, 0)

    # Use existing suggestion logic
    suggestion = _suggest_orphan_tag(tag, occurrences, pack)
    if not suggestion:
        # No good match found
        return SuggestGroupResponse(
            suggested_group_id="objects",  # Default fallback
            confidence=0.3,
            reasoning="No strong pattern match found, using default group"
        )

    group_id, label_id, display_name, confidence = suggestion

    # Generate alternatives
    alternatives = []
    for group in pack.groups.values():
        if group.id != group_id:
            alternatives.append({
                "group_id": group.id,
                "group_label": group.label,
                "confidence": max(0.1, confidence - 0.2)  # Lower confidence for alternatives
            })
            if len(alternatives) >= 3:  # Limit alternatives
                break

    return SuggestGroupResponse(
        suggested_group_id=group_id,
        confidence=confidence,
        reasoning=f"Matched with existing label '{display_name}'",
        alternatives=alternatives,
        label_id=label_id
    )


@router.get("/graduations")
def get_pending_graduations() -> Dict[str, object]:
    """Get pending graduations from the label pack manifest."""
    config = _load_config()
    label_dir = _resolve_label_dir(config)

    try:
        pack = label_pack_core.load_label_pack(label_dir)
    except Exception:
        return {"graduations": [], "stats": {"pending": 0, "resolved": 0}}

    # Group graduations by canonical label
    graduations_by_label: Dict[str, List[Dict[str, object]]] = defaultdict(list)

    for promotion in pack.promotions:
        status = promotion.get("status", "pending")
        if status == "resolved":
            continue

        # Group by the canonical label if available, otherwise by the promoted tag
        group_key = promotion.get("label_id") or promotion.get("tag", "")
        graduations_by_label[group_key].append(promotion)

    # Convert to response format
    result = []
    for label_id, promotions in graduations_by_label.items():
        # Get label metadata
        label_meta = pack.label_metadata.get(label_id)
        canonical_label = label_meta.text_label if label_meta else label_id

        result.append({
            "label_id": label_id,
            "canonical_label": canonical_label,
            "group": label_meta.group if label_meta else "",
            "promotions": promotions,
            "count": len(promotions)
        })

    # Sort by count (most promotions first)
    result.sort(key=lambda x: x["count"], reverse=True)

    stats = {
        "pending": sum(1 for p in pack.promotions if p.get("status", "pending") != "resolved"),
        "resolved": sum(1 for p in pack.promotions if p.get("status", "pending") == "resolved")
    }

    return {"graduations": result, "stats": stats}


@router.post("/graduations/{label_id}/resolve")
def resolve_graduation(label_id: str, action: str = "resolve") -> Dict[str, object]:
    """Resolve or skip a graduation for a specific label."""
    config = _load_config()
    label_dir = _resolve_label_dir(config)
    manifest_path = label_dir / MANIFEST_FILENAME

    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="No manifest found")

    data = _load_yaml(manifest_path)
    if not isinstance(data, dict):
        data = {}

    promotions = data.get("promotions", [])
    if not isinstance(promotions, list):
        promotions = []

    # Update promotions for this label
    updated_count = 0
    for promotion in promotions:
        if promotion.get("label_id") == label_id:
            promotion["status"] = "resolved" if action == "resolve" else "skipped"
            promotion["resolved_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            updated_count += 1

    if updated_count == 0:
        raise HTTPException(status_code=404, detail="No pending graduations found for this label")

    # Save the updated manifest
    data["promotions"] = promotions
    try:
        import yaml
        with manifest_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save manifest: {exc}")

    return {
        "status": "success",
        "label_id": label_id,
        "action": action,
        "updated_count": updated_count
    }


def _fallback_suggestion(tag: str) -> str:
    """Simple heuristic for group suggestion when no label pack is available."""
    tag_lower = tag.lower()

    # Simple keyword-based heuristics
    if any(keyword in tag_lower for keyword in ["beach", "ocean", "sea", "water", "lake", "river"]):
        return "scenes"
    if any(keyword in tag_lower for keyword in ["person", "people", "human", "face", "portrait"]):
        return "objects"
    if any(keyword in tag_lower for keyword in ["vintage", "retro", "modern", "classic", "artistic"]):
        return "styles"

    # Default to objects
    return "objects"


def _perform_promotion(
    *,
    tag: str,
    target_group: str | None,
    new_group_label: str | None,
    config: Mapping[str, object],
    label_dir: Path,
    group_files: Dict[str, Path],
    state_counts: Mapping[str, int],
    preferred_label_id: str | None = None,
) -> Dict[str, object]:
    normalized_tag_list = label_utils.normalize_labels([tag])
    if not normalized_tag_list:
        raise HTTPException(status_code=400, detail="Tag cannot be empty")
    normalized_tag = normalized_tag_list[0]

    created_group = False
    group_id: str | None = None
    group_label = ""
    target_path: Path | None = None

    if target_group:
        candidate = target_group.lower()
        target_path = group_files.get(candidate)
        if target_path is None:
            raise HTTPException(status_code=404, detail="Target group not found")
        group_id = candidate
        group_label = _format_group_label(group_id)
    elif new_group_label:
        slug = _slugify_group(new_group_label)
        candidate = slug
        suffix = 2
        while candidate in group_files:
            candidate = f"{slug}-{suffix}"
            suffix += 1
        target_path = label_dir / f"{candidate}.txt"
        group_id = candidate
        group_label = new_group_label.strip() or _format_group_label(candidate)
        created_group = True
        group_files[group_id] = target_path
    else:
        raise HTTPException(status_code=400, detail="Provide target_group or new_group_label")

    assert group_id and target_path

    tags = _read_group_file(target_path)
    if normalized_tag in tags:
        raise HTTPException(status_code=409, detail="Tag already exists in target group")

    tags.append(normalized_tag)
    _write_group_file(target_path, tags)

    occurrences = state_counts.get(normalized_tag)
    label_id = _determine_label_id(label_dir, normalized_tag, preferred_label_id)

    payload: Dict[str, object] = {
        "status": "promoted",
        "tag": normalized_tag,
        "group": group_id,
        "group_label": group_label,
        "total": len(tags),
        "created_group": created_group,
        "occurrences": occurrences,
        "label_id": label_id,
    }
    _record_promotion(label_dir, payload)
    return payload


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


def _slugify_group(label: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", label.lower())
    slug = text.strip("-")
    return slug or "group"


def _format_group_label(group_id: str) -> str:
    if not group_id:
        return "Group"
    parts = group_id.replace("-", " ").replace("_", " ").split()
    return " ".join(word.capitalize() for word in parts)


def _determine_label_id(label_dir: Path, normalized_tag: str, preferred: str | None = None) -> str:
    existing_ids: Set[str] = set()
    try:
        pack = label_pack_core.load_label_pack(label_dir)
    except Exception:
        pack = None
    if pack:
        existing = pack.label_ids_by_text.get(normalized_tag)
        if existing:
            return existing
        existing_ids = set(pack.label_metadata)
    if preferred:
        base = _slugify_group(preferred)
    else:
        base = _slugify_group(normalized_tag)
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _record_promotion(label_dir: Path, payload: Mapping[str, object]) -> None:
    entry = {
        "tag": payload.get("tag"),
        "label_id": payload.get("label_id"),
        "group": payload.get("group"),
        "group_label": payload.get("group_label"),
        "created_group": payload.get("created_group"),
        "total": payload.get("total"),
        "occurrences": payload.get("occurrences"),
        "status": "pending",
        "promoted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    sanitized = {key: value for key, value in entry.items() if value is not None}
    _append_manifest_promotion(label_dir, sanitized)


def _append_manifest_promotion(label_dir: Path, entry: Dict[str, object]) -> None:
    manifest_path = label_dir / MANIFEST_FILENAME
    data = _load_yaml(manifest_path)
    if not isinstance(data, dict):
        data = {}
    if not data:
        data = {"version": 1}
    data.setdefault("version", data.get("version", 1) or 1)
    promotions_obj = data.get("promotions")
    if isinstance(promotions_obj, list):
        promotions = promotions_obj
    else:
        promotions = []
        data["promotions"] = promotions
    promotions.append(entry)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml  # local import to avoid global dependency at import time

        with manifest_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=False)
    except Exception:
        # Writing to the manifest is best-effort and should not break promotions.
        pass


def _group_sort_key(group_id: str, info: Optional[label_pack_core.LabelGroupInfo]) -> Tuple[int, int, str]:
    if info and info.display_order is not None:
        return (0, info.display_order, group_id)
    if group_id in DEFAULT_GROUP_ORDER:
        return (1, DEFAULT_GROUP_ORDER.index(group_id), group_id)
    return (2, 0, group_id)


def _build_orphan_entry(
    tag: str,
    occurrences: int,
    pack: Optional[label_pack_core.LabelPack],
) -> TagSummaryResponse.OrphanTag:
    suggestion_group = None
    suggestion_label = None
    suggestion_hint = None
    confidence = None

    if pack:
        suggestion = _suggest_orphan_tag(tag, occurrences, pack)
        if suggestion:
            suggestion_group, suggestion_label, suggestion_hint, confidence = suggestion

    return TagSummaryResponse.OrphanTag(
        name=tag,
        occurrences=occurrences,
        suggested_group_id=suggestion_group,
        suggested_label_id=suggestion_label,
        label_hint=suggestion_hint,
        confidence=confidence,
    )


def _suggest_orphan_tag(
    tag: str,
    occurrences: int,
    pack: label_pack_core.LabelPack,
) -> Optional[Tuple[str, str, str, float]]:
    normalized = label_utils.normalize_labels([tag])
    if not normalized:
        return None
    token = normalized[0]

    candidates: List[Tuple[str, str, str, str, str]] = []
    for metadata in pack.label_metadata.values():
        candidates.append((metadata.text_label, metadata.id, metadata.group, metadata.name, "canonical"))
        for alias in metadata.aliases:
            candidates.append((alias, metadata.id, metadata.group, metadata.name, "alias"))

    best: Optional[Tuple[float, str, str, str]] = None
    occ_factor = min(occurrences / 10.0, 1.0)
    for candidate_text, canonical_id, group_id, display_name, match_type in candidates:
        if not candidate_text:
            continue
        if candidate_text == token:
            similarity = 1.0
        else:
            similarity = SequenceMatcher(None, token, candidate_text).ratio()
        if similarity < 0.45:
            continue

        base_score = similarity
        if match_type == "alias" and similarity >= 0.85:
            base_score = max(base_score, 0.92)

        combined = (0.7 * base_score) + (0.3 * occ_factor)
        if best is None or combined > best[0]:
            best = (combined, canonical_id, group_id, display_name)

    if best is None:
        return None

    confidence = round(min(best[0], 1.0), 3)
    return best[2], best[1], best[3], confidence


__all__ = ["router"]

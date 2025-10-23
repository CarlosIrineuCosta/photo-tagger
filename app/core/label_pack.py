from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml

from app.core import labels as label_utils


DEFAULT_PROMPT = "a photo of {}"
DEFAULT_GROUPS = ("objects", "scenes", "styles")
IGNORE_FILES = {"candidates.txt"}
MANIFEST_NAME = "label_pack.yaml"


@dataclass(frozen=True)
class LabelGroupInfo:
    id: str
    label: str
    path: Path
    description: Optional[str] = None
    default_threshold: Optional[float] = None
    supports_bulk: bool = False
    allow_user_labels: bool = False
    display_order: Optional[int] = None


@dataclass(frozen=True)
class LabelMetadata:
    id: str
    name: str
    group: str
    text_label: str
    aliases: List[str] = field(default_factory=list)
    threshold: Optional[float] = None
    prompt_templates: List[str] = field(default_factory=list)
    equivalence_group: Optional[str] = None
    disambiguation: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass(frozen=True)
class LabelPack:
    labels: List[str]
    prompts_per_label: Dict[str, List[str]]
    tier_for_label: Dict[str, str]
    tier_thresholds: Dict[str, float]
    label_thresholds: Dict[str, float]
    equivalence_groups: List[List[str]]
    candidates: List[str]
    source_dir: Path
    groups: Dict[str, LabelGroupInfo]
    label_metadata: Dict[str, LabelMetadata]
    label_ids_by_text: Dict[str, str]
    promotions: List[Dict[str, object]]

    def prompt_hash(self) -> str:
        return hash_prompt_map(self.prompts_per_label)


def load_label_pack(path: str | Path) -> LabelPack:
    path = Path(path).expanduser().resolve()
    if not path.is_dir():
        raise NotADirectoryError(f"Label pack directory not found: {path}")

    manifest_path = path / MANIFEST_NAME
    manifest_data = _load_yaml(manifest_path)

    groups_by_id: Dict[str, LabelGroupInfo] = {}
    labels_by_id: Dict[str, LabelMetadata] = {}
    label_ids_by_text: Dict[str, str] = {}
    promotions: List[Dict[str, object]] = []

    if manifest_data:
        _parse_manifest(path, manifest_data, groups_by_id, labels_by_id, label_ids_by_text)
        promotions = _parse_manifest_promotions(manifest_data)

    group_paths: Dict[str, Path] = {}
    if groups_by_id:
        for group_id, info in groups_by_id.items():
            group_paths[group_id] = info.path
    else:
        for group_id in DEFAULT_GROUPS:
            group_paths.setdefault(group_id, path / f"{group_id}.txt")

    for candidate in sorted(path.glob("*.txt")):
        if candidate.name.lower() in IGNORE_FILES:
            continue
        group_id = candidate.stem.lower()
        group_paths.setdefault(group_id, candidate)
        if group_id not in groups_by_id:
            groups_by_id[group_id] = LabelGroupInfo(
                id=group_id,
                label=_labelize(group_id),
                path=group_paths[group_id],
            )

    tier_for_label: Dict[str, str] = {}
    group_to_labels: Dict[str, List[str]] = {}

    for group_id, group_path in group_paths.items():
        values = _read_label_file(group_path)
        group_to_labels[group_id] = list(values)
        for label in values:
            tier_for_label[label] = group_id

    if labels_by_id:
        for metadata in labels_by_id.values():
            group_to_labels.setdefault(metadata.group, [])
            if metadata.text_label not in group_to_labels[metadata.group]:
                group_to_labels[metadata.group].append(metadata.text_label)
            tier_for_label.setdefault(metadata.text_label, metadata.group)

    prompts_config = _load_yaml(path / "prompts.yaml")
    tier_templates: Dict[str, List[str]] = {}
    if isinstance(prompts_config, Mapping):
        for tier, templates in prompts_config.items():
            if not isinstance(tier, str):
                continue
            if not isinstance(templates, Sequence) or isinstance(templates, (str, bytes)):
                continue
            rendered: List[str] = []
            for template in templates:
                if isinstance(template, str):
                    rendered.append(template)
            if rendered:
                tier_templates[tier] = rendered

    thresholds_config = _load_yaml(path / "thresholds.yaml")
    tier_thresholds: Dict[str, float] = {}
    label_thresholds: Dict[str, float] = {}
    if isinstance(thresholds_config, Mapping):
        tiers_raw = thresholds_config.get("tiers", {})
        if isinstance(tiers_raw, Mapping):
            for tier, value in tiers_raw.items():
                if not isinstance(tier, str):
                    continue
                try:
                    tier_thresholds[tier] = float(value)
                except (TypeError, ValueError):
                    continue
        labels_raw = thresholds_config.get("labels", {})
        if isinstance(labels_raw, Mapping):
            for label, value in labels_raw.items():
                if not isinstance(label, str):
                    continue
                normalized = label_utils.normalize_labels([label])
                if not normalized:
                    continue
                try:
                    label_thresholds[normalized[0]] = float(value)
                except (TypeError, ValueError):
                    continue

    # Manifest overrides
    for group_id, info in groups_by_id.items():
        if info.default_threshold is not None:
            tier_thresholds[group_id] = float(info.default_threshold)

    for metadata in labels_by_id.values():
        if metadata.threshold is not None:
            label_thresholds[metadata.text_label] = float(metadata.threshold)

    # Determine group ordering
    group_items = sorted(
        group_paths.items(),
        key=lambda item: _group_sort_key(item[0], groups_by_id.get(item[0])),
    )

    labels: List[str] = []
    seen_labels: set[str] = set()
    for group_id, _ in group_items:
        for label in group_to_labels.get(group_id, []):
            if label in seen_labels:
                continue
            labels.append(label)
            seen_labels.add(label)

    # Add fallback metadata for labels missing from the manifest
    existing_ids = set(labels_by_id)
    for text_label in labels:
        if text_label not in label_ids_by_text:
            base_id = _slugify(text_label)
            canonical_id = _ensure_unique_id(base_id, existing_ids)
            existing_ids.add(canonical_id)
            metadata = LabelMetadata(
                id=canonical_id,
                name=_labelize(text_label),
                group=tier_for_label.get(text_label, ""),
                text_label=text_label,
            )
            labels_by_id[canonical_id] = metadata
            label_ids_by_text[text_label] = canonical_id

    prompts_per_label: Dict[str, List[str]] = {}
    for text_label in labels:
        metadata = labels_by_id.get(label_ids_by_text.get(text_label, ""))
        if metadata and metadata.prompt_templates:
            prompts = _render_templates(metadata.prompt_templates, text_label)
        else:
            tier = tier_for_label.get(text_label)
            base_templates = tier_templates.get(tier)
            if base_templates:
                prompts = _render_templates(base_templates, text_label)
            else:
                prompts = _render_templates([DEFAULT_PROMPT], text_label)
        prompts_per_label[text_label] = prompts

    # Ensure every label has a threshold entry when possible
    for label in labels:
        override = label_thresholds.get(label)
        if override is not None:
            continue
        tier = tier_for_label.get(label)
        if tier is not None and tier in tier_thresholds:
            label_thresholds[label] = tier_thresholds[tier]

    equivalence_data = _load_yaml(path / "equivalences.yaml")
    equivalence_groups: List[List[str]] = []
    if isinstance(equivalence_data, Mapping):
        raw_groups = equivalence_data.get("equivalences", [])
        if isinstance(raw_groups, Sequence) and not isinstance(raw_groups, (str, bytes)):
            for group in raw_groups:
                if not isinstance(group, Iterable):
                    continue
                normalized = label_utils.normalize_labels(group)
                if len(normalized) >= 2:
                    equivalence_groups.append(normalized)

    # Manifest-driven equivalence group handles
    manifest_equivalences: Dict[str, List[str]] = {}
    for metadata in labels_by_id.values():
        if not metadata.equivalence_group:
            continue
        manifest_equivalences.setdefault(metadata.equivalence_group, []).append(metadata.text_label)
    for entries in manifest_equivalences.values():
        normalized = label_utils.normalize_labels(entries)
        if len(normalized) >= 2:
            equivalence_groups.append(normalized)

    candidates = _read_label_file(path / "candidates.txt")

    return LabelPack(
        labels=labels,
        prompts_per_label=prompts_per_label,
        tier_for_label=tier_for_label,
        tier_thresholds=tier_thresholds,
        label_thresholds=label_thresholds,
        equivalence_groups=equivalence_groups,
        candidates=candidates,
        source_dir=path,
        groups=groups_by_id,
        label_metadata=labels_by_id,
        label_ids_by_text=label_ids_by_text,
        promotions=promotions,
    )


def hash_prompt_map(prompts_per_label: Mapping[str, Sequence[str]]) -> str:
    parts: List[str] = []
    for label in sorted(prompts_per_label):
        parts.append(label)
        variants = prompts_per_label[label]
        for variant in variants:
            parts.append(variant)
    blob = "\n".join(parts).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()


def reduce_equivalences(
    label_scores: Sequence[Mapping[str, float]],
    equivalence_groups: Sequence[Sequence[str]],
) -> List[Mapping[str, float]]:
    """
    Filter out lower-scoring synonyms based on equivalence groups.
    """
    score_map = {entry["label"]: float(entry["score"]) for entry in label_scores if "label" in entry}
    for group in equivalence_groups:
        best_label = None
        best_score = float("-inf")
        for candidate in group:
            candidate_score = score_map.get(candidate)
            if candidate_score is None:
                continue
            if candidate_score > best_score:
                best_label = candidate
                best_score = candidate_score
        if best_label is None:
            continue
        for candidate in group:
            if candidate != best_label:
                score_map.pop(candidate, None)
    reduced = [{"label": label, "score": score} for label, score in score_map.items()]
    reduced.sort(key=lambda item: item["score"], reverse=True)
    return reduced


def _read_label_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return label_utils.normalize_labels(lines)


def _load_yaml(path: Path) -> Mapping:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _render_templates(templates: Sequence[str], label: str) -> List[str]:
    rendered: List[str] = []
    for template in templates:
        if not isinstance(template, str):
            continue
        rendered.append(template.format(label) if "{}" in template else template)
    if not rendered:
        rendered.append(DEFAULT_PROMPT.format(label))
    return rendered


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower())
    slug = text.strip("-")
    return slug or "label"


def _ensure_unique_id(base: str, existing: set[str]) -> str:
    candidate = base
    counter = 2
    while candidate in existing:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _labelize(value: str) -> str:
    text = value.replace("-", " ").replace("_", " ")
    return " ".join(part.capitalize() for part in text.split())


def _group_sort_key(group_id: str, info: Optional[LabelGroupInfo]) -> Tuple[int, int, str]:
    if info and info.display_order is not None:
        return (0, info.display_order, group_id)
    if group_id in DEFAULT_GROUPS:
        return (1, DEFAULT_GROUPS.index(group_id), group_id)
    return (2, 0, group_id)


def _parse_manifest(
    base_path: Path,
    manifest: Mapping[str, object],
    groups_out: Dict[str, LabelGroupInfo],
    labels_out: Dict[str, LabelMetadata],
    label_ids_by_text: Dict[str, str],
) -> None:
    raw_groups = manifest.get("groups", [])
    if isinstance(raw_groups, Sequence) and not isinstance(raw_groups, (str, bytes)):
        for entry in raw_groups:
            if not isinstance(entry, Mapping):
                continue
            raw_id = entry.get("id")
            if not isinstance(raw_id, str):
                continue
            group_id = raw_id.strip().lower()
            if not group_id:
                continue
            label = _safe_str(entry.get("label")) or _labelize(group_id)
            raw_path = entry.get("path") or f"{group_id}.txt"
            path_obj = Path(str(raw_path)).expanduser()
            if not path_obj.is_absolute():
                path_obj = base_path / path_obj
            groups_out[group_id] = LabelGroupInfo(
                id=group_id,
                label=label,
                path=path_obj,
                description=_safe_str(entry.get("description")),
                default_threshold=_safe_float(entry.get("default_threshold")),
                supports_bulk=bool(entry.get("supports_bulk", False)),
                allow_user_labels=bool(entry.get("allow_user_labels", False)),
                display_order=_safe_int(entry.get("display_order")),
            )

    raw_labels = manifest.get("labels", {})
    if isinstance(raw_labels, Mapping):
        for label_id, entry in raw_labels.items():
            if not isinstance(label_id, str) or not isinstance(entry, Mapping):
                continue
            canonical_id = label_id.strip()
            if not canonical_id:
                continue
            group = entry.get("group")
            if not isinstance(group, str):
                continue
            group_id = group.strip().lower()
            if not group_id:
                continue
            name = _safe_str(entry.get("name")) or canonical_id
            text_value = entry.get("text_label") or name
            normalized_text = label_utils.normalize_labels([text_value])
            if not normalized_text:
                continue
            text_label = normalized_text[0]
            aliases = _parse_aliases(entry.get("aliases", []))
            prompt_templates = _parse_prompt_templates(entry.get("prompt_templates", []))
            disambiguation = _parse_string_list(entry.get("disambiguation", []))
            metadata = LabelMetadata(
                id=canonical_id,
                name=name,
                group=group_id,
                text_label=text_label,
                aliases=aliases,
                threshold=_safe_float(entry.get("threshold")),
                prompt_templates=prompt_templates,
                equivalence_group=_safe_str(entry.get("equivalence_group")),
                disambiguation=disambiguation,
                notes=_safe_str(entry.get("notes")),
            )
            labels_out[canonical_id] = metadata
            label_ids_by_text[text_label] = canonical_id
            for alias in aliases:
                label_ids_by_text.setdefault(alias, canonical_id)


def _parse_manifest_promotions(manifest: Mapping[str, object]) -> List[Dict[str, object]]:
    promotions: List[Dict[str, object]] = []
    raw_entries = manifest.get("promotions", [])
    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
        return promotions
    for item in raw_entries:
        if isinstance(item, Mapping):
            promotions.append(dict(item))
    return promotions


def _safe_str(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_float(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_aliases(value: object) -> List[str]:
    if isinstance(value, (str, bytes)):
        return label_utils.normalize_labels([value])
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return label_utils.normalize_labels(value)
    return []


def _parse_prompt_templates(value: object) -> List[str]:
    if isinstance(value, (str, bytes)):
        return [str(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        templates: List[str] = []
        for entry in value:
            if isinstance(entry, str):
                templates.append(entry)
        return templates
    return []


def _parse_string_list(value: object) -> List[str]:
    if isinstance(value, (str, bytes)):
        text = str(value).strip()
        return [text] if text else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        result: List[str] = []
        for entry in value:
            if isinstance(entry, str) and entry.strip():
                result.append(entry.strip())
        return result
    return []


__all__ = [
    "LabelGroupInfo",
    "LabelMetadata",
    "LabelPack",
    "load_label_pack",
    "hash_prompt_map",
    "reduce_equivalences",
]

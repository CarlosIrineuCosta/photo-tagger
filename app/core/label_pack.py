from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

import yaml

from app.core import labels as label_utils


DEFAULT_PROMPT = "a photo of {}"


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

    def prompt_hash(self) -> str:
        return hash_prompt_map(self.prompts_per_label)


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


def load_label_pack(path: str | Path) -> LabelPack:
    path = Path(path).expanduser().resolve()
    if not path.is_dir():
        raise NotADirectoryError(f"Label pack directory not found: {path}")

    objects = _read_label_file(path / "objects.txt")
    scenes = _read_label_file(path / "scenes.txt")
    styles = _read_label_file(path / "styles.txt")

    labels = [*objects, *scenes, *styles]
    tier_for_label: Dict[str, str] = {}
    for label in objects:
        tier_for_label[label] = "objects"
    for label in scenes:
        tier_for_label[label] = "scenes"
    for label in styles:
        tier_for_label[label] = "styles"

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
                if not isinstance(template, str):
                    continue
                rendered.append(template)
            if rendered:
                tier_templates[tier] = rendered

    prompts_per_label: Dict[str, List[str]] = {}
    for label in labels:
        tier = tier_for_label.get(label)
        templates = tier_templates.get(tier)
        if not templates:
            prompts_per_label[label] = [DEFAULT_PROMPT.format(label)]
        else:
            prompts_per_label[label] = [template.format(label) for template in templates]

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
    if equivalence_data:
        raw_groups = equivalence_data.get("equivalences", [])
        if isinstance(raw_groups, Sequence) and not isinstance(raw_groups, (str, bytes)):
            for group in raw_groups:
                if not isinstance(group, Iterable):
                    continue
                normalized = label_utils.normalize_labels(group)
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


__all__ = ["LabelPack", "load_label_pack", "hash_prompt_map", "reduce_equivalences"]

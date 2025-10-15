from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence


def normalize_labels(labels: Iterable[str]) -> List[str]:
    """
    Lowercase, strip, and deduplicate label strings while preserving order.
    """
    seen = set()
    normalized: List[str] = []
    for label in labels:
        if label is None:
            continue
        text = str(label).strip().lower()
        if not text or text.startswith("#"):
            continue
        if text not in seen:
            seen.add(text)
            normalized.append(text)
    return normalized


def load_labels(path: str | Path) -> List[str]:
    """
    Load newline-delimited labels from ``path`` and return normalized entries.
    """
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"labels file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        labels = [line.rstrip("\n") for line in handle]
    return normalize_labels(labels)


def merge_labels(primary: Sequence[str], overrides: Sequence[str] | None = None) -> List[str]:
    """
    Merge two label sequences, applying normalization and deduplication.
    """
    if overrides is None:
        return normalize_labels(primary)
    return normalize_labels(list(primary) + list(overrides))


__all__ = ["load_labels", "normalize_labels", "merge_labels"]

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Sequence, Tuple

_PATH_TOKEN_RE = re.compile(r"(19|20)\d{2}(?:[\-_](0?[1-9]|1[0-2])(?:[\-_](0?[1-9]|[12]\d|3[01]))?)?")


def sha1_file(path: str, chunk_size: int = 1 << 20) -> str:
    """Return SHA-1 hash of file bytes."""
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def chunked(seq: Sequence, size: int) -> Iterator[Sequence]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def path_date_tokens(path: str) -> list[str]:
    """Return probable date tokens from path components."""
    tokens: list[str] = []
    for part in Path(path).parts:
        for match in _PATH_TOKEN_RE.finditer(part):
            tokens.append(match.group())
    return tokens


def safe_datetime_parse(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip().replace("\x00", "")
    formats = [
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y%m%d_%H%M%S",
        "%Y%m%d%H%M%S",
        "%Y:%m:%d",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def mean(values: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for v in values:
        total += float(v)
        count += 1
    return total / count if count else 0.0


def normalize(vec) -> Tuple:
    import numpy as np

    arr = np.asarray(vec, dtype="float32")
    norm = float(np.linalg.norm(arr))
    if norm < 1e-6:
        return tuple(arr.tolist())
    return tuple((arr / norm).tolist())


__all__ = [
    "sha1_file",
    "ensure_dir",
    "chunked",
    "path_date_tokens",
    "safe_datetime_parse",
    "mean",
    "normalize",
]

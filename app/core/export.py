from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Mapping, Sequence

CSV_COLUMNS = [
    "path",
    "rel_path",
    "width",
    "height",
    "top1",
    "top1_score",
    "top5_labels",
    "top5_scores",
    "approved_labels",
    "run_id",
    "model_name",
]


def _ensure_columns(row: Mapping[str, object]) -> dict:
    formatted: dict[str, object] = {}
    for column in CSV_COLUMNS:
        value = row.get(column) if isinstance(row, Mapping) else None
        if column in {"top5_labels", "top5_scores", "approved_labels"}:
            formatted[column] = _pipe_join(value)
        else:
            formatted[column] = value
    return formatted


def _pipe_join(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable):
        cleaned = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                cleaned.append(text)
        return "|".join(cleaned)
    return str(value)


def write_csv(rows: Sequence[Mapping[str, object]], dest: str | Path) -> Path:
    """
    Write ``rows`` to ``dest`` following the agreed CSV schema.
    """
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with dest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(_ensure_columns(row))

    return dest_path


def _ensure_exiftool() -> str:
    exe = shutil.which("exiftool")
    if not exe:
        raise RuntimeError("exiftool not found on PATH")
    return exe


def _unique_keywords(keywords: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen = set()
    for keyword in keywords:
        if not keyword:
            continue
        normalized = str(keyword).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def write_sidecars(
    image_paths: Sequence[str | Path],
    keywords: Sequence[Sequence[str]],
    batch_size: int = 256,
) -> None:
    """
    Write .xmp sidecars for ``image_paths`` using ExifTool.

    Each image receives the keywords provided in the paired ``keywords`` entry.
    """
    if len(image_paths) != len(keywords):
        raise ValueError("image_paths and keywords must have the same length")

    exiftool = _ensure_exiftool()
    paths = [Path(path) for path in image_paths]

    for start in range(0, len(paths), max(1, batch_size)):
        stop = min(start + batch_size, len(paths))
        batch_paths = paths[start:stop]
        batch_keywords = keywords[start:stop]

        for path, kws in zip(batch_paths, batch_keywords):
            unique = _unique_keywords(kws)
            if not unique:
                continue
            cmd = [
                exiftool,
                "-P",
                "-overwrite_original",
                "-m",
                "-o",
                "%d%f.xmp",
            ]
            for keyword in unique:
                cmd.extend(
                    [
                        f"-XMP-dc:Subject+={keyword}",
                        f"-IPTC:Keywords+={keyword}",
                    ]
                )
            cmd.append(str(path))
            subprocess.run(cmd, check=True)


__all__ = ["CSV_COLUMNS", "write_csv", "write_sidecars"]

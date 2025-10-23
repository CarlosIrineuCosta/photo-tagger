from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".dng",
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
    ".rw2",
    ".orf",
}


def _normalize_root(root: str | Path) -> Path:
    root_path = Path(root).expanduser()
    if not root_path.is_absolute():
        root_path = (Path.cwd() / root_path).resolve()
    return root_path


def _iter_image_files(root: Path, include_exts: Iterable[str]) -> Iterable[Path]:
    allowed = {ext.lower() for ext in include_exts}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in allowed:
            yield path


def scan_directory(
    root: str | Path,
    include_exts: Iterable[str] | None = None,
    max_images: int | None = None,
) -> List[str]:
    """
    Return a sorted list of absolute image paths under ``root``.

    Only files whose suffix is in ``include_exts`` (defaults to JPEG/PNG) are
    returned. Paths are resolved to their absolute form. Results are truncated
    to ``max_images`` if provided.
    """
    include = list(include_exts) if include_exts is not None else sorted(IMAGE_EXTENSIONS)
    if not include:
        return []

    root_path = _normalize_root(root)
    if not root_path.exists():
        return []

    collected: List[str] = []
    for path in _iter_image_files(root_path, include):
        collected.append(str(path))
        if max_images is not None and len(collected) >= max_images:
            break

    collected.sort()
    return collected


def scan_directories(
    roots: Sequence[str | Path],
    include_exts: Iterable[str] | None = None,
    max_images: int | None = None,
) -> List[str]:
    """
    Convenience wrapper that accepts multiple roots and returns unique, sorted
    absolute paths respecting ``max_images`` across the combined results.
    """
    include = list(include_exts) if include_exts is not None else sorted(IMAGE_EXTENSIONS)
    seen = set()
    collected: List[str] = []

    for root in roots:
        for path in scan_directory(root, include_exts=include, max_images=None):
            if path in seen:
                continue
            seen.add(path)
            collected.append(path)
            if max_images is not None and len(collected) >= max_images:
                collected.sort()
                return collected

    collected.sort()
    return collected


__all__ = ["scan_directory", "scan_directories", "IMAGE_EXTENSIONS"]

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Sequence

from PIL import Image

DEFAULT_CACHE_ROOT = Path("thumb_cache")
DEFAULT_MAX_EDGE = 512


def _sha1_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_cache_root(cache_root: Path) -> Path:
    cache_root.mkdir(parents=True, exist_ok=True)
    return cache_root


def thumbnail_path(image_path: str | Path, cache_root: str | Path = DEFAULT_CACHE_ROOT) -> Path:
    """
    Return the expected thumbnail path for ``image_path`` inside ``cache_root``.
    """
    cache_root = _ensure_cache_root(Path(cache_root))
    image_path = Path(image_path)
    digest = _sha1_file(image_path)
    return cache_root / f"{digest}.jpg"


def _resize_image(image: Image.Image, max_edge: int) -> Image.Image:
    width, height = image.size
    if max(width, height) <= max_edge:
        return image
    if width >= height:
        new_width = max_edge
        new_height = int(height * (max_edge / width))
    else:
        new_height = max_edge
        new_width = int(width * (max_edge / height))
    resample = getattr(Image, "Resampling", Image).LANCZOS  # Pillow < 9 fallback
    return image.resize((new_width, new_height), resample)


def build_thumbnail(
    image_path: str | Path,
    cache_root: str | Path = DEFAULT_CACHE_ROOT,
    max_edge: int = DEFAULT_MAX_EDGE,
    overwrite: bool = False,
) -> dict:
    """
    Create (or reuse) the cached thumbnail for ``image_path`` and return metadata.
    """
    image_path = Path(image_path)
    thumb_path = thumbnail_path(image_path, cache_root=cache_root)

    if thumb_path.exists() and not overwrite:
        with Image.open(thumb_path) as thumb:
            width, height = thumb.size
    else:
        with Image.open(image_path) as original:
            original = original.convert("RGB")
            resized = _resize_image(original, max_edge)
            width, height = resized.size
            resized.save(thumb_path, format="JPEG", quality=90, optimize=True)

    return {
        "path": str(image_path),
        "thumbnail": str(thumb_path),
        "width": width,
        "height": height,
        "sha1": thumb_path.stem,
    }


def build_thumbnails(
    image_paths: Sequence[str | Path],
    cache_root: str | Path = DEFAULT_CACHE_ROOT,
    max_edge: int = DEFAULT_MAX_EDGE,
    overwrite: bool = False,
) -> List[dict]:
    """
    Generate thumbnails for ``image_paths`` and return their metadata.
    """
    results: List[dict] = []
    for image_path in image_paths:
        results.append(
            build_thumbnail(
                image_path=image_path,
                cache_root=cache_root,
                max_edge=max_edge,
                overwrite=overwrite,
            )
        )
    return results


__all__ = [
    "DEFAULT_CACHE_ROOT",
    "DEFAULT_MAX_EDGE",
    "build_thumbnail",
    "build_thumbnails",
    "thumbnail_path",
]

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List, Sequence
import xml.etree.ElementTree as ET

from PIL import Image

try:
    import rawpy
except Exception:  # pragma: no cover - rawpy is optional at import time
    rawpy = None

from app.config import load_config

RAW_EXTENSIONS = {
    ".dng",
    ".nef",
    ".arw",
    ".cr2",
    ".cr3",
    ".rw2",
    ".orf",
    ".raf",
    ".srw",
}

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


def _parse_xmp_exposure(xmp_path: Path) -> dict | None:
    """
    Parse an XMP file and extract the exposure setting.
    This is a simplified parser for demonstration.
    """
    try:
        tree = ET.parse(xmp_path)
        root = tree.getroot()
        # Namespace may vary, so we search for the tag with a wildcard
        for desc in root.findall(".//{*}Description"):
            exposure = desc.get("{http://ns.adobe.com/crs/1.0/}Exposure2012")
            if exposure:
                return {"exposure": float(exposure)}
    except (ET.ParseError, FileNotFoundError):
        return None
    return None


def build_thumbnail(
    image_path: str | Path,
    cache_root: str | Path = DEFAULT_CACHE_ROOT,
    max_edge: int = DEFAULT_MAX_EDGE,
    overwrite: bool = False,
    config_path: str = "config.yaml",
) -> dict:
    """
    Create (or reuse) the cached thumbnail for ``image_path`` and return metadata.
    """
    image_path = Path(image_path)
    thumb_path = thumbnail_path(image_path, cache_root=cache_root)
    
    config = load_config(config_path)
    thumb_config = config.get("thumbnails", {})
    xmp_processing = thumb_config.get("xmp_processing", False)
    xmp_cache_dir = Path(thumb_config.get("xmp_cache_dir", "xmp_cache"))

    if thumb_path.exists() and not overwrite:
        with Image.open(thumb_path) as thumb:
            width, height = thumb.size
    else:
        ext = image_path.suffix.lower()
        if ext in RAW_EXTENSIONS:
            if rawpy is None:
                raise RuntimeError(
                    f"rawpy is required to process RAW files (missing dependency for {image_path})"
                )
            
            postprocess_params = {
                "use_auto_wb": True,
                "no_auto_bright": True,
                "output_color": rawpy.ColorSpace.sRGB,
                "output_bps": 8,
            }

            if xmp_processing:
                xmp_path = image_path.with_suffix(".xmp")
                if xmp_path.exists():
                    xmp_sha1 = _sha1_file(xmp_path)
                    xmp_cache_path = _ensure_cache_root(xmp_cache_dir) / f"{xmp_sha1}.json"

                    if xmp_cache_path.exists():
                        with open(xmp_cache_path, "r") as f:
                            adjustments = json.load(f)
                    else:
                        adjustments = _parse_xmp_exposure(xmp_path)
                        if adjustments:
                            with open(xmp_cache_path, "w") as f:
                                json.dump(adjustments, f)
                    
                    if adjustments and "exposure" in adjustments:
                        # The 'bright' parameter in rawpy is a multiplier.
                        # An exposure of +1 in Lightroom is roughly equivalent to doubling the brightness.
                        # So we can use 2^exposure as a multiplier.
                        postprocess_params["bright"] = 2 ** adjustments["exposure"]
                        postprocess_params["no_auto_bright"] = False # Allow brightness adjustment

            with rawpy.imread(str(image_path)) as raw:
                rgb = raw.postprocess(**postprocess_params)
                original = Image.fromarray(rgb)
        else:
            original = Image.open(image_path)

        with original:
            converted = original.convert("RGB")
            resized = _resize_image(converted, max_edge)
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
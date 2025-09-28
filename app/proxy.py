from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import numpy as np
from PIL import Image

from app.utils import ensure_dir

try:
    import rawpy
except Exception:  # pragma: no cover - optional at import time
    rawpy = None

_RAW_EXTS = {".dng", ".nef", ".arw", ".cr2", ".cr3", ".rw2", ".orf"}


def _load_image(path: Path) -> Image.Image:
    ext = path.suffix.lower()
    if ext in _RAW_EXTS and rawpy is not None:
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(use_camera_wb=True, output_bps=8, no_auto_bright=True)
        return Image.fromarray(rgb)
    return Image.open(path).convert("RGB")


def _resize(image: Image.Image, max_edge: int) -> Image.Image:
    w, h = image.size
    if max(w, h) <= max_edge:
        return image
    if w >= h:
        new_w = max_edge
        new_h = int(h * (max_edge / w))
    else:
        new_h = max_edge
        new_w = int(w * (max_edge / h))
    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _luminance_stats(image: Image.Image) -> Tuple[float, float]:
    arr = np.asarray(image, dtype="float32") / 255.0
    if arr.ndim == 3:
        lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    else:
        lum = arr
    median = float(np.median(lum))
    dark_ratio = float((lum < 0.08).mean())
    return median, dark_ratio


def build_proxy(
    source_path: str,
    sha1: str,
    proxies_dir: Path,
    max_edge: int = 1024,
    jpeg_quality: int = 90,
    overwrite: bool = False,
) -> Dict:
    proxies_dir = ensure_dir(proxies_dir)
    out_path = proxies_dir / f"{sha1}.jpg"
    if out_path.exists() and not overwrite:
        with Image.open(out_path) as img:
            median, dark_ratio = _luminance_stats(img)
            width, height = img.size
        return {
            "path": source_path,
            "proxy_path": str(out_path),
            "proxy_width": width,
            "proxy_height": height,
            "median_luma": median,
            "dark_ratio": dark_ratio,
        }

    image = _load_image(Path(source_path))
    image = _resize(image, max_edge)
    median, dark_ratio = _luminance_stats(image)
    width, height = image.size
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="JPEG", quality=jpeg_quality, optimize=True)

    return {
        "path": source_path,
        "proxy_path": str(out_path),
        "proxy_width": width,
        "proxy_height": height,
        "median_luma": median,
        "dark_ratio": dark_ratio,
    }


__all__ = ["build_proxy"]

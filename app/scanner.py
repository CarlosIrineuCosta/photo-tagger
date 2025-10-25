from __future__ import annotations

import os
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import exifread
from PIL import Image

from app.utils import path_date_tokens, safe_datetime_parse, sha1_file

try:
    import rawpy
except Exception:  # pragma: no cover - rawpy optional at build time
    rawpy = None


_RAW_EXTS = {".dng", ".nef", ".arw", ".cr2", ".cr3", ".rw2", ".orf"}


def _ratio_to_float(value) -> Optional[float]:
    try:
        if hasattr(value, "num") and hasattr(value, "den"):
            return float(value.num) / float(value.den) if value.den else None
        return float(value)
    except Exception:
        return None


def _read_exif_metadata(path: str) -> Dict[str, Optional[datetime]]:
    meta: Dict[str, Optional[datetime] | str | float] = {
        "exif_datetime_original": None,
        "exif_datetime_create": None,
        "iso": None,
        "fnumber": None,
        "exposure_time": None,
        "focal_length": None,
        "make": None,
        "model": None,
        "lens_model": None,
    }
    try:
        with open(path, "rb") as fh:
            tags = exifread.process_file(fh, details=False)
    except Exception:
        return meta

    dto = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
    dtc = tags.get("EXIF DateTimeDigitized") or tags.get("Image DateTime")
    if dto:
        meta["exif_datetime_original"] = safe_datetime_parse(str(dto))
    if dtc:
        meta["exif_datetime_create"] = safe_datetime_parse(str(dtc))

    if tags.get("EXIF ISOSpeedRatings"):
        meta["iso"] = _ratio_to_float(tags["EXIF ISOSpeedRatings"])
    if tags.get("EXIF FNumber"):
        meta["fnumber"] = _ratio_to_float(tags["EXIF FNumber"])
    if tags.get("EXIF ExposureTime"):
        exposure = _ratio_to_float(tags["EXIF ExposureTime"])
        if exposure:
            meta["exposure_time"] = exposure
    if tags.get("EXIF FocalLength"):
        meta["focal_length"] = _ratio_to_float(tags["EXIF FocalLength"])
    if tags.get("Image Make"):
        meta["make"] = str(tags["Image Make"]).strip()
    if tags.get("Image Model"):
        meta["model"] = str(tags["Image Model"]).strip()
    if tags.get("EXIF LensModel"):
        meta["lens_model"] = str(tags["EXIF LensModel"]).strip()

    return meta


def _read_dimensions(path: str) -> Tuple[int, int]:
    ext = Path(path).suffix.lower()
    if ext in _RAW_EXTS and rawpy is not None:
        try:
            with rawpy.imread(path) as raw:
                sizes = raw.sizes
                return int(sizes.width), int(sizes.height)
        except Exception:
            return 0, 0
    try:
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return 0, 0


def _fs_datetimes(stat_res) -> Tuple[datetime, datetime]:
    mtime = datetime.fromtimestamp(stat_res.st_mtime)
    ctime = datetime.fromtimestamp(stat_res.st_ctime)
    return mtime, ctime


def _sane(dt: Optional[datetime], cfg: Dict) -> bool:
    if not dt:
        return False
    start, end = cfg.get("sane_range", [1990, 2100])
    return start <= dt.year <= end


def resolve_datetime(meta: Dict, cfg: Dict) -> Tuple[Optional[datetime], float, List[str]]:
    weights = cfg.get("weights", {})
    outlier_days = cfg.get("outlier_days", 30)

    dt_original = meta.get("exif_datetime_original")
    dt_create = meta.get("exif_datetime_create")
    fs_mtime = meta.get("fs_mtime")
    fs_ctime = meta.get("fs_ctime")
    path_tokens = meta.get("path_tokens", [])

    path_dt = None
    for token in path_tokens:
        dt = safe_datetime_parse(token.replace("_", "-").replace("/", "-"))
        if dt:
            path_dt = dt
            break

    signals = {
        "exif_original": dt_original if _sane(dt_original, cfg) else None,
        "exif_create": dt_create if _sane(dt_create, cfg) else None,
        "fs_time": fs_mtime,
        "fs_ctime": fs_ctime,
        "path_tokens": path_dt,
    }

    priority = ["exif_original", "exif_create", "fs_time", "path_tokens", "fs_ctime"]
    chosen = None
    chosen_label = None
    for label in priority:
        dt = signals.get(label)
        if dt is not None:
            chosen = dt
            chosen_label = label
            break

    trust = 0.0
    used = []
    if chosen is None:
        return None, trust, used

    for label, dt in signals.items():
        if dt is None:
            continue
        delta = abs((chosen - dt).days)
        if label != chosen_label and delta > outlier_days:
            continue
        trust += weights.get(label, 0.0)
        used.append(label)

    return chosen, min(trust, 1.0), used


import json

def crawl(
    roots: Iterable[str],
    include_ext: Iterable[str],
    exclude_regex: Iterable[str],
    date_cfg: Optional[Dict] = None,
    force_rescan: bool = False,
) -> List[Dict]:
    include = {ext.lower() for ext in include_ext}
    patterns = [re.compile(pat, re.IGNORECASE) for pat in exclude_regex]
    date_cfg = date_cfg or {}

    rows: List[Dict] = []
    seq = 0

    if not roots:
        return []

    first_root = Path(roots[0])
    cache_path = first_root / ".tagger_cache.json"
    
    cached_mtimes = {}
    if not force_rescan and cache_path.exists():
        try:
            with open(cache_path, "r") as f:
                cached_mtimes = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            cached_mtimes = {}

    current_mtimes = {}

    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                ext = Path(name).suffix.lower()
                if include and ext not in include:
                    continue
                if any(p.search(name) for p in patterns):
                    continue

                full_path = os.path.join(dirpath, name)
                try:
                    stat_res = os.stat(full_path)
                except FileNotFoundError:
                    continue

                # TIFF guardrail
                if ext in {".tif", ".tiff"} and stat_res.st_size > 1 * 1024 * 1024 * 1024:  # 1GB
                    continue

                mtime = stat_res.st_mtime
                
                file_status = "new"
                if full_path in cached_mtimes:
                    if mtime == cached_mtimes[full_path]:
                        file_status = "unchanged"
                    else:
                        file_status = "modified"

                sha1 = sha1_file(full_path)
                exif_meta = _read_exif_metadata(full_path)
                width, height = _read_dimensions(full_path)
                fs_mtime, fs_ctime = _fs_datetimes(stat_res)
                path_tokens = path_date_tokens(full_path)

                meta = {
                    "id": seq,
                    "path": full_path,
                    "ext": ext,
                    "sha1": sha1,
                    "bytes": stat_res.st_size,
                    "mtime": mtime,
                    "ctime": stat_res.st_ctime,
                    "fs_mtime": fs_mtime,
                    "fs_ctime": fs_ctime,
                    "width": width,
                    "height": height,
                    **exif_meta,
                    "path_tokens": path_tokens,
                    "status": file_status,
                }

                resolved_dt, trust, used = resolve_datetime(meta, date_cfg)
                meta.update(
                    {
                        "resolved_datetime": resolved_dt,
                        "date_trust": trust,
                        "date_signals_used": used,
                    }
                )

                rows.append(meta)
                current_mtimes[full_path] = mtime
                seq += 1

    # Save updated cache
    try:
        with open(cache_path, "w") as f:
            json.dump(current_mtimes, f)
    except IOError:
        pass

    return rows


__all__ = ["crawl", "resolve_datetime"]

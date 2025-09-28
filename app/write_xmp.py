from __future__ import annotations

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable, List


def _ensure_exiftool() -> str:
    exe = shutil.which("exiftool")
    if not exe:
        raise RuntimeError("exiftool not found in PATH")
    return exe


def _write_single(exiftool_path: str, path: str, keywords: Iterable[str]):
    keywords = list(dict.fromkeys([kw.strip() for kw in keywords if kw and kw.strip()]))
    if not keywords:
        return
    cmd = [exiftool_path, "-overwrite_original"]
    for kw in keywords:
        cmd.append(f"-XMP-dc:Subject+={kw}")
        cmd.append(f"-IPTC:Keywords+={kw}")
    cmd.append(path)
    subprocess.run(cmd, check=True)


def write_keywords(
    paths: List[str],
    keywords: List[List[str]],
    prefix_ck: str,
    prefix_ai: str,
    workers: int = 4,
):
    exiftool_path = _ensure_exiftool()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for path, kws in zip(paths, keywords):
            pool.submit(_write_single, exiftool_path, path, kws)


__all__ = ["write_keywords"]

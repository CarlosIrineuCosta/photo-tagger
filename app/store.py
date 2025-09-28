from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.utils import ensure_dir


class CacheStore:
    """Helper around configured cache_root."""

    def __init__(self, cache_root: str):
        self.root = ensure_dir(cache_root)

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def parquet(self, name: str) -> Path:
        return self.path(f"{name}.parquet")

    def csv(self, name: str) -> Path:
        return self.path(f"{name}.csv")

    def proxies_dir(self) -> Path:
        return ensure_dir(self.path("proxies"))

    def sqlite_db(self, filename: str) -> Path:
        return self.path(filename)


__all__ = ["CacheStore"]

from __future__ import annotations

import shutil
from pathlib import Path

from backend.api import index


def _setup_test_env(monkeypatch, tmp_path: Path, *, images_state: dict | None = None):
    monkeypatch.setattr(index, "load_config", lambda: {"thumb_cache": str(tmp_path)})
    monkeypatch.setattr(index, "get_state", lambda cfg: {"images": images_state or {}})
    index.THUMB_PREFETCH_JOBS.clear()


def test_thumb_prefetch_success(tmp_path, monkeypatch):
    sample_src = Path("tests/images/20240525_161829.jpg")
    sample_dst = tmp_path / "sample.jpg"
    shutil.copy(sample_src, sample_dst)

    processed_paths: list[str] = []

    def fake_build(path: str, *, cache_root: str, overwrite: bool):
        processed_paths.append(path)
        cache_dir = Path(cache_root)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "sample_thumb.jpg").touch()

    monkeypatch.setattr(index.thumbs_core, "build_thumbnail", fake_build)
    _setup_test_env(monkeypatch, tmp_path)

    request = index.ThumbPrefetchRequest(paths=[str(sample_dst)], overwrite=False)
    response = index.prefetch_thumbnails(request)
    payload = response.model_dump()
    assert payload["scheduled"] == 1
    job_id = payload["job_id"]
    assert processed_paths == [str(sample_dst)]

    status_response = index.get_prefetch_job_status(job_id)
    status = status_response.model_dump()
    assert status["status"] == "complete"
    assert status["processed"] == 1
    assert status["total"] == 1
    assert status["errors"] == []


def test_thumb_prefetch_reports_errors(tmp_path, monkeypatch):
    sample_src = Path("tests/images/20240525_161829.jpg")
    sample_dst = tmp_path / "broken.jpg"
    shutil.copy(sample_src, sample_dst)

    def failing_build(path: str, *, cache_root: str, overwrite: bool):
        raise RuntimeError("boom")

    monkeypatch.setattr(index.thumbs_core, "build_thumbnail", failing_build)
    _setup_test_env(monkeypatch, tmp_path)

    request = index.ThumbPrefetchRequest(paths=[str(sample_dst)], overwrite=False)
    response = index.prefetch_thumbnails(request)
    payload = response.model_dump()
    job_id = payload["job_id"]
    assert payload["scheduled"] == 1

    status_response = index.get_prefetch_job_status(job_id)
    status = status_response.model_dump()
    assert status["status"] == "error"
    assert status["processed"] == 0
    assert status["total"] == 1
    assert len(status["errors"]) == 1
    assert "boom" in status["errors"][0]

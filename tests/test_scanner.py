from datetime import datetime, timedelta
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app import scanner


def test_resolve_datetime_prefers_exif_and_accumulates_trust():
    base = datetime(2021, 5, 1, 12, 0, 0)
    meta = {
        "exif_datetime_original": base,
        "exif_datetime_create": base + timedelta(minutes=1),
        "fs_mtime": base + timedelta(days=1),
        "fs_ctime": base + timedelta(days=40),
        "path_tokens": ["2021-05-02"],
    }
    cfg = {
        "sane_range": [1990, 2100],
        "outlier_days": 30,
        "weights": {
            "exif_original": 0.6,
            "exif_create": 0.2,
            "fs_time": 0.1,
            "path_tokens": 0.1,
            "fs_ctime": 0.1,
        },
    }

    resolved, trust, used = scanner.resolve_datetime(meta, cfg)

    assert resolved == base
    # fs_ctime should be ignored due to being outside outlier window
    assert trust == pytest.approx(1.0)
    assert used == ["exif_original", "exif_create", "fs_time", "path_tokens"]


def test_resolve_datetime_falls_back_to_filesystem_when_no_exif():
    fs_time = datetime(2023, 9, 27, 10, 0, 0)
    meta = {
        "exif_datetime_original": None,
        "exif_datetime_create": None,
        "fs_mtime": fs_time,
        "fs_ctime": fs_time,
        "path_tokens": ["2023-09-27"],
    }
    cfg = {
        "weights": {"fs_time": 0.5, "path_tokens": 0.5},
        "outlier_days": 30,
    }

    resolved, trust, used = scanner.resolve_datetime(meta, cfg)

    assert resolved == fs_time
    assert trust == pytest.approx(1.0)
    assert used[0] == "fs_time"
    assert "path_tokens" in used


def test_resolve_datetime_returns_none_when_no_signals():
    resolved, trust, used = scanner.resolve_datetime({}, {})
    assert resolved is None
    assert trust == 0.0
    assert used == []


@patch("exifread.process_file", return_value={})
def test_crawl_skips_large_tiff(mock_exif, tmp_path: Path):
    """
    Verify that the crawl function skips TIFF files larger than 1GB.
    """
    # Create dummy files
    large_tiff = tmp_path / "large.tif"
    large_tiff.touch()
    small_jpg = tmp_path / "small.jpg"
    small_jpg.touch()

    # Mock os.stat to return different sizes
    def mock_stat(path):
        mock_stat_result = MagicMock()
        mock_stat_result.st_mtime = datetime.now().timestamp()
        mock_stat_result.st_ctime = datetime.now().timestamp()
        if str(path).endswith(".tif"):
            mock_stat_result.st_size = 2 * 1024 * 1024 * 1024  # 2GB
        else:
            mock_stat_result.st_size = 1024 * 1024 # 1MB
        return mock_stat_result

    with patch("os.stat", side_effect=mock_stat):
        results = scanner.crawl(
            roots=[str(tmp_path)],
            include_ext=[".tif", ".jpg"],
            exclude_regex=[],
        )

    assert len(results) == 1
    assert Path(results[0]["path"]).name == "small.jpg"


@patch("exifread.process_file", return_value={})
def test_crawl_delta_computation(mock_exif, tmp_path: Path):
    """
    Verify that the crawl function correctly identifies new, modified, and unchanged files.
    """
    # Initial setup
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    file1 = dir1 / "file1.jpg"
    file1.touch()
    file2 = dir1 / "file2.jpg"
    file2.touch()

    # First run: all files should be new
    results1 = scanner.crawl(roots=[str(dir1)], include_ext=[".jpg"], exclude_regex=[])
    assert len(results1) == 2
    assert {r["status"] for r in results1} == {"new"}

    # Second run: all files should be unchanged
    results2 = scanner.crawl(roots=[str(dir1)], include_ext=[".jpg"], exclude_regex=[])
    assert len(results2) == 2
    assert {r["status"] for r in results2} == {"unchanged"}

    # Modify one file and add another
    file2.write_text("modified")
    file3 = dir1 / "file3.jpg"
    file3.touch()

    # Third run: check for new, modified, and unchanged
    results3 = scanner.crawl(roots=[str(dir1)], include_ext=[".jpg"], exclude_regex=[])
    assert len(results3) == 3
    
    statuses = {Path(r["path"]).name: r["status"] for r in results3}
    assert statuses["file1.jpg"] == "unchanged"
    assert statuses["file2.jpg"] == "modified"
    assert statuses["file3.jpg"] == "new"

from datetime import datetime, timedelta

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

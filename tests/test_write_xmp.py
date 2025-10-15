import pytest

from app import write_xmp


def test_write_single_trims_and_deduplicates(monkeypatch):
    recorded = []

    def fake_run(cmd, check):
        recorded.append(cmd)
        assert check is True

    monkeypatch.setattr(write_xmp.subprocess, "run", fake_run)

    write_xmp._write_single("/usr/bin/exiftool", "/tmp/image.jpg", [" CK:tag  ", "", "CK:tag", "AI:sky"])  # pylint: disable=protected-access

    assert recorded == [
        [
            "/usr/bin/exiftool",
            "-overwrite_original",
            "-XMP-dc:Subject+=CK:tag",
            "-IPTC:Keywords+=CK:tag",
            "-XMP-dc:Subject+=AI:sky",
            "-IPTC:Keywords+=AI:sky",
            "/tmp/image.jpg",
        ]
    ]


def test_write_keywords_uses_exiftool(monkeypatch):
    calls = []

    monkeypatch.setattr(write_xmp.shutil, "which", lambda name: "/usr/bin/exiftool")

    def fake_run(cmd, check):
        calls.append(cmd)

    monkeypatch.setattr(write_xmp.subprocess, "run", fake_run)

    class SyncExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args, **kwargs):
            fn(*args, **kwargs)

    monkeypatch.setattr(write_xmp, "ThreadPoolExecutor", SyncExecutor)

    paths = ["/tmp/a.jpg", "/tmp/b.jpg"]
    keywords = [["CK:one", "CK:one"], []]

    write_xmp.write_keywords(paths, keywords, prefix_ck="CK:", prefix_ai="AI:")

    assert calls == [
        [
            "/usr/bin/exiftool",
            "-overwrite_original",
            "-XMP-dc:Subject+=CK:one",
            "-IPTC:Keywords+=CK:one",
            "/tmp/a.jpg",
        ]
    ]

    # second path has no keywords, so no additional subprocess call
    assert len(calls) == 1


def test_write_keywords_raises_when_exiftool_missing(monkeypatch):
    monkeypatch.setattr(write_xmp.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError):
        write_xmp.write_keywords(["/tmp/x.jpg"], [["tag"]], prefix_ck="CK:", prefix_ai="AI:")

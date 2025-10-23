from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterator

import pytest
import yaml

from app.core import label_pack as label_pack_core
from backend.api import tags as tags_api


@pytest.fixture()
def label_pack_dir(tmp_path: Path) -> Iterator[Path]:
    label_dir = tmp_path / "labels"
    label_dir.mkdir()
    (label_dir / "objects.txt").write_text("camera body\nlens\n", encoding="utf-8")
    (label_dir / "styles.txt").write_text("", encoding="utf-8")

    manifest: Dict[str, object] = {
        "version": 1,
        "groups": [
            {
                "id": "objects",
                "label": "Objects",
                "path": "objects.txt",
                "description": "Physical items, props, and distinct subjects.",
                "default_threshold": 0.25,
                "supports_bulk": True,
            }
        ],
        "labels": {
            "camera-body": {
                "name": "Camera Body",
                "group": "objects",
                "text_label": "camera body",
                "threshold": 0.3,
                "aliases": ["dslr body"],
                "prompt_templates": ["a photo of a {}", "{} closeup"],
                "equivalence_group": "camera-hardware",
            }
        },
        "promotions": [
            {
                "tag": "camera body",
                "label_id": "camera-body",
                "group": "objects",
                "promoted_at": "2024-04-01T12:00:00Z",
                "status": "pending",
            }
        ],
    }
    with (label_dir / "label_pack.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, sort_keys=False)

    yield label_dir


def test_load_label_pack_manifest_populates_metadata(label_pack_dir: Path) -> None:
    pack = label_pack_core.load_label_pack(label_pack_dir)

    assert pack.groups["objects"].label == "Objects"
    assert pack.groups["objects"].supports_bulk is True
    assert pack.label_metadata["camera-body"].aliases == ["dslr body"]
    assert pack.label_metadata["camera-body"].prompt_templates == ["a photo of a {}", "{} closeup"]
    assert pack.label_ids_by_text["camera body"] == "camera-body"
    # Fallback metadata for labels not described in the manifest
    assert "lens" in pack.labels
    assert pack.label_ids_by_text["lens"].startswith("lens")
    assert len(pack.promotions) == 1
    assert pack.promotions[0]["status"] == "pending"


def test_suggest_orphan_tag_uses_manifest_alias(label_pack_dir: Path) -> None:
    pack = label_pack_core.load_label_pack(label_pack_dir)
    suggestion = tags_api._suggest_orphan_tag("dslr body", occurrences=5, pack=pack)
    assert suggestion is not None
    group_id, label_id, label_hint, confidence = suggestion
    assert group_id == "objects"
    assert label_id == "camera-body"
    assert label_hint == "Camera Body"
    assert 0.7 <= confidence <= 1.0

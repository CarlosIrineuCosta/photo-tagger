from __future__ import annotations

import csv
from pathlib import Path

from backend.api.index import _load_medoid_map


def _write_medoid_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "folder",
                "cluster_type",
                "cluster_tag",
                "label_hint",
                "cluster_size",
                "medoid_rel_path",
                "cosine_to_centroid",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def test_load_medoid_map_parses_hybrid_clusters(tmp_path: Path) -> None:
    run_path = tmp_path / "run"
    run_path.mkdir()
    root_path = tmp_path / "root"
    (root_path / "samples").mkdir(parents=True)
    image_path = root_path / "samples" / "image-01.jpg"
    image_path.touch()

    medoids_csv = run_path / "medoids.csv"
    _write_medoid_csv(
        medoids_csv,
        [
            {
                "folder": "samples",
                "cluster_type": "folder",
                "cluster_tag": "",
                "label_hint": "",
                "cluster_size": "12",
                "medoid_rel_path": "samples/image-01.jpg",
                "cosine_to_centroid": "0.9123",
            },
            {
                "folder": "samples",
                "cluster_type": "tag",
                "cluster_tag": "cat",
                "label_hint": "cat",
                "cluster_size": "4",
                "medoid_rel_path": "samples/image-01.jpg",
                "cosine_to_centroid": "0.9542",
            },
            {
                "folder": "samples",
                "cluster_type": "embedding",
                "cluster_tag": "",
                "label_hint": "embedding_1",
                "cluster_size": "3",
                "medoid_rel_path": "samples/image-01.jpg",
                "cosine_to_centroid": "0.8765",
            },
        ],
    )

    medoid_map = _load_medoid_map(run_path, root_path, {})
    absolute_key = str(image_path.resolve())
    assert absolute_key in medoid_map
    entry = medoid_map[absolute_key]
    assert entry["folder"] == "samples"
    assert entry["cluster_size"] == 12
    assert entry["cosine_to_centroid"] == 0.9123
    clusters = entry["clusters"]
    assert len(clusters) == 3
    assert clusters[0]["cluster_type"] == "folder"
    assert clusters[1]["cluster_type"] == "tag"
    assert clusters[1]["cluster_tag"] == "cat"
    assert clusters[2]["cluster_type"] == "embedding"
    # relative lookup should share the same entry
    assert medoid_map["samples/image-01.jpg"] is entry


def test_load_medoid_map_handles_legacy_format(tmp_path: Path) -> None:
    run_path = tmp_path / "run"
    run_path.mkdir()
    root_path = tmp_path / "root"
    (root_path / "set").mkdir(parents=True)
    image_path = root_path / "set" / "legacy.png"
    image_path.touch()

    medoids_dir = tmp_path / "runs" / "docs"
    medoids_dir.mkdir(parents=True)
    medoids_csv = medoids_dir / "legacy.csv"
    with medoids_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["folder", "medoid_rel_path", "cosine_to_centroid"])
        writer.writerow(["set", "set/legacy.png", "0.803"])

    metadata = {"medoids_file": str(medoids_csv)}
    medoid_map = _load_medoid_map(run_path, root_path, metadata)
    absolute_key = str(image_path.resolve())
    entry = medoid_map[absolute_key]
    assert entry["folder"] == "set"
    assert len(entry["clusters"]) == 1
    cluster = entry["clusters"][0]
    assert cluster["cluster_type"] == "folder"
    assert cluster["cosine_to_centroid"] == 0.803

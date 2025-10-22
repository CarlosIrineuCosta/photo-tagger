from __future__ import annotations

import numpy as np

from app.core import medoid as medoid_core


def test_compute_folder_medoids_default_returns_single_medoid() -> None:
    embeddings = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    folder_map = {"mixed": [0, 1, 2]}

    results = medoid_core.compute_folder_medoids(folder_map, embeddings)
    assert "mixed" in results
    mixed = results["mixed"]
    assert mixed["medoid_index"] in {0, 1}
    assert mixed["size"] == 3
    assert mixed["clusters"] == []


def test_compute_folder_medoids_tag_clusters_split_by_label() -> None:
    embeddings = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.95, 0.05, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.95, 0.05],
        ],
        dtype=float,
    )
    folder_map = {"mixed": [0, 1, 2, 3]}
    tags_per_index = {
        0: ["cat"],
        1: ["cat"],
        2: ["dog"],
        3: ["dog"],
    }

    results = medoid_core.compute_folder_medoids(
        folder_map,
        embeddings,
        tags_per_index=tags_per_index,
        use_tag_clusters=True,
        min_cluster_size=1,
    )

    mixed = results["mixed"]
    clusters = mixed["clusters"]
    assert len(clusters) == 2
    cat_cluster = next(cluster for cluster in clusters if cluster["tag"] == "cat")
    dog_cluster = next(cluster for cluster in clusters if cluster["tag"] == "dog")
    assert cat_cluster["size"] == 2
    assert dog_cluster["size"] == 2
    assert cat_cluster["medoid_index"] in {0, 1}
    assert dog_cluster["medoid_index"] in {2, 3}

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
    assert mixed["cluster_mode"] == "simple"
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
    assert cat_cluster["cluster_type"] == "tag"
    assert cat_cluster["label_hint"] == "cat"
    assert cat_cluster["members"] == [0, 1]
    assert dog_cluster["cluster_type"] == "tag"
    assert dog_cluster["label_hint"] == "dog"
    assert dog_cluster["members"] == [2, 3]


def test_compute_folder_medoids_embedding_clusters_when_hybrid() -> None:
    embeddings = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.98, 0.02, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.99, 0.01],
        ],
        dtype=float,
    )
    folder_map = {"mixed": [0, 1, 2, 3]}

    results = medoid_core.compute_folder_medoids(
        folder_map,
        embeddings,
        use_tag_clusters=False,
        cluster_mode="hybrid",
        min_cluster_size=1,
        embedding_cluster_threshold=0.95,
        max_embedding_clusters=3,
    )

    mixed = results["mixed"]
    clusters = mixed["clusters"]
    assert any(cluster["cluster_type"] == "embedding" for cluster in clusters)
    embedding_clusters = [cluster for cluster in clusters if cluster["cluster_type"] == "embedding"]
    assert len(embedding_clusters) >= 2
    first_cluster = embedding_clusters[0]
    assert first_cluster["label_hint"].startswith("embedding_")
    assert first_cluster["size"] >= 1
    assert isinstance(first_cluster["members"], list)

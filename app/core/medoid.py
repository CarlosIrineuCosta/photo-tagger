from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np


def _normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return embeddings / norms


def compute_folder_medoids(
    folder_to_indices: Mapping[str, Sequence[int]],
    embeddings: np.ndarray,
    *,
    tags_per_index: Optional[Mapping[int, Sequence[str]]] = None,
    use_tag_clusters: bool = False,
    min_cluster_size: int = 3,
) -> Dict[str, Dict[str, object]]:
    """
    Compute medoids per folder, optionally clustering by tag before medoid selection.

    Returns a mapping of folder name to a dictionary containing:
        {
            "medoid_index": int,
            "cosine_to_centroid": float,
            "size": int,
            "clusters": [
                {
                    "tag": str,
                    "medoid_index": int,
                    "cosine_to_centroid": float,
                    "size": int,
                },
                ...
            ],
        }
    """
    if embeddings.ndim != 2:
        raise ValueError("embeddings must be a 2D array")
    if min_cluster_size < 1:
        raise ValueError("min_cluster_size must be >= 1")

    normalized = _normalize_embeddings(embeddings)
    results: Dict[str, Dict[str, object]] = {}

    for folder, indices in folder_to_indices.items():
        valid_indices = [idx for idx in indices if 0 <= idx < len(normalized)]
        if not valid_indices:
            continue

        medoid_index, cosine_to_centroid = _compute_medoid_for_indices(valid_indices, normalized)
        folder_result: Dict[str, object] = {
            "medoid_index": medoid_index,
            "cosine_to_centroid": cosine_to_centroid,
            "size": len(valid_indices),
            "clusters": [],
        }

        if use_tag_clusters and tags_per_index:
            clusters = _cluster_by_tag(valid_indices, tags_per_index, min_cluster_size)
            cluster_entries: List[Dict[str, object]] = []
            for tag, cluster_indices in clusters:
                medoid_index, cluster_cosine = _compute_medoid_for_indices(cluster_indices, normalized)
                cluster_entries.append(
                    {
                        "tag": tag,
                        "medoid_index": medoid_index,
                        "cosine_to_centroid": cluster_cosine,
                        "size": len(cluster_indices),
                    }
                )
            folder_result["clusters"] = cluster_entries

        results[folder] = folder_result

    return results


def _compute_medoid_for_indices(indices: Sequence[int], normalized_embeddings: np.ndarray) -> Tuple[int, float]:
    if not indices:
        raise ValueError("indices cannot be empty")
    vectors = normalized_embeddings[indices]
    centroid = vectors.mean(axis=0)
    centroid_norm = np.linalg.norm(centroid)
    centroid_unit = centroid / centroid_norm if centroid_norm else centroid
    similarities = vectors @ centroid_unit
    best_pos = int(np.argmax(similarities))
    return int(indices[best_pos]), float(similarities[best_pos])


def _cluster_by_tag(
    indices: Sequence[int],
    tags_per_index: Mapping[int, Sequence[str]],
    min_cluster_size: int,
) -> List[Tuple[str, List[int]]]:
    buckets: Dict[str, List[int]] = {}
    for idx in indices:
        tags = tags_per_index.get(idx)
        if not tags:
            continue
        for tag in tags:
            if tag is None:
                continue
            normalized_tag = str(tag).strip().lower()
            if not normalized_tag:
                continue
            bucket = buckets.setdefault(normalized_tag, [])
            if idx not in bucket:
                bucket.append(idx)

    clusters: List[Tuple[str, List[int]]] = []
    for tag, bucket in buckets.items():
        unique_indices: List[int] = []
        seen = set()
        for value in bucket:
            if value in seen:
                continue
            seen.add(value)
            unique_indices.append(value)
        if len(unique_indices) >= min_cluster_size:
            clusters.append((tag, unique_indices))

    clusters.sort(key=lambda item: (-len(item[1]), item[0]))
    return clusters


__all__ = ["compute_folder_medoids"]

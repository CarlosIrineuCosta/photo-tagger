from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

DEFAULT_EMBEDDING_THRESHOLD = 0.82
DEFAULT_MAX_EMBEDDING_CLUSTERS = 5
VALID_CLUSTER_MODES = {"simple", "hybrid"}


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
    cluster_mode: str = "simple",
    embedding_cluster_threshold: float = DEFAULT_EMBEDDING_THRESHOLD,
    max_embedding_clusters: Optional[int] = DEFAULT_MAX_EMBEDDING_CLUSTERS,
) -> Dict[str, Dict[str, object]]:
    """
    Compute medoids per folder with optional tag-aware and embedding-aware clustering.

    Returns a mapping of folder name to a dictionary containing:
        {
            "medoid_index": int,
            "cosine_to_centroid": float,
            "size": int,
            "cluster_mode": str,
            "clusters": [
                {
                    "cluster_type": "tag" | "embedding",
                    "tag": str,
                    "label_hint": str,
                    "members": List[int],
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
    if cluster_mode not in VALID_CLUSTER_MODES:
        raise ValueError(f"cluster_mode must be one of {sorted(VALID_CLUSTER_MODES)}")
    if not (0 < embedding_cluster_threshold <= 1.0):
        raise ValueError("embedding_cluster_threshold must be in (0, 1]")
    if max_embedding_clusters is not None and max_embedding_clusters < 1:
        max_embedding_clusters = None

    normalized = _normalize_embeddings(embeddings)
    results: Dict[str, Dict[str, object]] = {}

    for folder, indices in folder_to_indices.items():
        valid_indices = [idx for idx in indices if 0 <= idx < len(normalized)]
        if not valid_indices:
            continue

        medoid_index, cosine_to_centroid = _compute_medoid_for_indices(valid_indices, normalized)
        cluster_entries: List[Dict[str, object]] = []

        tagged_indices: set[int] = set()
        if use_tag_clusters and tags_per_index:
            clusters = _cluster_by_tag(valid_indices, tags_per_index, min_cluster_size)
            for tag, cluster_indices in clusters:
                medoid_idx, cluster_cosine = _compute_medoid_for_indices(cluster_indices, normalized)
                members = sorted(cluster_indices)
                cluster_entries.append(
                    {
                        "cluster_type": "tag",
                        "tag": tag,
                        "label_hint": tag,
                        "members": members,
                        "medoid_index": medoid_idx,
                        "cosine_to_centroid": cluster_cosine,
                        "size": len(members),
                    }
                )
                tagged_indices.update(members)

        if cluster_mode == "hybrid":
            remaining_indices = [idx for idx in valid_indices if idx not in tagged_indices]
            embedding_clusters = _cluster_by_embedding(
                remaining_indices,
                normalized,
                embedding_cluster_threshold,
                max_embedding_clusters,
                min_cluster_size,
            )
            for seq, cluster_indices in enumerate(embedding_clusters, start=1):
                medoid_idx, cluster_cosine = _compute_medoid_for_indices(cluster_indices, normalized)
                members = sorted(cluster_indices)
                cluster_entries.append(
                    {
                        "cluster_type": "embedding",
                        "tag": "",
                        "label_hint": f"embedding_{seq}",
                        "members": members,
                        "medoid_index": medoid_idx,
                        "cosine_to_centroid": cluster_cosine,
                        "size": len(members),
                    }
                )

        folder_result: Dict[str, object] = {
            "medoid_index": medoid_index,
            "cosine_to_centroid": cosine_to_centroid,
            "size": len(valid_indices),
            "cluster_mode": cluster_mode,
            "clusters": cluster_entries,
        }
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


def _cluster_by_embedding(
    indices: Sequence[int],
    normalized_embeddings: np.ndarray,
    threshold: float,
    max_clusters: Optional[int],
    min_cluster_size: int,
) -> List[List[int]]:
    if not indices:
        return []

    remaining = [idx for idx in dict.fromkeys(indices) if 0 <= idx < len(normalized_embeddings)]
    assigned: set[int] = set()
    clusters: List[List[int]] = []
    min_size = max(1, min_cluster_size)

    while remaining and (max_clusters is None or len(clusters) < max_clusters):
        seed = remaining.pop(0)
        if seed in assigned:
            continue

        cluster_members = [seed]
        assigned.add(seed)
        centroid = normalized_embeddings[seed]

        keep: List[int] = []
        for idx in remaining:
            if idx in assigned:
                continue
            vector = normalized_embeddings[idx]
            similarity = float(vector @ centroid)
            if similarity >= threshold:
                cluster_members.append(idx)
                assigned.add(idx)
                centroid = normalized_embeddings[cluster_members].mean(axis=0)
                centroid_norm = np.linalg.norm(centroid)
                centroid = centroid / centroid_norm if centroid_norm else centroid
            else:
                keep.append(idx)

        remaining = keep
        if len(cluster_members) >= min_size:
            clusters.append(sorted(cluster_members))

    clusters.sort(key=lambda cluster: (-len(cluster), cluster[0] if cluster else -1))
    return clusters


__all__ = ["compute_folder_medoids"]

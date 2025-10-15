from __future__ import annotations

from typing import Dict, Mapping, Sequence

import numpy as np


def _normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return embeddings / norms


def compute_folder_medoids(
    folder_to_indices: Mapping[str, Sequence[int]],
    embeddings: np.ndarray,
) -> Dict[str, Dict[str, float]]:
    """
    Compute medoids per folder.

    Returns a mapping of folder path to a dictionary containing:
        {
            "medoid_index": int,
            "cosine_to_centroid": float,
        }
    """
    if embeddings.ndim != 2:
        raise ValueError("embeddings must be a 2D array")

    normalized = _normalize_embeddings(embeddings)
    results: Dict[str, Dict[str, float]] = {}

    for folder, indices in folder_to_indices.items():
        valid_indices = [idx for idx in indices if 0 <= idx < len(normalized)]
        if not valid_indices:
            continue

        vectors = normalized[valid_indices]
        centroid = vectors.mean(axis=0)
        centroid_norm = np.linalg.norm(centroid)
        if centroid_norm == 0:
            centroid_unit = centroid
        else:
            centroid_unit = centroid / centroid_norm

        similarities = vectors @ centroid_unit
        best_pos = int(np.argmax(similarities))
        results[folder] = {
            "medoid_index": int(valid_indices[best_pos]),
            "cosine_to_centroid": float(similarities[best_pos]),
        }

    return results


__all__ = ["compute_folder_medoids"]

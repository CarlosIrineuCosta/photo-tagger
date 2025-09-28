from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import pairwise_distances

try:
    import hdbscan
except ImportError:  # pragma: no cover
    hdbscan = None


@dataclass
class ClusterConfig:
    method: str = "hdbscan"
    min_cluster_size: int = 6
    min_samples: int = 2
    cosine_threshold: float = 0.14
    time_window_minutes: int = 60


def _medoid_index(embeddings: np.ndarray) -> int:
    if len(embeddings) == 1:
        return 0
    distances = pairwise_distances(embeddings, metric="cosine")
    sums = distances.sum(axis=1)
    return int(np.argmin(sums))


def _threshold_cluster(ids: Sequence[int], embeddings: np.ndarray, threshold: float) -> Dict[int, List[int]]:
    clusters: Dict[int, List[int]] = {}
    current_cluster = []
    cluster_idx = 0
    for idx, emb in zip(ids, embeddings):
        if not current_cluster:
            current_cluster.append((idx, emb))
            clusters[cluster_idx] = [idx]
            continue
        last_emb = current_cluster[-1][1]
        cos_dist = float(1.0 - np.dot(last_emb, emb))
        if cos_dist <= threshold:
            clusters.setdefault(cluster_idx, []).append(idx)
            current_cluster.append((idx, emb))
        else:
            cluster_idx += 1
            clusters[cluster_idx] = [idx]
            current_cluster = [(idx, emb)]
    return clusters


def cluster_time_windowed(
    index_df: pd.DataFrame,
    embeds_df: pd.DataFrame,
    cfg_dict: Dict,
    date_cfg: Dict | None = None,
) -> pd.DataFrame:
    defaults = ClusterConfig()
    cfg = ClusterConfig(
        method=cfg_dict.get("method", defaults.method),
        min_cluster_size=cfg_dict.get("min_cluster_size", defaults.min_cluster_size),
        min_samples=cfg_dict.get("min_samples", defaults.min_samples),
        cosine_threshold=cfg_dict.get("cosine_threshold", defaults.cosine_threshold),
        time_window_minutes=cfg_dict.get("time_window_minutes", defaults.time_window_minutes),
    )

    idx_df = index_df.copy()
    idx_df["resolved_datetime"] = pd.to_datetime(idx_df.get("resolved_datetime"))
    idx_df["fallback_time"] = pd.to_datetime(idx_df["mtime"], unit="s")
    idx_df["sort_time"] = idx_df["resolved_datetime"].fillna(idx_df["fallback_time"])
    idx_df = idx_df.sort_values("sort_time").reset_index(drop=True)

    embed_map = {row["id"]: np.asarray(row["emb"], dtype="float32") for _, row in embeds_df.iterrows()}

    results: List[Dict] = []
    cluster_id = 0
    window_minutes = cfg.time_window_minutes
    current_ids: List[int] = []
    current_embeds: List[np.ndarray] = []
    current_start: pd.Timestamp | None = None

    for _, row in idx_df.iterrows():
        rid = int(row["id"])
        emb = embed_map.get(rid)
        if emb is None:
            continue
        ts = row["sort_time"]
        if current_start is None:
            current_start = ts
        delta_minutes = (ts - current_start).total_seconds() / 60.0
        if delta_minutes > window_minutes and current_ids:
            cluster_id = _append_window_clusters(
                results,
                cluster_id,
                current_ids,
                current_embeds,
                cfg,
            )
            current_ids = []
            current_embeds = []
            current_start = ts

        current_ids.append(rid)
        current_embeds.append(emb)

    if current_ids:
        cluster_id = _append_window_clusters(
            results,
            cluster_id,
            current_ids,
            current_embeds,
            cfg,
        )

    df = pd.DataFrame(results)
    return df


def _append_window_clusters(
    results: List[Dict],
    cluster_id_start: int,
    ids: Sequence[int],
    embeds: Sequence[np.ndarray],
    cfg: ClusterConfig,
) -> int:
    if not ids:
        return cluster_id_start
    embeddings = np.stack(embeds)
    clusters: Dict[int, List[int]] = {}

    embed_map = {mid: embed for mid, embed in zip(ids, embeds)}

    if cfg.method == "hdbscan" and hdbscan is not None and len(ids) >= cfg.min_cluster_size:
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=cfg.min_cluster_size,
            min_samples=cfg.min_samples,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(embeddings)
        for lbl, rid in zip(labels, ids):
            if lbl == -1:
                clusters.setdefault(f"noise_{rid}", []).append(rid)
            else:
                clusters.setdefault(int(lbl), []).append(rid)
    else:
        clusters = _threshold_cluster(ids, embeddings, cfg.cosine_threshold)

    next_cluster_id = cluster_id_start
    for _, member_ids in clusters.items():
        member_embeds = np.stack([embed_map[mid] for mid in member_ids])
        medoid_local_idx = _medoid_index(member_embeds)
        medoid_id = member_ids[medoid_local_idx]
        results.append(
            {
                "cluster_id": next_cluster_id,
                "member_ids": member_ids,
                "count": len(member_ids),
                "medoid_id": medoid_id,
                "is_people": False,
            }
        )
        next_cluster_id += 1

    return next_cluster_id


__all__ = ["cluster_time_windowed"]

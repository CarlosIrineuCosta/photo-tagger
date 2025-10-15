# app/core/score.py
from __future__ import annotations
from typing import List, Dict, Tuple
import numpy as np

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # a: [N,D], b: [M,D]; returns [N,M]
    a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
    b = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-8)
    return a @ b.T  # cosine similarity

def score_labels(
    img_emb: "np.ndarray",
    txt_emb: "np.ndarray",
    labels: List[str],
    topk: int = 5,
    threshold: float = 0.25,
) -> List[Dict]:
    """
    Returns one dict per image:
      {
        'top1': str,
        'top1_score': float,
        'topk_labels': List[str],
        'topk_scores': List[float],
        'over_threshold': List[Tuple[str,float]]
      }
    """
    sims = _cosine_sim(img_emb, txt_emb)  # [N_images, N_labels]
    n_img, n_lbl = sims.shape
    k = min(topk, n_lbl)

    out: List[Dict] = []
    for i in range(n_img):
        row = sims[i]
        top_idx = np.argpartition(-row, k-1)[:k]
        # sort those k by score
        top_idx = top_idx[np.argsort(-row[top_idx])]
        top_labels = [labels[j] for j in top_idx]
        top_scores = [float(row[j]) for j in top_idx]
        t1_idx = top_idx[0]
        over = [(labels[j], float(row[j])) for j in np.where(row >= threshold)[0]]

        out.append({
            "top1": labels[t1_idx],
            "top1_score": float(row[t1_idx]),
            "topk_labels": top_labels,
            "topk_scores": top_scores,
            "over_threshold": sorted(over, key=lambda x: -x[1])
        })
    return out

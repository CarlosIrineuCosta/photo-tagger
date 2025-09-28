from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

import numpy as np

from app.embed import ClipEmbedder
from app.heuristics import studio_black_vs_night, suppress_hand_on_nude


@dataclass
class CkConfig:
    vocab: Dict[str, Sequence[str]]
    max_ck_tags: int
    prefix: str
    clip_model: str
    clip_pretrained: str
    device: str = "cuda"


class CkTagger:
    def __init__(self, cfg: CkConfig, heuristics_cfg: Dict):
        self.cfg = cfg
        self.heuristics_cfg = heuristics_cfg
        self.embedder = ClipEmbedder(cfg.clip_model, cfg.clip_pretrained, cfg.device, batch_size=64)
        self.labels: List[str] = []
        prompts: List[str] = []
        for section in ("subjects", "people_concepts", "gear", "places_coarse"):
            for label in cfg.vocab.get(section, []):
                prompts.append(f"a photo of {label}")
                self.labels.append(label)
        text_embeds = self.embedder.encode_text(prompts) if prompts else np.zeros((0, 1))
        self.text_embeds = text_embeds.astype("float32")

    def score(self, image_embedding: np.ndarray) -> List[tuple[str, float]]:
        if self.text_embeds.size == 0:
            return []
        img = np.asarray(image_embedding, dtype="float32")
        if img.ndim == 1:
            img = img[None, :]
        img = img / (np.linalg.norm(img, axis=1, keepdims=True) + 1e-6)
        scores = (img @ self.text_embeds.T)[0]
        pairs = list(zip(self.labels, scores.tolist()))
        pairs.sort(key=lambda p: p[1], reverse=True)
        return pairs

    def tags_for_image(
        self,
        image_embedding: np.ndarray,
        metadata: Dict,
        proxy_meta: Dict,
        has_person: bool = False,
        is_nude: bool = False,
    ) -> List[str]:
        scored = self.score(image_embedding)
        tags: List[str] = []
        suppress = set()
        heuristic_result = studio_black_vs_night(
            metadata,
            proxy_meta,
            self.heuristics_cfg.get("studio_black_vs_night", {}),
            has_person,
            prefix=self.cfg.prefix,
        )
        tags.extend(heuristic_result.get("add", []))
        suppress.update(heuristic_result.get("suppress", []))

        hand_cfg = self.heuristics_cfg.get("hand_tag", {})
        if hand_cfg.get("suppress_on_nude", True) and suppress_hand_on_nude(has_person, is_nude):
            suppress.add(f"{self.cfg.prefix}hand")

        # Add gear tags directly from metadata
        prefix = self.cfg.prefix
        make = (metadata.get("make") or "").lower()
        model = (metadata.get("model") or "").lower()
        lens = (metadata.get("lens_model") or "").lower()

        for gear in self.cfg.vocab.get("gear", []):
            low = gear.lower()
            if low in make or low in model or low in lens:
                tags.append(f"{prefix}{gear}")

        for label, score in scored:
            tag = f"{prefix}{label}"
            if tag in suppress:
                continue
            if tag in tags:
                continue
            tags.append(tag)
            if len(tags) >= self.cfg.max_ck_tags:
                break
        return tags


__all__ = ["CkTagger", "CkConfig"]

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import numpy as np
import torch
import open_clip
from PIL import Image

from app.utils import chunked


class ClipEmbedder:
    def __init__(self, model_name: str, pretrained: str, device: str = "cuda", batch_size: int = 128):
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
        self.device = device
        self.batch_size = batch_size
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained, device=device
        )
        self.model.eval()
        self.tokenizer = open_clip.get_tokenizer(model_name)

    def encode_paths(self, paths: Iterable[str]) -> np.ndarray:
        imgs = list(paths)
        embeds: List[np.ndarray] = []
        with torch.no_grad():
            for batch_paths in chunked(imgs, self.batch_size):
                images = [self.preprocess(Image.open(p).convert("RGB")) for p in batch_paths]
                image_tensor = torch.stack(images).to(self.device)
                feats = self.model.encode_image(image_tensor)
                feats = feats / feats.norm(dim=-1, keepdim=True)
                embeds.append(feats.cpu().numpy())
        if embeds:
            return np.concatenate(embeds, axis=0)
        return np.zeros((0, self.model.visual.output_dim), dtype="float32")

    def encode_text(self, prompts: List[str]) -> np.ndarray:
        with torch.no_grad():
            tokens = self.tokenizer(prompts).to(self.device)
            feats = self.model.encode_text(tokens)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.cpu().numpy()


__all__ = ["ClipEmbedder"]

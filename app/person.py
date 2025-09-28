from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
from PIL import Image

try:
    import torchvision
    from torchvision.transforms.functional import to_tensor
except Exception:  # pragma: no cover
    torchvision = None
    to_tensor = None


@dataclass
class PersonDetectorConfig:
    threshold: float = 0.6
    device: str = "cuda"


class PersonDetector:
    def __init__(self, cfg: PersonDetectorConfig | None = None):
        if cfg is None:
            cfg = PersonDetectorConfig()
        if cfg.device == "cuda" and not torch.cuda.is_available():
            cfg.device = "cpu"
        if torchvision is None:
            raise RuntimeError("torchvision not available")
        weights = torchvision.models.detection.FasterRCNN_ResNet50_FPN_Weights.DEFAULT
        self.model = torchvision.models.detection.fasterrcnn_resnet50_fpn(weights=weights)
        self.model.to(cfg.device)
        self.model.eval()
        self.threshold = cfg.threshold
        self.device = cfg.device
        self.preprocess = weights.transforms()

    def person_present(self, image_path: str) -> bool:
        image = Image.open(image_path).convert("RGB")
        tensor = self.preprocess(image).to(self.device)
        with torch.no_grad():
            outputs = self.model([tensor])
        scores = outputs[0]["scores"].detach().cpu().numpy()
        labels = outputs[0]["labels"].detach().cpu().numpy()
        for score, label in zip(scores, labels):
            if label == 1 and score >= self.threshold:
                return True
        return False


__all__ = ["PersonDetector", "PersonDetectorConfig"]

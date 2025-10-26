from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict

import yaml


@dataclass
class Label:
    id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    description: str | None = None


@dataclass
class LabelPack:
    version: int
    labels: List[Label] = field(default_factory=list)
    
    def get_label_by_id(self, label_id: str) -> Label | None:
        for label in self.labels:
            if label.id == label_id:
                return label
        return None


def load_label_pack(path: Path | str) -> LabelPack:
    """
    Load a label pack from a YAML file.
    """
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    version = data.get("version")
    if version != 1:
        raise ValueError(f"Unsupported label pack version: {version}")

    labels_data = data.get("labels", [])
    labels = [Label(**label_data) for label_data in labels_data]

    return LabelPack(version=version, labels=labels)
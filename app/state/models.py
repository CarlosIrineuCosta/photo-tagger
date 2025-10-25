from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ReviewStage(str, Enum):
    """
    Canonical review stages used by the API and UI.
    """

    NEW = "new"
    NEEDS_TAGS = "needs_tags"
    HAS_DRAFT = "has_draft"
    SAVED = "saved"
    BLOCKED = "blocked"


@dataclass
class ImageState:
    """
    Persistent metadata for a single image tracked by the API.
    """

    stage: ReviewStage
    selected: List[str] = field(default_factory=list)
    saved: bool = False
    first_seen: float = field(default_factory=lambda: time.time())
    last_processed: Optional[float] = None
    last_saved: Optional[float] = None
    blocked_reason: Optional[str] = None
    pending_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "selected": list(self.selected),
            "saved": bool(self.saved),
            "first_seen": float(self.first_seen),
            "last_processed": self.last_processed,
            "last_saved": self.last_saved,
            "blocked_reason": self.blocked_reason,
            "pending_reasons": list(self.pending_reasons),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ImageState":
        stage_value = payload.get("stage")
        try:
            stage = ReviewStage(stage_value)
        except Exception:
            stage = ReviewStage.NEEDS_TAGS
        return cls(
            stage=stage,
            selected=list(payload.get("selected", [])),
            saved=bool(payload.get("saved", False)),
            first_seen=float(payload.get("first_seen", time.time())),
            last_processed=payload.get("last_processed"),
            last_saved=payload.get("last_saved"),
            blocked_reason=payload.get("blocked_reason"),
            pending_reasons=list(payload.get("pending_reasons", [])),
        )


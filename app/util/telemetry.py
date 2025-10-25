from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass(slots=True)
class TelemetryEvent:
    """
    Structured event describing pipeline progress.
    """

    stage: str
    event: str
    duration_ms: float
    item_count: int | None = None
    run_id: str | None = None
    timestamp: float = field(default_factory=lambda: time.time())
    details: dict[str, object] | None = None

    def to_json(self) -> str:
        payload = asdict(self)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "TelemetryEvent":
        data = json.loads(raw)
        return cls(
            stage=str(data.get("stage", "")),
            event=str(data.get("event", "")),
            duration_ms=float(data.get("duration_ms", 0.0)),
            item_count=data.get("item_count"),
            run_id=data.get("run_id"),
            timestamp=float(data.get("timestamp", time.time())),
            details=data.get("details") or None,
        )


def run_telemetry_path(run_dir: Path | str, run_id: str) -> Path:
    """
    Return the JSONL telemetry file for a run.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / run_id / "telemetry.jsonl"


def append_event(path: Path, event: TelemetryEvent) -> None:
    """
    Append an event to the telemetry JSONL file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(event.to_json())
        handle.write("\n")


def extend_events(path: Path, events: Iterable[TelemetryEvent]) -> None:
    """
    Append multiple events efficiently.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(event.to_json())
            handle.write("\n")


def read_events(path: Path, limit: Optional[int] = None) -> List[TelemetryEvent]:
    """
    Read telemetry events from disk, optionally truncating to the most recent N.
    """
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    if limit is not None and limit >= 0:
        lines = lines[-limit:]
    return [TelemetryEvent.from_json(line) for line in lines if line.strip()]


__all__ = ["TelemetryEvent", "run_telemetry_path", "append_event", "extend_events", "read_events"]

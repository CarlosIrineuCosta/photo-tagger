from __future__ import annotations

from pathlib import Path

from app.util.telemetry import (
    TelemetryEvent,
    append_event,
    extend_events,
    read_events,
    run_telemetry_path,
)


def test_run_telemetry_path(tmp_path: Path):
    path = run_telemetry_path(tmp_path, "run123")
    assert path.name == "telemetry.jsonl"
    assert str(path).endswith("run123/telemetry.jsonl")


def test_append_and_read_events(tmp_path: Path):
    path = tmp_path / "telemetry.jsonl"
    event = TelemetryEvent(stage="scan", event="start", duration_ms=12.5, item_count=10, run_id="run123")
    append_event(path, event)

    events = read_events(path)
    assert len(events) == 1
    retrieved = events[0]
    assert retrieved.stage == "scan"
    assert retrieved.event == "start"
    assert retrieved.duration_ms == 12.5
    assert retrieved.item_count == 10
    assert retrieved.run_id == "run123"


def test_extend_events_with_limit(tmp_path: Path):
    path = tmp_path / "telemetry.jsonl"
    events = [
        TelemetryEvent(stage="scan", event="start", duration_ms=10.0),
        TelemetryEvent(stage="scan", event="complete", duration_ms=25.0),
        TelemetryEvent(stage="thumbs", event="complete", duration_ms=50.0),
    ]
    extend_events(path, events)

    recent = read_events(path, limit=2)
    assert len(recent) == 2
    assert [event.event for event in recent] == ["complete", "complete"]

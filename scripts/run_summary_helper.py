import argparse
import json
from pathlib import Path
import sys

# Add the project root to the python path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from app.util.telemetry import read_events, TelemetryEvent


def main():
    parser = argparse.ArgumentParser(description="CLI helper for run summary export.")
    parser.add_argument("--run-id", required=True, help="The ID of the run to summarize.")
    parser.add_argument("--run-dir", default="runs", help="Directory where run artifacts are stored.")
    args = parser.parse_args()

    run_path = Path(args.run_dir) / args.run_id
    if not run_path.exists():
        print(f"Error: Run directory not found: {run_path}", file=sys.stderr)
        sys.exit(1)

    # Load run metadata
    run_meta_path = run_path / "run.json"
    run_meta = {}
    if run_meta_path.exists():
        with run_meta_path.open("r", encoding="utf-8") as f:
            run_meta = json.load(f)

    print(f"--- Run Summary for {args.run_id} ---")
    print(f"Root: {run_meta.get('root', 'N/A')}")
    print(f"Image Count: {run_meta.get('image_count', 'N/A')}")
    print(f"Model: {run_meta.get('model_name', 'N/A')} ({run_meta.get('pretrained', 'N/A')})")
    print("-" * 30)

    # Load telemetry events
    telemetry_path = run_path / "telemetry.jsonl"
    if not telemetry_path.exists():
        print(f"Warning: Telemetry file not found: {telemetry_path}", file=sys.stderr)
        return

    events = read_events(telemetry_path)

    # Process events to extract timings
    timings = {}
    start_times = {}
    for event in events:
        if event.event == "start":
            start_times[event.stage] = event.timestamp
        elif event.event == "complete" and event.stage in start_times:
            duration_ms = (event.timestamp - start_times[event.stage]) * 1000
            timings[event.stage] = f"{duration_ms:.2f} ms"
            if event.item_count is not None:
                timings[event.stage] += f" ({event.item_count} items)"

    print("Processing Times:")
    for stage in ["scan", "thumbs", "embed", "score", "medoids", "export", "run"]:
        if stage in timings:
            print(f"  {stage.capitalize()}: {timings[stage]}")
    print("-" * 30)


if __name__ == "__main__":
    main()

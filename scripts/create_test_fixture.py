import json
from pathlib import Path
import sys

# Add the project root to the python path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from backend.api.index import _prepare_gallery_records, load_config

def create_fixture():
    """
    Generates a trimmed api_state.json fixture from the smoke test data.
    """
    cfg = load_config()
    cfg["root"] = str(project_root / "tests" / "smoke" / "photos")

    _, _, state = _prepare_gallery_records(cfg)

    # Trim timestamps from the state
    if "images" in state and isinstance(state["images"], dict):
        for image_path, image_data in state["images"].items():
            if isinstance(image_data, dict):
                image_data["first_seen"] = 0.0
                image_data["last_processed"] = None
                image_data["last_saved"] = None

    fixture_dir = project_root / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = fixture_dir / "api_state.json"

    with fixture_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)

    print(f"Fixture created at {fixture_path}")

if __name__ == "__main__":
    create_fixture()

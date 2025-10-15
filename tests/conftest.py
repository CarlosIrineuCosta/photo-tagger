import sys
import types
from pathlib import Path

# Ensure the project root is on sys.path so `import app` works without installation.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Provide a lightweight stub for `exifread` so scanner imports work during tests
if "exifread" not in sys.modules:
    exifread_stub = types.ModuleType("exifread")

    def _process_file(_fh, details=False):  # noqa: D401 - simple stub
        return {}

    exifread_stub.process_file = _process_file
    sys.modules["exifread"] = exifread_stub

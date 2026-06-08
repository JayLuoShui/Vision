from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
APP_PATHS = [
    ROOT / "apps" / "cvds_annotation_tool_v2_3",
    ROOT / "apps",
]

for path in reversed(APP_PATHS):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

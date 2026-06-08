from pathlib import Path
import sys


APP_ROOT = Path(__file__).resolve().parent / "cvds_annotation_tool_v2_3"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from cvds_annotation_tool.main import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())

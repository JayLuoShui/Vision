from pathlib import Path
import sys


APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from cvds_jam_video_synthesizer.main import main  # noqa: E402

raise SystemExit(main())

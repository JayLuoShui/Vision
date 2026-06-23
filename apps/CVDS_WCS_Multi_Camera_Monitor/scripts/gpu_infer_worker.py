#!/usr/bin/env python
"""GPU inference worker entry for the standalone WCS multi-camera app.

The production worker is still shared with apps/cvds_cpp_detector. Keeping this
thin wrapper gives the WCS app its own stable script path while avoiding two
copies of the same inference implementation.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    this_file = Path(__file__).resolve()
    repo_root = this_file.parents[3]
    shared_worker = repo_root / "apps" / "cvds_cpp_detector" / "scripts" / "worker_entry.py"
    if not shared_worker.exists():
        sys.stderr.write(f"shared worker not found: {shared_worker}\n")
        return 2
    sys.argv[0] = str(shared_worker)
    runpy.run_path(str(shared_worker), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

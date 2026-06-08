#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    from dws_validator.cli import main as cli_main
    from dws_validator_gui.app import main as gui_main

    args = sys.argv[1:]
    if "--cli" in args or "--diagnose" in args or "--version" in args:
        return cli_main(args)
    return gui_main(args)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Development entry point so ``./main.py`` works from a checkout.

For real installs use ``pipx install .`` (or ``make install``), which puts an
``eco`` command on your PATH via the console script defined in pyproject.toml.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eco.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

"""Pre/post-update hook execution."""

from __future__ import annotations

import logging
import os
import subprocess

from . import console as ui
from .config import Paths

logger = logging.getLogger(__name__)


class Hooks:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths

    def run(self, phase: str) -> None:
        """Run every executable script in ``hooks/<phase>/`` in name order."""
        directory = self.paths.hooks_dir / phase
        if not directory.exists():
            return
        scripts = [s for s in sorted(directory.glob("*")) if os.access(s, os.X_OK)]
        if not scripts:
            return

        ui.rule(f"{phase} hooks")
        for script in scripts:
            try:
                proc = subprocess.run(
                    [str(script)], capture_output=True, text=True, timeout=300
                )
                if proc.returncode == 0:
                    ui.ok(script.name)
                else:
                    ui.err(f"{script.name} (exit {proc.returncode})")
                    logger.error("Hook %s failed: %s", script.name, proc.stderr)
            except subprocess.TimeoutExpired:
                ui.err(f"{script.name} (timeout)")
                logger.error("Hook %s timed out", script.name)
            except OSError as error:
                ui.err(f"{script.name} ({error})")
                logger.error("Hook %s error: %s", script.name, error)

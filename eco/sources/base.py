"""Base types shared by every update source.

The design splits an update into two clearly separated phases:

* ``check()``  -- **read-only**. Safe to run in parallel. Never mutates the
  system, never blocks on interactive input. Returns a :class:`CheckResult`.
* ``apply()``  -- performs the actual update, running the underlying tool with
  the real terminal attached so its prompts/output work normally. Sources that
  share a global lock (pacman & AUR helpers) are applied sequentially by the
  orchestrator, never in parallel.

This is the core fix for the original tool, where the flatpak "check" secretly
ran a full update, and parallel mode fought over the pacman lock.
"""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    """Outcome of a read-only availability check."""

    name: str
    display: str
    available: bool = False
    count: int = 0
    packages: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ApplyResult:
    """Outcome of actually applying updates."""

    name: str
    display: str
    success: bool = False
    changed: bool = False
    packages: list[str] = field(default_factory=list)
    error: str | None = None


def which(program: str) -> bool:
    """True if *program* is on PATH."""
    return shutil.which(program) is not None


def capture(cmd: list[str], *, timeout: int | None = 120) -> subprocess.CompletedProcess:
    """Run *cmd* capturing output. Never raises on non-zero exit."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def passthrough(cmd: list[str], *, cwd: str | None = None) -> int:
    """Run *cmd* with the real terminal attached; return its exit code.

    Used for the interactive update commands so pacman/yay prompts, colours and
    progress bars behave exactly as they would when run by hand.
    """
    return subprocess.run(cmd, cwd=cwd, check=False).returncode


class UpdateSource(ABC):
    """Interface implemented by every update source."""

    name: str
    display: str

    @abstractmethod
    def supported(self) -> bool:
        """Whether the required tooling is present on this system."""

    @abstractmethod
    def check(self) -> CheckResult:
        """Read-only check for available updates."""

    @abstractmethod
    def apply(self, *, noconfirm: bool, excluded: list[str]) -> ApplyResult:
        """Apply available updates. Assumes :meth:`check` reported some."""

    def unavailable_reason(self) -> str:
        """Why :meth:`supported` said no -- shown when this source was asked for."""
        return "required tooling is not installed"

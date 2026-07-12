"""Pacman (official repositories) update source."""

from __future__ import annotations

import logging

from .base import ApplyResult, CheckResult, UpdateSource, capture, passthrough, which

logger = logging.getLogger(__name__)


class PacmanSource(UpdateSource):
    name = "pacman"
    display = "Pacman"

    def supported(self) -> bool:
        return which("pacman")

    def check(self) -> CheckResult:
        if not which("checkupdates"):
            return CheckResult(
                self.name,
                self.display,
                error="checkupdates missing (install pacman-contrib)",
            )

        # checkupdates exit codes: 0 = updates, 2 = none, anything else = failure.
        proc = capture(["checkupdates"], timeout=120)
        if proc.returncode == 2:
            return CheckResult(self.name, self.display, available=False)
        if proc.returncode not in (0, 2):
            return CheckResult(
                self.name,
                self.display,
                error=(proc.stderr or "checkupdates failed").strip().splitlines()[-1]
                if proc.stderr.strip()
                else "checkupdates failed (is the network up?)",
            )

        packages = [
            line.split()[0]
            for line in proc.stdout.splitlines()
            if line.strip()
        ]
        return CheckResult(
            self.name,
            self.display,
            available=bool(packages),
            count=len(packages),
            packages=packages,
        )

    def apply(self, *, noconfirm: bool, excluded: list[str]) -> ApplyResult:
        before = self.check()
        cmd = ["sudo", "pacman", "-Syu"]
        for pkg in excluded:
            cmd += ["--ignore", pkg]
        if noconfirm:
            cmd.append("--noconfirm")

        logger.info("Running: %s", " ".join(cmd))
        code = passthrough(cmd)
        if code != 0:
            return ApplyResult(
                self.name, self.display, success=False, error=f"exit code {code}"
            )
        return ApplyResult(
            self.name,
            self.display,
            success=True,
            changed=before.available,
            packages=[p for p in before.packages if p not in excluded],
        )

    def orphans(self) -> list[str]:
        """Return the list of orphaned packages (``pacman -Qtdq``)."""
        proc = capture(["pacman", "-Qtdq"])
        if proc.returncode != 0:
            return []
        return [line for line in proc.stdout.splitlines() if line.strip()]

    def remove_orphans(self, orphans: list[str], *, noconfirm: bool) -> bool:
        cmd = ["sudo", "pacman", "-Rns", *orphans]
        if noconfirm:
            cmd.append("--noconfirm")
        return passthrough(cmd) == 0

"""Flatpak update source.

The original tool's "check" ran ``flatpak update`` (an *interactive* command),
which either hung waiting for hidden input or performed the update as a side
effect. Here the check is a genuine read-only ``remote-ls --updates``.
"""

from __future__ import annotations

import logging

from .base import ApplyResult, CheckResult, UpdateSource, capture, passthrough, which

logger = logging.getLogger(__name__)


class FlatpakSource(UpdateSource):
    name = "flatpak"
    display = "Flatpak"

    def supported(self) -> bool:
        return which("flatpak")

    def check(self) -> CheckResult:
        if not which("flatpak"):
            return CheckResult(self.name, self.display, error="flatpak not installed")

        proc = capture(
            ["flatpak", "remote-ls", "--updates", "--columns=ref"], timeout=120
        )
        if proc.returncode != 0:
            return CheckResult(
                self.name,
                self.display,
                error=(proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "check failed"),
            )

        refs = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        # ref looks like "app/org.foo.Bar/x86_64/stable" -> keep the id part.
        packages = [ref.split("/")[1] if "/" in ref else ref for ref in refs]
        return CheckResult(
            self.name,
            self.display,
            available=bool(packages),
            count=len(packages),
            packages=packages,
        )

    def apply(self, *, noconfirm: bool, excluded: list[str]) -> ApplyResult:
        before = self.check()
        cmd = ["flatpak", "update"]
        if noconfirm:
            cmd.append("-y")

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
            packages=before.packages,
        )

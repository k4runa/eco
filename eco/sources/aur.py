"""AUR update source (yay or paru).

Fixes two bugs from the original tool:

* It upgraded the AUR with ``-Syu`` which *also* performs a full repo upgrade,
  duplicating the work already done by the pacman source. We use ``-Sua`` so
  only AUR packages are touched.
* If both yay and paru were installed it ran both. We pick a single helper.
"""

from __future__ import annotations

import logging

from .base import ApplyResult, CheckResult, UpdateSource, capture, passthrough, which

logger = logging.getLogger(__name__)

PREFERRED = ("paru", "yay")


class AurSource(UpdateSource):
    name = "aur"

    def __init__(self) -> None:
        self.helper = next((h for h in PREFERRED if which(h)), None)
        self.display = f"AUR ({self.helper})" if self.helper else "AUR"

    def supported(self) -> bool:
        return self.helper is not None

    def check(self) -> CheckResult:
        if not self.helper:
            return CheckResult(self.name, self.display, error="no AUR helper (yay/paru)")

        # `<helper> -Qua` lists only AUR packages with pending updates.
        proc = capture([self.helper, "-Qua"], timeout=120)
        packages = [
            line.split()[0] for line in proc.stdout.splitlines() if line.strip()
        ]
        if packages:
            return CheckResult(
                self.name,
                self.display,
                available=True,
                count=len(packages),
                packages=packages,
            )
        if proc.returncode in (0, 1):
            return CheckResult(self.name, self.display, available=False)
        return CheckResult(
            self.name,
            self.display,
            error=(proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "check failed"),
        )

    def apply(self, *, noconfirm: bool, excluded: list[str]) -> ApplyResult:
        if not self.helper:
            return ApplyResult(self.name, self.display, success=False, error="no helper")

        before = self.check()
        cmd = [self.helper, "-Sua"]
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

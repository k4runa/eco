"""Automatic-update scheduling.

Prefers **systemd user timers** (the idiomatic Arch mechanism, and one that
works without the ``cronie`` package, which the original tool silently required
via ``crontab``). Falls back to cron only if systemd user instance is absent.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

UNIT = "eco-update"

ONCALENDAR = {
    "daily": "*-*-* 02:00:00",
    "weekly": "Sun *-*-* 02:00:00",
}


def _eco_command() -> str:
    exe = shutil.which("eco")
    if exe:
        return f"{exe} --update --noconfirm"
    return f"{sys.executable} -m eco --update --noconfirm"


def _has_systemd_user() -> bool:
    if not shutil.which("systemctl"):
        return False
    result = subprocess.run(
        ["systemctl", "--user", "is-system-running"],
        capture_output=True,
        text=True,
        check=False,
    )
    # "running" or "degraded" both mean the user instance is usable.
    return result.returncode == 0 or "running" in result.stdout or "degraded" in result.stdout


class Scheduler:
    def __init__(self) -> None:
        self.unit_dir = Path.home() / ".config" / "systemd" / "user"

    # -- systemd path -----------------------------------------------------
    def _write_units(self, frequency: str) -> None:
        self.unit_dir.mkdir(parents=True, exist_ok=True)
        (self.unit_dir / f"{UNIT}.service").write_text(
            "[Unit]\n"
            "Description=eco automatic system update\n\n"
            "[Service]\n"
            "Type=oneshot\n"
            f"ExecStart={_eco_command()}\n"
        )
        (self.unit_dir / f"{UNIT}.timer").write_text(
            "[Unit]\n"
            f"Description=Run eco {frequency}\n\n"
            "[Timer]\n"
            f"OnCalendar={ONCALENDAR[frequency]}\n"
            "Persistent=true\n"
            "RandomizedDelaySec=300\n\n"
            "[Install]\n"
            "WantedBy=timers.target\n"
        )

    def _systemctl(self, *args: str) -> int:
        # Capture output so routine "unit does not exist" noise doesn't leak
        # into eco's clean UI; real failures are surfaced by the caller.
        return subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True,
            text=True,
            check=False,
        ).returncode

    def enable(self, frequency: str) -> tuple[bool, str]:
        if frequency not in ONCALENDAR:
            return False, "frequency must be 'daily' or 'weekly'"

        if _has_systemd_user():
            self._write_units(frequency)
            self._systemctl("daemon-reload")
            code = self._systemctl("enable", "--now", f"{UNIT}.timer")
            if code == 0:
                return True, f"systemd timer enabled ({frequency}, 02:00)"
            return False, "failed to enable systemd timer"

        return self._cron_enable(frequency)

    def disable(self) -> tuple[bool, str]:
        removed = False
        if _has_systemd_user():
            self._systemctl("disable", "--now", f"{UNIT}.timer")
            for name in (f"{UNIT}.timer", f"{UNIT}.service"):
                path = self.unit_dir / name
                if path.exists():
                    path.unlink()
                    removed = True
            self._systemctl("daemon-reload")
        cron_removed = self._cron_disable()
        if removed or cron_removed:
            return True, "scheduled updates removed"
        return False, "no scheduled updates found"

    def status(self) -> str:
        if _has_systemd_user():
            result = subprocess.run(
                ["systemctl", "--user", "list-timers", f"{UNIT}.timer", "--no-pager"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip() or "no eco timer scheduled"
        return "systemd user instance unavailable"

    # -- cron fallback ----------------------------------------------------
    def _cron_enable(self, frequency: str) -> tuple[bool, str]:
        if not shutil.which("crontab"):
            return False, "neither systemd user timers nor crontab are available"
        when = "0 2 * * *" if frequency == "daily" else "0 2 * * 0"
        entry = f"{when} {_eco_command()}  # {UNIT}\n"
        current = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, check=False
        )
        lines = [
            line
            for line in (current.stdout.splitlines() if current.returncode == 0 else [])
            if UNIT not in line
        ]
        lines.append(entry.rstrip())
        proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        proc.communicate("\n".join(lines) + "\n")
        return True, f"cron job scheduled ({frequency}, 02:00)"

    def _cron_disable(self) -> bool:
        if not shutil.which("crontab"):
            return False
        current = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, check=False
        )
        if current.returncode != 0 or UNIT not in current.stdout:
            return False
        lines = [line for line in current.stdout.splitlines() if UNIT not in line]
        proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        proc.communicate("\n".join(lines) + "\n")
        return True

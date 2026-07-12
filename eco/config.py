"""Configuration: filesystem paths and user-editable settings.

Paths follow the XDG Base Directory spec. ``UserConfig`` is persisted as JSON
and can be both read and written (the old tool could only ever read it).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from . import APP_NAME

logger = logging.getLogger(__name__)


def _xdg(env: str, default: Path) -> Path:
    import os

    value = os.environ.get(env)
    return Path(value) if value else default


class Paths:
    """Resolved on-disk locations for eco's state and configuration."""

    def __init__(self, app_name: str = APP_NAME) -> None:
        home = Path.home()
        self.config_dir = _xdg("XDG_CONFIG_HOME", home / ".config") / app_name
        self.state_dir = _xdg("XDG_STATE_HOME", home / ".local" / "state") / app_name

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def repos_file(self) -> Path:
        return self.config_dir / "repositories.json"

    @property
    def stats_file(self) -> Path:
        return self.config_dir / "statistics.json"

    @property
    def hooks_dir(self) -> Path:
        return self.config_dir / "hooks"

    @property
    def log_file(self) -> Path:
        return self.state_dir / f"{APP_NAME}.log"

    def ensure(self) -> None:
        """Create the directory tree lazily (only when actually needed)."""
        for directory in (self.config_dir, self.state_dir):
            directory.mkdir(parents=True, exist_ok=True)
        for sub in ("pre-update", "post-update"):
            (self.hooks_dir / sub).mkdir(parents=True, exist_ok=True)


#: every update source eco knows about, in the order they run
ALL_SOURCES = ("pacman", "aur", "flatpak", "git")


@dataclass
class UserConfig:
    """User-tunable behaviour. Deliberately small -- every field is honoured.

    Things intentionally *not* here: ``noconfirm`` and ``dry-run`` are
    per-invocation decisions and live only as CLI flags; desktop notifications
    are implied by ``notify-send`` being installed; a webhook is implied by
    ``webhook_url`` being set.
    """

    sources: list[str] = field(default_factory=lambda: list(ALL_SOURCES))
    excluded_packages: list[str] = field(default_factory=list)
    webhook_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserConfig":
        data = cls._migrate(dict(data))
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    @staticmethod
    def _migrate(data: dict[str, Any]) -> dict[str, Any]:
        """Translate the old ``enable_*`` layout into the new schema."""
        if "sources" not in data and any(k.startswith("enable_") for k in data):
            legacy = {
                "pacman": "enable_pacman",
                "aur": "enable_aur",
                "flatpak": "enable_flatpak",
                "git": "enable_git_repos",
            }
            data["sources"] = [
                name for name, key in legacy.items() if data.get(key, True)
            ]
        return data

    def set_field(self, key: str, raw: str) -> None:
        """Set a field from a raw string value (used by ``eco --set k=v``)."""
        known = {f.name: f for f in fields(self)}
        if key not in known:
            raise KeyError(key)
        current = getattr(self, key)
        if isinstance(current, bool):
            value: Any = raw.strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(current, list):
            value = [item.strip() for item in raw.split(",") if item.strip()]
        elif current is None or isinstance(current, str):
            value = raw if raw.lower() not in ("none", "null", "") else None
        else:
            value = raw
        setattr(self, key, value)


class ConfigManager:
    """Load and save :class:`UserConfig` as JSON."""

    def __init__(self, paths: Paths) -> None:
        self.paths = paths

    def load(self) -> UserConfig:
        path = self.paths.config_file
        if not path.exists():
            return UserConfig()
        try:
            with open(path, "r") as handle:
                return UserConfig.from_dict(json.load(handle))
        except (json.JSONDecodeError, OSError) as error:
            logger.error("Could not read config (%s); using defaults", error)
            return UserConfig()

    def save(self, config: UserConfig) -> None:
        self.paths.ensure()
        with open(self.paths.config_file, "w") as handle:
            json.dump(config.to_dict(), handle, indent=2)
        logger.info("Configuration saved to %s", self.paths.config_file)

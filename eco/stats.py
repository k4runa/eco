"""Update statistics.

Unlike the original (which recorded a component name but *never* any package
names, so the advertised "most updated packages" table was always empty), this
records the real package lists produced by the check phase.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from .config import Paths

logger = logging.getLogger(__name__)

_EMPTY: dict[str, Any] = {
    "total_runs": 0,
    "last_update": None,
    "history": [],
}


class Statistics:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths

    def _load(self) -> dict[str, Any]:
        if not self.paths.stats_file.exists():
            return json.loads(json.dumps(_EMPTY))
        try:
            with open(self.paths.stats_file) as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return json.loads(json.dumps(_EMPTY))
        for key, value in _EMPTY.items():
            data.setdefault(key, json.loads(json.dumps(value)))
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.paths.ensure()
        try:
            with open(self.paths.stats_file, "w") as handle:
                json.dump(data, handle, indent=2)
        except OSError as error:
            logger.error("Failed to save statistics: %s", error)

    def record(self, component: str, packages: list[str] | None = None) -> None:
        packages = packages or []
        data = self._load()
        data["total_runs"] += 1
        data["last_update"] = datetime.now().isoformat(timespec="seconds")
        data["history"].append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "component": component,
                "package_count": len(packages),
            }
        )
        data["history"] = data["history"][-100:]
        self._save(data)

    def snapshot(self) -> dict[str, Any]:
        return self._load()

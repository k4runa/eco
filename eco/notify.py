"""Notifications: desktop (notify-send) and webhooks (Discord/Slack)."""

from __future__ import annotations

import json
import logging
import subprocess
import urllib.error
import urllib.request

from .config import UserConfig
from .sources.base import which

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: UserConfig) -> None:
        self.config = config

    def send(self, title: str, message: str, urgency: str = "normal") -> None:
        # Desktop notifications are implied by notify-send being installed;
        # a webhook is implied by webhook_url being set.
        if which("notify-send"):
            self._desktop(title, message, urgency)
        if self.config.webhook_url:
            self._webhook(title, message)

    def _desktop(self, title: str, message: str, urgency: str) -> None:
        if not which("notify-send"):
            return
        try:
            subprocess.run(
                ["notify-send", "-a", "eco", "-u", urgency, title, message],
                check=False,
            )
        except OSError as error:
            logger.error("desktop notification failed: %s", error)

    def _webhook(self, title: str, message: str) -> None:
        url = self.config.webhook_url or ""
        # Slack and Discord use different JSON keys; pick the right one.
        if "slack.com" in url:
            payload = {"text": f"*{title}*\n{message}"}
        else:  # Discord (and Discord-compatible endpoints)
            payload = {"content": f"**{title}**\n{message}"}
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(request, timeout=10)
        except (urllib.error.URLError, OSError) as error:
            logger.error("webhook notification failed: %s", error)

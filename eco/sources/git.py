"""Tracked Git repositories update source.

Fixes the original's most serious bug: the actual ``git pull`` ran in eco's own
working directory (no ``cwd``) and success was reported unconditionally, so no
repository was ever really updated. Here every git call is pinned to the repo
directory and the reported result reflects what git actually did.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import Paths
from .base import ApplyResult, CheckResult, UpdateSource, which

logger = logging.getLogger(__name__)


@dataclass
class RepoStatus:
    path: Path
    exists: bool
    pending: int = 0
    error: str | None = None


class GitRepo:
    """A single git working copy."""

    def __init__(self, path: str) -> None:
        self.path = Path(path).expanduser().resolve()

    def validate(self) -> None:
        if not self.path.exists():
            raise ValueError(f"path does not exist: {self.path}")
        if not (self.path / ".git").exists():
            raise ValueError(f"not a git repository: {self.path}")

    def _git(self, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=self.path,  # <-- the fix: always run inside the repo
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def pending(self) -> RepoStatus:
        """Fetch and count commits the upstream is ahead by."""
        if not self.path.exists():
            return RepoStatus(self.path, exists=False)
        try:
            self.validate()
        except ValueError as error:
            return RepoStatus(self.path, exists=True, error=str(error))

        fetch = self._git(["fetch", "--quiet"])
        if fetch.returncode != 0:
            msg = fetch.stderr.strip().splitlines()[-1] if fetch.stderr.strip() else "fetch failed"
            return RepoStatus(self.path, exists=True, error=msg)

        rev = self._git(["rev-list", "--count", "HEAD..@{u}"])
        if rev.returncode != 0:
            return RepoStatus(self.path, exists=True, error="no upstream tracking branch")
        try:
            count = int(rev.stdout.strip())
        except ValueError:
            count = 0
        return RepoStatus(self.path, exists=True, pending=count)

    def pull(self) -> tuple[bool, str | None]:
        proc = self._git(["pull", "--ff-only"], timeout=120)
        if proc.returncode == 0:
            return True, None
        detail = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "pull failed"
        return False, detail


class RepositoryStore:
    """Persistence for the tracked-repository list."""

    def __init__(self, paths: Paths) -> None:
        self.file = paths.repos_file
        self.paths = paths

    def load(self) -> list[str]:
        if not self.file.exists():
            return []
        try:
            with open(self.file) as handle:
                return json.load(handle).get("repositories", [])
        except (json.JSONDecodeError, OSError) as error:
            logger.error("Could not read repositories file: %s", error)
            return []

    def save(self, repos: list[str]) -> None:
        self.paths.ensure()
        with open(self.file, "w") as handle:
            json.dump({"repositories": repos}, handle, indent=2)

    def add(self, path: str) -> tuple[bool, str]:
        repo = GitRepo(path)
        try:
            repo.validate()
        except ValueError as error:
            return False, str(error)
        normalized = str(repo.path)
        repos = self.load()
        if normalized in repos:
            return False, f"already tracked: {normalized}"
        repos.append(normalized)
        self.save(repos)
        return True, normalized

    def remove(self, path: str) -> tuple[bool, str]:
        normalized = str(Path(path).expanduser().resolve())
        repos = self.load()
        if normalized not in repos:
            return False, f"not tracked: {normalized}"
        repos.remove(normalized)
        self.save(repos)
        return True, normalized


class GitSource(UpdateSource):
    name = "git"
    display = "Git repos"

    def __init__(self, paths: Paths) -> None:
        self.store = RepositoryStore(paths)
        self._statuses: list[RepoStatus] = []

    def supported(self) -> bool:
        return which("git") and bool(self.store.load())

    def check(self) -> CheckResult:
        if not which("git"):
            return CheckResult(self.name, self.display, error="git not installed")
        repos = self.store.load()
        if not repos:
            return CheckResult(self.name, self.display)

        self._statuses = [GitRepo(path).pending() for path in repos]
        pending = [s for s in self._statuses if s.pending > 0]
        errors = [s for s in self._statuses if s.error or not s.exists]
        names = [s.path.name for s in pending]
        error_note = None
        if errors and not pending:
            error_note = f"{len(errors)} repo(s) unreachable/missing"
        return CheckResult(
            self.name,
            self.display,
            available=bool(pending),
            count=len(pending),
            packages=names,
            error=error_note,
        )

    def apply(self, *, noconfirm: bool, excluded: list[str]) -> ApplyResult:
        if not self._statuses:
            self.check()
        updated: list[str] = []
        failed: list[str] = []
        for status in self._statuses:
            if status.pending <= 0:
                continue
            success, _ = GitRepo(str(status.path)).pull()
            (updated if success else failed).append(status.path.name)
        return ApplyResult(
            self.name,
            self.display,
            success=not failed,
            changed=bool(updated),
            packages=updated,
            error=(f"failed: {', '.join(failed)}" if failed else None),
        )

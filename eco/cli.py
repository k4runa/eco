"""Command-line interface and entry point."""

from __future__ import annotations

import argparse
import logging
import sys

from rich.prompt import Confirm
from rich.table import Table

from . import APP_NAME, AUTHOR, __version__
from . import console as ui
from .config import ConfigManager, Paths, UserConfig
from .console import console
from .scheduler import Scheduler
from .sources.base import passthrough, which
from .sources.git import RepositoryStore
from .sources.pacman import PacmanSource
from .stats import Statistics
from .updater import run_update

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# read-only display commands
# --------------------------------------------------------------------------- #
def show_stats(paths: Paths) -> None:
    data = Statistics(paths).snapshot()
    ui.rule("Update statistics")
    console.print(f"[eco.accent]Total runs[/]: [eco.count]{data['total_runs']}[/]")
    if data["last_update"]:
        console.print(f"[eco.accent]Last update[/]: {data['last_update']}")

    if data["history"]:
        table = Table(title="Recent activity", box=None, title_style="eco.heading")
        table.add_column("When", style="eco.muted")
        table.add_column("Component", style="eco.accent")
        table.add_column("Items", justify="right")
        for entry in data["history"][-5:]:
            table.add_row(entry["timestamp"], entry["component"], str(entry["package_count"]))
        console.print(table)


def show_config(cfg: UserConfig) -> None:
    ui.rule("Configuration")
    table = Table(show_header=False, box=None)
    table.add_column(style="eco.accent", no_wrap=True)
    table.add_column()
    for key, value in cfg.to_dict().items():
        if isinstance(value, list):
            value = ", ".join(value) if value else "(none)"
        elif value is None:
            value = "(unset)"
        table.add_row(key, str(value))
    console.print(table)


def list_repos(store: RepositoryStore) -> None:
    repos = store.load()
    ui.rule("Tracked git repositories")
    if not repos:
        ui.muted("No repositories tracked yet.")
        ui.muted(f"Add one with: {APP_NAME} --add-repo /path/to/repo")
        return
    from pathlib import Path

    table = Table(box=None)
    table.add_column("", width=2)
    table.add_column("#", justify="right", style="eco.muted")
    table.add_column("Path", style="eco.accent")
    for i, repo in enumerate(repos, 1):
        mark = f"[eco.ok]{ui.OK}[/]" if Path(repo).exists() else f"[eco.err]{ui.ERR}[/]"
        table.add_row(mark, str(i), repo)
    console.print(table)
    ui.muted(f"Total: {len(repos)}")


# --------------------------------------------------------------------------- #
# maintenance commands
# --------------------------------------------------------------------------- #
def clear_cache(helper: str) -> int:
    helper = helper.lower()
    if helper == "pacman":
        if not which("paccache"):
            ui.err("paccache missing (install pacman-contrib)")
            return 1
        ui.info("Removing cached pacman packages...")
        return passthrough(["sudo", "paccache", "-rk1"])
    if helper == "flatpak":
        if not which("flatpak"):
            ui.err("flatpak is not installed")
            return 1
        ui.info("Removing unused flatpak runtimes...")
        return passthrough(["flatpak", "uninstall", "--unused", "-y"])
    ui.err(f"Unsupported helper '{helper}'. Use: pacman, flatpak")
    return 1


def clean_orphans(noconfirm: bool) -> None:
    source = PacmanSource()
    orphans = source.orphans()
    ui.rule("Orphaned packages")
    if not orphans:
        ui.ok("No orphaned packages found.")
        return
    console.print(f"[eco.warn]Found {len(orphans)} orphan(s):[/] {', '.join(orphans)}")
    if not noconfirm and not Confirm.ask("[eco.heading]Remove them?[/]", default=False):
        ui.warn("Cancelled.")
        return
    if source.remove_orphans(orphans, noconfirm=noconfirm):
        ui.ok("Orphaned packages removed.")
    else:
        ui.err("Failed to remove orphaned packages.")


# --------------------------------------------------------------------------- #
# argument parsing / dispatch
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Unified system update manager for Arch Linux.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"Examples:\n"
            f"  {APP_NAME} --update                 update everything\n"
            f"  {APP_NAME} --update --dry-run       preview only\n"
            f"  {APP_NAME} --add-repo ~/dotfiles    track a git repo\n"
            f"  {APP_NAME} --set sources=pacman,aur  choose what to update\n"
            f"  {APP_NAME} --schedule daily         auto-update at 02:00\n\n"
            f"v{__version__} by {AUTHOR}"
        ),
    )
    g = parser.add_argument_group("Updates")
    g.add_argument("--update", action="store_true", help="update pacman, AUR, flatpak and git repos")
    g.add_argument("--dry-run", action="store_true", help="show what would be updated, change nothing")
    g.add_argument("--noconfirm", action="store_true", help="skip confirmation prompts")

    g = parser.add_argument_group("Git repositories")
    g.add_argument("--add-repo", metavar="PATH", help="track a git repository")
    g.add_argument("--remove-repo", metavar="PATH", help="stop tracking a git repository")
    g.add_argument("--list-repos", action="store_true", help="list tracked repositories")

    g = parser.add_argument_group("Maintenance")
    g.add_argument("--clear-cache", metavar="HELPER", help="clear cache for: pacman, flatpak")
    g.add_argument("--clean-orphans", action="store_true", help="remove orphaned packages")

    g = parser.add_argument_group("Scheduling")
    g.add_argument("--schedule", metavar="FREQ", choices=["daily", "weekly"], help="daily or weekly auto-updates")
    g.add_argument("--unschedule", action="store_true", help="remove scheduled auto-updates")
    g.add_argument("--schedule-status", action="store_true", help="show the schedule timer")

    g = parser.add_argument_group("Information & configuration")
    g.add_argument("--stats", action="store_true", help="show update statistics")
    g.add_argument("--config", action="store_true", help="show current configuration")
    g.add_argument("--set", metavar="KEY=VALUE", action="append", help="set a config value (repeatable)")

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def setup_logging(paths: Paths) -> None:
    paths.ensure()
    logging.basicConfig(
        filename=str(paths.log_file),
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not which("pacman"):
        ui.err("eco targets Arch Linux and Arch-based distributions (pacman not found).")
        return 1

    paths = Paths()
    setup_logging(paths)
    config_manager = ConfigManager(paths)
    cfg = config_manager.load()
    noconfirm = bool(args.noconfirm)

    store = RepositoryStore(paths)

    try:
        if args.set:
            for pair in args.set:
                if "=" not in pair:
                    ui.err(f"Expected KEY=VALUE, got '{pair}'")
                    return 1
                key, value = pair.split("=", 1)
                try:
                    cfg.set_field(key.strip(), value)
                except KeyError:
                    ui.err(f"Unknown setting '{key.strip()}'")
                    return 1
            config_manager.save(cfg)
            ui.ok("Configuration updated.")
            show_config(cfg)
            return 0

        if args.update:
            ui.banner(__version__)
            run_update(paths, cfg, noconfirm=noconfirm, dry_run=args.dry_run)
        elif args.stats:
            show_stats(paths)
        elif args.config:
            show_config(cfg)
        elif args.add_repo:
            success, message = store.add(args.add_repo)
            (ui.ok if success else ui.warn)(f"{'Added' if success else 'Skipped'}: {message}")
        elif args.remove_repo:
            success, message = store.remove(args.remove_repo)
            (ui.ok if success else ui.warn)(f"{'Removed' if success else 'Skipped'}: {message}")
        elif args.list_repos:
            list_repos(store)
        elif args.clear_cache:
            return clear_cache(args.clear_cache)
        elif args.clean_orphans:
            clean_orphans(noconfirm)
        elif args.schedule:
            success, message = Scheduler().enable(args.schedule)
            (ui.ok if success else ui.err)(message)
        elif args.unschedule:
            success, message = Scheduler().disable()
            (ui.ok if success else ui.warn)(message)
        elif args.schedule_status:
            ui.rule("Schedule")
            console.print(Scheduler().status())
        else:
            ui.banner(__version__)
            parser.print_help()
    except KeyboardInterrupt:
        console.print()
        ui.warn("Interrupted.")
        return 130
    return 0

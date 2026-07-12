"""Update orchestration and the live status UI.

Flow:

1. **Check phase** -- every enabled source is checked *in parallel* (all checks
   are read-only) behind a live, animated status board.
2. **Summary** -- what will change is shown as a table. ``--dry-run`` stops here.
3. **Apply phase** -- sources are updated **sequentially**, with the underlying
   tool attached to the real terminal, so pacman/yay prompts and progress work
   normally. Sources sharing the pacman lock can never collide.
4. **Result** -- a summary panel plus an optional desktop/webhook notification.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from rich.live import Live
from rich.prompt import Confirm
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from . import console as ui
from .config import Paths, UserConfig
from .console import console
from .hooks import Hooks
from .notify import Notifier
from .sources import (
    AurSource,
    CheckResult,
    FlatpakSource,
    GitSource,
    PacmanSource,
    UpdateSource,
)
from .stats import Statistics

logger = logging.getLogger(__name__)


@dataclass
class _Row:
    source: UpdateSource
    result: CheckResult | None = None


def _enabled_sources(paths: Paths, cfg: UserConfig) -> list[UpdateSource]:
    everything: list[UpdateSource] = [
        PacmanSource(),
        AurSource(),
        FlatpakSource(),
        GitSource(paths),
    ]
    return [s for s in everything if s.name in cfg.sources and s.supported()]


def _status_cell(row: _Row) -> Text | Spinner:
    if row.result is None:
        return Spinner(ui.SPINNER, text=Text(" checking", style="eco.muted"))
    r = row.result
    if r.error:
        return Text(f"{ui.ERR} error", style="eco.err")
    if r.available:
        return Text(f"{ui.ARROW} {r.count} update(s)", style="eco.count")
    return Text(f"{ui.OK} up to date", style="eco.ok")


def _detail_cell(row: _Row) -> Text:
    if row.result is None:
        return Text("")
    r = row.result
    if r.error:
        return Text(r.error, style="eco.muted")
    if r.available and r.packages:
        preview = ", ".join(r.packages[:4])
        if len(r.packages) > 4:
            preview += f" +{len(r.packages) - 4} more"
        return Text(preview, style="eco.muted")
    return Text("")


def _board(rows: list[_Row]) -> Table:
    table = Table(show_header=True, header_style="eco.heading", expand=True, box=None, pad_edge=False)
    table.add_column("Source", style="eco.accent", no_wrap=True, width=16)
    table.add_column("Status", width=18)
    table.add_column("Details", ratio=1)
    for row in rows:
        table.add_row(row.source.display, _status_cell(row), _detail_cell(row))
    return table


def _run_checks(rows: list[_Row]) -> None:
    """Run every source's check in parallel behind an animated board."""
    with Live(_board(rows), console=console, refresh_per_second=12, transient=False) as live:
        with ThreadPoolExecutor(max_workers=max(1, len(rows))) as pool:
            futures = {pool.submit(row.source.check): row for row in rows}
            for future in as_completed(futures):
                row = futures[future]
                try:
                    row.result = future.result()
                except Exception as error:  # noqa: BLE001 - surface as a row error
                    logger.exception("check failed for %s", row.source.name)
                    row.result = CheckResult(row.source.name, row.source.display, error=str(error))
                live.update(_board(rows))
        live.update(_board(rows))


def run_update(
    paths: Paths, cfg: UserConfig, *, noconfirm: bool = False, dry_run: bool = False
) -> None:
    logger.info("Update run started (dry_run=%s)", dry_run)
    sources = _enabled_sources(paths, cfg)
    if not sources:
        ui.warn("No enabled update sources are available on this system.")
        return

    ui.rule("Checking for updates")
    rows = [_Row(source) for source in sources]
    _run_checks(rows)

    pending = [row for row in rows if row.result and row.result.available]
    errored = [row for row in rows if row.result and row.result.error]

    for row in errored:
        ui.warn(f"{row.source.display}: {row.result.error}")

    if not pending:
        console.print()
        ui.ok("Everything is up to date. Nothing to do.")
        return

    total = sum(row.result.count for row in pending)
    console.print()
    if cfg.excluded_packages:
        ui.muted(f"Excluded from updates: {', '.join(cfg.excluded_packages)}")

    if dry_run:
        ui.rule("Dry run")
        for row in pending:
            ui.info(f"Would update {row.source.display}: {row.result.count} item(s)")
        ui.muted("No changes were made.")
        return

    console.print()
    if not noconfirm:
        if not Confirm.ask(
            f"[eco.heading]Apply updates to {len(pending)} source(s) "
            f"({total} item(s))?[/]",
            default=True,
        ):
            ui.warn("Cancelled.")
            return

    stats = Statistics(paths)
    notifier = Notifier(cfg)
    started = time.monotonic()

    Hooks(paths).run("pre-update")

    applied: list[str] = []
    failures: list[str] = []
    for row in pending:
        source = row.source
        ui.rule(f"Updating {source.display}")
        try:
            result = source.apply(noconfirm=noconfirm, excluded=cfg.excluded_packages)
        except Exception as error:  # noqa: BLE001
            logger.exception("apply failed for %s", source.name)
            ui.err(f"{source.display}: {error}")
            failures.append(source.display)
            continue

        if result.success:
            ui.ok(f"{source.display} updated")
            if result.changed:
                applied.append(source.display)
                stats.record(source.name, result.packages)
        else:
            ui.err(f"{source.display}: {result.error or 'failed'}")
            failures.append(source.display)

    Hooks(paths).run("post-update")

    _summary(applied, failures, total, time.monotonic() - started)

    if applied and not failures:
        notifier.send("eco", f"Updated {len(applied)} source(s): {', '.join(applied)}")
    elif failures:
        notifier.send("eco", f"Update finished with errors: {', '.join(failures)}", "critical")


def _summary(applied: list[str], failures: list[str], total: int, elapsed: float) -> None:
    from rich.panel import Panel

    lines = Text()
    if applied:
        lines.append(f"{ui.OK} ", style="eco.ok")
        lines.append(f"Updated: {', '.join(applied)}\n", style="eco.ok")
    if failures:
        lines.append(f"{ui.ERR} ", style="eco.err")
        lines.append(f"Failed: {', '.join(failures)}\n", style="eco.err")
    if not applied and not failures:
        lines.append("Nothing changed.\n", style="eco.muted")
    lines.append(f"{total} item(s) considered in {elapsed:.1f}s", style="eco.muted")

    border = "eco.err" if failures else "eco.ok"
    console.print()
    console.print(Panel(lines, title="[eco.heading]Summary[/]", border_style=border, padding=(1, 3)))

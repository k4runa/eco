"""Shared visual language: theme, symbols, banner and small UI helpers.

Everything user-facing goes through here so the whole tool reads as one design
system. Colours are chosen to stay legible on both dark and light terminals and
degrade gracefully when the terminal has no truecolor / no unicode.
"""

from __future__ import annotations

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

# eco == ecosystem: a calm green/teal identity with amber + red accents.
THEME = Theme(
    {
        "eco.brand": "bold #4ec9b0",
        "eco.accent": "#4ec9b0",
        "eco.heading": "bold #7fd6c2",
        "eco.muted": "dim",
        "eco.ok": "bold #6ccf6c",
        "eco.warn": "bold #e2c08d",
        "eco.err": "bold #f14c4c",
        "eco.info": "#569cd6",
        "eco.count": "bold #dcdcaa",
    }
)

console = Console(theme=THEME, highlight=False)

# Symbols with an ASCII fallback for dumb terminals.
if console.options.encoding.lower().startswith("utf"):
    OK, ERR, WARN, DOT, ARROW, LEAF = "✓", "✗", "!", "•", "→", "🌱"
else:  # pragma: no cover - only on legacy terminals
    OK, ERR, WARN, DOT, ARROW, LEAF = "+", "x", "!", "*", "->", "*"

SPINNER = "dots"


def banner(version: str) -> None:
    """Render the header wordmark."""
    title = Text()
    title.append(f"{LEAF} ", style="eco.ok")
    title.append("eco", style="eco.brand")
    title.append(f"  v{version}", style="eco.muted")
    subtitle = Text("unified system update manager for Arch Linux", style="eco.muted")
    body = Align.center(Text.assemble(title, "\n", subtitle))
    console.print(Panel(body, border_style="eco.accent", padding=(1, 4)))


def rule(label: str) -> None:
    console.rule(f"[eco.heading]{label}[/]", style="eco.accent")


def ok(message: str) -> None:
    console.print(f"[eco.ok]{OK}[/] {message}")


def err(message: str) -> None:
    console.print(f"[eco.err]{ERR}[/] {message}")


def warn(message: str) -> None:
    console.print(f"[eco.warn]{WARN}[/] {message}")


def info(message: str) -> None:
    console.print(f"[eco.info]{DOT}[/] {message}")


def muted(message: str) -> None:
    console.print(f"[eco.muted]{message}[/]")

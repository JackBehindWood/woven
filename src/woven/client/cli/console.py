from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.theme import Theme

WOVEN_THEME = Theme(
    {
        "woven.accent": "bold cyan",
        "woven.dim": "dim",
        "woven.success": "bold green",
        "woven.error": "bold red",
        "woven.warning": "yellow",
    }
)


def make_console(**kwargs: Any) -> Console:
    """Build the styled `Console` shared across the woven CLI.

    Centralizing the theme here keeps color choices in one place — call
    sites use semantic style names (`woven.accent`, `woven.error`, ...)
    instead of scattering raw color names through render/app code.
    """
    return Console(theme=WOVEN_THEME, **kwargs)

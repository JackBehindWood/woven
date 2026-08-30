from __future__ import annotations

from collections.abc import Callable

import typer

_COMMANDS: list[tuple[str, Callable[..., None]]] = []
_GROUPS: list[tuple[str, typer.Typer]] = []


def register_command(
    name: str,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Mark a function, defined in its own module, as a top-level `woven` command.

    `app.command()` can't be used directly in a command's own module — that
    module is imported by `app.py`, so importing `app` back would be
    circular. Registering here and letting `app.py` wire the registry onto
    `app` once (at import time) avoids that without every new command file
    needing its own manual `app.command(name)(func)` line in `app.py`.
    """

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        _COMMANDS.append((name, func))
        return func

    return decorator


def register_group(name: str) -> Callable[[typer.Typer], typer.Typer]:
    """Mark a Typer sub-app, built in its own module, for mounting onto `app`.

    Same cross-module rationale as `register_command` — apply directly to
    the constructed `typer.Typer()` (a decorator is just `f = dec(f)`; a
    plain object has no `def`/`class` line for `@` syntax to attach to).
    """

    def decorator(group: typer.Typer) -> typer.Typer:
        _GROUPS.append((name, group))
        return group

    return decorator


def registered_commands() -> list[tuple[str, Callable[..., None]]]:
    return list(_COMMANDS)


def registered_groups() -> list[tuple[str, typer.Typer]]:
    return list(_GROUPS)


def clear() -> None:
    """Drop the registry's held references once `app.py` has wired them onto `app`.

    Only needed during CLI startup wiring — the Typer `app` object keeps its
    own references to each command/group after that, so this is purely
    releasing otherwise-dead memory, not something `app` depends on.
    """
    _COMMANDS.clear()
    _GROUPS.clear()

# CLI client architecture

This document is the durable, committed reference for Woven's CLI client — the first client to occupy the "Clients" box in `docs/architecture/agent-runtime.md`'s layering diagram. It complements `agent-runtime.md` (which documents the runtime itself) by recording the client/runtime boundary, event-rendering design, and packaging decisions behind `src/woven/client/cli/`.

Where this document says "current implementation," it describes code that exists today. Where it says "future," it describes direction only.

## Position in the architecture

```text
Clients
   ↓
Application/API
   ↓
Agent Runtime
```

The CLI is a same-process, same-Python consumer of the runtime — it imports `woven.runtime`, `woven.modes`, `woven.models`, and `woven.events` directly. There is no network/API boundary yet; that's the same relationship the existing test suite already has with the runtime, just from a different caller.

## Packaging isolation

- A new `cli` optional-dependency group (`typer`, `rich`) in `pyproject.toml`, kept separate from `dev`. The runtime package (`woven.events`/`models`/`modes`/`runtime`/`workflow`) has zero imports of `typer`/`rich` anywhere — only `src/woven/client/cli/*` imports them, so the runtime stays usable (and testable) without installing the CLI's UI stack.
- `[project.scripts] woven = "woven.client.cli.app:app"` — the first console-script entry point in this repo. Named `woven`, matching the project/package name, rather than an invented separate brand.
- `src/woven/client/` is the package home for client implementations generally, not just the CLI — a future client (e.g. an API server for VS Code to talk to) would live at `src/woven/client/<name>/` alongside `cli`, following the same "consume `AgentRuntime.run_turn` as-is" pattern documented below.

## Client/runtime boundary

`AgentRuntime.run_turn(run, mode_name, input_text, model) -> Turn` is consumed as-is, unmodified — the CLI adds no orchestration, routing, or workflow logic of its own. There is no `AgentClient`/`ClientSession` wrapper class.

**Why not a class:** `run_turn` already takes and returns plain data (`AgentRun`, strings, a `Model`, a `Turn`) — it's already the client-agnostic seam. Wrapping it in a class today would be a pass-through with no independent state or behavior, which `docs/architecture/decisions.md`'s reasoning for deferring a `Node` base class already argues against for exactly this reason: a class earns its cost once there's a second consumer or genuine shared state to manage, not before.

The one thing a client genuinely needs beyond the raw call — turning the two undocumented runtime failure modes into rendered, non-crashing output, and replaying a turn's recorded events — is a single function:

```python
def run_chat_turn(
    runtime: AgentRuntime,
    run: AgentRun,
    mode_name: str,
    input_text: str,
    model: Model,
    console: Console,
) -> Turn | None: ...
```

(`src/woven/client/cli/session.py`). This is the whole client boundary. A future non-CLI Python client could reuse the same pattern — construct one `AgentRuntime` + one `AgentRun`, call `run_turn` per turn, render `turn.events` — without needing this exact function.

### The event-injection gap

`run_turn`'s `emit` closure (`src/woven/runtime/core.py`) is defined **inside** the method and closes only over its local `turn`/`run` — there is no parameter for a caller to inject an external `EventSink`. A client cannot observe events *live*; it can only call `run_turn` and then replay the events recorded on the returned `Turn` (success) or on `run.events` (failure — `ModelError` is re-raised before a `Turn` is ever returned, so `run_chat_turn` reads `run.events[-1]` instead).

Because every current runtime operation is synchronous and returns in microseconds, this post-hoc replay is visually indistinguishable from live streaming today. This is a real runtime seam, not a CLI shortcoming — documented here rather than worked around with new runtime code, which would be out of scope for a CLI-only slice. If a future node type introduces genuinely long-running work, `run_turn` would need an optional external `EventSink` parameter so a live client could render mid-turn progress; nothing requires that yet.

## Event → rendering map

`src/woven/client/cli/render.py` holds a dispatch table keyed by event type, so a future event type (e.g. `ToolCallStarted`) is renderable via a plain fallback line without any change to the dispatch mechanism itself.

| Event | Default visibility | Rendered as |
|---|---|---|
| `RunStarted` | suppressed | fires per `run_turn` call, not once per session (see `agent-runtime.md`'s "Known simplification") — showing it every REPL message would look broken |
| `TurnStarted` | suppressed | same reason |
| `ModelStarted` | shown | dim `◌ Calling model…` activity line |
| `ModelCompleted` | shown | dim `✓ Model responded` activity line |
| `TurnCompleted` | shown | green-bordered panel, body rendered via Rich `Markdown` (gives Markdown formatting and syntax-highlighted fenced code blocks for free) |
| `RunCompleted` | suppressed | same reason as `RunStarted` |
| `RunFailed` | shown | red-bordered error panel |
| unknown/future | shown | plain dim `· <TypeName>` fallback — never crashes, never silently vanishes |

A dim `console.rule()` is printed between turns in the REPL loop for visual separation, independent of the event dispatch itself.

## Startup chrome

`_run_chat()` (`src/woven/client/cli/app.py`) runs a fixed sequence before entering the REPL loop, independent of event rendering: clear the screen (`console.clear()`) → set the terminal window title to "Woven" (`console.set_window_title`) → print a centered wordmark (`render_banner`) → print the header panel (`render_header`) → print a one-line exit-instructions hint (`render_hint`). `render_banner` and `render_hint` live in `render.py` alongside `render_header`, following the same plain-function-plus-theme-markup shape. None of this touches the event dispatch table or `run_chat_turn`.

## REPL commands

Beyond the bare exit words (`exit`/`quit`/`:q`), any REPL input starting with `/` is looked up in `app.py`'s `_COMMANDS` table — `dict[str, tuple[str, Callable[[Console, str], None]]]` mapping a command name to its `/help` description and its handler. Adding a new command is one dict entry; no change to the REPL loop itself is needed. Today's commands:

| Command | Effect |
|---|---|
| `/help` | Renders a panel listing every registered command plus the exit words, via `render_help()` (`render.py`) |
| `/clear` | Clears the screen and redraws the startup chrome (`render_banner` → `render_header` → `render_hint`) so context isn't just wiped |

An unrecognized `/foo` renders an error via the existing `render_error()` and the REPL continues — same "never crashes the session" posture as `run_chat_turn`'s error handling below. `render_hint()`'s text points at `/help` so the command set is discoverable without reading docs.

## Error handling

- **`ModelError`** — caught in `run_chat_turn`, rendered from `run.events[-1]` (the `RunFailed` event recorded before the exception was re-raised), `run_chat_turn` returns `None`, and the REPL continues — one bad turn doesn't kill the session.
- **Unknown `mode_name`** — surfaces as a raw `KeyError` from `BUILTIN_MODES[mode_name]` (`agent-runtime.md`'s documented "Errors" gap: no `RunFailed` is emitted for this path). Caught client-side and rendered as `"Unknown mode: ..."`. The `chat` command always passes the literal `"chat"`, so this path is exercised only by tests today — it exists so `mode_name` can stay a real parameter rather than a hardcoded string, in case a `--mode` flag is added once a second mode exists.

## The demo-model disclosure

No real `Model` implementation exists yet — CLAUDE.md's constraints explicitly forbid adding a model provider in this slice. `woven chat` runs against `FakeModel` exclusively, with `--response`/`-r` controlling its one fixed reply. The startup header states this directly (`demo model: FakeModel — every message gets this same fixed reply: "..."`) so the CLI never implies it's a real assistant.

## Current implementation vs. future work

| Concept | Status |
|---|---|
| `woven chat` command | Implemented |
| `run_chat_turn` client boundary | Implemented |
| Event → Rich rendering | Implemented (7 known event types + fallback) |
| `--response`/`-r` flag | Implemented |
| Clean exit (`exit`/`quit`/`:q`, Ctrl+C, Ctrl+D) | Implemented |
| Window title (`set_window_title`) | Implemented |
| Startup wordmark/banner | Implemented |
| Screen clear on launch | Implemented |
| Hint footer (exit instructions) | Implemented |
| REPL commands (`/help`, `/clear`) | Implemented — extensible dispatch table, one entry per command |
| `--mode` flag | Not implemented — `BUILTIN_MODES` has exactly one entry today |
| `--verbose` flag (reveal `RunStarted`/`TurnStarted`/`RunCompleted`) | Not implemented — no current demand |
| Live/streaming event rendering | Not implemented — blocked on the `run_turn` `EventSink`-injection gap above |
| Session persistence across CLI invocations | Not implemented — matches the runtime being fully in-memory |
| `project`/`model`/`config` commands | Not implemented — no runtime capability backs any of them yet |
| `AgentClient`/`ClientSession` class | Not implemented — see "Why not a class" above |
| A real model provider | Not implemented — forbidden by CLAUDE.md's constraints right now |

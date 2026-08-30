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
    *,
    tool: Tool | None = None,
    context_source: Context | None = None,
    context_request: ContextRequest | None = None,
    approval: ApprovalPolicy | None = None,
) -> Turn | None: ...
```

The four keyword-only params are `None` by default and simply forwarded into `AgentRuntime.run_turn(...)` — `chat` mode passes none of them (unchanged behavior), while `plan`/`code` pass the subset each mode's workflow actually consumes (see "Per-mode wiring" below). `run_chat_turn`'s `except` clause was broadened from `ModelError` alone to `(ModelError, ToolError, ContextError, ApprovalDenied)` — the same exception set `AgentRuntime.run_turn` itself can raise — using the same "render `run.events[-1]`, return `None`" pattern for every one of them.

(`src/woven/client/cli/session.py`). This is the whole client boundary. `run_chat_turn` itself is CLI-specific glue, not a reusable core: it takes a Rich `Console` and calls `render_event`/`render_error` directly from inside its `try`/`except` branches, so a non-Rich caller can't use this function as-is. A future non-CLI Python client could still reuse the *pattern* it demonstrates — construct one `AgentRuntime` + one `AgentRun`, call `run_turn` per turn, render `turn.events` in whatever way fits that client — without needing this exact function.

**Considered and deferred:** splitting `src/woven/client/` so a Rich-free "core" (call `run_turn`, catch its two failure modes, hand back events/errors for the caller to render) lives directly under `src/woven/client/`, separate from the Rich/Typer-specific presentation code in `cli/`. Rejected for now, for the same reason as "Why not a class" above: there is no second client today (Additional clients work isn't scheduled), so the split has no consumer to validate its shape against and would be speculative. Revisit when that work actually starts.

### The event-injection gap

`run_turn`'s `emit` closure (`src/woven/runtime/core.py`) is defined **inside** the method and closes only over its local `turn`/`run` — there is no parameter for a caller to inject an external `EventSink`. A client cannot observe events *live*; it can only call `run_turn` and then replay the events recorded on the returned `Turn` (success) or on `run.events` (failure — `ModelError` is re-raised before a `Turn` is ever returned, so `run_chat_turn` reads `run.events[-1]` instead).

Because every current runtime operation is synchronous and returns in microseconds, this post-hoc replay is visually indistinguishable from live streaming today. This is a real runtime seam, not a CLI shortcoming — documented here rather than worked around with new runtime code, which would be out of scope for a CLI-only slice. If a future node type introduces genuinely long-running work, `run_turn` would need an optional external `EventSink` parameter so a live client could render mid-turn progress; nothing requires that yet.

## Event → rendering map

`src/woven/client/cli/render.py` holds a dispatch table keyed by event type, so a future event type (e.g. `ToolCallStarted`) is renderable via a plain fallback line without any change to the dispatch mechanism itself.

| Event | Default visibility | Rendered as |
|---|---|---|
| `RunStarted` | suppressed | fires per `run_turn` call, not once per session (see `agent-runtime.md`'s "Known simplification") — showing it every REPL message would look broken |
| `TurnStarted` | suppressed | same reason |
| `ModelStarted` | suppressed | the model-call spinner (below) now covers this moment |
| `ModelCompleted` | suppressed | same reason |
| `ToolCallStarted` | shown | dim one-line activity line, truncated `request.input_text` |
| `ToolCallCompleted` | shown | dim one-line activity line, truncated `result.output_text` |
| `ContextRetrieved` | shown | dim-bordered panel listing every retrieved file path, or "no files matched" if the snapshot is empty |
| `ApprovalRequested` | suppressed | the interactive policy's own `Confirm.ask` prompt (or the `auto`-tier's silent pass) already covers this moment — a third UI surface here would be redundant |
| `ApprovalDecided` | shown | dim "approved" line, or a warning line with the denial reason |
| `TurnCompleted` | shown | green-bordered panel, body rendered via Rich `Markdown` (gives Markdown formatting and syntax-highlighted fenced code blocks for free) |
| `RunCompleted` | suppressed | same reason as `RunStarted` |
| `RunFailed` | shown | red-bordered error panel |
| unknown/future | shown | plain dim `· <TypeName>` fallback — never crashes, never silently vanishes |

`render_status_panel(console, title, lines)` is a small additional helper (not part of the event dispatch table) used by the `/mode`, `/permission`, and `/context` command handlers to render their status/confirmation output in the same accent-bordered panel style as the rest of the CLI's chrome.

A dim `console.rule()` is printed between turns in the REPL loop for visual separation, independent of the event dispatch itself.

### Model-call spinner

`run_chat_turn` (`session.py`) wraps the `runtime.run_turn(...)` call itself in `console.status("Calling model…", spinner="dots")` — not the event dispatch table. This replaces the old static `ModelStarted`/`ModelCompleted` indicator lines (now suppressed, like `RunStarted`) with a real spinner that spans the actual call.

This does **not** close the event-injection gap above: `run_turn` is still called synchronously and its events still only exist for post-hoc replay after it returns — the spinner just wraps that one (currently near-instant) call, it isn't driven by live `ModelStarted`/`ModelCompleted` signals. It will show real, visible duration once a real model provider exists; today it's a cosmetic improvement over the two-line indicator.

## Startup chrome

`_run_chat()` (`src/woven/client/cli/app.py`) runs a fixed sequence before entering the REPL loop, independent of event rendering: clear the screen (`console.clear()`) → set the terminal window title to "Woven" (`console.set_window_title`) → print a centered wordmark (`render_banner`) → print the header panel (`render_header`) → print a one-line exit-instructions hint (`render_hint`). `render_banner` and `render_hint` live in `render.py` alongside `render_header`, following the same plain-function-plus-theme-markup shape. None of this touches the event dispatch table or `run_chat_turn`.

## REPL commands

Beyond the bare exit words (`exit`/`quit`/`:q`), any REPL input starting with `/` is looked up in `app.py`'s `_COMMANDS` table — `dict[str, tuple[str, Callable[[Console, SessionState, str], None]]]` mapping a command name to its `/help` description and its handler. Adding a new command is one dict entry; no change to the REPL loop itself is needed. Today's commands:

| Command | Effect |
|---|---|
| `/help` | Renders a panel listing every registered command plus the exit words, via `render_help()` (`render.py`) |
| `/clear` | Clears the screen and redraws the startup chrome (`render_banner` → `render_header` → `render_hint`) so context isn't just wiped |
| `/settings` | Read-only combined view of `/mode` + `/permission` + `/context`'s current-session status, plus the persisted default mode/permission tier and one `"<provider> api key: set\|not set"` line per known provider (`woven.settings.resolve_api_key`, currently just `gemini`) — no arguments, no mutation from here; use `/mode`/`/permission`/`/context` to change the current session, or `woven settings set` (below) to change the persisted default |
| `/mode [chat\|plan\|code]` | No argument shows the current mode and the full `BUILTIN_MODES` list; a valid argument switches `SessionState.mode_name`; an invalid one renders an error and leaves the mode unchanged |
| `/permission [auto\|guarded\|manual]` | No argument shows the current tier plus all three (`guarded` marked `(default)`); a valid argument switches `SessionState.permission_mode`; an invalid one renders an error |
| `/context [path <p>\|glob <g>\|query <q>\|clear\|show]` | No argument (or `show`) displays the current `ContextRequest`'s `paths`/`name_glob`/`text_query`; `path <p>` appends to `paths`; `glob`/`query` replace those fields; `clear` resets to an empty request; anything else renders a usage error |

`command_word, _, argument = stripped.partition(" ")` splits the REPL line into the command itself and everything after the first space, so `/mode code` and `/context glob *.py` route their argument text straight into the handler. Every command handler now has the shape `Callable[[Console, SessionState, str], None]` — `SessionState` (a small mutable dataclass: `response`, `mode_name`, `permission_mode`, `context_request`) replaces the bare `response: str` that command handlers used to receive, since there's now session state beyond the one fixed reply string. Both `--mode`/`--permission-mode` (session startup) and `/mode`/`/permission` (mid-session) write into the same `SessionState` fields, read fresh on every turn-loop iteration — there is exactly one source of truth for "what mode/tier is active right now."

An unrecognized `/foo` renders an error via the existing `render_error()` and the REPL continues — same "never crashes the session" posture as `run_chat_turn`'s error handling below. `render_hint()`'s text points at `/help` so the command set is discoverable without reading docs.

## Persisted settings

`--mode`/`--permission-mode` now default to `None` rather than a hardcoded string, so `_run_chat` (`app.py`) can distinguish "flag not passed" from "use the persisted default." Resolution order is CLI flag → persisted `Settings` value (`woven.settings.load_config()`) → the hardcoded `Settings` field default (`"chat"`/`"guarded"`). This applies to the bare `woven` invocation too (`main()` calls `_run_chat(DEFAULT_RESPONSE)` with no mode/permission-mode override), so it now starts in whatever mode/tier was last persisted via `woven settings set`, not always `chat`/`guarded`. A `ConfigError` from a corrupt config file is rendered and exits the process with code 1, the same pattern as an invalid `--mode`/`--permission-mode` value.

`woven settings show` / `woven settings set <field> [value]` (`src/woven/client/cli/settings_command.py`, mounted via `register_group("settings")`, see "Top-level commands and the registry" below) is the out-of-session mutation surface — see `docs/architecture/user-settings.md` for the full design of the underlying `src/woven/settings/` package. `show` prints the user id/name, every plain setting, and one `"<provider> api key: set|not set"` line per known provider (never the raw value); `set` validates `field` (`mode` against `BUILTIN_MODES`, `permission-mode` against `PERMISSION_MODES`, `model-provider` against `MODEL_PROVIDERS` — all three via `FIELDS`, `src/woven/setup/fields.py`) before writing plain fields, exiting 1 without touching the file on an invalid field/value. A secret field (currently `gemini-api-key`) takes `value` as optional — if omitted, it's collected via a hidden prompt instead of a plain CLI argument (so it never lands in shell history or `ps` output) and is written to a separate `secrets.json`, not `config.json`.

## Top-level commands and the registry

`woven` has four top-level Typer entries: `chat` (defined directly in `app.py`, via `@app.command()`), `settings` (a sub-`Typer`, `settings_command.py`), and `setup`/`doctor` (plain commands, `setup_command.py`/`doctor_command.py`) — see `docs/architecture/setup-and-diagnostics.md` for what the latter two actually do; this section covers only how they get wired onto `app`.

A command or sub-app defined in its own module can't decorate itself with `@app.command()`/`app.add_typer()` directly — that module is imported *by* `app.py`, so importing `app` back to decorate against would be circular. `src/woven/client/cli/registry.py` breaks that cycle with two decorator-factories:

```python
@register_command("setup")
def setup_command() -> None: ...

settings_app = register_group("settings")(typer.Typer(...))
```

Each just appends `(name, func_or_typer)` to a module-level list (`register_group` is applied directly to the constructed `typer.Typer()` — a decorator is just `f = dec(f)`, and a plain object has no `def`/`class` line for `@` syntax to attach to). `app.py` imports every command/group module purely for this side effect (`from woven.client.cli import setup_command as _setup_command_module  # noqa: F401`), then wires the registry onto `app` once at import time:

```python
for _group_name, _group in registered_groups():
    app.add_typer(_group, name=_group_name)
for _name, _func in registered_commands():
    app.command(_name)(_func)
clear()
```

`clear()` drops the registry's own references immediately after — `app` already holds what it needs, so nothing depends on the registry past CLI startup. `chat` stays a plain `@app.command()` in `app.py` itself since it has no cross-module cycle to solve; the registry exists for modules that do.

## Per-mode wiring

`_run_chat` constructs one `FilesystemContext(root=Path.cwd())`, one `MockTools()`, and all three approval policies once per session, then passes a subset of them into `run_chat_turn` on every turn based on `state.mode_name`:

| Mode | `tool` | `context_source` / `context_request` | `approval` |
|---|---|---|---|
| `chat` | — | — | — |
| `plan` | — | `FilesystemContext` / `state.context_request` | — |
| `code` | `MockTools()` | `FilesystemContext` / `state.context_request` | the policy for `state.permission_mode` |

This mirrors exactly what each mode's `Workflow` (`BUILTIN_MODES`, `src/woven/modes/core.py`) actually consumes — `chat` is `[model_node]`, `plan` is `[context_node, model_node]`, `code` is `[context_node, model_node, approval_node, tool_node]` — so `chat` mode's behavior is unchanged from before this slice.

## Error handling

- **`ModelError`** — caught in `run_chat_turn`, rendered from `run.events[-1]` (the `RunFailed` event recorded before the exception was re-raised), `run_chat_turn` returns `None`, and the REPL continues — one bad turn doesn't kill the session.
- **Unknown `mode_name`** — surfaces as a raw `KeyError` from `BUILTIN_MODES[mode_name]` (`agent-runtime.md`'s documented "Errors" gap: no `RunFailed` is emitted for this path). Caught client-side and rendered as `"Unknown mode: ..."`. The `chat` command always passes the literal `"chat"`, so this path is exercised only by tests today — it exists so `mode_name` can stay a real parameter rather than a hardcoded string, in case a `--mode` flag is added once a second mode exists.

## Permission modes

Three selectable tool-approval tiers, chosen via `--permission-mode` at startup or `/permission` mid-session:

| Tier | Behavior |
|---|---|
| `auto` | Today's original silent behavior: `AutoApprovalPolicy` alone — approves everything except its `DEFAULT_DENY_PATTERNS` matches, never prompts |
| `guarded` (**default**) | `InteractiveApprovalPolicy(always_prompt=False)` — silently approves unless the request matches `DEFAULT_REVIEW_PATTERNS`, in which case it prompts interactively; the underlying hard-deny floor still applies first |
| `manual` | `InteractiveApprovalPolicy(always_prompt=True)` — every request past the hard-deny floor is prompted interactively, unconditionally; never a silent approval |

`InteractiveApprovalPolicy` (`src/woven/client/cli/approval.py`) backs both interactive tiers with one mechanism: it composes an `AutoApprovalPolicy` as a hard-deny floor (a request matching `DEFAULT_DENY_PATTERNS` is denied outright, never prompted — same as `auto`), then either passes silently or calls `rich.prompt.Confirm.ask` depending on `always_prompt` and, for `guarded`, whether the request matches `DEFAULT_REVIEW_PATTERNS` — a deliberately broader/softer list (`"rm "`, `"sudo"`, `"git push --force"`, `"delete"`, `"drop "`, `"chmod"`, `"curl"`, `"wget"`, `"mv /"`) than the hard-deny list, since reusing the deny list as the review trigger would mean the review step never fires (anything on the deny list is already caught by the floor first). `confirm` is constructor-injectable, the same idiom `FakeModel`/`MockTools`/`MockApproval` already use, so tests can drive approval decisions deterministically without touching real stdin.

`InteractiveApprovalPolicy` lives under `woven.client.cli`, not `woven.permissions` or `woven.workflow`: it does real terminal I/O (a Rich `Console`, `Confirm.ask`), and `woven.permissions` must stay Rich/Typer-free so the runtime keeps working without the CLI's UI stack installed (same packaging-isolation reasoning as "Packaging isolation" above). It satisfies the `ApprovalPolicy` protocol structurally, so `AgentRuntime`/`workflow.approval_node` need no changes to accept it.

`guarded` becoming the default is a deliberate behavior change from this CLI's original fully-silent approval — `code` mode sessions now pause for confirmation on `DEFAULT_REVIEW_PATTERNS` matches unless `--permission-mode auto` is passed explicitly. The startup header does **not** disclose the active permission mode (unlike the demo-model/demo-tool lines below) — `/permission` with no argument is the way to check it, kept as an explicit non-build to avoid a header that's already three-to-four lines long growing a fifth.

## The demo-model and demo-tool disclosures, and `--model`

`woven chat` runs against `FakeModel` by default — no `--model` flag, no persisted `default_model_provider` — with `--response`/`-r` controlling its one fixed reply. The startup header states this directly (`demo model: FakeModel — every message gets this same fixed reply: "..."`) so the CLI never implies it's a real assistant when it isn't one.

A real provider is opt-in via `--model <provider>` (e.g. `--model gemini`), mirroring `--mode`/`--permission-mode`'s CLI-flag → persisted-default → hardcoded-default resolution through `resolve_runtime_config`. `_run_chat` looks the provider name up in `MODEL_PROVIDERS` (`src/woven/models/providers/__init__.py`); an unknown provider or a missing API key (`resolve_api_key`, `FileSecretStore`) renders a clear error and exits 1 before any SDK call is attempted — no stack trace either way. When a real provider is active, the header's model line switches from the `demo model: FakeModel` disclosure to `model: <provider> (<model_id>)` (`render_header`'s `model_description` param) — this also holds across `/clear` mid-session, via `SessionState.model_description`.

`code` mode additionally wires in `MockTools()` — also permanent test infrastructure, repurposed here as a demo tool — as the single `Tool` every tool call in that mode goes through; it always returns the same fixed `"ok"` result regardless of what it's asked to do. `render_header`'s `mode_name` param controls this: when `mode_name == "code"`, the header panel gains a fourth line (`demo tool: MockTools — tool calls always return a fixed result ("ok")`), mirroring the demo-model line's disclosure pattern exactly. `chat` and `plan` mode headers are unaffected since neither mode wires in a `tool`.

## Current implementation vs. future work

| Concept | Status |
|---|---|
| `woven chat` command | Implemented |
| `run_chat_turn` client boundary | Implemented |
| Event → Rich rendering | Implemented (12 known event types + fallback) |
| `--response`/`-r` flag | Implemented |
| Clean exit (`exit`/`quit`/`:q`, Ctrl+C, Ctrl+D) | Implemented |
| Window title (`set_window_title`) | Implemented |
| Startup wordmark/banner | Implemented |
| Screen clear on launch | Implemented |
| Hint footer (exit instructions) | Implemented |
| REPL commands (`/help`, `/clear`, `/settings`, `/mode`, `/permission`, `/context`) | Implemented — extensible dispatch table, one entry per command |
| Model-call status spinner | Implemented — wraps `runtime.run_turn` in `session.py`, not event-driven |
| `--mode` / `/mode` (chat, plan, code) | Implemented — `BUILTIN_MODES` now has three entries, all reachable from the CLI |
| `--model` (real provider selection, e.g. `gemini`) | Implemented — session-start flag only, no `/model` REPL command (see `docs/architecture/agent-runtime.md`'s GeminiProvider section) |
| Real (non-mock) context retrieval in the CLI | Implemented — `FilesystemContext(root=Path.cwd())`, driven by `/context` |
| Demo tool disclosure + tool-call rendering | Implemented — `MockTools()` in `code` mode |
| Interactive tool-call approval | Implemented — `InteractiveApprovalPolicy`, three selectable tiers (see "Permission modes" above) |
| `woven setup` / `woven doctor` commands, cross-module command registry | Implemented — see `docs/architecture/setup-and-diagnostics.md` and "Top-level commands and the registry" above |
| `--verbose` flag (reveal `RunStarted`/`TurnStarted`/`RunCompleted`) | Not implemented — no current demand |
| Live/streaming event rendering | Not implemented — blocked on the `run_turn` `EventSink`-injection gap above |
| Session persistence across CLI invocations | Not implemented — matches the runtime being fully in-memory |
| `project`/`model`/`config` commands | Not implemented — no runtime capability backs any of them yet |
| `AgentClient`/`ClientSession` class | Not implemented — see "Why not a class" above |
| Permission-mode disclosure in the startup header | Not implemented — `/permission` is the way to check it; an explicit non-build, see "Permission modes" above |
| Persistent `woven settings` subcommand + config/secrets files | Implemented — see `docs/architecture/user-settings.md`; plain fields in `~/.config/woven/config.json`, per-provider API keys in `~/.config/woven/secrets.json` |
| Bare `woven` invocation respecting persisted mode/permission defaults | Implemented — `main()` calls `_run_chat(DEFAULT_RESPONSE)` with no mode/permission override, so it resolves the persisted default like `woven chat` does; it still takes no flags of its own (an explicit non-build keeping the top-level shortcut minimal) |
| A real model provider | Not implemented — forbidden by CLAUDE.md's constraints right now |

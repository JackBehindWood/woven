# Decisions log

Short, dated notes on specific calls made while building the first Agent Runtime slice — not a full ADR process, just enough context that a future contributor doesn't have to reconstruct *why* from git history. See `agent-runtime.md` for the resulting design; this file is about the choices behind it.

## Data types: pydantic over stdlib dataclasses

All slice-1 data types (`ModelRequest`, `ModelResponse`, `WorkflowState`, the `Event` hierarchy, `Mode`, `AgentRun`, `Turn`) are pydantic `BaseModel`s. The initial design used stdlib `dataclasses` specifically to avoid introducing Woven's first runtime dependency for no concrete need. The project owner asked to switch to pydantic instead, for consistency; `pydantic>=2.0` was added to `[project.dependencies]`. `Model` stays a `typing.Protocol` (behavioral interface, not data) and `FakeModel` stays a plain class (stateful test double, not a data schema) — the switch applies to types the user identified as "data," not to interfaces or test doubles.

Practical notes from the switch:
- `WorkflowState.model: Model` needed `model_config = ConfigDict(arbitrary_types_allowed=True)` plus `@runtime_checkable` on the `Model` protocol, since pydantic validates non-pydantic field types via `isinstance`.
- Immutable "value object" models (`ModelRequest`, `ModelResponse`, `WorkflowState`, all `Event` types, `Mode`) use `model_config = ConfigDict(frozen=True)`. `AgentRun` and `Turn` are intentionally mutable (turns/events get appended, `output_text` gets set after construction).
- `WorkflowState` transitions use `state.model_copy(update={...})` in place of the `dataclasses.replace` the original design used.

## No generic `Node` abstraction yet

`model_node` is a plain function, not a class in a `Node` hierarchy. With exactly one node kind implemented (ToolNode/ContextNode/ApprovalNode are future work), a base class would have no shared behavior to justify it. Revisit when a second node kind is actually added — see `agent-runtime.md`'s Nodes section.

**2026-08-26 update (Slice 3):** `tool_node` was added as the second node kind, and still no `Node` class was extracted. The revisit trigger named above ("a second node kind is actually added") fired, but the actual condition for earning the abstraction — shared lifecycle/validation logic beyond the common `Callable[[WorkflowState, EventSink], WorkflowState]` step signature — still isn't met: `tool_node` needs nothing `model_node` doesn't already have (read state, call one collaborator, emit two events, return updated state). Extracting a `Node` protocol now would formalize a shape both functions already satisfy structurally, with no new behavior to attach to it. Revisit again if a third node kind needs something the plain-function shape can't express (e.g. per-node config validation, a `.name` for introspection, or a resource `Tool` needs `state.tool` set — currently unenforced, see `agent-runtime.md`'s Tools section).

## `turn_id` lives on `WorkflowState`

Events need to be stamped with the `turn_id` they belong to, and `model_node` is what constructs them. Rather than threading `turn_id` as a separate parameter through every workflow step, it's a field on `WorkflowState` itself. This is a pragmatic, non-speculative addition — it's read by every node that emits events, not a "might need it later" field.

## Graphiti vs. Graphify — do not confuse

`CLAUDE.md` had an uncommitted, accidental edit changing "Graphiti" to "Graphify" in its constraints list. These are unrelated:
- **Graphiti** (`getzep/graphiti`) — a temporal-knowledge-graph memory *library*. This is the correct term for Woven's future, optional Memory-subsystem backend, referenced throughout `docs/architecture.md` and `agent-runtime.md`. Not a dependency; not implemented.
- **Graphify** — the Claude Code *skill* (`~/.claude/skills/graphify`) used as a dev-assistant tool for exploring this repository's codebase. It has no Python SDK and is not part of Woven's runtime architecture in any way.

The `CLAUDE.md` edit was reverted back to "Graphiti." If Graphify is initialized for this repo (e.g. producing a `graphify-out/` knowledge graph of the codebase for dev-assistant use), that is unrelated tooling and should not be referenced from the architecture docs.

## Ruff automation: both a Claude Code hook and a git pre-commit hook

Two independent, non-overlapping mechanisms:
- **Claude Code hook** (`.claude/settings.json`, untracked/local): a `PostToolUse` hook on `Write|Edit` that runs `uv run ruff check --fix` and `uv run ruff format` on the specific Python file just written, automatically, inside Claude Code sessions only.
- **git pre-commit hook** (`.pre-commit-config.yaml`, tracked; `pre-commit` added to `[project.optional-dependencies].dev`): runs `uv run ruff check` and `uv run ruff format --check` on staged Python files before every commit, for every contributor who runs `uv run pre-commit install` once after cloning. Unlike the Claude Code hook, this one *blocks* the commit on failure rather than auto-fixing, since git hooks running on someone else's uncommitted work should not silently rewrite it.

## Pre-existing `pyproject.toml` bug fixed in passing

`[tool.ruff] target-version` was `["py312"]` (a list) instead of `"py312"` (a string) — invalid TOML for that key, which made `ruff` fail to even parse the config. This predates this slice; fixed here since it blocked the quality gates for this work.

## 2026-08-26 — Multi-agent-readiness considerations (Slice 3, design-only)

While planning Slice 3 (Tools), the current architecture (`AgentRuntime`, `AgentRun`/`Turn`, `Workflow`/`WorkflowState`, `Mode`, the Event stream, the CLI's client/runtime boundary) was rechecked against whether it would box in future multi-agent support. No multi-agent work is scheduled or implemented; this is analysis only, recorded so a future slice doesn't have to rediscover it.

**Orchestrator shape.** An "orchestrator" agent most likely looks like a `Workflow` step that itself invokes another `AgentRuntime.run_turn` (or the same runtime, recursively) and folds the sub-agent's result back into `WorkflowState` — structurally close to `tool_node` (a step delegating to an external unit of work and getting a result back), not a different `AgentRuntime` shape. It does not require a new node type today because nothing in Slice 3 needs it yet; it's a plausible future node, not a required one.

**AgentRun/Turn/Event scoping.** These do assume one linear agent's-eye view: `Event.turn_id` and `AgentRun.events`'s flat list have no field distinguishing "which agent." This is a pre-existing seam, not something Slice 3 introduces or worsens — it's the same shape as `agent-runtime.md`'s already-documented "Known simplification to revisit" (`RunStarted`/`RunCompleted` firing per-turn, not per-run). If/when multi-agent becomes concrete, the natural extension (by the same reasoning that put `turn_id` directly on `WorkflowState`) is an `agent_id` field added where it's actually read — not a redesign of `AgentRun`'s list structure.

**Tool-as-agent is a false equivalence, worth naming.** A `Tool.execute()` call is synchronous, stateless, and collapses to one `ToolResult`. Wrapping a sub-agent behind that same `Protocol` would work syntactically (an agent-as-tool adapter could technically return a `ToolResult`), but it would flatten away the sub-agent's own event stream and `Turn` structure into a single scalar — real information loss, not a clean generalization. If an agent-as-tool adapter is ever built, it should be named and documented as a lossy adapter over `Tool`'s shape, not treated as literal "an agent is just another Tool."

**CLI client/runtime boundary.** `run_chat_turn` assumes one `AgentRuntime` + one `AgentRun` per call, rendered synchronously after `run_turn` returns. Nothing prevents constructing multiple `AgentRun`s today, but a client driving several concurrent agents would want interleaved/live rendering across them — which runs into the same "event-injection gap" `cli-client.md` already documents (no live `EventSink` parameter on `run_turn`), just now motivated by concurrency instead of duration.

**Bottom line:** Slice 3's concrete `Tool`/`tool_node`/`MockTools` design has no tension with any of the above — none of these seams are made bigger or smaller by adding a second node kind. The two real gaps (single-agent-scoped `Event`/`AgentRun`, and the tool-as-agent equivalence) already exist independent of Tools; nothing here changes what Slice 3 built.

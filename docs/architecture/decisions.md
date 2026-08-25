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

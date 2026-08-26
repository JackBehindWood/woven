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
- **git pre-commit hook** (`.pre-commit-config.yaml`, tracked): runs `uv run ruff check` and `uv run ruff format --check` on staged Python files before every commit, for every contributor who runs `uv tool install pre-commit && pre-commit install` once after cloning. `pre-commit` itself is installed as an isolated `uv tool`, not a project dependency (see the 2026-08-26 entry below) — the hooks are `language: system`, so they only need `uv`/`ruff` on `PATH`, not `pre-commit` inside the project's `.venv`. Unlike the Claude Code hook, this one *blocks* the commit on failure rather than auto-fixing, since git hooks running on someone else's uncommitted work should not silently rewrite it.

## Pre-existing `pyproject.toml` bug fixed in passing

`[tool.ruff] target-version` was `["py312"]` (a list) instead of `"py312"` (a string) — invalid TOML for that key, which made `ruff` fail to even parse the config. This predates this slice; fixed here since it blocked the quality gates for this work.

## 2026-08-26 — Multi-agent-readiness considerations (Slice 3, design-only)

While planning Slice 3 (Tools), the current architecture (`AgentRuntime`, `AgentRun`/`Turn`, `Workflow`/`WorkflowState`, `Mode`, the Event stream, the CLI's client/runtime boundary) was rechecked against whether it would box in future multi-agent support. No multi-agent work is scheduled or implemented; this is analysis only, recorded so a future slice doesn't have to rediscover it.

**Orchestrator shape.** An "orchestrator" agent most likely looks like a `Workflow` step that itself invokes another `AgentRuntime.run_turn` (or the same runtime, recursively) and folds the sub-agent's result back into `WorkflowState` — structurally close to `tool_node` (a step delegating to an external unit of work and getting a result back), not a different `AgentRuntime` shape. It does not require a new node type today because nothing in Slice 3 needs it yet; it's a plausible future node, not a required one.

**AgentRun/Turn/Event scoping.** These do assume one linear agent's-eye view: `Event.turn_id` and `AgentRun.events`'s flat list have no field distinguishing "which agent." This is a pre-existing seam, not something Slice 3 introduces or worsens — it's the same shape as `agent-runtime.md`'s already-documented "Known simplification to revisit" (`RunStarted`/`RunCompleted` firing per-turn, not per-run). If/when multi-agent becomes concrete, the natural extension (by the same reasoning that put `turn_id` directly on `WorkflowState`) is an `agent_id` field added where it's actually read — not a redesign of `AgentRun`'s list structure.

**Tool-as-agent is a false equivalence, worth naming.** A `Tool.execute()` call is synchronous, stateless, and collapses to one `ToolResult`. Wrapping a sub-agent behind that same `Protocol` would work syntactically (an agent-as-tool adapter could technically return a `ToolResult`), but it would flatten away the sub-agent's own event stream and `Turn` structure into a single scalar — real information loss, not a clean generalization. If an agent-as-tool adapter is ever built, it should be named and documented as a lossy adapter over `Tool`'s shape, not treated as literal "an agent is just another Tool."

**CLI client/runtime boundary.** `run_chat_turn` assumes one `AgentRuntime` + one `AgentRun` per call, rendered synchronously after `run_turn` returns. Nothing prevents constructing multiple `AgentRun`s today, but a client driving several concurrent agents would want interleaved/live rendering across them — which runs into the same "event-injection gap" `cli-client.md` already documents (no live `EventSink` parameter on `run_turn`), just now motivated by concurrency instead of duration.

**Bottom line:** Slice 3's concrete `Tool`/`tool_node`/`MockTools` design has no tension with any of the above — none of these seams are made bigger or smaller by adding a second node kind. The two real gaps (single-agent-scoped `Event`/`AgentRun`, and the tool-as-agent equivalence) already exist independent of Tools; nothing here changes what Slice 3 built.

## 2026-08-26 — Multi-agent architecture design (Slice 4, design-only)

The analysis above was turned into a full design doc: `docs/architecture/multi-agent.md`. Two forks left open by the analysis above were resolved with the project owner before writing it:

- **Nesting model:** a sub-agent's events are flattened into the parent `AgentRun.events` (tagged with `agent_id`) *and* the sub-agent's `Turn`/`AgentRun` object is retained via a nested `WorkflowState.sub_runs` reference — both, not one or the other, to avoid the lossy-adapter problem named above while keeping today's flat-list CLI rendering unchanged.
- **Orchestrator shape:** a plain Workflow step (`agent_node`), same `Callable[[WorkflowState, EventSink], WorkflowState]` signature as `model_node`/`tool_node` — not a new Mode-level composition concept, and no new `Node` class.

`multi-agent.md` also concludes `AgentRuntime` needs no new method for concurrency (multiple `AgentRun` instances already suffice) and names the concrete mechanism `agent_node` would need beyond `tool_node`'s shape: re-emitting a child `Turn`'s events through the parent's `emit` closure, since the child's own `emit` closes over the child's `turn`/`run`, not the parent's. All new fields/events (`agent_id`, `parent_run_id`, `sub_runs`, `SubAgentStarted`/`Completed`) are deferred until an orchestrator is actually built — same non-speculative-addition reasoning as `turn_id` and the `Node` abstraction above. See `multi-agent.md` for the full design.

## 2026-08-26 — Editable-install/venv flakiness: actual fix, not just a workaround

The "known issue" documented in README (stray `.pth`-ordering bug, `ModuleNotFoundError: No module named 'woven'`) was suspected to stem from `virtualenv` — a real transitive dependency of `pre-commit` — being installed into the *same* `.venv` as `woven`'s own editable install, since `pre-commit` lived in `[project.optional-dependencies].dev`. Rather than only documenting a recovery command, the actual trigger for that coexistence is removed:

- `uv` upgraded 0.10.8 → 0.12.6 (Homebrew).
- `pre-commit` moved out of `dev` and installed instead via `uv tool install pre-commit` — an isolated tool venv, like `pipx`. It never shares `.venv` with `woven` again, so `virtualenv` can't land there either. The pre-commit hooks themselves are unaffected (`.pre-commit-config.yaml`'s hooks are `language: system`, calling `uv run ruff ...` directly — they never needed `pre-commit` itself inside the project's venv).

This is a structural fix (the two packages/tools no longer share an environment at all) rather than a version pin aimed at a specific guessed mechanism. `.python-version` + `python-preference = "managed"` (added previously) stay in place as additional belt-and-braces. `rm -rf .venv && uv sync --all-extras` remains the documented fallback in README if `ModuleNotFoundError` ever recurs regardless.

## 2026-08-26 — Context (Slice 5): `FilesystemContext` needs no `Fake` sibling

`FakeModel` and `MockTools` exist because the *real* `Model`/`Tool` implementations they stand in for are inherently nondeterministic (network calls, LLM sampling) — a permanent deterministic double is the only way to test `model_node`/`tool_node` without live infrastructure. `FilesystemContext`, the real `Context` implementation backing `context_node`, has no such problem: local filesystem reads with no embeddings are deterministic by construction. So `FilesystemContext` itself — constructed against a `tmp_path` — is directly usable in tests; adding a `FakeContext`/`MockContext` alongside it would duplicate `FilesystemContext`'s own logic with no new determinism to buy. This is a genuine asymmetry from the `Model`/`Tool` pattern, not an oversight — recorded here so it isn't "fixed" into symmetry later for its own sake.

`ContextRequest` reuses the same `purpose`/data-carrying shape as `ModelRequest`/`ToolRequest`, but with three retrieval-mode fields (`paths`, `name_glob`, `text_query`) instead of a single `input_text` — the concept doc's "explicit file selection, path/name search, text search" maps directly to these three, combinable in one request and deduped by relative path in `FilesystemContext.retrieve`.

## 2026-08-26 — Permissions (Slice 6): design choices

**`ApprovalPolicy.evaluate` reuses `ToolRequest`, no new `ApprovalRequest` type.** The Tools diagram in `agent-runtime.md` (`ToolRequest → Permission/Policy → Tool → ToolResult`) already gives `Permission/Policy` a `ToolRequest` as its input — inventing a parallel `ApprovalRequest` type would duplicate that shape with no new information. `ApprovalDecision` (`approved: bool`, `reason: str | None`) is the only new request/response-shaped type this slice needed.

**`MockApproval` has no `raise_error` option, unlike `FakeModel`/`MockTools`.** Those two simulate an I/O-style failure (a model/tool adapter erroring out) — a genuinely exceptional, unplanned outcome. A policy denying a request is not that: `ApprovalDecision(approved=False)` is a first-class, expected return value. `approval_node`, not the policy, is what turns a denial into an exception (`ApprovalDenied`). Giving `MockApproval` a `raise_error` flag would conflate "the policy says no" with "the policy is broken," which are different failure modes with different callers needing to handle them differently in the future.

**`AutoApprovalPolicy` — the "auto mode" approval policy.** Added at the project owner's request: most tool calls should be approved without friction; only requests matching a deterministic "suspected harmful" pattern should be denied. Implementation (`src/woven/permissions/auto.py`): case-insensitive substring match of `request.input_text` against `DEFAULT_DENY_PATTERNS` — a small, non-exhaustive, caller-overridable set (`rm -rf`, `sudo `, `drop table`/`drop database`, `chmod -r 777`, `mkfs.`, `curl`/`wget` piped to a shell, a fork-bomb literal). Deliberately just deterministic string matching — no LLM classification, no heuristic scoring, consistent with the project's standing "no embeddings/heavy infra" constraint.

This runtime has no interactive human-confirmation mechanism yet (no `HumanInputNode`, still listed as future work in `agent-runtime.md`'s Nodes section) — confirmed with the project owner that a matched request should be **denied outright** (fail-safe) rather than left in a third "pending" state. `ApprovalDecision` therefore stays binary (`approved`/`reason`), not a three-state enum; adding a "pending" state now would be speculative until an interactive gate actually exists to resolve it.

`run_turn` never constructs a default `ApprovalPolicy` (or any other resource) on the caller's behalf — same as it's never constructed a default `Model`/`Tool`. `AutoApprovalPolicy()` must be explicitly passed as `approval=...` by whichever caller wants "auto mode" behavior for a `code`-mode turn. This keeps resource injection uniform and explicit across `model`/`tool`/`context_source`/`approval`, and avoids `AgentRuntime` making a security-relevant policy choice implicitly.

**Named, accepted gap:** `approval_node` and `tool_node` each independently build a `ToolRequest` via the shared `_build_tool_request(state)` helper — they produce `==`-equal but not identical objects. In `code` mode's current step list (`[context_node, model_node, approval_node, tool_node]`) this is harmless: no step runs between `approval_node` and `tool_node`, so `state.output_text` cannot change between the two calls, meaning the approved request and the executed request are guaranteed equal in practice. If a future mode ever inserts a step between them, that guarantee breaks. Not fixed now — the only fix would be caching the built `ToolRequest` on `WorkflowState`, which is a speculative field with no current consumer. Recorded so it's a known, named tradeoff rather than a surprise if a future mode's step order changes.

## 2026-08-26 — Modes (Slice 7): `plan`/`code`, keyword-only `run_turn` params, and the broadened `except` clause

`BUILTIN_MODES` gained `"plan"` (`[context_node, model_node]`) and `"code"` (`[context_node, model_node, approval_node, tool_node]`), composing the node kinds built in Slices 3, 5, and 6. `plan` deliberately excludes `approval_node`/`tool_node` — it's for producing text, not taking action. `code`'s tool call is unconditionally gated by `approval_node` (confirmed with the project owner) — no variant of `code` mode skips approval.

For these modes to be runnable end-to-end (not just structurally present in the dict), `AgentRuntime.run_turn` gained four new parameters — `tool`, `context_source`, `context_request`, `approval` — all **keyword-only** (after a bare `*`) and all defaulting to `None`. Keyword-only was the mechanism chosen specifically to preserve the existing 4-positional-argument call shape (`run_turn(run, mode_name, input_text, model)`) exactly, so every existing call site (`chat` mode's tests, the CLI's `session.py`) keeps working unmodified — this is additive, not a breaking signature change.

The `except (ModelError, ...)` clause in `run_turn` was broadened to `except (ModelError, ToolError, ContextError, ApprovalDenied) as exc:` in this slice specifically, not in Slice 6 when `ApprovalDenied` was introduced. Reasoning: `ToolError`/`ContextError`/`ApprovalDenied` were all *unreachable* through any `Mode` until `plan`/`code` existed (no dict entry ever ran `tool_node`/`context_node`/`approval_node`), so narrowing the except clause earlier would have added a name with no reachable behavior to test. Slice 7 is the first point where the "failures are recorded, never swallowed" invariant (`agent-runtime.md`'s Errors section) needed to hold across all four exception types, so that's the slice that broadens the clause.

**Fresh addendum to "No generic `Node` abstraction yet":** with `context_node` and `approval_node` added (Slices 5–6), there are now four node kinds. The revisit trigger from the original entry ("a third node kind needs something the plain-function shape can't express") still hasn't fired — all four remain "read state, call one collaborator, emit event(s), return updated state." See the corresponding 2026-08-26 addendum in `agent-runtime.md`'s Nodes section for the one piece of shared logic that *was* extracted (`_build_tool_request`, a plain helper function, not a class).

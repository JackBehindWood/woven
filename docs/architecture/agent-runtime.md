# Agent Runtime architecture

This document is the durable, committed reference for Woven's Agent Runtime. It complements the high-level overview in `docs/architecture.md` by recording the concrete design of the first implemented slice — interfaces, module layout, and the reasoning behind each decision — so contributors don't have to reconstruct it from git history.

Where this document says "current implementation," it describes code that exists today under `src/woven/`. Where it says "future," it describes direction only — nothing described as future is implemented, and nothing here should be read as a promise of a specific timeline.

## Core principle

The Agent Runtime is the central execution system, conceptually:

```text
Clients
   ↓
Application/API
   ↓
Agent Runtime
   ↓
Mode
   ↓
Workflow
   ↓
Nodes
   ↓
Models / Tools / Context / Permissions
   ↓
Infrastructure
```

The runtime is usable independently of any client. No clients exist yet (Woven app, CLI, VS Code extension are all future work); `AgentRuntime` today is invoked directly from Python (see tests under `tests/`), which is itself a proof that no client is required to exercise the runtime.

## Modes

**Concept:** Modes are behavioral/profile configurations over the same runtime (Chat, Code, Plan, potentially Design later) — not separate agents. A new mode should be addable without modifying the runtime itself.

**Current implementation** (`src/woven/modes/core.py`):
- `Mode` is a frozen pydantic `BaseModel` with two fields: `name: str` and `workflow_factory: Callable[[], Workflow]`.
- `BUILTIN_MODES` is a plain module-level `dict[str, Mode]` with three entries:
  - `"chat"` → `[model_node]`
  - `"plan"` → `[context_node, model_node]` — gathers context and produces text; deliberately never executes a tool.
  - `"code"` → `[context_node, model_node, approval_node, tool_node]` — the full loop; every tool call is gated by `approval_node`, unconditionally (no ungated variant).
- `AgentRuntime` (see below) looks up `BUILTIN_MODES[mode_name]` and never branches on mode name itself — adding Code/Plan/Design later means adding dict entries and new `workflow_factory` functions, not touching the runtime. Design mode remains unimplemented.

An enum was rejected because it can't carry behavior (which workflow to build) without an external dict keyed by the enum — that's this design with extra steps. A plugin/registry loader was rejected because there is exactly one mode today; that machinery would have no second consumer to justify it. (That reasoning predates `plan`/`code`; three entries still don't justify loader machinery.)

## Workflows

**Concept:** A Workflow defines execution strategy — eventually model calls, tools, context retrieval, approvals, conditions, artifacts, multiple nodes. LangGraph may become a future orchestration *implementation* but is not the domain architecture and is not used here.

**Current implementation** (`src/woven/workflow/core.py`):
- `Workflow` holds a `name` and an ordered `steps: list[Callable[[WorkflowState, EventSink], WorkflowState]]`.
- `Workflow.run(state, emit)` executes the steps in a straight-line loop, threading state through each one.
- No branching, no DAG, no conditions, no retries, no parallelism. Extending it later means appending another callable — there is no generic executor to design against yet.

## Nodes

**Concept:** Conceptual node types include ModelNode, ToolNode, ContextNode, ApprovalNode, ConditionNode, ArtifactNode, with HumanInputNode/SubWorkflowNode as future possibilities.

**Current implementation:** there is no generic `Node` base class. `model_node`, `tool_node`, `context_node`, and `approval_node` (all `src/woven/workflow/core.py`) are plain functions matching the `Callable[[WorkflowState, EventSink], WorkflowState]` step signature — not a class hierarchy.

**Why:** a `Node` base class earns its cost once there are ≥2 heterogeneous node kinds needing shared lifecycle/validation logic. With exactly one node kind implemented, a class hierarchy would be ceremony with no shared behavior to justify it. If/when a second node kind (e.g. ToolNode) is added, extracting a shared `Node` protocol at that point is a cheap, well-motivated refactor — cheaper than maintaining an unused abstraction now.

**2026-08-26 update:** two more node kinds (`context_node`, `approval_node`) were added, bringing the total to four. The revisit trigger still hasn't fired: none of the four need anything beyond "read state, call one collaborator, emit one or two events, return updated state" — the same observation `decisions.md` recorded when `tool_node` was added as the second kind. `tool_node` and `approval_node` do share one real piece of logic (building a `ToolRequest` from `state.output_text`/`state.input_text`), but that was extracted as a private module-level function (`_build_tool_request`), not a `Node` class — a shared helper function is the cheaper, correctly-scoped fix for two functions needing one identical line, not a reason to introduce class hierarchy across all four.

## AgentRun and Turn

**Concept:**

```text
AgentRun
    ├── Turn 1
    ├── Turn 2
    ├── Turn 3
    └── ...
```

A Turn ≈ user input → selected Mode → Workflow execution → Agent output. Modes may change between Turns within the same AgentRun.

**Current implementation** (`src/woven/runtime/core.py`):
- `AgentRun` and `Turn` are pydantic `BaseModel`s, held entirely in memory — no persistence.
- `AgentRun.turns` is an append-only list; `AgentRuntime.run_turn(run, mode_name, input_text, model)` creates one `Turn`, executes it, and appends it — so a run can hold multiple turns, and each call can pass a different `mode_name`.
- IDs (`run_id`, `turn_id`) are plain strings (`uuid.uuid4().hex` where generated), used only for log/event correlation, not for lookup or storage.

Persistence is explicitly deferred (see "Deferred / future work" below).

## WorkflowState

**Concept:** WorkflowState must be typed, structured, and explicit — never `dict[str, Any]` as the state abstraction.

**Current implementation** (`src/woven/workflow/core.py`): a frozen pydantic `BaseModel` with exactly the fields the current workflow needs:

```python
class WorkflowState(BaseModel):
    turn_id: str
    input_text: str
    model: Model
    tool: Tool | None = None
    context_source: Context | None = None
    context_request: ContextRequest | None = None
    context: ContextSnapshot | None = None
    approval: ApprovalPolicy | None = None
    output_text: str | None = None
```

`turn_id` is included so `model_node` can stamp it onto the events it emits without threading a second parameter through every step. Being frozen, each step produces a new state via `state.model_copy(update={...})` rather than mutating in place. Every field was added only once a concrete step reads or writes it (`tool` for `tool_node`; `context_source`/`context_request`/`context` for `context_node`, with `context` also read by `model_node`; `approval` for `approval_node`) — no speculative fields.

`context_node`, `approval_node`, and `tool_node` each guard their required field being `None` before touching it, raising `WorkflowError("<field> is required for this step")` (`state.context_source`, `state.approval`, `state.tool` respectively) rather than letting a bare `AttributeError` leak out. This closes a gap that was harmless only while `modes/core.py`'s fixed per-mode step lists guaranteed reachability by construction — see the Errors section below and `decisions.md`.

## Model abstraction

**Concept:** Models are infrastructure-independent. FakeModel today; llama.cpp, a remote inference server, or a cloud model are future adapters. The runtime should not care where a model runs, and should not do sophisticated routing.

**Current implementation** (`src/woven/models/protocol.py`):

```python
@runtime_checkable
class Model(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...
```

A `Protocol` (not an ABC) so `FakeModel` — and any future real adapter — needs no shared base-class or `__init__` inheritance; structural typing is sufficient. `@runtime_checkable` lets `WorkflowState` (which holds `arbitrary_types_allowed=True` for this field) validate a `Model` value via `isinstance` without adopting a Woven-internal base class.

## ModelRequest

**Concept:** ModelNodes should operate on semantic requests, not giant raw prompt strings — eventually capturing purpose, requirements, context requirements, and expected output. Avoid building a prompt-engineering framework prematurely.

**Current implementation** (`src/woven/models/protocol.py`):

```python
class ModelRequest(BaseModel):
    purpose: str
    input_text: str
    context: ContextSnapshot | None = None


class ModelResponse(BaseModel):
    text: str
```

`purpose` is the one forward-looking field: it costs nothing today and is the natural seam for future prompt-selection/routing. `context` was added once `context_node` existed to populate it — `model_node` passes `state.context` straight through; `FakeModel` ignores it, same as it ignores `purpose`. Fields like `expected_output` or sampling parameters remain omitted because nothing reads them yet.

## FakeModel

**Current implementation** (`src/woven/models/fake.py`): a plain class, not a pydantic model (it's stateful/behavioral, not a data schema).

- Records every `ModelRequest` it receives, in order, in `received_requests: list[ModelRequest]`.
- Returns a fixed, caller-configured `response_text` — no randomness, no time/hash-based variation, so the same input always produces the same output.
- Can be constructed with `raise_error=True` to deterministically raise `ModelError` on `generate()`, exercising the failure path without a second class.
- Depends only on the shape of the `Model` protocol; `model_node` and `Workflow` never import `FakeModel` directly.

`FakeModel` is permanent test infrastructure per `docs/architecture.md` and `tests/README.md` — not a throwaway mock to be deleted once a real adapter exists.

## Provider protocol

**Concept:** a thin, structural counterpart to `Model` that answers "which provider/model is this?" without exposing `generate()`'s mechanics — so a future router/capabilities layer (`.claude/plans/model-router.md`, `.claude/plans/model-capabilities.md`) can inspect a `Model` value's provenance without every implementation inheriting a shared base class.

**Current implementation** (`src/woven/models/providers/protocol.py`):

```python
@runtime_checkable
class Provider(Protocol):
    provider_name: str
    model_id: str

    def check_connection(self) -> None: ...
```

Deliberately excludes the API key — this protocol exists purely for identification, never for exposing a secret as a public, structurally-matched attribute. `check_connection()` (raises `ModelError` on failure) was added by `.claude/plans/setup-and-diagnostics.md` as the first hook on this protocol — `woven doctor`'s provider-reachability check needed a cheap, generation-token-free way to validate a key/connection, and that's exactly the second concrete use case (beyond `generate()`'s own error handling) that justifies a real method here now. See `docs/architecture/setup-and-diagnostics.md` for the full design.

## GeminiProvider

**Current implementation** (`src/woven/models/providers/gemini.py`): the first real `Model` implementation, backed by the official `google-genai` SDK (`genai.Client`, not a hand-rolled HTTP client — the SDK absorbs Gemini API wire-protocol drift that a hand-rolled client would need to track manually).

- Implements `Model` (via `generate()`) and `Provider` (via `provider_name`/`model_id`/`check_connection()`) structurally — no inheritance from either.
- `generate()` concatenates `request.context`'s file contents (if any) with `request.input_text` into one plain string passed as the SDK's `contents` param; `request.purpose` stays unused, same as `FakeModel`.
- `client: genai.Client | None = None` is a constructor injection point — tests substitute a small fake double shaped like `genai.Client` (a `.models.generate_content(model=, contents=)` / `.models.get(model=)` pair of methods), never real network calls or `vcrpy` cassettes. See `tests/unit/test_gemini_model.py`.
- Maps `google.genai.errors.APIError` → `ModelError`, and an empty/`None` `response.text` → `ModelError`, so callers only ever see the one exception type the `Model` protocol already implies. Both `generate()` and `check_connection()` also catch `(httpx.ConnectError, httpx.TimeoutException)` → `ModelError("Gemini unreachable: network error")` — the `google-genai` SDK retries these internally but re-raises the raw `httpx` exception once retries are exhausted (`reraise=True`), so without this second `except` clause a genuine network outage would leak an unhandled `httpx` traceback instead of the clean `ModelError` every other failure path produces.
- `check_connection()` calls `self._client.models.get(model=self.model_id)` — a cheap metadata call, not `generate()` — so `woven doctor` can validate a key/connection without spending real generation tokens on every run. It differentiates failure causes for a more actionable message: an invalid key → "Gemini API key rejected" (real Gemini responses return this as HTTP 400/`INVALID_ARGUMENT` with an "API key not valid" message, not 401/403 as the HTTP status alone would suggest — 401/403 are kept as a defensive fallback), `429` → "rate limited or quota exceeded", `5xx` → "service unavailable, try again later", anything else → the same flat message `generate()` uses.
- `SETUP_HINT: ClassVar[str]` — a short human-readable string pointing at where to get a free Gemini API key, readable directly off the class (`GeminiProvider.SETUP_HINT`) without constructing an instance — `woven setup` prints it before prompting for a key, and `woven doctor` references it in its "no key configured" fix-hint.
- `DEFAULT_GEMINI_MODEL_ID` (`"gemini-3.7-flash"` as of 2026-08-28) is hardcoded, not a `Settings` field — Gemini's model-id strings have churned enough (confirmed via `ai.google.dev/gemini-api/docs/models`) that this is expected to need periodic updates, not a one-time choice.
- `src/woven/models/providers/__init__.py` exports a flat `MODEL_PROVIDERS: dict[str, type[Model]]` registry (`{"gemini": GeminiProvider}`) — the provider **class** itself, not a wrapping lambda, so `SETUP_HINT` is reachable pre-instantiation (`MODEL_PROVIDERS[name].SETUP_HINT`) for `woven setup`'s guided flow. Mirrors `BUILTIN_MODES`'s own precedent (`src/woven/modes/core.py`): a plain dict, not a plugin/loader system, until a second real provider exists to justify one.
- No streaming, no model-driven tool calls, no capabilities/metadata beyond `Provider`'s fields — `Model.generate(request) -> response` is unchanged. Each of these has its own forward-looking roadmap item instead of being built now or forgotten (see `.claude/plans/roadmap.md` items 6, 8, 9, 15).

Manual/live verification against the real Gemini API happens via `examples/sandbox_gemini.py` (a standalone script, not pytest-collected) — the automated suite never makes a network call, deliberately, so a stray env var or CI misconfiguration can't trigger a real, billed API call.

## Tools

**Concept:**

```text
ToolRequest
    ↓
Permission / Policy
    ↓
Tool
    ↓
ToolResult
```

MCP is a future adapter/integration boundary, not Woven's internal tool architecture. Permission/Policy is implemented — see the Permissions section below.

**Current implementation** (`src/woven/tools/protocol.py`, `src/woven/tools/mock.py`, `src/woven/workflow/core.py`):

- `Tool` is a `runtime_checkable` `Protocol` with one method, `execute(request: ToolRequest) -> ToolResult` — mirrors `Model`'s shape exactly, for the same reason: structural typing, no shared base class needed.
- `ToolRequest`/`ToolResult` are frozen pydantic `BaseModel`s with `purpose`/`input_text` and `output_text` fields respectively, mirroring `ModelRequest`/`ModelResponse`. Neither carries a tool name — the specific `Tool` instance to call is already selected by whoever holds the reference, same as `ModelRequest` carrying no model identifier.
- `tool_node` (`src/woven/workflow/core.py`) is a plain function alongside `model_node`, matching the same `Callable[[WorkflowState, EventSink], WorkflowState]` step signature. It emits `ToolCallStarted`/`ToolCallCompleted`, calls `state.tool.execute(...)`, and writes the result into `state.output_text`. It builds its `ToolRequest` via the shared `_build_tool_request(state)` helper, which reads `state.output_text` if a prior step already set it (falling back to `state.input_text`) — this is what lets `[model_node, tool_node]` chain a model's reply into a tool call.
- `WorkflowState.tool: Tool | None = None` — optional, so the existing `chat` workflow (which never sets a tool) is unaffected.
- `MockTools` (`src/woven/tools/mock.py`) is `FakeModel`'s permanent-test-infrastructure counterpart: records every `ToolRequest`, returns a fixed configured `output_text`, and can be constructed with `raise_error=True` to deterministically raise `ToolError`.

**Wired:** `tool_node` is part of `BUILTIN_MODES["code"]`'s workflow (`[context_node, model_node, approval_node, tool_node]`), always preceded by `approval_node` — a `code`-mode tool call is never ungated. `chat` still runs `[model_node]` only; `plan` never includes `tool_node`.

## Permissions

**Concept:** the `Permission / Policy` stage of the Tools diagram above — a gate between deciding to call a tool and actually calling it.

**Current implementation** (`src/woven/permissions/`):

- `ApprovalPolicy` is a `runtime_checkable` `Protocol` with one method, `evaluate(request: ToolRequest) -> ApprovalDecision` — reuses `ToolRequest` from `woven.tools` rather than inventing a parallel `ApprovalRequest` type, since the Tools diagram already gives `Permission/Policy` a `ToolRequest` as input.
- `ApprovalDecision` is a frozen pydantic `BaseModel`: `approved: bool`, `reason: str | None = None`. Binary by design — no third "pending" state, since this runtime has no interactive human-confirmation mechanism yet; a flagged request is denied outright (fail-safe), not left waiting.
- `approval_node` (`src/woven/workflow/core.py`) builds a `ToolRequest` via `_build_tool_request`, emits `ApprovalRequested`, calls `state.approval.evaluate(request)`, emits `ApprovalDecided`, and raises `ApprovalDenied` if the decision is not approved. It runs before `tool_node` in `code` mode's step list.
- `WorkflowState.approval: ApprovalPolicy | None = None` — optional, mirroring `tool`/`context_source`.
- `MockApproval` (`src/woven/permissions/mock.py`) is the permanent deterministic test double: constructed with a fixed `approve`/`reason`, records every `ToolRequest` it receives. Unlike `FakeModel`/`MockTools`, it has **no** `raise_error` option — denial is a first-class, non-exceptional return value (`ApprovalDecision(approved=False)`); `approval_node`, not the policy, is what turns a denial into an exception.
- `AutoApprovalPolicy` (`src/woven/permissions/auto.py`) is a real, usable "auto mode" policy, not a test double — deterministic, no LLM/embeddings. It case-insensitively substring-matches `request.input_text` against `DEFAULT_DENY_PATTERNS` (a small, non-exhaustive set: `rm -rf`, `sudo `, `drop table`, `drop database`, `chmod -r 777`, `mkfs.`, `curl`/`wget` piped to a shell, a fork-bomb literal). Any match → denied with a reason naming the matched pattern; no match → approved. `deny_patterns` is caller-overridable via the constructor.
- `run_turn` never constructs a default policy behind the caller's back — `AutoApprovalPolicy` (or `MockApproval`) must be explicitly passed as `approval=...`, the same explicit-resource-injection pattern used for `model`/`tool`/`context_source`.

**Known, accepted gap:** `approval_node` and `tool_node` each build their own `ToolRequest` via `_build_tool_request(state)` — the approved request and the executed request are `==`-equal but not the same object. Harmless today (no step runs between `approval_node` and `tool_node` in `code` mode, so `state.output_text` can't change between the two calls), but a future mode inserting a step between them could open an "approved something slightly different from what actually ran" gap. Not fixed now — would require a speculative `WorkflowState` field to cache the built request. Named here so it isn't rediscovered as a surprise.

## Context

**Concept:** answers "what information is relevant to this task?" via deterministic retrieval (explicit file selection, path/name search, text search) — no embeddings, vector databases, or knowledge graphs. Symbol info and recent-conversation retrieval remain future work, not implemented in this slice.

**Current implementation** (`src/woven/context/`):

- `Context` is a `runtime_checkable` `Protocol` with one method, `retrieve(request: ContextRequest) -> ContextSnapshot` — mirrors `Model`/`Tool`'s shape.
- `ContextRequest` is a frozen pydantic `BaseModel`: `purpose: str`, `paths: list[str] = []` (explicit file selection), `name_glob: str | None = None` (path/name search), `text_query: str | None = None` (substring text search). All three retrieval modes can be combined in one request; results are deduped by relative path.
- `ContextFile` (`path: str`, `content: str`) and `ContextSnapshot` (`files: list[ContextFile] = []`) are the frozen data types — deliberately just files, no `symbols`/`conversation_history` fields since nothing reads them yet.
- `FilesystemContext` (`src/woven/context/filesystem.py`) is the real, deterministic implementation, constructed with a `root: Path | str`. It has **no** `Fake`/`Mock` sibling: unlike `Model`/`Tool`, whose real implementations are inherently nondeterministic (network/LLM calls) — which is *why* `FakeModel`/`MockTools` exist — local filesystem reads with no embeddings are deterministic by construction, so `FilesystemContext` is directly usable in tests (with `tmp_path`). It raises `ContextError` for an explicit path that doesn't exist or that resolves outside `root`, and skips hidden directories (anything under a path component starting with `.`) during glob/text search.
- `context_node` (`src/woven/workflow/core.py`) calls `state.context_source.retrieve(...)`, emits a single `ContextRetrieved` event (no Started/Completed pair — retrieval is a cheap synchronous local call, unlike a `Model`/`Tool` invocation), and writes the result into `state.context`.
- `model_node` passes `context=state.context` into the `ModelRequest` it builds — this is the concrete `ContextSnapshot → ModelRequest` wiring the original design anticipated below.
- `WorkflowState.context_source: Context | None = None`, `context_request: ContextRequest | None = None`, `context: ContextSnapshot | None = None` — all optional, so `chat` (which sets none of them) is unaffected.

**Wired:** `context_node` is the first step in both `BUILTIN_MODES["plan"]` and `BUILTIN_MODES["code"]`.

### ContextSnapshot vs WorkflowState

This distinction, anticipated before either type existed, now holds concretely:

```text
WorkflowState  = what the workflow currently knows
ContextSnapshot = what a particular model invocation actually received
```

`state.context` is threaded into every subsequent `model_node` call's `ModelRequest.context` — they are not conflated: `WorkflowState` is the superset the workflow carries between steps, `ContextSnapshot` is the specific slice a given `ModelRequest` receives.

## Memory

**Concept (future):** answers "what should the system remember?" — distinct from retrieval's "what's relevant right now?" Project memory should eventually be isolated by project by default.

**Current implementation:** none. Memory is entirely out of scope for this slice.

### Graphiti

Graphiti (`getzep/graphiti`, a temporal-knowledge-graph library) is a **future, optional** Memory-subsystem backend. It is not a dependency of this repository, is not designed around in the current runtime, and must not be added until there is a concrete need. When eventually introduced, it should sit behind clean Woven memory/retrieval interfaces so the core runtime and its deterministic tests remain fully usable without it.

(Note: Graphiti is unrelated to "Graphify," the Claude Code skill used as a dev-assistant tool for exploring this repository. Graphify has no bearing on Woven's runtime architecture and is not referenced further in this document.)

## Events

**Concept:** An AgentRun produces an event stream — the architectural principle, not a specific taxonomy. Future events may include FileChangeProposed, TestStarted/Completed, RunCancelled, and more. No event bus/message broker.

**Current implementation** (`src/woven/events/core.py`): immutable frozen pydantic models, all inheriting a `turn_id: str` field from `Event`:

- `RunStarted(run_id)`
- `TurnStarted(mode_name)`
- `ModelStarted(request: ModelRequest)`
- `ModelCompleted(response: ModelResponse)`
- `ToolCallStarted(request: ToolRequest)`
- `ToolCallCompleted(result: ToolResult)`
- `ContextRetrieved(snapshot: ContextSnapshot)`
- `ApprovalRequested(request: ToolRequest)`
- `ApprovalDecided(decision: ApprovalDecision)`
- `TurnCompleted(output_text)`
- `RunCompleted(run_id)`
- `RunFailed(run_id, error)`

Events are collected via a plain callback (`emit: Callable[[Event], None]`) that `AgentRuntime.run_turn` closes over, appending each event to both `Turn.events` and `AgentRun.events`. This is the "callback/listener" option, not a broker — there is no publish/subscribe machinery, no async dispatch, and no external transport.

The event sequence for a successful turn depends on the mode's step list:

- `chat` (`[model_node]`): `RunStarted, TurnStarted, ModelStarted, ModelCompleted, TurnCompleted, RunCompleted`
- `plan` (`[context_node, model_node]`): `RunStarted, TurnStarted, ContextRetrieved, ModelStarted, ModelCompleted, TurnCompleted, RunCompleted`
- `code` (`[context_node, model_node, approval_node, tool_node]`): `RunStarted, TurnStarted, ContextRetrieved, ModelStarted, ModelCompleted, ApprovalRequested, ApprovalDecided, ToolCallStarted, ToolCallCompleted, TurnCompleted, RunCompleted`

**Known simplification to revisit:** `RunStarted`/`RunCompleted` currently fire around each individual `run_turn` call rather than around the lifetime of the whole `AgentRun`. This is fine today because nothing in the runtime needs run-level setup/teardown distinct from turn-level setup/teardown — but it's a designed seam to revisit once multi-turn runs need genuine run-scoped behavior (e.g. run-level context that persists across turns).

## Errors

**Current implementation** (`src/woven/runtime/core.py`): five exception types, each raised by one collaborator on failure — `ModelError` (`Model`), `ToolError` (`Tool`), `ContextError` (`Context`), `ApprovalDenied` (`ApprovalPolicy`, via `approval_node`), `WorkflowError` (`src/woven/workflow/core.py`, raised by `tool_node`/`context_node`/`approval_node` when their required `WorkflowState` field is `None`). `AgentRuntime.run_turn` catches all five in one `except (ModelError, ToolError, ContextError, ApprovalDenied, WorkflowError) as exc:` clause, appends a `RunFailed` event (recording the failure before the exception surfaces to the caller), and re-raises — failures are recorded, never swallowed. `src/woven/client/cli/session.py`'s `run_chat_turn` catches the same five types so a CLI-level wiring bug renders as a normal error, not a stack trace.

Before `plan`/`code` modes existed, only `ModelError` was reachable (no mode used `tool_node`/`context_node`/`approval_node`), so the `except` clause only needed to name it. Adding `plan`/`code` is what first makes `ToolError`/`ContextError`/`ApprovalDenied` reachable through a real mode — the clause was broadened at that point specifically to keep the "failures are recorded, never swallowed" invariant true once those modes exist. `WorkflowError` was added later, once a repo audit ahead of `real-tools.md` flagged that a wiring bug pairing a step with a missing state field would otherwise surface as a raw `AttributeError`.

There is no broader exception hierarchy (e.g. no common `WovenError` base) — an unknown mode name still surfaces as a plain `KeyError` from the `BUILTIN_MODES` dict lookup, since there is only one caller path and wrapping it today would add a type with no behavioral difference. `WorkflowError` itself lives in `workflow/core.py`, not a new hierarchy — the same per-package convention as `ToolError`/`ContextError`/`ApprovalDenied`/`ModelError`.

## Cancellation

Deferred. Every operation in the current implementation (`FakeModel.generate`, straight-line workflow steps) is synchronous and returns in microseconds — there is nothing long-running for a caller to need to interrupt.

## Serialization

Deferred. Nothing in the current implementation crosses a process, thread, or storage boundary — `AgentRun`, `Turn`, and events live and die within a single Python process's memory.

## Testing

Deterministic testing is a permanent architectural requirement: the runtime must be testable without local LLMs, llama.cpp, cloud APIs, MCP, Graphiti, or vector databases. `FakeModel` is the permanent mechanism for the `Model` boundary; `FilesystemContext` is directly usable (deterministic by construction, no `Fake` sibling needed). See `tests/unit/test_fake_model.py`, `tests/unit/test_mock_tools.py`, `tests/unit/test_filesystem_context.py`, `tests/unit/test_mock_approval.py`, `tests/unit/test_auto_approval.py`, `tests/unit/test_workflow.py`, `tests/unit/test_modes.py`, and `tests/unit/test_agent_runtime.py` for the current coverage (successful end-to-end execution per mode, exact event-sequence assertions, request-content assertions, multi-turn behavior, and the deterministic failure paths for all five exception types, including `WorkflowError`'s missing-field guards).

## Current implementation vs. future work

| Concept | Status |
|---|---|
| AgentRuntime, AgentRun, Turn | Implemented (in-memory, no persistence) |
| Mode (`chat`, `plan`, `code`) | Implemented — Design mode not implemented |
| Workflow (straight-line steps) | Implemented |
| Node abstraction | Not implemented — `model_node`/`tool_node`/`context_node`/`approval_node` are all plain functions; four node kinds now exist and still share no behavior beyond the common step signature (and a small extracted `_build_tool_request` helper), so no `Node` class was extracted |
| WorkflowState | Implemented (fields added only as each node kind needed them) |
| Model protocol, ModelRequest/Response, FakeModel | Implemented (`ModelRequest.context` added once `context_node` existed) |
| Provider protocol, GeminiProvider, MODEL_PROVIDERS | Implemented — Gemini only; local/server-based providers are `.claude/plans/local-inference.md` |
| `Provider.check_connection()`, `SETUP_HINT` | Implemented — see `docs/architecture/setup-and-diagnostics.md` |
| Events (12 types, callback-collected) | Implemented |
| Errors (`ModelError`/`ToolError`/`ContextError`/`ApprovalDenied`/`WorkflowError` → `RunFailed`) | Implemented |
| Tools (`Tool` protocol, `tool_node`, `MockTools`) | Implemented — wired into `code` mode, always gated by `approval_node` |
| Context (`Context` protocol, `ContextSnapshot`, `FilesystemContext`, `context_node`) | Implemented — no embeddings/vector DB; symbol info and conversation-history retrieval remain future work |
| Permissions (`ApprovalPolicy`, `MockApproval`, `AutoApprovalPolicy`, `approval_node`) | Implemented |
| Memory / Graphiti | Not implemented |
| Cancellation | Not implemented (deferred — nothing blocks) |
| Serialization / persistence | Not implemented (deferred — nothing crosses a boundary) |
| Additional modes (Code, Plan) | Implemented — Design mode not implemented |
| LangGraph, MCP, model routing | Not implemented |
| Clients (Woven app, CLI, VS Code, API server) | CLI implemented for `chat` mode only; `plan`/`code` reachable via the direct Python API, not yet wired into the CLI |

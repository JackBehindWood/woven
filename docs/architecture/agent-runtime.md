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
- `BUILTIN_MODES` is a plain module-level `dict[str, Mode]` with one entry, `"chat"`.
- `AgentRuntime` (see below) looks up `BUILTIN_MODES[mode_name]` and never branches on mode name itself — adding Code/Plan/Design later means adding dict entries and new `workflow_factory` functions, not touching the runtime.

An enum was rejected because it can't carry behavior (which workflow to build) without an external dict keyed by the enum — that's this design with extra steps. A plugin/registry loader was rejected because there is exactly one mode today; that machinery would have no second consumer to justify it.

## Workflows

**Concept:** A Workflow defines execution strategy — eventually model calls, tools, context retrieval, approvals, conditions, artifacts, multiple nodes. LangGraph may become a future orchestration *implementation* but is not the domain architecture and is not used here.

**Current implementation** (`src/woven/workflow/core.py`):
- `Workflow` holds a `name` and an ordered `steps: list[Callable[[WorkflowState, EventSink], WorkflowState]]`.
- `Workflow.run(state, emit)` executes the steps in a straight-line loop, threading state through each one.
- No branching, no DAG, no conditions, no retries, no parallelism. Extending it later means appending another callable — there is no generic executor to design against yet.

## Nodes

**Concept:** Conceptual node types include ModelNode, ToolNode, ContextNode, ApprovalNode, ConditionNode, ArtifactNode, with HumanInputNode/SubWorkflowNode as future possibilities.

**Current implementation:** there is no generic `Node` base class. `model_node` (`src/woven/workflow/core.py`) is a plain function matching the `Callable[[WorkflowState, EventSink], WorkflowState]` step signature — not a class hierarchy.

**Why:** a `Node` base class earns its cost once there are ≥2 heterogeneous node kinds needing shared lifecycle/validation logic. With exactly one node kind implemented, a class hierarchy would be ceremony with no shared behavior to justify it. If/when a second node kind (e.g. ToolNode) is added, extracting a shared `Node` protocol at that point is a cheap, well-motivated refactor — cheaper than maintaining an unused abstraction now.

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
    output_text: str | None = None
```

`turn_id` is included so `model_node` can stamp it onto the events it emits without threading a second parameter through every step. Being frozen, each step produces a new state via `state.model_copy(update={...})` rather than mutating in place. No speculative fields (no `step_index`, `history`, `variables`, `context_references`) — every field here is read or written by the one implemented step.

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


class ModelResponse(BaseModel):
    text: str
```

`purpose` is the one forward-looking field: it costs nothing today and is the natural seam for future prompt-selection/routing. Fields like `context_requirements`, `expected_output`, or sampling parameters are omitted because nothing in this slice reads them — `FakeModel` doesn't need sampling params, and there's no context subsystem to request from yet.

## FakeModel

**Current implementation** (`src/woven/models/fake.py`): a plain class, not a pydantic model (it's stateful/behavioral, not a data schema).

- Records every `ModelRequest` it receives, in order, in `received_requests: list[ModelRequest]`.
- Returns a fixed, caller-configured `response_text` — no randomness, no time/hash-based variation, so the same input always produces the same output.
- Can be constructed with `raise_error=True` to deterministically raise `ModelError` on `generate()`, exercising the failure path without a second class.
- Depends only on the shape of the `Model` protocol; `model_node` and `Workflow` never import `FakeModel` directly.

`FakeModel` is permanent test infrastructure per `docs/architecture.md` and `tests/README.md` — not a throwaway mock to be deleted once a real adapter exists.

## Tools

**Concept (future):**

```text
ToolRequest
    ↓
Permission / Policy
    ↓
Tool
    ↓
ToolResult
```

MCP is a future adapter/integration boundary, not Woven's internal tool architecture.

**Current implementation:** none. Tools are entirely out of scope for this slice.

## Context

**Concept (future):** answers "what information is relevant to this task?" via deterministic retrieval (explicit file selection, path/name search, text search, symbol info, recent conversation) — no embeddings, vector databases, or knowledge graphs.

**Current implementation:** none. Context is entirely out of scope for this slice.

### ContextSnapshot vs WorkflowState

This distinction is preserved for future work even though neither Context nor ContextSnapshot exist yet:

```text
WorkflowState  = what the workflow currently knows
ContextSnapshot = what a particular model invocation actually received
```

They must not be conflated when Context is eventually implemented.

## Memory

**Concept (future):** answers "what should the system remember?" — distinct from retrieval's "what's relevant right now?" Project memory should eventually be isolated by project by default.

**Current implementation:** none. Memory is entirely out of scope for this slice.

### Graphiti

Graphiti (`getzep/graphiti`, a temporal-knowledge-graph library) is a **future, optional** Memory-subsystem backend. It is not a dependency of this repository, is not designed around in the current runtime, and must not be added until there is a concrete need. When eventually introduced, it should sit behind clean Woven memory/retrieval interfaces so the core runtime and its deterministic tests remain fully usable without it.

(Note: Graphiti is unrelated to "Graphify," the Claude Code skill used as a dev-assistant tool for exploring this repository. Graphify has no bearing on Woven's runtime architecture and is not referenced further in this document.)

## Events

**Concept:** An AgentRun produces an event stream — the architectural principle, not a specific taxonomy. Future events may include ContextRetrieved, ToolCallRequested, ApprovalRequested, FileChangeProposed, TestStarted/Completed, RunCancelled, and more. No event bus/message broker.

**Current implementation** (`src/woven/events/core.py`): immutable frozen pydantic models, all inheriting a `turn_id: str` field from `Event`:

- `RunStarted(run_id)`
- `TurnStarted(mode_name)`
- `ModelStarted(request: ModelRequest)`
- `ModelCompleted(response: ModelResponse)`
- `TurnCompleted(output_text)`
- `RunCompleted(run_id)`
- `RunFailed(run_id, error)`

Events are collected via a plain callback (`emit: Callable[[Event], None]`) that `AgentRuntime.run_turn` closes over, appending each event to both `Turn.events` and `AgentRun.events`. This is the "callback/listener" option, not a broker — there is no publish/subscribe machinery, no async dispatch, and no external transport.

For a successful turn, the sequence is always: `RunStarted, TurnStarted, ModelStarted, ModelCompleted, TurnCompleted, RunCompleted`.

**Known simplification to revisit:** `RunStarted`/`RunCompleted` currently fire around each individual `run_turn` call rather than around the lifetime of the whole `AgentRun`. This is fine today because nothing in the runtime needs run-level setup/teardown distinct from turn-level setup/teardown — but it's a designed seam to revisit once multi-turn runs need genuine run-scoped behavior (e.g. run-level context that persists across turns).

## Errors

**Current implementation** (`src/woven/models/protocol.py`): one exception type, `ModelError`, raised by a `Model` implementation on failure. `AgentRuntime.run_turn` catches it, appends a `RunFailed` event (recording the failure before the exception surfaces to the caller), and re-raises — failures are recorded, never swallowed. There is no broader exception hierarchy (e.g. no separate `WorkflowError` or `InvalidModeError`) — an unknown mode name currently surfaces as a plain `KeyError` from the `BUILTIN_MODES` dict lookup, since there is only one caller path and wrapping it today would add a type with no behavioral difference.

## Cancellation

Deferred. Every operation in the current implementation (`FakeModel.generate`, straight-line workflow steps) is synchronous and returns in microseconds — there is nothing long-running for a caller to need to interrupt.

## Serialization

Deferred. Nothing in the current implementation crosses a process, thread, or storage boundary — `AgentRun`, `Turn`, and events live and die within a single Python process's memory.

## Testing

Deterministic testing is a permanent architectural requirement: the runtime must be testable without local LLMs, llama.cpp, cloud APIs, MCP, Graphiti, or vector databases. `FakeModel` is the permanent mechanism for this — see `tests/test_fake_model.py`, `tests/test_workflow.py`, `tests/test_modes.py`, and `tests/test_agent_runtime.py` for the current coverage (successful end-to-end execution, exact event-sequence assertions, request-content assertions, multi-turn behavior, and the deterministic failure path).

## Current implementation vs. future work

| Concept | Status |
|---|---|
| AgentRuntime, AgentRun, Turn | Implemented (in-memory, no persistence) |
| Mode (single `chat` mode) | Implemented |
| Workflow (straight-line steps) | Implemented |
| Node abstraction | Not implemented — `model_node` is a plain function; deferred until a second node kind exists |
| WorkflowState | Implemented (minimal fields only) |
| Model protocol, ModelRequest/Response, FakeModel | Implemented |
| Events (7 types, callback-collected) | Implemented |
| Errors (`ModelError` → `RunFailed`) | Implemented |
| Tools | Not implemented |
| Context / ContextSnapshot | Not implemented |
| Memory / Graphiti | Not implemented |
| Cancellation | Not implemented (deferred — nothing blocks) |
| Serialization / persistence | Not implemented (deferred — nothing crosses a boundary) |
| Additional modes (Code, Plan, Design) | Not implemented — architecture allows adding them without runtime changes |
| LangGraph, MCP, model routing, real provider adapters | Not implemented |
| Clients (Woven app, CLI, VS Code, API server) | Not implemented |

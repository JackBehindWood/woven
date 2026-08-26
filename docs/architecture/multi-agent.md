# Multi-agent architecture (design only)

This document is the durable, committed reference for how multi-agent support — an orchestrator agent delegating to sub-agents, or multiple concurrent agents driven by one client — would extend Woven's Agent Runtime. It is Slice 4's deliverable: a dedicated planning pass, no code. It complements `docs/architecture/agent-runtime.md` (the current single-agent runtime) and `docs/architecture/cli-client.md` (the current client/runtime boundary) the same way those two complement each other — recording design and reasoning so a future contributor doesn't have to reconstruct it.

**Nothing in this document is implemented.** Every field, event, and function named below is a target shape for a future slice, not code that exists today. Where this document says "current," it describes `src/woven/` as it stands after Slice 3 (Tools). Where it says "future," it describes direction only — no promise of a specific slice or timeline beyond what `.claude/plans/project-timeline.md` already schedules.

This document builds directly on `docs/architecture/decisions.md`'s 2026-08-26 "Multi-agent-readiness considerations" entry (written during Slice 3), which first identified the two real gaps this document resolves: the single-agent scoping of `Event`/`AgentRun`, and why "agent-as-tool" is a false equivalence. Two forks left open there were checked with the project owner before writing this document:

- **Nesting model:** a sub-agent's events are **flattened** into the parent `AgentRun.events` (tagged for correlation) *and* the sub-agent's own `Turn`/`AgentRun` object is **retained** via a nested reference — not one or the other. This avoids the "lossy adapter" problem named below, while keeping today's flat-list consumers (the CLI's event rendering) unchanged.
- **Orchestrator shape:** a plain **Workflow step**, matching the existing `Callable[[WorkflowState, EventSink], WorkflowState]` signature used by `model_node`/`tool_node` — not a new Mode-level composition concept. No new node class.

## 1. Correlation fields: where `agent_id` would live

Two things get conflated by a single "agent_id" label; the target design keeps them as two fields on two different types:

- **`Event.agent_id: str`** — which agent produced this event. This is the field that's actually *read*, and only when a sub-agent's events are flattened into the parent's `AgentRun.events` list: without it, a caller can't tell a delegated sub-agent's `ModelStarted` from the orchestrating agent's own. This mirrors exactly why `turn_id` lives directly on `Event` today (`decisions.md`: "read by every node that emits events, not a might-need-it-later field") — same non-speculative-addition reasoning, applied to the same kind of field.
- **`AgentRun.agent_id: str`** (identity of the agent this run belongs to) and **`AgentRun.parent_run_id: str | None`** (links a sub-agent's run back to the run that spawned it, `None` for a top-level run). `Turn` needs no separate field of its own — it already belongs to exactly one `AgentRun`, so `Turn`'s agent identity is inherited, not duplicated.

**Recommendation: defer the actual field additions.** Nothing today reads `agent_id` or `parent_run_id` — there is no orchestrator step to produce or consume them. Adding them now would be exactly the kind of speculative field `agent-runtime.md`'s `WorkflowState` section and CLAUDE.md's principles both rule out ("No speculative fields... every field here is read or written by the one implemented step"). The target shape is recorded here specifically so that when an orchestrator step *is* built, adding these fields is additive (new optional/required fields with clear producers and consumers already known) rather than a redesign discovered mid-implementation.

## 2. `AgentRuntime`: no new method needed for concurrency

**Conclusion: multiple `AgentRun` instances, already legal today, are sufficient — no new `AgentRuntime` method or shape is needed for either concurrency scenario.**

`AgentRuntime.run_turn(run, mode_name, input_text, model)` (`src/woven/runtime/core.py`) holds no mutable state of its own — every piece of state that changes (`Turn`, `AgentRun`, the `emit` closure) is constructed fresh or passed in per call. This has two consequences:

- **Multiple concurrent top-level agents** (e.g. a future client juggling several chats): the caller simply holds N independent `AgentRun` objects and calls `run_turn` on whichever one needs its next turn. Nothing in `AgentRuntime` couples calls to each other. This is already possible with the current signature; it just has no consumer yet (no client drives more than one `AgentRun` today).
- **An orchestrator step recursing into the runtime**: a `Workflow` step calling `runtime.run_turn(child_run, ...)` from inside another `run_turn` call is a reentrant call into the same stateless method — not a different code path, and not a capability that needs to be added.

The real gaps for multi-agent are not in `AgentRuntime` itself:

- **(a)** The event-injection gap `cli-client.md` already documents: `run_turn`'s `emit` closure is defined inside the method with no parameter for a caller to inject an external `EventSink`, so a client can only replay events post-hoc, never observe them live. That gap was originally motivated by call duration (nothing today is long-running); multi-agent adds a second, independent motivation — a client driving several concurrent agents would want interleaved live rendering across them, which needs the same injectable `EventSink` this gap already calls for.
- **(b)** The correlation/nesting fields from Section 1, needed to make sense of a flattened multi-agent event stream once one exists.

## 3. Minimal orchestrator step (`agent_node`): what it needs beyond `ToolNode`'s shape

This is the concrete answer to "what does a minimal orchestrator step need beyond `ToolNode`'s shape."

**Signature:** identical to the existing node functions — `agent_node(state: WorkflowState, emit: EventSink) -> WorkflowState` — a plain function, same as `model_node`/`tool_node`, not a class. No `Node` base class is introduced; this is a third instance of the same `Callable` shape, consistent with `decisions.md`'s standing position that a `Node` abstraction is only earned once a node kind needs shared behavior the plain-function shape can't express, which is not the case here either.

**Behavior:** builds a child `AgentRun`, calls `runtime.run_turn(child_run, sub_mode_name, derived_input_text, model)`, and receives back a `Turn`.

**The delta from `tool_node` — why this needs more than `ToolNode`'s shape:**

`tool_node` calls `state.tool.execute(request)`, which returns one scalar `ToolResult`, and emits exactly one `ToolCallStarted`/`ToolCallCompleted` pair. `agent_node` calls `runtime.run_turn(...)`, which returns a full `Turn` — an object carrying its *own* event list, not a scalar. Concretely: the child `run_turn` call's `emit` closure is defined *inside that call* and closes over the child's `turn`/`run` objects (`src/woven/runtime/core.py`'s `run_turn` body) — so every event the child produces (`RunStarted`, `TurnStarted`, `ModelStarted`, ...) lands in `child_turn.events` and `child_run.events`, **never automatically in the parent's**. `agent_node` runs in the parent's own `run_turn` call, closing over the *parent's* `emit` — a structurally separate closure. To flatten, `agent_node` must explicitly iterate `child_turn.events` after the child call returns and re-emit each one through its own (parent) `emit`, tagged with the child's `agent_id` (Section 1). This re-emission step is the concrete mechanism `ToolNode` never needed, because `ToolResult` carries no sub-events to propagate.

**New events (named here, not implemented):** `SubAgentStarted`/`SubAgentCompleted`, bracketing the delegation the same way `ModelStarted`/`ModelCompleted` and `ToolCallStarted`/`ToolCallCompleted` bracket their respective calls — carrying the child's `run_id`/`agent_id` so a renderer can identify a delegation boundary in the flattened stream even before inspecting individual re-emitted child events.

**Nesting (structural fidelity):** a new `WorkflowState` field, e.g. `sub_runs: list[AgentRun] = []`, added only when `agent_node` is actually built — same precedent as `WorkflowState.tool: Tool | None` being added only when `tool_node` needed it. This holds the child `AgentRun` object itself (not just its flattened events), so a caller can walk the actual sub-agent structure rather than reconstructing it from tags in a flat list.

**Output folding:** `state.output_text` set from `child_turn.output_text` — the same pattern `model_node` and `tool_node` already use.

## 4. Agent-as-tool remains a false equivalence

Reaffirming `decisions.md`'s existing finding, now tied directly to the design above: `Tool.execute(request: ToolRequest) -> ToolResult` (`src/woven/tools/protocol.py`) is synchronous, stateless, and collapses to one scalar `ToolResult`. Section 3 shows exactly what would be lost if a sub-agent were wrapped behind that same `Protocol` instead of designed as its own Workflow step: the sub-agent's `Turn` and its full event list have nowhere to go inside a `ToolResult`'s single `output_text` field — precisely the information the flatten-and-nest design in Sections 1 and 3 exists to preserve. If an agent-as-tool adapter is ever built for some other reason (e.g. exposing a sub-agent through an existing tool-calling interface), it must be documented as a deliberately lossy adapter, not treated as "an agent is just another Tool."

## 5. Interface changes: now vs. later

| Change | When |
|---|---|
| `Event.agent_id`, `AgentRun.agent_id` / `parent_run_id` | Later — add when `agent_node` is actually built (Section 1) |
| `WorkflowState.sub_runs: list[AgentRun]` | Later — add when `agent_node` is actually built (Section 3) |
| `SubAgentStarted` / `SubAgentCompleted` events | Later — add alongside `agent_node` |
| `agent_node` itself | Later — no scheduled slice yet; candidate for a future "Additional Modes"-adjacent slice once an orchestrator use case is concrete |
| Optional injectable `EventSink` parameter on `run_turn` | Later, but tracked now as doubly-motivated (duration, per `cli-client.md`, and concurrency, per Section 2) — a natural candidate whenever Slice 10 (Additional clients) or a live-rendering need becomes concrete |
| `AgentRuntime` method/shape changes | **None planned** — Section 2 concludes the existing `run_turn` signature is sufficient |

All of the "later" changes are additive (new optional fields/parameters, new event types) — deferring them costs nothing today and breaks no existing call site. This follows the same reasoning `decisions.md` already applied to `turn_id` and the `Node` abstraction: add a field or type when something concrete reads or produces it, not before.

**Explicitly out of scope / unresolved here** — named as open questions for whichever future slice implements an orchestrator, not resolved by this document:

- **Sub-agent error propagation.** Today, `AgentRuntime.run_turn` catches `ModelError`, emits `RunFailed`, and re-raises (`agent-runtime.md`'s "Errors" section) — entirely single-agent-scoped. What happens when a *child* `run_turn` call inside `agent_node` raises mid-orchestration (does the parent's `run_turn` also fail? does the parent get a chance to recover and continue without the sub-agent's result?) is not decided here.
- **Resource/model-pooling for concurrent sub-agents.** Whether concurrent agents share one `Model` instance, get independent instances, or need any coordination is not addressed — nothing in the current `Model` protocol assumes exclusivity, but nothing here has been designed against real concurrent load either.

## Current implementation vs. future work

| Concept | Status |
|---|---|
| Single-agent `AgentRuntime`/`AgentRun`/`Turn`/`Event`/`Workflow` | Implemented (Slice 1–3) |
| This document (`multi-agent.md`) | Design only — no code (Slice 4) |
| `Event.agent_id`, `AgentRun.agent_id`/`parent_run_id` | Not implemented — deferred, target shape recorded (Section 1) |
| `agent_node` Workflow step | Not implemented — no scheduled slice |
| `WorkflowState.sub_runs` | Not implemented — deferred (Section 3) |
| `SubAgentStarted`/`SubAgentCompleted` events | Not implemented — deferred (Section 3) |
| Injectable `EventSink` on `run_turn` | Not implemented — pre-existing gap (`cli-client.md`), now doubly motivated (Section 2) |
| New `AgentRuntime` method for concurrency | Not planned — existing `run_turn` signature judged sufficient (Section 2) |

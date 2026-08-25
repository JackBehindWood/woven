# Architecture overview

This document describes the intended architecture for Woven and the core conceptual boundaries. This is an architectural overview — not implementation documentation.

Principles

- Model-agnostic: The runtime should not depend on a single model provider. Model adapters are infrastructure that plug into the runtime.
- Client-independent: UIs (CLI, VS Code, Web) are clients of the runtime, not the place where agent logic lives.
- Context-first: Retrieval and relevant context delivery are first-class concerns.
- Deterministic development: Core behavior must be testable without high-quality models.

Core concepts

- Agent Runtime: The central orchestration layer that accepts requests from clients, manages modes/workflows, coordinates tools, models, context, and memory, and emits events. Initially this is a conceptual boundary only.

- Modes: High-level behavioral configurations (Chat, Code, Plan, Design). Modes are composed from workflows and settings rather than separate agents.

- Workflows: Reusable orchestration patterns that define a sequence of steps/nodes for a given task. Workflows are domain logic and must be decoupled from runtime internals.

- Nodes: Discrete units of work in a workflow (e.g., call model, call tool, retrieve context). Nodes are stateless and reproducible.

- AgentRun / Turn: A single interaction or conversation step managed by the runtime. AgentRun tracks inputs, outputs, and intermediate events.

- WorkflowState: The runtime representation of a workflow's execution state (variables, step index, progress, partial results).

- Model abstraction: A generic interface describing how the runtime requests completions or embeddings. ModelRequest should capture input, temperature, max_tokens, and metadata.

- ModelRequest: A structured request that captures the inputs and constraints for calling a model adapter.

- Tools: External capabilities the agent can call (file system helpers, shell, web retrieval). Tools expose a clean, testable interface and are runtime adapters.

- Context: Relevant information retrieved for a turn. ContextSnapshot is a curated collection of items (file snippets, notes, messages) provided to the model for a specific request.

- Memory: Persistent storage of selected facts and events. Memory answers "what should the system remember?" and is separate from retrieval/context.

- Events: The runtime emits events for important lifecycle moments (turn-start, turn-end, tool-called, model-called) for observability and debugging.

- Projects / Workspaces: Namespaced collections that isolate conversations, instructions, files, memory, tools, permissions, and agent configuration.

- Multiple clients: CLI, Web, and VS Code are clients of the runtime and should be thin — the runtime is the source of truth.

Current repository state vs intended architecture

- Current state: repository foundation with documentation and development tooling. No runtime, models, or tools are implemented yet.
- Intended architecture: conceptual boundaries and goals described above. Implementation will follow in small, deterministic slices.

Guidance for implementers

- Start with a small deterministic vertical slice: core runtime abstractions, FakeModel for tests, and a minimal workflow executor.
- Keep adapters (models, tools) behind clear interfaces so they can be swapped without changing domain logic.
- Prioritize tests that run locally on modest hardware.

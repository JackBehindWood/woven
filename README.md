# Woven

Open-source, local-first AI agent platform for weaving together models, tools, context, memory, and workflows.

## Vision

Woven aims to become an open-source, local-first AI agent platform that composes models, tools, context, memory, workflows, and projects into a single, modular system. Over time Woven will support multiple clients (CLI, web, VS Code) and multiple model backends while keeping the core runtime model-agnostic.

## Why Woven

- Model independence: architected so model providers are pluggable rather than baked into the runtime.
- Local-first development: contributors can work without cloud services or powerful GPUs.
- Composable workflows: support behavioral "modes" built from reusable workflow components.
- Intelligent context management: prefer retrieving and delivering relevant context to the agent rather than sending large raw blobs.
- Persistent project memory: projects/workspaces will store durable memory, files, and configuration.
- Multiple clients: the runtime will be client-independent so that UIs are thin clients.
- Deterministic development and testing: the core design values reproducibility and deterministic unit tests.

## Architecture direction

The intended high-level architecture looks like:

Clients
   ↓
Application / API
   ↓
Agent Runtime
   ↓
Modes / Workflows
   ↓
Models / Tools / Context / Permissions
   ↓
Infrastructure

This diagram represents an intended direction, not a fully implemented system. The Agent Runtime should remain model-agnostic and client-independent.

## Current status

Woven is in the early repository and architecture setup stage. This repository provides the foundation and development tooling; no runtime, local inference, memory system, MCP integration, or client integrations are implemented yet.

## Development philosophy

- Small, incremental changes.
- Deterministic tests by default.
- Model-independent development: avoid coupling to any single model provider.
- Avoid premature complexity: don't add heavy infra before the architecture is proven.
- Contributors should be able to develop with modest hardware (an 8 GB laptop).

## Development (local)

This repository initializes a minimal Python development environment using Python 3.12 and uv. Developer tooling includes:

- uv for environment and dependency management
- pytest for tests
- ruff for linting and formatting

To set up locally (example):

1. Install Python 3.12.
2. Install uv: `pip install uv`.
3. Install dev dependencies: `uv install -d`.

(We have intentionally not created the package/runtime layout yet. That will come with the first implementation slice.)

## Testing

Testing is deterministic-first. The repository includes a tests README explaining the testing philosophy. Unit tests that don't depend on model quality are preferred; model/provider integration tests should be opt-in and run separately.

## Contributing

Please see CONTRIBUTING.md for how to contribute. In short: open a small, focused branch (feature/* or fix/*), work locally, open a PR, and request review. Keep changes small and include deterministic tests when appropriate.

## Roadmap (high-level)

1. Repository and development foundation (this stage).
2. Deterministic Agent Runtime vertical slice (core abstractions, FakeModel for tests).
3. Tools and context retrieval.
4. Code-focused workflows and modes.
5. Projects/workspaces and persistence.
6. Real model provider adapters and optional local inference.
7. HTTP/API and client integrations.
8. VS Code extension and other clients.

This roadmap is a high-level direction, not a binding promise.

---

For more details, see docs/architecture.md and CONTRIBUTING.md.

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

Woven has a first deterministic Agent Runtime vertical slice (`src/woven/`): an `AgentRuntime` executes a `Turn` through a `Mode`/`Workflow` that invokes a model step against a `FakeModel`, producing a deterministic event stream, covered by tests. See `docs/architecture/agent-runtime.md` for the current design.

A first CLI client (`woven chat`, under `src/woven/client/cli/`) now demonstrates driving the runtime from outside its own test suite — see `docs/architecture/cli-client.md`. It still runs against `FakeModel` only. A `Tool` protocol, `tool_node`, and deterministic `MockTools` exist (see `docs/architecture/agent-runtime.md`'s Tools section) but aren't wired into any Mode yet. No local inference, memory system, context retrieval, or MCP integration are implemented yet.

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

To set up locally:

1. Install Python 3.12.
2. Install uv: `pip install uv`.
3. Install dependencies: `uv sync --extra dev` (add `--extra cli` for the CLI client's typer/rich dependencies).
4. Run the tests: `uv run pytest`.
5. Lint and format: `uv run ruff check .` and `uv run ruff format --check .`.

The package lives under `src/woven/`. Try the CLI with `uv run woven chat` (after syncing `--extra cli`).

**Known issue: editable-install / venv flakiness.** Occasionally `uv run woven` (or `import woven`) fails with `ModuleNotFoundError: No module named 'woven'` even though `uv sync` reports success. This is a stray `.pth`-ordering bug in the dev venv, triggered by `virtualenv` (a transitive dependency of `pre-commit`) racing the editable install — not a code issue. It has recurred more than once, so don't re-debug it from scratch: `.python-version` (pinning `3.12`) and `pyproject.toml`'s `[tool.uv] python-preference = "managed"` reduce how often it happens; if it still occurs, `rm -rf .venv && uv sync --all-extras` (or `uv sync --all-extras --reinstall-package woven`) clears it.

## Testing

Testing is deterministic-first. The repository includes a tests README explaining the testing philosophy. Unit tests that don't depend on model quality are preferred; model/provider integration tests should be opt-in and run separately.

## Contributing

Please see CONTRIBUTING.md for how to contribute. In short: open a small, focused branch (feature/* or fix/*), work locally, open a PR, and request review. Keep changes small and include deterministic tests when appropriate.

## Roadmap (high-level)

1. ~~Repository and development foundation.~~
2. ~~Deterministic Agent Runtime vertical slice (core abstractions, FakeModel for tests).~~ Done — see `docs/architecture/agent-runtime.md`.
3. ~~Tools.~~ Protocol/`tool_node`/`MockTools` done, not wired into a Mode yet — see `docs/architecture/agent-runtime.md`. Context retrieval still pending.
4. Code-focused workflows and modes.
5. Projects/workspaces and persistence.
6. Real model provider adapters and optional local inference.
7. ~~HTTP/API and client integrations.~~ First slice done — CLI client (`woven chat`), see `docs/architecture/cli-client.md`.
8. VS Code extension and other clients.

This roadmap is a high-level direction, not a binding promise.

---

For more details, see docs/architecture.md, docs/architecture/ (current runtime design), and CONTRIBUTING.md.

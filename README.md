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

Woven has a deterministic Agent Runtime (`src/woven/`): an `AgentRuntime` executes a `Turn` through one of three `Mode`s (`chat`, `plan`, `code`), each a `Workflow` composing model, context, approval, and tool steps, producing a deterministic event stream, covered by tests. See `docs/architecture/agent-runtime.md` for the current design.

A CLI client (`woven chat`, under `src/woven/client/cli/`) is at parity with the runtime — three selectable permission tiers, real filesystem context retrieval, and `/mode`/`/permission`/`/context`/`/settings` commands — see `docs/clients/cli.md`. Multi-agent support is designed but not implemented yet — see `docs/architecture/multi-agent.md`. Everything above still runs on fakes: no real model provider, no persistence, no memory, no MCP integration.

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
6. (Optional) Install the git pre-commit hook: `uv tool install pre-commit && pre-commit install`. `pre-commit` is installed as an isolated uv tool, not a project dependency — it never shares the project's `.venv`, so its `virtualenv` dependency can't collide with `woven`'s own editable install there.

The package lives under `src/woven/`. Try the CLI with `uv run woven chat` (after syncing `--extra cli`).

**Resolved issue: editable-install / venv flakiness.** `uv run woven` (or `import woven`) used to occasionally fail with `ModuleNotFoundError: No module named 'woven'` even though `uv sync` reported success — a stray `.pth`-ordering bug in the dev venv, suspected to be triggered by `virtualenv` (then a transitive dependency of `pre-commit`, which used to live in the project's own venv via the `dev` extra) racing the editable install. Fixed by upgrading `uv` (0.10.8 → 0.12.6) and moving `pre-commit` out of `dev` into an isolated `uv tool install` (see step 6 above), so `virtualenv` no longer installs into `.venv` at all. `.python-version` (pinning `3.12`) and `[tool.uv] python-preference = "managed"` remain in place as belt-and-braces. If `ModuleNotFoundError: No module named 'woven'` ever recurs regardless: `rm -rf .venv && uv sync --all-extras` (or `uv sync --all-extras --reinstall-package woven`) clears it.

## Testing

Testing is deterministic-first. The repository includes a tests README explaining the testing philosophy. Unit tests that don't depend on model quality are preferred; model/provider integration tests should be opt-in and run separately.

## Contributing

Please see CONTRIBUTING.md for how to contribute. In short: open a small, focused branch (feature/* or fix/*), work locally, open a PR, and request review. Keep changes small and include deterministic tests when appropriate.

## Roadmap (high-level)

1. ~~Repository and development foundation.~~
2. ~~Deterministic Agent Runtime (core abstractions, FakeModel for tests).~~ Done — see `docs/architecture/agent-runtime.md`.
3. ~~Tools, Context, Permissions, and the `plan`/`code` Modes.~~ Done — see `docs/architecture/agent-runtime.md`.
4. ~~A CLI client at parity with the runtime.~~ Done — see `docs/clients/cli.md`.
5. Real model provider adapters (cloud first, then local inference).
6. Real tool implementations (shell/file), replacing `MockTools`.
7. Projects/workspaces and persistence.
8. Project-scoped memory.
9. Multi-agent implementation — see `docs/architecture/multi-agent.md` for the design.
10. VS Code extension and other clients.

Items 5–10 are dependency-ordered. This roadmap is a high-level direction, not a binding promise.

---

For more details, see docs/architecture.md, docs/architecture/ (current runtime design), and CONTRIBUTING.md.

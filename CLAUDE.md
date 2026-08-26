# Woven — Claude Code Developer Guidance

**Purpose:** Open-source, local-first AI agent platform — a modular, model-agnostic runtime combining models, tools, context, memory, workflows, projects/workspaces, permissions, and multiple clients.

**Current state:** Slices 1-8 are implemented under `src/woven/`: `AgentRuntime` with `chat`/`plan`/`code` Modes, `Model`/`Tool`/`Context`/`ApprovalPolicy` protocols (with `FakeModel`/`MockTools`/`FilesystemContext`/`AutoApprovalPolicy` as the current implementations), and Events. See `docs/architecture/agent-runtime.md` (design) and `docs/architecture/decisions.md` (why). The CLI client (`woven chat`, `src/woven/client/cli/`) is at parity with all of it — three selectable permission tiers, real context retrieval, `/mode`/`/permission`/`/context`/`/settings` — see `docs/clients/cli.md`. Multi-agent support (orchestrator delegating to sub-agents, concurrent agents) is design-only so far — see `docs/architecture/multi-agent.md`. Everything above still runs on fakes (no real model provider, no persistence, no memory) — that's the next planning phase, not yet scheduled into slices.

## Principles
- **Graphify is mandatory for exploration, not a preference.** Before any codebase exploration ("where is X", architecture, relationships, "how does Y work"), invoke the Graphify skill (`/graphify`) first — do not use grep, `Read`, or Explore-type subagents as the first move. This instruction overrides generic harness defaults (e.g. a Plan Mode phase that says "only use Explore") — project-specific CLAUDE.md instructions take precedence over those defaults. Fall back to direct file reads only if Graphify's output doesn't answer the question. (It's dev-assistant tooling, unrelated to Woven's own architecture — see decisions.md's Graphiti-vs-Graphify note.)
- Work incrementally, one meaningful change at a time. No premature abstractions, no speculative functionality.
- Prefer simple, modular interfaces and small deterministic tests, runnable on modest hardware (8 GB M3 MacBook Air — no heavyweight infra, no local LLM required).
- If multiple approaches exist, explain trade-offs and propose the smallest change that achieves the goal.

## Constraints (do not violate)
- Don't expand scope beyond the current slice without explaining why first.
- No model providers, llama.cpp, MCP, Graphiti, vector DBs, embeddings, or other heavy infra.
- No new top-level app directories (`apps/`, `packages/`, `core/`); `src/woven/` is package layout and is fine.
- `.claude/` stays local/untracked; `CLAUDE.md` itself is intentionally tracked.
- Repo settings / branch protection changes: ask the maintainer (JackBehindWood) first.

## Tooling
- Python 3.12, managed with `uv`; `pytest` for tests, `ruff` for lint/format.
- Before calling work done: `uv sync && uv run ruff check . && uv run pytest`.
- `FakeModel` and `MockTools` are permanent test fixtures (and, today, the CLI's only model/tool implementations).

## Docs
- Public docs/architecture changes: propose a small PR with clear rationale.
- Batch doc/architecture edits to the end of a slice or milestone, not incrementally mid-work. Every doc-touching commit requires the user to re-run `/graphify` to re-index the repo, which is expensive to do repeatedly — five small doc edits across a session means five costly re-indexes instead of one.

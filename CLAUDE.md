# Woven — Claude Code Developer Guidance

**Purpose:** Open-source, local-first, model-agnostic AI agent platform (`src/woven/`).

**Principle:** The runtime is the product; clients are thin interfaces to it. `src/woven/{runtime,workflow,modes,events,permissions,context,tools,models}/` must work with zero clients installed — clients (`src/woven/client/cli/` today) never hold agent logic.

**Current state:** `AgentRuntime` (chat/plan/code Modes, Model/Tool/Context/ApprovalPolicy protocols) runs on `FakeModel`/`MockTools` — permanent test fixtures, and today the CLI's only model/tool impl; `FilesystemContext`/`AutoApprovalPolicy` are real. Real: settings persistence (`src/woven/settings/`), Gemini provider (wired, not yet default), CLI at parity with runtime. Still design-only: multi-agent (`docs/architecture/multi-agent.md`). See `docs/architecture/*.md` for detail; `.claude/plans/roadmap.md` for what's next.

## Scope
- Stay within the current planned phase (`.claude/plans/roadmap.md`); explain before expanding scope.
- Heavy infra (model providers, orchestration frameworks, vector DBs/embeddings, etc.) ships only once it has a named `.claude/plans/*.md` item that's actively being worked — never pre-built speculatively. Currently planned: Gemini (`model-providers.md`, via `SecretStore`/`GEMINI_API_KEY`), local LLM/llama.cpp/Jetson (`local-inference.md`), LangGraph + MCP (`orchestration-upgrade.md`). LangChain is evaluation-only. Graphiti, vector DBs, and embeddings have no plan file yet — out of scope for now, not permanently excluded.
- No new top-level app dirs (`apps/`, `packages/`, `core/`) — `src/woven/` is the package layout.
- `.claude/` stays local/untracked; `docs/` never names `.claude/` planning artifacts.
- Repo settings / branch protection changes: ask the maintainer (JackBehindWood) first.

## Graphify (mandatory before exploration)
Before any "where is X" / architecture / relationship question, invoke `/graphify` — overrides generic harness defaults (e.g. Plan Mode's "Explore only"). If `graphify-out/graph.json` exists, run `graphify query "..."` directly; else run the full pipeline. Fall back to direct reads only if Graphify doesn't answer. Any doc-writing pass invalidates the graph — run `/graphify --update` after (ask permission first), once per session. Code-only (`.py`) passes: run `graphify update <path>` instead (cheaper, AST-only, no LLM) — reserve the full skill for passes touching docs/papers/images. This also counts for explorer agents!

## Dev
Python 3.12, `uv`, `pytest`, `ruff`. Ruff auto-runs post-`Write`/`Edit` via hook. Before calling work done: `uv sync && uv run ruff check . && uv run pytest`. Must run on 8GB M3 Air — no heavyweight infra, no local LLM required (yet).

## Docs
`docs/architecture/` and `docs/clients/` are durable references, updated once work ships (small PR, clear rationale). `.claude/plans/` is forward-looking/local-only, updated as work progresses (gitignored, no PR needed). Batch doc edits to milestone end — each doc-touching commit forces an expensive `/graphify` re-index.

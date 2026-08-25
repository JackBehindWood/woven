Woven — Claude Code Developer Guidance

Project identity
- Repository: Woven (woven)
- Purpose: Open-source, local-first AI agent platform. Long-term goals: modular, model-agnostic agent system combining models, tools, context, memory, workflows, projects/workspaces, permissions, and multiple clients.
- Current state: repository and architecture foundation only. NO runtime, model adapters, or external integrations are implemented yet.

Claude Code development principles for this repo
- Inspect the actual repository before making assumptions.
- Work incrementally: make one meaningful change at a time.
- Avoid premature abstractions and avoid adding speculative future functionality.
- Prefer simple, modular interfaces and small deterministic tests.
- Preserve working functionality: do not change public-facing docs or behavior unless required.
- Do NOT introduce heavyweight infra or require a powerful local LLM. The development machine is an 8 GB M3 MacBook Air.
- If multiple reasonable approaches exist, explain trade-offs and propose the smallest change that achieves the goal.

Important constraints (do not violate)
- Do NOT implement Agent Runtime or application code in this step.
- Do NOT add model providers, llama.cpp, MCP, Graphiti, vector DBs, embeddings, or other heavy infra.
- Do NOT create new top-level application directories (apps/, packages/, core/, etc.) at this repository-prep stage.
- Keep all Claude Code developer configuration local and untracked.

Local tooling expectations
- Python 3.12 is the target development runtime.
- Use uv for environment management when implementing code later.
- Use pytest for tests and ruff for linting/formatting.
- Tests must be deterministic and runnable on modest hardware.
- FakeModel and MockTools will be permanent test fixtures in future slices (but not implemented now).

If you need to change repository settings or create branch protection rules, ask the project maintainer (JackBehindWood) first.

Usage
- This CLAUDE.md is a local instruction file for Claude Code and should remain untracked. Add it to .gitignore locally (the project .gitignore will be updated to list CLAUDE.md).
- For any development work, run uv install -d, uv run ruff check ., uv run pytest.

Contact / notes
- This file is local-only. To modify public repository docs or architecture, propose a small PR with clear rationale.

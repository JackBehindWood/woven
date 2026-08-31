Tests

This repository follows a deterministic-first testing philosophy. Tests should be reliable on modest hardware and avoid nondeterministic dependencies.

Structure

- `tests/unit/` — all current tests. Fully deterministic and offline; every model/tool/context dependency is faked (e.g. `FakeModel`, `MockTools`, `_FakeGenaiClient` for `GeminiProvider`).
- `tests/integration/` — tests marked `pytest.mark.integration`, excluded by default and run only via `uv run pytest -m integration`. See `tests/integration/README.md` for the rules. Currently empty aside from its README: there is no non-billed integration scenario to test yet.
- `tests/conftest.py` — an autouse fixture that isolates `XDG_CONFIG_HOME` and clears provider API-key env vars for every test in both subtrees, so no test can touch the developer's real `~/.config/woven/`.

Key points

- Prefer deterministic unit tests that don't require external model providers.
- **No test in this suite — unit or integration, gated or not — may call a real, billed third-party model API** (Gemini, Claude, OpenAI, or any other paid provider). This is a hard, explicitly-decided constraint; see `.claude/plans/roadmap.md`'s "Resolved cross-cutting decisions". Manual live verification against a real provider belongs in `examples/gemini_repl.py`, which pytest never collects.
- `uv run pytest` runs only `tests/unit/`-style tests (integration excluded by default via `addopts` in `pyproject.toml`) — fast, deterministic, fully offline.
- `uv run pytest -m integration` opts into `tests/integration/`.

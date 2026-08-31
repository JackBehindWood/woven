# Integration tests

Tests here are marked `pytest.mark.integration` and excluded by default
(`addopts = "-m 'not integration'"` in `pyproject.toml`). Run them explicitly
with:

```
uv run pytest -m integration
```

**Hard rule: no test under this marker may call a real, billed third-party
model API — Gemini, Claude, OpenAI, or any other paid provider — gated or
not, opt-in or not.** This was explicitly decided by the project owner (see
`.claude/plans/roadmap.md`'s "Resolved cross-cutting decisions") after an
earlier `RUN_LIVE_MODEL_TESTS=1`-gated live-Gemini test was removed for
exactly this reason. Manual live verification against a real provider lives
in `examples/gemini_repl.py`, which is not collected by pytest at all.

This directory is currently empty aside from this README — there is no
free/local integration scenario to test yet. It becomes real once one
exists, for example: real local `llama.cpp` inference
(`.claude/plans/local-inference.md`), or a multi-component runtime path that
makes no network calls.

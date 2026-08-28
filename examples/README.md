# Examples

Loose, runnable scripts for interactive/manual exploration — trying a
provider or a prompt by hand. Not a sub-project: `uv run examples/<script>.py`
runs directly against the repo's own environment, since example scripts only
need dependencies the core package already carries (e.g. `google-genai`).

This is **not** the place to grow ad hoc "is my config working" or "can I
reach Gemini" checks — that surface is `woven doctor`
(`.claude/plans/setup-and-diagnostics.md`), which will have a proper
status/message/suggested-fix structure. `sandbox_gemini.py` predates
`doctor` and does more than a connectivity check (REPL, `--context`,
`--prompt`); it's precedent, not a pattern to extend toward diagnostics.

## Secret convention

Every example script loads `examples/.env` (copy `examples/.env.example`)
via a small `_load_dotenv` helper and reads the provider's API key from
`os.environ[PROVIDER_ENV_VARS["<provider>"]]` — never
`resolve_api_key(FileSecretStore(), ...)` (that reads/writes the
developer's real `~/.config/woven/secrets.json`), and never a bespoke
hardcoded env var name. `PROVIDER_ENV_VARS` (from `woven.settings`) is the
one primitive shared with the CLI/`doctor` side — the env var *name* for a
provider stays canonical everywhere; how it gets populated deliberately
diverges: the real CLI persists through `FileSecretStore`, examples
populate it locally from `examples/.env`. A `GEMINI_API_KEY` already set in
the process environment always wins over `.env`.

`examples/.env` is gitignored; `examples/.env.example` is the tracked
template.

## Thresholds for growing this directory

- **Shared boilerplate:** `sandbox_gemini.py`'s `_load_context`/argparse
  scaffolding is fine to duplicate once. If a second example script needs
  the same boilerplate, extract it into `examples/_common.py` at that
  point — not before.
- **Sub-project:** graduate `examples/` to its own `pyproject.toml` only
  when it needs a dependency the core package doesn't already carry (e.g.
  a heavy local-inference example needing `llama-cpp-python`).

## Sandbox project environment (Future Consideration)

We plan to introduce a local sandboxing boundary to isolate exploratory `examples/` execution from host filesystem state and sensitive local credentials.

- **Objective & Isolation Boundary:** Prevent scripts, provider clients, and unvetted prompts from reading or modifying host files outside the designated workspace (e.g., via containerisation or process-level directory restrictions).
- **Settings & Credential Safety:** 
  - Woven resolves persistent credentials via `FileSecretStore` in `~/.config/woven/secrets.json` (enforcing strict `0600`/`0700` file permissions) or process environment variables.
  - Sandbox scripts read local keys via `examples/.env` and the shared `PROVIDER_ENV_VARS` mapping. A true sandbox boundary guarantees that running exploratory code never mutates or exposes host settings in `~/.config/woven/`.
- **Git Leak Prevention:**
  - `examples/.env` is gitignored by default, with `examples/.env.example` acting as the tracked template.
  - Example scripts load credentials through `_load_dotenv` and standard `os.environ` lookups, never through hardcoded strings or custom env file names, ensuring local API keys are never committed or pushed to remote repositories.
- **Guided Onboarding vs. Exploration (`woven setup`):**
  - First-time API key configuration and defaults selection (e.g., default mode or provider) belong in `woven setup`, an interactive CLI presentation layer over the core settings primitives.
  - Sandbox scripts assume configuration is already complete or supplied via local `.env`—they are not an onboarding or setup surface, but we should probably add a way or example for this.
- **Operational Health Checks (`woven doctor`):**
  - Sandbox scripts are designed strictly for manual experimentation (REPLs, prompt testing), **not** for growing ad-hoc environment or connectivity checks.
  - Diagnostic tasks—such as checking `~/.config/woven/` file permissions, verifying API key resolution, or testing provider reachability—belong exclusively in `woven doctor` (`.claude/plans/setup-and-diagnostics.md`), which outputs structured statuses and actionable fixes.
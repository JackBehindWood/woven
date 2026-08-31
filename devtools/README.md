# devtools

Developer-only playgrounds, manual verification, and repo-local secrets —
not a sub-project. `uv run devtools/<script>.py` runs directly against the
repo's own environment, since dev scripts only need dependencies the core
package already carries (e.g. `google-genai`).

This is **not** the place to grow ad hoc "is my config working" or "can I
reach Gemini" checks — that surface is `woven doctor`
(`.claude/plans/setup-and-diagnostics.md`), which has a proper
status/message/suggested-fix structure. `gemini_repl.py` predates `doctor`
and does more than a connectivity check (REPL, `--context`, `--prompt`);
it's precedent, not a pattern to extend toward diagnostics.

See `../examples/README.md` for the public-facing counterpart to this
directory, and how the two are meant to differ.

## Secret convention

`gemini_repl.py` loads `devtools/.env` (copy `devtools/.env.example`) via a
small `_load_dotenv` helper and reads the provider's API key from
`os.environ[PROVIDER_ENV_VARS["<provider>"]]` — never
`resolve_api_key(FileSecretStore(), ...)` (that reads/writes the
developer's real `~/.config/woven/secrets.json`), and never a bespoke
hardcoded env var name. `PROVIDER_ENV_VARS` (from `woven.settings`) is the
one primitive shared with the CLI/`doctor` side — the env var *name* for a
provider stays canonical everywhere; how it gets populated deliberately
diverges: the real CLI persists through `FileSecretStore`, dev scripts here
populate it locally from `devtools/.env`. A `GEMINI_API_KEY` already set in
the process environment always wins over `.env`.

`devtools/.env` is gitignored; `devtools/.env.example` is the tracked
template.

This local-`.env` convention is deliberately **devtools-only**. Public
`examples/` scripts must not depend on it — see `../examples/README.md`'s
configuration rule.

## Thresholds for growing this directory

- **Shared boilerplate:** `gemini_repl.py`'s `_load_context`/argparse
  scaffolding is fine to duplicate once. If a second script needs the same
  boilerplate, extract it into `devtools/_common.py` at that point — not
  before.
- **Sub-project:** graduate `devtools/` to its own `pyproject.toml` only
  when it needs a dependency the core package doesn't already carry (e.g.
  a heavy local-inference experiment needing `llama-cpp-python`).
- **`devtools/experiments/<topic>/`:** create it the first time a
  multi-file exploratory prototype outgrows a single script — not before.
- **`devtools/fixtures/<name>/`:** create it the first time manual
  experimentation needs a larger sample repository/workspace than a
  deterministic `tests/fixtures/` entry would ever need — not before. See
  `tests/README.md` for the deterministic, automated-test counterpart to
  this.

## Container sandbox

See [`container/README.md`](container/README.md) for how to run dev scripts,
`woven` commands, or `pytest` inside the project's container-based sandbox
instead of against your real host state.

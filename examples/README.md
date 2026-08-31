# Examples

Loose, runnable scripts for interactive/manual exploration — trying a
provider or a prompt by hand. Not a sub-project: `uv run examples/<script>.py`
runs directly against the repo's own environment, since example scripts only
need dependencies the core package already carries (e.g. `google-genai`).

This is **not** the place to grow ad hoc "is my config working" or "can I
reach Gemini" checks — that surface is `woven doctor`
(`.claude/plans/setup-and-diagnostics.md`), which will have a proper
status/message/suggested-fix structure. `gemini_repl.py` predates
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

- **Shared boilerplate:** `gemini_repl.py`'s `_load_context`/argparse
  scaffolding is fine to duplicate once. If a second example script needs
  the same boilerplate, extract it into `examples/_common.py` at that
  point — not before.
- **Sub-project:** graduate `examples/` to its own `pyproject.toml` only
  when it needs a dependency the core package doesn't already carry (e.g.
  a heavy local-inference example needing `llama-cpp-python`).

## Sandbox project environment

`Dockerfile` + `docker-compose.yml` at the repo root run `woven setup`,
`woven chat`, `gemini_repl.py`, or `pytest` inside a container instead of
against your real host state. `src/woven/sandbox/` (`Sandbox` protocol,
`ContainerSandbox` implementation) is the Python-facing primitive behind it;
see `docs/architecture/sandbox-environment.md` for the full design. This is
orthogonal to `woven doctor`/pytest's existing isolation (`tests/conftest.py`'s
`XDG_CONFIG_HOME` fixture) — it's a manual boundary a developer opts into,
not a place to grow diagnostics.

**What's isolated, precisely** — three separate claims, not one blurred
"sandboxed" claim:

- **Config/secrets: yes.** `XDG_CONFIG_HOME` is container-local
  (`/home/sandbox/.config`); the container never mounts your real
  `~/.config/woven`.
- **Filesystem: no.** The repo is bind-mounted read-write at `/app` — code
  running inside can modify tracked and untracked files exactly like
  running locally. This is not a filesystem sandbox.
- **Network: no.** Default Docker networking permits outbound calls;
  nothing here adds a network policy. What actually prevents an accidental
  real Gemini call is that `docker-compose.yml` doesn't pass host env vars
  through, so no real API key reaches the container unless you opt into
  the `examples/.env` mount below — credential absence, not network
  isolation.

**Install the engine (one-time, per machine):**

Any Docker-API-compatible engine works; these are the two known-good, tested
paths — pick one:

```sh
# colima (CLI-only, recommended for headless/CI-like use — no GUI app)
brew install colima docker docker-compose
mkdir -p ~/.docker && cat > ~/.docker/config.json <<'EOF'
{
  "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]
}
EOF
colima start --cpu 2 --memory 2 --disk 20
```

```sh
# OrbStack (GUI app, less manual setup, brew cask)
brew install --cask orbstack
open -a OrbStack   # one-time: launch once to finish setup
```

Either way, verify it worked before building:

```sh
docker info    # should reach a Server section, not a connection error
docker compose version
```

The `~/.docker/config.json` step is only needed for colima — the
`docker-compose` Homebrew formula installs the `docker compose` CLI plugin
outside Docker's default plugin search path, so Docker won't find it
without this. OrbStack ships its own Docker Desktop-compatible CLI and
plugin wiring, so it needs no equivalent step.

Sized `--cpu 2 --memory 2` deliberately, matching this repo's 8GB M3 Air
floor — colima's un-sized default is also 2 CPU/2GiB, but pass the flags
explicitly so the sizing is visible and intentional rather than incidental.

**Build:**

```sh
docker compose build
```

**Run:**

```sh
docker compose run --rm sandbox uv run woven setup
docker compose run --rm sandbox uv run woven chat
docker compose run --rm sandbox uv run python examples/gemini_repl.py
docker compose run --rm sandbox uv run pytest
```

Each run is ephemeral (`--rm`, no named volume) — no state, including
`XDG_CONFIG_HOME`'s contents, persists between runs. Revisit this if it
proves annoying for iterative manual testing.

To let a sandboxed run reach a real provider (e.g. for `gemini_repl.py`),
uncomment the `examples/.env` mount in `docker-compose.yml` — it stays
commented by default since Compose has no "mount if exists".

Recommend [OrbStack](https://orbstack.dev/) or
[colima](https://github.com/abiosoft/colima) over Docker Desktop on an 8GB
M3 Air: both use Apple's Virtualization.framework and idle at a fraction of
Docker Desktop's RAM.

Note: the `Dockerfile`'s default `CMD` runs `uv sync --all-extras` on every
`docker compose run` invocation, which adds real, multi-second latency to
each command — not just hypothetically. If that proves too slow in
practice, simplify the `CMD` to a plain shell and run `uv sync` once
per container lifetime instead.
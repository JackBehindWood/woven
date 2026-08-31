# Container sandbox — developer usage

**Scope of this file:** developer documentation and manual workflows only.
This is not a second owner of the Docker/Compose configuration — that lives
at the repo root (`Dockerfile`, `docker-compose.yml`, `.dockerignore`) — and
not a second owner of the runtime sandbox implementation — that's
`src/woven/sandbox/` (`Sandbox` protocol, `ContainerSandbox`). This file
documents how to use those; it doesn't define or duplicate them. See
`docs/architecture/sandbox-environment.md` for the full design, including
the authoritative "what's isolated, precisely" breakdown.

`Dockerfile` + `docker-compose.yml` at the repo root run `woven setup`,
`woven chat`, `devtools/gemini_repl.py`, or `pytest` inside a container
instead of against your real host state. This is orthogonal to
`woven doctor`/pytest's existing isolation (`tests/conftest.py`'s
`XDG_CONFIG_HOME` fixture) — it's a manual boundary a developer opts into,
not a place to grow diagnostics.

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
docker compose run --rm sandbox uv run python devtools/gemini_repl.py
docker compose run --rm sandbox uv run pytest
```

Each run is `--rm` (the container itself is thrown away), but `XDG_CONFIG_HOME`
(`/home/sandbox/.config`) persists across runs via the named
`woven-sandbox-config` volume — so `woven setup` inside the sandbox sticks
between invocations, the same way it would on a real machine, while still
never touching your real host `~/.config/woven` (a Docker-managed volume,
not a bind mount — completely separate from host state).

**Reset to a clean slate manually** when you want one, rather than getting
it automatically on every run:

```sh
docker compose down -v   # removes the sandbox-config volume (and any others)
# or, to remove just the config volume by name:
docker volume rm woven-sandbox-config
```

To let a sandboxed run reach a real provider (e.g. for `gemini_repl.py`),
uncomment the `devtools/.env` mount in `docker-compose.yml` — it stays
commented by default since Compose has no "mount if exists".

Recommend [OrbStack](https://orbstack.dev/) or
[colima](https://github.com/abiosoft/colima) over Docker Desktop on an 8GB
M3 Air: both use Apple's Virtualization.framework and idle at a fraction of
Docker Desktop's RAM.

Note: the `Dockerfile`'s `ENTRYPOINT` runs `uv sync --all-extras` before
every command, including ones passed via `docker compose run sandbox
<command>` — this has to be `ENTRYPOINT`, not `CMD`, because `run`'s command
override replaces `CMD` outright, which would otherwise skip the sync and
leave `uv run <cmd>`'s own implicit sync to install only the base
dependency group (no `cli`/`dev` extras — e.g. `typer` missing from `woven
--help`). This adds real, multi-second latency to each invocation, not just
hypothetically. If that proves too slow in practice, revisit whether the
sync belongs in `ENTRYPOINT` at all versus running `uv sync` once manually
per container lifetime.

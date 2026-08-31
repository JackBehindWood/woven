# Sandbox environment architecture

This document is the durable, committed reference for Woven's isolation boundary — `src/woven/sandbox/` plus the `Dockerfile`/`docker-compose.yml` at the repo root. It complements `examples/README.md`, which carries the `docker compose` usage recipes.

Where this document says "current implementation," it describes code that exists today. Where it says "future," it describes direction only.

## Purpose

Ordinary `woven setup`/`woven chat` usage, and `examples/gemini_repl.py`, all read/write the real `~/.config/woven` and can make real provider network calls — unlike `pytest`, already isolated via `tests/conftest.py`'s `XDG_CONFIG_HOME` autouse fixture. `.claude/plans/sandbox-environment.md` (roadmap item 4, sequenced directly before `real-tools.md`) closes that gap with a single container-based isolation boundary, decided to serve two purposes at once: dev/test isolation today, and the execution boundary `real-tools.md`'s future shell/file `Tool` implementations will run inside.

## Position in the architecture

`src/woven/sandbox/` is a runtime-level, zero-client-dependency package — matching `src/woven/{tools,permissions,context}/`'s existing granularity — not a CLI-only helper. `Sandbox` is a general execution/isolation `Protocol`; `ContainerSandbox` is its only implementation today, backed by `docker compose run --rm`. A future host-process executor or remote execution backend could satisfy the same `Protocol`, but neither is built here — no current caller needs one.

The container definition (`Dockerfile`, `docker-compose.yml`, `.dockerignore`) lives at the repo root — ordinary tooling config, the same class of file as `.pre-commit-config.yaml`, not a new top-level app dir.

## `src/woven/sandbox/`

**Current implementation** (`protocol.py`):

```python
class SandboxError(Exception):
    """Raised when a Sandbox implementation cannot execute a command at all."""

class SandboxRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    command: Sequence[str]
    cwd: str | None = None
    timeout: float | None = None

class SandboxResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False

@runtime_checkable
class Sandbox(Protocol):
    def run(self, request: SandboxRequest) -> SandboxResult: ...
```

Matches every other `Protocol` in the repo (`Tool.execute`, `Context.retrieve`, `Model.generate`, `ApprovalPolicy.evaluate`): one sync method, one frozen Pydantic request in, one frozen result out. Deliberately omits the `purpose: str` field every other `*Request` carries — that field exists to justify a call to an `ApprovalPolicy`/for event text, and `Sandbox` isn't a decision point in this slice (not wired into `Tool`/`ApprovalPolicy` yet). Also skips env vars, network policy, resource limits, and execution IDs — no caller in this slice needs them.

A timed-out command is represented as data (`timed_out=True, exit_code=None`), not an exception — consistent with a non-zero exit code also being a normal `SandboxResult`, not an exception. `exit_code` is `None` rather than borrowing GNU `timeout`'s `124` convention, since no process actually exited.

**`container.py`** — `ContainerSandbox(compose_file: Path | None = None, service: str = "sandbox")`, `compose_file` defaulting to the repo-root `docker-compose.yml`:

- `.run(request)`: if `request.cwd` is absolute, raises `SandboxError` immediately rather than silently mis-mapping a host path. A relative `cwd` maps to `/app/{cwd}` (the compose file's mount point) via a `--workdir` flag. Shells out to `docker compose -f <compose_file> run --rm [--workdir /app/<cwd>] <service> <command...>` via `subprocess.run(capture_output=True, text=True, check=False, timeout=request.timeout)`.
- `subprocess.TimeoutExpired` → `SandboxResult(exit_code=None, timed_out=True, ...)`, not raised.
- `FileNotFoundError` (no `docker` binary) → re-raised as `SandboxError` pointing at `examples/README.md`'s OrbStack/colima recommendation.

**Path contract:** `SandboxRequest.cwd` is always workspace-relative, never a host absolute path — the host repo root and the container's mount point (`/app`) are different paths, so forwarding a host path straight through would silently resolve to the wrong directory or fail. `ContainerSandbox` has exactly one mount point, fixed in `docker-compose.yml`, so it does the relative→`/app/…` join itself; no general host↔container path-mapping object exists, since there is only one implementation and one mapping today.

**`__init__.py`** re-exports `Sandbox`, `SandboxError`, `SandboxRequest`, `SandboxResult`, `ContainerSandbox`.

Not wired into `runtime/core.py`'s hardcoded exception tuple (`ModelError, ToolError, ContextError, ApprovalDenied, WorkflowError`) — `Sandbox` isn't called from inside `Workflow` in this slice, so `SandboxError` isn't reachable from `AgentRuntime.run_turn` yet. Not wired into any `Tool`, `ApprovalPolicy`, or CLI command either — all of `real-tools.md`'s job.

## Container definition (repo root)

**`Dockerfile`** — `python:3.12-slim` base; `uv` installed via the static binary from `ghcr.io/astral-sh/uv` (no network call during build beyond the layer pull itself); non-root `sandbox` user (uid 1000) owning `/app`; `XDG_CONFIG_HOME=/home/sandbox/.config` (container-local, never the host's `~/.config`); no `COPY` of repo source — code arrives via the bind mount at run time, so a code edit never requires an image rebuild, only a `pyproject.toml`/`Dockerfile` change does. Default `CMD` runs `uv sync --all-extras` then drops to a shell, so `docker compose run --rm sandbox <command>` works after a fresh mount with no separate provisioning step.

**`docker-compose.yml`** — one `sandbox` service: `build: .`, repo root bind-mounted read-write at `/app`, a commented-out (opt-in) `examples/.env` mount, no host environment pass-through and no named volumes — state, including `XDG_CONFIG_HOME`'s contents, lives only inside the ephemeral container filesystem.

**`.dockerignore`** mirrors `.gitignore`'s build-artifact/cache entries.

## What's isolated, precisely

Three separate claims, not one blurred "sandboxed" claim — see `examples/README.md` for the developer-facing version of the same breakdown:

- **Config/secrets: yes** — container-local `XDG_CONFIG_HOME`, no mount of host `~/.config/woven`.
- **Filesystem: no** — the repo is bind-mounted read-write at `/app`; code running inside can modify tracked and untracked files exactly like running locally. This is not a filesystem sandbox.
- **Network: no** — default Docker networking permits outbound calls; nothing here adds a network policy. What actually prevents an accidental real provider call is that `docker-compose.yml` doesn't pass host env vars through, so no real API key reaches the container unless a developer opts into the `examples/.env` mount — credential absence, not network isolation.

## Testing

`tests/unit/test_container_sandbox.py` mocks `subprocess.run` (monkeypatch) — no real container engine is touched, keeping `uv sync && uv run pytest` fully independent of Docker being installed: expected argv construction, relative `cwd` → `--workdir` flag, absolute `cwd` → `SandboxError` without calling `subprocess.run`, non-zero exit code as a normal result, `TimeoutExpired` → `timed_out=True` result, and `FileNotFoundError` → `SandboxError`.

A manual smoke test (`docker compose build && docker compose run --rm sandbox uv run pytest`) verifies the real container path when OrbStack/colima is available locally — not part of CI.

## Explicitly out of scope (this slice)

- `Sandbox`/`ContainerSandbox` are not reachable from `AgentRuntime`/`Workflow` yet — not wired into any `Tool`, not in `runtime/core.py`'s exception tuple. For whoever picks up `real-tools.md` next: this is the first thing to change there, not something to rediscover by grepping.
- Whether shell/file `Tool`s will *require* a running container once `real-tools.md` ships (fail closed vs. fall back to host execution) — deferred to that item's own planning pass.
- Whether this item's real isolation makes `real-tools.md`'s pattern-matching-hardening fork moot, or still worth doing as defense in depth — same deferral.
- CI and `pytest` are untouched — `tests/conftest.py`'s `XDG_CONFIG_HOME` autouse fixture remains the pytest isolation mechanism; the container is a manual `docker compose run` a developer reaches for, not a gate.

## Current implementation vs. future work

| Concept | Status |
|---|---|
| `Sandbox` protocol, `SandboxRequest`/`SandboxResult` (`src/woven/sandbox/protocol.py`) | Implemented |
| `ContainerSandbox` (`src/woven/sandbox/container.py`) | Implemented |
| `Dockerfile` / `docker-compose.yml` / `.dockerignore` (repo root) | Implemented |
| `examples/README.md` sandbox usage docs | Implemented |
| Wiring `Sandbox` into a real `Tool` / `ApprovalPolicy` / `runtime/core.py`'s exception tuple | Not implemented — `.claude/plans/real-tools.md` |
| Host-process or remote execution backend satisfying `Sandbox` | Not implemented — no current caller needs one |
| Resource limits, network policy, env var passthrough on `SandboxRequest` | Not implemented — no current caller needs them |

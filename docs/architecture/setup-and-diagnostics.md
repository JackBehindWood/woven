# Setup & diagnostics architecture

This document is the durable, committed reference for Woven's guided-setup and diagnostics subsystems — `src/woven/setup/` and `src/woven/diagnostics/`. It complements `docs/architecture/user-settings.md` (the config/secrets primitives both build on) and `docs/clients/cli.md` (the CLI's presentation of them via `woven setup`/`woven doctor`).

Where this document says "current implementation," it describes code that exists today. Where it says "future," it describes direction only.

## Purpose

`user-settings.md` shipped a persisted `User`/`Settings`/`SecretStore`, and `model-providers.md` shipped a real `GeminiProvider`, but neither gave users a guided way to configure Woven or a way to tell *why* it isn't working — a user had to already know `woven settings set gemini-api-key <value>` exists, and a bad key or unreachable provider failed with whatever raw error the Gemini client raised. `.claude/plans/setup-and-diagnostics.md` (roadmap item 3, sequenced directly after `model-providers.md`) closes both gaps: `woven setup` (guided config) and `woven doctor` (structured diagnostics).

## Position in the architecture

`src/woven/setup/` and `src/woven/diagnostics/` are runtime-level, zero-client-dependency packages — matching `src/woven/settings/`'s own precedent — not CLI-only helpers. Both are a presentation layer's *backend*, not the presentation itself: `src/woven/client/cli/setup_command.py`/`doctor_command.py` do the prompting/rendering; the two runtime packages hold the logic that decides what to persist and what to check. This keeps the same checks reusable by a future non-CLI client's health screen, the same way `AgentRuntime.run_turn` already backs every client's chat turn.

Neither package introduces a parallel config-access path — both are thin wrappers over `src/woven/settings/`'s existing `SecretStore`, `resolve_api_key`, `load_config`/`save_config`.

## `Provider.check_connection()`

See `docs/architecture/agent-runtime.md`'s Provider protocol / GeminiProvider sections for the full design — summarized here for context: `Provider` gained a `check_connection() -> None` method (raises `ModelError` on failure), the first real hook on that protocol. `GeminiProvider` implements it via a cheap metadata call (`client.models.get(model=self.model_id)`, not `generate()`), differentiates failure causes (invalid key / rate-limited / service unavailable / network-unreachable) into distinct messages, and exposes `SETUP_HINT: ClassVar[str]` so `woven setup` can print "how to get a key" before an instance (or even a key) exists. `MODEL_PROVIDERS` changed shape from a `dict[str, Callable[[str], Model]]` of wrapping lambdas to `dict[str, type[Model]]` storing the provider class directly, which is what makes `MODEL_PROVIDERS[name].SETUP_HINT` reachable pre-instantiation.

## `src/woven/setup/`

**Current implementation:**

- `fields.py` — `FIELDS: dict[str, tuple[str, Callable[[str], str | None]]]`, mapping a CLI field name (`mode`, `permission-mode`, `model-provider`) to its `Settings` attribute and validator. This is the single source of truth: `woven settings set` (`settings_command.py`) and `woven setup` both import from here rather than each keeping their own copy — the three validators used to live private to `settings_command.py` before this package existed.
- `service.py` — `SetupService`, constructor-injectable (`secret_store`, `load_config`, `save_config`, matching `GeminiProvider(client=...)`'s/`SessionState.secret_store`'s existing DI precedent):
  - `.current_config() -> Config`
  - `.set_field(field: str, value: str) -> Config` — validates via `FIELDS`, persists via `model_copy` + `save_config`, raises `SetupError` on an unknown field or invalid value.
  - `.set_secret(provider: str, value: str) -> None` — validates `provider` is a known key in `PROVIDER_ENV_VARS`, then `secret_store.set(...)`.
  - `SetupError` — one exception type per module, matching `ConfigError`/`ModelError`/`ToolError`.

`secret_store` defaults to `None` and falls back to `FileSecretStore()` inside `__init__` (`secret_store or FileSecretStore()`), not a bare `= FileSecretStore()` default value — a literal default would be constructed once, at module-import time, before any per-test `XDG_CONFIG_HOME` override takes effect, silently sharing one real `FileSecretStore` across every `SetupService()` call site. `SessionState.secret_store`'s existing `field(default_factory=FileSecretStore)` sidesteps the same trap; `SetupService` uses the equivalent `or`-guard idiom since it's a plain `__init__`, not a dataclass field.

## `src/woven/diagnostics/`

**Current implementation** (`service.py`):

```python
class CheckStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"

@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    status: CheckStatus
    message: str
    fix_hint: str | None = None
```

`DiagnosticService` (constructor-injectable: `secret_store`, `load_config`, `model_providers`, defaulting to the real `MODEL_PROVIDERS`) exposes one method per check category, plus `.run_all()`:

- `.check_environment()` — `config_dir()`/`config_path()` are readable/writable at the expected `0o700`/`0o600` permissions; `FAIL` naming the specific problem otherwise.
- `.check_dependencies()` — attempts `import google.genai`; `ImportError` → `FAIL` with a fix hint to re-run `uv sync`, catching a broken/incomplete install before it surfaces as a confusing failure elsewhere.
- `.check_config_validity()` — one `DiagnosticCheck` per settings field (`mode`, `permission-mode`, `model-provider`): still a member of `BUILTIN_MODES`/`PERMISSION_MODES`/`MODEL_PROVIDERS`? `WARN` per stale field, naming it and the current valid set — catches config drift after an upgrade renames/removes a mode, permission tier, or provider.
- `.check_credentials()` — one check per provider in `PROVIDER_ENV_VARS`: does `resolve_api_key` find a value? `WARN` with a fix hint naming that provider's `SETUP_HINT` plus `woven setup`/`woven settings set <provider>-api-key` if not.
- `.check_provider_reachable()` — reads `config.settings.default_model_provider`. No default → `WARN`. A default with no resolvable key → `FAIL`. Otherwise builds the model via `MODEL_PROVIDERS[provider](api_key=api_key)` and calls `.check_connection()`: success → `OK`, `ModelError` → `FAIL` with the cause-specific error text as the fix hint. This is the *only* check that makes a real (cheap) network call, and only once a provider and key are both actually configured — never during a `WARN` path.
- `.run_all() -> list[DiagnosticCheck]` — all of the above, in a fixed order: environment, dependencies, config validity (3 checks), credentials (1 per provider), provider (1). This flat list is exactly what both CLI output modes below render from, unchanged — the concrete proof that the check-list is reusable outside the CLI's own rendering.

## CLI integration

**`woven setup`** (`src/woven/client/cli/setup_command.py`) — a guided flow, each answer persisted immediately (matching `settings set`'s immediate-persistence semantics, no pending/transaction state):

1. Show current settings.
2. Prompt for a default model provider from `MODEL_PROVIDERS` (blank → stays on `FakeModel`); every prompt shows the currently-persisted value as its `typer.prompt` default, so a bare re-run reflects prior answers instead of starting blank.
3. If a provider was chosen: print its `SETUP_HINT`, prompt for the key (`hide_input=True`) via `SetupService.set_secret`, then validate immediately by constructing the provider and calling `.check_connection()` — on failure, show the (now cause-specific) message and re-prompt, up to 3 attempts, before giving up with a pointer to re-run `woven setup` later. The provider is still saved as the default even if the key never validates — `woven doctor`'s provider-reachability check is exactly the surface for catching that afterward.
4. Prompt for default mode from `BUILTIN_MODES`.
5. Prompt for default permission tier from `PERMISSION_MODES`.
6. Offer (`typer.confirm`) to run the full `woven doctor` check-list immediately, rendered the same way `woven doctor` renders it.

**`woven doctor`** (`src/woven/client/cli/doctor_command.py`) — calls `DiagnosticService().run_all()`:

- Default output: `render_diagnostics()` (`render.py`) — one colored line per check (✓/!/✗ via the existing `woven.success`/`woven.warning`/`woven.error` theme styles), a `fix:` line under any check that has one, and a summary line (`N ok, N warn, N fail`).
- `--json`: the same `DiagnosticCheck` list, `json.dumps(asdict(check) ...)` — for scripting/CI use, and the concrete proof the check-list is reusable outside the CLI's own rendering.
- Exit code `1` if any check is `FAIL`, else `0`, in both output modes.

Both commands are wired onto `app` via the cross-module command registry (`src/woven/client/cli/registry.py`) rather than a manual `app.command(...)` call in `app.py` — see `docs/clients/cli.md`'s "Top-level commands and the registry" section for that mechanism; it's a CLI wiring detail, not part of either runtime package's own design.

`PERMISSION_MODES` — previously `_PERMISSION_MODES`, private to `app.py` — moved to `src/woven/permissions/__init__.py` as part of this work, alongside `ApprovalPolicy`/`AutoApprovalPolicy`, so `woven.setup.fields` (a runtime-level package) could validate against it without importing a client module. `app.py` and `settings_command.py` import the moved constant instead of redefining or reaching into `app.py`.

## Testing

- `tests/unit/test_gemini_model.py` — `check_connection()`'s differentiated-message branches (including the real-world 400/`INVALID_ARGUMENT` "API key not valid" shape, not just synthetic 401/403), the network-error branch on both `generate()` and `check_connection()`, and `GeminiProvider.SETUP_HINT`.
- `tests/unit/test_setup_service.py` — field validation, `set_field` success/failure, `set_secret`, persistence round-trip.
- `tests/unit/test_diagnostic_service.py` — each check category, using a fake `Provider` double whose `check_connection()` raises or doesn't; never a real network call (this project's standing rule). Includes a test asserting no check makes a network call when nothing is configured.
- `tests/unit/test_cli_setup.py` — `CliRunner` with scripted `input=` sequences: a fresh run, a re-run showing prior values as defaults, the key-validation retry-then-succeed and retry-then-give-up paths, and declining/accepting the closing "run doctor now?" offer.
- `tests/unit/test_cli_doctor.py` — the clean-config exit-0 path, a `FAIL`-injected exit-1 path, and `--json` output parsing as valid JSON.

## Explicitly out of scope (this slice)

- Project-local `.env` support for `resolve_api_key` — deferred to `.claude/plans/projects.md`, which already owns project-scoped credentials.
- Sandbox containerization / isolation-boundary concerns raised alongside this work — no roadmap item covers them yet; a separate `.claude/plans/sandbox-environment.md` would need its own planning pass.
- Any provider usage-rate/quota-limit surface — Gemini's API has no queryable "remaining quota" endpoint today, and summarizing per-call `usage_metadata` needs turn/run history that doesn't exist yet (`.claude/plans/persistence.md`).
- `SetupService.set_field("model-provider", "")` (clearing a configured default back to "no provider") — the guided flow only ever sets a non-empty provider; clearing one isn't exposed by either `woven setup` or `woven settings set` today.

## Current implementation vs. future work

| Concept | Status |
|---|---|
| `Provider.check_connection()`, cause-specific error messages | Implemented (`src/woven/models/providers/gemini.py`) |
| `GeminiProvider.SETUP_HINT` | Implemented |
| `MODEL_PROVIDERS: dict[str, type[Model]]` (class registry, not lambdas) | Implemented |
| `PERMISSION_MODES` at `woven.permissions` (moved from `app.py`) | Implemented |
| `src/woven/setup/` (`FIELDS`, `SetupService`, `SetupError`) | Implemented |
| `src/woven/diagnostics/` (`DiagnosticCheck`, `CheckStatus`, `DiagnosticService`) | Implemented |
| `woven setup` guided CLI command | Implemented |
| `woven doctor` CLI command, `--json` output | Implemented |
| Cross-module CLI command registry (`register_command`/`register_group`) | Implemented (`src/woven/client/cli/registry.py`) |
| Project-local `.env` as a credential source | Not implemented — `.claude/plans/projects.md` |
| Provider usage-rate/quota-limit diagnostics | Not implemented — blocked on `.claude/plans/persistence.md` |
| Clearing a configured default model provider back to "none" | Not implemented — no current demand |

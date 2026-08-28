# User & settings architecture

This document is the durable, committed reference for Woven's settings subsystem — `src/woven/settings/`. It complements `docs/architecture/agent-runtime.md` (the runtime itself) and `docs/clients/cli.md` (the CLI's consumption of this subsystem) by recording the persisted-config design and the reasoning behind it.

Where this document says "current implementation," it describes code that exists today. Where it says "future," it describes direction only.

## Purpose

Before this subsystem existed, the CLI's `/settings` command was a read-only, in-session-only view — nothing about a Woven session persisted across process invocations. `src/woven/settings/` is the first persistence anywhere in the project: a small, user-global config file holding one local `User` identity and one `Settings` record (default mode, default permission tier, a placeholder for a future default model provider), plus a physically separate secrets store for per-provider API keys.

This is deliberately **not** a full accounts/auth framework — see "Explicitly out of scope" below.

## Position in the architecture

`src/woven/settings/` is a leaf runtime package: it imports only `pydantic` and the standard library — no dependency on `woven.modes`, `woven.permissions`, or any client. This keeps mode/permission-tier *value* validation client-side (the CLI's `BUILTIN_MODES`/`_PERMISSION_MODES` checks), avoiding a dependency pointing the wrong direction and avoiding a second, potentially-drifting copy of those lists inside the settings package itself. It is usable and testable with zero clients installed, matching the "runtime is the product, clients are interfaces to it" principle.

## Data model

**Current implementation** (`src/woven/settings/models.py`):

```python
class User(BaseModel):
    id: str
    name: str


class Settings(BaseModel):
    default_mode: str = "chat"
    default_permission_mode: str = "guarded"
    default_model_provider: str | None = None


class Config(BaseModel):
    user: User
    settings: Settings
```

All three are frozen pydantic `BaseModel`s. `Settings`' field defaults double as the hardcoded fallback values — no separate constant is needed. `mode`/`permission_mode` are stored as plain `str`, not validated against `BUILTIN_MODES`/`_PERMISSION_MODES` at this layer (see "Position in the architecture" above) — validation happens where those enums already live, client-side.

A fixed schema was chosen over arbitrary key/value storage: the concrete set of settings needed today (mode, permission tier, model provider placeholder) is small and known, and a fixed schema keeps `load_config()`/`save_config()` simple pydantic round-trips rather than needing a separate validation layer for arbitrary keys.

API keys are **not** a `Settings` field — see "Secrets" below for why they live in a separate store.

## Storage

**Current implementation** (`src/woven/settings/store.py`):

- **Location:** `config_dir()` resolves to `$XDG_CONFIG_HOME/woven` if `XDG_CONFIG_HOME` is set, else `~/.config/woven` — user-global, not project-local, not a `.env` file. `config_path()` is `config_dir() / "config.json"`.
- **Permissions:** the config directory is created `0700` and the config file is written `0600` on every `save_config()` call, via `os.open(..., O_CREAT|O_WRONLY|O_TRUNC, 0o600)` rather than write-then-chmod — this closes the narrow window where a brand-new file would otherwise briefly exist at the OS-default umask permissions before being chmod'd. An explicit `chmod` still runs after the write, since `os.open`'s mode argument only applies to a file it actually creates — it does not change the permissions of a pre-existing file being overwritten, so the trailing `chmod` is what self-heals a file that had been loosened by something outside Woven. `load_config()` also self-heals a looser-than-`0600` file back to `0600` on every load (no error raised — just corrected).
- **First run:** `load_config()` on a missing config file constructs `Config(user=User(id=uuid4().hex, name="local"), settings=Settings())`, persists it via `save_config()`, and returns it — so the `User.id` is generated once and stays stable across every subsequent `load_config()` call (it's read back from the file, never regenerated).
- **Corrupt file:** `load_config()` and `save_config()` both raise `ConfigError` (not a bare exception) on unreadable/invalid-JSON reads or failed writes (disk full, permission denied). Callers (the CLI) catch this and render a client-appropriate error rather than letting a raw exception surface.
- **Legacy migration:** `load_config()` parses the raw JSON once before pydantic validation and checks for a pre-`SecretStore` `settings.gemini_api_key` key (the shape this subsystem shipped with initially). If present, it moves the value into `FileSecretStore` under `gemini_api_key` and re-saves `config.json` without it — a one-time, one-directional migration. Pydantic's default `extra="ignore"` behavior means an old file would not otherwise fail to load, but silently dropping a real secret on first load-after-upgrade would be worse than this small explicit step.

## Secrets

**Current implementation** (`src/woven/settings/secrets.py`):

API keys are physically separate from `config.json`'s ordinary settings — a deliberate response to the fact that `config.json` is the kind of file a user might reasonably paste into a bug report or back up in cleartext, while an API key should not be.

- **`SecretStore` protocol:** `get(key) -> str | None`, `set(key, value) -> None`, `delete(key) -> None`.
- **`FileSecretStore`:** the only current implementation, backed by `config_dir() / "secrets.json"`. Same `0700`/`0600` directory/file permissions and the same atomic-create-plus-self-healing-chmod write pattern as `config.json` (see "Storage" above). No OS keychain, no `keyring` dependency — this is a file-level separation of concerns, not a stronger-than-file-permissions security boundary. Revisit if/when the threat model changes.
- **Provider keying:** `PROVIDER_ENV_VARS: dict[str, str]` maps a provider name to its environment-variable override (currently `{"gemini": "GEMINI_API_KEY"}`); a provider's stored key lives under `f"{provider}_api_key"` in the secret store. This is a generalization from an earlier Gemini-specific `gemini_api_key` field, done now because the roadmap already anticipates more providers and reshaping the schema later would be more disruptive than generalizing it now.
- **`resolve_api_key(store, provider)`:** the environment variable for that provider wins if set, else the value from `store.get(f"{provider}_api_key")`, else `None`. The environment variable remains a fallback/override (useful for CI and quick local testing) — the secret store is the primary, persisted home for the key. This supersedes both the earlier "env var only, no config file" secrets stance recorded in `.claude/plans/model-providers.md` and the original single-field `resolve_gemini_api_key`.

## Runtime resolution

**Current implementation** (`src/woven/settings/resolve.py`):

`resolve_runtime_config(config, *, mode=None, permission_mode=None) -> RuntimeConfig` is a pure precedence-merge function: CLI-provided override wins, else the persisted `Settings` default, else the hardcoded field default already baked into `Settings`. `RuntimeConfig` (frozen pydantic: `mode`, `permission_mode`, `model_provider`) is the single shape both the CLI's session-start resolution and its `/settings` display now read from, replacing what used to be three inline lines duplicated across call sites. It does not validate `mode`/`permission_mode` against `BUILTIN_MODES`/`_PERMISSION_MODES` — that stays client-side, per "Position in the architecture" above. It has no project-layer awareness — none exists yet.

## Profile scope

Exactly one local `User` — no multi-profile support, no profile-switching surface. Multi-user/multi-profile support and real authorization are deliberately deferred to `.claude/plans/projects.md` (see the roadmap's sequencing notes for why that item is positioned late).

## CLI integration

**Current implementation** (`src/woven/client/cli/`):

- **`_run_chat`** (`app.py`) calls `load_config()`, then `resolve_runtime_config(config, mode=mode, permission_mode=permission_mode)` to merge any `--mode`/`--permission-mode` flags onto the persisted defaults (`chat()`'s typer options default to `None` rather than a hardcoded string, so `_run_chat` can distinguish "flag not passed" from "use the persisted default"). A `ConfigError` from either `load_config()` or a failed `save_config()` write is rendered and exits the process with code 1, mirroring the existing invalid-mode/invalid-permission-mode error pattern.
- **`SessionState`** carries `persisted_runtime: RuntimeConfig` (the *unresolved-by-CLI-flags* persisted defaults — a separate `resolve_runtime_config(config)` call with no overrides, computed once at session start purely for `/settings` display) and `secret_store: SecretStore` (a `FileSecretStore()`, constructed once alongside `load_config()`). Neither is mutated mid-session.
- **`woven settings show` / `woven settings set <field> [value]`** (`src/woven/client/cli/settings_command.py`, a `typer.Typer` sub-app mounted at `app.add_typer(settings_app, name="settings")`) is the out-of-session mutation surface `docs/clients/cli.md` had previously flagged as "not implemented, better justified once the CLI needs to remember anything across invocations" — that trigger has now arrived.
  - Known fields split into two tables: `_FIELDS` for plain `Settings` attributes (`mode` → `BUILTIN_MODES`, `permission-mode` → `_PERMISSION_MODES` imported from `app.py` rather than redefined so the two lists can't drift, `model-provider` → unvalidated) and `_SECRET_FIELDS`, generated from `PROVIDER_ENV_VARS` as `{"<provider>-api-key": "<provider>_api_key"}` — currently just `gemini-api-key`.
  - `show` renders the user id/name, every plain `Settings` field, and one `"<provider> api key: set|not set"` line per entry in `PROVIDER_ENV_VARS` (via `resolve_api_key`) — never the raw value.
  - `set <field> <value>` for a plain field behaves as before: validates, then writes via `config.model_copy(...)` + `save_config()`. For a secret field, `value` is optional — if omitted, it's collected via `typer.prompt(..., hide_input=True)` rather than a plain CLI argument, so the key doesn't land in shell history or become visible via `ps` while the value is being entered — then written via `FileSecretStore().set(...)`, never through `config.json`. Either path echoes `"(hidden)"` back for a secret field, never the raw value. An invalid field or a missing value for a plain field renders an error and exits 1 **without** touching the persisted file.
  - `_validate_permission_mode` imports `_PERMISSION_MODES` from `woven.client.cli.app` lazily (inside the function body, not at module scope) to avoid a circular import — `app.py` imports `settings_app` from `settings_command.py` at module scope, so `settings_command.py` cannot import back from `app.py` at module scope too.
- **The in-REPL `/settings` command** (`_handle_settings`, `app.py`) stays read-only — no new mutation path was added here, deliberately: `/mode`/`/permission` still only change the current session, avoiding a surprise "this also changes your permanent default" side effect. It shows the persisted default mode/permission tier (from `state.persisted_runtime`) and one `"<provider> api key: set|not set"` line per known provider (same generalization as `show`, via `state.secret_store`), plus a one-line hint pointing at `woven settings set`.

## Testing

`tests/conftest.py`'s autouse `_isolated_config_home` fixture sets `XDG_CONFIG_HOME` to a `tmp_path` subdirectory and unsets every provider's environment variable (iterating `PROVIDER_ENV_VARS`) for every test — so no test run ever touches the real `~/.config/woven/` or picks up a real API key from the developer's shell environment. This fixture is required infrastructure for any test that invokes `chat`/`settings` — every pre-existing `chat`-invoking test in `test_cli_app.py` depends on it implicitly.

- `tests/test_settings_store.py` — `load_config`/`save_config`, permissions, corrupt-file handling, `User.id` stability, and the legacy `gemini_api_key` migration.
- `tests/test_secret_store.py` — `FileSecretStore` get/set/delete, missing-file behavior, permission self-heal, `resolve_api_key` precedence.
- `tests/test_settings_resolve.py` — `resolve_runtime_config` precedence (CLI override > persisted > hardcoded default).
- `tests/test_cli_settings.py` — the `woven settings show`/`set` subcommand, including the hidden-prompt path for a secret field with no value argument.
- `tests/test_cli_app.py` — CLI-integration behavior: persisted defaults flowing into `chat`, flags overriding them, and the `/settings` display.

## Explicitly out of scope (this slice)

- No `Project` model or `User`↔`Project` ownership wiring — that's `.claude/plans/projects.md`.
- No multi-user/multi-profile support or profile-switching CLI surface.
- No real authentication (login, tokens, sessions) — no concrete consumer exists until a networked client does.
- No encryption beyond file permissions — no OS keychain, no `keyring` dependency.
- No "unset"/clear mechanism exposed via the CLI (`SecretStore.delete` exists as part of the protocol, but nothing calls it yet).
- No atomic replace (temp file + rename) on `save_config()`/`FileSecretStore` writes — a mid-write interruption could still leave a truncated file. Low severity (single local process, rare window); revisit only if it becomes a real issue.
- No implicit persistence from the `/mode`/`/permission` REPL commands — persistence only via the explicit `woven settings set` surface.
- No setup wizard / `doctor` diagnostics command — sequenced as its own roadmap item, `.claude/plans/setup-and-diagnostics.md`, directly after `model-providers.md`.

## Current implementation vs. future work

| Concept | Status |
|---|---|
| `User`/`Settings`/`Config` models | Implemented (`src/woven/settings/models.py`) |
| Persisted config file (`~/.config/woven/config.json`, `0600`) | Implemented (`src/woven/settings/store.py`) |
| `load_config`/`save_config`, first-run defaults, corrupt-file handling, write-error handling | Implemented |
| `SecretStore` protocol / `FileSecretStore` (`~/.config/woven/secrets.json`, `0600`) | Implemented (`src/woven/settings/secrets.py`) |
| Generalized per-provider credential keying (`PROVIDER_ENV_VARS`, `resolve_api_key`) | Implemented |
| One-time migration of a legacy `settings.gemini_api_key` into `secrets.json` | Implemented |
| `resolve_runtime_config` (centralized CLI-override/persisted/default merge) | Implemented (`src/woven/settings/resolve.py`) |
| CLI persisted-default threading into `chat` (`--mode`/`--permission-mode`) | Implemented |
| `woven settings show` / `woven settings set` (plain fields + hidden-prompt secret fields) | Implemented |
| `/settings` REPL display of persisted values | Implemented (read-only) |
| Real Gemini provider consuming the stored API key/`default_model_provider` | Implemented — `GeminiProvider`, see `docs/architecture/agent-runtime.md`'s Model abstraction section |
| Setup wizard / `doctor` diagnostics | Not implemented — `.claude/plans/setup-and-diagnostics.md` |
| Multi-profile / multi-user / real auth | Not implemented — `.claude/plans/projects.md` |
| OS keychain / encrypted secrets storage | Not implemented — plain file + `0600` is the current decision |

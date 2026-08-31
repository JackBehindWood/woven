# Examples

Public, self-contained demonstrations of how to use Woven — each script
should answer "how do I use this part of Woven?", demonstrate one concept or
workflow, and be understandable in isolation by someone outside this repo.

This directory is currently empty of scripts. That's intentional: examples
should exist because they demonstrate a real public API well, not to
populate the directory. See `../devtools/README.md` for interactive REPLs,
manual verification, provider experimentation, and anything else that isn't
a clean, standalone example yet.

## Configuration rule

Examples must not depend on repo-local developer configuration —
`devtools/.env`, its dotenv loader, or `FileSecretStore`'s developer-local
`~/.config/woven/secrets.json`. This is **not** a rule against provider
examples needing credentials: an example may legitimately read a standard,
documented environment variable directly (e.g.
`os.environ[woven.settings.PROVIDER_ENV_VARS["gemini"]]`) the same way any
real Woven deployment would. State the requirement plainly in the script's
docstring — e.g. "set `GEMINI_API_KEY` in your shell before running this" —
rather than reading from a private `.env` file.

## What belongs here vs. `devtools/`

- **Here:** a public API demo, self-contained, one concept, standard
  configuration only.
- **`devtools/`:** interactive REPLs, manual dev testing, provider
  experiments, repo-local secrets, container/sandbox dev documentation —
  see `../devtools/README.md`.

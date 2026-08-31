FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN useradd --create-home --uid 1000 sandbox
ENV XDG_CONFIG_HOME=/home/sandbox/.config

# Pre-create XDG_CONFIG_HOME, sandbox-owned, so the named
# woven-sandbox-config volume (docker-compose.yml) initializes from this
# directory's ownership on first mount instead of defaulting to root.
RUN mkdir -p "$XDG_CONFIG_HOME" && chown -R sandbox:sandbox /home/sandbox

WORKDIR /app
RUN chown sandbox:sandbox /app
USER sandbox

# No COPY of repo source: code arrives via the docker-compose.yml bind
# mount at run time, so a code edit never requires an image rebuild.
#
# ENTRYPOINT (not CMD) runs the sync: `docker compose run sandbox <args>`
# replaces CMD entirely, so a sync step in CMD would be skipped whenever a
# command is passed — leaving `uv run <cmd>` to sync only the base
# dependency group (no `cli`/`dev` extras). ENTRYPOINT's argv isn't
# replaced by `run`'s override; the override becomes its "$@" instead.
ENTRYPOINT ["sh", "-c", "uv sync --all-extras && exec \"$@\"", "--"]
CMD ["bash"]

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN useradd --create-home --uid 1000 sandbox
ENV XDG_CONFIG_HOME=/home/sandbox/.config

WORKDIR /app
RUN chown sandbox:sandbox /app
USER sandbox

# No COPY of repo source: code arrives via the docker-compose.yml bind
# mount at run time, so a code edit never requires an image rebuild.
CMD ["sh", "-c", "uv sync --all-extras && exec bash"]

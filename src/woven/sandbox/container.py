from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

from woven.sandbox.protocol import SandboxError, SandboxRequest, SandboxResult

_REPO_ROOT = Path(__file__).resolve().parents[3]


class ContainerSandbox:
    """Sandbox backed by `docker compose run --rm` (see docker-compose.yml)."""

    def __init__(
        self,
        compose_file: Path | None = None,
        service: str = "sandbox",
    ):
        self.compose_file = compose_file or (_REPO_ROOT / "docker-compose.yml")
        self.service = service

    def run(self, request: SandboxRequest) -> SandboxResult:
        if request.cwd is not None and PurePosixPath(request.cwd).is_absolute():
            raise SandboxError(
                f"SandboxRequest.cwd must be workspace-relative, got absolute "
                f"path: {request.cwd!r}"
            )

        argv = [
            "docker",
            "compose",
            "-f",
            str(self.compose_file),
            "run",
            "--rm",
            *(["--workdir", f"/app/{request.cwd}"] if request.cwd else []),
            self.service,
            *request.command,
        ]

        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=request.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return SandboxResult(
                exit_code=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                timed_out=True,
            )
        except FileNotFoundError as exc:
            raise SandboxError(
                "docker not found — install a Docker-API-compatible engine "
                "(OrbStack or colima recommended; see examples/README.md)"
            ) from exc

        return SandboxResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

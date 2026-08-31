import subprocess
from pathlib import Path

import pytest

from woven.sandbox import ContainerSandbox, SandboxError, SandboxRequest


def _sandbox() -> ContainerSandbox:
    return ContainerSandbox(compose_file=Path("/repo/docker-compose.yml"))


def test_run_builds_expected_argv_and_returns_result(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, returncode=0, stdout="hi\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = _sandbox()

    result = sandbox.run(SandboxRequest(command=["echo", "hi"]))

    assert captured["argv"] == [
        "docker",
        "compose",
        "-f",
        "/repo/docker-compose.yml",
        "run",
        "--rm",
        "sandbox",
        "echo",
        "hi",
    ]
    assert result.exit_code == 0
    assert result.stdout == "hi\n"
    assert result.timed_out is False


def test_relative_cwd_adds_workdir_flag(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = _sandbox()

    sandbox.run(SandboxRequest(command=["pytest"], cwd="tests"))

    assert captured["argv"] == [
        "docker",
        "compose",
        "-f",
        "/repo/docker-compose.yml",
        "run",
        "--rm",
        "--workdir",
        "/app/tests",
        "sandbox",
        "pytest",
    ]


def test_absolute_cwd_raises_without_calling_subprocess(monkeypatch):
    def fake_run(argv, **kwargs):
        raise AssertionError("subprocess.run must not be called for an absolute cwd")

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = _sandbox()

    with pytest.raises(SandboxError):
        sandbox.run(SandboxRequest(command=["ls"], cwd="/Users/x/tests"))


def test_nonzero_exit_code_is_a_normal_result_not_an_exception(monkeypatch):
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = _sandbox()

    result = sandbox.run(SandboxRequest(command=["false"]))

    assert result.exit_code == 1
    assert result.stderr == "boom"
    assert result.timed_out is False


def test_timeout_expired_surfaces_as_timed_out_result(monkeypatch):
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=argv, timeout=1, output="partial", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = _sandbox()

    result = sandbox.run(SandboxRequest(command=["sleep", "10"], timeout=1))

    assert result.exit_code is None
    assert result.timed_out is True
    assert result.stdout == "partial"


def test_missing_docker_binary_raises_sandbox_error(monkeypatch):
    def fake_run(argv, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = _sandbox()

    with pytest.raises(SandboxError):
        sandbox.run(SandboxRequest(command=["echo", "hi"]))

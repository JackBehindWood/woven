from typer.testing import CliRunner

from woven.client.cli.app import app

runner = CliRunner()


def test_help_shows_chat_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "chat" in result.stdout


def test_chat_session_echoes_fixed_response_and_exits_on_command():
    result = runner.invoke(
        app, ["chat", "--response", "pinned-reply"], input="hello\nexit\n"
    )

    assert result.exit_code == 0
    assert "pinned-reply" in result.stdout
    assert "Goodbye" in result.stdout


def test_chat_session_exits_cleanly_on_eof():
    result = runner.invoke(app, ["chat"], input="hello\n")

    assert result.exit_code == 0
    assert "Goodbye" in result.stdout


def test_chat_header_discloses_demo_model():
    result = runner.invoke(app, ["chat"], input="\n")

    assert "demo" in result.stdout.lower()
    assert "FakeModel" in result.stdout


def test_bare_invocation_starts_chat_directly():
    result = runner.invoke(app, [], input="hi\nexit\n")

    assert result.exit_code == 0
    assert "Goodbye" in result.stdout
    assert "demo model" in result.stdout.lower()


def test_chat_session_shows_banner_and_hint():
    result = runner.invoke(app, ["chat"], input="\n")

    assert "W O V E N" in result.stdout
    assert "exit" in result.stdout
    assert ":q" in result.stdout

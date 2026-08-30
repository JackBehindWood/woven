import typer

from woven.client.cli import registry
from woven.client.cli.app import app


def test_register_command_and_clear():
    registry.clear()

    @registry.register_command("probe")
    def _probe() -> None:
        pass

    assert ("probe", _probe) in registry.registered_commands()

    registry.clear()

    assert registry.registered_commands() == []


def test_register_group_and_clear():
    registry.clear()
    group = typer.Typer(name="probe-group")

    registry.register_group("probe-group")(group)

    assert ("probe-group", group) in registry.registered_groups()

    registry.clear()

    assert registry.registered_groups() == []


def test_app_has_all_known_commands_wired():
    command_names = set(typer.main.get_command(app).commands)

    assert {"chat", "setup", "doctor", "settings"} <= command_names

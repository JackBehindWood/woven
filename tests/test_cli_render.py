import io

from rich.console import Console

from woven.client.cli.console import make_console
from woven.client.cli.render import render_banner, render_event, render_hint
from woven.events import (
    Event,
    ModelCompleted,
    ModelStarted,
    RunCompleted,
    RunFailed,
    RunStarted,
    TurnCompleted,
    TurnStarted,
)
from woven.models import ModelRequest, ModelResponse


def _capturing_console() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return make_console(file=buffer, width=100, no_color=True), buffer


def test_render_banner_prints_wordmark():
    console, buffer = _capturing_console()

    render_banner(console)

    assert "W O V E N" in buffer.getvalue()


def test_render_hint_prints_exit_instructions():
    console, buffer = _capturing_console()

    render_hint(console)

    output = buffer.getvalue()
    assert "exit" in output
    assert "quit" in output
    assert ":q" in output


def test_turn_completed_renders_output_text():
    console, buffer = _capturing_console()

    render_event(TurnCompleted(turn_id="t1", output_text="hello world"), console)

    assert "hello world" in buffer.getvalue()


def test_run_failed_renders_error_message():
    console, buffer = _capturing_console()

    render_event(RunFailed(turn_id="t1", run_id="r1", error="boom"), console)

    output = buffer.getvalue()
    assert "Turn failed" in output
    assert "boom" in output


def test_model_started_and_completed_render_indicator_lines():
    console, buffer = _capturing_console()

    render_event(
        ModelStarted(
            turn_id="t1", request=ModelRequest(purpose="chat_reply", input_text="hi")
        ),
        console,
    )
    render_event(
        ModelCompleted(turn_id="t1", response=ModelResponse(text="hello")), console
    )

    output = buffer.getvalue()
    assert "Calling model" in output
    assert "Model responded" in output


def test_run_started_turn_started_run_completed_are_suppressed():
    console, buffer = _capturing_console()

    render_event(RunStarted(turn_id="t1", run_id="r1"), console)
    render_event(TurnStarted(turn_id="t1", mode_name="chat"), console)
    render_event(RunCompleted(turn_id="t1", run_id="r1"), console)

    assert buffer.getvalue() == ""


def test_unknown_event_type_falls_back_without_crashing():
    class _FutureEvent(Event):
        pass

    console, buffer = _capturing_console()

    render_event(_FutureEvent(turn_id="t1"), console)

    assert "_FutureEvent" in buffer.getvalue()

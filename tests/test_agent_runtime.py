import pytest

from woven.events import (
    ModelCompleted,
    ModelStarted,
    RunCompleted,
    RunFailed,
    RunStarted,
    TurnCompleted,
    TurnStarted,
)
from woven.models import FakeModel, ModelError
from woven.runtime import AgentRun, AgentRuntime


def test_run_turn_executes_and_returns_output():
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    turn = runtime.run_turn(run, "chat", "hi", FakeModel(response_text="hello"))

    assert turn.output_text == "hello"
    assert run.turns == [turn]


def test_run_turn_produces_expected_event_sequence():
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    turn = runtime.run_turn(run, "chat", "hi", FakeModel(response_text="hello"))

    assert [type(e) for e in turn.events] == [
        RunStarted,
        TurnStarted,
        ModelStarted,
        ModelCompleted,
        TurnCompleted,
        RunCompleted,
    ]
    assert turn.events == run.events


def test_model_node_receives_expected_request():
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")
    model = FakeModel(response_text="hello")

    runtime.run_turn(run, "chat", "hello world", model)

    assert len(model.received_requests) == 1
    assert model.received_requests[0].input_text == "hello world"


def test_multiple_turns_can_use_different_modes_on_same_run():
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")

    runtime.run_turn(run, "chat", "first", FakeModel(response_text="a"))
    runtime.run_turn(run, "chat", "second", FakeModel(response_text="b"))

    assert len(run.turns) == 2
    assert run.turns[0].output_text == "a"
    assert run.turns[1].output_text == "b"


def test_run_turn_failure_produces_failure_event_and_propagates():
    runtime = AgentRuntime()
    run = AgentRun(run_id="r1")
    model = FakeModel(raise_error=True)

    with pytest.raises(ModelError):
        runtime.run_turn(run, "chat", "hi", model)

    assert [type(e) for e in run.events] == [
        RunStarted,
        TurnStarted,
        ModelStarted,
        RunFailed,
    ]

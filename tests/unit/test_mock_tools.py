from woven.tools import MockTools, ToolError, ToolRequest


def test_mock_tools_returns_configured_result():
    tool = MockTools(output_text="done")

    result = tool.execute(ToolRequest(purpose="tool_call", input_text="hi"))

    assert result.output_text == "done"


def test_mock_tools_records_received_requests():
    tool = MockTools(output_text="done")
    request_one = ToolRequest(purpose="tool_call", input_text="first")
    request_two = ToolRequest(purpose="tool_call", input_text="second")

    tool.execute(request_one)
    tool.execute(request_two)

    assert tool.received_requests == [request_one, request_two]


def test_mock_tools_raises_when_configured():
    tool = MockTools(raise_error=True)

    try:
        tool.execute(ToolRequest(purpose="tool_call", input_text="hi"))
        assert False, "expected ToolError to be raised"
    except ToolError:
        pass

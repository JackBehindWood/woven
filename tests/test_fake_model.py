from woven.models import FakeModel, ModelError, ModelRequest


def test_fake_model_returns_configured_response():
    model = FakeModel(response_text="hello")

    response = model.generate(ModelRequest(purpose="chat_reply", input_text="hi"))

    assert response.text == "hello"


def test_fake_model_records_received_requests():
    model = FakeModel(response_text="hello")
    request_one = ModelRequest(purpose="chat_reply", input_text="first")
    request_two = ModelRequest(purpose="chat_reply", input_text="second")

    model.generate(request_one)
    model.generate(request_two)

    assert model.received_requests == [request_one, request_two]


def test_fake_model_raises_when_configured():
    model = FakeModel(raise_error=True)

    try:
        model.generate(ModelRequest(purpose="chat_reply", input_text="hi"))
        assert False, "expected ModelError to be raised"
    except ModelError:
        pass

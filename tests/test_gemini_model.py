import pytest
from google.genai import errors

from woven.context import ContextFile, ContextSnapshot
from woven.models import GeminiProvider, ModelError, ModelRequest


class _FakeGenaiResponse:
    def __init__(self, text: str | None):
        self.text = text


class _FakeGenaiModels:
    def __init__(
        self, response_text: str | None = "hello", *, error: Exception | None = None
    ):
        self.response_text = response_text
        self.error = error
        self.calls: list[dict[str, object]] = []

    def generate_content(self, *, model: str, contents: str) -> _FakeGenaiResponse:
        self.calls.append({"model": model, "contents": contents})
        if self.error is not None:
            raise self.error
        return _FakeGenaiResponse(self.response_text)


class _FakeGenaiClient:
    def __init__(
        self, *, response_text: str | None = "hello", error: Exception | None = None
    ):
        self.models = _FakeGenaiModels(response_text=response_text, error=error)


def test_generate_returns_response_text_from_client():
    client = _FakeGenaiClient(response_text="hi from gemini")
    provider = GeminiProvider(api_key="key", client=client)

    response = provider.generate(ModelRequest(purpose="chat_reply", input_text="hi"))

    assert response.text == "hi from gemini"


def test_generate_passes_model_id_and_input_text_as_contents():
    client = _FakeGenaiClient()
    provider = GeminiProvider(api_key="key", model_id="gemini-test-id", client=client)

    provider.generate(ModelRequest(purpose="chat_reply", input_text="hello there"))

    assert client.models.calls == [
        {"model": "gemini-test-id", "contents": "hello there"}
    ]


def test_generate_concatenates_context_files_with_input_text():
    client = _FakeGenaiClient()
    provider = GeminiProvider(api_key="key", client=client)
    context = ContextSnapshot(
        files=[ContextFile(path="notes.py", content="print('hi')")]
    )

    provider.generate(
        ModelRequest(
            purpose="chat_reply", input_text="what does this do?", context=context
        )
    )

    contents = client.models.calls[0]["contents"]
    assert "notes.py" in contents
    assert "print('hi')" in contents
    assert "what does this do?" in contents


def test_generate_raises_model_error_when_client_raises_api_error():
    api_error = errors.APIError(
        code=503,
        response_json={
            "error": {"message": "backend unavailable", "status": "UNAVAILABLE"}
        },
    )
    client = _FakeGenaiClient(error=api_error)
    provider = GeminiProvider(api_key="key", client=client)

    with pytest.raises(ModelError, match="backend unavailable"):
        provider.generate(ModelRequest(purpose="chat_reply", input_text="hi"))


@pytest.mark.parametrize("response_text", [None, ""])
def test_generate_raises_model_error_when_response_text_is_empty(response_text):
    client = _FakeGenaiClient(response_text=response_text)
    provider = GeminiProvider(api_key="key", client=client)

    with pytest.raises(ModelError, match="no text output"):
        provider.generate(ModelRequest(purpose="chat_reply", input_text="hi"))


def test_provider_exposes_provider_name_and_model_id():
    provider = GeminiProvider(
        api_key="key", model_id="gemini-test-id", client=_FakeGenaiClient()
    )

    assert provider.provider_name == "gemini"
    assert provider.model_id == "gemini-test-id"

import httpx
import pytest
from google.genai import errors

from woven.context import ContextFile, ContextSnapshot
from woven.models import GeminiProvider, ModelError, ModelRequest


class _FakeGenaiResponse:
    def __init__(self, text: str | None):
        self.text = text


class _FakeGenaiModels:
    def __init__(
        self,
        response_text: str | None = "hello",
        *,
        error: Exception | None = None,
        get_error: Exception | None = None,
    ):
        self.response_text = response_text
        self.error = error
        self.get_error = get_error
        self.calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []

    def generate_content(self, *, model: str, contents: str) -> _FakeGenaiResponse:
        self.calls.append({"model": model, "contents": contents})
        if self.error is not None:
            raise self.error
        return _FakeGenaiResponse(self.response_text)

    def get(self, *, model: str) -> object:
        self.get_calls.append({"model": model})
        if self.get_error is not None:
            raise self.get_error
        return object()


class _FakeGenaiClient:
    def __init__(
        self,
        *,
        response_text: str | None = "hello",
        error: Exception | None = None,
        get_error: Exception | None = None,
    ):
        self.models = _FakeGenaiModels(
            response_text=response_text, error=error, get_error=get_error
        )


def _api_error(code: int, message: str) -> errors.APIError:
    return errors.APIError(
        code=code,
        response_json={"error": {"message": message, "status": "ERROR"}},
    )


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


@pytest.mark.parametrize("exc_cls", [httpx.ConnectError, httpx.TimeoutException])
def test_generate_raises_model_error_on_network_failure(exc_cls):
    client = _FakeGenaiClient(error=exc_cls("boom"))
    provider = GeminiProvider(api_key="key", client=client)

    with pytest.raises(ModelError, match="Gemini unreachable: network error"):
        provider.generate(ModelRequest(purpose="chat_reply", input_text="hi"))


def test_check_connection_calls_models_get_with_model_id():
    client = _FakeGenaiClient()
    provider = GeminiProvider(api_key="key", model_id="gemini-test-id", client=client)

    provider.check_connection()

    assert client.models.get_calls == [{"model": "gemini-test-id"}]


@pytest.mark.parametrize("code", [401, 403])
def test_check_connection_raises_model_error_for_invalid_key(code):
    client = _FakeGenaiClient(get_error=_api_error(code, "bad key"))
    provider = GeminiProvider(api_key="key", client=client)

    with pytest.raises(ModelError, match="API key rejected"):
        provider.check_connection()


def test_check_connection_raises_model_error_for_real_world_invalid_key_response():
    # Google's live response to a bad key is 400/INVALID_ARGUMENT with an
    # "API key not valid" message, not 401/403 - verified against a real call.
    client = _FakeGenaiClient(
        get_error=_api_error(400, "API key not valid. Please pass a valid API key.")
    )
    provider = GeminiProvider(api_key="key", client=client)

    with pytest.raises(ModelError, match="API key rejected"):
        provider.check_connection()


def test_check_connection_treats_unrelated_400_as_generic_failure():
    client = _FakeGenaiClient(get_error=_api_error(400, "model not found"))
    provider = GeminiProvider(api_key="key", client=client)

    with pytest.raises(ModelError, match="Gemini request failed: model not found"):
        provider.check_connection()


def test_check_connection_raises_model_error_for_rate_limit():
    client = _FakeGenaiClient(get_error=_api_error(429, "slow down"))
    provider = GeminiProvider(api_key="key", client=client)

    with pytest.raises(ModelError, match="rate limited or quota exceeded"):
        provider.check_connection()


@pytest.mark.parametrize("code", [500, 503])
def test_check_connection_raises_model_error_for_service_unavailable(code):
    client = _FakeGenaiClient(get_error=_api_error(code, "down"))
    provider = GeminiProvider(api_key="key", client=client)

    with pytest.raises(ModelError, match="service unavailable"):
        provider.check_connection()


def test_check_connection_raises_model_error_for_other_api_error():
    client = _FakeGenaiClient(get_error=_api_error(418, "teapot"))
    provider = GeminiProvider(api_key="key", client=client)

    with pytest.raises(ModelError, match="Gemini request failed: teapot"):
        provider.check_connection()


@pytest.mark.parametrize("exc_cls", [httpx.ConnectError, httpx.TimeoutException])
def test_check_connection_raises_model_error_on_network_failure(exc_cls):
    client = _FakeGenaiClient(get_error=exc_cls("boom"))
    provider = GeminiProvider(api_key="key", client=client)

    with pytest.raises(ModelError, match="Gemini unreachable: network error"):
        provider.check_connection()


def test_check_connection_succeeds_when_get_does_not_raise():
    client = _FakeGenaiClient()
    provider = GeminiProvider(api_key="key", client=client)

    provider.check_connection()


def test_setup_hint_is_a_non_empty_string_accessible_on_the_class():
    assert isinstance(GeminiProvider.SETUP_HINT, str)
    assert GeminiProvider.SETUP_HINT

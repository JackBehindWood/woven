from __future__ import annotations

from typing import ClassVar

import httpx
from google import genai
from google.genai import errors

from woven.models.protocol import ModelError, ModelRequest, ModelResponse

DEFAULT_GEMINI_MODEL_ID = "gemini-3.7-flash"

_NETWORK_ERROR_MESSAGE = "Gemini unreachable: network error"
_NETWORK_EXCEPTIONS = (httpx.ConnectError, httpx.TimeoutException)


def _build_contents(request: ModelRequest) -> str:
    parts: list[str] = []
    if request.context is not None:
        for file in request.context.files:
            parts.append(f"{file.path}:\n{file.content}")
    parts.append(request.input_text)
    return "\n\n".join(parts)


def _is_invalid_key_error(exc: errors.APIError) -> bool:
    # Google's real-world response for a bad key is 400/INVALID_ARGUMENT with
    # an "API key not valid" message, not 401/403 as HTTP status alone would
    # suggest — confirmed against a live call with a bogus key. 401/403 are
    # kept as a defensive fallback in case that ever changes.
    if exc.code in (401, 403):
        return True
    return exc.code == 400 and "api key" in (exc.message or "").lower()


def _describe_connection_error(exc: errors.APIError) -> str:
    if _is_invalid_key_error(exc):
        return f"Gemini API key rejected: {exc.message}"
    if exc.code == 429:
        return f"Gemini rate limited or quota exceeded: {exc.message}"
    if exc.code is not None and 500 <= exc.code < 600:
        return f"Gemini service unavailable, try again later: {exc.message}"
    return f"Gemini request failed: {exc.message}"


class GeminiProvider:
    """Model implementation backed by the official google-genai SDK."""

    SETUP_HINT: ClassVar[str] = (
        "Get a free Gemini API key from Google AI Studio: "
        "https://aistudio.google.com/apikey"
    )

    def __init__(
        self,
        api_key: str,
        *,
        model_id: str = DEFAULT_GEMINI_MODEL_ID,
        client: genai.Client | None = None,
    ):
        self.provider_name = "gemini"
        self.model_id = model_id
        self._client = client or genai.Client(api_key=api_key)

    def generate(self, request: ModelRequest) -> ModelResponse:
        contents = _build_contents(request)
        try:
            response = self._client.models.generate_content(
                model=self.model_id, contents=contents
            )
        except errors.APIError as exc:
            raise ModelError(f"Gemini request failed: {exc.message}") from exc
        except _NETWORK_EXCEPTIONS as exc:
            raise ModelError(_NETWORK_ERROR_MESSAGE) from exc
        if not response.text:
            raise ModelError("Gemini returned no text output")
        return ModelResponse(text=response.text)

    def check_connection(self) -> None:
        try:
            self._client.models.get(model=self.model_id)
        except errors.APIError as exc:
            raise ModelError(_describe_connection_error(exc)) from exc
        except _NETWORK_EXCEPTIONS as exc:
            raise ModelError(_NETWORK_ERROR_MESSAGE) from exc

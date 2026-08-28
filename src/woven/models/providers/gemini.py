from __future__ import annotations

from google import genai
from google.genai import errors

from woven.models.protocol import ModelError, ModelRequest, ModelResponse

DEFAULT_GEMINI_MODEL_ID = "gemini-3.7-flash"


def _build_contents(request: ModelRequest) -> str:
    parts: list[str] = []
    if request.context is not None:
        for file in request.context.files:
            parts.append(f"{file.path}:\n{file.content}")
    parts.append(request.input_text)
    return "\n\n".join(parts)


class GeminiProvider:
    """Model implementation backed by the official google-genai SDK."""

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
        if not response.text:
            raise ModelError("Gemini returned no text output")
        return ModelResponse(text=response.text)

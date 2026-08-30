from woven.models.protocol import Model
from woven.models.providers.gemini import DEFAULT_GEMINI_MODEL_ID, GeminiProvider
from woven.models.providers.protocol import Provider

MODEL_PROVIDERS: dict[str, type[Model]] = {
    "gemini": GeminiProvider,
}

__all__ = [
    "DEFAULT_GEMINI_MODEL_ID",
    "MODEL_PROVIDERS",
    "GeminiProvider",
    "Provider",
]

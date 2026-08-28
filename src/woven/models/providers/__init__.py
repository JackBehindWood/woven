from collections.abc import Callable

from woven.models.protocol import Model
from woven.models.providers.gemini import DEFAULT_GEMINI_MODEL_ID, GeminiProvider
from woven.models.providers.protocol import Provider

MODEL_PROVIDERS: dict[str, Callable[[str], Model]] = {
    "gemini": lambda api_key: GeminiProvider(api_key=api_key),
}

__all__ = [
    "DEFAULT_GEMINI_MODEL_ID",
    "MODEL_PROVIDERS",
    "GeminiProvider",
    "Provider",
]

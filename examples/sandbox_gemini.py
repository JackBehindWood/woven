"""Interactive sandbox for GeminiProvider — manual smoke-testing, not pytest.

Usage:
    uv run examples/sandbox_gemini.py
    uv run examples/sandbox_gemini.py --model-id gemini-2.5-flash
    uv run examples/sandbox_gemini.py --context notes.py --prompt "what does this do?"

Requires a Gemini API key. Set `GEMINI_API_KEY` in examples/.env (copy
examples/.env.example) or in your process environment.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from woven.context import ContextFile, ContextSnapshot
from woven.models import ModelError, ModelRequest
from woven.models.providers import DEFAULT_GEMINI_MODEL_ID, GeminiProvider
from woven.settings import PROVIDER_ENV_VARS

_EXIT_WORDS = {"exit", "quit", ":q"}


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _load_context(path: str | None) -> ContextSnapshot | None:
    if path is None:
        return None
    content = Path(path).read_text()
    return ContextSnapshot(files=[ContextFile(path=path, content=content)])


def _run_once(
    provider: GeminiProvider, prompt: str, context: ContextSnapshot | None
) -> None:
    request = ModelRequest(purpose="chat_reply", input_text=prompt, context=context)
    try:
        response = provider.generate(request)
    except ModelError as exc:
        print(f"[error] {exc}")
        return
    print(response.text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default=DEFAULT_GEMINI_MODEL_ID)
    parser.add_argument(
        "--context", help="Path to a file to include as context on every prompt."
    )
    parser.add_argument(
        "--prompt", help="Send one prompt and exit, instead of starting a REPL."
    )
    args = parser.parse_args()

    _load_dotenv(Path(__file__).parent / ".env")
    api_key = os.environ.get(PROVIDER_ENV_VARS["gemini"])
    if api_key is None:
        print(
            "No Gemini API key configured. Set GEMINI_API_KEY, e.g. in "
            "examples/.env (copy examples/.env.example).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    provider = GeminiProvider(api_key=api_key, model_id=args.model_id)
    context = _load_context(args.context)
    print(f"GeminiProvider sandbox — model: {provider.model_id}")

    if args.prompt is not None:
        _run_once(provider, args.prompt, context)
        return

    print(f"Type a prompt, or one of {sorted(_EXIT_WORDS)} to quit.")
    while True:
        try:
            prompt = input("you > ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        stripped = prompt.strip()
        if not stripped:
            continue
        if stripped.lower() in _EXIT_WORDS:
            break
        _run_once(provider, stripped, context)


if __name__ == "__main__":
    main()

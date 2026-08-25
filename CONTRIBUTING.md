# Contributing to Woven

Thank you for your interest in contributing to Woven. We aim for a low-friction contribution process and welcome small, focused changes.

Getting started

1. Fork the repository and clone:

   git clone https://github.com/JackBehindWood/woven.git
   cd woven

2. Install Python 3.12.
3. Install uv (recommended):

   pip install uv

4. Install development dependencies:

   uv install -d

Development philosophy

- Keep changes small and focused. Open a single purpose PR per change (feature/*, fix/*, docs/*).
- Discuss large architectural changes before implementing them.
- Prefer deterministic tests that do not require external model providers or GPUs.
- Contributors should not need powerful AI hardware to run the core test suite.

Running tests

- Once tests exist, run them with:

  uv run pytest

- For linting/formatting, use ruff:

  uv run ruff check .

Pull request expectations

- Use a descriptive PR title and short description of what changed and why.
- Include how the change was tested.
- Mark whether the change affects architecture or public APIs.
- Keep PRs reviewable and avoid very large changes in a single PR.

License and copyright

By contributing you agree that your contributions will be licensed under the project's Apache-2.0 license.

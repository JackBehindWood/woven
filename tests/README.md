Tests

This repository follows a deterministic-first testing philosophy. Tests should be reliable on modest hardware and avoid nondeterministic dependencies.

Key points

- Prefer deterministic unit tests that don't require external model providers.
- FakeModel and MockTools will be provided as deterministic test fixtures in future work to enable testing of higher-level runtime behavior.
- Integration tests that require model providers, local inference, or external services should be separated and run only in optional CI lanes or by developers who opt-in.

At this foundation stage there are no runtime tests. Add tests under tests/ using pytest when adding implementation code.
